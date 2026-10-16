"""Multimodal chart analysis via Gemini or Claude vision (REST, via httpx)."""
import base64
import json
import re
from typing import Literal, Optional

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.config import settings

GEMINI_MODEL = "gemini-1.5-flash"
CLAUDE_MODEL = "claude-3-5-sonnet-latest"
TIMEOUT_SECONDS = 30.0


class VisionServiceError(Exception):
    """Base error for vision service failures."""


class VisionConfigError(VisionServiceError):
    """Missing/invalid provider configuration."""


class VisionAPIError(VisionServiceError):
    """The upstream LLM API failed."""


class VisionValidationError(VisionServiceError):
    """The model output did not match the required schema."""


class TimeframeRead(BaseModel):
    candlesticks: str = ""
    support_resistance: str = ""
    liquidity_sweeps: str = ""
    order_blocks: str = ""


class StructuralRead(BaseModel):
    m5: TimeframeRead = Field(default_factory=TimeframeRead, alias="5M")
    m15: TimeframeRead = Field(default_factory=TimeframeRead, alias="15M")
    h1: TimeframeRead = Field(default_factory=TimeframeRead, alias="1H")
    model_config = {"populate_by_name": True}


class VisionAnalysis(BaseModel):
    signal: Literal["BUY", "SELL", "HOLD"]
    confidence: float = Field(ge=0, le=100)
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    rr: Optional[float] = Field(default=None, ge=0)
    rationale: str
    structure: StructuralRead = Field(default_factory=StructuralRead)

    @model_validator(mode="after")
    def _check_levels(self):
        if self.signal in ("BUY", "SELL"):
            if None in (self.entry, self.stop_loss, self.take_profit):
                raise ValueError("entry, stop_loss and take_profit required for BUY/SELL")
            e, s, t = self.entry, self.stop_loss, self.take_profit
            if self.signal == "BUY" and not (s < e < t):
                raise ValueError("BUY requires stop_loss < entry < take_profit")
            if self.signal == "SELL" and not (t < e < s):
                raise ValueError("SELL requires take_profit < entry < stop_loss")
            if self.rr is None and e != s:
                self.rr = round(abs(t - e) / abs(e - s), 2)
        return self


SYSTEM_PROMPT = """You are an expert FX/price-action analyst. Analyze the provided chart screenshot.
If several labelled chart images are provided, one per timeframe, assess the higher-timeframe bias first, then refine with the lower timeframes; the "Active timeframe" is the execution timeframe.
Assess candlestick patterns, support/resistance, liquidity sweeps and order blocks across the 5M, 15M and 1H timeframes (infer what is visible; say "not visible" otherwise).
Be conservative: prefer HOLD when structure is unclear or a breakout looks unconfirmed.
Breakout discipline: only call a breakout BUY/SELL when a candle has CLOSED beyond the level with a solid body (not just a wick) and the move is retested or follows through; a wick beyond a level is a liquidity sweep/fakeout, which favours the opposite direction or HOLD.
High-volatility news: if the chart shows abnormally large candles, wide spreads/gaps, or the context mentions a high-impact event (FOMC, NFP, CPI, central bank, etc.), treat breakouts as likely false; return HOLD unless price has closed beyond the level on at least two consecutive candles and the stop sits beyond the news spike extreme. Cap confidence at 60 in these conditions.
Never let confidence exceed 75 unless 5M, 15M and 1H structure agree; with only one image provided, never exceed 75.
Respond with ONLY a JSON object, no markdown, in this exact shape:
{"signal":"BUY|SELL|HOLD","confidence":0-100,"entry":number|null,"stop_loss":number|null,"take_profit":number|null,"rr":number|null,
"rationale":"string",
"structure":{"5M":{"candlesticks":"","support_resistance":"","liquidity_sweeps":"","order_blocks":""},"15M":{...same...},"1H":{...same...}}}
For BUY: stop_loss < entry < take_profit. For SELL: take_profit < entry < stop_loss."""


def _build_prompt(symbol: str, timeframe: str, extra_context: str = "", frame_labels: Optional[list] = None) -> str:
    parts = [extra_context.strip()] if extra_context.strip() else []
    if frame_labels and len(frame_labels) > 1:
        parts.append(
            f"Symbol: {symbol}\nExecution timeframe: {timeframe}\n"
            f"{len(frame_labels)} chart images follow, in order: {', '.join(frame_labels)}. "
            "Assess the higher-timeframe bias first. Analyze these charts together."
        )
    else:
        parts.append(f"Symbol: {symbol}\nActive timeframe: {timeframe}\nAnalyze this chart.")
    return "\n\n".join(parts)


def _strip_b64(image_base64: str) -> str:
    if image_base64.startswith("data:"):
        image_base64 = image_base64.split(",", 1)[-1]
    image_base64 = image_base64.strip()
    try:
        base64.b64decode(image_base64, validate=True)
    except Exception as exc:
        raise VisionServiceError("image_base64 is not valid base64") from exc
    return image_base64


def _detect_mime(image_b64: str) -> str:
    head = base64.b64decode(image_b64[:64] + "=" * (-len(image_b64[:64]) % 4))
    if head.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _post(url: str, headers: dict, payload: dict) -> dict:
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise VisionAPIError(f"Request to LLM provider failed: {exc}") from exc
    if resp.status_code >= 400:
        raise VisionAPIError(f"LLM provider returned HTTP {resp.status_code}: {resp.text[:500]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise VisionAPIError("LLM provider returned non-JSON response") from exc


def _call_gemini(api_key: str, images: list, prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    parts = [{"text": prompt}]
    for label, img in images:
        if len(images) > 1:
            parts.append({"text": f"Chart image: {label}"})
        parts.append({"inline_data": {"mime_type": _detect_mime(img), "data": img}})
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    data = _post(url, {"x-goog-api-key": api_key}, payload)
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionAPIError(f"Unexpected Gemini response shape: {str(data)[:300]}") from exc


def _call_claude(api_key: str, images: list, prompt: str) -> str:
    content = []
    for label, img in images:
        if len(images) > 1:
            content.append({"type": "text", "text": f"Chart image: {label}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": _detect_mime(img), "data": img}})
    content.append({"type": "text", "text": prompt})
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 2000,
        "temperature": 0.2,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": content}],
    }
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    data = _post("https://api.anthropic.com/v1/messages", headers, payload)
    try:
        return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise VisionAPIError(f"Unexpected Claude response shape: {str(data)[:300]}") from exc


def _call_openrouter(api_key: str, images: list, prompt: str) -> str:
    url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if settings.OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
    if settings.OPENROUTER_APP_NAME:
        headers["X-Title"] = settings.OPENROUTER_APP_NAME
    content = [{"type": "text", "text": prompt}]
    for _label, img in images:
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:{_detect_mime(img)};base64,{img}"}}
        )
    payload = {
        "model": settings.OPENROUTER_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "response_format": {"type": "json_object"},
    }
    data = _post(url, headers, payload)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionAPIError(f"Unexpected OpenRouter response shape: {str(data)[:300]}") from exc


def parse_analysis(raw: str) -> VisionAnalysis:
    """Extract and validate JSON from raw model text."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        obj = json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise VisionValidationError(f"Model output contained no JSON: {raw[:300]}")
        try:
            obj = json.loads(m.group(0))
        except ValueError as exc:
            raise VisionValidationError(f"Model output was not valid JSON: {raw[:300]}") from exc
    if isinstance(obj, dict) and isinstance(obj.get("signal"), str):
        obj["signal"] = obj["signal"].strip().upper()
    try:
        return VisionAnalysis.model_validate(obj)
    except ValidationError as exc:
        raise VisionValidationError(f"Model output failed schema validation: {exc}") from exc


def analyze_chart(
    image_base64: Optional[str], symbol: str, timeframe: str, extra_context: str = "", frames: Optional[list] = None
) -> dict:
    """Analyze a base64 PNG chart; returns a validated dict.

    extra_context (e.g. memory-engine block) is prepended to the user prompt.
    """
    provider = (settings.LLM_PROVIDER or "openrouter").strip().lower()
    if provider not in ("gemini", "claude", "openrouter"):
        raise VisionConfigError(
            f"Unsupported LLM_PROVIDER '{settings.LLM_PROVIDER}' (use openrouter|gemini|claude)"
        )
    if not settings.LLM_API_KEY:
        raise VisionConfigError("LLM_API_KEY is not configured")
    if frames:
        images = [(str(f["timeframe"]), _strip_b64(f["image_base64"])) for f in frames]
    else:
        images = [(timeframe, _strip_b64(image_base64 or ""))]
    prompt = _build_prompt(symbol, timeframe, extra_context, [lbl for lbl, _ in images])
    call = {"gemini": _call_gemini, "claude": _call_claude, "openrouter": _call_openrouter}[provider]
    raw = call(settings.LLM_API_KEY, images, prompt)
    result = parse_analysis(raw).model_dump(by_alias=True)
    result["provider"] = provider
    return result

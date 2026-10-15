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
Assess candlestick patterns, support/resistance, liquidity sweeps and order blocks across the 5M, 15M and 1H timeframes (infer what is visible; say "not visible" otherwise).
Be conservative: prefer HOLD when structure is unclear or a breakout looks unconfirmed.
Respond with ONLY a JSON object, no markdown, in this exact shape:
{"signal":"BUY|SELL|HOLD","confidence":0-100,"entry":number|null,"stop_loss":number|null,"take_profit":number|null,"rr":number|null,
"rationale":"string",
"structure":{"5M":{"candlesticks":"","support_resistance":"","liquidity_sweeps":"","order_blocks":""},"15M":{...same...},"1H":{...same...}}}
For BUY: stop_loss < entry < take_profit. For SELL: take_profit < entry < stop_loss."""


def _build_prompt(symbol: str, timeframe: str, extra_context: str = "") -> str:
    parts = [extra_context.strip()] if extra_context.strip() else []
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


def _call_gemini(api_key: str, image_b64: str, prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/png", "data": image_b64}},
        ]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    data = _post(url, {"x-goog-api-key": api_key}, payload)
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionAPIError(f"Unexpected Gemini response shape: {str(data)[:300]}") from exc


def _call_claude(api_key: str, image_b64: str, prompt: str) -> str:
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 2000,
        "temperature": 0.2,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
            {"type": "text", "text": prompt},
        ]}],
    }
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    data = _post("https://api.anthropic.com/v1/messages", headers, payload)
    try:
        return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise VisionAPIError(f"Unexpected Claude response shape: {str(data)[:300]}") from exc


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


def analyze_chart(image_base64: str, symbol: str, timeframe: str, extra_context: str = "") -> dict:
    """Analyze a base64 PNG chart; returns a validated dict.

    extra_context (e.g. memory-engine block) is prepended to the user prompt.
    """
    provider = (settings.LLM_PROVIDER or "").strip().lower()
    if provider not in ("gemini", "claude"):
        raise VisionConfigError(f"Unsupported LLM_PROVIDER '{settings.LLM_PROVIDER}' (use gemini|claude)")
    if not settings.LLM_API_KEY:
        raise VisionConfigError("LLM_API_KEY is not configured")
    img = _strip_b64(image_base64)
    prompt = _build_prompt(symbol, timeframe, extra_context)
    call = _call_gemini if provider == "gemini" else _call_claude
    raw = call(settings.LLM_API_KEY, img, prompt)
    result = parse_analysis(raw).model_dump(by_alias=True)
    result["provider"] = provider
    return result

"""Live news + social sentiment via Tavily, summarized for trade-risk checks."""
import logging
import re
import time
from typing import Any, Literal, Optional

import httpx
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"

BULLISH_WORDS = {
    "surge", "surges", "rally", "rallies", "gain", "gains", "rise", "rises", "jump",
    "jumps", "climb", "climbs", "strengthen", "strengthens", "bullish", "hawkish",
    "upbeat", "beat", "beats", "higher", "soar", "soars",
}
BEARISH_WORDS = {
    "fall", "falls", "drop", "drops", "slump", "slumps", "decline", "declines",
    "plunge", "plunges", "weaken", "weakens", "bearish", "dovish", "miss", "misses",
    "lower", "slide", "slides", "tumble", "tumbles", "sell-off", "selloff",
}
HIGH_IMPACT_KEYWORDS = {
    "central_bank": ["fomc", "fed ", "ecb", "boj", "boe", "rate decision", "rate hike",
                     "rate cut", "interest rate", "powell", "lagarde", "central bank"],
    "economic_data": ["nfp", "non-farm", "nonfarm", "cpi", "inflation", "gdp",
                      "unemployment", "payrolls", "pmi", "retail sales"],
    "geopolitical": ["war", "sanction", "invasion", "tariff", "election", "attack"],
}
CURRENCY_TOPICS = {
    "USD": "US dollar Federal Reserve", "EUR": "euro ECB", "GBP": "British pound Bank of England",
    "JPY": "Japanese yen Bank of Japan", "AUD": "Australian dollar RBA",
    "NZD": "New Zealand dollar RBNZ", "CAD": "Canadian dollar Bank of Canada",
    "CHF": "Swiss franc SNB", "XAU": "gold", "BTC": "bitcoin",
}


class SentimentSummary(BaseModel):
    symbol: str
    sentiment: Literal["bullish", "bearish", "neutral"] = "neutral"
    summary: str = ""
    high_impact: bool = False
    high_impact_flags: dict[str, bool] = Field(default_factory=dict)
    headlines: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    available: bool = False
    error: Optional[str] = None


_cache: dict[str, tuple[float, SentimentSummary]] = {}


def _normalize(symbol: str) -> tuple[str, str, str]:
    clean = re.sub(r"[^A-Za-z]", "", (symbol or "").split(":")[-1]).upper()
    if len(clean) >= 6:
        return clean, clean[:3], clean[3:6]
    return clean, clean, ""


def _build_queries(symbol: str) -> list[str]:
    clean, base, quote = _normalize(symbol)
    topics = " ".join(t for t in (CURRENCY_TOPICS.get(base, base), CURRENCY_TOPICS.get(quote, quote)) if t)
    pair = f"{base}/{quote}" if quote else clean
    return [
        f"{pair} forex breaking news today {topics}",
        f"{pair} sentiment traders twitter x.com",
        "high impact economic events today central bank NFP CPI FOMC",
    ]


def _score(text: str) -> int:
    words = re.findall(r"[a-z\-]+", text.lower())
    return sum(w in BULLISH_WORDS for w in words) - sum(w in BEARISH_WORDS for w in words)


def _flags(text: str) -> dict[str, bool]:
    t = " " + text.lower() + " "
    return {k: any(w in t for w in kws) for k, kws in HIGH_IMPACT_KEYWORDS.items()}


def summarize_results(symbol: str, results: list[dict[str, Any]], answers: list[str] | None = None) -> SentimentSummary:
    """Pure function: turn raw Tavily results into a SentimentSummary."""
    clean, _, _ = _normalize(symbol)
    if not results and not answers:
        return SentimentSummary(symbol=clean, summary="No recent news found.", available=True)
    texts = [f"{r.get('title', '')}. {r.get('content', '')}" for r in results]
    texts += list(answers or [])
    score = sum(_score(t) for t in texts)
    flags: dict[str, bool] = {k: False for k in HIGH_IMPACT_KEYWORDS}
    for t in texts:
        for k, v in _flags(t).items():
            flags[k] = flags[k] or v
    sentiment = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"
    headlines, sources, seen = [], [], set()
    for r in results:
        title = (r.get("title") or "").strip()
        if title and title not in seen:
            seen.add(title)
            headlines.append(title)
            if r.get("url"):
                sources.append(r["url"])
    headlines, sources = headlines[:5], sources[:5]
    high = any(flags.values())
    summary = (answers[0].strip() if answers and answers[0] else "") or (
        f"{len(results)} recent items; net tone {sentiment}."
    )
    if high:
        active = ", ".join(k.replace("_", " ") for k, v in flags.items() if v)
        summary += f" High-impact catalysts mentioned ({active}); avoid trading against them."
    return SentimentSummary(
        symbol=clean, sentiment=sentiment, summary=summary[:600], high_impact=high,
        high_impact_flags=flags, headlines=headlines, sources=sources, available=True,
    )


def _degraded(symbol: str, reason: str) -> SentimentSummary:
    clean, _, _ = _normalize(symbol)
    return SentimentSummary(
        symbol=clean, summary=f"Sentiment unavailable: {reason}", available=False, error=reason,
    )


def get_sentiment(symbol: str, timeout: float | None = None) -> SentimentSummary:
    """Fetch and summarize news/sentiment for `symbol`. Never raises."""
    key = settings.SEARCH_API_KEY
    if not key:
        return _degraded(symbol, "SEARCH_API_KEY not configured")
    clean, _, _ = _normalize(symbol)
    ttl = settings.SEARCH_CACHE_TTL_SECONDS
    cached = _cache.get(clean)
    if cached and time.monotonic() - cached[0] < ttl:
        return cached[1]

    timeout = timeout or settings.SEARCH_TIMEOUT_SECONDS
    results: list[dict[str, Any]] = []
    answers: list[str] = []
    errors = 0
    try:
        with httpx.Client(timeout=timeout) as client:
            for i, q in enumerate(_build_queries(symbol)):
                try:
                    resp = client.post(TAVILY_URL, json={
                        "api_key": key, "query": q, "topic": "news", "days": 1,
                        "max_results": settings.SEARCH_MAX_RESULTS,
                        "include_answer": i == 0,
                        **({"include_domains": ["x.com", "twitter.com"]} if i == 1 else {}),
                    }, headers={"Authorization": f"Bearer {key}"})
                    resp.raise_for_status()
                    data = resp.json()
                    results.extend(data.get("results") or [])
                    if data.get("answer"):
                        answers.append(data["answer"])
                except (httpx.HTTPError, ValueError) as e:
                    errors += 1
                    logger.warning("Tavily query failed: %s", e)
    except Exception as e:  # noqa: BLE001 - graceful degradation
        logger.warning("Search service error: %s", e)
        return _degraded(symbol, "search request failed")

    if errors == 3:
        return _degraded(symbol, "search request failed")
    result = summarize_results(symbol, results, answers)
    _cache[clean] = (time.monotonic(), result)
    return result

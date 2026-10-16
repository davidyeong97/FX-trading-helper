# Integration tests, latency and prompt tuning

## Tests
`cd backend && pip install -r requirements.txt && pytest` (17 tests, vision and search mocked, in-memory SQLite).
Covers `/api/v1/analyze` (happy path, 422, error mapping 503/502/400), the trade outcome flow
(PATCH `/trades/{id}/outcome` -> lesson row), `/memory/stats`, lessons feeding the vision prompt,
and the loss-penalty behaviour below.

## Latency (target: round-trip < 3 s)
Round trip = capture -> compress -> upload -> LLM vision call -> Tavily search -> DB write -> render.

| Stage | Change / measurement |
|---|---|
| Image payload | Extension (`sidepanel.js: compressImage`) downscales to max 1280 px wide and re-encodes as JPEG q=0.72 before upload. `python tests/bench_compression.py` (synthetic 1920x1080 chart): flat chart 12 KiB PNG vs 42 KiB JPEG (flat synthetic charts compress well as PNG); noisy/antialiased chart 3.0 MiB PNG -> 68 KiB JPEG. Real TradingView captures sit between, typically a 5-20x reduction. |
| Backend overhead (mocked LLM/search) | < 250 ms/request asserted in `test_backend_overhead_is_small`; measured ~10 ms locally. |
| LLM call | Dominant cost. Smaller image means fewer input tokens and faster upload; Gemini 1.5 Flash is typically ~1-2 s. NOT measured here: no API key in the build environment, so end-to-end time must be confirmed on a live key. |
| Multi-timeframe | Each extra frame (max 3 via `frames[]`) adds one more image to the LLM request: input tokens, upload size and LLM latency grow roughly linearly per image (expect ~+0.5-1 s per extra frame on Gemini Flash; unmeasured, confirm on a live key). The 3 s target is for single-frame analysis; use 2-3 frames when accuracy matters more than speed. A single frame caps BUY/SELL confidence at 75 (`frame_guard` in response). |
| Search | Sentiment is fetched before the vision call, concurrently with the memory lookup, and fed into the prompt. Tavily has a 2 s timeout (`SEARCH_TIMEOUT_SECONDS`, default 2.0) and 120 s cache; cached/degraded path adds ~0 ms. High-impact news caps BUY/SELL confidence at 60 (`news_guard` in response). |

The backend sniffs JPEG/PNG/WebP magic bytes and sends the correct MIME type to the provider (OpenRouter/Gemini/Claude).

## Prompt changes (`vision_service.SYSTEM_PROMPT`)
- Breakout discipline: require a candle *close* beyond the level with a solid body; wicks = sweep/fakeout.
- High-volatility news: treat breakouts as false unless two consecutive closes beyond the level and the stop is beyond the news-spike extreme; otherwise HOLD; cap confidence at 60.
- Confidence above 75 requires 5M/15M/1H agreement.

## Loss -> confidence feedback
Prompt text alone is not guaranteed to move the model's confidence, so `memory_engine.adjust_confidence`
applies a deterministic adjustment to BUY/SELL signals: over the last 10 resolved trades with the same
symbol + timeframe + signal, penalty = 8 x losses - 3 x wins, clamped to [0, 30] points.
The stored/returned `confidence` is the adjusted value; `memory_insights.confidence_adjustment` exposes
raw and adjusted values. Verified in `test_logged_losses_lower_confidence_on_similar_setups`
(80 -> 72 -> 64) and `test_loss_penalty_scoped_to_similar_setup` (other timeframe/direction unaffected).

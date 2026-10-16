# 📈 FX Trading Helper (FX-Trading-Helper)

> **Context-Aware AI Trading Assistant** built as a Chrome Extension Side Panel. Combines 1-click chart vision analysis, live news sentiment, and a self-learning memory log for high-confidence trading signals.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Chrome Extension](https://img.shields.io/badge/manifest-v3-green.svg)
![Python](https://img.shields.io/badge/FastAPI-0.100%2B-blue.svg)

---

## 📌 Overview

**FX Trading Helper** eliminates the friction of manually taking chart screenshots, switching windows, and pasting prompts into LLM web chats. 

Operated directly alongside **TradingView, Binance Web, or WebBull** via the **Chrome Side Panel**, it captures your active chart canvas with a single click, automatically extracts ticker metadata (Symbol & Timeframe), and evaluates multi-timeframe price structures against real-time news sentiment. 

It features an integrated **Self-Learning Memory Log (SQLite)** that tracks prediction accuracy over time, feeding past trade post-mortems back into the AI model to continuously refine signal accuracy.

---

## ✨ Key Features

- 🧩 **Chrome Side Panel Integration:** Operates directly beside your live browser charts without context switching.
- ⚡ **1-Click Screen Capture & Auto-Metadata:** Grabs active chart region and extracts Symbol/Timeframe directly from page DOM.
- 👁️ **Multi-Timeframe Vision AI:** Evaluates candlestick structures, support/resistance, liquidity sweeps, and order blocks across 5M, 15M, and 1H intervals.
- 📰 **Live Market Sentiment Engine:** Fetches breaking financial news and X (Twitter) sentiment for the active pair to prevent trading against high-impact catalysts.
- 🧠 **Self-Learning Feedback Loop:** Logs every prediction into a local SQLite database. Tracked outcomes and post-mortem lessons are fed back into future prompts as context.
- 📊 **Risk & Confidence Scoring:** Provides explicit entry, stop-loss, take-profit levels, and an overall Confidence Rating (0–100%).

---

## 🏗️ System Architecture


```

┌─────────────────────────────────────────────────────────────────────────────┐
│                           CHROME BROWSER (TradingView)                       │
│                                                                             │
│ ┌─────────────────────────────────────────┐ ┌─────────────────────────────┐ │
│ │                                         │ │  CHROME SIDE PANEL          │ │
│ │          TradingView Chart              │ │ ┌─────────────────────────┐ │ │
│ │          (BTC/USD - 15M)                │ │ │ 🔘 "Analyze Chart"      │ │ │
│ │                                         │ │ └─────────────────────────┘ │ │
│ │                                         │ │                             │ │
│ │                                         │ │ 📊 Signal: STRONG BUY       │ │ │
│ │                                         │ │ 🎯 Target: 69,500           │ │ │
│ │                                         │ │ 🛑 Stop: 66,800             │ │ │
│ │                                         │ │                             │ │
│ │                                         │ │ 🧠 AI Memory Log:           │ │ │
│ │                                         │ │ "Win Rate on 15M OB: 72%" │ │ │
│ │                                         │ │                             │ │
│ └─────────────────────────────────────────┘ └─────────────────────────────┘ │
└────────────────────────────────────┬────────┴──────────────────────────────┘
│
▼ (REST API / Localhost)
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FASTAPI LOCAL BACKEND                            │
│                                                                             │
│  ┌────────────────────┐   ┌──────────────────────┐   ┌───────────────────┐  │
│  │  Vision AI Engine  │   │  News & Search Engine│   │ Self-Learning DB  │  │
│  │ (Gemini / Claude)  │   │   (Tavily / News)    │   │ (SQLite + Logs)   │  │
│  └────────────────────┘   └──────────────────────┘   └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘

```

---

## 🚀 Quick Start

### 1. Set Up Backend Server

```bash
# Clone repository
git clone https://github.com/davidyeong97/FX-trading-helper.git
cd FX-trading-helper/backend

# Virtual environment setup
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your LLM_API_KEY and SEARCH_API_KEY (see Configuration)

# Start FastAPI local server
uvicorn app.main:app --reload --port 8000
```

### 2. Load Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (toggle in top right).
3. Click **Load unpacked** and select the `FX-trading-helper/extension` directory.
4. Pin the **FX Trading Helper** extension and open the Side Panel on any chart page.

---

## ⚙️ Configuration

Backend settings are read from environment variables or `backend/.env` (see `backend/.env.example` and `backend/app/config.py`).

| Variable | Default | Description |
|---|---|---|
| `LLM_API_KEY` | _(empty)_ | API key for the vision LLM. `/api/v1/analyze` returns 503 until set. |
| `LLM_PROVIDER` | `gemini` | Vision provider: `gemini` or `claude`. |
| `SEARCH_API_KEY` | _(empty)_ | Tavily API key for news/sentiment. If empty, analysis runs without live news. |
| `SEARCH_TIMEOUT_SECONDS` | `2.0` | Timeout for the news search call. |
| `SEARCH_MAX_RESULTS` | `6` | Maximum search results fed into the prompt. |
| `SEARCH_CACHE_TTL_SECONDS` | `120` | How long search results per symbol are cached. |
| `DB_URL` | `sqlite:///./fx_helper.db` | SQLAlchemy database URL. |
| `CORS_ALLOW_ORIGINS` | `*` | Comma-separated allowed origins (e.g. `chrome-extension://<your-extension-id>`). |

See [backend/docs/TUNING.md](backend/docs/TUNING.md) for latency, prompt and confidence-feedback tuning.

---

## 🧭 Usage

**Single chart:** open a chart on TradingView (Binance/Webull are best-effort), open the side panel and click **Analyze Active Chart**. The panel shows the signal (BUY/SELL/HOLD), confidence, entry/SL/TP, R:R and memory insights. A single frame caps BUY/SELL confidence at 75.

**Multi-timeframe:** expand **Multi-timeframe**, switch the chart to a timeframe (e.g. 1H) and click **Capture this timeframe**; repeat for up to 3 frames (e.g. 1H, 15M, 5M), then click **Analyze N frames**.

**Marking outcomes:** after a trade plays out, use the outcome widget to mark it **WIN**, **LOSS** or **INVALID**. For a loss, add a post-mortem reason; it is stored as a lesson and fed into future prompts, and lowers confidence on similar setups (same symbol, timeframe and signal).

**Pending trades:** the **Pending trades** card lists analyses whose outcome is still `PENDING` so you can resolve them later.

---

## 🧪 Running tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

Vision and search calls are mocked and the database is in-memory SQLite, so no API keys are needed.

---

## 🛠️ Troubleshooting

- **Backend offline / "Cannot reach backend":** make sure `uvicorn app.main:app --port 8000` is running and check `http://localhost:8000/health` returns `{"status":"ok"}`.
- **Symbol not detected (shows `— / —`):** reload the chart page so the content script is injected, then retry. Binance/Webull selectors are best-effort and may break when those sites change.
- **CORS errors:** set `CORS_ALLOW_ORIGINS` in `backend/.env` to `*` or your `chrome-extension://<id>` origin and restart the backend.
- **Changing the backend URL:** edit the backend URL in the side panel **Settings** section (default `http://localhost:8000`); it is saved in extension storage.
- **503 on analyze:** `LLM_API_KEY` is not set (or `LLM_PROVIDER` is not `gemini`/`claude`).

---

## ⚠️ Disclaimer

This software is for educational and research purposes only. Do not use this tool for live financial execution without proper personal risk management.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.

---

## 🗺️ Project Structure & Implementation Plan

### 📁 Directory Tree

```

FX-trading-helper/
├── extension/                   # Manifest V3 Chrome Extension
│   ├── manifest.json            # Extension configuration & Side Panel API setup
│   ├── sidepanel.html           # UI layout for the side panel dashboard
│   ├── sidepanel.js             # Event handlers, screenshot trigger & backend API calls
│   ├── content.js               # Script for DOM scraping (Symbol & Timeframe extraction)
│   ├── background.js            # Service worker handling extension lifecycle
│   └── styles.css               # Styling for signals, confidence meters & memory log
│
├── backend/                     # Python FastAPI Local Server
│   ├── app/
│   │   ├── main.py              # FastAPI app initialization & route registration
│   │   ├── config.py            # API keys & system environment configurations
│   │   ├── api/
│   │   │   ├── analyze.py       # Endpoint: POST /api/v1/analyze (Vision + News + DB Memory)
│   │   │   ├── trades.py        # Endpoint: GET/POST /api/v1/trades (Log trade & update outcome)
│   │   │   └── memory.py        # Endpoint: GET /api/v1/memory/stats (Win rate & past lessons)
│   │   ├── services/
│   │   │   ├── vision_service.py # Gemini/Claude Vision API integration
│   │   │   ├── search_service.py # News & X/Twitter real-time web search integration
│   │   │   └── memory_engine.py  # Prompt enrichment logic using past post-mortems
│   │   └── db/
│   │       ├── database.py      # SQLite connection & session management
│   │       └── models.py        # SQLAlchemy models (TradeLog, LessonLog)
│   ├── tests/                   # pytest suite (vision + search mocked in conftest.py)
│   ├── docs/
│   │   └── TUNING.md            # Latency, prompt & confidence-feedback tuning notes
│   ├── pytest.ini
│   ├── requirements.txt
│   └── .env.example
│
├── README.md
├── LICENSE
└── .gitignore

```

---

### 📋 Phase-by-Phase Implementation Plan

#### Phase 1: Chrome Extension UI & Canvas Capture (Week 1)
- [x] **Manifest V3 Setup:** Configure `manifest.json` with permissions (`sidePanel`, `activeTab`, `scripting`, `tabs`).
- [x] **Side Panel UI:** Build `sidepanel.html` featuring:
  - "Analyze Active Chart" primary trigger button.
  - Signal Display Header (BUY / SELL / HOLD + Confidence Bar).
  - Collapsible Trade Details (Entry, Stop Loss, Take Profit, R:R).
  - Recent AI Lessons & Memory Log Widget.
- [x] **Tab Capture Scripting:** Implement `chrome.tabs.captureVisibleTab` in `sidepanel.js` to grab high-resolution PNG chart captures.
- [x] **DOM Metadata Scraper:** Write `content.js` to automatically extract ticker symbols and active interval parameters from TradingView DOM (`.single-symbol`, `.interval`). _TradingView is primary; Binance and Webull selectors are best-effort._

#### Phase 2: FastAPI Backend & AI Pipeline (Week 2)
- [x] **Core Server Setup:** Initialize FastAPI server with CORS middleware allowing local extension requests.
- [x] **Vision Processing Module:** Implement `vision_service.py` using multimodal APIs (Gemini Vision) to evaluate candlestick patterns, market structure, and key price levels from base64 image strings.
- [x] **Real-Time News Engine:** Implement `search_service.py` to fetch breaking sentiment and key macro events for extracted trading pairs.
- [x] **Unified Analysis Route (`POST /api/v1/analyze`):** Orchestrate multi-modal inputs into a single structured response JSON.

#### Phase 3: SQLite Database & Self-Learning Loop (Week 3)
- [x] **Database Schema:** Create `trades` and `lessons` tables in SQLite using SQLAlchemy:
  - `trades`: `id`, `symbol`, `timeframe`, `signal`, `confidence`, `entry`, `sl`, `tp`, `outcome_status` (PENDING/WIN/LOSS/INVALID), `created_at`.
  - `lessons`: `id`, `trade_id`, `post_mortem_reason`, `mistake_category`.
- [x] **Context Injection Engine:** Build `memory_engine.py` to retrieve relevant past trade post-mortems based on symbol/timeframe and inject them into the system prompt prior to vision inference.
- [x] **Outcome Feedback Interface:** Add a quick "Mark Win/Loss" feedback widget in the Chrome Side Panel so users can audit trade outcomes with 1-click.

#### Phase 4: Testing & Optimization (Week 4)
- [x] **Latency Tuning:** Optimize image compression before API transmission to keep analysis round-trip under 3 seconds. _Images are downscaled/JPEG-encoded; the live LLM round-trip is unmeasured without an API key (see TUNING.md)._
- [x] **Prompt Fine-Tuning:** Refine system prompts to eliminate false breakout signals during high-volatility news events.
- [x] **User Feedback Audit:** Verify that logged trade losses accurately modify subsequent prediction confidence in similar technical setups.

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
git clone [https://github.com/your-username/FX-trading-helper.git](https://github.com/your-username/FX-trading-helper.git)
cd FX-trading-helper/backend

# Virtual environment setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your LLM_API_KEY and SEARCH_API_KEY

# Start FastAPI local server
uvicorn app.main:app --reload --port 8000

```

### 2. Load Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (toggle in top right).
3. Click **Load unpacked** and select the `FX-trading-helper/extension` directory.
4. Pin the **FX Trading Helper** extension and open the Side Panel on any chart page.

---

## ⚠️ Disclaimer

This software is for educational and research purposes only. Do not use this tool for live financial execution without proper personal risk management.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.

```

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
│   ├── requirements.txt
│   └── .env.example
│
├── README.md
└── .gitignore

```

---

### 📋 Phase-by-Phase Implementation Plan

#### Phase 1: Chrome Extension UI & Canvas Capture (Week 1)
- [ ] **Manifest V3 Setup:** Configure `manifest.json` with permissions (`sidePanel`, `activeTab`, `scripting`, `tabs`).
- [ ] **Side Panel UI:** Build `sidepanel.html` featuring:
  - "Analyze Active Chart" primary trigger button.
  - Signal Display Header (BUY / SELL / HOLD + Confidence Bar).
  - Collapsible Trade Details (Entry, Stop Loss, Take Profit, R:R).
  - Recent AI Lessons & Memory Log Widget.
- [ ] **Tab Capture Scripting:** Implement `chrome.tabs.captureVisibleTab` in `sidepanel.js` to grab high-resolution PNG chart captures.
- [ ] **DOM Metadata Scraper:** Write `content.js` to automatically extract ticker symbols and active interval parameters from TradingView DOM (`.single-symbol`, `.interval`).

#### Phase 2: FastAPI Backend & AI Pipeline (Week 2)
- [ ] **Core Server Setup:** Initialize FastAPI server with CORS middleware allowing local extension requests.
- [ ] **Vision Processing Module:** Implement `vision_service.py` using multimodal APIs (Gemini Vision) to evaluate candlestick patterns, market structure, and key price levels from base64 image strings.
- [ ] **Real-Time News Engine:** Implement `search_service.py` to fetch breaking sentiment and key macro events for extracted trading pairs.
- [ ] **Unified Analysis Route (`POST /api/v1/analyze`):** Orchestrate multi-modal inputs into a single structured response JSON.

#### Phase 3: SQLite Database & Self-Learning Loop (Week 3)
- [ ] **Database Schema:** Create `trades` and `lessons` tables in SQLite using SQLAlchemy:
  - `trades`: `id`, `symbol`, `timeframe`, `signal`, `confidence`, `entry`, `sl`, `tp`, `outcome_status` (PENDING/WIN/LOSS/INVALID), `created_at`.
  - `lessons`: `id`, `trade_id`, `post_mortem_reason`, `mistake_category`.
- [ ] **Context Injection Engine:** Build `memory_engine.py` to retrieve relevant past trade post-mortems based on symbol/timeframe and inject them into the system prompt prior to vision inference.
- [ ] **Outcome Feedback Interface:** Add a quick "Mark Win/Loss" feedback widget in the Chrome Side Panel so users can audit trade outcomes with 1-click.

#### Phase 4: Testing & Optimization (Week 4)
- [ ] **Latency Tuning:** Optimize image compression before API transmission to keep analysis round-trip under 3 seconds.
- [ ] **Prompt Fine-Tuning:** Refine system prompts to eliminate false breakout signals during high-volatility news events.
- [ ] **User Feedback Audit:** Verify that logged trade losses accurately modify subsequent prediction confidence in similar technical setups.

---

<ElicitationsGroup message="How would you like to proceed with development?">
  <Elicitation label="Generate Chrome Extension boilerplate" query="Provide the full code for manifest.json, sidepanel.html, and sidepanel.js to start building the extension."/>
  <Elicitation label="Generate FastAPI backend code" query="Provide the FastAPI backend code structure with database models and the Gemini Vision integration endpoint."/>
</ElicitationsGroup>

```

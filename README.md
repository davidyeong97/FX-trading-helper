# 📈 FX Trading Helper (`FX-trading-helper`)

> **Context-Aware AI Trading Assistant & Self-Learning Chrome Extension**  
> Fusing multi-timeframe chart Vision AI with real-time web sentiment and historical trade memory directly inside your browser.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Chrome Extension](https://img.shields.io/badge/chrome-manifest_v3-green.svg)
![Python](https://img.shields.io/badge/python-fastapi_3.10+-blue.svg)

---

## 📌 Overview

**FX Trading Helper** eliminates the manual overhead of taking screenshots, cropping charts, and prompting AI tools. Built as a Chrome Side Panel extension, it captures active web charts (TradingView, Binance, Bybit) with a single click, extracts symbol/timeframe metadata from the page, and queries a Vision AI model.

The engine incorporates a **Self-Learning Feedback Loop** that tracks trade predictions, audits outcomes over time, and injects past lessons directly into system prompts to continuously refine signal accuracy.

---

## ✨ Key Features

- 🧩 **Chrome Side Panel HUD:** Runs directly alongside TradingView or exchange charts for a frictionless 1-click experience.
- 👁️ **Visual K-Line Analysis:** Analyzes candlestick patterns, order blocks, liquidity sweeps, and multi-timeframe structures visible on screen.
- 🌐 **Real-Time Sentiment Integration:** Scrapes and processes breaking market news and social sentiment for the active trading pair.
- 🧠 **Self-Learning Memory Log:** Records past predictions, checks actual trade outcomes, and uses historical post-mortems to adjust future confidence scores.
- 🎯 **Automated Metadata Extraction:** Automatically reads symbol (e.g., `BTCUSDT`) and timeframe (e.g., `15M`, `1H`) from page DOM/URLs.

---

## 🏗 System Architecture

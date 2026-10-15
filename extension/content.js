// Content script: scrapes the active symbol and timeframe from the page DOM.
// Message: { type: "FXTH_GET_CONTEXT" } -> { symbol, timeframe, source, url }
(() => {
  if (window.__fxthContentLoaded) return;
  window.__fxthContentLoaded = true;

  const MSG = "FXTH_GET_CONTEXT";
  const isTop = window.top === window;

  const text = (el) => (el && (el.getAttribute("data-symbol-short") || el.textContent) || "").trim();
  const firstText = (selectors, root = document) => {
    for (const sel of selectors) {
      try {
        const el = root.querySelector(sel);
        const t = text(el);
        if (t) return t;
      } catch (_) { /* invalid selector or detached DOM */ }
    }
    return null;
  };

  // Symbol like EURUSD, EUR/USD, BTCUSDT, BINANCE:BTCUSDT, XAUUSD, AAPL
  const SYMBOL_RE = /\b(?:[A-Z]{2,12}:)?([A-Z0-9]{2,10}(?:[/\-_][A-Z0-9]{2,10})?)\b/;
  function cleanSymbol(raw) {
    if (!raw) return null;
    const s = raw.toUpperCase().replace(/\s+/g, " ").trim();
    const m = s.match(SYMBOL_RE);
    if (!m) return null;
    return m[1].replace(/[/\-_]/g, "");
  }

  // Normalize timeframe to e.g. 1M, 5M, 15M, 1H, 4H, 1D, 1W
  function normalizeTimeframe(raw) {
    if (!raw) return null;
    const s = String(raw).trim().toLowerCase();
    let m = s.match(/^(\d+)\s*(s|sec|m|min|minutes?|h|hr|hours?|d|day|days?|w|week|weeks?|mo|month|months?)?$/);
    if (!m) return null;
    const n = m[1];
    const u = m[2];
    if (!u) {
      // TradingView raw numbers are minutes
      const mins = parseInt(n, 10);
      if (mins >= 60 && mins % 60 === 0) return `${mins / 60}H`;
      return `${mins}M`;
    }
    if (u === "s" || u === "sec") return `${n}S`;
    if (u === "m" || u.startsWith("min")) return `${n}M`;
    if (u === "h" || u === "hr" || u.startsWith("hour")) return `${n}H`;
    if (u === "d" || u.startsWith("day")) return `${n}D`;
    if (u === "w" || u.startsWith("week")) return `${n}W`;
    if (u === "mo" || u.startsWith("month")) return `${n}MO`;
    return null;
  }

  const TV_SYMBOL_SELECTORS = [
    '[data-name="legend-source-title"] .title-l31H9iuA',
    '[data-name="legend-source-title"]',
    "#header-toolbar-symbol-search .js-button-text",
    '#header-toolbar-symbol-search [class*="text"]',
    ".chart-markup-table .pane-legend-title__description",
    ".single-symbol",
    '[class*="symbolTitle"]',
    '[data-symbol-short]',
  ];
  const TV_INTERVAL_SELECTORS = [
    '#header-toolbar-intervals button[aria-checked="true"]',
    '#header-toolbar-intervals [class*="isActive"]',
    '#header-toolbar-intervals button[class*="selected"]',
    ".interval-active",
    ".interval .active",
    '[data-name="date-ranges-tabs"] [aria-checked="true"]',
  ];
  const BINANCE_SYMBOL_SELECTORS = [
    ".showPrice .name",
    '[class*="symbolName"]',
    '[class*="SymbolName"]',
    "#tradingPair",
    '[data-testid="symbol-name"]',
  ];
  const BINANCE_INTERVAL_SELECTORS = [
    '[class*="chart-interval"] [class*="active"]',
    '[class*="timeframe"] [class*="active"]',
    '[class*="Interval"] [class*="active"]',
    ".tab-item.active",
  ];
  const WEBULL_SYMBOL_SELECTORS = [
    ".csr122 .tit",
    '[class*="tickerName"]',
    '[class*="stockName"]',
    '[class*="symbol"] h1',
    "h1",
  ];
  const WEBULL_INTERVAL_SELECTORS = [
    '[class*="period"] [class*="active"]',
    '[class*="timeframe"] [class*="active"]',
    '[class*="tab"][class*="active"]',
  ];

  function hostGroup() {
    const h = location.hostname;
    if (/tradingview\.com$/.test(h)) return "tradingview";
    if (/binance\.(com|us)$/.test(h)) return "binance";
    if (/webull\.com$/.test(h)) return "webull";
    return "generic";
  }

  // Interval from URL query/path (TradingView ?interval=15, Binance /trade/BTC_USDT)
  function fromUrl() {
    let symbol = null, timeframe = null;
    try {
      const u = new URL(location.href);
      const sp = u.searchParams;
      symbol = cleanSymbol(sp.get("symbol") || sp.get("s"));
      timeframe = normalizeTimeframe(sp.get("interval") || sp.get("timeframe") || sp.get("tf"));
      if (!symbol) {
        const m = u.pathname.match(/\/(?:trade|futures|chart|quote)\/([A-Za-z0-9]{2,10}[_\-/]?[A-Za-z0-9]{0,10})/i);
        if (m) symbol = cleanSymbol(m[1]);
      }
    } catch (_) {}
    return { symbol, timeframe };
  }

  // Parse document.title, e.g. "EURUSD 1.0852 ▲ +0.1% - Unnamed", "BTCUSDT 65,000 | Binance"
  function fromTitle() {
    const t = (document.title || "").toUpperCase();
    if (!t) return { symbol: null, timeframe: null };
    const head = t.split(/[\s|–—-]{1,}\s*(?=[A-Z])/)[0] || t;
    let symbol = null;
    const m = t.match(/^\s*(?:[A-Z]{2,12}:)?([A-Z0-9]{2,10}(?:[/_][A-Z0-9]{2,10})?)\s+[\d.,]/) ||
              t.match(/^\s*(?:[A-Z]{2,12}:)?([A-Z0-9]{2,10}(?:[/_][A-Z0-9]{2,10})?)\b/);
    if (m) symbol = m[1].replace(/[/_]/g, "");
    else symbol = cleanSymbol(head);
    return { symbol, timeframe: null };
  }

  function scrape() {
    const group = hostGroup();
    const sets = {
      tradingview: [TV_SYMBOL_SELECTORS, TV_INTERVAL_SELECTORS],
      binance: [BINANCE_SYMBOL_SELECTORS, BINANCE_INTERVAL_SELECTORS],
      webull: [WEBULL_SYMBOL_SELECTORS, WEBULL_INTERVAL_SELECTORS],
      generic: [
        [...TV_SYMBOL_SELECTORS, ...BINANCE_SYMBOL_SELECTORS],
        [...TV_INTERVAL_SELECTORS, ...BINANCE_INTERVAL_SELECTORS, ...WEBULL_INTERVAL_SELECTORS],
      ],
    }[group];

    let symbol = null, timeframe = null, source = null;

    try {
      symbol = cleanSymbol(firstText(sets[0]));
      if (symbol) source = "dom";
    } catch (_) {}
    try {
      timeframe = normalizeTimeframe(firstText(sets[1]));
    } catch (_) {}

    const u = fromUrl();
    if (!symbol && u.symbol) { symbol = u.symbol; source = "url"; }
    if (!timeframe && u.timeframe) timeframe = u.timeframe;

    if (!symbol && isTop) {
      const t = fromTitle();
      if (t.symbol) { symbol = t.symbol; source = "title"; }
    }

    // Timeframe from TradingView widget title attribute, e.g. title="15 minutes"
    if (!timeframe) {
      try {
        const btn = document.querySelector('#header-toolbar-intervals [aria-checked="true"], #header-toolbar-intervals [data-value][class*="active" i]');
        if (btn) timeframe = normalizeTimeframe(btn.getAttribute("data-value") || btn.getAttribute("aria-label") || btn.title);
      } catch (_) {}
    }

    return { symbol: symbol || null, timeframe: timeframe || null, source, url: location.href };
  }

  try {
    chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
      if (!msg || msg.type !== MSG) return false;
      try {
        const res = scrape();
        // Sub-frames only answer when they found something so the top frame/chart frame wins.
        if (!isTop && !res.symbol && !res.timeframe) return false;
        sendResponse(res);
      } catch (e) {
        if (isTop) sendResponse({ symbol: null, timeframe: null, source: null, url: location.href });
      }
      return false;
    });
  } catch (_) { /* extension context invalidated */ }
})();

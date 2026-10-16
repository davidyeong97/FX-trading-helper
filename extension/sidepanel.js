(() => {
  const $ = (id) => document.getElementById(id);
  const DEFAULT_BASE_URL = "http://localhost:8000";
  const STORAGE_KEY = "backendUrl";
  const REQUEST_TIMEOUT_MS = 60000;

  let currentTradeId = null;

  const fmt = (v) => (v == null ? "—" : Number(v).toLocaleString());

  function setError(msg) {
    const el = $("error");
    el.textContent = msg || "";
    el.hidden = !msg;
  }

  const MAX_FRAMES = 3;
  let frames = [];
  let primaryTf = null;
  let busy = false;
  let lastInsights = { sentiment: null, rationale: "" };

  function setLoading(on, msg) {
    busy = on;
    $("analyze-btn").disabled = on;
    $("analyze-btn").textContent = on ? "Analyzing…" : "Analyze Active Chart";
    $("mtf-capture-btn").disabled = on;
    renderFrames();
    $("status").textContent = on ? msg || "Working…" : "";
  }

  function baseUrl() {
    const v = ($("backend-url").value || "").trim().replace(/\/+$/, "");
    return v || DEFAULT_BASE_URL;
  }

  async function loadSettings() {
    try {
      const s = await chrome.storage.local.get(STORAGE_KEY);
      $("backend-url").value = s[STORAGE_KEY] || DEFAULT_BASE_URL;
    } catch (_) {
      $("backend-url").value = DEFAULT_BASE_URL;
    }
  }

  $("backend-url").addEventListener("change", () => {
    try { chrome.storage.local.set({ [STORAGE_KEY]: baseUrl() }); } catch (_) {}
  });

  async function api(path, options = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
    let res;
    try {
      res = await fetch(baseUrl() + path, {
        ...options,
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
      });
    } catch (e) {
      if (e.name === "AbortError") throw new Error("Backend request timed out.");
      throw new Error(`Cannot reach backend at ${baseUrl()}. Is it running?`);
    } finally {
      clearTimeout(timer);
    }
    let body = null;
    try { body = await res.json(); } catch (_) {}
    if (!res.ok) {
      let detail = body && body.detail;
      if (Array.isArray(detail)) detail = detail.map((d) => d.msg).join("; ");
      throw new Error(detail || `Backend error ${res.status}`);
    }
    return body;
  }

  async function getActiveTab() {
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (!tab) throw new Error("No active tab found.");
    return tab;
  }

  async function captureChart(tab) {
    try {
      return await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
    } catch (e) {
      throw new Error("Could not capture the tab: " + (e.message || e));
    }
  }

  const MAX_IMAGE_WIDTH = 1280;
  const JPEG_QUALITY = 0.72;

  async function compressImage(dataUrl) {
    try {
      const blob = await (await fetch(dataUrl)).blob();
      const bmp = await createImageBitmap(blob);
      const scale = Math.min(1, MAX_IMAGE_WIDTH / bmp.width);
      const w = Math.round(bmp.width * scale);
      const h = Math.round(bmp.height * scale);
      const canvas = new OffscreenCanvas(w, h);
      const g = canvas.getContext("2d");
      g.fillStyle = "#fff";
      g.fillRect(0, 0, w, h);
      g.drawImage(bmp, 0, 0, w, h);
      const out = await canvas.convertToBlob({ type: "image/jpeg", quality: JPEG_QUALITY });
      const buf = new Uint8Array(await out.arrayBuffer());
      let bin = "";
      for (let i = 0; i < buf.length; i += 0x8000) {
        bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
      }
      return btoa(bin);
    } catch (_) {
      return dataUrl.replace(/^data:image\/\w+;base64,/, "");
    }
  }

  function getContext(tab) {
    return new Promise((resolve) => {
      try {
        chrome.tabs.sendMessage(tab.id, { type: "FXTH_GET_CONTEXT" }, (res) => {
          if (chrome.runtime.lastError) return resolve(null);
          resolve(res || null);
        });
      } catch (_) {
        resolve(null);
      }
    });
  }

  function renderMemory(mem, sentiment, rationale) {
    const items = [];
    if (mem) {
      const total = (mem.wins || 0) + (mem.losses || 0);
      if (total > 0 && mem.win_rate != null) {
        const rate = mem.win_rate <= 1 ? mem.win_rate * 100 : mem.win_rate;
        items.push(`Win rate on ${mem.symbol} ${mem.timeframe}: ${Math.round(rate)}% (${mem.wins}W / ${mem.losses}L)`);
      }
      for (const l of mem.lessons || []) {
        const reason = (l.reason || "").trim();
        items.push(`Past mistake [${l.mistake_category}] (${l.signal || l.outcome})` + (reason ? `: ${reason}` : ""));
      }
    }
    if (sentiment && sentiment.available && sentiment.summary) {
      items.push(`News (${sentiment.sentiment}${sentiment.high_impact ? ", high impact" : ""}): ${sentiment.summary}`);
    }
    if (rationale) items.push("AI rationale: " + rationale);
    const log = $("memory-log");
    if (!items.length) items.push("No insights yet.");
    log.replaceChildren(...items.map((m, i) => {
      const li = document.createElement("li");
      li.textContent = m;
      if (m === "No insights yet.") li.className = "muted";
      return li;
    }));
  }

  function render(r) {
    const signal = String(r.signal || "HOLD").toUpperCase();
    const conf = Math.max(0, Math.min(100, Math.round(Number(r.confidence) || 0)));
    const badge = $("signal-badge");
    badge.textContent = signal;
    badge.className = "badge " + signal.toLowerCase();
    $("confidence-text").textContent = conf + "%";
    $("confidence-bar").style.width = conf + "%";
    $("confidence-bar-wrap").setAttribute("aria-valuenow", conf);
    const t = r.trade || r;
    $("d-entry").textContent = fmt(t.entry);
    $("d-sl").textContent = fmt(t.sl);
    $("d-tp").textContent = fmt(t.tp);
    let rr = t.rr;
    if (rr == null && t.entry != null && t.sl != null && t.tp != null && t.entry !== t.sl) {
      rr = Math.abs(t.tp - t.entry) / Math.abs(t.entry - t.sl);
    }
    $("d-rr").textContent = rr == null ? "—" : "1:" + Number(rr).toFixed(2);
    lastInsights = { sentiment: r.sentiment || null, rationale: r.rationale || "" };
    renderMemory(r.memory_insights, lastInsights.sentiment, lastInsights.rationale);
    $("pair-meta").textContent = `${r.symbol} · ${r.timeframe}`;
    memSymbol = r.symbol;
    memTimeframe = r.timeframe;
    setLastTrade(r.trade_id == null ? null : r.trade_id);
    renderOutcomeWidget();
    $("outcome").textContent = "";
    loadPending();
  }

  async function analyze() {
    setError("");
    setLoading(true, "Capturing chart…");
    try {
      const tab = await getActiveTab();
      const dataUrl = await captureChart(tab);
      const image_base64 = await compressImage(dataUrl);
      setLoading(true, "Reading symbol and timeframe…");
      const ctx = await getContext(tab);
      const symbol = ctx && ctx.symbol;
      const timeframe = ctx && ctx.timeframe;
      if (!symbol || !timeframe) {
        throw new Error(
          "Could not detect " + (!symbol ? "symbol" : "timeframe") +
          ". Open a supported chart (TradingView, Binance, Webull) and reload the page."
        );
      }
      $("pair-meta").textContent = `${symbol} · ${timeframe}`;
      setLoading(true, "Analyzing chart with AI…");
      const result = await api("/api/v1/analyze", {
        method: "POST",
        body: JSON.stringify({ image_base64, symbol, timeframe }),
      });
      render(result);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  function renderFrames() {
    const n = frames.length;
    $("mtf-count").textContent = n ? `(${n})` : "";
    const btn = $("mtf-analyze-btn");
    btn.textContent = `Analyze ${n} frame${n === 1 ? "" : "s"}`;
    btn.disabled = busy || n === 0;
    $("mtf-chips").replaceChildren(...frames.map((f) => {
      const chip = el("span", "chip" + (f.timeframe === primaryTf ? " primary" : ""), f.timeframe);
      chip.title = f.timeframe === primaryTf ? "Primary timeframe" : "Click to make primary";
      chip.addEventListener("click", () => { primaryTf = f.timeframe; renderFrames(); });
      const x = el("button", null, "×");
      x.type = "button";
      x.title = "Remove";
      x.setAttribute("aria-label", "Remove " + f.timeframe);
      x.addEventListener("click", (ev) => {
        ev.stopPropagation();
        frames = frames.filter((g) => g !== f);
        if (primaryTf === f.timeframe) primaryTf = frames.length ? frames[frames.length - 1].timeframe : null;
        renderFrames();
      });
      chip.append(x);
      return chip;
    }));
  }

  async function captureFrame() {
    setError("");
    setLoading(true, "Capturing timeframe…");
    try {
      const tab = await getActiveTab();
      const dataUrl = await captureChart(tab);
      const image_base64 = await compressImage(dataUrl);
      const ctx = await getContext(tab);
      const symbol = ctx && ctx.symbol;
      const timeframe = ctx && ctx.timeframe;
      if (!symbol || !timeframe) {
        throw new Error(
          "Could not detect " + (!symbol ? "symbol" : "timeframe") +
          ". Open a supported chart (TradingView, Binance, Webull) and reload the page."
        );
      }
      if (frames.length && frames[0].symbol !== symbol) {
        frames = [];
        primaryTf = null;
      }
      const existing = frames.findIndex((f) => f.timeframe === timeframe);
      if (existing >= 0) frames.splice(existing, 1);
      else if (frames.length >= MAX_FRAMES) throw new Error(`Max ${MAX_FRAMES} frames. Remove one first.`);
      frames.push({ symbol, timeframe, image_base64 });
      primaryTf = timeframe;
      $("pair-meta").textContent = `${symbol} · ${timeframe}`;
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  async function analyzeFrames() {
    if (!frames.length) return;
    setError("");
    setLoading(true, `Analyzing ${frames.length} frame(s) with AI…`);
    try {
      const symbol = frames[0].symbol;
      const timeframe = frames.some((f) => f.timeframe === primaryTf) ? primaryTf : frames[frames.length - 1].timeframe;
      const result = await api("/api/v1/analyze", {
        method: "POST",
        body: JSON.stringify({
          symbol,
          timeframe,
          frames: frames.map((f) => ({ timeframe: f.timeframe, image_base64: f.image_base64 })),
        }),
      });
      render(result);
      frames = [];
      primaryTf = null;
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  const CATEGORIES = [
    ["", "Mistake category (optional)"],
    ["false_breakout", "False breakout"],
    ["news_spike", "News spike"],
    ["against_trend", "Against trend"],
    ["early_entry", "Early entry"],
    ["stop_too_tight", "Stop too tight"],
    ["other", "Other"],
  ];
  const MAX_REASON = 500;
  const LAST_TRADE_KEY = "lastTradeId";

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  async function submitOutcome(tradeId, outcome, category, reason) {
    const body = { outcome_status: outcome };
    if (reason) body.post_mortem_reason = reason.slice(0, MAX_REASON);
    if (category) body.mistake_category = category;
    await api(`/api/v1/trades/${tradeId}/outcome`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  }

  function buildOutcomeControls(tradeId, onDone) {
    const wrap = el("div", "outcome-controls");
    const btns = el("div", "row");
    const msg = el("div", "muted small");
    const form = el("div", "pm-form");
    form.hidden = true;
    const all = [];
    for (const [label, cls, outcome] of [["Win", "win", "WIN"], ["Loss", "loss", "LOSS"], ["Invalid", "invalid", "INVALID"]]) {
      const b = el("button", cls, label);
      b.type = "button";
      b.addEventListener("click", () => choose(outcome));
      all.push(b);
      btns.append(b);
    }
    const setBusy = (on) => all.forEach((b) => (b.disabled = on));

    async function finish(outcome, category, reason) {
      setError("");
      setBusy(true);
      form.hidden = true;
      msg.textContent = "Saving…";
      try {
        await submitOutcome(tradeId, outcome, category, reason);
        msg.textContent = `Marked as ${outcome}.`;
        onDone(outcome);
      } catch (e) {
        msg.textContent = "";
        setError(e.message || String(e));
        setBusy(false);
      }
    }

    function choose(outcome) {
      setError("");
      form.replaceChildren();
      const sel = el("select");
      for (const [v, t] of CATEGORIES) {
        const o = el("option", null, t);
        o.value = v;
        sel.append(o);
      }
      const ta = el("textarea");
      ta.maxLength = MAX_REASON;
      ta.rows = 3;
      ta.placeholder = "Short post-mortem reason (optional)";
      const count = el("div", "muted small", `0/${MAX_REASON}`);
      ta.addEventListener("input", () => (count.textContent = `${ta.value.length}/${MAX_REASON}`));
      const actions = el("div", "row");
      const save = el("button", "primary-sm", "Save");
      const skip = el("button", "secondary", "Skip");
      save.type = skip.type = "button";
      save.addEventListener("click", () => finish(outcome, sel.value, ta.value.trim()));
      skip.addEventListener("click", () => finish(outcome, "", ""));
      actions.append(save, skip);
      form.append(el("div", "small", `Why ${outcome}? (optional)`), sel, ta, count, actions);
      form.hidden = false;
      msg.textContent = "";
    }

    wrap.append(btns, form, msg);
    return wrap;
  }

  function setLastTrade(id) {
    currentTradeId = id;
    try {
      if (id == null) chrome.storage.local.remove(LAST_TRADE_KEY);
      else chrome.storage.local.set({ [LAST_TRADE_KEY]: id });
    } catch (_) {}
  }

  function renderOutcomeWidget() {
    const w = $("outcome-widget");
    if (currentTradeId == null) {
      w.replaceChildren(el("div", "muted small", "Run an analysis to mark its outcome."));
      return;
    }
    const tradeId = currentTradeId;
    w.replaceChildren(
      el("div", "muted small", `Trade #${tradeId}`),
      buildOutcomeControls(tradeId, () => {
        if (currentTradeId === tradeId) setLastTrade(null);
        $("outcome").textContent = "";
        loadPending();
        refreshMemory();
      })
    );
  }

  function ageText(iso) {
    const t = Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(iso || "") ? iso : (iso || "") + "Z");
    if (isNaN(t)) return "";
    const m = Math.max(0, Math.round((Date.now() - t) / 60000));
    if (m < 60) return `${m}m ago`;
    if (m < 1440) return `${Math.floor(m / 60)}h ago`;
    return `${Math.floor(m / 1440)}d ago`;
  }

  async function loadPending() {
    const list = $("pending-list");
    try {
      const trades = await api("/api/v1/trades?outcome_status=PENDING&limit=10");
      $("pending-count").textContent = trades.length ? `(${trades.length})` : "";
      if (!trades.length) {
        list.replaceChildren(el("div", "muted small", "No pending trades."));
        return;
      }
      list.replaceChildren(...trades.map((t) => {
        const row = el("div", "pending-row");
        const head = el("div", "pending-head");
        head.append(
          el("strong", null, `${t.symbol} · ${t.timeframe}`),
          el("span", "badge-sm " + String(t.signal).toLowerCase(), `${t.signal} ${Math.round(t.confidence)}%`),
          el("span", "muted small", ageText(t.created_at))
        );
        row.append(
          head,
          el("div", "small muted", `Entry ${fmt(t.entry)} · SL ${fmt(t.sl)} · TP ${fmt(t.tp)}`),
          buildOutcomeControls(t.id, () => {
            if (currentTradeId === t.id) {
              setLastTrade(null);
              renderOutcomeWidget();
            }
            loadPending();
            refreshMemory();
          })
        );
        return row;
      }));
    } catch (e) {
      $("pending-count").textContent = "";
      list.replaceChildren(el("div", "muted small", "Pending trades unavailable: " + (e.message || e)));
    }
  }

  let memSymbol = null;
  let memTimeframe = null;

  async function refreshMemory() {
    if (!memSymbol || !memTimeframe) return;
    const symbol = memSymbol, timeframe = memTimeframe;
    try {
      const st = await api("/api/v1/memory/stats?limit=50");
      if (symbol !== memSymbol || timeframe !== memTimeframe) return;
      const g = (st.by_symbol_timeframe || []).find((x) => x.symbol === symbol && x.timeframe === timeframe);
      const lessons = (st.recent_lessons || [])
        .filter((l) => l.symbol === symbol && l.timeframe === timeframe)
        .slice(0, 5);
      renderMemory({
        symbol, timeframe,
        wins: g ? g.wins : 0,
        losses: g ? g.losses : 0,
        win_rate: g ? g.win_rate : null,
        lessons,
      }, lastInsights.sentiment, lastInsights.rationale);
    } catch (_) {
      const li = el("li", "muted", "Memory unavailable (backend offline).");
      $("memory-log").replaceChildren(li);
    }
  }

  async function detectContext() {
    try {
      const tab = await getActiveTab();
      const ctx = await getContext(tab);
      if (ctx && ctx.symbol && ctx.timeframe) {
        const changed = ctx.symbol !== memSymbol || ctx.timeframe !== memTimeframe;
        memSymbol = ctx.symbol;
        memTimeframe = ctx.timeframe;
        $("pair-meta").textContent = `${memSymbol} · ${memTimeframe}`;
        if (changed) {
          lastInsights = { sentiment: null, rationale: "" };
          refreshMemory();
        }
      }
    } catch (_) {}
  }

  $("analyze-btn").addEventListener("click", analyze);
  $("mtf-capture-btn").addEventListener("click", captureFrame);
  $("mtf-analyze-btn").addEventListener("click", analyzeFrames);
  renderFrames();
  try {
    chrome.tabs.onActivated.addListener(() => detectContext());
    chrome.tabs.onUpdated.addListener((_id, info) => {
      if (info.status === "complete") detectContext();
    });
  } catch (_) {}

  (async () => {
    await loadSettings();
    try {
      const s = await chrome.storage.local.get(LAST_TRADE_KEY);
      if (s[LAST_TRADE_KEY] != null) currentTradeId = s[LAST_TRADE_KEY];
    } catch (_) {}
    renderOutcomeWidget();
    loadPending();
    detectContext();
  })();
})();

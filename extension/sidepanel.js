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

  function setLoading(on, msg) {
    $("analyze-btn").disabled = on;
    $("analyze-btn").textContent = on ? "Analyzing…" : "Analyze Active Chart";
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
        items.push(`Past mistake [${l.mistake_category}] (${l.signal}, ${l.outcome})` + (reason ? `: ${reason}` : ""));
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
    renderMemory(r.memory_insights, r.sentiment, r.rationale);
    $("pair-meta").textContent = `${r.symbol} · ${r.timeframe}`;
    currentTradeId = r.trade_id;
    $("win-btn").disabled = $("loss-btn").disabled = currentTradeId == null;
    $("outcome").textContent = "";
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

  async function mark(outcome) {
    if (currentTradeId == null) return;
    setError("");
    $("win-btn").disabled = $("loss-btn").disabled = true;
    $("outcome").textContent = "Saving…";
    try {
      await api(`/api/v1/trades/${currentTradeId}/outcome`, {
        method: "PATCH",
        body: JSON.stringify({ outcome_status: outcome }),
      });
      $("outcome").textContent = `Marked as ${outcome}.`;
      currentTradeId = null;
    } catch (e) {
      $("outcome").textContent = "";
      setError(e.message || String(e));
      $("win-btn").disabled = $("loss-btn").disabled = false;
    }
  }

  $("analyze-btn").addEventListener("click", analyze);
  $("win-btn").addEventListener("click", () => mark("WIN"));
  $("loss-btn").addEventListener("click", () => mark("LOSS"));
  loadSettings();
})();

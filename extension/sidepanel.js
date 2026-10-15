(() => {
  const $ = (id) => document.getElementById(id);
  const PLACEHOLDERS = [
    { signal: "BUY", confidence: 72, entry: 68200, sl: 66800, tp: 69500,
      memory: ["Win rate on 15M order blocks: 72%", "Past mistake: entered before news release"] },
    { signal: "SELL", confidence: 58, entry: 68200, sl: 69000, tp: 66500,
      memory: ["Win rate on 15M liquidity sweeps: 55%"] },
    { signal: "HOLD", confidence: 35, entry: null, sl: null, tp: null,
      memory: ["No clear structure; avoid trading."] },
  ];
  let idx = 0;

  const fmt = (v) => (v == null ? "—" : Number(v).toLocaleString());

  function render(r) {
    const badge = $("signal-badge");
    badge.textContent = r.signal;
    badge.className = "badge " + r.signal.toLowerCase();
    $("confidence-text").textContent = r.confidence + "%";
    $("confidence-bar").style.width = r.confidence + "%";
    $("confidence-bar-wrap").setAttribute("aria-valuenow", r.confidence);
    $("d-entry").textContent = fmt(r.entry);
    $("d-sl").textContent = fmt(r.sl);
    $("d-tp").textContent = fmt(r.tp);
    const rr = r.entry != null ? Math.abs(r.tp - r.entry) / Math.abs(r.entry - r.sl) : null;
    $("d-rr").textContent = rr == null ? "—" : "1:" + rr.toFixed(2);
    const log = $("memory-log");
    log.replaceChildren(...r.memory.map((m) => {
      const li = document.createElement("li");
      li.textContent = m;
      return li;
    }));
    $("pair-meta").textContent = "BTC/USD · 15M";
    $("win-btn").disabled = $("loss-btn").disabled = false;
    $("outcome").textContent = "";
  }

  $("analyze-btn").addEventListener("click", () => {
    const btn = $("analyze-btn");
    btn.disabled = true;
    $("status").textContent = "Analyzing (placeholder data)…";
    setTimeout(() => {
      render(PLACEHOLDERS[idx++ % PLACEHOLDERS.length]);
      $("status").textContent = "Done.";
      btn.disabled = false;
    }, 600);
  });

  function mark(outcome) {
    $("outcome").textContent = "Marked as " + outcome + " (local only).";
    $("win-btn").disabled = $("loss-btn").disabled = true;
  }
  $("win-btn").addEventListener("click", () => mark("WIN"));
  $("loss-btn").addEventListener("click", () => mark("LOSS"));
})();

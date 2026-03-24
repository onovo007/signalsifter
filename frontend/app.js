/**
 * SignalSifter v2.1 – Premium Frontend
 * Dr. Amobi Andrew Onovo · Quantium Insights LLC
 */

const API_BASE = window.SS_API_BASE || "https://signalsifter-api.onrender.com";

const state = {
  sessionId: null,
  columns: [],
  ivResults: null,
  selectedFeatures: new Set(),
  selectedExclude:  new Set(),
  ivHistory:  [],
  genHistory: [],
};

const $ = (id) => document.getElementById(id);

window.addEventListener("DOMContentLoaded", () => {
  checkApiHealth();
  initUpload();
  initBinsSlider();
  initRunButton();
  initAgents();
  initSidebar();
  initNavHighlight();
});

// ── API health ────────────────────────────────────────────────────────────────
async function checkApiHealth() {
  const dot = $("api-dot"), lbl = $("api-label");
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(7000) });
    if (res.ok) { dot.className = "api-dot ok"; lbl.textContent = "API Online"; }
    else throw new Error();
  } catch {
    dot.className = "api-dot err"; lbl.textContent = "API Offline";
  }
}

// ── Sidebar toggle (mobile) ───────────────────────────────────────────────────
function initSidebar() {
  $("menu-toggle").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });
}

// ── Upload ────────────────────────────────────────────────────────────────────
function initUpload() {
  const zone = $("drop-zone"), input = $("file-input");
  zone.addEventListener("click", () => input.click());
  input.addEventListener("change", () => { if (input.files[0]) handleFile(input.files[0]); });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("drag-over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault(); zone.classList.remove("drag-over");
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
}

async function handleFile(file) {
  showFeedback("Uploading…", "");
  const form = new FormData();
  form.append("file", file);
  try {
    const res  = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    state.sessionId = data.session_id;
    state.columns   = data.columns;
    state.ivHistory = []; state.genHistory = [];
    showFeedback(`✅ "${file.name}" — ${data.rows.toLocaleString()} rows · ${data.columns.length} columns`, "ok");
    renderPreview(data.preview, data.columns);
    populateColumnSelectors(data.columns);
    $("bins-row").classList.remove("hidden");
    $("preview-wrap").classList.remove("hidden");
    $("cols-section").classList.remove("hidden");
    $("cols-section").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showFeedback(`❌ ${err.message}`, "error");
  }
}

function showFeedback(msg, type) {
  const el = $("upload-feedback");
  el.textContent = msg;
  el.className = `feedback${type ? " " + type : ""}`;
  el.classList.remove("hidden");
}

// ── Preview ───────────────────────────────────────────────────────────────────
function renderPreview(rows, cols) {
  $("preview-table").innerHTML = buildTable(cols, rows);
  $("dataset-info").textContent = `First ${rows.length} rows · ${cols.length} columns`;
}

function buildTable(cols, rows, ivRow = false) {
  const thead = `<thead><tr>${cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>`;
  const tbody = `<tbody>${rows.map(r =>
    `<tr>${cols.map(c => {
      const val = r[c] ?? "";
      const isIV = ivRow && c === "IV";
      const style = isIV ? ` class="iv-cell" style="color:${ivColor(Number(val))}"` : "";
      return `<td${style}>${esc(String(val))}</td>`;
    }).join("")}</tr>`
  ).join("")}</tbody>`;
  return `<table>${thead}${tbody}</table>`;
}

// ── Bins slider ───────────────────────────────────────────────────────────────
function initBinsSlider() {
  const slider = $("bins-slider"), valEl = $("bins-val");
  const update = () => {
    valEl.textContent = slider.value;
    slider.style.setProperty("--pct", ((slider.value - 2) / 8 * 100) + "%");
  };
  slider.addEventListener("input", update);
  update();
}

// ── Column selectors ──────────────────────────────────────────────────────────
function populateColumnSelectors(cols) {
  const tgt = $("target-select");
  tgt.innerHTML = `<option value="">— select target —</option>`;
  cols.forEach(c => tgt.innerHTML += `<option value="${esc(c)}">${esc(c)}</option>`);
  tgt.addEventListener("change", updateRunButton);

  state.selectedFeatures.clear();
  state.selectedExclude.clear();
  buildChips("indep-wrap", cols, state.selectedFeatures, "teal");
  buildChips("excl-wrap",  cols, state.selectedExclude,  "excl");

  buildChips("gen-num-wrap", cols, new Set(), "teal");
  const gDep = $("gen-dep-select");
  gDep.innerHTML = `<option value="">— select —</option>`;
  cols.forEach(c => gDep.innerHTML += `<option value="${esc(c)}">${esc(c)}</option>`);
}

function buildChips(wrapId, cols, selectedSet, variant) {
  const wrap = $(wrapId);
  wrap.innerHTML = "";
  cols.forEach(col => {
    const chip = document.createElement("span");
    chip.className = `col-chip${variant === "excl" ? " excl" : ""}`;
    chip.textContent = col; chip.dataset.col = col;
    chip.addEventListener("click", () => {
      if (selectedSet.has(col)) { selectedSet.delete(col); chip.classList.remove("selected"); }
      else { selectedSet.add(col); chip.classList.add("selected"); }
      updateRunButton();
    });
    wrap.appendChild(chip);
  });
}

function updateRunButton() {
  $("run-btn").disabled = !($("target-select").value && state.selectedFeatures.size > 0);
}

// ── Run Analysis ──────────────────────────────────────────────────────────────
function initRunButton() { $("run-btn").addEventListener("click", runAnalysis); }

async function runAnalysis() {
  const target   = $("target-select").value;
  const features = [...state.selectedFeatures];
  const exclude  = [...state.selectedExclude];
  const bins     = parseInt($("bins-slider").value);

  const section = $("analysis-section");
  section.classList.remove("hidden");
  $("analysis-spinner").classList.remove("hidden");
  section.scrollIntoView({ behavior: "smooth", block: "start" });

  ["stat-strip","iv-chart","summary-table","summary-header","woe-table",
   "woe-header","rec-cards","rec-header","rec-loading"]
    .forEach(id => $(id).classList.add("hidden"));

  try {
    const res  = await fetch(`${API_BASE}/api/analyse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, target, features, exclude, bins }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Analysis failed");
    state.ivResults = data;
    renderAnalysisResults(data);
    // Kick off LLM recommendations asynchronously
    fetchLLMRecommendations();
  } catch (err) {
    alert(`Analysis error: ${err.message}`);
  } finally {
    $("analysis-spinner").classList.add("hidden");
  }
}

function renderAnalysisResults(data) {
  const m = data.metrics;
  $("m-total").textContent = m.total; $("m-vs").textContent = m.very_strong;
  $("m-s").textContent = m.strong;    $("m-m").textContent = m.moderate;
  $("m-w").textContent = m.weak;      $("m-n").textContent = m.not_useful;
  $("m-avg").textContent = m.avg_iv;
  $("stat-strip").classList.remove("hidden");

  const fig = JSON.parse(data.chart);
  const chartEl = $("iv-chart");
  chartEl.classList.remove("hidden");
  Plotly.newPlot(chartEl, fig.data, {
    ...fig.layout,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor:  "rgba(0,0,0,.15)",
    font: { color: "#8da4cc", family: "DM Sans, sans-serif" },
    xaxis: { ...fig.layout.xaxis, gridcolor: "rgba(255,255,255,.05)", color: "#8da4cc" },
    yaxis: { ...fig.layout.yaxis, gridcolor: "rgba(255,255,255,.05)", color: "#8da4cc" },
    title: { ...fig.layout.title, font: { color: "#e8f0ff", family: "Syne, sans-serif", size: 17 } },
    margin: { l: 160, r: 110, t: 60, b: 50 },
  }, { responsive: true, displaylogo: false });

  const sumCols = ["feature","IV","Gini","KS_Statistic"];
  $("summary-table").innerHTML = buildTable(sumCols, data.summary, true);
  $("summary-header").classList.remove("hidden");
  $("summary-table").classList.remove("hidden");

  if (data.woe_top3?.length) {
    const woeCols = Object.keys(data.woe_top3[0]);
    $("woe-table").innerHTML = buildTable(woeCols, data.woe_top3);
    $("woe-header").classList.remove("hidden");
    $("woe-table").classList.remove("hidden");
  }

  // Show rec header + loading spinner
  $("rec-header").classList.remove("hidden");
  $("rec-loading").classList.remove("hidden");
}

async function fetchLLMRecommendations() {
  try {
    const res  = await fetch(`${API_BASE}/api/llm-recommendations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, question: "" }),
    });
    const data = await res.json();
    $("rec-loading").classList.add("hidden");
    if (!res.ok || !data.recommendations?.length) {
      $("rec-cards").innerHTML = `<p style="color:var(--txt-3);font-size:.85rem">Could not generate AI recommendations. Try asking the IV Expert agent directly.</p>`;
      $("rec-cards").classList.remove("hidden");
      return;
    }
    renderRecCards(data.recommendations);
  } catch {
    $("rec-loading").classList.add("hidden");
  }
}

function renderRecCards(recs) {
  $("rec-cards").innerHTML = recs.map((r, i) => `
    <div class="rec-card" style="--rc-color:${r.color}; animation-delay:${i * 0.06}s">
      <div class="rec-head">
        <span class="rec-feat">${esc(r.feature)}</span>
        <span class="rec-label">${esc(r.label)}</span>
      </div>
      <div class="rec-meta">IV ${r.iv} · Gini ${r.gini} · KS ${r.ks}</div>
      <div class="rec-body">
        <strong>${esc(r.action)}</strong>
        <p style="margin-top:.35rem">${esc(r.narrative)}</p>
        <ul class="rec-steps">${r.steps.map(s => `<li>${esc(s)}</li>`).join("")}</ul>
      </div>
    </div>
  `).join("");
  $("rec-cards").classList.remove("hidden");
}

// ── Agents ────────────────────────────────────────────────────────────────────
function initAgents() {
  $("iv-ask-btn").addEventListener("click", askIVAgent);
  $("iv-question").addEventListener("keydown", (e) => { if (e.key==="Enter"&&!e.shiftKey){e.preventDefault();askIVAgent();} });
  document.querySelectorAll(".ppill").forEach(btn => {
    btn.addEventListener("click", () => { $("iv-question").value = btn.dataset.q; askIVAgent(); });
  });
  $("gen-ask-btn").addEventListener("click", askGeneralAgent);
  $("gen-question").addEventListener("keydown", (e) => { if (e.key==="Enter"&&!e.shiftKey){e.preventDefault();askGeneralAgent();} });
  $("iv-clear-btn").addEventListener("click",  () => clearChat("iv-chat-box",  "ivHistory"));
  $("gen-clear-btn").addEventListener("click", () => clearChat("gen-chat-box", "genHistory", "gen-plot"));
}

async function askIVAgent() {
  const q = $("iv-question").value.trim();
  if (!q || !state.sessionId) return;
  appendChat("iv-chat-box", "user", q);
  state.ivHistory.push({ role:"user", content:q });
  $("iv-question").value = "";
  $("iv-spinner").classList.remove("hidden");
  $("iv-ask-btn").disabled = true;
  try {
    const res  = await fetch(`${API_BASE}/api/iv-agent`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ session_id: state.sessionId, question: q }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    appendChat("iv-chat-box", "assistant", data.answer);
    state.ivHistory.push({ role:"assistant", content:data.answer });
  } catch (err) { appendChat("iv-chat-box","assistant",`Error: ${err.message}`); }
  finally { $("iv-spinner").classList.add("hidden"); $("iv-ask-btn").disabled=false; }
}

async function askGeneralAgent() {
  const q = $("gen-question").value.trim();
  if (!q || !state.sessionId) return;
  const numCols = [...$("gen-num-wrap").querySelectorAll(".col-chip.selected")].map(c=>c.dataset.col);
  const depCol  = $("gen-dep-select").value;
  appendChat("gen-chat-box","user",q);
  state.genHistory.push({ role:"user", content:q });
  $("gen-question").value = "";
  $("gen-spinner").classList.remove("hidden");
  $("gen-ask-btn").disabled = true;
  try {
    const res  = await fetch(`${API_BASE}/api/general-agent`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({
        session_id: state.sessionId, question:q,
        num_cols:numCols, dep_col:depCol,
        history: state.genHistory.slice(-10),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    appendChat("gen-chat-box","assistant",data.text,true);
    state.genHistory.push({ role:"assistant", content:data.text });
    if (data.plotly_json) renderPlotlyChart("gen-plot", data.plotly_json);
  } catch (err) { appendChat("gen-chat-box","assistant",`Error: ${err.message}`); }
  finally { $("gen-spinner").classList.add("hidden"); $("gen-ask-btn").disabled=false; }
}

function renderPlotlyChart(id, plotlyJson) {
  const el = $(id);
  el.classList.remove("hidden"); el.innerHTML = "";
  try {
    const fig = JSON.parse(plotlyJson);
    Plotly.newPlot(el, fig.data, {
      ...(fig.layout||{}),
      paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"rgba(0,0,0,.15)",
      font:{ color:"#8da4cc", family:"DM Sans, sans-serif" },
      margin:{ l:60, r:30, t:60, b:60 },
    }, { responsive:true, displaylogo:false });
  } catch(e) {
    el.innerHTML = `<p style="color:var(--red);padding:1rem">Chart error: ${e.message}</p>`;
  }
}

// ── Chat helpers ──────────────────────────────────────────────────────────────
function appendChat(boxId, role, text, renderCode=false) {
  const box = $(boxId);
  box.querySelector(".chat-empty")?.remove();
  const wrap = document.createElement("div");
  wrap.className = `chat-msg ${role}`;
  const content = renderCode ? formatWithCode(text) : `<div class="chat-bubble">${esc(text)}</div>`;
  wrap.innerHTML = `<span class="chat-role">${role==="user"?"You":"AI Expert"}</span>${content}`;
  box.appendChild(wrap);
  box.scrollTop = box.scrollHeight;
}

function formatWithCode(text) {
  return text.split(/(```(?:python|sql|bash)?\s*[\s\S]*?```)/g).map(part => {
    const m = part.match(/```(python|sql|bash)?\s*([\s\S]*?)```/);
    if (m) {
      const lang = m[1]||"python", code = esc(m[2].trim());
      return `<div class="code-block"><div class="code-header"><span class="code-lang">${lang}</span><button class="copy-btn" onclick="copyCode(this)">Copy</button></div><pre><code>${code}</code></pre></div>`;
    }
    const html = esc(part).replace(/\*\*(.*?)\*\*/g,"<strong>$1</strong>").replace(/\*(.*?)\*/g,"<em>$1</em>").replace(/\n/g,"<br>");
    return `<div class="chat-bubble">${html}</div>`;
  }).join("");
}

function copyCode(btn) {
  navigator.clipboard.writeText(btn.closest(".code-block").querySelector("code").textContent)
    .then(()=>{ btn.textContent="Copied!"; setTimeout(()=>btn.textContent="Copy",2000); });
}

function clearChat(boxId, historyKey, plotId=null) {
  $(boxId).innerHTML = `<div class="chat-empty">Conversation cleared.</div>`;
  state[historyKey] = [];
  if (plotId) { const el=$(plotId); if(el){el.innerHTML="";el.classList.add("hidden");} }
}

// ── Nav highlight ──────────────────────────────────────────────────────────────
function initNavHighlight() {
  const items = document.querySelectorAll(".sidenav-item");
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting)
        items.forEach(l => l.classList.toggle("active", l.dataset.section===e.target.id));
    });
  }, { threshold: 0.4 });
  ["upload-section","analysis-section","agent-section","general-section"]
    .forEach(id => { const el=$(id); if(el) obs.observe(el); });
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#039;");
}
function ivColor(iv) {
  if (iv>0.5)  return "#22c55e";
  if (iv>=0.3) return "#86efac";
  if (iv>=0.1) return "#fcd34d";
  if (iv>=0.02)return "#f87171";
  return "#6b7280";
}

/**
 * SignalSifter – Frontend Application
 * Dr. Amobi Andrew Onovo · Quantium Insights LLC
 */

// ══ Config ═══════════════════════════════════════════════════════════════════
// Replace this URL with your Render service URL after deployment.
// For local dev: http://localhost:8000
const API_BASE = window.SS_API_BASE || "https://signalsifter-api.onrender.com";

// ══ State ═════════════════════════════════════════════════════════════════════
const state = {
  sessionId: null,
  columns: [],
  ivResults: null,
  selectedFeatures: new Set(),
  selectedExclude: new Set(),
};

// ══ DOM refs ══════════════════════════════════════════════════════════════════
const $ = (id) => document.getElementById(id);

// ══ On load ═══════════════════════════════════════════════════════════════════
window.addEventListener("DOMContentLoaded", () => {
  checkApiHealth();
  initUpload();
  initBinsSlider();
  initRunButton();
  initAgents();
  initNavHighlight();
});

// ══ Health check ══════════════════════════════════════════════════════════════
async function checkApiHealth() {
  const dot  = $("api-status-dot");
  const text = $("api-status-text");
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(7000) });
    if (res.ok) {
      dot.className  = "status-dot ok";
      text.textContent = "API Online";
    } else {
      throw new Error("non-200");
    }
  } catch {
    dot.className  = "status-dot error";
    text.textContent = "API Offline";
  }
}

// ══ Upload ════════════════════════════════════════════════════════════════════
function initUpload() {
  const zone  = $("drop-zone");
  const input = $("file-input");

  zone.addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    if (input.files[0]) handleFile(input.files[0]);
  });

  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("drag-over"); });
  zone.addEventListener("dragleave", ()  => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
}

async function handleFile(file) {
  showFeedback("Uploading…", "");
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res  = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");

    state.sessionId = data.session_id;
    state.columns   = data.columns;

    showFeedback(`✅ Uploaded "${file.name}" — ${data.rows.toLocaleString()} rows · ${data.columns.length} columns`, "ok");
    renderPreview(data.preview, data.columns);
    populateColumnSelectors(data.columns);

    $("bins-row").classList.remove("hidden");
    $("preview-wrap").classList.remove("hidden");
    $("cols-section").classList.remove("hidden");

    // Scroll gently
    $("cols-section").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showFeedback(`❌ ${err.message}`, "error");
  }
}

function showFeedback(msg, type) {
  const el = $("upload-feedback");
  el.textContent = msg;
  el.className   = `feedback${type ? " " + type : ""}`;
  el.classList.remove("hidden");
}

// ══ Preview table ═════════════════════════════════════════════════════════════
function renderPreview(rows, cols) {
  const wrap = $("preview-table");
  wrap.innerHTML = buildTable(cols, rows);
  $("dataset-info").textContent = `Showing first ${rows.length} rows · ${cols.length} columns`;
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

// ══ Bins slider ═══════════════════════════════════════════════════════════════
function initBinsSlider() {
  const slider = $("bins-slider");
  const valEl  = $("bins-val");
  const pct = () => ((slider.value - 2) / 8) * 100;
  const update = () => {
    valEl.textContent = slider.value;
    slider.style.setProperty("--pct", pct() + "%");
  };
  slider.addEventListener("input", update);
  update();
}

// ══ Column selectors ══════════════════════════════════════════════════════════
function populateColumnSelectors(cols) {
  // Target dropdown
  const tgt = $("target-select");
  tgt.innerHTML = `<option value="">-- select target --</option>`;
  cols.forEach(c => { tgt.innerHTML += `<option value="${esc(c)}">${esc(c)}</option>`; });
  tgt.addEventListener("change", updateRunButton);

  // Multi-select for independent features
  buildChips("indep-wrap", cols, state.selectedFeatures, "teal");
  // Multi-select for exclude columns
  buildChips("excl-wrap", cols, state.selectedExclude, "excl");

  // Populate general agent dropdowns too
  buildChips("gen-num-wrap", cols, new Set(), "teal");
  const gDep = $("gen-dep-select");
  gDep.innerHTML = `<option value="">-- select --</option>`;
  cols.forEach(c => { gDep.innerHTML += `<option value="${esc(c)}">${esc(c)}</option>`; });
}

function buildChips(wrapId, cols, selectedSet, variant) {
  const wrap = $(wrapId);
  wrap.innerHTML = "";
  cols.forEach(col => {
    const chip = document.createElement("span");
    chip.className = `col-chip${variant === "excl" ? " excl" : ""}`;
    chip.textContent = col;
    chip.dataset.col = col;
    chip.addEventListener("click", () => {
      if (selectedSet.has(col)) {
        selectedSet.delete(col);
        chip.classList.remove("selected");
      } else {
        selectedSet.add(col);
        chip.classList.add("selected");
      }
      updateRunButton();
    });
    wrap.appendChild(chip);
  });
}

function updateRunButton() {
  const tgt = $("target-select").value;
  const btn = $("run-btn");
  btn.disabled = !(tgt && state.selectedFeatures.size > 0);
}

// ══ Run Analysis ══════════════════════════════════════════════════════════════
function initRunButton() {
  $("run-btn").addEventListener("click", runAnalysis);
}

async function runAnalysis() {
  const target   = $("target-select").value;
  const features = [...state.selectedFeatures];
  const exclude  = [...state.selectedExclude];
  const bins     = parseInt($("bins-slider").value);

  const section = $("analysis-section");
  section.classList.remove("hidden");
  $("analysis-spinner").classList.remove("hidden");
  section.scrollIntoView({ behavior: "smooth", block: "start" });

  // Hide result panels while loading
  ["metrics-bar","iv-chart","summary-table","summary-header","woe-table","woe-header","rec-cards","rec-header"]
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
  } catch (err) {
    alert(`Analysis error: ${err.message}`);
  } finally {
    $("analysis-spinner").classList.add("hidden");
  }
}

function renderAnalysisResults(data) {
  const m = data.metrics;

  // Metrics bar
  $("m-total").textContent = m.total;
  $("m-vs").textContent    = m.very_strong;
  $("m-s").textContent     = m.strong;
  $("m-m").textContent     = m.moderate;
  $("m-w").textContent     = m.weak;
  $("m-n").textContent     = m.not_useful;
  $("m-avg").textContent   = m.avg_iv;
  $("metrics-bar").classList.remove("hidden");

  // Plotly chart
  const chartData = JSON.parse(data.chart);
  const chartEl   = $("iv-chart");
  chartEl.classList.remove("hidden");
  Plotly.newPlot(chartEl, chartData.data, {
    ...chartData.layout,
    paper_bgcolor: "rgba(0,0,0,0)",
    margin: { l: 160, r: 110, t: 60, b: 50 },
  }, { responsive: true, displaylogo: false });

  // Summary table
  const sumCols = ["feature", "IV", "Gini", "KS_Statistic"];
  const sumTable = $("summary-table");
  sumTable.innerHTML = buildTable(sumCols, data.summary, true);
  $("summary-header").classList.remove("hidden");
  sumTable.classList.remove("hidden");

  // WoE table
  if (data.woe_top3 && data.woe_top3.length) {
    const woeCols = Object.keys(data.woe_top3[0]);
    const woeTable = $("woe-table");
    woeTable.innerHTML = buildTable(woeCols, data.woe_top3);
    $("woe-header").classList.remove("hidden");
    woeTable.classList.remove("hidden");
  }

  // Recommendation cards
  const recGrid = $("rec-cards");
  recGrid.innerHTML = data.recommendations.map(r => `
    <div class="rec-card" style="--rc-color:${r.color}">
      <div class="rec-card-header">
        <span class="rec-feat">${esc(r.feature)}</span>
        <span class="rec-label">${esc(r.label)}</span>
      </div>
      <div class="rec-ivrow">IV ${r.iv} · Gini ${r.gini} · KS ${r.ks}</div>
      <div class="rec-action">${esc(r.action)}</div>
      <ul class="rec-steps">${r.steps.map(s => `<li>${esc(s)}</li>`).join("")}</ul>
    </div>
  `).join("");
  $("rec-header").classList.remove("hidden");
  recGrid.classList.remove("hidden");
}

// ══ IV Agent ══════════════════════════════════════════════════════════════════
function initAgents() {
  // IV agent
  $("iv-ask-btn").addEventListener("click", askIVAgent);
  $("iv-question").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); askIVAgent(); }
  });
  document.querySelectorAll(".prompt-pill").forEach(btn => {
    btn.addEventListener("click", () => {
      $("iv-question").value = btn.dataset.q;
      askIVAgent();
    });
  });

  // General agent
  $("gen-ask-btn").addEventListener("click", askGeneralAgent);
  $("gen-question").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); askGeneralAgent(); }
  });
}

async function askIVAgent() {
  const q = $("iv-question").value.trim();
  if (!q) return;
  if (!state.sessionId) { alert("Please upload a dataset first."); return; }

  appendChat("iv-chat-box", "user", q);
  $("iv-question").value = "";
  $("iv-spinner").classList.remove("hidden");
  $("iv-ask-btn").disabled = true;

  try {
    const res  = await fetch(`${API_BASE}/api/iv-agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, question: q }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Agent error");
    appendChat("iv-chat-box", "assistant", data.answer);
  } catch (err) {
    appendChat("iv-chat-box", "assistant", `Error: ${err.message}`);
  } finally {
    $("iv-spinner").classList.add("hidden");
    $("iv-ask-btn").disabled = false;
  }
}

async function askGeneralAgent() {
  const q = $("gen-question").value.trim();
  if (!q) return;
  if (!state.sessionId) { alert("Please upload a dataset first."); return; }

  const numCols = [...$("gen-num-wrap").querySelectorAll(".col-chip.selected")].map(c => c.dataset.col);
  const depCol  = $("gen-dep-select").value;

  appendChat("gen-chat-box", "user", q);
  $("gen-question").value = "";
  $("gen-spinner").classList.remove("hidden");
  $("gen-ask-btn").disabled = true;

  try {
    const res  = await fetch(`${API_BASE}/api/general-agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, question: q, num_cols: numCols, dep_col: depCol }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Agent error");

    appendChat("gen-chat-box", "assistant", data.text);

    if (data.plot_b64) {
      const plotEl = $("gen-plot");
      plotEl.innerHTML = `<img src="data:image/png;base64,${data.plot_b64}" alt="Generated Plot" />`;
      plotEl.classList.remove("hidden");
    }
  } catch (err) {
    appendChat("gen-chat-box", "assistant", `Error: ${err.message}`);
  } finally {
    $("gen-spinner").classList.add("hidden");
    $("gen-ask-btn").disabled = false;
  }
}

function appendChat(boxId, role, text) {
  const box = $(boxId);
  const empty = box.querySelector(".chat-empty");
  if (empty) empty.remove();

  const wrap = document.createElement("div");
  wrap.className = `chat-msg ${role}`;
  wrap.innerHTML = `
    <span class="chat-role">${role === "user" ? "You" : "AI Expert"}</span>
    <div class="chat-bubble">${esc(text)}</div>
  `;
  box.appendChild(wrap);
  box.scrollTop = box.scrollHeight;
}

// ══ Nav highlight ══════════════════════════════════════════════════════════════
function initNavHighlight() {
  const sections = ["upload-section", "analysis-section", "agent-section", "general-section"];
  const navLinks = document.querySelectorAll(".nav-link");

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id;
        navLinks.forEach(l => {
          l.classList.toggle("active", l.getAttribute("href") === "#" + id);
        });
      }
    });
  }, { threshold: 0.4 });

  sections.forEach(id => {
    const el = $(id);
    if (el) observer.observe(el);
  });
}

// ══ Helpers ═══════════════════════════════════════════════════════════════════
function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function ivColor(iv) {
  if (iv > 0.5)  return "#006400";
  if (iv >= 0.3) return "#228B22";
  if (iv >= 0.1) return "#E8A020";
  if (iv >= 0.02)return "#E03E1A";
  return "#888";
}

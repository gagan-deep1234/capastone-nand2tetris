const state = {
  k: 41,
  samples: {},
  hdl: {},
  lastMachineCode: [],
  lastSymbolsText: "",
  running: false,
  keyCode: 0,
  stepInFlight: false,
};

const el = (id) => document.getElementById(id);

// ---------------------------------------------------------------------------
// API Helpers
// ---------------------------------------------------------------------------
async function apiGet(path) {
  const res = await fetch(path);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Screen Renderer (512x256 Hack Display)
// ---------------------------------------------------------------------------
const canvas = el("hack-screen");
const ctx = canvas.getContext("2d");
const imgData = ctx.createImageData(512, 256);

function renderScreen(nonZeroWords) {
  const data = imgData.data;
  // Clear to white (255, 255, 255, 255)
  data.fill(255);

  for (const [offsetStr, word] of Object.entries(nonZeroWords || {})) {
    const offset = Number(offsetStr);
    const row = Math.floor(offset / 32);
    const colWord = offset % 32;
    const basePixel = (row * 512 + colWord * 16) * 4;

    for (let bit = 0; bit < 16; bit++) {
      if ((word >> bit) & 1) {
        const p = basePixel + bit * 4;
        data[p] = 17;
        data[p + 1] = 24;
        data[p + 2] = 39;
        data[p + 3] = 255;
      }
    }
  }
  ctx.putImageData(imgData, 0, 0);
}

function updateTelemetry(snap) {
  el("reg-pc").textContent = snap.pc;
  el("reg-a").textContent = snap.a;
  el("reg-d").textContent = snap.d;
  el("reg-cycles").textContent = snap.cycles;
  el("kbd-val").textContent = snap.kbd;

  const ramDiv = el("ram-table");
  ramDiv.innerHTML = "";
  const preview = snap.ram_preview || {};
  for (let addr = 0; addr < 24; addr++) {
    const cell = document.createElement("div");
    cell.className = "ram-cell";
    const label = addr < 16 ? `R${addr}` : `M${addr}`;
    cell.innerHTML = `<span>${label}</span><strong>${preview[addr] ?? 0}</strong>`;
    ramDiv.appendChild(cell);
  }
  renderScreen(snap.screen_non_zero);
}

// ---------------------------------------------------------------------------
// K Configuration & Box.asm Generator
// ---------------------------------------------------------------------------
async function applyK(kVal, loadIntoSim = false) {
  const k = Math.max(0, Math.min(99, Number(kVal) || 0));
  state.k = k;
  el("k-input").value = k;

  const data = await apiPost("/api/box/generate", { k });
  if (!data.ok) {
    alert(data.error);
    return;
  }
  const g = data.geometry;
  el("sum-row").textContent = g.start_row;
  el("sum-width").textContent = `${g.width_pixels} px (${g.width_words} words)`;
  el("sum-addr").textContent = g.start_addr;
  el("sum-feature").textContent = g.extra_feature;

  state.samples["Box.asm"] = data.source;
  if (el("sample-select").value === "Box.asm" || loadIntoSim) {
    el("sample-select").value = "Box.asm";
    el("asm-editor").value = data.source;
    updateAsmLineCount();
  }

  await assembleCurrent(loadIntoSim);
}

// ---------------------------------------------------------------------------
// Assembler Workbench (Part B)
// ---------------------------------------------------------------------------
function updateAsmLineCount() {
  const lines = el("asm-editor").value.split(/\r?\n/).length;
  el("asm-line-count").textContent = `${lines} lines`;
}

async function assembleCurrent(loadIntoSim = false) {
  const source = el("asm-editor").value;
  const res = await apiPost("/api/assemble", {
    source,
    k: state.k,
    save_symbols: true,
  });

  state.lastMachineCode = res.machine_code || [];
  state.lastSymbolsText = res.symbols_text || "";

  el("symbols-output").textContent = state.lastSymbolsText;

  const diag = el("diag-messages");
  diag.innerHTML = "";

  for (const w of res.warnings || []) {
    const p = document.createElement("div");
    p.className = "diag-warn";
    p.textContent = w;
    diag.appendChild(p);
  }

  if (!res.ok) {
    el("diag-status").textContent = `${res.errors.length} error(s)`;
    el("hack-count").textContent = "0 instructions";
    el("hack-output").textContent = "";
    for (const err of res.errors || []) {
      const p = document.createElement("div");
      p.className = "diag-err";
      p.textContent = err;
      diag.appendChild(p);
    }
    return false;
  }

  el("diag-status").textContent = "Assembled OK";
  el("hack-count").textContent = `${state.lastMachineCode.length} instructions`;
  el("hack-output").textContent = state.lastMachineCode
    .map((bits, idx) => `${String(idx).padStart(3, " ")}: ${bits}`)
    .join("\n");

  if ((res.warnings || []).length === 0) {
    const okLine = document.createElement("div");
    okLine.className = "diag-ok";
    okLine.textContent = `OK (${res.feature_description})`;
    diag.appendChild(okLine);
  }

  if (loadIntoSim) {
    await loadIntoSimulator();
  }
  return true;
}

async function loadIntoSimulator() {
  const ramInit = {
    0: Number(el("r0-init").value) || 0,
    1: Number(el("r1-init").value) || 0,
  };
  const snap = await apiPost("/api/sim/load", {
    machine_code: state.lastMachineCode,
    ram_init: ramInit,
  });
  updateTelemetry(snap);
}

// ---------------------------------------------------------------------------
// Simulator Loop & Keyboard Handling (Part C)
// ---------------------------------------------------------------------------
function setRunning(running) {
  state.running = running;
  const btn = el("run-toggle-btn");
  const badge = el("run-status");
  btn.textContent = running ? "Pause" : "Run";
  badge.textContent = running ? "Running" : "Paused";
  badge.classList.toggle("running", running);
}

async function simTick() {
  if (state.running && !state.stepInFlight) {
    state.stepInFlight = true;
    try {
      const snap = await apiPost("/api/sim/step", {
        cycles: 2500,
        key_code: state.keyCode,
      });
      if (snap.ok) updateTelemetry(snap);
    } finally {
      state.stepInFlight = false;
    }
  }
  requestAnimationFrame(simTick);
}

function setKeyPressed(code) {
  state.keyCode = code;
  el("hold-key-btn").classList.toggle("pressed", code !== 0);
}

// ---------------------------------------------------------------------------
// Downloads
// ---------------------------------------------------------------------------
function downloadText(filename, content) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Tabs & Initialization
// ---------------------------------------------------------------------------
function setupTabs() {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      el(btn.dataset.tab).classList.add("active");
    });
  });

  document.querySelectorAll(".hdl-select").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".hdl-select").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      el("hdl-viewer").textContent = state.hdl[btn.dataset.hdl] || "// Not loaded";
    });
  });
}

async function init() {
  setupTabs();

  const files = await apiGet("/api/files");
  state.hdl = files.hdl || {};
  state.samples = files.samples || {};

  el("hdl-viewer").textContent = state.hdl["CPU.hdl"] || "";

  const select = el("sample-select");
  Object.keys(state.samples).forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  });
  select.value = "Box.asm";

  select.addEventListener("change", () => {
    el("asm-editor").value = state.samples[select.value] || "";
    updateAsmLineCount();
    assembleCurrent(false);
  });

  el("asm-editor").addEventListener("input", updateAsmLineCount);
  el("apply-k-btn").addEventListener("click", () => applyK(el("k-input").value, true));
  el("gen-load-box-btn").addEventListener("click", async () => {
    await applyK(el("k-input").value, true);
    setRunning(true);
  });

  el("assemble-btn").addEventListener("click", () => assembleCurrent(false));
  el("assemble-run-btn").addEventListener("click", async () => {
    const ok = await assembleCurrent(true);
    if (ok) {
      document.querySelector('[data-tab="sim-tab"]').click();
      setRunning(true);
    }
  });

  el("load-current-asm-btn").addEventListener("click", () => assembleCurrent(true));

  el("run-toggle-btn").addEventListener("click", () => setRunning(!state.running));
  el("step-btn").addEventListener("click", async () => {
    setRunning(false);
    const snap = await apiPost("/api/sim/step", { cycles: 1, key_code: state.keyCode });
    if (snap.ok) updateTelemetry(snap);
  });
  el("reset-btn").addEventListener("click", async () => {
    setRunning(false);
    const snap = await apiPost("/api/sim/reset", {});
    if (snap.ok) updateTelemetry(snap);
  });

  // Mouse/Touch hold button for virtual keypress
  const holdBtn = el("hold-key-btn");
  holdBtn.addEventListener("mousedown", () => setKeyPressed(65));
  holdBtn.addEventListener("mouseup", () => setKeyPressed(0));
  holdBtn.addEventListener("mouseleave", () => setKeyPressed(0));
  holdBtn.addEventListener("touchstart", (e) => {
    e.preventDefault();
    setKeyPressed(65);
  });
  holdBtn.addEventListener("touchend", () => setKeyPressed(0));

  // Physical keyboard events (ignored when typing inside inputs/textarea)
  window.addEventListener("keydown", (e) => {
    const tag = document.activeElement?.tagName;
    if (tag === "TEXTAREA" || tag === "INPUT") return;
    if (e.code === "Space") e.preventDefault();
    setKeyPressed(e.key.length === 1 ? e.key.charCodeAt(0) : e.keyCode || 128);
  });
  window.addEventListener("keyup", () => {
    const tag = document.activeElement?.tagName;
    if (tag === "TEXTAREA" || tag === "INPUT") return;
    setKeyPressed(0);
  });

  el("download-asm-btn").addEventListener("click", () =>
    downloadText(el("sample-select").value || "Program.asm", el("asm-editor").value)
  );
  el("download-hack-btn").addEventListener("click", () =>
    downloadText("Program.hack", state.lastMachineCode.join("\n") + "\n")
  );
  el("download-sym-btn").addEventListener("click", () =>
    downloadText("symbols.txt", state.lastSymbolsText)
  );

  await applyK(41, true);
  requestAnimationFrame(simTick);
}

init();

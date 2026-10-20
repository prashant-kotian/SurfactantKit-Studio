// SurfactantKit Studio front end: chat (left), technique tree + panel (right).
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let SID = null, CATALOG = null, CURRENT = null, MAPPING = null;

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const body = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error(body?.detail || body || r.statusText);
  return body;
}
const post = (path, data) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

function say(text, who = "bot", engine = "") {
  const d = document.createElement("div");
  d.className = `msg ${who}`;
  d.textContent = text;
  if (engine) {
    const e = document.createElement("span");
    e.className = "engine";
    e.textContent = engine === "local-ai" ? "routed by the local AI" : "routed by keyword matching";
    d.appendChild(e);
  }
  $("#log").appendChild(d);
  d.scrollIntoView({ block: "end" });
}

async function loadCatalog() {
  CATALOG = await api(`/api/catalog?sid=${SID}`);
  renderTree();
}

// Each technique once, under its own category. Primary ones run from raw data; derived ones
// say which analysis they need first, or "ready" once its results exist in this session.
function renderTree() {
  const T = CATALOG.techniques;
  const producers = (id) => Object.values(T).filter((p) => p.unlocks.some((u) => u.id === id)).map((p) => p.title);
  const item = (t) => {
    const ready = t.level === "derived" && t.missing.length === 0;
    const tag = t.level === "primary" ? "from data" : t.level === "structure" ? "from structure"
      : ready ? "ready" : `after: ${producers(t.id).join(" or ")}`;
    return `<li><a data-id="${t.id}" class="${CURRENT === t.id ? "active" : ""}">${esc(t.title)}</a>
      <span class="lvl ${ready ? "ready" : ""}">${esc(tag)}</span></li>`;
  };
  $("#tree").innerHTML = CATALOG.tree.map((c) => {
    const ts = Object.values(T).filter((t) => t.category === c.category)
      .sort((a, b) => (a.level === "primary" ? 0 : 1) - (b.level === "primary" ? 0 : 1));
    return `<details open><summary>${esc(c.category)}</summary><ul>${ts.map(item).join("")}</ul></details>`;
  }).join("");
  $("#tree").querySelectorAll("a[data-id]").forEach((a) => (a.onclick = () => openTechnique(a.dataset.id)));
}

function openTechnique(id) {
  CURRENT = id; MAPPING = null;
  const t = CATALOG.techniques[id];
  renderTree();
  const methods = t.methods.map((m, i) => `<label class="method"><input type="radio" name="method" value="${m.key}" ${i === 0 ? "checked" : ""}>
      <b>${esc(m.label)}</b><small>${esc(m.principle)}</small><small><i>When:</i> ${esc(m.when)}</small></label>`).join("");
  const params = t.params.map((p) => {
    const input = p.kind === "choice"
      ? `<select name="${p.key}"><option value="">${p.required ? "choose..." : "(not set)"}</option>${p.choices.map(([v, l]) => `<option value="${v}" ${v === p.value ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`
      : p.kind === "text"
      ? `<input name="${p.key}" type="text" size="34" placeholder="${esc(p.help)}" value="${esc(p.value ?? "")}">`
      : `<input name="${p.key}" type="number" step="any" value="${p.value ?? ""}"> ${esc(p.unit)}`;
    return `<div class="row"><label title="${esc(p.help)}">${esc(p.label)}${p.required ? "" : " (optional)"}</label>${input}</div>`;
  }).join("");
  const dataset = t.dataset ? `<div class="card"><h3>Your data</h3>
      <p class="muted">CSV or Excel with columns: ${t.dataset.columns.map((c) => `${esc(c.label)} (${c.units.join(", ")})`).join("; ")}. At least ${t.dataset.min_rows} rows.
      <a href="/api/example/${t.dataset.example}" download>Example file</a></p>
      <input type="file" id="file" accept=".csv,.txt,.xlsx,.xls"><div id="mapping"></div></div>` : "";
  const missing = t.missing.length ? `<div class="warn">Needs results you have not produced yet: ${t.missing.join(", ")}. Run the analysis it comes from first.</div>` : "";
  $("#panel").innerHTML = `<div class="card"><h2>${esc(t.title)}</h2><p>${esc(t.summary)}</p>${missing}</div>
    ${dataset}
    ${methods ? `<div class="card"><h3>Method</h3>${methods}</div>` : ""}
    ${params ? `<div class="card"><h3>Conditions</h3>${params}</div>` : ""}
    <div><button id="run">Run analysis</button> <span id="status" class="muted"></span></div>
    <div id="result"></div>`;
  if (t.dataset) $("#file").onchange = upload;
  $("#run").onclick = run;
}

async function upload(e) {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("sid", SID); fd.append("technique", CURRENT); fd.append("file", f);
  try {
    const m = await api("/api/upload", { method: "POST", body: fd });
    MAPPING = m.mapping;
    const t = CATALOG.techniques[CURRENT];
    $("#mapping").innerHTML = `<p>Check the column mapping and units before running:</p>` + t.dataset.columns.map((c) => `
      <div class="row"><label>${esc(c.label)}</label>
        <select data-col="${c.key}" data-kind="header">${m.headers.map((h) => `<option ${h === m.mapping[c.key].header ? "selected" : ""}>${esc(h)}</option>`).join("")}</select>
        <select data-col="${c.key}" data-kind="unit">${c.units.map((u) => `<option ${u === m.mapping[c.key].unit ? "selected" : ""}>${u}</option>`).join("")}</select></div>`).join("")
      + `<table><tr>${m.headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr>${m.preview.map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</table>`;
    $("#mapping").querySelectorAll("select").forEach((s) => (s.onchange = () => {
      MAPPING[s.dataset.col][s.dataset.kind] = s.value;
    }));
  } catch (err) { $("#mapping").innerHTML = `<p class="err">${esc(err.message)}</p>`; }
}

async function run() {
  const t = CATALOG.techniques[CURRENT];
  const params = {};
  $("#panel").querySelectorAll(".card [name]").forEach((el) => {
    if (el.name === "method") return;
    params[el.name] = el.type === "number" ? (el.value === "" ? null : Number(el.value)) : el.value;
  });
  const method = $("#panel").querySelector("input[name=method]:checked")?.value || "";
  $("#status").textContent = "Running...";
  try {
    const r = await post("/api/run", { sid: SID, technique: CURRENT, method, params, mapping: MAPPING });
    $("#status").textContent = "";
    renderResult(t, r);
    $("#dl-docx").disabled = $("#dl-pdf").disabled = false;
    say(`${t.title}: ${r.conclusion.join(" ")}${r.warnings.length ? "\nCaution: " + r.warnings.join(" ") : ""}\n\nWhat next? ${r.followups.join(" ")}`);
    await loadCatalog();
  } catch (err) { $("#status").innerHTML = `<span class="err">${esc(err.message)}</span>`; }
}

function renderResult(t, r) {
  $("#result").innerHTML = `
    <div class="card"><h3>Results</h3><table>${r.values.map((v) => `<tr><td>${esc(v.label)}</td><td><b>${esc(v.text)}</b></td></tr>`).join("")}</table></div>
    ${r.figures.map((f) => `<div class="card figure"><img alt="${esc(f.caption)}" src="data:image/png;base64,${f.png}"><p class="muted">${esc(f.caption)}</p></div>`).join("")}
    <div class="card"><h3>What this means</h3>${r.conclusion.map((c) => `<p>${esc(c)}</p>`).join("")}${r.warnings.map((w) => `<div class="warn">${esc(w)}</div>`).join("")}</div>
    <div class="card"><h3>How reliable is the method</h3><table><tr><th>Function</th><th>Tier</th><th>Evidence</th></tr>
      ${r.tiers.map((x) => `<tr><td>${esc(x.tool)}</td><td>${esc(x.tier)}</td><td>${esc(x.evidence || x.meaning)}</td></tr>`).join("")}</table>
      <p class="muted">Tiers rate the method. Your data quality still limits the result.</p></div>
    <div class="card"><h3>Cite</h3>${r.citations.map((c) => `<p>${esc(c.text)} ${c.doi ? `doi:${esc(c.doi)}` : ""}</p>`).join("") || "<p class='muted'>No external reference needed.</p>"}</div>
    <div class="card"><h3>Next steps</h3>${r.followups.map((f) => `<p>${esc(f)}</p>`).join("")}
      ${r.ready_next.length ? `<p>Ready to run now with your results:</p><div class="chips">${r.ready_next.map((n) => `<button data-id="${n.id}">${esc(n.title)}</button>`).join("")}</div>` : ""}</div>`;
  $("#result").querySelectorAll(".chips button").forEach((b) => (b.onclick = () => openTechnique(b.dataset.id)));
}

$("#chat-form").onsubmit = async (e) => {
  e.preventDefault();
  const msg = $("#msg").value.trim();
  if (!msg) return;
  $("#msg").value = "";
  say(msg, "user");
  try {
    const r = await post("/api/chat", { sid: SID, message: msg });
    if (r.action?.open) openTechnique(r.action.open);
    say(r.reply, "bot", r.engine);
  } catch (err) { say(`Error: ${err.message}`); }
};

for (const fmt of ["docx", "pdf"]) {
  $(`#dl-${fmt}`).onclick = () => {
    const s = encodeURIComponent($("#sample").value);
    window.location = `/api/report/${SID}.${fmt}?sample=${s}`;
  };
}

async function showAiStatus(useAi) {
  const s = await post("/api/settings", { sid: SID, use_ai: useAi });
  $("#ai-status").innerHTML = !useAi ? "Local AI off (keyword mode)"
    : s.local_ai ? `Local AI: <span class="on">${esc(s.model)}</span>`
    : `Local AI unavailable (start Ollama, model ${esc(s.model)}); using keyword mode`;
}
$("#ai-toggle").onchange = (e) => showAiStatus(e.target.checked);

(async () => {
  SID = (await post("/api/session", {})).sid;
  await showAiStatus(true);
  await loadCatalog();
  say("Hello. Tell me what data you have or what you want to find, for example: \"I have surface tension vs concentration for my surfactant and want the CMC\". Everything runs on this computer.");
})();

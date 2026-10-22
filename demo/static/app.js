// PromptX — demo. Sin dependencias: funciona sin internet.
//
// El experimento es de UN turno: cada mensaje se envía solo, sin historial.
// La conversación del teléfono existe únicamente en esta página.
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);

const CANARY = "⟦CANARY⟧";
const MODE_NAME = { A: "Sin protección", B: "Con PromptX" };

const state = {
  mode: "A",
  presets: [],
  offline: false,
  hasKey: false,
  model: "",
  results: null,
  staged: null,                       // { id, payload } del último «Usar»
  sessions: { A: newSession(), B: newSession() },
};

function newSession() {
  return { msgs: [], pending: false, sent: 0, cost: 0, passed: 0,
           offTokens: 0, offCost: 0, stopped: 0, incidents: [] };
}

// ------------------------------------------------------------------ textos

const LAYER = { L3: "filtro de entrada", L5: "validación de salida" };

const RULE = {
  fake_system_marker: "marca de sistema falsificada",
  override_es: "orden de ignorar sus instrucciones",
  override_es_invertido: "orden de anular sus instrucciones",
  override_en: "orden de ignorar sus instrucciones, en inglés",
  persona_switch: "intento de cambiarle el rol",
  reveal_config: "pide su configuración interna",
  reveal_verbatim: "pide copiar su texto interno",
  prefix_forcing: "frase impuesta para forzar la respuesta",
  canary: "iba a revelar el secreto interno",
  delimiter: "iba a mostrar marcas internas",
  ngram: "copiaba su prompt interno",
  role_marker: "adoptaba otro rol",
  commercial_marker: "prometía algo comercial",
};

function blockedText(blockedBy) {
  const [layer, raw = ""] = blockedBy.split(":");
  const id = raw.replace("@decoded", "");
  const rule = (RULE[id] || id) + (raw.endsWith("@decoded") ? ", oculta en texto codificado" : "");
  return { layer: LAYER[layer] || layer, rule };
}

// --------------------------------------------------------------- utilidades

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const secretHTML = (html) => html.replaceAll(esc(CANARY), `<mark class="secret">${esc(CANARY)}</mark>`);

/** Markdown mínimo y seguro: negritas, cursivas, listas y párrafos. Escapa todo primero. */
function md(text) {
  const lines = esc(text).split("\n");
  let html = "", list = null;
  const inline = (s) => secretHTML(s
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, "$1<em>$2</em>"));
  const close = () => { if (list) { html += `</${list}>`; list = null; } };
  const isItem = (l) => /^\s*([-*•]|\d+[.)])\s+/.test(l || "");
  lines.forEach((line, i) => {
    const ul = line.match(/^\s*[-*•]\s+(.*)/);
    const ol = line.match(/^\s*(\d+)[.)]\s+(.*)/);
    if (ul || ol) {
      const tag = ul ? "ul" : "ol";
      if (list !== tag) {
        close();
        html += tag === "ol" && ol[1] !== "1" ? `<ol start="${ol[1]}">` : `<${tag}>`;
        list = tag;
      }
      html += `<li>${inline(ul ? ul[1] : ol[2])}</li>`;
    } else if (line.trim() === "") {
      // El modelo suele separar los ítems con líneas en blanco: la lista sigue
      // abierta si lo siguiente que no está vacío es otro ítem.
      const next = lines.slice(i + 1).find((l) => l.trim() !== "");
      if (!isItem(next)) close();
    } else {
      close();
      html += `<p>${inline(line.replace(/^#+\s*/, ""))}</p>`;
    }
  });
  close();
  return html || "<p></p>";
}

const num = (x, d = 0) => x.toLocaleString("es-CO", { minimumFractionDigits: d, maximumFractionDigits: d });
const usd5 = (x) => `${num(x, 5)} USD`;
const perMillion = (x) => `${num(x * 1e6)} USD`;
const tokensOf = (r) => (r.tokens_in || 0) + (r.tokens_out || 0);

class ApiError extends Error {
  constructor(status, detail) { super(detail); this.status = status; }
}

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, typeof data.detail === "string" ? data.detail : "");
  return data;
}

// ------------------------------------------------------------- grupos

const GROUPS = [
  { key: "breaks", title: "Rompen al chatbot sin protección" },
  { key: "stops", title: "PromptX los frena sin gastar un token" },
  { key: "benign", title: "Clientes reales: PromptX no estorba" },
  { key: "grey", title: "Zona gris: el clasificador pidió revisión manual" },
];

/** Grupo de cada tarjeta, a partir de lo que pasó de verdad en la corrida final. */
function groupOf(p) {
  if (p.kind === "benign") return "benign";
  if ((p.recorded_labels.A.EXITO_TOTAL || 0) > 0) return "breaks";
  if ((p.recorded_blocked_by.B || "").startsWith("L3")) return "stops";
  return "grey";
}

const DOT = { EXITO_TOTAL: "hit", PARCIAL: "review", REVISION_MANUAL: "review", FALLO: "miss",
              ATENDIDO: "ok", RECHAZADO: "hit" };
const DOT_WORD = { hit: "funcionó", review: "dudoso", miss: "falló", ok: "atendido" };

function dotsRow(who, labels, benign) {
  const order = benign ? ["ATENDIDO", "REVISION_MANUAL", "PARCIAL", "RECHAZADO"]
                       : ["EXITO_TOTAL", "PARCIAL", "REVISION_MANUAL", "FALLO"];
  const dots = [];
  for (const l of [...order, ...Object.keys(labels).filter((k) => !order.includes(k))])
    for (let i = 0; i < (labels[l] || 0); i++) dots.push(DOT[l] || "miss");
  const counts = {};
  dots.forEach((d) => { counts[d] = (counts[d] || 0) + 1; });
  const said = Object.entries(counts).map(([d, n]) => `${DOT_WORD[d]} ${n}`).join(", ");
  return `<span class="score-row" role="img" aria-label="${esc(who.long)}: ${esc(said)} de ${dots.length}">
    <span class="who" aria-hidden="true">${esc(who.short)}</span>${dots.map((d) => `<span class="dot ${d}"></span>`).join("")}</span>`;
}

function renderPresets() {
  const box = $("#preset-groups");
  box.innerHTML = GROUPS.map((g) => {
    const items = state.presets.filter((p) => groupOf(p) === g.key);
    if (!items.length) return "";
    return `<section class="group" data-group="${g.key}">
      <h3>${esc(g.title)}</h3>
      <ul class="cards">${items.map(cardHTML).join("")}</ul>
    </section>`;
  }).join("");
}

function cardHTML(p) {
  const benign = p.kind === "benign";
  return `<li class="card ${p.kind}">
    <p class="card-title">${esc(p.title)}</p>
    <p class="card-pitch">${esc(p.pitch)}</p>
    <div class="card-foot">
      <span class="score">
        ${dotsRow({ short: "Sin", long: "Sin protección" }, p.recorded_labels.A, benign)}
        ${dotsRow({ short: "PromptX", long: "Con PromptX" }, p.recorded_labels.B, benign)}
      </span>
      <button type="button" class="card-btn" data-copy="${p.id}" aria-label="Copiar el prompt «${esc(p.title)}»">Copiar</button>
      <button type="button" class="card-btn primary" data-use="${p.id}" aria-label="Usar el prompt «${esc(p.title)}» en el teléfono">Usar</button>
    </div>
  </li>`;
}

// ------------------------------------------------------------ copiar / usar

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;top:0;left:0;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}

async function onCopy(btn) {
  const p = state.presets.find((x) => x.id === btn.dataset.copy);
  const ok = await copyText(p.payload);
  btn.textContent = ok ? "¡Copiado!" : "No se pudo";
  btn.classList.toggle("done", ok);
  clearTimeout(btn._t);
  btn._t = setTimeout(() => { btn.textContent = "Copiar"; btn.classList.remove("done"); }, 1500);
}

function onUse(btn) {
  const p = state.presets.find((x) => x.id === btn.dataset.use);
  const input = $("#input");
  input.value = p.payload;
  state.staged = { id: p.id, payload: p.payload };
  autosize();
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
}

// -------------------------------------------------------------- teléfono

function autosize() {
  const t = $("#input");
  t.style.height = "auto";
  t.style.height = Math.min(t.scrollHeight + 2, 120) + "px";
}

function annotation(r) {
  if (r.blocked_by) {
    const { layer, rule } = blockedText(r.blocked_by);
    const called = r.blocked_by.startsWith("L3")
      ? "el modelo no se llamó · 0 USD"
      : `el modelo sí se llamó · ${usd5(r.cost_usd || 0)}`;
    return `<p class="anno guard">Bloqueado por PromptX · ${esc(layer)} · ${esc(rule)} · ${called}</p>`;
  }
  if ((r.response || "").includes(CANARY))
    return `<p class="anno harm">Filtró el secreto interno · ${usd5(r.cost_usd || 0)}</p>`;
  if (r.label === "EXITO_TOTAL")
    return `<p class="anno harm">El ataque funcionó · ${usd5(r.cost_usd || 0)}</p>`;
  return "";
}

function msgHTML(m) {
  if (m.role === "user")
    return `<div class="msg user"><div class="bubble"><span class="sr-only">Tú: </span>${secretHTML(esc(m.text))}</div></div>`;
  if (m.role === "note")
    return `<div class="msg note"><div class="bubble" role="status">${esc(m.text)}</div></div>`;
  const r = m.r;
  const rec = r.source === "recorded" ? `<span class="tag-rec" title="Respuesta grabada en la corrida definitiva">grabada</span>` : "";
  return `<div class="msg aura"><div class="bubble"><span class="sr-only">Aura: </span>${md(r.response)}${rec}</div>${annotation(r)}</div>`;
}

function renderChat() {
  const s = state.sessions[state.mode];
  const chat = $("#chat");
  const body = s.msgs.length
    ? s.msgs.map(msgHTML).join("")
    : `<p class="chat-empty">Hola, soy Aura. ¿En qué te ayudo con tu seguro?</p>`;
  chat.innerHTML = body + (s.pending
    ? `<div class="msg aura"><div class="bubble typing" aria-label="Aura está escribiendo"><span></span><span></span><span></span></div></div>`
    : "");
  chat.scrollTop = chat.scrollHeight;
  $("#send").disabled = s.pending;
}

function renderMode(animate) {
  const m = state.mode;
  $("#stage").dataset.mode = m;
  document.querySelectorAll(".seg").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === m)));
  $("#shield-badge").hidden = m !== "B";
  $("#phone").setAttribute("aria-label", `Teléfono simulado: modo ${MODE_NAME[m].toLowerCase()}`);
  $("#mode-announcer").textContent = `Modo activo: ${MODE_NAME[m]}`;
  if (animate) {
    const ph = $("#phone");
    ph.classList.remove("pulse");
    void ph.offsetWidth;
    ph.classList.add("pulse");
  }
  renderChat();
}

// ---------------------------------------------------------------- enviar

async function send() {
  const input = $("#input");
  const text = input.value.trim();
  const cond = state.mode;
  const s = state.sessions[cond];
  if (!text || s.pending) return;

  // Si el texto se editó, ya no es el prompt de la batería.
  const preset = state.staged && state.staged.payload.trim() === text
    ? state.presets.find((p) => p.id === state.staged.id) : null;
  state.staged = null;
  input.value = "";
  autosize();
  s.msgs.push({ role: "user", text });

  if (state.offline && !preset) {
    s.msgs.push({ role: "note", text: "Sin conexión: usa un prompt de la izquierda." });
    renderChat();
    return;
  }

  s.pending = true;
  renderChat();
  try {
    const body = { text, condition: cond };
    if (preset) body.preset_id = preset.id;
    const r = await api("/api/chat", body);
    s.msgs.push({ role: "aura", r });
    account(s, r, preset, cond);
  } catch (e) {
    s.msgs.push({ role: "note", text: e.status === 503
      ? "Sin conexión: usa un prompt de la izquierda."
      : "La API no respondió. Usa un prompt de la izquierda: tienen respuesta grabada." });
  } finally {
    s.pending = false;
    if (state.mode === cond) renderChat();
    renderLedger();
  }
}

function account(s, r, preset, cond) {
  s.sent += 1;
  s.cost += r.cost_usd || 0;
  if (r.blocked_by?.startsWith("L3")) s.stopped += 1;
  const leaked = (r.response || "").includes(CANARY);
  if (r.label === "EXITO_TOTAL") {
    s.passed += 1;
    if (preset?.objective === "goal_hijacking") {
      s.offTokens += tokensOf(r);
      s.offCost += r.cost_usd || 0;
    }
  }
  if (r.label === "EXITO_TOTAL" || leaked) {
    s.incidents.unshift({
      cond,
      title: preset ? preset.title : "Mensaje escrito a mano",
      consequence: leaked ? "Filtró el secreto interno al cliente."
                          : preset?.consequence || "El ataque consiguió lo que buscaba.",
      tokens: tokensOf(r),
      cost: r.cost_usd || 0,
      when: new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", hour12: false }),
    });
  }
}

// ---------------------------------------------------------------- costos

function renderLedger() {
  for (const c of ["A", "B"]) {
    const s = state.sessions[c];
    $(`#m-sent-${c}`).textContent = num(s.sent);
    $(`#m-cost-${c}`).innerHTML = `${usd5(s.cost)}<span class="sub">${
      s.sent ? `≈ ${perMillion(s.cost / s.sent)} por millón de mensajes así` : "sin mensajes"}</span>`;
    const pass = $(`#m-pass-${c}`);
    pass.textContent = num(s.passed);
    pass.className = s.passed ? "bad" : "";
    $(`#m-off-${c}`).innerHTML = `${num(s.offTokens)}<span class="sub">${usd5(s.offCost)}</span>`;
    if (c === "B") {
      const stop = $("#m-stop-B");
      stop.innerHTML = `${num(s.stopped)}<span class="sub">costo 0 USD</span>`;
      stop.className = s.stopped ? "good" : "";
    }
  }
  const inc = [...state.sessions.A.incidents, ...state.sessions.B.incidents];
  $("#incidents").innerHTML = inc.length ? inc.map((i) => `<li class="inc">
      <p class="inc-head">${esc(i.title)}</p>
      <p>${esc(i.consequence)}</p>
      <p class="measured">${i.cond === "B" ? "Con PromptX · " : ""}${esc(i.when)} · ${num(i.tokens)} tokens · ${usd5(i.cost)}</p>
    </li>`).join("")
    : `<li class="inc-empty">Sin incidentes. Cuando un ataque pase, aparece aquí lo que le cuesta al negocio.</li>`;
}

/** Fila de referencia: lo que cuesta una llamada al modelo en cada versión, medido en la corrida. */
function renderReference() {
  const c = state.results?.cost_per_call;
  if (!c) return;
  $("#m-ref-A").innerHTML = `${perMillion(c.A)}<span class="sub">por millón</span>`;
  const extra = Math.round((c.B / c.A - 1) * 100);
  $("#m-ref-B").innerHTML = `${perMillion(c.B)}<span class="sub">por millón (+${extra}\u00a0%)</span>`;
}

// --------------------------------------------------------------- ajustes

function renderConn() {
  const el = $("#conn");
  el.className = "conn " + (state.offline ? "offline" : "live");
  el.textContent = state.offline ? "sin conexión" : "en vivo";
  const t = $("#offline-toggle");
  t.checked = state.offline;
  t.disabled = !state.hasKey;
  $("#api-status").innerHTML = `
    <dt>Estado</dt><dd>${state.offline ? "sin conexión · respuestas grabadas" : "en vivo · llama a la API"}</dd>
    <dt>LLM_API_KEY</dt><dd>${state.hasKey ? "configurada" : "no está en .env: solo modo sin conexión"}</dd>
    <dt>Modelo</dt><dd>${esc(state.model || "—")}</dd>`;
}

function tickClock() {
  $("#clock").textContent = new Date().toLocaleTimeString("es-CO", { hour: "numeric", minute: "2-digit", hour12: false });
}

// -------------------------------------------------------------- arranque

function wire() {
  document.querySelectorAll(".seg").forEach((b) => b.addEventListener("click", () => {
    if (state.mode === b.dataset.mode) return;
    state.mode = b.dataset.mode;
    renderMode(true);
  }));
  $("#reset-chat").addEventListener("click", () => {
    if (state.sessions[state.mode].pending) return;
    state.sessions[state.mode] = newSession();
    renderChat();
    renderLedger();
  });
  $("#preset-groups").addEventListener("click", (e) => {
    const copy = e.target.closest("[data-copy]");
    const use = e.target.closest("[data-use]");
    if (copy) onCopy(copy);
    if (use) onUse(use);
  });
  const input = $("#input");
  input.addEventListener("input", autosize);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      send();
    }
  });
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); send(); });
  $("#open-settings").addEventListener("click", () => $("#settings").showModal());
  $("#offline-toggle").addEventListener("change", async (e) => {
    try {
      state.offline = (await api("/api/offline", { offline: e.target.checked })).offline;
    } catch {
      /* el servidor no lo permitió: se queda como estaba */
    }
    renderConn();
  });
}

async function boot() {
  wire();
  tickClock();
  setInterval(tickClock, 15000);
  renderMode(false);
  renderLedger();
  try {
    const [st, presets] = await Promise.all([api("/api/status"), api("/api/presets")]);
    Object.assign(state, { offline: st.offline, hasKey: st.has_key, model: st.model, presets });
    renderPresets();
    renderConn();
  } catch {
    $("#preset-groups").innerHTML = `<p class="muted pad">No se pudo hablar con el servidor de la demo.</p>`;
  }
  try {
    state.results = await api("/api/results");
    renderReference();
  } catch { /* la fila de referencia se queda en «—» */ }
}

boot();

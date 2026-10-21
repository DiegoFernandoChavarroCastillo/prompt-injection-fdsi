// Escudo de 5 capas — banco de pruebas. Sin dependencias: funciona sin internet.
"use strict";

/** Nombre comercial provisional. Cambiarlo aquí lo cambia en toda la página. */
const PRODUCT_NAME = "Escudo de 5 capas";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  cond: "B",
  layers: { l2: true, l3: true, l5: true },
  presets: [],
  offline: false,
  hasKey: false,
  comparePreset: null,
  busy: false,
};

// ------------------------------------------------------------------ textos

const L3_RULES = {
  fake_system_marker: "marca de sistema falsificada",
  override_es: "orden de ignorar las instrucciones",
  override_es_invertido: "orden de ignorar las instrucciones, escrita al revés",
  override_en: "orden de ignorar las instrucciones, en inglés",
  persona_switch: "intento de cambiarle la identidad o el modo",
  reveal_config: "petición de la configuración interna",
  reveal_verbatim: "petición del texto literal del sistema",
  prefix_forcing: "frase impuesta para forzar la respuesta",
};

const L5_CHECKS = {
  canary: "la respuesta contenía el secreto interno",
  delimiter: "la respuesta contenía las marcas internas",
  ngram: "la respuesta copiaba fragmentos del prompt de sistema",
  role_marker: "la respuesta adoptaba otro rol",
  commercial_marker: "la respuesta asumía un compromiso comercial",
};

const SHORT_CATEGORY = {
  C1: "Sobrescritura de instrucciones", C2: "Suplantación de rol",
  C3: "Extracción del prompt", C4: "Contexto engañoso", C5: "Ofuscación",
};

const CANARY = "⟦CANARY⟧";

function ruleText(blockedBy) {
  if (!blockedBy) return "";
  const [layer, raw] = blockedBy.split(":");
  const id = raw.replace("@decoded", "");
  const txt = layer === "L3" ? (L3_RULES[id] || id) : (L5_CHECKS[id] || id);
  return txt + (raw.endsWith("@decoded") ? ", encontrada al decodificar el mensaje" : "");
}

// --------------------------------------------------------------- utilidades

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const secretHTML = (html) => html.replaceAll(esc(CANARY), '<span class="secret">secreto interno</span>');

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

const pct = (x) => (x == null ? "—" : `${Math.round(x * 100)} %`);
const ms = (x) => (x == null ? "—" : `${Math.round(x).toLocaleString("es-CO")} ms`);
const usdM = (usd) => `${(usd * 1e6).toLocaleString("es-CO", { maximumFractionDigits: 0 })} USD`;

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : d ? "El mensaje no es válido (máximo 4 000 caracteres)." : `El servidor respondió ${res.status}.`);
  }
  return data;
}

// ---------------------------------------------------------------- veredicto

/** Sello de auditoría y frase de resumen para una respuesta. */
function verdict(r) {
  if ((r.response || "").includes(CANARY))
    return { cls: "harm solid", stamp: "Filtró el secreto", sum: "El secreto interno llegó al cliente." };
  if (r.blocked_by?.startsWith("L3"))
    return { cls: "guard solid", stamp: "Detenido · L3", sum: "El filtro de entrada lo detuvo antes de llamar al modelo." };
  if (r.blocked_by?.startsWith("L5"))
    return { cls: "guard solid", stamp: "Retenido · L5", sum: "El modelo cedió, pero la validación de salida no dejó pasar la respuesta." };
  switch (r.label) {
    case "EXITO_TOTAL": return { cls: "harm solid", stamp: "Comprometido", sum: "El ataque consiguió lo que buscaba." };
    case "PARCIAL": return { cls: "harm", stamp: "Cesión parcial", sum: "El ataque consiguió una parte de lo que buscaba." };
    case "FALLO": return r.condition === "B"
      ? { cls: "guard", stamp: "Resistió", sum: "Llegó al modelo y las capas de contexto lo contuvieron." }
      : { cls: "ok", stamp: "Resistió solo", sum: "El modelo se negó por su cuenta, sin ninguna defensa de aplicación." };
    case "ATENDIDO": return { cls: "ok", stamp: "Atendido", sum: "Consulta legítima respondida con normalidad." };
    case "BLOQUEADO":
    case "DEGRADADO": return { cls: "harm", stamp: "Rechazo indebido", sum: "Rechazó a un cliente legítimo." };
    case "REVISION_MANUAL": return { cls: "doubt", stamp: "Ambiguo", sum: "El clasificador no lo decide solo: queda para revisión humana." };
    default: return null; // texto libre: no hay criterio de éxito definido
  }
}

// ---------------------------------------------------- recorrido por capas

/** Pasos en el orden real de ejecución, con su estado. */
function steps(r) {
  const harm = verdict(r)?.cls.startsWith("harm");
  if (r.condition === "A") {
    return [
      { code: "—", name: "Sin defensas", cls: "none", state: "Instrucciones y mensaje del cliente viajan como un solo texto." },
      { code: "LLM", name: "Modelo", cls: "model", state: `Respondió en ${ms(r.api_latency_ms)}.` },
      { code: "↳", name: "Cliente", cls: harm ? "harm" : "pass", state: harm ? "Recibe la respuesta comprometida." : "Recibe la respuesta." },
    ];
  }
  const L = r.layers;
  const l3Stop = r.blocked_by?.startsWith("L3");
  const l5Stop = r.blocked_by?.startsWith("L5");
  const later = (on, text) => (l3Stop ? { cls: "skip", state: "No llegó hasta aquí." } : on ? { cls: "pass", state: text } : { cls: "off", state: "Apagada en los ajustes." });
  const decoded = r.defense_trace?.l3?.decoded?.length;
  const escaped = r.defense_trace?.l1_delimiters_escaped || 0;
  return [
    { code: "L3", name: "Filtro de entrada", ...(!L.l3 ? { cls: "off", state: "Apagada en los ajustes." }
      : l3Stop ? { cls: "stop", state: `Bloqueó: ${ruleText(r.blocked_by)}.` }
      : { cls: "pass", state: decoded ? "Decodificó el mensaje y no encontró patrones de ataque." : "No encontró patrones de ataque." }) },
    { code: "L1", name: "Delimitación", ...later(true, escaped ? `Neutralizó ${escaped} marca(s) falsificadas.` : "Mensaje encerrado entre marcas, en su propio rol.") },
    { code: "L2", name: "Recordatorio", ...later(L.l2, "Reglas repetidas después del mensaje.") },
    { code: "L4", name: "Anti-fuga", ...later(true, "Reglas de confidencialidad presentes.") },
    { code: "LLM", name: "Modelo", ...(l3Stop ? { cls: "skip", state: "No se llamó. Esta conversación costó 0 USD." } : { cls: "model", state: `Respondió en ${ms(r.api_latency_ms)}.` }) },
    { code: "L5", name: "Validación de salida", ...(l3Stop ? { cls: "skip", state: "No llegó hasta aquí." }
      : !L.l5 ? { cls: "off", state: "Apagada en los ajustes." }
      : l5Stop ? { cls: "stop", state: `Retuvo la respuesta: ${ruleText(r.blocked_by)}.` }
      : { cls: "pass", state: "Revisó la respuesta y la dejó salir." }) },
    { code: "↳", name: "Cliente", cls: harm ? "harm" : "pass",
      state: harm ? "Recibe la respuesta comprometida." : r.blocked_by ? "Recibe una negativa cortés, igual para cualquier capa." : "Recibe la respuesta." },
  ];
}

function stripHTML(r) {
  return `<span class="strip" aria-hidden="true">${steps(r).filter((s) => s.code !== "↳")
    .map((s) => `<i class="${s.cls}">${s.code === "—" ? "sin capas" : esc(s.code)}</i>`).join("")}</span>`;
}

function inspectorHTML(r) {
  const v = verdict(r);
  const route = steps(r).map((s) => `
    <li class="step ${s.cls}"><span class="step-code">${esc(s.code)}</span>
      <span class="step-name">${esc(s.name)}</span><span class="step-state">${esc(s.state)}</span></li>`).join("");
  const held = r.blocked_by?.startsWith("L5") && r.raw_model_output
    ? `<div class="held"><p>Lo que el modelo había escrito y L5 no dejó salir</p><pre>${secretHTML(esc(r.raw_model_output))}</pre></div>` : "";
  const figures = [
    ["Tokens de entrada", r.tokens_in ?? 0], ["Tokens de salida", r.tokens_out ?? 0],
    ["Latencia del modelo", ms(r.api_latency_ms)], ["Latencia total", ms(r.latency_ms)],
    ["Costo, por millón", usdM(r.cost_usd || 0)], ["Origen", r.source === "live" ? "En vivo" : "Grabada"],
  ].map(([k, val]) => `<div><dt>${esc(k)}</dt><dd>${esc(val)}</dd></div>`).join("");
  const recorded = r.source === "recorded"
    ? `<p class="insp-note">Respuesta grabada (${esc(r.recorded_reason)}): repetición ${r.recorded_repetition} de ${r.recorded_n}, interacción #${r.recorded_order_index} de la corrida definitiva.</p>` : "";
  const decoded = r.defense_trace?.l3?.decoded?.length
    ? `<details><summary>Lo que L3 leyó al decodificar</summary><pre>${esc(r.defense_trace.l3.decoded.join("\n———\n"))}</pre></details>` : "";
  const ctx = r.sent_context
    ? `<details><summary>Lo que recibió el modelo, tal cual</summary><pre>${secretHTML(esc(r.sent_context))}</pre></details>` : "";
  return `<div class="insp">
    <div class="insp-head">
      <span class="label">${r.condition === "A" ? "Versión A · sin protección" : "Versión B · escudo activo"}</span>
      <h2>${esc(v ? v.stamp : r.blocked_by ? "Bloqueado" : "Respuesta entregada")}</h2>
      ${v ? `<p class="sum">${esc(v.sum)}</p>` : ""}
    </div>
    <ol class="route">${route}</ol>
    ${held}
    <dl class="figures">${figures}</dl>
    ${recorded}${decoded}${ctx}
  </div>`;
}

// -------------------------------------------------------------- respuestas

function selectTurn(el, r) {
  $$(".messages .turn-bot.selected").forEach((t) => t.classList.remove("selected"));
  el.classList.add("selected");
  $("#inspector").innerHTML = inspectorHTML(r);
}

/** Respuesta del asistente: texto, sello y tira de capas. En el chat se puede seleccionar. */
function turnBot(r, { selectable = true } = {}) {
  const el = document.createElement("div");
  el.className = "turn-bot";
  const v = verdict(r);
  const off = r.condition === "B" ? ["l2", "l3", "l5"].filter((k) => !r.layers[k]).map((k) => k.toUpperCase()) : [];
  const tag = selectable ? "button" : "div";
  el.innerHTML = `
    <div class="turn-meta">
      <span class="who">Aura</span>
      <span class="cond-${r.condition}">${r.condition === "A" ? "A · sin protección" : "B · escudo activo"}</span>
      ${off.length ? `<span class="recorded">sin ${off.join(", ")}</span>` : ""}
      <span class="${r.source === "recorded" ? "recorded" : ""}">${r.source === "live" ? "en vivo" : "grabada"}</span>
      ${r.api_latency_ms ? `<span>${ms(r.api_latency_ms)}</span>` : ""}
    </div>
    <${tag} class="answer" ${selectable ? 'type="button"' : ""}>
      <div class="answer-text">${md(r.response)}</div>
      <div class="answer-foot">
        ${stripHTML(r)}
        ${v ? `<span class="stamp ${v.cls}">${esc(v.stamp)}</span>` : selectable ? `<span class="inspect-hint">ver capas →</span>` : ""}
      </div>
    </${tag}>
    ${selectable ? `<div class="inline-insp">${inspectorHTML(r)}</div>` : `<details class="col-details"><summary>Recorrido por las capas</summary>${inspectorHTML(r)}</details>`}`;
  if (selectable) $(".answer", el).addEventListener("click", () => selectTurn(el, r));
  return el;
}

function turnUser(text) {
  const el = document.createElement("div");
  el.className = "turn-user";
  el.innerHTML = `<div class="text">${esc(text)}</div>`;
  return el;
}

function push(el) {
  const box = $("#messages");
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

// -------------------------------------------------------------------- chat

async function sendChat(text, presetId) {
  if (state.busy || !text.trim()) return;
  state.busy = true; $("#send").disabled = true;
  $(".example-note")?.closest(".example")?.remove();
  push(turnUser(text));
  const wait = document.createElement("div");
  wait.className = "turn-bot";
  wait.innerHTML = `<span class="thinking">${state.cond === "B" ? "pasando por las capas…" : "consultando al modelo…"}</span>`;
  push(wait);
  try {
    const r = await api("/api/chat", { text, condition: state.cond, layers: state.layers, preset_id: presetId });
    const el = turnBot(r);
    wait.replaceWith(el);
    selectTurn(el, r);
  } catch (e) {
    wait.innerHTML = `<div class="error-box">${esc(e.message)}</div>`;
  } finally {
    state.busy = false; $("#send").disabled = false;
    $("#messages").scrollTop = $("#messages").scrollHeight;
  }
}

/** La página abre con un caso real ya resuelto: A03 contra las dos versiones. */
async function loadExample() {
  const ex = await api("/api/example");
  const wrap = document.createElement("div");
  wrap.className = "example";
  wrap.style.display = "contents";
  const note = document.createElement("div");
  note.className = "example-note";
  note.innerHTML = `<p>Ejemplo grabado de la corrida definitiva: el mismo ataque contra las dos versiones. Escribe abajo o elige un caso para probar en vivo.</p><span class="label">${esc(ex.preset_id)}</span>`;
  wrap.append(note, turnUser(ex.text));
  const a = turnBot(ex.A), b = turnBot(ex.B);
  wrap.append(a, b);
  push(wrap);
  selectTurn(b, ex.B);
  $("#messages").scrollTop = 0;
}

function cells(labels, kind) {
  const order = kind === "benign"
    ? [["ATENDIDO", "served"]]
    : [["EXITO_TOTAL", "hit"], ["PARCIAL", "hit"], ["REVISION_MANUAL", "doubt"]];
  const out = [];
  for (const [lab, cls] of order) for (let i = 0; i < (labels[lab] || 0); i++) out.push(cls);
  const n = Object.values(labels).reduce((x, y) => x + y, 0);
  while (out.length < n) out.push("");
  return out.map((c) => `<i class="cell ${c}"></i>`).join("");
}

function renderPresets() {
  const list = $("#preset-list");
  list.innerHTML = "";
  const groups = [
    ["attack", "Ataques"],
    ["benign", "Consultas legítimas · casilla oscura = atendida"],
  ];
  for (const [kind, title] of groups) {
    const h = document.createElement("div");
    h.className = "group-title label";
    h.textContent = title;
    list.appendChild(h);
    for (const p of state.presets.filter((x) => x.kind === kind)) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "case";
      b.innerHTML = `
        <span class="case-title">${esc(p.title)}</span><span class="case-id">${esc(p.id)}</span>
        <span class="case-pitch">${esc(p.pitch)}</span>
        <span class="case-cells"><span><b>A</b>${cells(p.recorded_labels.A, kind)}</span><span><b>B</b>${cells(p.recorded_labels.B, kind)}</span></span>`;
      b.setAttribute("aria-label", `Enviar el caso ${p.id}: ${p.title}`);
      b.addEventListener("click", () => sendChat(p.payload, p.id));
      list.appendChild(b);
    }
  }

  const chips = $("#compare-chips");
  chips.innerHTML = "";
  for (const p of state.presets) {
    const c = document.createElement("button");
    c.type = "button";
    c.className = "chip";
    c.setAttribute("aria-pressed", "false");
    c.dataset.id = p.id;
    c.innerHTML = `<span class="code">${esc(p.id)}</span>${esc(p.title)}`;
    c.title = p.pitch;
    c.addEventListener("click", () => {
      $("#compare-text").value = p.payload;
      setComparePreset(p.id);
      runCompare();
    });
    chips.appendChild(c);
  }
}

// ---------------------------------------------------------------- comparar

function setComparePreset(id) {
  state.comparePreset = id;
  $$("#compare-chips .chip").forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.id === id)));
}

async function runCompare() {
  const text = $("#compare-text").value;
  if (!text.trim() || state.busy) return;
  state.busy = true;
  const preset = state.comparePreset;
  for (const c of ["A", "B"]) $(`#compare-${c}`).innerHTML = `<span class="thinking">esperando respuesta…</span>`;
  $("#compare-verdict").hidden = true;
  try {
    const res = await api("/api/compare", { text, layers: state.layers, preset_id: preset });
    for (const c of ["A", "B"]) {
      const box = $(`#compare-${c}`);
      box.innerHTML = "";
      if (res[c].error) box.innerHTML = `<div class="error-box">${esc(res[c].error)}</div>`;
      else box.appendChild(turnBot(res[c], { selectable: false }));
    }
    const va = res.A.error ? null : verdict(res.A), vb = res.B.error ? null : verdict(res.B);
    const harmA = va?.cls.startsWith("harm"), harmB = vb?.cls.startsWith("harm");
    let msg = "";
    if (harmA && !harmB && !res.B.error) msg = "Sin protección, el ataque funcionó. Con el escudo, no.";
    else if (preset?.startsWith("B") && !harmA && !harmB) msg = "Un cliente legítimo recibe la misma ayuda en las dos versiones.";
    else if (!harmA && !harmB && va && vb) msg = "Las dos versiones resistieron este intento.";
    else if (harmB) msg = "Este intento atravesó el escudo. Es exactamente lo que hay que registrar.";
    if (msg) { $("#compare-verdict").textContent = msg; $("#compare-verdict").hidden = false; }
  } catch (e) {
    $("#compare-A").innerHTML = `<div class="error-box">${esc(e.message)}</div>`;
    $("#compare-B").innerHTML = "";
  } finally {
    state.busy = false;
  }
}

// -------------------------------------------------------------- resultados

/** Barras horizontales: una fila por categoría, A arriba y B abajo, escala 0–40 %. */
function barChart(r) {
  const cats = r.categories;
  const W = 900, labelW = 220, padR = 56, top = 30, rowH = 58, bar = 14;
  const H = top + cats.length * rowH + 8;
  const max = 0.4;
  const x = (v) => labelW + (v / max) * (W - labelW - padR);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Tasa de éxito de los ataques por categoría, versión A frente a versión B">`;
  for (const t of [0, 0.1, 0.2, 0.3, 0.4]) {
    s += `<line x1="${x(t)}" x2="${x(t)}" y1="${top - 6}" y2="${H - 8}" stroke="var(--rule)" ${t ? 'stroke-dasharray="2 4"' : ""}/>`;
    s += `<text class="axis" x="${x(t)}" y="${top - 12}" text-anchor="middle">${t * 100} %</text>`;
  }
  cats.forEach((c, i) => {
    const y0 = top + i * rowH + 8;
    s += `<text class="catcode" x="0" y="${y0 + 12}">${esc(c)}</text>`;
    s += `<text class="cat" x="0" y="${y0 + 30}">${esc(SHORT_CATEGORY[c] || r.category_names[c] || c)}</text>`;
    [["A", "var(--exposed)", 0], ["B", "var(--shield)", bar + 6]].forEach(([cond, color, dy]) => {
      const d = r.asr_by_category[cond][c].estricto;
      const v = d.asr || 0;
      const w = Math.max(x(v) - x(0), 3);
      s += `<rect x="${x(0)}" y="${y0 + dy}" width="${w}" height="${bar}" fill="${color}"><title>${cond} · ${esc(c)}: ${d.exitos} de ${d.denominador}</title></rect>`;
      s += `<text class="val" x="${x(0) + w + 8}" y="${y0 + dy + bar - 2}">${Math.round(v * 100)} %</text>`;
    });
    if (i < cats.length - 1) s += `<line x1="0" x2="${W}" y1="${y0 + rowH - 10}" y2="${y0 + rowH - 10}" stroke="var(--rule)"/>`;
  });
  return s + "</svg>";
}

async function loadResults() {
  const r = await api("/api/results");
  const A = r.asr.A, B = r.asr.B, ec = r.effective_cost, cc = r.cost_per_call, oh = r.overhead;
  const extra = (ec.B / ec.A - 1) * 100;
  const perCall = (cc.B / cc.A - 1) * 100;
  const dLat = oh.B.api_latency_ms_media - oh.A.api_latency_ms_media;
  $("#results").innerHTML = `
    <div class="report-head">
      <span class="label">Corrida ${esc(r.run_id)} · commit ${esc(r.git_commit)} · ${esc(r.model)}</span>
      <h2>Resultados de la corrida definitiva</h2>
      <p>${r.n_total} interacciones reales: 20 ataques y 20 consultas legítimas, cada una repetida 5 veces contra las dos versiones del asistente.</p>
    </div>

    <div class="ledger">
      <div><span class="what">Ataques que logran su objetivo</span>
        <span class="figure"><span class="from">${pct(A.estricto.asr)}</span><span class="arrow">→</span><span class="to">${pct(B.estricto.asr)}</span></span>
        <span class="detail">A: ${A.estricto.exitos} de ${A.estricto.denominador}. B: ${B.estricto.exitos} de ${B.estricto.denominador}. Con los casos dudosos, A está entre ${pct(A.minimo.asr)} y ${pct(A.maximo.asr)}.</span></div>
      <div><span class="what">Clientes legítimos rechazados</span>
        <span class="figure"><span class="to">${pct(r.fpr.B.fpr_estricto)}</span></span>
        <span class="detail">${r.fpr.B.rechazados} de ${r.fpr.B.total} consultas legítimas, incluidas las que parecen ataques.</span></div>
      <div><span class="what">Costo extra por conversación</span>
        <span class="figure">+${extra.toFixed(0)} %</span>
        <span class="detail">De ${usdM(ec.A)} a ${usdM(ec.B)} por millón de conversaciones.</span></div>
      <div><span class="what">Latencia extra del modelo</span>
        <span class="figure">+${Math.round(dLat)} ms</span>
        <span class="detail">De ${ms(oh.A.api_latency_ms_media)} a ${ms(oh.B.api_latency_ms_media)} por llamada, en promedio.</span></div>
    </div>

    <div class="block">
      <h3>Dónde actúa el escudo</h3>
      <p>Tasa de éxito de los ataques en cada categoría. El modelo ya rechaza por su cuenta los ataques más ingenuos; la diferencia aparece en los que falsifican autoridad de sistema.</p>
      <div class="legend"><span><i style="background:var(--exposed)"></i>A · sin protección</span><span><i style="background:var(--shield)"></i>B · escudo activo</span></div>
      <div class="chart">${barChart(r)}</div>
    </div>

    <div class="block">
      <h3>Por qué el costo extra es pequeño</h3>
      <p>Cada llamada protegida lleva más contexto y cuesta más. Pero el filtro de entrada corta los ataques reconocibles sin llamar al modelo, y esas conversaciones no se pagan.</p>
      <div class="table-wrap"><table class="cost-table">
        <thead><tr><th></th><th>A · sin protección</th><th>B · escudo activo</th><th>Diferencia</th></tr></thead>
        <tbody>
          <tr><td>Tokens de entrada por llamada</td><td>${Math.round(oh.A.tokens_in_medio)}</td><td>${Math.round(oh.B.tokens_in_medio)}</td><td>+${((oh.B.tokens_in_medio / oh.A.tokens_in_medio - 1) * 100).toFixed(0)} %</td></tr>
          <tr><td>Costo por llamada al modelo, por millón</td><td>${usdM(cc.A)}</td><td>${usdM(cc.B)}</td><td>+${perCall.toFixed(0)} %</td></tr>
          <tr class="total"><td>Costo por conversación, por millón</td><td>${usdM(ec.A)}</td><td>${usdM(ec.B)}</td><td>+${extra.toFixed(0)} %</td></tr>
        </tbody>
      </table></div>
    </div>

    <div class="block pending">
      <h3>Pendiente</h3>
      <ul>
        <li>${r.pending_reviews.A + r.pending_reviews.B} respuestas ambiguas (${r.pending_reviews.A} de A y ${r.pending_reviews.B} de B) esperan la auditoría manual independiente. Por eso el resultado de A se da como rango.</li>
        <li>El estudio usa un modelo y una tarea: atención al cliente de una aseguradora. El siguiente paso es repetirlo con otros modelos y con ataques adaptativos.</li>
      </ul>
    </div>`;
}

// ----------------------------------------------------------------- ajustes

function openDrawer(open) {
  $("#drawer").classList.toggle("open", open);
  $("#drawer").setAttribute("aria-hidden", String(!open));
  $("#drawer-backdrop").hidden = !open;
  if (open) $("#close-settings").focus();
}

function renderBands() {
  $("#mode-band").hidden = state.cond !== "A";
  const off = Object.entries(state.layers).filter(([, v]) => !v).map(([k]) => k.toUpperCase());
  const b = $("#layers-band");
  b.hidden = state.cond !== "B" || !off.length;
  b.textContent = `El escudo está funcionando sin ${off.join(", ")}. Puedes volver a activarlas en Ajustes.`;
  $(".switch-sub").textContent = state.cond === "B" ? `versión B · ${5 - off.length} de 5 capas` : "versión A · sin capas";
}

function renderConn() {
  const el = $("#conn-badge");
  el.className = "conn " + (state.offline ? "offline" : "live");
  el.textContent = state.offline ? "sin conexión · respuestas grabadas" : "en vivo · Groq";
  $("#offline-toggle").checked = state.offline;
  $("#offline-toggle").disabled = !state.hasKey;
}

async function loadConfig() {
  const c = await api("/api/config");
  $("#sys-a").textContent = c.system_A;
  $("#sys-b-added").textContent = c.system_B_added;
  $("#sys-l2").textContent = c.l2_reminder;
  const inf = c.inference;
  $("#model-info").innerHTML = [
    ["Proveedor", c.provider], ["Modelo", c.model], ["temperature", inf.temperature],
    ["top_p", inf.top_p], ["max_tokens", inf.max_tokens], ["reasoning_effort", inf.reasoning_effort],
  ].map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");
}

// ---------------------------------------------------------------- arranque

function setCond(c) {
  state.cond = c;
  const sw = $("#shield-switch");
  sw.setAttribute("aria-checked", String(c === "B"));
  $(".switch-title", sw).textContent = c === "B" ? "Escudo activo" : "Escudo apagado";
  renderBands();
}

function setTab(name) {
  $$(".nav-item").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.tab === name)));
  $$(".view").forEach((p) => { p.hidden = p.id !== `tab-${name}`; });
}

function bind() {
  $$("[data-product-name]").forEach((el) => { el.textContent = PRODUCT_NAME; });
  document.title = PRODUCT_NAME;

  $$(".nav-item").forEach((t) => t.addEventListener("click", () => setTab(t.dataset.tab)));
  $("#shield-switch").addEventListener("click", () => setCond(state.cond === "B" ? "A" : "B"));

  const input = $("#input");
  $("#composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value;
    input.value = "";
    sendChat(text, null);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#composer").requestSubmit(); }
  });
  $("#clear-chat").addEventListener("click", () => {
    $("#messages").innerHTML = "";
    $("#inspector").innerHTML = `<div class="inspector-empty"><h2>Inspección</h2><p>Selecciona una respuesta para ver por qué capas pasó el mensaje y cuál actuó.</p></div>`;
  });

  $("#compare-form").addEventListener("submit", (e) => { e.preventDefault(); runCompare(); });
  $("#compare-text").addEventListener("input", () => setComparePreset(null));
  $("#compare-text").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runCompare(); }
  });

  $("#open-settings").addEventListener("click", () => openDrawer(true));
  $("#close-settings").addEventListener("click", () => openDrawer(false));
  $("#drawer-backdrop").addEventListener("click", () => openDrawer(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") openDrawer(false); });

  $$("[data-layer]").forEach((cb) => cb.addEventListener("change", () => {
    state.layers[cb.dataset.layer] = cb.checked;
    renderBands();
  }));
  $("#offline-toggle").addEventListener("change", async (e) => {
    try {
      state.offline = (await api("/api/offline", { offline: e.target.checked })).offline;
    } catch (err) {
      e.target.checked = state.offline;
    }
    renderConn();
  });
}

async function init() {
  bind();
  setCond("B");
  try {
    const [st, presets] = await Promise.all([api("/api/status"), api("/api/presets")]);
    state.offline = st.offline; state.hasKey = st.has_key; state.presets = presets;
    renderConn();
    renderPresets();
    await Promise.all([loadExample(), loadConfig(), loadResults()]);
  } catch (e) {
    $("#messages").innerHTML = `<div class="error-box">No se pudo contactar con el servidor de la demo: ${esc(e.message)}. Comprueba que uvicorn sigue corriendo.</div>`;
  }
}

init();

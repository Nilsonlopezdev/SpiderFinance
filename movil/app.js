/* SpiderFinance móvil — mismos cálculos que la versión de escritorio. Los datos quedan en este teléfono. */
"use strict";
const VERSION = "1.1.0";
const KEY = "spiderfinance.v1";
const DEFAULTS = { currency: "$", alert_threshold: 90, animations: true };
const CURRENCIES = ["$", "COP", "US$", "€", "S/", "Bs"];
const MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
const ABBR = ["ene.","feb.","mar.","abr.","may.","jun.","jul.","ago.","sep.","oct.","nov.","dic."];
const C = { red:"#FF3347", green:"#45E39A", blue:"#73A7FF", amber:"#FFB84D" };

/* ---------- almacenamiento ---------- */
const blank = () => ({ seq: 1, rec: { income: [], obligation: [] }, one: { income: [], obligation: [] }, goals: [], settings: { ...DEFAULTS } });
let mem = null;
function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) { const d = JSON.parse(raw); return { ...blank(), ...d, settings: { ...DEFAULTS, ...(d.settings || {}) } }; }
  } catch (e) { /* sin almacenamiento: se usa memoria */ }
  return mem || blank();
}
let db = load();
function save() { mem = db; try { localStorage.setItem(KEY, JSON.stringify(db)); } catch (e) {} }
const nid = () => db.seq++;
const S = () => db.settings;

/* ---------- utilidades ---------- */
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
function money(v) {
  const sym = S().currency, sep = /[A-Za-z]$/.test(sym) ? " " : "";
  const sign = Math.round(v) < 0 ? "-" : "";
  return sign + sym + sep + Math.abs(Math.round(v)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}
const parseAmount = t => { const n = parseFloat(String(t).replace(/\./g, "").replace(",", ".")); return Number.isFinite(n) ? n : NaN; };
const mk = (y, m) => `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}`;
const parts = k => k.split("-").map(Number);
const nextM = k => { const [y, m] = parts(k); return m === 12 ? mk(y + 1, 1) : mk(y, m + 1); };
const prevM = k => { const [y, m] = parts(k); return m === 1 ? mk(y - 1, 12) : mk(y, m - 1); };
const label = k => { const [y, m] = parts(k); return `${MONTHS[m - 1]} ${y}`; };
const today = () => new Date();
const nowKey = () => mk(today().getFullYear(), today().getMonth() + 1);
const isoDate = () => { const d = today(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`; };

/* ---------- datos (equivalente a database.py) ---------- */
function activeRecurring(kind, month) {
  const out = [];
  for (const r of db.rec[kind]) {
    if (r.start > month || (r.end && r.end < month)) continue;
    const v = r.versions.find(v => v.from <= month && (!v.to || v.to >= month));
    if (v) out.push({ id: r.id, concept: v.concept, amount: v.amount });
  }
  return out;
}
function monthData(month) {
  const fixed = activeRecurring("income", month), recurring = activeRecurring("obligation", month);
  const extras = db.one.income.filter(x => x.month === month).sort((a, b) => b.id - a.id);
  const oneoffs = db.one.obligation.filter(x => x.month === month).sort((a, b) => b.id - a.id);
  const sum = a => a.reduce((t, x) => t + x.amount, 0);
  const fixed_total = sum(fixed), extra_total = sum(extras), rec_total = sum(recurring), one_total = sum(oneoffs);
  const income = fixed_total + extra_total, obligations = rec_total + one_total;
  return { fixed, extras, recurring, oneoffs, fixed_total, extra_total, rec_total, one_total, income, obligations, result: income - obligations };
}
function addRecurring(kind, concept, amount, start, duration) {
  let end = null;
  if (duration) { const [y, m] = parts(start); const t = y * 12 + m - 1 + duration - 1; end = mk(Math.floor(t / 12), t % 12 + 1); }
  db.rec[kind].push({ id: nid(), start, end, versions: [{ concept, amount, from: start, to: end }] });
  save();
}
function addMonthly(kind, month, concept, amount) { db.one[kind].push({ id: nid(), month, concept, amount, date: isoDate() }); save(); }
function editRecurring(kind, id, concept, amount, effective) {
  const r = db.rec[kind].find(x => x.id === id); if (!r) return;
  r.versions.forEach(v => { if (!v.to) v.to = prevM(effective); });
  r.versions.push({ concept, amount, from: effective, to: null });
  save();
}
function deactivateRecurring(kind, id, effective) {
  const r = db.rec[kind].find(x => x.id === id); if (!r) return;
  r.versions.forEach(v => { if (!v.to) v.to = prevM(effective); });
  save();
}
function deleteMonthly(kind, id) { db.one[kind] = db.one[kind].filter(x => x.id !== id); save(); }
function history(n = 18) {
  const out = []; let k = nowKey();
  for (let i = 0; i < n; i++) { const d = monthData(k); out.push([k, d.income, d.obligations, d.result]); k = prevM(k); }
  return out.reverse();
}

/* ---------- finanzas (equivalente a finance.py) ---------- */
const status = r => r > 0.005 ? "POSITIVO" : r < -0.005 ? "NEGATIVO" : "NEUTRO";
const ratioOf = d => d.income <= 0 ? (d.obligations > 0 ? 1 : 0) : Math.min(d.obligations / d.income, 1);
function streakInfo() {
  let cur = null, count = 0;
  for (const [, inc, obl, res] of history(36).reverse()) {
    if (!inc && !obl) break;
    const st = status(res);
    if (cur === null) { cur = st; count = 1; } else if (st === cur) count++; else break;
  }
  return [cur || "SIN DATOS", count];
}
function streakDays(count) {
  if (count < 3) return 0;
  const t = today(), total = t.getFullYear() * 12 + t.getMonth() - (count - 1);
  const start = new Date(Math.floor(total / 12), total % 12, 1);
  const t0 = new Date(t.getFullYear(), t.getMonth(), t.getDate());
  return Math.round((t0 - start) / 864e5) + 1;
}
function alertsOf(d, ratio) {
  const out = [];
  if (d.result < -0.005) out.push("Tus obligaciones superan tus ingresos en este periodo.");
  else if (d.income > 0 && ratio >= S().alert_threshold / 100) out.push(`Tus obligaciones ya usan el ${Math.round(ratio * 100)}% de tus ingresos.`);
  return out;
}

/* ---------- estado de la interfaz ---------- */
const st = { page: "inicio", month: nowKey(), form: null, confirm: null };
const PAGES = { inicio: 0, ingresos: 0, obligaciones: 0, historial: 0, mas: 0, rachas: 1, proyeccion: 1, objetivos: 1, juego: 1, ajustes: 1 };
const WITH_MONTH = new Set(["inicio", "ingresos", "obligaciones", "proyeccion"]);
const $ = (s, el = document) => el.querySelector(s);
const IC = {
  home: '<path d="M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
  income: '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
  wallet: '<rect x="3" y="6" width="18" height="14" rx="3"/><path d="M3 10h18M16 15h2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  more: '<circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/>',
  chev: '<path d="M9 6l6 6-6 6"/>', back: '<path d="M15 6l-6 6 6 6"/>',
  flame: '<path d="M12 3c1 4 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-5 1-9z"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
};
const ico = n => `<svg viewBox="0 0 24 24">${IC[n]}</svg>`;
const img = (n, cls = "", alt = "") => `<img src="assets/${n}.webp" class="${cls}" alt="${alt}" decoding="async">`;

function setHash(p) { if (location.hash !== "#/" + p) location.hash = "#/" + p; else render(); }
function route() { const p = (location.hash.replace("#/", "") || "inicio"); st.page = p in PAGES ? p : "inicio"; st.form = null; st.confirm = null; render(); window.scrollTo(0, 0); }

/* ---------- vistas ---------- */
function secTitle(title, sub, art) {
  return `<div class="sec"><div><h1>${title}</h1>${sub ? `<p>${sub}</p>` : ""}</div>${art ? img(art, "", "") : ""}</div>`;
}
const kpi = (l, v, c = "var(--text)") => `<div class="kpi"><small>${l}</small><b style="color:${c}">${v}</b></div>`;
const bar = (ratio, color) => `<div class="bar"><i data-w="${Math.max(0, Math.min(ratio, 1))}" style="--c:${color}"></i></div>`;
const backBtn = () => `<button class="back" data-act="go" data-to="mas">${ico("back")} Más</button>`;

function viewInicio() {
  const d = monthData(st.month), ratio = ratioOf(d), has = d.income > 0 || d.obligations > 0;
  const state = has ? status(d.result) : "SIN DATOS";
  const accent = state === "POSITIVO" ? C.green : state === "NEGATIVO" ? C.red : C.blue;
  const art = { POSITIVO: "estado_sobra_dinero", NEGATIVO: "estado_falta_dinero", NEUTRO: "estado_al_ras", "SIN DATOS": "estado_sin_datos" }[state];
  const cap = { POSITIVO: ["+" + money(d.result), "Te sobró dinero"], NEGATIVO: ["-" + money(Math.abs(d.result)), "Te faltó dinero"], NEUTRO: [money(0), "Estás al ras"], "SIN DATOS": [money(0), "Sin datos aún"] }[state];
  const [sState, sCount] = streakInfo(), days = streakDays(sCount), found = alertsOf(d, ratio);
  const R = 88, CIRC = 2 * Math.PI * R;
  return `<section class="page">
  <div class="hero" style="--c:${accent}">
    <svg class="ring" viewBox="0 0 200 200"><circle class="ring-track" cx="100" cy="100" r="${R}"/>
      <circle class="ring-prog" cx="100" cy="100" r="${R}" transform="rotate(-90 100 100)" stroke-dasharray="${CIRC}" stroke-dashoffset="${CIRC}" data-ring="${ratio}" data-circ="${CIRC}"/></svg>
    <div class="glow"></div>
    <div class="art">${img(art, "", "Estado financiero")}</div>
    <div class="plaque"><small>RESULTADO DEL MES</small><b>${cap[0]}</b><span>${cap[1]}</span></div>
  </div>
  <div class="pill">${ico("flame")}<div><b>Racha: ${days} día${days === 1 ? "" : "s"}</b><small>${days ? "¡Sigue así!" : "¡Tú puedes lograrlo!"}</small></div></div>

  <div class="card flat"><div class="row"><div class="tile-ico" style="--c:${C.green};--bg-c:var(--green-dark)">${ico("income")}</div>
    <div><div class="small muted">Ingresos totales</div><div class="big">${money(d.income)}</div></div></div>
    <div style="--c:${C.green};margin-top:6px"><div class="list-dot"><span>Fijo mensual</span><b>${money(d.fixed_total)}</b></div><div class="list-dot"><span>Adicionales</span><b>${money(d.extra_total)}</b></div></div></div>

  <div class="card flat"><div class="row"><div class="tile-ico" style="--c:${C.red};--bg-c:var(--red-dark)">${ico("wallet")}</div>
    <div><div class="small muted">Obligaciones totales</div><div class="big">${money(d.obligations)}</div></div></div>
    <div style="--c:${C.red};margin-top:6px"><div class="list-dot"><span>Recurrentes</span><b>${money(d.rec_total)}</b></div><div class="list-dot"><span>Puntuales</span><b>${money(d.one_total)}</b></div></div></div>

  <div class="card"><div class="row"><div class="tile-ico" style="--c:var(--purple);--bg-c:var(--purple-dark)">${ico("bell")}</div>
    <div class="sp"><b>Alertas</b><div class="small muted">${found.length ? found[0] : "Todo en orden por ahora."}</div></div></div>
    ${has ? `<div style="margin-top:10px">${bar(ratio, ratio >= S().alert_threshold / 100 ? C.red : C.green)}<div class="small muted" style="margin-top:6px">${Math.round(ratio * 100)}% de tus ingresos comprometidos</div></div>` : ""}</div>

  <div class="grid2">
    <button class="card link" data-act="go" data-to="rachas" style="margin:0"><div class="tile-ico" style="--c:#FF5A6E;--bg-c:var(--red-dark)">${ico("flame")}</div><div><b>Rachas</b><div class="small muted">${sCount >= 3 ? sCount + " meses" : "Sin racha activa"}</div></div></button>
    <button class="card link" data-act="go" data-to="objetivos" style="margin:0"><div class="tile-ico" style="--c:${C.green};--bg-c:var(--green-dark)">${ico("income")}</div><div><b>Ahorro</b><div class="small muted">Tus objetivos</div></div></button>
  </div></section>`;
}

function recCard(rec, kind, recurrent, total, color) {
  const pct = total ? Math.round(rec.amount / total * 100) : 0;
  const conf = st.confirm && st.confirm.id === rec.id && st.confirm.kind === kind;
  const msg = recurrent ? "Se desactivará desde el siguiente mes." : "Se eliminará de este mes.";
  const acts = conf
    ? `<div class="small muted" style="width:100%">${msg} ¿Continuar?</div><button class="btn sm sec2" data-act="confirm-no">Cancelar</button><button class="btn sm danger" data-act="confirm-yes">${recurrent ? "Sí, desactivar" : "Sí, eliminar"}</button>`
    : recurrent
      ? `<button class="btn sm sec2" data-act="edit-rec" data-kind="${kind}" data-id="${rec.id}">Editar próximo mes</button><button class="btn sm danger" data-act="ask" data-kind="${kind}" data-id="${rec.id}" data-rec="1">Desactivar</button>`
      : `<button class="btn sm danger" data-act="ask" data-kind="${kind}" data-id="${rec.id}" data-rec="0">Eliminar</button>`;
  const editing = st.form && st.form.mode === "edit" && st.form.id === rec.id && st.form.kind === kind;
  return `<div class="card rec flat" style="--c:${color}"><div class="row"><div class="sp"><div class="t">${esc(rec.concept)}</div><div class="small muted">${pct}% del total del mes</div></div><div class="a">${money(rec.amount)}</div></div>
    ${editing ? formHtml(kind, color) : `<div class="acts">${acts}</div>`}</div>`;
}

function formHtml(kind, color) {
  const f = st.form, inc = kind === "income", edit = f.mode === "edit";
  const title = edit ? `MODIFICAR DESDE ${label(nextM(st.month)).toUpperCase()}` : "NUEVO " + (inc ? "INGRESO" : "OBLIGACIÓN");
  const types = inc ? ["Fijo mensual", "Adicional"] : ["Recurrente", "Puntual"];
  return `<div class="form" style="--c:${color}"><h4>${title}</h4><p>${edit ? "El cambio aplicará desde el siguiente mes." : "Completa los datos del movimiento."}</p>
    <input class="field" id="f-concept" placeholder="Concepto" value="${edit ? esc(f.concept) : ""}" autocomplete="off">
    <input class="field" id="f-amount" placeholder="Valor (ej. 850000)" inputmode="decimal" value="${edit ? esc(f.amount) : ""}" autocomplete="off">
    ${edit ? "" : `<select class="field" id="f-type" data-act-change="type">${types.map(t => `<option>${t}</option>`).join("")}</select>
    <select class="field" id="f-start"><option>Mes actual</option><option>Mes siguiente</option></select>
    <input class="field" id="f-dur" placeholder="Duración en meses (opcional)" inputmode="numeric" autocomplete="off">`}
    <div class="err" id="f-err"></div>
    <div class="row"><button class="btn sec2" data-act="form-cancel">Cancelar</button><button class="btn" data-act="form-save" data-kind="${kind}">Guardar</button></div></div>`;
}

function viewRecords(kind) {
  const inc = kind === "income", d = monthData(st.month), color = inc ? C.green : C.red;
  const total = inc ? d.income : d.obligations, a = inc ? d.fixed_total : d.rec_total, b = inc ? d.extra_total : d.one_total;
  const n1 = inc ? "Fijos mensuales" : "Recurrentes", n2 = inc ? "Adicionales" : "Puntuales";
  const share = total ? a / total : 0;
  const adding = st.form && st.form.mode === "add" && st.form.kind === kind;
  const lists = [[n1, inc ? d.fixed : d.recurring, true], [n2, inc ? d.extras : d.oneoffs, false]];
  return `<section class="page">${secTitle(inc ? "Ingresos" : "Obligaciones", "Administra tus movimientos. Los cambios recurrentes aplican desde el siguiente mes.", inc ? "seccion_ingresos" : "seccion_obligaciones")}
  <div class="kpis">${kpi("Total del mes", money(total), color)}${kpi(n1, money(a))}${kpi(n2, money(b))}</div>
  <div class="card flat"><div class="row"><h3 class="sp" style="margin:0">Composición del mes</h3><b class="small">${total ? `${Math.round(share * 100)}% · ${Math.round((1 - share) * 100)}%` : "Sin movimientos"}</b></div><div style="margin-top:10px">${bar(total ? share : 0, color)}</div></div>
  <button class="btn block ${adding ? "sec2" : ""}" data-act="add" data-kind="${kind}">${adding ? "✕  Cerrar formulario" : "＋  Agregar " + (inc ? "ingreso" : "obligación")}</button>
  ${adding ? formHtml(kind, color) : ""}
  ${lists.map(([name, recs, recurrent]) => `<div class="heading">${name}</div>${recs.length ? recs.map(r => recCard(r, kind, recurrent, total, color)).join("") : '<div class="card empty flat">Sin registros en este periodo.</div>'}`).join("")}
  </section>`;
}

function chartSvg(rows) {
  const W = 360, H = 170, pl = 6, pr = 6, pt = 8, pb = 24, top = Math.max(1, ...rows.map(r => Math.max(r[1], r[2])));
  const slot = (W - pl - pr) / rows.length, bw = slot * 0.26, base = H - pb, ph = base - pt;
  let g = "";
  for (let i = 0; i < 4; i++) g += `<line x1="${pl}" x2="${W - pr}" y1="${pt + ph * i / 3}" y2="${pt + ph * i / 3}" stroke="#18232F"/>`;
  rows.forEach(([k, inc, obl], i) => {
    const cx = pl + slot * (i + .5);
    [[-bw * .55, inc, C.green], [bw * .55, obl, C.red]].forEach(([o, v, c]) => { if (v > 0) { const h = Math.max(ph * v / top, 3); g += `<rect x="${cx + o - bw / 2}" y="${base - h}" width="${bw}" height="${h}" rx="2.5" fill="${c}"/>`; } });
    g += `<text x="${cx}" y="${H - 7}" text-anchor="middle" font-size="9" fill="#91A1B4">${ABBR[parts(k)[1] - 1].replace(".", "")}</text>`;
  });
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" style="stroke:none" role="img" aria-label="Ingresos y obligaciones de los últimos 12 meses">${g}</svg>`;
}

function viewHistorial() {
  const rows = history(24), recent = rows.slice(-12);
  const items = rows.slice().reverse().map(([k, inc, obl, res]) => {
    const has = inc || obl, state = has ? status(res) : "NEUTRO", c = state === "POSITIVO" ? C.green : state === "NEGATIVO" ? C.red : C.blue;
    const arrow = state === "POSITIVO" ? "▲ " : state === "NEGATIVO" ? "▼ " : "● ";
    return `<div class="card flat hist" style="${has ? "" : "opacity:.5"}"><span class="m">${label(k)}</span><span class="r" style="color:${has ? c : "var(--dim)"}">${has ? arrow + money(res) : "—"}</span>
      ${has ? `<span class="sub"><span class="green">Ingresos ${money(inc)}</span><span class="red">Obligaciones ${money(obl)}</span></span>` : ""}</div>`;
  }).join("");
  return `<section class="page">${secTitle("Historial", "Evolución de tus ingresos, obligaciones y resultado mensual.", "seccion_historial")}
  <div class="card flat"><div class="row"><h3 class="sp" style="margin:0">Últimos 12 meses</h3><div class="legend"><span><i style="background:${C.green}"></i>Ingresos</span><span><i style="background:${C.red}"></i>Obligaciones</span></div></div>${chartSvg(recent)}</div>
  ${items}</section>`;
}

function viewMas() {
  const items = [["rachas", "racha_al_ras", "Rachas", "Meses seguidos con el mismo resultado"], ["proyeccion", "seccion_proyeccion", "Proyección", "Anticipa el resultado del mes"], ["objetivos", "seccion_objetivos", "Objetivos de ahorro", "Metas y aportes"], ["juego", "seccion_juego", "Mini juego", "Un reto para tu criterio financiero"], ["ajustes", "seccion_ajustes", "Configuración", "Moneda, alertas y más"]];
  return `<section class="page">${secTitle("Más", "Todas las secciones de SpiderFinance.")}
  ${items.map(([to, a, t, s]) => `<button class="card link" data-act="go" data-to="${to}">${img(a)}<div><b>${t}</b><div class="small muted">${s}</div></div>${ico("chev").replace("<svg", '<svg class="chev"')}</button>`).join("")}</section>`;
}

function viewRachas() {
  const [state, count] = streakInfo();
  const pretty = { POSITIVO: "Te sobró dinero", NEGATIVO: "Te faltó dinero", NEUTRO: "Estás al ras", "SIN DATOS": "Sin datos" }[state];
  const art = { POSITIVO: "racha_sobra_dinero", NEGATIVO: "racha_falta_dinero" }[state] || "racha_al_ras";
  const c = state === "NEGATIVO" ? C.red : state === "POSITIVO" ? C.green : C.blue;
  return `<section class="page">${backBtn()}${secTitle("Rachas", "Mantén el mismo resultado durante tres meses consecutivos para activar una racha.")}
  <div class="card flat center" style="--c:${c}"><div class="small muted" style="letter-spacing:.08em">RACHA ACTUAL</div>${img(art, "streak-art")}
    <div class="big">${pretty}</div>
    <div class="steps">${[0, 1, 2].map(i => `<div class="step ${i < Math.min(count, 3) ? "on" : ""}">${i < Math.min(count, 3) ? "✓" : i + 1}</div>`).join("")}</div>
    ${bar(Math.min(count, 3) / 3, c)}
    <div class="small" style="margin-top:8px;color:${c};font-weight:700">${count} mes(es) consecutivos · ${count >= 3 ? "¡Racha activa!" : "faltan " + (3 - count) + " para la racha"}</div></div>
  <div class="kpis">${kpi("Meses seguidos", count, c)}${kpi("Días de racha", streakDays(count))}${kpi("Meta", "3 meses")}</div></section>`;
}

function viewProyeccion() {
  const d = monthData(st.month), ratio = ratioOf(d), has = d.income > 0 || d.obligations > 0, lim = S().alert_threshold / 100;
  const col = ratio >= lim ? C.red : ratio >= lim - .2 ? C.amber : C.green, found = alertsOf(d, ratio);
  const note = !has ? "Aún no hay datos en este periodo. Agrega ingresos y obligaciones para ver la proyección." : found.length ? "⚠ " + found[0] : "Todo en orden: tus obligaciones están por debajo del límite recomendado.";
  const rc = d.result > .005 ? C.green : d.result < -.005 ? C.red : C.blue;
  return `<section class="page">${backBtn()}${secTitle("Proyección", "Estimación con tus ingresos y obligaciones del periodo seleccionado.", "seccion_proyeccion")}
  <div class="kpis">${kpi("Ingresos", money(d.income), C.green)}${kpi("Obligaciones", money(d.obligations), C.red)}${kpi("Resultado", money(d.result), rc)}</div>
  <div class="card flat"><div class="row"><h3 class="sp" style="margin:0">Ingresos comprometidos</h3><b class="big" style="color:${has ? col : "var(--muted)"};font-size:22px">${has ? Math.round(ratio * 100) + "%" : "—"}</b></div>
    <div style="margin:10px 0">${bar(has ? ratio : 0, col)}</div><div class="small">${note}</div>
    <div class="small dim" style="margin-top:8px">La proyección no crea ni modifica registros.</div></div></section>`;
}

function goalForm() {
  const f = st.form;
  if (f.mode === "new") return `<div class="form" style="--c:${C.blue}"><h4>NUEVO OBJETIVO</h4><p>Ponle un nombre y define cuánto quieres ahorrar.</p>
    <input class="field" id="g-name" placeholder="Nombre del objetivo" autocomplete="off"><input class="field" id="g-target" placeholder="Meta en pesos (ej. 2000000)" inputmode="decimal" autocomplete="off">
    <div class="err" id="f-err"></div><div class="row"><button class="btn sec2" data-act="form-cancel">Cancelar</button><button class="btn blue" data-act="goal-save">Crear objetivo</button></div></div>`;
  const g = db.goals.find(x => x.id === f.id); if (!g) return "";
  if (f.mode === "contribute") return `<div class="form" style="--c:${C.blue}"><h4>APORTAR A «${esc(g.name.toUpperCase())}»</h4><p>Faltan ${money(Math.max(g.target - g.saved, 0))} para completar la meta.</p>
    <input class="field" id="g-amount" placeholder="Valor del aporte" inputmode="decimal" autocomplete="off"><div class="err" id="f-err"></div>
    <div class="row"><button class="btn sec2" data-act="form-cancel">Cancelar</button><button class="btn blue" data-act="goal-contribute" data-id="${g.id}">Guardar aporte</button></div></div>`;
  return `<div class="form" style="--c:${C.red}"><h4>ELIMINAR «${esc(g.name.toUpperCase())}»</h4><p>El objetivo dejará de mostrarse. Tus ingresos y obligaciones no cambian.</p>
    <div class="row"><button class="btn sec2" data-act="form-cancel">Cancelar</button><button class="btn danger" data-act="goal-delete" data-id="${g.id}">Sí, eliminar</button></div></div>`;
}

function viewObjetivos() {
  const goals = db.goals.filter(g => g.active !== false).slice().reverse();
  const saved = goals.reduce((t, g) => t + g.saved, 0), target = goals.reduce((t, g) => t + g.target, 0), creating = st.form && st.form.mode === "new";
  return `<section class="page">${backBtn()}${secTitle("Objetivos de ahorro", "Crea metas y registra aportes sin alterar tu resultado mensual.", "seccion_objetivos")}
  <div class="kpis">${kpi("Objetivos", goals.length)}${kpi("Ahorrado", money(saved), C.green)}${kpi("Progreso", (target ? Math.round(saved / target * 100) : 0) + "%", C.blue)}</div>
  <button class="btn block ${creating ? "sec2" : ""}" data-act="goal-new">${creating ? "✕  Cerrar formulario" : "＋  Crear objetivo"}</button>
  ${creating ? goalForm() : ""}
  ${goals.length ? goals.map(g => {
    const r = Math.min(g.saved / g.target, 1), done = r >= 1, c = done ? C.green : r < .5 ? C.blue : r < .8 ? C.amber : C.green, open = st.form && st.form.id === g.id;
    return `<div class="card flat" style="margin-top:10px"><div class="row"><div class="sp"><b style="color:${done ? C.green : "inherit"}">${done ? "✓ " : ""}${esc(g.name)}</b>
      <div class="small muted">${money(g.saved)} de ${money(g.target)}${done ? " · ¡Meta cumplida!" : " · faltan " + money(g.target - g.saved)}</div></div><b style="color:${c};font-size:18px">${Math.round(r * 100)}%</b></div>
      <div style="margin:10px 0">${bar(r, c)}</div>
      ${open ? goalForm() : `<div class="acts"><button class="btn sm" data-act="goal-contrib" data-id="${g.id}">＋ Aportar</button><button class="btn sm sec2" data-act="goal-del" data-id="${g.id}">✕ Eliminar</button></div>`}</div>`;
  }).join("") : `<div class="card empty flat" style="margin-top:10px">Todavía no tienes objetivos de ahorro.<br>Crea el primero con el botón de arriba.</div>`}</section>`;
}

function viewJuego() {
  return `<section class="page">${backBtn()}${secTitle("Mini juego", "Un pequeño reto para poner a prueba tu criterio financiero.", "seccion_juego")}
  <div class="card flat"><h3>Reto rápido</h3><p style="margin:0 0 10px">Si recibes $1.000.000 y tus obligaciones son $750.000, ¿cuánto te queda?</p>
    <input class="field" id="q-ans" placeholder="Tu respuesta en pesos" inputmode="decimal" autocomplete="off"><div class="err" id="q-msg" style="font-weight:700"></div>
    <button class="btn block" data-act="quiz">Comprobar</button></div></section>`;
}

let installEvent = null;
function viewAjustes() {
  const s = S();
  return `<section class="page">${backBtn()}${secTitle("Configuración", "Los cambios se aplican al instante y se guardan solos.", "seccion_ajustes")}
  <div class="card flat"><h3>Alertas</h3><div class="opt"><div><b>Umbral de alerta</b><small>Avisa cuando las obligaciones llegan a este porcentaje de tus ingresos.</small></div><b class="red" id="thr-val">${s.alert_threshold}%</b></div>
    <input type="range" id="thr" min="50" max="100" step="5" value="${s.alert_threshold}" aria-label="Umbral de alerta"></div>
  <div class="card flat"><h3>Formato</h3><div class="opt"><div><b>Símbolo de moneda</b><small>Ejemplo: ${money(1250000)}</small></div>
    <select class="field" id="cur" style="width:110px;margin:0">${CURRENCIES.map(c => `<option ${c === s.currency ? "selected" : ""}>${c}</option>`).join("")}</select></div></div>
  <div class="card flat"><h3>Comportamiento</h3><div class="opt"><div><b>Animaciones</b><small>Anillo que respira y barras que se llenan.</small></div>
    <button class="switch" role="switch" aria-checked="${s.animations}" data-act="anim" aria-label="Animaciones"></button></div></div>
  <div class="card flat install ${installEvent ? "show" : ""}" id="install"><h3>Instalar</h3><div class="opt"><div><b>Agregar a la pantalla de inicio</b><small>Úsala como una app, incluso sin internet.</small></div><button class="btn sm" data-act="install">Instalar</button></div></div>
  <div class="card flat"><h3>Acerca de</h3><div class="small muted">SpiderFinance v${VERSION}. Tus datos se guardan solo en este teléfono, dentro del navegador. Si borras los datos del sitio, se pierden.</div>
    ${st.confirm && st.confirm.type === "reset" ? `<div class="acts"><div class="small muted" style="width:100%">¿Volver los ajustes a sus valores originales? Tus registros no se modifican.</div><button class="btn sm sec2" data-act="confirm-no">Cancelar</button><button class="btn sm danger" data-act="reset-yes">Sí, restablecer</button></div>`
    : `<div class="acts"><button class="btn sm sec2" data-act="reset">Restablecer ajustes</button></div>`}</div></section>`;
}

const VIEWS = { inicio: viewInicio, ingresos: () => viewRecords("income"), obligaciones: () => viewRecords("obligation"), historial: viewHistorial, mas: viewMas, rachas: viewRachas, proyeccion: viewProyeccion, objetivos: viewObjetivos, juego: viewJuego, ajustes: viewAjustes };
const TABS = [["inicio", "Inicio", "home"], ["ingresos", "Ingresos", "income"], ["obligaciones", "Obligaciones", "wallet"], ["historial", "Historial", "clock"], ["mas", "Más", "more"]];

function render() {
  document.body.classList.toggle("noanim", !S().animations);
  $(".top").classList.toggle("nomonth", !WITH_MONTH.has(st.page));
  $("#monthLabel").textContent = label(st.month);
  const group = PAGES[st.page] ? "mas" : st.page;
  $("#tabs").innerHTML = `<div class="tabs-in">${TABS.map(([id, t, i]) => `<button class="tab ${id === group ? "on" : ""}" data-act="go" data-to="${id}" ${id === group ? 'aria-current="page"' : ""}>${ico(i)}<span>${t}</span></button>`).join("")}</div>`;
  const keep = window.scrollY;
  $("#view").innerHTML = VIEWS[st.page]();
  requestAnimationFrame(() => requestAnimationFrame(() => {
    document.querySelectorAll(".bar i[data-w]").forEach(el => { el.style.width = (parseFloat(el.dataset.w) * 100) + "%"; });
    document.querySelectorAll("[data-ring]").forEach(el => { const c = parseFloat(el.dataset.circ); el.style.strokeDashoffset = c * (1 - Math.max(parseFloat(el.dataset.ring), .02)); });
  }));
  if (st.keepScroll) { window.scrollTo(0, keep); st.keepScroll = false; }
  const first = $("#view .field"); if (first && st.form && st.focus) { first.focus({ preventScroll: false }); st.focus = false; }
  applyTypeState();
}
function rerender(keep = true) { st.keepScroll = keep; render(); }

function applyTypeState() {
  const t = $("#f-type"); if (!t) return;
  const rec = ["Recurrente", "Fijo mensual"].includes(t.value);
  ["#f-start", "#f-dur"].forEach(s => { const el = $(s); if (el) el.disabled = !rec; });
}

/* ---------- eventos ---------- */
document.addEventListener("click", e => {
  const b = e.target.closest("[data-act]"); if (!b) return;
  const a = b.dataset.act, kind = b.dataset.kind, id = Number(b.dataset.id);
  switch (a) {
    case "go": setHash(b.dataset.to); break;
    case "month-prev": st.month = prevM(st.month); st.form = null; st.confirm = null; render(); break;
    case "month-next": st.month = nextM(st.month); st.form = null; st.confirm = null; render(); break;
    case "add": st.form = st.form && st.form.mode === "add" && st.form.kind === kind ? null : { mode: "add", kind }; st.confirm = null; st.focus = true; rerender(); break;
    case "edit-rec": {
      const r = activeRecurring(kind, st.month).find(x => x.id === id); if (!r) break;
      st.form = { mode: "edit", kind, id, concept: r.concept, amount: Number.isInteger(r.amount) ? String(r.amount) : String(r.amount) }; st.confirm = null; st.focus = true; rerender(); break; }
    case "form-cancel": st.form = null; rerender(); break;
    case "form-save": saveForm(kind); break;
    case "ask": st.confirm = { kind, id, rec: b.dataset.rec === "1" }; st.form = null; rerender(); break;
    case "confirm-no": st.confirm = null; rerender(); break;
    case "confirm-yes": {
      const c = st.confirm; st.confirm = null;
      if (c.rec) deactivateRecurring(c.kind, c.id, nextM(st.month)); else deleteMonthly(c.kind, c.id);
      rerender(); break; }
    case "goal-new": st.form = st.form && st.form.mode === "new" ? null : { mode: "new" }; st.focus = true; rerender(); break;
    case "goal-contrib": st.form = st.form && st.form.mode === "contribute" && st.form.id === id ? null : { mode: "contribute", id }; st.focus = true; rerender(); break;
    case "goal-del": st.form = { mode: "delete", id }; rerender(); break;
    case "goal-save": {
      const name = $("#g-name").value.trim(), t = parseAmount($("#g-target").value);
      if (!name || !(t > 0)) { $("#f-err").textContent = "Escribe un nombre y una meta mayor que cero."; break; }
      db.goals.push({ id: nid(), name, target: t, saved: 0, active: true }); save(); st.form = null; rerender(); break; }
    case "goal-contribute": {
      const v = parseAmount($("#g-amount").value);
      if (!(v > 0)) { $("#f-err").textContent = "Escribe un valor mayor que cero."; break; }
      const g = db.goals.find(x => x.id === id); if (g) g.saved += v; save(); st.form = null; rerender(); break; }
    case "goal-delete": { const g = db.goals.find(x => x.id === id); if (g) g.active = false; save(); st.form = null; rerender(); break; }
    case "quiz": {
      const ok = parseAmount($("#q-ans").value) === 250000, m = $("#q-msg");
      m.style.color = ok ? C.green : C.red; m.textContent = ok ? "¡Correcto! Te quedan $250.000." : "Inténtalo de nuevo."; break; }
    case "anim": S().animations = !S().animations; save(); rerender(); break;
    case "reset": st.confirm = { type: "reset" }; rerender(); break;
    case "reset-yes": db.settings = { ...DEFAULTS }; save(); st.confirm = null; rerender(); break;
    case "install": if (installEvent) { installEvent.prompt(); installEvent = null; rerender(); } break;
  }
});
document.addEventListener("change", e => {
  if (e.target.id === "f-type") applyTypeState();
  if (e.target.id === "cur") { S().currency = e.target.value; save(); rerender(); }
});
document.addEventListener("input", e => {
  if (e.target.id === "thr") { S().alert_threshold = Number(e.target.value); $("#thr-val").textContent = e.target.value + "%"; save(); }
});
window.addEventListener("hashchange", route);

function saveForm(kind) {
  const f = st.form, name = $("#f-concept").value.trim(), val = parseAmount($("#f-amount").value), err = $("#f-err");
  const bad = "Escribe un concepto y un valor mayor que cero. La duración debe ser un número entero.";
  if (!name || !(val > 0)) { err.textContent = bad; return; }
  if (f.mode === "edit") editRecurring(kind, f.id, name, val, nextM(st.month));
  else if (["Recurrente", "Fijo mensual"].includes($("#f-type").value)) {
    const start = $("#f-start").value === "Mes actual" ? st.month : nextM(st.month), raw = $("#f-dur").value.trim();
    let dur = null; if (raw) { dur = Number(raw); if (!Number.isInteger(dur) || dur <= 0) { err.textContent = bad; return; } }
    addRecurring(kind, name, val, start, dur);
  } else addMonthly(kind, st.month, name, val);
  st.form = null; rerender();
}

/* ---------- instalación y sin conexión ---------- */
window.addEventListener("beforeinstallprompt", e => { e.preventDefault(); installEvent = e; const el = $("#install"); if (el) el.classList.add("show"); });
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
window.__sf = { monthData, history, streakInfo, db: () => db };
route();

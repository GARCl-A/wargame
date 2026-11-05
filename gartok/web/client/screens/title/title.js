// The title: the menu, the last guild's map and charter, the guilds kept and one guild's saves.
"use strict";

let T = null, busy = false, asking = null;   // asking: the delete waiting for its yes ("w:<world>" / "s:<save>")
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"];

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.hidden = true; }, 3600);
}

async function post(verb, body = {}) {
  if (busy) return;
  busy = true;
  try {
    const r = await api(`/api/title/${verb}`, body);
    if (r.quit) { window.close(); document.body.innerHTML = ""; return; }
    if (r.screen && r.screen !== "title") { location.reload(); return; }
    asking = null;
    render(r);
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
  }
}

function shade(rgb, k) { return `rgb(${rgb.map(v => Math.max(0, Math.min(255, Math.round(v * k)))).join(",")})`; }
function banner(el, b) {
  el.style.setProperty("--banner-hi", shade(b.color, 1.25));
  el.style.setProperty("--banner", shade(b.color, 1));
  el.style.setProperty("--banner-lo", shade(b.color, .55));
}
const crest = b => `<div class="crest"><div class="rim"></div><div class="body"></div>${ico(b.emblem || "body/sword-tie")}</div>`;

// ---------------------------------------------------------------- the menu
function menu() {
  let n = 0;
  const hot = {guilds: "load", saves: "load"}[T.mode];
  $("menu").innerHTML = T.menu.map(m => {
    if (!m) return `<div class="gap"></div>`;
    const cls = ["item", m.primary ? "primary" : "", m.quiet ? "quiet" : "", m.enabled ? "" : "off", hot === m.key ? "hot" : ""].join(" ");
    const emblem = m.emblem ? ico(m.emblem) : "";
    return `<div class="${cls}" data-key="${m.key}"><span class="num">${ROMAN[n++]}</span>${emblem}${esc(m.label)}${m.hint ? `<span class="hint">${esc(m.hint)}</span>` : ""}</div>`;
  }).join("");
}

function choose(key) {
  const m = T.menu.find(x => x && x.key === key);
  if (!m || !m.enabled) return;
  if (key === "continue") post("continue");
  else if (key === "new") post("new");
  else if (key === "load") post("page", {page: T.mode === "guilds" ? "home" : "guilds"});
  else if (key === "wiki" || key === "settings" || key === "credits") post(key);
  else if (key === "quit") post("quit");
}

// ---------------------------------------------------------------- home: the map and the charter
function places() {
  const side = MapSheet.labelSides(), M = T.map;
  let html = M.nodes.map(n => {
    const [x, y] = MapSheet.P(n.id);
    return `<div class="node" style="left:${x}px;top:${y}px"><div class="m">${n.icon ? ico(n.icon) : ""}</div>
      <div class="n ${side[n.id]}">${esc(n.name)}</div></div>`;
  }).join("");
  const at = {};
  for (const g of M.groups) (at[g.at] = at[g.at] || []).push(g);
  for (const list of Object.values(at)) list.forEach((g, i) => {
    const [x, y] = MapSheet.P(g.at);
    html += `<div class="flag" style="left:${x + 4 + i * 16}px;top:${y - 8}px"></div>`;
  });
  $("nodes").innerHTML = html;
}

function charter() {
  const C = T.charter, el = $("charter");
  el.className = "paper charter";
  if (!C) {
    el.classList.add("invite");
    el.innerHTML = `<div class="kicker">${tr("title.no_guild")}</div>
      <div class="head"><div><h2>${tr("title.found")}</h2><div class="motto">${tr("title.found_note")}</div></div></div>
      <div class="roster">${T.invite.map(f => `<div class="face"><div class="medal">${face(f.portrait, f.name)}</div><b>${esc(f.name)}</b></div>`).join("")}</div>
      <p>${tr("title.found_end")}</p>`;
    return;
  }
  banner($("title"), C);
  if (!T.map) el.classList.add("alone");
  el.classList.toggle("clickable", !C.broken);
  const where = C.where ? `<div class="where"><b>${tr("title.at", {place: esc(C.where.place)})}</b>${C.where.rest ? ` · ${esc(C.where.rest)}` : ""}</div>` : "";
  el.innerHTML = `<div class="kicker">${tr("title.last_guild")} <em>${tr("title.saved", {when: esc(C.saved)})}</em></div>
    <div class="head">${crest(C)}<div><h2>${esc(C.name)}</h2>${C.vocation ? `<div class="voc">${esc(C.vocation)}</div>` : ""}
      ${C.motto ? `<div class="motto">${esc(C.motto)}</div>` : ""}</div></div>
    <div class="ledger">${C.ledger.map(([v, k]) => `<div><b>${esc(v)}</b><span>${esc(k)}</span></div>`).join("")}</div>
    <div class="roster">${C.faces.map(f => `<div class="face"><div class="medal ${f.hurt ? "hurt" : ""}">${face(f.portrait, f.name)}</div>
      <b>${esc(f.name)}</b><small>${esc(f.what)}</small></div>`).join("")}${C.more ? `<div class="face more"><div class="medal"><div class="initial">+${C.more}</div></div><b>${tr("title.more")}</b></div>` : ""}</div>
    ${where}${C.broken ? `<div class="broken">${esc(C.broken)}</div>` : ""}
    ${C.broken ? "" : `<div class="ribbon"></div><div class="seal" id="seal"><div>${ico("map/fort")}<b>${tr("title.continue")}</b><small>${tr("title.enter")}</small></div></div>`}`;
}

// ---------------------------------------------------------------- the guilds kept, one guild's saves
function guilds() {
  const rows = T.guilds.map(w => {
    const ask = asking === "w:" + w.world;
    return `<div class="row" data-world="${esc(w.world)}" style="--banner:${shade(w.color, 1)};--banner-hi:${shade(w.color, 1.25)};--banner-lo:${shade(w.color, .55)}">
      ${crest(w)}
      <div class="txt"><b>${esc(w.name)}</b><span>${w.vocation ? esc(w.vocation) + " · " : ""}${tr("title.day", {n: w.day})} · ${trn("unit.member", w.members)} · ${trn("unit.win", w.wins)}</span>
        <small>${tr("title.last_played", {when: esc(w.saved)})} · ${trn("unit.save", w.saves)}</small></div>
      <div class="mini">${w.faces.map(f => `<div class="medal">${face(f.portrait, f.name)}</div>`).join("")}</div>
      <div class="acts">${ask
        ? `<span class="ask">${tr("title.ask_world")}</span><div class="pbtn danger" data-do="delete_world">${tr("title.delete")}</div><div class="pbtn" data-do="cancel">${tr("title.keep")}</div>`
        : `<div class="pbtn go" data-do="load">${tr("title.continue")}</div><div class="pbtn" data-do="saves">${tr("title.saves")}</div><div class="pbtn danger" data-do="ask_world">${tr("title.delete")}</div>`}</div></div>`;
  }).join("");
  $("page").innerHTML = `<div class="kicker">${tr("title.kept")}</div><h2>${tr("title.load")}</h2>
    <div class="lead">${tr("title.load_note")}</div>
    <div class="rows">${rows || `<div class="empty">${tr("title.none")}</div>`}</div>
    <div class="pagefoot"><div class="pbtn" data-do="home">${tr("title.back")}</div></div>`;
}

function saves() {
  const S = T.saves;
  const rows = S.rows.map(s => {
    const ask = asking === "s:" + s.id;
    return `<div class="row" data-save="${esc(s.id)}"><div class="tag ${s.kind}">${esc(s.kind_label)}</div>
      <div class="txt"><b>${esc(s.saved)}</b><span>${esc(s.label)}</span>
        <small>${s.day != null ? `${tr("title.day", {n: s.day})} · ` : ""}${trn("unit.member", s.members)} · ${trn("unit.win", s.wins)}</small></div>
      <div class="acts">${ask
        ? `<span class="ask">${tr("title.ask_save")}</span><div class="pbtn danger" data-do="delete_save">${tr("title.delete")}</div><div class="pbtn" data-do="cancel">${tr("title.keep")}</div>`
        : `<div class="pbtn go" data-do="load_save">${tr("title.load_btn")}</div>${s.kind === "current" ? "" : `<div class="pbtn danger" data-do="ask_save">${tr("title.delete")}</div>`}`}</div></div>`;
  }).join("");
  $("page").innerHTML = `<div class="kicker">${tr("title.saves_of")}</div><h2>${esc(S.name)}</h2>
    <div class="lead">${tr("title.saves_note")}</div>
    <div class="rows">${rows}</div>
    <div class="pagefoot"><div class="pbtn" data-do="guilds">${tr("title.back_guilds")}</div></div>`;
}

// ---------------------------------------------------------------- the whole screen
function render(state) {
  T = state;
  $("quote").innerHTML = esc(T.quote).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  $("notice").hidden = !T.notice;
  $("notice").textContent = T.notice || "";
  menu();
  $("home").hidden = T.mode !== "home";
  $("page").hidden = T.mode === "home";
  if (T.mode === "home") {
    $("sheet").hidden = !T.map;
    if (T.map) { MapSheet.set(T.map); places(); }
    charter();
  } else if (T.mode === "guilds") guilds();
  else saves();
}

$("menu").addEventListener("click", e => { const t = e.target.closest("[data-key]"); if (t) choose(t.dataset.key); });
$("charter").addEventListener("click", () => { if (T && T.charter && !T.charter.broken) post("continue"); });
$("page").addEventListener("click", e => {
  const t = e.target.closest("[data-do]");
  if (!t) return;
  const w = t.closest("[data-world]"), s = t.closest("[data-save]");
  const world = w ? w.dataset.world : T.saves && T.saves.world, save = s && s.dataset.save;
  const d = t.dataset.do;
  if (d === "home" || d === "guilds") post("page", {page: d});
  else if (d === "saves") post("page", {page: "saves", world});
  else if (d === "load") post("load", {world});
  else if (d === "load_save") post("load", {world, save});
  else if (d === "ask_world") { asking = "w:" + world; guilds(); }
  else if (d === "ask_save") { asking = "s:" + save; saves(); }
  else if (d === "cancel") { asking = null; T.mode === "guilds" ? guilds() : saves(); }
  else if (d === "delete_world") post("delete_world", {world});
  else if (d === "delete_save") post("delete_save", {world, save});
});

addEventListener("keydown", e => {
  if (!T) return;
  if (e.key === "Enter" && T.mode === "home") choose("continue");
  else if (e.key === "Escape") {
    if (asking) { asking = null; T.mode === "guilds" ? guilds() : saves(); }
    else if (T.mode === "saves") post("page", {page: "guilds"});
    else if (T.mode === "guilds") post("page", {page: "home"});
  }
});

api("/api/title/state").then(render).catch(e => toast(e.message));

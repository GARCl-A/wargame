// A new guild: the vocation, the pool of nine with the commission tokens, the charter.
"use strict";

let D = null, busy = false;
let slip = null;            // the commission slip while open: the archetypes ticked
let renaming = null;        // the founder whose name is being written
const ico = name => `<span class="ico mask" style="--icon:url(/assets/icons/${name}.svg)"></span>`;
const sgn = n => (n >= 0 ? "+" : "") + n;
const ROMAN = ["I", "II", "III"];

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.hidden = true; }, 3600);
}

// a click while a call is out is dropped; the guild's name and FOUND wait their turn instead (`queue`),
// since leaving the name field posts it just as the seal is pressed
let inflight = Promise.resolve();
async function post(verb, body = {}, queue = false) {
  if (busy && !queue) return;
  const run = async () => {
    busy = true;
    try {
      const r = await api(`/api/draft/${verb}`, body);
      if (r.screen && r.screen !== "draft") { location.reload(); return; }
      render(r);
    } catch (e) {
      toast(e.message);
    } finally {
      busy = false;
    }
  };
  inflight = inflight.then(run);
  return inflight;
}

function shade(rgb, k) { return `rgb(${rgb.map(v => Math.max(0, Math.min(255, Math.round(v * k)))).join(",")})`; }
function banner(rgb) {
  const el = $("draft");
  el.style.setProperty("--banner-hi", shade(rgb, 1.15));
  el.style.setProperty("--banner", shade(rgb, 1));
  el.style.setProperty("--banner-lo", shade(rgb, .6));
}
const medal = (src, name, w, side = "") => `<div class="medal" style="width:${w}px;height:${w}px;${side ? `--side:${side}` : ""}">${face(src, name)}</div>`;
const modCls = m => m > 0 ? "up" : m < 0 ? "dn" : "";

// ---------------------------------------------------------------- the founding, on leather
function steps() {
  $("steps").innerHTML = D.steps.map((s, i) => `<div class="step ${s.state}"><span class="n">${s.state === "done" ? "✓" : ROMAN[i]}</span>
    <div><b>${esc(s.label)}</b><small>${esc(s.sub)}</small></div></div>`).join("");
}

function sealHtml(word, sub, icon, off) {
  const s = $("seal");
  s.className = "seal" + (off ? " off" : "");
  s.innerHTML = `<div>${ico(icon)}<b>${esc(word)}</b><small>${esc(sub)}</small></div>`;
}

function side() {
  const V = D.vocation;
  let body = "";
  if (D.step === "vocation") {
    body = V ? `<div class="chosen"><div class="em">${ico(V.icon)}</div><div><b>${esc(V.name)}</b><small>${esc(V.motto)}</small></div></div>
      <div class="clause"><div class="lbl">The guild's perk</div><p>${esc(V.perk)}</p></div>
      <div class="note">The draft brings one of each of <b>${V.races.map(r => esc(r.race)).join(", ")}</b>; three more come from anywhere.</div>
      <div class="note">Chosen once. It cannot be changed later.</div>`
      : `<div class="note idle">The trade your guild is founded on. Its perk belongs to every member, and the draft brings one of each of its races.</div>`;
    sealHtml("Continue", V ? "to the draft" : "pick a vocation", "gui/contract", !V);
  } else if (D.step === "pick") {
    const slots = [0, 1, 2].map(k => {
      const i = D.squad[k];
      if (i === undefined) return `<div class="slot empty">pick a ${["first", "second", "third"][k]} from the pool</div>`;
      const c = D.pool[i];
      return `<div class="slot" data-pick="${i}"><span class="num">${k + 1}</span>${medal(c.portrait, c.name, 60, "var(--enamel-hi)")}
        <div><b>${esc(c.name)}</b><small>${esc(c.race)} · ${esc(c.occ)}</small><div class="mini">${c.attrs.map(a => `<span>${a.k}<i>${a.v}</i></span>`).join("")}</div></div></div>`;
    }).join("");
    const coins = Array.from({length: D.tokens_max}, (_, k) => `<div class="coin ${k < D.tokens ? "" : "spent"}"></div>`).join("");
    body = `<div class="lbl">The squad · ${D.squad.length} of ${D.team}</div>${slots}
      <div class="tokens"><div class="lbl">Commission tokens · ${D.tokens} of ${D.tokens_max}</div><div class="coins">${coins}</div>
      <p>Call for what the pool lacks (a leader, the strong, the wise). Each archetype costs a token; the card you click next is replaced.</p>
      <span class="ghost-btn ${D.tokens && !D.pending.length ? "" : "off"}" id="commission">${D.tokens ? "Commission…" : "No tokens left"}</span></div>`;
    const full = D.squad.length === D.team;
    sealHtml("Continue", full ? "to the charter" : `${D.squad.length} of ${D.team} picked`, "gui/contract", !full);
  } else {
    const C = D.charter;
    body = `<div class="lbl">Who leads the guild</div>
      <div class="note" style="margin-top:6px">The leader haggles for the guild and sponsors its recruits.</div>
      ${C.founders.map((f, i) => `<div class="lead ${f.leader ? "on" : ""}" data-lead="${i}">${f.leader ? `<span class="tag">Leader</span>` : ""}
        ${medal(f.portrait, f.name, 52, f.leader ? "var(--brass)" : "var(--enamel-hi)")}
        <div><div class="nm">${renaming === i
          ? `<input id="rename" maxlength="${C.max_founder}" value="${esc(f.name)}">`
          : `${esc(f.name)}<span class="pen" data-rename="${i}" title="Rename">${ico("gui/pencil")}</span>`}</div>
          <small>${esc(f.race)} · ${esc(f.occ)} · ${esc(f.align)}</small>
          <div class="rec">Can recruit ${f.recruits}<i>${esc(f.recruits_why)}</i></div></div>
        <div class="mods">${f.attrs.map(a => `<div><span>${a.k}</span><b class="${modCls(a.mod)}">${sgn(a.mod)}</b></div>`).join("")}</div></div>`).join("")}`;
    sealHtml("Found", C.can_found ? "the guild" : "pick a leader", "map/city", !C.can_found);
  }
  $("body").innerHTML = body;
  const back = {vocation: "", pick: "Vocation", charter: "The squad"}[D.step];
  $("back").hidden = !back;
  $("back").textContent = back ? "◂ " + back : "";
  if (renaming !== null) {
    const inp = $("rename");
    inp.focus();
    inp.select();
  }
}

// ---------------------------------------------------------------- the right side
function vocations() {
  return `<div id="head"><h2>Choose a Vocation</h2><span>the trade your guild is founded on</span><span class="right">${D.vocations.length} trades</span></div>`
    + D.vocations.map((v, i) => `<div class="paper voc ${v.chosen ? "on" : ""} ${v.open ? "" : "closed"}" data-voc="${v.id}"
      style="left:${530 + (i % 3) * 452}px;top:${170 + Math.floor(i / 3) * 412}px">
      ${v.chosen ? `<div class="chip"><div class="seal"><div>${ico(v.icon)}<b>Chosen</b></div></div></div>` : ""}
      <div class="top"><div class="em">${ico(v.icon)}</div><div><h3>${esc(v.name)}</h3><div class="motto">${esc(v.motto)}</div></div></div>
      <div class="kicker rlabel">Its races</div>
      <div class="races">${v.races.map(r => `<div class="race">${medal(r.portrait, r.race, 58)}<span>${esc(r.race)}</span></div>`).join("")}</div>
      <div class="perk"><div class="k">${v.open ? "Guild perk" : "Not open yet"}</div><p>${esc(v.perk)}</p></div></div>`).join("");
}

function dossier(c, i) {
  const k = D.squad.indexOf(i), w = c.weapon;
  const stamps = c.tags.map(t => `<span class="stamp ${t.commissioned ? "star" : t.style}" title="${esc(t.desc)}">${t.commissioned ? "★ " : ""}${esc(t.label)}</span>`).join("");
  return `<div class="paper dos ${k >= 0 ? "picked" : ""}" data-pick="${i}" style="left:${530 + (i % 3) * 452}px;top:${108 + Math.floor(i / 3) * 314}px">
    ${k >= 0 ? `<div class="ribbon">${k + 1}</div>` : c.commissioned ? `<span class="newmark">commissioned</span>` : ""}
    <div class="top">${medal(c.portrait, c.name, 68)}
      <div class="who"><h4>${esc(c.name)}</h4><div class="ro">${esc(c.race)} · ${esc(c.occ)}</div>
        <div class="al">${esc(c.align)} · ${esc(c.size)} · age ${c.age}</div><div class="stamps">${stamps}</div></div></div>
    <div class="vit"><div><span>HP</span><b>${c.hp}</b></div><div><span>AC</span><b>${c.ac}</b></div><div><span>MD</span><b>${c.md}</b></div><div><span>SPD</span><b>${c.spd}</b></div><div><span>INIT</span><b>${esc(c.init)}</b></div></div>
    <div class="att">${c.attrs.map(a => `<div><span>${a.k}</span><b>${a.v}</b><i class="${modCls(a.mod)}">${sgn(a.mod)}</i></div>`).join("")}</div>
    <div class="wpn"><b>${esc(w.name)}</b><span>${esc(w.hit)} · ${esc(w.dmg)} · ${esc(w.tags)}</span>${w.action ? `<em>${esc(w.action)}</em>` : ""}</div>
    <div class="ab" title="${esc(c.ability.text)}"><b>${esc(c.ability.name)}</b> · ${c.langs.map(esc).join(", ") || "no languages"}</div>
    <div class="xstamp">Replace</div></div>`;
}

function slipHtml() {
  const sel = slip, room = D.tokens;
  return `<div id="veil"></div><div class="paper slip" id="slip">
    <div class="kicker">Commission<em>${room} token${room === 1 ? "" : "s"} left</em></div>
    <h3>Call for what the pool lacks</h3>
    <div class="why">Tick the archetypes you want in one candidate, a token each. Then click the card they replace; a picked card leaves the squad.</div>
    <div class="arcs">${D.archetypes.map(a => {
      const on = sel.includes(a.key), full = !on && sel.length >= room;
      return `<div class="arc ${on ? "on" : full ? "off" : ""}" data-arc="${a.key}"><span class="box">${on ? "✓" : ""}</span>
        <span class="stamp ${on ? "star" : a.style}">${esc(a.label)}</span><p>${esc(a.desc)}</p></div>`;
    }).join("")}</div>
    <div class="slipfoot"><span class="cost">Costs <b>${sel.length}</b> of ${room}</span>
      <div class="coins">${Array.from({length: room}, (_, k) => `<div class="coin ${k < sel.length ? "use" : ""}"></div>`).join("")}</div>
      <span class="sp"></span><span class="ghost-btn ink" data-slip="cancel">Cancel</span><span class="btn ${sel.length ? "" : "off"}" data-slip="call">Call them</span></div></div>`;
}

function pool() {
  const head = D.pending.length
    ? `<div class="targetbar"><b>Pick the one to replace</b><span>for ${D.pending.map(esc).join(" + ")} · ${D.pending.length} token${D.pending.length === 1 ? "" : "s"}</span><span class="ghost-btn" data-cancel>Cancel</span></div>`
    : `<div id="head"><h2>The Pool</h2><span>pick ${D.team} of ${D.pool.length} · a click picks, a second click lets go</span>
       <span class="right">${esc(D.vocation.name)} · one of each of its races</span></div>`;
  return head + `<div id="cards" class="${D.pending.length ? "targeting" : ""}">${D.pool.map(dossier).join("")}</div>` + (slip ? slipHtml() : "");
}

function charter() {
  const C = D.charter, V = D.vocation;
  banner(C.color);
  const emb = C.emblems.find(e => e.on);
  const order = [...C.founders.keys()].sort((a, b) => C.founders[b].leader - C.founders[a].leader);
  return `<div class="paper" id="charter">
    <div class="kicker">Charter of the guild<em>drawn up at Ankareth, on the first day</em></div>
    <div class="bek">Be it known that the undersigned found the guild of</div>
    <div class="gname"><input id="gname" maxlength="${C.max_name}" placeholder="The Guild" value="${esc(C.name)}" spellcheck="false">${ico("item/quill-ink").replace("ico", "ico pen")}</div>
    <div class="trade">in the trade of <b>${esc(V.name)}</b>, under the word <i>“${esc(V.motto)}”</i></div>
    <div class="trade" style="margin-top:6px"><b>Perk</b> &nbsp;${esc(V.perk)} <i>(every member)</i></div>
    <div class="sec"><div class="kicker">Its arms</div>
      <div class="arms"><div class="shield"><div class="rim"></div><div class="body"></div>${ico(emb.icon)}</div>
        <div class="picks"><div class="lbl">Colour</div>
          <div class="swatches">${C.colors.map((k, i) => `<div class="sw ${k.on ? "on" : ""}" data-color="${i}"><div style="background:rgb(${k.rgb.join(",")})"></div><span>${esc(k.name)}</span></div>`).join("")}</div>
          <div class="lbl">Emblem</div>
          <div class="emblems">${C.emblems.map(e => `<div class="emb ${e.on ? "on" : ""}" data-emblem="${e.slug}" title="${esc(e.label)}">${ico(e.icon)}</div>`).join("")}</div>
          <div class="embname">${esc(emb.label)}</div></div></div></div>
    <div class="sec"><div class="kicker">Signed</div>
      <div class="sigs">${order.map(i => { const f = C.founders[i];
        return `<div class="sig ${f.leader ? "first" : ""}">${f.leader ? `<span class="master"></span>` : ""}
          <div class="hand">${esc(f.name)}</div><div class="line"></div><b>${f.leader ? "Master of the guild" : "Founder"}</b><small>${esc(f.race)} · ${esc(f.occ)}</small></div>`; }).join("")}</div></div>
  </div>
  <div id="banner"><div class="cloth"></div><div class="trim"></div><div class="rod"></div>${ico(emb.icon)}<div class="motto" id="bannername">${esc(C.name || "The Guild")}</div></div>
  <div class="bannercap">The banner flies over the squad's tokens on the board and its pennants on the map.</div>`;
}

// ---------------------------------------------------------------- the whole screen
function render(state) {
  D = state;
  if (D.step !== "pick") slip = null;
  if (D.step !== "charter") renaming = null;
  steps();
  side();
  $("right").innerHTML = D.step === "vocation" ? vocations() : D.step === "pick" ? pool() : charter();
}

function advance() {
  if ($("seal").classList.contains("off")) return;
  if (D.step === "charter") post("found", {name: $("gname").value}, true);
  else post("next");
}

function back() {
  if (slip) { slip = null; render(D); }
  else if (renaming !== null) { renaming = null; render(D); }
  else if (D.step === "pick" && D.pending.length) post("cancel");
  else post("back");
}

$("seal").addEventListener("click", advance);
$("back").addEventListener("click", back);

$("body").addEventListener("click", e => {
  const t = e.target;
  if (t.closest("#commission") && D.tokens && !D.pending.length) { slip = []; render(D); return; }
  const pen = t.closest("[data-rename]");
  if (pen) { renaming = +pen.dataset.rename; render(D); return; }
  if (t.closest("input")) return;
  const lead = t.closest("[data-lead]");
  if (lead) { post("leader", {index: +lead.dataset.lead}); return; }
  const slot = t.closest("[data-pick]");
  if (slot && !D.pending.length) post("pick", {index: +slot.dataset.pick});
});

$("body").addEventListener("keydown", e => {
  if (e.target.id !== "rename") return;
  e.stopPropagation();
  if (e.key === "Enter") { const i = renaming; renaming = null; post("rename", {index: i, name: e.target.value}); }
  else if (e.key === "Escape") { renaming = null; render(D); }
});

$("right").addEventListener("click", e => {
  const t = e.target;
  const voc = t.closest("[data-voc]");
  if (voc && !voc.classList.contains("closed")) { post("vocation", {id: voc.dataset.voc}); return; }
  if (t.closest("[data-cancel]")) { post("cancel"); return; }
  const arc = t.closest("[data-arc]");
  if (arc && !arc.classList.contains("off")) {
    const k = arc.dataset.arc;
    slip = slip.includes(k) ? slip.filter(x => x !== k) : [...slip, k];
    render(D);
    return;
  }
  const s = t.closest("[data-slip]");
  if (s) {
    if (s.dataset.slip === "cancel") { slip = null; render(D); }
    else if (slip.length) { const labels = slip; slip = null; post("commission", {labels}); }
    return;
  }
  if (t.closest("#veil")) { slip = null; render(D); return; }
  const card = t.closest("[data-pick]");
  if (card) { post("pick", {index: +card.dataset.pick}); return; }
  const sw = t.closest("[data-color]");
  if (sw) { post("color", {index: +sw.dataset.color}); return; }
  const emb = t.closest("[data-emblem]");
  if (emb) post("emblem", {slug: emb.dataset.emblem});
});

$("right").addEventListener("input", e => {
  if (e.target.id === "gname") $("bannername").textContent = e.target.value.trim() || "The Guild";
});
$("right").addEventListener("change", e => {
  if (e.target.id === "gname") post("name", {name: e.target.value}, true);
});

addEventListener("keydown", e => {
  if (!D) return;
  if (e.key === "Enter") {
    e.preventDefault();
    advance();
  } else if (e.key === "Escape") {
    if (e.target.id === "gname") { e.target.blur(); return; }
    back();
  }
});

api("/api/draft/state").then(render).catch(e => toast(e.message));

// A member's talents: the tracks and the band on leather, one tree on paper as THE MAP (rings round the
// portrait, a camera) or THE BRANCH (an outline and the talent's neighbourhood), the talent in hand on
// the right. A click takes a talent in hand, TAKE spends the pick. The layout reads only `requires`.
"use strict";

let T = null, busy = false, fresh = null;
let cam = null, camKey = null;                 // the map's camera, kept while the same tree is shown
let view = "map";
try { view = localStorage.getItem("talents.view") === "branch" ? "branch" : "map"; } catch (e) { /* no storage */ }

const ico = name => name ? `<span class="ico mask" style="--icon:url(/assets/icons/${name}.svg)"></span>` : "";
const mod = v => { const m = Math.floor((v - 10) / 2); return (m >= 0 ? "+" : "−") + Math.abs(m); };
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
const ATTR = {STR: "Strength", DEX: "Dexterity", CON: "Constitution", INT: "Intelligence", WIS: "Wisdom", CHA: "Charisma"};
const HEADS = {
  combat: "Each level won in a fight gives one pick. A deeper talent needs the one above it, and nothing is closed for good: given the levels, every talent here can be held.",
  work: "Each level of work gives one pick: what a shift pays, how fast it ends, what the body bears on the road.",
  racial: "The race's own gifts. The racial track earns nothing by itself: it climbs with every level in the other three, a hit die each, and every fifth racial level gives a pick.",
  magic: "The caster's tree. Magic XP comes from a foe put down by a spell and from a spell studied to the end; both need a school.",
};
const chk = `<svg class="chk" viewBox="0 0 20 16"><path d="M3 8l5 5 9-11" fill="none" stroke="#fff3dc" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const ring = `<svg class="ring" viewBox="0 0 126 104"><path d="M63 6c34 0 58 18 57 44s-26 48-60 47S5 76 6 50 32 4 70 8" fill="none" stroke="#8e2a1e" stroke-width="2.6" stroke-linecap="round" opacity=".85"/></svg>`;
const stroke = s => s === "taken" ? 'stroke="#2b1d10" stroke-width="3"' :
  s === "open" ? 'stroke="#9a7434" stroke-width="2.5" stroke-dasharray="7 5"' :
  'stroke="rgba(80,52,24,.38)" stroke-width="1.6" stroke-dasharray="2 5"';

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.hidden = true; }, 2600);
}

async function post(verb, body = {}) {
  if (busy) return;
  busy = true;
  try {
    const r = await api(`/api/talents/${verb}`, body);
    if (r.screen && r.screen !== "talents") { location.reload(); return; }
    if (verb === "take") { Sound.play("level_up"); fresh = body.id; }
    render(r);
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
  }
}

const track = () => T.tracks.find(t => t.track === T.track);
const byId = () => Object.fromEntries(T.nodes.map(n => [n.id, n]));
const kids = id => T.nodes.filter(n => n.requires === id);
const depthOf = (n, B) => n.requires && B[n.requires] ? 1 + depthOf(B[n.requires], B) : 0;

// ---------------------------------------------------------------- the top
function heading() {
  const u = T.unit;
  $("title").textContent = `${u.name}'s talents`;
  $("subtitle").innerHTML = `<b>${esc(u.race)} ${esc(u.occupation)}</b> · ${esc(T.guild)} · day ${T.day}`;
  $("topright").innerHTML = T.chain ? `<div class="chain">${T.chain.map(c =>
    `<span class="${c.at === "later" ? "" : c.at}">${esc(c.label)}</span>`).join("<i>›</i>")}</div>` : "";
}

// ---------------------------------------------------------------- left: who, the tracks, the band
function trackCard(t) {
  let note, bar = "";
  if (t.track === "racial") note = t.picks ? "a racial pick to spend" : `next racial pick at racial level ${t.next_racial} · every level anywhere adds a hit die`;
  else if (t.track === "magic" && !T.unit.schools.length) note = "no school yet · a school opens at its sanctuary";
  else if (t.span) {
    note = `${t.into} / ${t.span} XP to level ${t.level + 1}`;
    bar = `<div class="tbar"><i style="width:${100 * t.into / t.span}%"></i></div>`;
  } else note = "the last level";
  return `<div class="track ${t.track === T.track ? "on" : ""}" data-track="${t.track}">
    ${t.picks ? `<div class="pick">${t.picks} pick${t.picks > 1 ? "s" : ""}</div>` : ""}
    <div class="row"><span class="nm">${t.label}</span><span class="lv">LEVEL<b>${t.level}</b></span></div>
    ${bar}<div class="note">${note} · ${t.held} held</div></div>`;
}

function who() {
  const u = T.unit, h = T.hand;
  const hot = new Set(h && h.delta ? h.delta.map(d => d[0]) : []);
  const label = Object.fromEntries(T.tracks.map(t => [t.track, t.label]));
  $("who").innerHTML = `
    <div class="plate"><div class="medal">${face(u.portrait, u.name)}</div>
      <div><b>${esc(u.name)}</b><span>${esc(u.race)} ${esc(u.occupation)}</span><small>racial level ${u.racial_level} · HP ${u.hp}/${u.hp_max}</small></div></div>
    <div class="attrs">${u.attrs.map(a => `<div class="attr ${hot.has(a.k) ? "hot" : ""}"><span>${a.k}</span><b>${a.v}</b><i>${mod(a.v)}</i></div>`).join("")}</div>
    <div class="kicker">The four tracks<em>a level, a pick</em></div>
    ${T.tracks.map(trackCard).join("")}
    <div class="kicker">Can take now<em>${T.can_take.length} open</em></div>
    <div class="canlist">${T.can_take.length ? T.can_take.map(c => `<div class="crow ${c.id === T.hand?.id ? "on" : ""}" data-track="${c.track}" data-id="${c.id}">
      <i></i><span>${esc(c.name)}</span><em>${label[c.track].toLowerCase()} · tier ${ROMAN[c.tier - 1] || c.tier}</em></div>`).join("")
      : `<div class="none">No pick to spend: the next level in a track brings one.</div>`}</div>
    ${T.band.length > 1 ? `<div class="kicker">The band<em>picks waiting</em></div>
    <div class="band ${T.band.length > 6 ? "many" : ""}">${T.band.map(m => `<div class="mate ${m.uid === u.uid ? "on" : m.picks ? "" : "dim"}" data-uid="${m.uid}">
      <div class="medal">${face(m.portrait, m.name)}</div>${m.picks ? `<em>${m.picks}</em>` : ""}<span>${esc(m.name.split(" ")[0])}</span></div>`).join("")}</div>` : ""}
    <div class="foot"><div class="bigbtn ghost small" id="back">${esc(T.back)}</div></div>`;
  $("who").querySelectorAll(".track").forEach(el => el.onclick = () => post("look", {track: el.dataset.track}));
  $("who").querySelectorAll(".crow").forEach(el => el.onclick = () => post("look", {track: el.dataset.track, id: el.dataset.id}));
  $("who").querySelectorAll(".mate").forEach(el => el.onclick = () => post("look", {uid: el.dataset.uid}));
  $("back").onclick = () => post("back");
}

// ---------------------------------------------------------------- centre: the tree
function disc(n, tick) {
  return `<div class="disc">${ico(n.icon)}${n.state === "taken" && tick ? chk : ""}</div>`;
}

function nodeHtml(n, x, y, extra = "") {
  const sel = T.hand && n.id === T.hand.id;
  return `<div class="node ${n.state} ${sel ? "sel" : ""} ${n.id === fresh ? "fresh" : ""} ${extra}" data-id="${n.id}" style="left:${x}px;top:${y}px">
    ${sel ? ring : ""}${disc(n, true)}<div class="nm">${esc(n.name)}</div></div>`;
}

function sheet() {
  const t = track(), u = T.unit;
  const empty = !T.nodes.length;
  const school = t.track === "magic" && !u.schools.length;
  $("sheet").innerHTML = `
    <div class="head"><div><div class="kicker">${esc(u.race)} ${esc(u.occupation)} · ${t.label} level ${t.level}<em>${t.track === "racial" ? `gifts of the ${esc(u.race.toLowerCase())}` : "one tree per track"}</em></div>
        <h1>${t.label}</h1><p>${HEADS[t.track]}</p></div>
      <div class="seals">
        <div><div class="wax ${t.picks ? "" : "black"}"><b>${t.picks}</b></div><small>pick${t.picks === 1 ? "" : "s"} to spend</small></div>
        <div class="held"><b>${t.held}<span> of ${t.total}</span></b><small>held</small></div>
      </div></div>
    <div id="tree">${empty ? "" : `<div class="mode"><span data-mode="map" class="${view === "map" ? "on" : ""}">The map</span><span data-mode="branch" class="${view === "branch" ? "on" : ""}">The branch</span></div>`}</div>`;
  const tree = $("tree");
  if (empty) {
    tree.insertAdjacentHTML("beforeend", `<div class="pencil">— no gifts written for the ${esc(u.race.toLowerCase())} yet —</div>`);
    return;
  }
  tree.querySelectorAll(".mode span").forEach(b => b.onclick = () => {
    view = b.dataset.mode;
    try { localStorage.setItem("talents.view", view); } catch (e) { /* no storage */ }
    sheet();
  });
  if (view === "branch") branch(tree); else map(tree);
  if (school) tree.insertAdjacentHTML("beforeend", `<div class="pencil">— waits for a school —<small>a school opens with initiation at its sanctuary</small></div>`);
  tree.querySelectorAll("[data-id]").forEach(el => el.addEventListener("click", () => {
    if (!cam || !cam.dragged) post("look", {id: el.dataset.id});
  }));
}

// THE MAP: the roots on the first ring round the portrait, each step deeper one ring out
function map(tree) {
  const B = byId(), roots = T.nodes.filter(n => !n.requires || !B[n.requires]);
  const col = {}, depth = {};
  let leaf = 0;
  const place = n => {
    const cs = kids(n.id);
    col[n.id] = cs.length ? cs.map(place).reduce((a, b) => a + b) / cs.length : leaf++;
    return col[n.id];
  };
  roots.forEach((r, i) => { if (i) leaf += 0.6; place(r); });
  const XY = {};
  for (const n of T.nodes) {
    depth[n.id] = depthOf(n, B);
    const a = (col[n.id] + 0.5) / Math.max(leaf, 1) * Math.PI * 2 - Math.PI / 2, r = 190 + depth[n.id] * 150;
    XY[n.id] = [Math.cos(a) * r, Math.sin(a) * r];
  }
  const deepest = Math.max(...Object.values(depth));
  let lines = "", html = "", hub = `<div class="hubface" style="left:0;top:0">${face(T.unit.portrait, T.unit.name)}</div>`;
  for (let d = 0; d <= deepest; d++) hub += `<div class="orbit" style="width:${2 * (190 + d * 150)}px;height:${2 * (190 + d * 150)}px"></div>`;
  for (const n of T.nodes) {
    if (n.requires && B[n.requires]) {
      const [px, py] = XY[n.requires], [qx, qy] = XY[n.id];
      lines += `<path d="M${px} ${py} L${qx} ${qy}" fill="none" ${stroke(n.state)}/>`;
    }
    html += nodeHtml(n, ...XY[n.id]);
  }
  const R = 190 + deepest * 150 + 90;
  tree.insertAdjacentHTML("beforeend", `<div class="view"><div class="world">${hub}
      <svg style="left:${-R}px;top:${-R}px;width:${2 * R}px;height:${2 * R}px" viewBox="${-R} ${-R} ${2 * R} ${2 * R}">${lines}</svg>${html}</div></div>
    <div class="cam"><span class="cb" data-z="out">−</span><span class="cb" data-z="in">+</span><span class="cb" data-z="fit">FIT</span><b class="scale"></b></div>
    <div class="legend"><span><i class="lg taken"></i>held</span><span><i class="lg open"></i>can take</span><span><i class="lg waiting"></i>needs a pick</span><span><i class="lg locked"></i>not yet</span></div>`);
  camera(tree, R);
}

function camera(tree, R) {
  const vw = tree.querySelector(".view"), world = tree.querySelector(".world"), scale = tree.querySelector(".scale");
  const VW = 1004, VH = 664, key = T.unit.uid + "/" + T.track;
  const fitAll = () => { const s = Math.min(VW / (2 * R), VH / (2 * R), 1.1); Object.assign(cam, {s, tx: VW / 2, ty: VH / 2}); };
  if (!cam || camKey !== key) { cam = {s: 1, tx: 0, ty: 0, dragged: false}; camKey = key; fitAll(); }
  const apply = () => {
    world.style.transform = `translate(${cam.tx}px,${cam.ty}px) scale(${cam.s})`;
    world.style.setProperty("--inv", 1 / cam.s);
    world.classList.toggle("far", cam.s < 0.62);
    world.classList.toggle("dots", cam.s < 0.3);
    scale.textContent = Math.round(cam.s * 100) + "%";
    declutter(world);
  };
  const zoom = (k, cx = VW / 2, cy = VH / 2) => {
    const ns = Math.max(0.15, Math.min(1.6, cam.s * k));
    cam.tx = cx - (cx - cam.tx) * ns / cam.s;
    cam.ty = cy - (cy - cam.ty) * ns / cam.s;
    cam.s = ns;
    apply();
  };
  tree.querySelectorAll(".cam .cb").forEach(b => b.onclick = () => {
    if (b.dataset.z === "fit") { fitAll(); apply(); } else zoom(b.dataset.z === "in" ? 1.25 : 1 / 1.25);
  });
  const stage = () => $("stage").getBoundingClientRect().width / 1920;
  vw.addEventListener("wheel", e => {
    e.preventDefault();
    const r = vw.getBoundingClientRect(), k = stage();
    zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15, (e.clientX - r.left) / k, (e.clientY - r.top) / k);
  }, {passive: false});
  let drag = null;
  vw.addEventListener("mousedown", e => { drag = [e.clientX, e.clientY, cam.tx, cam.ty]; cam.dragged = false; });
  onmouseup = () => { drag = null; vw.classList.remove("grabbing"); };
  onmousemove = e => {
    if (!drag) return;
    const k = stage();
    if (Math.abs(e.clientX - drag[0]) + Math.abs(e.clientY - drag[1]) > 4) { cam.dragged = true; vw.classList.add("grabbing"); }
    cam.tx = drag[2] + (e.clientX - drag[0]) / k;
    cam.ty = drag[3] + (e.clientY - drag[1]) / k;
    apply();
  };
  apply();
}

// zoomed out, a name that hits another hides; the talent in hand first, then what can be taken, then what is held
function declutter(world) {
  const labels = [...world.querySelectorAll(".node .nm")];
  labels.forEach(l => l.classList.remove("hide"));
  if (!world.classList.contains("far")) return;
  const rank = el => { const n = el.parentElement; return n.classList.contains("sel") ? 0 : n.classList.contains("open") ? 1 : 2; };
  const shown = [];
  for (const l of labels.filter(l => getComputedStyle(l).display !== "none").sort((a, b) => rank(a) - rank(b))) {
    const r = l.getBoundingClientRect();
    if (shown.some(s => r.left < s.right && r.right > s.left && r.top < s.bottom && r.bottom > s.top)) l.classList.add("hide");
    else shown.push(r);
  }
}

// THE BRANCH: every talent as an outline open along the branch in hand, and round it what it needs and opens
function branch(tree) {
  const B = byId(), sel = T.hand ? B[T.hand.id] : T.nodes[0];
  const below = n => { const all = [n]; kids(n.id).forEach(k => all.push(...below(k))); return all; };
  const line = new Set();
  for (let c = sel; c; c = B[c.requires]) line.add(c.id);
  let rows = "";
  const row = (n, d) => {
    const cs = kids(n.id), sub = below(n), held = sub.filter(m => m.state === "taken").length, op = sub.filter(m => m.state === "open").length;
    const expanded = line.has(n.id);
    rows += `<div class="orow ${n.state} ${n === sel ? "on" : ""}" data-id="${n.id}" style="padding-left:${10 + d * 16}px">
      <i class="tw">${cs.length ? (expanded ? "▾" : "▸") : ""}</i><i class="dot"></i><span>${esc(n.name)}</span>
      ${cs.length && !expanded ? `<em>${held}/${sub.length}${op ? ` · <b>${op} open</b>` : ""}</em>` : ""}</div>`;
    if (expanded) cs.forEach(k => row(k, d + 1));
  };
  T.nodes.filter(n => !n.requires || !B[n.requires]).forEach(r => row(r, 0));

  const anc = [];
  for (let c = B[sel.requires]; c; c = B[c.requires]) anc.unshift(c);
  const sib = sel.requires ? kids(sel.requires).filter(n => n !== sel) : [];
  const down = kids(sel.id), grand = down.flatMap(k => kids(k.id));
  const layers = [...anc.map(n => [n]), [...sib.slice(0, Math.ceil(sib.length / 2)), sel, ...sib.slice(Math.ceil(sib.length / 2))]];
  if (down.length) layers.push(down);
  if (grand.length) layers.push(grand);
  const W = 620, P = Math.min(120, 600 / layers.length), XY = {};
  layers.forEach((L, i) => L.forEach((n, j) => { XY[n.id] = [W / (L.length + 1) * (j + 1), 40 + P * i]; }));
  let lines = "", html = "";
  for (const id in XY) {
    const n = B[id];
    if (n.requires && XY[n.requires]) {
      const [px, py] = XY[n.requires], [qx, qy] = XY[id];
      lines += `<path d="M${px} ${py + 32} C${px} ${(py + qy) / 2} ${qx} ${(py + qy) / 2} ${qx} ${qy - 32}" fill="none" ${stroke(n.state)}/>`;
    }
    html += nodeHtml(n, ...XY[id], sib.includes(n) ? "sib" : "");
  }
  tree.insertAdjacentHTML("beforeend", `<div class="outline"><div class="kicker">All ${T.nodes.length}<em>open along this branch</em></div><div class="orows">${rows}</div></div>
    <div class="hood"><div class="kicker">Around ${esc(sel.name)}<em>needs above · opens below</em></div>
      <div class="hoodbox"><svg>${lines}</svg>${html}</div></div>`);
  tree.querySelector(".orow.on")?.scrollIntoView({block: "nearest"});
}

// ---------------------------------------------------------------- right: the talent in hand
function hand() {
  const h = T.hand, t = track(), u = T.unit;
  if (!h) { $("hand").innerHTML = `<div class="kicker">The talent in hand</div>`; return; }
  const n = byId()[h.id];
  let ledger = "";
  if (h.delta && h.delta.length) {
    ledger = `<div class="k">What it changes</div><div class="led">${h.delta.map(([k, a, b]) => {
      const isA = ATTR[k], mv = isA && mod(a) !== mod(b);
      return `<span>${ATTR[k] || esc(k)}</span><s>${a}</s><b>${b}</b><i class="${isA && !mv ? "flat" : ""}">${isA ? (mv ? `mod ${mod(a)} → ${mod(b)}` : `mod ${mod(b)}`) : ""}</i>`;
    }).join("")}</div>`;
    const a = h.delta.find(d => ATTR[d[0]]);
    if (a && mod(a[1]) === mod(a[2])) ledger += `<div class="gloss">The score rises but the modifier holds at ${mod(a[2])}; it moves at ${a[2] + 1}.</div>`;
  } else if (h.delta) {
    ledger = `<div class="k">What it changes</div><div class="gloss">No number on the sheet moves: it counts in play, each time it applies.</div>`;
  }
  const said = c => c.id === h.id ? "this one" : c.state === "taken" ? "held" : c.state === "open" ? "can take now" : "not yet";
  const steps = h.branch.length > 1 || h.opens.length ? `<div class="k">The branch</div>
    ${h.branch.map(c => `<div class="step ${c.state}" data-id="${c.id}">${disc(c)}<b>${esc(c.name)}</b><em>${said(c)}</em></div>`).join("")}
    ${h.opens.map(c => `<div class="step ${c.state}" data-id="${c.id}">${disc(c)}<b>${esc(c.name)}</b><em>opens after</em></div>`).join("")}` : "";
  let act;
  if (n.state === "open") {
    act = `<p>A pick is kept for good.${t.picks === 1 ? ` It is the last ${t.label.toLowerCase()} pick until the next level.` : ""}</p>
      <div class="bigbtn" id="take">${ico(n.icon)}Take ${esc(n.name)}</div>`;
  } else if (n.state === "locked") {
    const next = h.branch.find(c => c.state === "open");
    act = `<p>${next ? `Take ${esc(next.name)} first; this one follows along the branch.` : ""}</p><div class="bigbtn off">Needs ${esc(h.branch[h.branch.length - 2]?.name || "another")}</div>`;
  } else if (n.state === "taken") {
    act = `<div class="bigbtn off">${esc(u.name)} holds it</div>`;
  } else {
    act = `<div class="bigbtn off">No pick to spend</div>`;
  }
  const others = T.tracks.filter(x => x.picks && x.track !== T.track);
  $("hand").innerHTML = `
    <div class="kicker">The talent in hand<em>click a talent to read it</em></div>
    <div class="slip"><div class="big"><div class="${n.state}">${disc(n, true)}</div>
        <div><h2>${esc(n.name)}</h2><div class="tt">${t.label} · tier ${ROMAN[n.tier - 1] || n.tier}</div></div></div>
      <div class="eff">${esc(n.effect)}</div>
      <div class="status ${n.state}">${esc(h.status)}</div>
      ${ledger}${steps}</div>
    ${others.length ? `<div class="after">Still to spend: <b>${others.map(x => `${x.picks} ${x.label}`).join(", ")}</b>. Pick that track on the left.</div>` : ""}
    <div class="act">${act}</div>`;
  $("hand").querySelectorAll(".step").forEach(el => el.onclick = () => post("look", {id: el.dataset.id}));
  const take = $("take");
  if (take) take.onclick = () => post("take", {track: T.track, id: h.id});
}

function render(r) {
  T = r;
  heading();
  who();
  sheet();
  hand();
  fresh = null;
}

addEventListener("keydown", e => {
  if (e.key === "Escape") post("back");
  else if (e.key === "Enter" && $("take")) $("take").click();
});
api("/api/talents/state").then(render).catch(e => toast(e.message));

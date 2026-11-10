// A member's talents: the tracks and the band on leather, one tree on paper as THE MAP (rings round the
// portrait, a camera) or THE BRANCH (an outline and the talent's neighbourhood), the talent in hand on
// the right. A click takes a talent in hand, TAKE spends the pick. The layout hangs a node under `requires`; a hybrid's `also` is a second line into it.
"use strict";

let T = null, busy = false, fresh = null;
let cam = null, camKey = null;                 // the map's camera, kept while the same tree is shown
let view = "map";
try { view = localStorage.getItem("talents.view") === "branch" ? "branch" : "map"; } catch (e) { /* no storage */ }

const mod = v => { const m = Math.floor((v - 10) / 2); return (m >= 0 ? "+" : "−") + Math.abs(m); };
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
const ATTR = ["STR", "DEX", "CON", "INT", "WIS", "CHA"];
const attrName = k => ATTR.includes(k) ? tr(`talents.attr.${k.toLowerCase()}`) : null;
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
const needsOf = (n, B) => [n.requires, n.also].filter(x => x && B[x]);
const depthOf = (n, B) => { const p = needsOf(n, B); return p.length ? 1 + Math.max(...p.map(x => depthOf(B[x], B))) : 0; };

// ---------------------------------------------------------------- the top
function heading() {
  const u = T.unit;
  $("title").textContent = tr("talents.title", {name: u.name});
  $("subtitle").innerHTML = tr("talents.sub", {race: esc(u.race), guild: esc(T.guild), day: T.day});
  $("topright").innerHTML = T.chain ? `<div class="chain">${T.chain.map(c =>
    `<span class="${c.at === "later" ? "" : c.at}">${esc(c.label)}</span>`).join("<i>›</i>")}</div>` : "";
}

// ---------------------------------------------------------------- left: who, the tracks, the band
function trackCard(t) {
  let note, bar = "";
  if (t.track === "racial") note = t.picks ? tr("talents.racial_pick") : tr("talents.racial_next", {n: t.next_racial});
  else if (t.track === "magic" && !T.unit.schools.length) note = tr("talents.no_school");
  else if (t.span) {
    note = tr("talents.xp", {into: t.into, span: t.span, level: t.level + 1});
    bar = `<div class="tbar"><i style="width:${100 * t.into / t.span}%"></i></div>`;
  } else note = tr("talents.last_level");
  return `<div class="track ${t.track === T.track ? "on" : ""}" data-track="${t.track}">
    ${t.picks ? `<div class="pick">${trn("talents.picks", t.picks)}</div>` : ""}
    <div class="row"><span class="nm">${t.label}</span><span class="lv">${tr("talents.level")}<b>${t.level}</b></span></div>
    ${bar}<div class="note">${tr("talents.note_held", {note, n: t.held})}</div></div>`;
}

function who() {
  const u = T.unit, h = T.hand;
  const hot = new Set(h && h.delta ? h.delta.map(d => d[0]) : []);
  const label = Object.fromEntries(T.tracks.map(t => [t.track, t.label]));
  $("who").innerHTML = `
    <div class="plate"><div class="medal">${face(u.portrait, u.name)}</div>
      <div><b>${esc(u.name)}</b><span>${esc(u.race)}</span><small>${tr("talents.racial_level", {level: u.racial_level, hp: u.hp, max: u.hp_max})}</small></div></div>
    <div class="attrs">${u.attrs.map(a => `<div class="attr ${hot.has(a.k) ? "hot" : ""}"><span>${lab(a.k)}</span><b>${a.v}</b><i>${mod(a.v)}</i></div>`).join("")}</div>
    <div class="kicker">${tr("talents.four")}</div>
    ${T.tracks.map(trackCard).join("")}
    <div class="kicker">${tr("talents.can")}<em>${tr("talents.can_n", {n: T.can_take.length})}</em></div>
    <div class="canlist">${T.can_take.length ? T.can_take.map(c => `<div class="crow ${c.id === T.hand?.id ? "on" : ""}" data-track="${c.track}" data-id="${c.id}">
      <i></i><span>${esc(c.name)}</span><em>${tr("talents.can_row", {track: label[c.track].toLowerCase(), tier: ROMAN[c.tier - 1] || c.tier})}</em></div>`).join("")
      : `<div class="none">${tr("talents.none")}</div>`}</div>
    ${T.band.length > 1 ? `<div class="kicker">${tr("talents.band")}<em>${tr("talents.band_note")}</em></div>
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
    <div class="head"><div><div class="kicker">${tr("talents.kicker", {race: esc(u.race), track: t.label, level: t.level})}<em>${t.track === "racial" ? tr("talents.gifts", {race: esc(u.race.toLowerCase())}) : tr("talents.one_tree")}</em></div>
        <h1>${t.label}</h1><p>${tr(`talents.head.${t.track}`)}</p></div>
      <div class="seals">
        <div><div class="wax ${t.picks ? "" : "black"}"><b>${t.picks}</b></div><small>${tr(t.picks === 1 ? "talents.to_spend.one" : "talents.to_spend.other")}</small></div>
        <div class="held">${tr("talents.held_of", {held: t.held, total: t.total})}<small>${tr("talents.held")}</small></div>
      </div></div>
    <div id="tree">${empty ? "" : `<div class="mode"><span data-mode="map" class="${view === "map" ? "on" : ""}">${tr("talents.map")}</span><span data-mode="branch" class="${view === "branch" ? "on" : ""}">${tr("talents.branch")}</span></div>`}</div>`;
  const tree = $("tree");
  if (empty) {
    tree.insertAdjacentHTML("beforeend", `<div class="pencil">${tr("talents.no_gifts", {race: esc(u.race.toLowerCase())})}</div>`);
    return;
  }
  tree.querySelectorAll(".mode span").forEach(b => b.onclick = () => {
    view = b.dataset.mode;
    try { localStorage.setItem("talents.view", view); } catch (e) { /* no storage */ }
    sheet();
  });
  if (view === "branch") branch(tree); else map(tree);
  if (school) tree.insertAdjacentHTML("beforeend", `<div class="pencil">${tr("talents.waits_school")}</div>`);
  tree.querySelectorAll("[data-id]").forEach(el => el.addEventListener("click", () => {
    if (!cam || !cam.dragged) post("look", {id: el.dataset.id});
  }));
}

// THE MAP: the roots on the first ring round the portrait, each step deeper one ring out; the rings are
// squashed to the box's shape, so the whole tree fills it across and down
function map(tree) {
  const B = byId(), roots = T.nodes.filter(n => !n.requires || !B[n.requires]);
  const col = {}, depth = {};
  let leaf = 0;
  const place = n => {
    const cs = kids(n.id).filter(k => !k.also);
    col[n.id] = cs.length ? cs.map(place).reduce((a, b) => a + b) / cs.length : leaf++;
    return col[n.id];
  };
  roots.forEach((r, i) => { if (i) leaf += 0.6; place(r); });
  const VW = tree.clientWidth, VH = tree.clientHeight, AY = 0.8, AX = AY * VW / VH, XY = {}, ang = {};
  // a hybrid is not laid out under its first parent: it sits between its parents, on the ring after the
  // deepest one, and steps outward while another node is in its place
  const put = (n, a, r) => { ang[n.id] = a; XY[n.id] = [Math.cos(a) * r * AX, Math.sin(a) * r * AY]; };
  for (const n of T.nodes) depth[n.id] = depthOf(n, B);
  for (const n of T.nodes.filter(n => !n.also)) {
    put(n, (col[n.id] + 0.5) / Math.max(leaf, 1) * Math.PI * 2 - Math.PI / 2, 190 + depth[n.id] * 150);
  }
  let reach = Math.max(...Object.values(depth));
  for (const n of T.nodes.filter(n => n.also).sort((a, b) => depth[a.id] - depth[b.id])) {
    const ps = needsOf(n, B).filter(x => ang[x] !== undefined);
    const a = ps.length ? Math.atan2(ps.reduce((t, x) => t + Math.sin(ang[x]), 0), ps.reduce((t, x) => t + Math.cos(ang[x]), 0)) : 0;
    const r0 = 190 + depth[n.id] * 150, rmin = Math.max(...ps.map(x => Math.hypot(XY[x][0] / AX, XY[x][1] / AY))) + 60;
    const free = ([x, y]) => !Object.keys(XY).some(id => id !== n.id && Math.abs(XY[id][0] - x) < 150 && Math.abs(XY[id][1] - y) < 95);
    let best = null;
    for (let r = rmin; r <= r0 + 210; r += 30) {
      for (let da = -0.7; da <= 0.7; da += 0.04) {
        const xy = [Math.cos(a + da) * r * AX, Math.sin(a + da) * r * AY];
        if (!free(xy)) continue;
        const cost = ps.reduce((t, x) => t + Math.hypot(xy[0] - XY[x][0], xy[1] - XY[x][1]), 0);
        if (!best || cost < best.cost) best = {cost, r, a: a + da};
      }
    }
    const r = best ? best.r : r0;
    put(n, best ? best.a : a, r);
    reach = Math.max(reach, (r - 190) / 150);
  }
  const deepest = Math.ceil(reach);
  let lines = "", html = "", hub = `<div class="hubface" style="left:0;top:0">${face(T.unit.portrait, T.unit.name)}</div>`;
  for (let d = 0; d <= deepest; d++) hub += `<div class="orbit" style="width:${2 * (190 + d * 150) * AX}px;height:${2 * (190 + d * 150) * AY}px"></div>`;
  for (const n of T.nodes) {
    if (n.requires && B[n.requires]) {
      const [px, py] = XY[n.requires], [qx, qy] = XY[n.id];
      lines += `<path d="M${px} ${py} L${qx} ${qy}" fill="none" ${stroke(n.state)}/>`;
    }
    if (n.also && XY[n.also]) {
      const [px, py] = XY[n.also], [qx, qy] = XY[n.id];
      lines += `<path d="M${px} ${py} L${qx} ${qy}" fill="none" ${stroke(n.state)}/>`;
    }
    html += nodeHtml(n, ...XY[n.id]);
  }
  const R = 190 + deepest * 150, RX = R * AX + 90, RY = R * AY + 90;
  tree.insertAdjacentHTML("beforeend", `<div class="view"><div class="world">${hub}
      <svg style="left:${-RX}px;top:${-RY}px;width:${2 * RX}px;height:${2 * RY}px" viewBox="${-RX} ${-RY} ${2 * RX} ${2 * RY}">${lines}</svg>${html}</div></div>
    <div class="cam"><span class="cb" data-z="out">−</span><span class="cb" data-z="in">+</span><span class="cb" data-z="fit">${tr("talents.fit")}</span><b class="scale"></b></div>
    <div class="legend"><span><i class="lg taken"></i>${tr("talents.lg_held")}</span><span><i class="lg open"></i>${tr("talents.lg_open")}</span><span><i class="lg waiting"></i>${tr("talents.lg_waiting")}</span><span><i class="lg locked"></i>${tr("talents.lg_locked")}</span></div>`);
  camera(tree, RX, RY);
}

function camera(tree, RX, RY) {
  const vw = tree.querySelector(".view"), world = tree.querySelector(".world"), scale = tree.querySelector(".scale");
  const VW = vw.clientWidth, VH = vw.clientHeight, key = T.unit.uid + "/" + T.track;
  const fitAll = () => { const s = Math.min(VW / (2 * RX), VH / (2 * RY), 1.1); Object.assign(cam, {s, tx: VW / 2, ty: VH / 2}); };
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
  const stage = () => $("screen").getBoundingClientRect().width / 1920;
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
  const climb = c => { if (c && !line.has(c.id)) { line.add(c.id); needsOf(c, B).forEach(x => climb(B[x])); } };
  climb(sel);
  let rows = "";
  // a hybrid hangs under its first parent, and shows again, as a link, under the second
  const hybrids = n => T.nodes.filter(m => m.also === n.id);
  const row = (n, d, via = false) => {
    const cs = kids(n.id), sub = below(n), held = sub.filter(m => m.state === "taken").length, op = sub.filter(m => m.state === "open").length;
    const expanded = line.has(n.id) && !via;
    rows += `<div class="orow ${n.state} ${n === sel ? "on" : ""} ${via ? "via" : ""}" data-id="${n.id}" style="padding-left:${10 + d * 16}px">
      <i class="tw">${cs.length && !via ? (expanded ? "▾" : "▸") : ""}</i><i class="dot"></i><span>${esc(n.name)}</span>${n.also && B[n.also] ? `<small class="plus">${via ? `↳ ${esc(B[n.requires].name)}` : `+ ${esc(B[n.also].name)}`}</small>` : ""}
      ${cs.length && !expanded && !via ? `<em>${held}/${sub.length}${op ? ` · ${tr("talents.n_open", {n: op})}` : ""}</em>` : ""}</div>`;
    if (expanded) { cs.forEach(k => row(k, d + 1)); hybrids(n).forEach(k => row(k, d + 1, true)); }
  };
  T.nodes.filter(n => !n.requires || !B[n.requires]).forEach(r => row(r, 0));

  // the family within a reasonable reach: the line to the root with each one's siblings (uncles), and two
  // generations under the talent and its siblings (nephews)
  const kin = new Set(line);
  for (const id of line) if (B[id].requires) kids(B[id].requires).forEach(k => kin.add(k.id));
  let gen = sel.requires ? kids(sel.requires) : [sel];
  for (let g = 0; g < 2; g++) { gen = gen.flatMap(n => kids(n.id)); gen.forEach(n => kin.add(n.id)); }
  let root = sel;
  while (B[root.requires]) root = B[root.requires];
  const layers = [];
  for (let L = [root]; L.length; L = L.flatMap(n => kids(n.id)).filter(n => kin.has(n.id))) layers.push(L);
  const near = new Set([...line, ...below(sel).map(n => n.id)]);
  // a hybrid's second prerequisite lives in another branch: bring it in beside the first one's layer, and
  // bring in what the talent in hand is the second prerequisite of
  const placed = id => layers.some(L => L.some(n => n.id === id));
  const layerOf = id => layers.findIndex(L => L.some(n => n.id === id));
  const si = layerOf(sel.id);
  for (const m of hybrids(sel).filter(m => !placed(m.id))) {
    if (si + 1 >= layers.length) layers.push([]);
    layers[si + 1].push(m);
    near.add(m.id);
  }
  for (const n of layers.flat().filter(n => n.also)) {
    const i = layerOf(n.id);
    for (const x of needsOf(n, B).filter(x => !placed(x))) {
      layers[Math.max(i - 1, 0)].push(B[x]);
      near.add(x);
    }
  }
  const W = 620, P = Math.min(120, 600 / layers.length), XY = {};
  layers.forEach((L, i) => L.forEach((n, j) => { XY[n.id] = [W / (L.length + 1) * (j + 1), 40 + P * i]; }));
  let lines = "", html = "";
  const link = (from, n) => {
    const [px, py] = XY[from], [qx, qy] = XY[n.id];
    lines += `<path d="M${px} ${py + 32} C${px} ${(py + qy) / 2} ${qx} ${(py + qy) / 2} ${qx} ${qy - 32}" fill="none" ${stroke(n.state)}/>`;
  };
  for (const id in XY) {
    const n = B[id];
    if (n.requires && XY[n.requires]) link(n.requires, n);
    if (n.also && XY[n.also]) link(n.also, n);
    html += nodeHtml(n, ...XY[id], near.has(id) ? "" : "sib");
  }
  tree.insertAdjacentHTML("beforeend", `<div class="outline"><div class="kicker">${tr("talents.all_n", {n: T.nodes.length})}<em>${tr("talents.all_note")}</em></div><div class="orows">${rows}</div></div>
    <div class="hood"><div class="kicker">${tr("talents.around", {name: esc(sel.name)})}<em>${tr("talents.around_note")}</em></div>
      <div class="hoodbox"><svg>${lines}</svg>${html}</div></div>`);
  tree.querySelector(".orow.on")?.scrollIntoView({block: "nearest"});
}

// ---------------------------------------------------------------- right: the talent in hand
function hand() {
  const h = T.hand, t = track(), u = T.unit;
  if (!h) { $("hand").innerHTML = `<div class="kicker">${tr("talents.in_hand")}</div>`; return; }
  const n = byId()[h.id];
  let ledger = "";
  if (h.delta && h.delta.length) {
    ledger = `<div class="k">${tr("talents.changes")}</div><div class="led">${h.delta.map(([k, a, b]) => {
      const isA = attrName(k), mv = isA && mod(a) !== mod(b);
      return `<span>${attrName(k) || esc(k)}</span><s>${a}</s><b>${b}</b><i class="${isA && !mv ? "flat" : ""}">${isA ? (mv ? tr("talents.mod_move", {a: mod(a), b: mod(b)}) : tr("talents.mod_flat", {b: mod(b)})) : ""}</i>`;
    }).join("")}</div>`;
    const a = h.delta.find(d => attrName(d[0]));
    if (a && mod(a[1]) === mod(a[2])) ledger += `<div class="gloss">${tr("talents.gloss_flat", {mod: mod(a[2]), next: a[2] + 1})}</div>`;
  } else if (h.delta) {
    ledger = `<div class="k">${tr("talents.changes")}</div><div class="gloss">${tr("talents.gloss_none")}</div>`;
  }
  const said = c => c.id === h.id ? tr("talents.this_one") : c.state === "taken" ? tr("talents.said_held") : c.state === "open" ? tr("talents.said_open") : tr("talents.said_locked");
  const steps = h.branch.length > 1 || h.opens.length || h.also.length ? `<div class="k">${tr("talents.branch")}</div>
    ${h.branch.map(c => `<div class="step ${c.state}" data-id="${c.id}">${disc(c)}<b>${esc(c.name)}</b><em>${said(c)}</em></div>`).join("")}
    ${h.also.map(c => `<div class="step ${c.state}" data-id="${c.id}">${disc(c)}<b>${esc(c.name)}</b><em>${tr("talents.also_needs")} · ${said(c)}</em></div>`).join("")}
    ${h.opens.map(c => `<div class="step ${c.state}" data-id="${c.id}">${disc(c)}<b>${esc(c.name)}</b><em>${tr("talents.opens_after")}</em></div>`).join("")}` : "";
  let act;
  if (n.state === "open") {
    act = `<p>${tr("talents.kept")}${t.picks === 1 ? ` ${tr("talents.last_pick", {track: t.label.toLowerCase()})}` : ""}</p>
      <div class="bigbtn" id="take">${ico(n.icon)}${tr("talents.take", {name: esc(n.name)})}</div>`;
  } else if (n.state === "locked") {
    const next = h.branch.find(c => c.state === "open");
    const missing = [...h.branch.slice(0, -1), ...h.also].filter(c => c.state !== "taken").map(c => esc(c.name)).join(" + ");
    act = `<p>${next ? tr("talents.take_first", {name: esc(next.name)}) : ""}</p><div class="bigbtn off">${tr("talents.needs", {name: missing || tr("talents.another")})}</div>`;
  } else if (n.state === "taken") {
    act = `<div class="bigbtn off">${tr("talents.holds", {name: esc(u.name)})}</div>`;
  } else {
    act = `<div class="bigbtn off">${tr("talents.no_pick")}</div>`;
  }
  const others = T.tracks.filter(x => x.picks && x.track !== T.track);
  $("hand").innerHTML = `
    <div class="kicker">${tr("talents.in_hand")}<em>${tr("talents.in_hand_note")}</em></div>
    <div class="slip"><div class="big"><div class="${n.state}">${disc(n, true)}</div>
        <div><h2>${esc(n.name)}</h2><div class="tt">${tr("talents.tier", {track: t.label, tier: ROMAN[n.tier - 1] || n.tier})}</div></div></div>
      <div class="eff">${esc(n.effect)}</div>
      <div class="status ${n.state}">${esc(h.status)}</div>
      ${ledger}${steps}</div>
    ${others.length ? `<div class="after">${tr("talents.still", {list: others.map(x => `${x.picks} ${x.label}`).join(", ")})}</div>` : ""}
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

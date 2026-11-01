// The load test: a made-up combat tree of 100 talents (wider, deeper, some with two requirements),
// laid out four ways. ?state=big_down | big_zoom | big_right | big_radial | big_focus
(function () {
  const STATE = new URLSearchParams(location.search).get("state") || "";
  if (!STATE.startsWith("big")) return;
  const D = window.DATA;

  let seed = 7;
  const rnd = () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const pick = a => a[Math.floor(rnd() * a.length)];

  const real = D.tracks.flatMap(t => t.nodes);
  const effects = real.map(n => n.effect);
  const icons = Object.keys(window.ICONS);
  const A = ["Iron", "Quick", "Hollow", "Red", "Grey", "Long", "Bitter", "Silent", "Steady", "Wild", "Old", "Keen",
    "Broken", "Deep", "High", "Low", "Cold", "Burning", "Patient", "Last", "First", "Hard", "Bright", "Black"];
  const N = ["Guard", "Step", "Eye", "Hand", "Oath", "Feint", "Stance", "Edge", "Shout", "Grip", "Line", "Watch",
    "Blood", "Wall", "March", "Strike", "Breath", "Nerve", "Hide", "Count", "Mark", "Reach", "Knot", "Shield"];
  const used = new Set();
  const name = () => { for (;;) { const s = pick(A) + " " + pick(N); if (!used.has(s)) { used.add(s); return s; } } };

  const roots = ["strong", "agile", "tough", "alert", "imposing", "tactical_mind"].map(id => real.find(n => n.id === id));
  const nodes = roots.map(r => ({id: r.id, name: r.name, icon: r.icon, effect: r.effect, depth: 0, reqs: [], kids: 0}));
  for (let i = 0; i < 2; i++) nodes.push({id: "r" + i, name: name(), icon: pick(icons), effect: pick(effects), depth: 0, reqs: [], kids: 0});
  const ancestors = n => { const out = new Set(); const go = m => m.reqs.forEach(r => { if (!out.has(r)) { out.add(r); go(byId[r]); } }); go(n); return out; };
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  while (nodes.length < 100) {
    const rid = pick(nodes.filter(n => !n.reqs.length)).id;
    const cands = nodes.filter(n => n.kids < 3 && n.depth < 7 && root(n) === rid);
    if (!cands.length) continue;
    const w = cands.map(n => (1 + n.depth * 0.7) * (n.kids ? 1 : 1.6));
    let r = rnd() * w.reduce((a, b) => a + b), p = cands[0];
    for (let i = 0; i < cands.length; i++) { r -= w[i]; if (r <= 0) { p = cands[i]; break; } }
    const n = {id: "t" + nodes.length, name: name(), icon: pick(icons), effect: pick(effects), depth: p.depth + 1, reqs: [p.id], kids: 0};
    if (rnd() < 0.12 && p.depth > 0) {
      const anc = ancestors(p);
      const qs = nodes.filter(q => q !== p && q.depth <= p.depth && q.depth > 0 && !anc.has(q.id) && root(q) !== root(p));
      if (qs.length) n.reqs.push(pick(qs).id);
    }
    p.kids++; nodes.push(n); byId[n.id] = n;
  }
  function root(n) { while (n.reqs.length) n = byId[n.reqs[0]]; return n.id; }

  if (new URLSearchParams(location.search).get("real")) {
    // today's 30 real combat talents, as they stand for Ylhel
    const tr = D.tracks[0];
    nodes.length = 0;
    for (const n of tr.nodes) nodes.push({...n, reqs: n.requires ? [n.requires] : [], depth: n.tier - 1, req2: null});
    for (const k in byId) delete byId[k];
    nodes.forEach(n => { byId[n.id] = n; });
    const open = nodes.filter(n => n.state === "open");
    const want = new URLSearchParams(location.search).get("sel");
    window.BIG = {sel: byId[want] ? want : "sharp_analysis", state: STATE, nodes, byId, open};
    return;
  }
  const taken = new Set(["tactical_mind", "agile"]);
  for (let i = 0; i < 12; i++) {
    const c = nodes.filter(n => !taken.has(n.id) && n.reqs.every(r => taken.has(r)) && (n.reqs.length || rnd() < 0.15));
    if (!c.length) continue;
    taken.add(pick(c).id);
  }
  for (const n of nodes) {
    n.state = taken.has(n.id) ? "taken" : n.reqs.every(r => taken.has(r)) ? "open" : "locked";
    n.requires = n.reqs[0] || null; n.req2 = n.reqs[1] || null; n.tier = n.depth + 1; n.delta = [];
  }
  const open = nodes.filter(n => n.state === "open");
  const opens = n => nodes.filter(m => m.reqs.includes(n.id)).length;
  const sel = open.filter(n => n.depth >= 2).sort((a, b) => opens(b) - opens(a) || b.depth - a.depth)[0] || open[0];
  const combat = D.tracks[0];
  D.tracks[0] = {...combat, level: 16, picks: 2, held: taken.size, nodes, into: 21, span: 69};
  const want = new URLSearchParams(location.search).get("sel");
  window.BIG = {sel: byId[want] ? want : sel.id, state: STATE, nodes, byId, open};
})();

window.goBig = (id, state) => { const q = new URLSearchParams(location.search); if (id) q.set("sel", id); if (state) q.set("state", state); location.search = q.toString(); };

window.renderBig = function (ico) {
  const {nodes, byId, open, state} = window.BIG;
  const sel = byId[window.BIG.sel];
  const kids = id => nodes.filter(n => n.requires === id);
  const prim = nodes.filter(n => !n.requires);

  // tidy tree on the first requirement; a second requirement is drawn as an extra line
  const col = {}; let leaf = 0;
  const place = n => { const cs = kids(n.id); col[n.id] = cs.length ? cs.map(place).reduce((a, b) => a + b) / cs.length : leaf++; return col[n.id]; };
  prim.forEach((r, i) => { if (i) leaf += 0.6; place(r); });
  const leaves = leaf;

  const XY = {};
  if (state === "big_right") {
    for (const n of nodes) XY[n.id] = [n.depth * 230, col[n.id] * 96];
  } else if (state === "big_radial") {
    for (const n of nodes) {
      const a = (col[n.id] + 0.5) / leaves * Math.PI * 2 - Math.PI / 2, r = 190 + n.depth * 150;
      XY[n.id] = [Math.cos(a) * r, Math.sin(a) * r];
    }
  } else {
    for (const n of nodes) XY[n.id] = [col[n.id] * 150, n.depth * 150];
  }

  const sheet = document.getElementById("sheet");
  const tree = document.getElementById("tree");
  tree.innerHTML = "";
  tree.style.bottom = "40px";
  sheet.querySelector(".head p").textContent = {
    big_down: "A made-up tree of 100 talents, top to bottom, at FIT: names fold away when the whole tree is in view; zoom in to read them.",
    big_zoom: "The same tree zoomed onto the talent in hand: the scroll wheel zooms round the cursor, a drag pans, FIT shows it all again.",
    big_right: "The same 100, left to right: depth runs along the table's long side, the branches stack down the page.",
    big_radial: "The map of everything: the roots round the character, each step deeper one ring out. Zoom in to read the names; click a talent to take it in hand.",
    big_focus: "The branch: every talent as an outline, and round the one in hand what it needs above and what it opens below.",
  }[state];

  const toggle = state === "big_radial" || state === "big_focus" ? `<div class="mode"><span class="${state === "big_radial" ? "on" : ""}" data-mode="big_radial">The map</span><span class="${state === "big_focus" ? "on" : ""}" data-mode="big_focus">The branch</span></div>` : "";
  const wire = () => {
    tree.querySelectorAll(".mode span").forEach(b => b.onclick = () => window.goBig(null, b.dataset.mode));
    tree.querySelectorAll("[data-id]").forEach(el => el.addEventListener("click", () => { if (!window.BIG.dragged) window.goBig(el.dataset.id); }));
  };
  if (state === "big_focus") { focus(tree, ico, nodes, byId, sel); tree.insertAdjacentHTML("beforeend", toggle); wire(); return; }

  const minX = Math.min(...Object.values(XY).map(p => p[0])) - 90, maxX = Math.max(...Object.values(XY).map(p => p[0])) + 90;
  const minY = Math.min(...Object.values(XY).map(p => p[1])) - 60, maxY = Math.max(...Object.values(XY).map(p => p[1])) + 80;
  const ls = s => s === "taken" ? 'stroke="#2b1d10" stroke-width="3"' :
    s === "open" ? 'stroke="#9a7434" stroke-width="2.5" stroke-dasharray="7 5"' :
    'stroke="rgba(80,52,24,.38)" stroke-width="1.6" stroke-dasharray="2 5"';
  const edge = (p, q, s, second) => {
    const [px, py] = XY[p.id], [qx, qy] = XY[q.id];
    const st = second ? 'stroke="#8e2a1e" stroke-width="2" stroke-dasharray="1 6" stroke-linecap="round" opacity=".8"' : ls(s);
    if (second) return `<path d="M${px} ${py} C${px} ${(py + qy) / 2} ${qx} ${(py + qy) / 2} ${qx} ${qy}" fill="none" ${st}/>`;
    if (state === "big_right") { const m = (px + qx) / 2; return `<path d="M${px + 32} ${py} H${m} V${qy} H${qx - 32}" fill="none" ${st}/>`; }
    if (state === "big_radial") return `<path d="M${px} ${py} L${qx} ${qy}" fill="none" ${st}/>`;
    const m = (py + qy) / 2 + 6; return `<path d="M${px} ${py + 32} V${m} H${qx} V${qy - 32}" fill="none" ${st}/>`;
  };
  let lines = "", html = "";
  for (const n of nodes) {
    if (n.requires) lines += edge(byId[n.requires], n, n.state, false);
    if (n.req2) lines += edge(byId[n.req2], n, n.state, true);
  }
  const ring = `<svg class="ring" viewBox="0 0 126 104"><path d="M63 6c34 0 58 18 57 44s-26 48-60 47S5 76 6 50 32 4 70 8" fill="none" stroke="#8e2a1e" stroke-width="2.6" stroke-linecap="round" opacity=".85"/></svg>`;
  const chk = `<svg class="chk" viewBox="0 0 20 16"><path d="M3 8l5 5 9-11" fill="none" stroke="#fff3dc" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  for (const n of nodes) {
    const [x, y] = XY[n.id];
    html += `<div class="node ${n.state} ${n === sel ? "sel" : ""} ${n.req2 ? "two" : ""}" data-id="${n.id}" style="left:${x}px;top:${y}px">
      ${n === sel ? ring : ""}<div class="disc">${ico(n.icon, 34)}${n.state === "taken" ? chk : ""}</div><div class="nm">${n.name}</div></div>`;
  }
  let hub = "";
  if (state === "big_radial") {
    hub = `<div class="hubface" style="left:0;top:0"><img src="${window.DATA.unit.portrait}"></div>`;
    for (let d = 0; d < 8; d++) hub += `<div class="orbit" style="width:${2 * (190 + d * 150)}px;height:${2 * (190 + d * 150)}px"></div>`;
  }
  const bw = maxX - minX, bh = maxY - minY;
  const svg = `<svg class="wl" style="position:absolute;left:${minX}px;top:${minY}px;width:${bw}px;height:${bh}px;overflow:visible" viewBox="${minX} ${minY} ${bw} ${bh}">${lines}</svg>`;
  tree.innerHTML = `<div class="view"><div class="world">${hub}${svg}${html}</div></div>
    <div class="cam"><span class="ghost">−</span><span class="ghost">+</span><span class="ghost">FIT</span><b class="scale"></b></div>
    <div class="legend"><span><i class="lg taken"></i>held</span><span><i class="lg open"></i>can take</span><span><i class="lg locked"></i>not yet</span><span><i class="lg two"></i>second requirement</span></div>`;

  tree.insertAdjacentHTML("beforeend", toggle); wire();
  const view = tree.querySelector(".view"), world = tree.querySelector(".world"), scaleLbl = tree.querySelector(".scale");
  const VW = 1004, VH = 664;
  let s, tx, ty;
  const apply = () => {
    world.style.transform = `translate(${tx}px,${ty}px) scale(${s})`;
    world.style.setProperty("--inv", 1 / s);
    world.classList.toggle("far", s < 0.62); world.classList.toggle("crowd", nodes.length > 50); world.classList.toggle("dots", s < 0.3);
    scaleLbl.textContent = Math.round(s * 100) + "%";
  };
  const fitAll = () => { s = Math.min(VW / (maxX - minX), VH / (maxY - minY), 1.1); tx = (VW - (maxX + minX) * s) / 2; ty = (VH - (maxY + minY) * s) / 2; apply(); };
  const focusOn = (n, z) => { s = z; tx = VW / 2 - XY[n.id][0] * s; ty = VH / 2 - XY[n.id][1] * s; apply(); };
  if (state === "big_zoom") focusOn(sel, 1); else fitAll();
  const [minus, plus, fitb] = tree.querySelectorAll(".cam .ghost");
  const zoom = (k, cx = VW / 2, cy = VH / 2) => { const ns = Math.max(0.15, Math.min(1.6, s * k)); tx = cx - (cx - tx) * ns / s; ty = cy - (cy - ty) * ns / s; s = ns; apply(); };
  minus.onclick = () => zoom(1 / 1.25); plus.onclick = () => zoom(1.25); fitb.onclick = fitAll;
  const stageScale = () => document.getElementById("stage").getBoundingClientRect().width / 1920;
  view.addEventListener("wheel", e => { e.preventDefault(); const r = view.getBoundingClientRect(), k = stageScale();
    zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15, (e.clientX - r.left) / k, (e.clientY - r.top) / k); }, {passive: false});
  let drag = null;
  view.addEventListener("mousedown", e => { drag = [e.clientX, e.clientY, tx, ty]; window.BIG.dragged = false; });
  addEventListener("mouseup", () => { drag = null; });
  addEventListener("mousemove", e => { if (!drag) return; const k = stageScale(); if (Math.abs(e.clientX - drag[0]) + Math.abs(e.clientY - drag[1]) > 4) window.BIG.dragged = true; tx = drag[2] + (e.clientX - drag[0]) / k; ty = drag[3] + (e.clientY - drag[1]) / k; apply(); });
  window.BIG.focusOn = n => focusOn(n, 1);
};

function focus(tree, ico, nodes, byId, sel) {
  // left: the outline, open only along the talent's own branch; right: its neighbourhood
  const kids = id => nodes.filter(n => n.requires === id);
  const count = n => { const all = [n]; const go = m => kids(m.id).forEach(k => { all.push(k); go(k); }); go(n); return all; };
  const line = new Set(); for (let c = sel; c; c = byId[c.requires]) line.add(c.id);
  let rows = "";
  const row = (n, d) => {
    const cs = kids(n.id), sub = count(n), held = sub.filter(m => m.state === "taken").length, op = sub.filter(m => m.state === "open").length;
    const expanded = line.has(n.id);
    rows += `<div class="orow ${n.state} ${n === sel ? "on" : ""}" data-id="${n.id}" style="padding-left:${10 + d * 16}px">
      <i class="tw">${cs.length ? (expanded ? "▾" : "▸") : ""}</i><i class="dot"></i><span>${n.name}</span>
      ${cs.length && !expanded ? `<em>${held}/${sub.length}${op ? ` · <b>${op} open</b>` : ""}</em>` : ""}</div>`;
    if (expanded) cs.forEach(k => row(k, d + 1));
  };
  nodes.filter(n => !n.requires).forEach(r => row(r, 0));

  const anc = []; const seen = new Set();
  const up = n => n.reqs.forEach(r => { if (!seen.has(r)) { seen.add(r); anc.push(byId[r]); up(byId[r]); } }); up(sel);
  const sib = sel.requires ? kids(sel.requires).filter(n => n !== sel) : [];
  const down = nodes.filter(n => n.reqs.includes(sel.id));
  const grand = nodes.filter(n => down.some(k => n.reqs.includes(k.id)));
  const layers = {};
  const add = (n, d) => { (layers[d] = layers[d] || []).includes(n) || layers[d].push(n); };
  anc.forEach(n => add(n, n.depth)); sib.forEach(n => add(n, sel.depth)); add(sel, sel.depth);
  down.forEach(n => add(n, sel.depth + 1)); grand.forEach(n => add(n, sel.depth + 2));
  const ds = Object.keys(layers).map(Number).sort((a, b) => a - b);
  const W = 620, H = 640, P = Math.min(120, H / ds.length), XY = {};
  ds.forEach((d, i) => {
    const L = layers[d].sort((a, b) => (a === sel ? 0 : 1) - (b === sel ? 0 : 1));
    if (d === sel.depth) { const s2 = L.filter(n => n !== sel); L.length = 0; s2.slice(0, Math.ceil(s2.length / 2)).forEach(n => L.push(n)); L.push(sel); s2.slice(Math.ceil(s2.length / 2)).forEach(n => L.push(n)); }
    L.forEach((n, j) => { XY[n.id] = [W / (L.length + 1) * (j + 1), 40 + P * i]; });
  });
  let lines = "", html = "";
  const inN = new Set(Object.keys(XY));
  for (const n of nodes) {
    if (!inN.has(n.id)) continue;
    n.reqs.forEach((r, k) => {
      if (!inN.has(r)) return;
      const [px, py] = XY[r], [qx, qy] = XY[n.id];
      const st = k ? 'stroke="#8e2a1e" stroke-width="2" stroke-dasharray="1 6" stroke-linecap="round"' :
        n.state === "taken" ? 'stroke="#2b1d10" stroke-width="3"' : n.state === "open" ? 'stroke="#9a7434" stroke-width="2.5" stroke-dasharray="7 5"' : 'stroke="rgba(80,52,24,.38)" stroke-width="1.6" stroke-dasharray="2 5"';
      lines += `<path d="M${px} ${py + 32} C${px} ${(py + qy) / 2} ${qx} ${(py + qy) / 2} ${qx} ${qy - 32}" fill="none" ${st}/>`;
    });
  }
  const ring = `<svg class="ring" viewBox="0 0 126 104"><path d="M63 6c34 0 58 18 57 44s-26 48-60 47S5 76 6 50 32 4 70 8" fill="none" stroke="#8e2a1e" stroke-width="2.6" stroke-linecap="round" opacity=".85"/></svg>`;
  for (const id of inN) {
    const n = byId[id], [x, y] = XY[id];
    const faint = sib.includes(n) ? "sib" : "";
    const chk = `<svg class="chk" viewBox="0 0 20 16"><path d="M3 8l5 5 9-11" fill="none" stroke="#fff3dc" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    html += `<div class="node ${n.state} ${n === sel ? "sel" : ""} ${faint}" data-id="${n.id}" style="left:${x}px;top:${y}px">${n === sel ? ring : ""}<div class="disc">${ico(n.icon, 34)}${n.state === "taken" ? chk : ""}</div><div class="nm">${n.name}</div></div>`;
  }
  tree.innerHTML = `<div class="outline"><div class="kicker">All 100<em>open along this branch</em></div><div class="orows">${rows}</div></div>
    <div class="hood"><div class="kicker">Around ${sel.name}<em>needs above · opens below</em></div>
      <div class="hoodbox"><svg class="lines">${lines}</svg>${html}</div></div>`;
}

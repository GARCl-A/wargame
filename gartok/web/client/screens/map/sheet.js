// The sheet: the known world inked by hand on paper. The paper is painted once; the land, the roads and
// the bands' ways are drawn through the camera (zoom round the cursor, drag to pan, FIT) on every change,
// and the places and pawns are HTML over it (map.js).
"use strict";

const MapSheet = (() => {
  const W = 1060, H = 946;
  const INNER = { l: 80, r: W - 80, t: 115, b: H - 70 };
  const cv = $("map"), g = cv.getContext("2d");
  const cam = { z: 1, x: 0, y: 0 };
  let M = null, base = {}, deco = null, hoverPath = null, fitKey = "";

  // the land each place is drawn in: woods, peaks, furrows, trenches, rubble
  const TERRAIN = {
    wilds: ["woods", 110], nature_grove: ["woods", 50], wilds_territory: ["woods", 70], serpents_nest: ["woods", 50],
    mine: ["peaks", 0], dragon_lair: ["peaks", 0], farm: ["furrows", 0], ox_fields: ["furrows", 0],
    battlefield: ["trenches", 0], ancient_ruins: ["rubble", 0],
  };

  let seed = 1;
  const rnd = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
  const rr = (a, b) => a + (b - a) * rnd();
  const hash = s => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 2147483647, 7) || 1;

  // ---------- the paper, once ----------
  const paper = document.createElement("canvas");
  paper.width = W; paper.height = H;
  let edgePts = null;
  function deckle(c) {
    c.beginPath();
    edgePts.forEach((p, i) => i ? c.lineTo(...p) : c.moveTo(...p));
    c.closePath();
  }
  (function paintPaper() {
    seed = 23;
    const j = () => rr(-3, 3);
    edgePts = [];
    for (let x = 6; x <= W - 6; x += 14) edgePts.push([x, 6 + j()]);
    for (let y = 6; y <= H - 6; y += 14) edgePts.push([W - 6 + j(), y]);
    for (let x = W - 6; x >= 6; x -= 14) edgePts.push([x, H - 6 + j()]);
    for (let y = H - 6; y >= 6; y -= 14) edgePts.push([6 + j(), y]);
    const c = paper.getContext("2d");
    c.save(); deckle(c); c.clip();
    c.fillStyle = "#e6d5b0"; c.fillRect(0, 0, W, H);
    for (let i = 0; i < 30; i++) {
      const x = rr(0, W), y = rr(0, H), r = rr(60, 280), gr = c.createRadialGradient(x, y, 0, x, y, r);
      gr.addColorStop(0, `rgba(${rnd() < .5 ? "150,105,55" : "255,248,225"},${rr(.04, .10)})`);
      gr.addColorStop(1, "rgba(0,0,0,0)");
      c.fillStyle = gr; c.fillRect(x - r, y - r, 2 * r, 2 * r);
    }
    for (let i = 0; i < 5200; i++) { c.fillStyle = `rgba(90,60,30,${rr(.03, .12)})`; c.fillRect(rr(0, W), rr(0, H), rr(.6, 1.6), rr(.6, 1.6)); }
    for (let i = 0; i < 60; i++) {
      c.strokeStyle = `rgba(110,80,45,${rr(.04, .09)})`; c.lineWidth = rr(.5, 1); c.beginPath();
      const x = rr(0, W), y = rr(0, H);
      c.moveTo(x, y); c.bezierCurveTo(x + rr(-60, 60), y + rr(-20, 20), x + rr(-60, 60), y + rr(-20, 20), x + rr(-120, 120), y + rr(-30, 30));
      c.stroke();
    }
    c.restore();
  })();

  // ---------- where things are ----------
  function layout() {
    const xs = M.nodes.map(n => n.x), ys = M.nodes.map(n => n.y);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const s = Math.min((INNER.r - INNER.l) / Math.max(x1 - x0, .01), (INNER.b - INNER.t) / Math.max(y1 - y0, .01));
    const cx = (INNER.l + INNER.r) / 2, cy = (INNER.t + INNER.b) / 2;
    base = {};
    for (const n of M.nodes) base[n.id] = [cx + (n.x - (x0 + x1) / 2) * s, cy + (n.y - (y0 + y1) / 2) * s];
  }
  const toScreen = ([x, y]) => [x * cam.z + cam.x, y * cam.z + cam.y];
  const P = id => toScreen(base[id]);
  const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];

  // the seeded scatter of trees, peaks and the rest, in base coordinates, per known world
  function scatter() {
    const out = { trees: [], peaks: [], furrows: [], trenches: [], rubble: [], territories: [] };
    const far = (x, y, r) => Object.values(base).every(([px, py]) => Math.hypot(x - px, y - py) > r);
    for (const n of M.nodes) {
      const t = TERRAIN[n.id];
      if (!t) continue;
      seed = hash(n.id);
      const [nx, ny] = base[n.id];
      if (t[0] === "woods") {
        for (let i = 0; i < t[1]; i++) {
          const a = rr(0, Math.PI * 2), d = Math.sqrt(rnd()) * (40 + t[1] * 1.1);
          const x = nx + Math.cos(a) * d, y = ny + Math.sin(a) * d * .8;
          if (far(x, y, 34) && x > 30 && x < W - 30 && y > 120 && y < H - 30) out.trees.push([x, y, rr(8, 12)]);
        }
      } else if (t[0] === "peaks") {
        for (const [dx, dy, s] of [[60, 10, 20], [90, 60, 24], [40, 80, 17], [120, -10, 15], [-20, 90, 14], [150, 40, 18]])
          if (far(nx + dx, ny + dy, 30)) out.peaks.push([nx + dx, ny + dy, s]);
      } else if (t[0] === "furrows") out.furrows.push([nx, ny]);
      else if (t[0] === "trenches") out.trenches.push([nx, ny]);
      else if (t[0] === "rubble") for (let i = 0; i < 14; i++) out.rubble.push([nx + rr(-50, 50), ny + rr(18, 40), rr(3, 8), rr(2, 5)]);
    }
    const held = {};
    for (const n of M.nodes) if (n.jurisdiction) (held[n.jurisdiction] = held[n.jurisdiction] || []).push(base[n.id]);
    for (const [name, pts] of Object.entries(held)) out.territories.push(territory(pts, name));
    return out;
  }

  // A jurisdiction on the sheet: a wash round the nodes that share its name, the border stippled like a shore,
  // the name set along the edge
  const K = .55;   // the prototype's sizes, scaled to this canvas
  function territory(pts, name) {
    const cx = pts.reduce((a, p) => a + p[0], 0) / pts.length, cy = pts.reduce((a, p) => a + p[1], 0) / pts.length;
    const STEPS = 240, pad = 128 * K;
    let r = [];
    for (let i = 0; i < STEPS; i++) {
      const th = 2 * Math.PI * i / STEPS, dx = Math.cos(th), dy = Math.sin(th);
      let best = 0;
      for (const p of pts) {
        const ox = p[0] - cx, oy = p[1] - cy, b = ox * dx + oy * dy, d = b * b - (ox * ox + oy * oy - pad * pad);
        if (d >= 0) best = Math.max(best, b + Math.sqrt(d));
      }
      r.push(best);
    }
    for (let k = 0; k < 40; k++) r = r.map((v, i) => (r[(i + STEPS - 1) % STEPS] + 2 * v + r[(i + 1) % STEPS]) / 4);
    const poly = r.map((v, i) => {
      const th = 2 * Math.PI * i / STEPS, q = v * (1 + .03 * (.5 * Math.sin(3 * th + 1) + .3 * Math.sin(7 * th + 2) + .2 * Math.sin(13 * th)));
      return [cx + q * Math.cos(th), cy + q * Math.sin(th)];
    });
    const edge = []; let len = 0;
    poly.forEach((p, i) => {
      const a = poly[(i + STEPS - 1) % STEPS], b = poly[(i + 1) % STEPS], tx = b[0] - a[0], ty = b[1] - a[1], l = Math.hypot(tx, ty) || 1;
      edge.push({ p, t: [tx / l, ty / l], n: [ty / l, -tx / l], s: len });
      len += Math.hypot(b[0] - p[0], b[1] - p[1]);
    });
    if ((edge[0].p[0] - cx) * edge[0].n[0] + (edge[0].p[1] - cy) * edge[0].n[1] < 0) edge.forEach(q => { q.n = [-q.n[0], -q.n[1]]; });
    const save = seed; seed = hash("territory");
    const dots = [[], [], [], []];
    for (let i = 0; i < 2000; i++) {
      const q = edge[Math.floor(rnd() * edge.length)], d = (-Math.pow(rnd(), 2.2) * 46 - 2) * K;
      dots[Math.floor(rnd() * 4)].push([q.p[0] + q.n[0] * d + rr(-1.2, 1.2), q.p[1] + q.n[1] * d + rr(-1.2, 1.2), rr(.7, 1.6)]);
    }
    seed = save;
    const along = s => {
      const w = ((s % len) + len) % len; let i = 0;
      while (i < STEPS - 1 && edge[i + 1].s <= w) i++;
      const a = edge[i], b = edge[(i + 1) % STEPS], u = (w - a.s) / ((i === STEPS - 1 ? len : b.s) - a.s || 1), m = (x, y) => x + (y - x) * u;
      return { p: [m(a.p[0], b.p[0]), m(a.p[1], b.p[1])], t: [m(a.t[0], b.t[0]), m(a.t[1], b.t[1])], n: [m(a.n[0], b.n[0]), m(a.n[1], b.n[1])] };
    };
    const word = name.toUpperCase(), adv = 32 * K, off = 40 * K;
    const marks = Object.values(base).flatMap(([x, y]) => [[x, y], [x, y + 24], [x - 30, y + 24], [x + 30, y + 24]]);
    const set = from => {
      const d = edge.find(q => q.s === from).p[1] < cy ? 1 : -1, letters = []; let s = from - d * adv * (word.length - 1) / 2, prev = null, room = 1e9;
      for (const ch of word) {
        let q, x, y;
        do { s += d * 1.5 * K; q = along(s); x = q.p[0] - q.n[0] * off; y = q.p[1] - q.n[1] * off; } while (prev && Math.hypot(x - prev[0], y - prev[1]) < adv);
        prev = [x, y];
        for (const [mx, my] of marks) room = Math.min(room, Math.hypot(x - mx, y - my));
        letters.push([ch, x, y, Math.atan2(d * q.t[1], d * q.t[0])]);
      }
      return { letters, room };
    };
    // the name goes where the marks and their names leave the most room
    let best = null;
    for (let i = 0; i < edge.length; i += 4) { const c = set(edge[i].s); if (!best || c.room > best.room) best = c; }
    return { poly, dots, letters: best.letters, center: [cx, cy] };
  }

  // ---------- ink ----------
  function inkLine(pts, w, dash, key) {
    g.lineWidth = w; g.setLineDash(dash || []); g.beginPath(); g.moveTo(...pts[0]);
    for (let k = 1; k < pts.length; k++) {
      const [x0, y0] = pts[k - 1], [x1, y1] = pts[k], L = Math.hypot(x1 - x0, y1 - y0) || 1;
      const n = Math.max(3, Math.round(L / 26)), nx = -(y1 - y0) / L, ny = (x1 - x0) / L;
      const bend = (hash(key + k) % 13 - 6) / 120;
      for (let i = 1; i <= n; i++) {
        const t = i / n, s = Math.sin(t * Math.PI) * bend * L;
        g.lineTo(x0 + (x1 - x0) * t + nx * s, y0 + (y1 - y0) * t + ny * s);
      }
    }
    g.stroke(); g.setLineDash([]);
  }
  function forest(trees) {
    const crown = (x, y, s) => {
      g.moveTo(x, y - s); g.quadraticCurveTo(x + s * .75, y - s * .2, x + s * .55, y + s * .25);
      g.lineTo(x - s * .55, y + s * .25); g.quadraticCurveTo(x - s * .75, y - s * .2, x, y - s);
    };
    g.fillStyle = "#d9c49b"; g.strokeStyle = "rgba(36,22,10,.8)"; g.lineWidth = 1.1;
    g.beginPath();
    for (const [x, y, s] of trees) crown(x, y, s);
    g.fill(); g.beginPath();
    for (const [x, y, s] of trees) {
      crown(x, y, s);
      g.moveTo(x, y + s * .25); g.lineTo(x, y + s * .6);
      for (let i = 0; i < 3; i++) { g.moveTo(x + s * (.1 + i * .12), y - s * .5 + i * s * .22); g.lineTo(x + s * (.35 + i * .08), y - s * .3 + i * s * .22); }
    }
    g.stroke();
  }
  function peak(x, y, s) {
    g.fillStyle = "#e2d0a8"; g.strokeStyle = "rgba(36,22,10,.85)"; g.lineWidth = 1.3;
    g.beginPath(); g.moveTo(x - s, y + s * .5); g.lineTo(x - s * .1, y - s * .8); g.lineTo(x + s, y + s * .5); g.closePath(); g.fill(); g.stroke();
    g.lineWidth = .9;
    for (let i = 0; i < 6; i++) { const t = i / 6; g.beginPath(); g.moveTo(x - s * .1 + t * s * .9, y - s * .8 + t * s * 1.3); g.lineTo(x - s * .35 + t * s * .9, y - s * .45 + t * s * 1.3); g.stroke(); }
  }
  function arrow(a, b, color) {
    const ang = Math.atan2(b[1] - a[1], b[0] - a[0]), [mx, my] = lerp(a, b, .5);
    g.save(); g.translate(mx, my); g.rotate(ang); g.fillStyle = color;
    g.beginPath(); g.moveTo(8, 0); g.lineTo(-6, -6); g.lineTo(-2, 0); g.lineTo(-6, 6); g.closePath(); g.fill(); g.restore();
  }
  function text(t, x, y, font, color, align = "left") {
    g.font = font; g.fillStyle = color; g.textAlign = align; g.fillText(t, x, y); g.textAlign = "start";
  }
  const ordinal = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");

  // where a band's pawn stands: its node, or part-way along the leg it walks
  const walk = {};
  function bandPoint(b) {
    if (walk[b.gid]) return walk[b.gid];
    return typeof b.at === "string" ? P(b.at) : lerp(P(b.at[0]), P(b.at[1]), b.at[2]);
  }

  // paired footprints along the leg walked, fainter toward where it began
  function feet(from, at) {
    const ang = Math.atan2(at[1] - from[1], at[0] - from[0]), len = Math.hypot(at[0] - from[0], at[1] - from[1]);
    g.save();
    for (let d = 17, k = 0; d < len - 18; d += 17, k++) {
      const side = k % 2 ? 5 : -5, [x, y] = from;
      g.fillStyle = `rgba(33,66,102,${(.3 + .6 * d / len).toFixed(2)})`;
      g.beginPath();
      g.ellipse(x + Math.cos(ang) * d - Math.sin(ang) * side, y + Math.sin(ang) * d + Math.cos(ang) * side, 6, 3.2, ang, 0, 7);
      g.fill();
    }
    g.restore();
  }

  function drawWay(b, selected) {
    const t = b.trip;
    if (!t) return;
    const ink = "rgba(46,95,142,.95)", at = bandPoint(b), from = P(t.from);
    const ahead = t.stops.map(s => P(s.node));
    g.strokeStyle = ink; inkLine([from, at], 4, null, b.gid + "walked");
    feet(from, at);
    g.strokeStyle = "rgba(46,95,142,.8)"; inkLine([at, ...ahead], 3, [10, 6], b.gid + "ahead");
    [at, ...ahead].forEach((p, k, all) => k && arrow(all[k - 1], p, "#2e5f8e"));
    const next = t.stops[0], [nx, ny] = ahead[0];
    text(next.at, nx - 14, ny - 30, "italic 16px 'IM Fell English'", "#2e5f8e");
    if (selected && t.stops.length > 1) {
      const last = t.stops[t.stops.length - 1], [lx, ly] = ahead[ahead.length - 1];
      text(`at ${last.name} day ${last.day}, ${last.at}`, lx - 30, ly + 6, "italic 16px 'IM Fell English'", "#2e5f8e", "right");
    }
  }

  function compass() {
    const cx = W - 90, cy = 110;
    g.strokeStyle = "#2c1c0e"; g.lineWidth = 1.2;
    g.beginPath(); g.arc(cx, cy, 38, 0, 7); g.stroke(); g.beginPath(); g.arc(cx, cy, 32, 0, 7); g.stroke();
    for (let a = 0; a < 8; a++) {
      const t = a / 8 * Math.PI * 2 - Math.PI / 2, l = a % 2 ? 24 : 50, w = a % 2 ? 5 : 8;
      for (const [s, f] of [[1, a % 4 === 0 ? "#2c1c0e" : "#e6d5b0"], [-1, a % 4 === 0 ? "#e6d5b0" : "#2c1c0e"]]) {
        g.fillStyle = f; g.beginPath(); g.moveTo(cx + Math.cos(t) * l, cy + Math.sin(t) * l);
        g.lineTo(cx + Math.cos(t + s * Math.PI / 2) * w, cy + Math.sin(t + s * Math.PI / 2) * w); g.lineTo(cx, cy); g.closePath(); g.fill(); g.stroke();
      }
    }
    text("N", cx, cy - 56, "18px 'IM Fell English SC'", "#2c1c0e", "center");
  }

  function drawTerritory(t) {
    const z = cam.z, sz = Math.sqrt(z), pts = t.poly.map(toScreen), n = pts.length;
    const outline = () => {
      g.beginPath(); g.moveTo((pts[0][0] + pts[n - 1][0]) / 2, (pts[0][1] + pts[n - 1][1]) / 2);
      for (let i = 0; i < n; i++) { const a = pts[i], b = pts[(i + 1) % n]; g.quadraticCurveTo(a[0], a[1], (a[0] + b[0]) / 2, (a[1] + b[1]) / 2); }
      g.closePath();
    };
    const [cx, cy] = toScreen(t.center), wash = g.createRadialGradient(cx, cy, 0, cx, cy, 520 * K * z);
    wash.addColorStop(0, "rgba(176,128,64,.22)"); wash.addColorStop(1, "rgba(176,128,64,.08)");
    g.save(); outline(); g.clip();
    g.fillStyle = wash; g.fillRect(0, 0, W, H);
    g.lineJoin = "round";
    for (const [w, a] of [[56, .05], [38, .06], [24, .07], [12, .09]]) { g.strokeStyle = `rgba(110,70,30,${a})`; g.lineWidth = w * K * sz; outline(); g.stroke(); }
    g.restore();
    t.dots.forEach((bucket, k) => {
      g.fillStyle = `rgba(48,30,14,${.3 + k * .1})`; g.beginPath();
      for (const [x, y, s] of bucket) { const [px, py] = toScreen([x, y]); g.rect(px, py, s * sz, s * sz); }
      g.fill();
    });
    g.strokeStyle = "rgba(42,26,12,.62)"; g.lineWidth = 1.5; outline(); g.stroke();
    g.font = `700 ${30 * K * z}px Cinzel`; g.fillStyle = "#24160a"; g.textAlign = "center";
    for (const [ch, x, y, a] of t.letters) { const [px, py] = toScreen([x, y]); g.save(); g.translate(px, py); g.rotate(a); g.fillText(ch, 0, 0); g.restore(); }
    g.textAlign = "start";
  }

  function draw() {
    if (!M) return;
    g.clearRect(0, 0, W, H);
    g.drawImage(paper, 0, 0);
    g.save(); deckle(g); g.clip();
    const z = cam.z, sz = Math.sqrt(z);
    for (const t of deco.territories) drawTerritory(t);
    forest(deco.trees.map(([x, y, s]) => [...toScreen([x, y]), s * sz]));
    for (const [x, y, s] of deco.peaks) peak(...toScreen([x, y]), s * sz);
    g.strokeStyle = "rgba(80,55,25,.35)"; g.lineWidth = 1;
    for (const p of deco.furrows) {
      const [fx, fy] = toScreen(p);
      for (let i = 0; i < 10; i++) { const y = fy + (20 + i * 7) * sz; g.beginPath(); g.moveTo(fx - 70 * sz, y); g.lineTo(fx + 40 * sz, y - 10 * sz); g.stroke(); }
    }
    g.strokeStyle = "rgba(60,35,15,.45)"; g.lineWidth = 1.4;
    for (const p of deco.trenches) {
      const [bx, by] = toScreen(p);
      for (const o of [-30, 30]) {
        g.beginPath();
        for (let k = 0; k < 9; k++) { const x = bx + (-60 + k * 14) * sz, y = by + (o + 50 + (k % 2 ? 6 : -6)) * sz; k ? g.lineTo(x, y) : g.moveTo(x, y); }
        g.stroke();
      }
    }
    g.fillStyle = "rgba(60,40,20,.35)";
    for (const [x, y, w, h] of deco.rubble) { const [sx, sy] = toScreen([x, y]); g.fillRect(sx, sy, w * sz, h * sz); }

    g.strokeStyle = "rgba(42,26,12,.72)";
    for (const [a, b] of M.edges) inkLine([P(a), P(b)], 1.6, [7, 5], a + b);
    for (const b of M.groups) drawWay(b, b.gid === MapSheet.selected);
    if (hoverPath && hoverPath.length > 1) { g.strokeStyle = "rgba(122,35,24,.85)"; inkLine(hoverPath.map(P), 2.6, [2, 5], hoverPath.join()); }

    compass();
    g.strokeStyle = "rgba(42,26,12,.55)"; g.lineWidth = 1.4; g.strokeRect(20, 20, W - 40, H - 40);
    g.lineWidth = .8; g.strokeRect(26, 26, W - 52, H - 52);
    g.restore();
    MapSheet.onmove && MapSheet.onmove();
  }

  // which side of its mark each place's name goes (below, up, right, left), kept off the marks and the
  // names already set
  const NAME_W = 7.6;   // px per letter
  function labelSides() {
    const boxes = M.nodes.map(n => { const [x, y] = P(n.id); const r = 20; return [x - r, y - r, x + r, y + r]; });
    const hit = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
    const out = {};
    for (const n of M.nodes) {
      const [x, y] = P(n.id), w = n.name.length * NAME_W;
      const opts = {
        "": [x - w / 2, y + 22, x + w / 2, y + 40], up: [x - w / 2, y - 40, x + w / 2, y - 22],
        r: [x + 24, y - 10, x + 24 + w, y + 8], l: [x - 24 - w, y - 10, x - 24, y + 8]
      };
      const pick = Object.keys(opts).find(k => !boxes.some(b => hit(opts[k], b))) ?? "";
      boxes.push(opts[pick]); out[n.id] = pick;
    }
    return out;
  }

  function fit() { cam.z = 1; cam.x = 0; cam.y = 0; draw(); }
  function zoomAt(px, py, f) {
    const z = Math.max(.7, Math.min(4, cam.z * f));
    cam.x = px - (px - cam.x) * z / cam.z; cam.y = py - (py - cam.y) * z / cam.z; cam.z = z;
    draw();
  }

  const sheet = $("sheet");
  sheet.addEventListener("wheel", e => {
    e.preventDefault();
    const r = sheet.getBoundingClientRect(), k = W / r.width;
    zoomAt((e.clientX - r.left) * k, (e.clientY - r.top) * k, e.deltaY < 0 ? 1.15 : 1 / 1.15);
  }, { passive: false });
  let drag = null;
  sheet.addEventListener("pointerdown", e => {
    if (e.button !== 0 && e.button !== 2) return;
    drag = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y, moved: false };
  });
  addEventListener("pointermove", e => {
    if (!drag) return;
    const k = W / sheet.getBoundingClientRect().width, dx = (e.clientX - drag.x) * k, dy = (e.clientY - drag.y) * k;
    if (!drag.moved && Math.hypot(dx, dy) < 5) return;
    drag.moved = true; sheet.classList.add("grab");
    cam.x = drag.cx + dx; cam.y = drag.cy + dy; draw();
  });
  addEventListener("pointerup", () => { if (drag && drag.moved) MapSheet.dragged = performance.now(); drag = null; sheet.classList.remove("grab"); });
  sheet.addEventListener("contextmenu", e => e.preventDefault());
  $("zin").onclick = () => zoomAt(W / 2, H / 2, 1.3);
  $("zout").onclick = () => zoomAt(W / 2, H / 2, 1 / 1.3);
  $("zfit").onclick = fit;

  return {
    selected: null, onmove: null, dragged: 0, P, bandPoint, walk, lerp, fit, draw, labelSides,
    zoomIn: () => zoomAt(W / 2, H / 2, 1.3), zoomOut: () => zoomAt(W / 2, H / 2, 1 / 1.3),
    set(state) {
      M = state;
      const key = M.nodes.map(n => n.id + n.x + n.y).join();
      if (key !== fitKey) { fitKey = key; layout(); deco = scatter(); }
      draw();
    },
    hover(path) { hoverPath = path; draw(); },
  };
})();

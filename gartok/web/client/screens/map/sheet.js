// The sheet: the known world inked by hand on paper. The paper is painted once; the land, the roads and
// the bands' ways are drawn through the camera (zoom round the cursor, drag to pan, FIT) on every change,
// and the places and pawns are HTML over it (map.js).
"use strict";

const Sheet = (() => {
  const W = 1060, H = 946;
  const INNER = {l: 80, r: W - 80, t: 140, b: H - 90};   // the fit leaves the title and the scale clear
  const cv = $("map"), g = cv.getContext("2d");
  const cam = {z: 1, x: 0, y: 0};
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
    const out = {trees: [], peaks: [], furrows: [], trenches: [], rubble: []};
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
    // the town wall: round the city and the quarters an hour or less from it
    const city = M.nodes.find(n => n.id === "city");
    if (city) {
      const near = M.edges.filter(([a, b, d]) => (a === "city" || b === "city") && d <= 1 && a !== "road" && b !== "road")
        .map(([a, b]) => base[a === "city" ? b : a]).concat([base.city]);
      const xs = near.map(p => p[0]), ys = near.map(p => p[1]);
      out.wall = [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2,
                  (Math.max(...xs) - Math.min(...xs)) / 2 + 50, (Math.max(...ys) - Math.min(...ys)) / 2 + 46];
    }
    return out;
  }

  // ---------- ink ----------
  function inkLine(pts, w, dash) {
    g.lineWidth = w; g.setLineDash(dash || []); g.beginPath(); g.moveTo(...pts[0]);
    for (let k = 1; k < pts.length; k++) {
      const [x0, y0] = pts[k - 1], [x1, y1] = pts[k], L = Math.hypot(x1 - x0, y1 - y0) || 1;
      const n = Math.max(3, Math.round(L / 26)), nx = -(y1 - y0) / L, ny = (x1 - x0) / L;
      const bend = ((Math.round(x0 * 7 + y1 * 13)) % 13 - 6) / 120;
      for (let i = 1; i <= n; i++) {
        const t = i / n, s = Math.sin(t * Math.PI) * bend * L;
        g.lineTo(x0 + (x1 - x0) * t + nx * s, y0 + (y1 - y0) * t + ny * s);
      }
    }
    g.stroke(); g.setLineDash([]);
  }
  function tree(x, y, s) {
    g.fillStyle = "#d9c49b"; g.strokeStyle = "rgba(36,22,10,.8)"; g.lineWidth = 1.1;
    g.beginPath(); g.moveTo(x, y - s); g.quadraticCurveTo(x + s * .75, y - s * .2, x + s * .55, y + s * .25);
    g.lineTo(x - s * .55, y + s * .25); g.quadraticCurveTo(x - s * .75, y - s * .2, x, y - s); g.fill(); g.stroke();
    g.beginPath(); g.moveTo(x, y + s * .25); g.lineTo(x, y + s * .6); g.stroke();
    for (let i = 0; i < 3; i++) { g.beginPath(); g.moveTo(x + s * (.1 + i * .12), y - s * .5 + i * s * .22); g.lineTo(x + s * (.35 + i * .08), y - s * .3 + i * s * .22); g.stroke(); }
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
  function bandPoint(b) {
    return typeof b.at === "string" ? P(b.at) : lerp(P(b.at[0]), P(b.at[1]), b.at[2]);
  }

  function drawWay(b, selected) {
    const t = b.trip;
    if (!t) return;
    const ink = "rgba(46,95,142,.95)", at = bandPoint(b), from = P(t.from);
    const ahead = t.stops.map(s => P(s.node));
    g.strokeStyle = ink; inkLine([from, at], 4);
    g.strokeStyle = "rgba(46,95,142,.8)"; inkLine([at, ...ahead], 3, [10, 6]);
    [at, ...ahead].forEach((p, k, all) => k && arrow(all[k - 1], p, "#2e5f8e"));
    const next = t.stops[0], [nx, ny] = ahead[0];
    text(next.at, nx - 14, ny - 30, "italic 16px 'IM Fell English'", "#2e5f8e");
    if (selected && t.stops.length > 1) {
      const last = t.stops[t.stops.length - 1], [lx, ly] = ahead[ahead.length - 1];
      text(`at ${last.name} day ${last.day}, ${last.at}`, lx - 30, ly + 6, "italic 16px 'IM Fell English'", "#2e5f8e", "right");
    }
  }

  function scaleBar(sel) {
    if (!sel || !M.edges.length) return;
    const per = M.edges.map(([a, b, d]) => Math.hypot(base[a][0] - base[b][0], base[a][1] - base[b][1]) / d).sort((x, y) => x - y);
    const pxHour = per[per.length >> 1] * cam.z / sel.pace;
    const hours = [1, 2, 4, 8, 16].find(h => h * pxHour >= 90) || 16;
    const L = Math.min(hours * pxHour, 420), sx = 46, sy = H - 48;
    for (let k = 0; k < 4; k++) {
      g.fillStyle = k % 2 ? "#e6d5b0" : "#2c1c0e"; g.fillRect(sx + k * L / 4, sy, L / 4, 6);
      g.strokeStyle = "#2c1c0e"; g.lineWidth = 1; g.strokeRect(sx + k * L / 4, sy, L / 4, 6);
    }
    text(`${hours === 1 ? "one hour's" : hours + " hours'"} walk, at the band's pace`, sx, sy - 8, "italic 14px 'IM Fell English'", "#2c1c0e");
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

  function draw() {
    if (!M) return;
    g.clearRect(0, 0, W, H);
    g.drawImage(paper, 0, 0);
    g.save(); deckle(g); g.clip();
    const z = cam.z, sz = Math.sqrt(z);
    if (deco.wall) {
      const [x, y] = toScreen(deco.wall);
      g.strokeStyle = "rgba(42,26,12,.35)"; g.lineWidth = 1.2; g.setLineDash([3, 4]);
      g.beginPath(); g.ellipse(x, y, deco.wall[2] * z, deco.wall[3] * z, -.2, 0, 7); g.stroke(); g.setLineDash([]);
    }
    for (const [x, y, s] of deco.trees) tree(...toScreen([x, y]), s * sz);
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
    for (const [a, b] of M.edges) inkLine([P(a), P(b)], 1.6, [7, 5]);
    for (const b of M.groups) drawWay(b, b.gid === Sheet.selected);
    if (hoverPath && hoverPath.length > 1) { g.strokeStyle = "rgba(122,35,24,.85)"; inkLine(hoverPath.map(P), 2.6, [2, 5]); }

    g.save(); g.translate(40, H - 120); g.rotate(-.04);
    text("here the map is not yet drawn", 0, 0, "italic 18px 'IM Fell English'", "rgba(70,45,22,.5)"); g.restore();
    compass();
    const city = M.nodes.find(n => n.id === "city");
    text(`THE ENVIRONS OF ${(city ? city.name : "the guild").toUpperCase()}`, 46, 64, "700 25px Cinzel", "#2c1c0e");
    text(`as walked by ${M.meta.name}, to the ${ordinal(M.meta.day)} day`, 48, 88, "italic 17px 'IM Fell English'", "#5b4630");
    g.strokeStyle = "rgba(42,26,12,.6)"; g.lineWidth = 1; g.beginPath(); g.moveTo(46, 100); g.lineTo(420, 100); g.stroke();
    scaleBar(M.groups.find(b => b.gid === Sheet.selected));
    g.strokeStyle = "rgba(42,26,12,.55)"; g.lineWidth = 1.4; g.strokeRect(20, 20, W - 40, H - 40);
    g.lineWidth = .8; g.strokeRect(26, 26, W - 52, H - 52);
    g.restore();
    Sheet.onmove && Sheet.onmove();
  }

  // which side of its mark each place's name goes (below, up, right, left), kept off the marks and the
  // names already set
  const NAME_W = 7.6;   // px per letter
  function labelSides() {
    const boxes = M.nodes.map(n => { const [x, y] = P(n.id); const r = n.id === "city" ? 30 : 20; return [x - r, y - r, x + r, y + r]; });
    const hit = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
    const out = {};
    for (const n of M.nodes) {
      const [x, y] = P(n.id), w = n.name.length * (n.id === "city" ? 10 : NAME_W), big = n.id === "city" ? 12 : 0;
      const opts = {"": [x - w / 2, y + 22 + big, x + w / 2, y + 40 + big], up: [x - w / 2, y - 40 - big, x + w / 2, y - 22 - big],
                    r: [x + 24, y - 10, x + 24 + w, y + 8], l: [x - 24 - w, y - 10, x - 24, y + 8]};
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
  }, {passive: false});
  let drag = null;
  sheet.addEventListener("pointerdown", e => {
    if (e.button !== 0 && e.button !== 2) return;
    drag = {x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y, moved: false};
  });
  addEventListener("pointermove", e => {
    if (!drag) return;
    const k = W / sheet.getBoundingClientRect().width, dx = (e.clientX - drag.x) * k, dy = (e.clientY - drag.y) * k;
    if (!drag.moved && Math.hypot(dx, dy) < 5) return;
    drag.moved = true; sheet.classList.add("grab");
    cam.x = drag.cx + dx; cam.y = drag.cy + dy; draw();
  });
  addEventListener("pointerup", () => { if (drag && drag.moved) Sheet.dragged = performance.now(); drag = null; sheet.classList.remove("grab"); });
  sheet.addEventListener("contextmenu", e => e.preventDefault());
  $("zin").onclick = () => zoomAt(W / 2, H / 2, 1.3);
  $("zout").onclick = () => zoomAt(W / 2, H / 2, 1 / 1.3);
  $("zfit").onclick = fit;

  return {
    selected: null, onmove: null, dragged: 0, P, bandPoint, fit, draw, labelSides,
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

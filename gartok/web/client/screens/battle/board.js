// The board painted as an inked map: paper, hatched rock, the floor of the place, and over it
// the fog (blank paper where the side has never looked) and the light, smoothed from the
// per-cell levels the server sends.
//
// The map is painted once per state into a "world" canvas at a fixed cell size; the camera
// (zoom and pan) only crops and scales that picture onto the sheet, so moving it never repaints.
"use strict";

const Board = (() => {
  const W = 1384, H = 780, MARGIN = 30;
  const PADC = 4;                    // cells of world round the board: the rock rings of a delve
  const MAX_PX = 4e6;                // the world canvas's pixel budget, which caps its cell size
  const ZOOM_CELL = 112;             // the largest a cell gets on screen
  const INDOOR = new Set(["stone", "cave"]);
  const L = {cell: 48, ox: 0, oy: 0, cols: 0, rows: 0};      // the world
  const V = {s: 1, x: 0, y: 0, cell: 48, fit: 1, max: 1};    // the camera: screen = V.x + world * V.s
  let WW = W, WH = H;
  const base = document.getElementById("board").getContext("2d");
  const over = document.getElementById("overlay").getContext("2d");
  for (const c of [base.canvas, over.canvas]) { c.width = W; c.height = H; }
  const stones = new Image();
  stones.src = "/client/img/flagstones.jpg";
  const ready = new Promise(r => { stones.onload = r; stones.onerror = r; });

  let staticKey = null, staticCanvas = null, paperCanvas = null, worldPaper = null, worldCanvas = null;

  const K = (x, y) => x + "," + y;
  function hash(x, y, s = 0) {
    let h = (x * 374761393 + y * 668265263 + s * 2147483647) | 0;
    h = (h ^ (h >>> 13)) * 1274126177 | 0;
    return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
  }
  function rng(seed) {
    let s = (seed % 2147483646) + 1;
    return () => (s = (s * 16807) % 2147483647) / 2147483647;
  }
  const canvas = (w = WW, h = WH) => { const c = document.createElement("canvas"); c.width = w; c.height = h; return [c, c.getContext("2d")]; };
  const wx = x => L.ox + x * L.cell, wy = y => L.oy + y * L.cell;
  const cx = x => V.x + wx(x) * V.s, cy = y => V.y + wy(y) * V.s;

  function layout(cols, rows) {
    if (cols === L.cols && rows === L.rows) return false;
    L.cols = cols; L.rows = rows;
    const fit = Math.max(14, Math.min(72, Math.floor(Math.min((W - 2 * MARGIN) / cols, (H - 2 * MARGIN) / rows))));
    const budget = Math.floor(Math.sqrt(MAX_PX / ((cols + 2 * PADC) * (rows + 2 * PADC))));
    L.cell = Math.max(fit, Math.min(72, budget));
    L.ox = L.oy = PADC * L.cell;
    WW = (cols + 2 * PADC) * L.cell; WH = (rows + 2 * PADC) * L.cell;
    V.fit = fit / L.cell; V.max = Math.max(V.fit, ZOOM_CELL / L.cell);
    V.s = V.fit;
    clamp();
    return true;
  }

  // a board smaller than the sheet sits in its middle; a bigger one never leaves a gap at an edge
  function clamp() {
    V.cell = L.cell * V.s;
    const gw = L.cols * V.cell, gh = L.rows * V.cell;
    V.x = gw <= W - 2 * MARGIN ? (W - gw) / 2 - L.ox * V.s : Math.min(MARGIN - L.ox * V.s, Math.max(W - MARGIN - gw - L.ox * V.s, V.x));
    V.y = gh <= H - 2 * MARGIN ? (H - gh) / 2 - L.oy * V.s : Math.min(MARGIN - L.oy * V.s, Math.max(H - MARGIN - gh - L.oy * V.s, V.y));
  }

  function deckle(ctx, r) {
    ctx.beginPath();
    const pts = [];
    for (let x = 6; x <= W - 6; x += 14) pts.push([x, 6 + (r() - .5) * 6]);
    for (let y = 6; y <= H - 6; y += 14) pts.push([W - 6 + (r() - .5) * 6, y]);
    for (let x = W - 6; x >= 6; x -= 14) pts.push([x, H - 6 + (r() - .5) * 6]);
    for (let y = H - 6; y >= 6; y -= 14) pts.push([6 + (r() - .5) * 6, y]);
    pts.forEach((p, i) => i ? ctx.lineTo(...p) : ctx.moveTo(...p));
    ctx.closePath();
  }

  function paper(ctx, w, h, tone, seed) {
    const r = rng(seed);
    ctx.fillStyle = tone; ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 26; i++) {
      const x = r() * w, y = r() * h, rad = 60 + r() * 200;
      const g = ctx.createRadialGradient(x, y, 0, x, y, rad);
      g.addColorStop(0, r() < .5 ? `rgba(150,105,55,${.04 + r() * .06})` : `rgba(255,248,225,${.04 + r() * .06})`);
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g; ctx.fillRect(x - rad, y - rad, 2 * rad, 2 * rad);
    }
    for (let i = 0; i < w * h / 200; i++) {
      ctx.fillStyle = `rgba(90,60,30,${.03 + r() * .09})`;
      ctx.fillRect(r() * w, r() * h, .6 + r(), .6 + r());
    }
  }

  function hatch(ctx, x0, y0, w, h, alpha, clusters, r, size = 1) {
    for (let c = 0; c < clusters; c++) {
      const px = x0 + r() * w, py = y0 + r() * h, a = r() * Math.PI;
      const len = (10 + r() * 9) * size, k = 3 + Math.floor(r() * 4), gap = (2.6 + r() * .8) * size;
      const dx = Math.cos(a), dy = Math.sin(a), nx = -dy, ny = dx;
      ctx.strokeStyle = `rgba(36,22,10,${alpha * (.7 + r() * .3)})`;
      ctx.lineWidth = .9 + r() * .45; ctx.lineCap = "round";
      for (let i = 0; i < k; i++) {
        const o = (i - k / 2) * gap, l = len * (.7 + r() * .3);
        ctx.beginPath();
        ctx.moveTo(px + nx * o - dx * l / 2, py + ny * o - dy * l / 2);
        ctx.lineTo(px + nx * o + dx * l / 2, py + ny * o + dy * l / 2);
        ctx.stroke();
      }
    }
  }

  function inkLine(ctx, x0, y0, x1, y1, w, r) {
    ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(x0, y0);
    for (let i = 1; i <= 3; i++) { const t = i / 3; ctx.lineTo(x0 + (x1 - x0) * t + (r() - .5) * 1.6, y0 + (y1 - y0) * t + (r() - .5) * 1.6); }
    ctx.stroke();
  }

  function floorLayer(b) {
    const [c, f] = canvas();
    const gw = b.cols * L.cell, gh = b.rows * L.cell, r = rng(b.cols * 31 + b.rows);
    f.save(); f.beginPath(); f.rect(L.ox, L.oy, gw, gh); f.clip();
    if (b.floor === "stone" || b.floor === "cave" || b.floor === "cobble") {
      const ts = (b.floor === "cobble" ? 4 : 7) * L.cell;
      for (let x = L.ox; x < L.ox + gw; x += ts) for (let y = L.oy; y < L.oy + gh; y += ts) f.drawImage(stones, x, y, ts, ts);
      f.globalCompositeOperation = "multiply";
      f.fillStyle = b.floor === "cave" ? "#a8987f" : "#d4b88c"; f.fillRect(0, 0, WW, WH);
      f.globalCompositeOperation = "source-over";
    } else {
      f.fillStyle = {arena: "#dcc296", earth: "#cfb487", grass: "#d6c99a"}[b.floor] || "#d8c49c";
      f.fillRect(L.ox, L.oy, gw, gh);
      const n = gw * gh / 90;
      for (let i = 0; i < n; i++) {
        f.fillStyle = `rgba(70,45,20,${.06 + r() * .14})`;
        const s = .8 + r() * (b.floor === "arena" ? 1.2 : 1.8);
        f.beginPath(); f.arc(L.ox + r() * gw, L.oy + r() * gh, s, 0, 7); f.fill();
      }
      if (b.floor === "grass") {
        for (let i = 0; i < gw * gh / 900; i++) {
          const x = L.ox + r() * gw, y = L.oy + r() * gh;
          f.strokeStyle = `rgba(60,62,28,${.25 + r() * .3})`; f.lineWidth = 1;
          for (let k = -2; k <= 2; k++) { f.beginPath(); f.moveTo(x + k * 2, y); f.lineTo(x + k * 3 + (r() - .5) * 3, y - 5 - r() * 5); f.stroke(); }
        }
      }
      if (b.floor === "earth" || b.floor === "arena") {
        for (let i = 0; i < gw * gh / 9000; i++) {
          const x = L.ox + r() * gw, y = L.oy + r() * gh, l = 40 + r() * 120;
          f.strokeStyle = "rgba(80,55,28,.18)"; f.lineWidth = 1.2;
          f.beginPath(); f.moveTo(x, y); f.bezierCurveTo(x + l / 3, y + (r() - .5) * 20, x + 2 * l / 3, y + (r() - .5) * 20, x + l, y + (r() - .5) * 10); f.stroke();
        }
      }
    }
    f.restore();
    return c;
  }

  function drawWalls(ctx, b, walls) {
    const kind = b.wall_kind === "rock" && b.floor !== "cave" ? "block" : b.wall_kind;
    const has = (x, y) => walls.has(K(x, y));
    // the shadow each wall casts down and to the right
    ctx.fillStyle = "rgba(40,25,10,.28)";
    for (const k of walls) {
      const [x, y] = k.split(",").map(Number);
      if (kind === "tree") { ctx.beginPath(); ctx.ellipse(wx(x) + L.cell * .62, wy(y) + L.cell * .7, L.cell * .44, L.cell * .3, 0, 0, 7); ctx.fill(); }
      else ctx.fillRect(wx(x) + L.cell * .14, wy(y) + L.cell * .18, L.cell, L.cell);
    }
    for (const k of [...walls].sort((a, b2) => a.split(",")[1] - b2.split(",")[1])) {
      const [x, y] = k.split(",").map(Number), r = rng(x * 977 + y * 131 + 7);
      const X = wx(x), Y = wy(y), C = L.cell;
      if (kind === "tree") {
        ctx.fillStyle = "#4a3a22"; ctx.beginPath(); ctx.arc(X + C / 2, Y + C * .62, C * .1, 0, 7); ctx.fill();
        const lobes = 7, R = C * .44;
        ctx.beginPath();
        for (let i = 0; i <= lobes; i++) {
          const a = i / lobes * Math.PI * 2, rr = R * (.82 + r() * .2);
          const px = X + C / 2 + Math.cos(a) * rr, py = Y + C * .45 + Math.sin(a) * rr;
          i ? ctx.quadraticCurveTo(X + C / 2 + Math.cos(a - Math.PI / lobes) * R * 1.12, Y + C * .45 + Math.sin(a - Math.PI / lobes) * R * 1.12, px, py) : ctx.moveTo(px, py);
        }
        ctx.closePath(); ctx.fillStyle = "#a79a6a"; ctx.fill();
        ctx.save(); ctx.clip(); hatch(ctx, X, Y + C * .35, C, C * .6, .8, 6, r, C / 60); ctx.restore();
        ctx.strokeStyle = "#1d140a"; ctx.lineWidth = Math.max(1.4, C / 26); ctx.stroke();
        continue;
      }
      if (kind === "rock") {
        const pts = [];
        for (let i = 0; i < 9; i++) { const a = i / 9 * Math.PI * 2, k2 = (.38 + r() * .12) * C; pts.push([X + C / 2 + Math.cos(a) * k2, Y + C / 2 + Math.sin(a) * k2]); }
        ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(...p) : ctx.moveTo(...p)); ctx.closePath();
        ctx.fillStyle = "#9c8664"; ctx.fill();
        ctx.save(); ctx.clip(); hatch(ctx, X + C * .2, Y + C * .35, C * .8, C * .7, .85, 6, r, C / 60); ctx.restore();
        ctx.strokeStyle = "#1d140a"; ctx.lineWidth = Math.max(1.4, C / 24); ctx.stroke();
        continue;
      }
      ctx.fillStyle = "#8d7350"; ctx.fillRect(X, Y, C, C);
      ctx.save(); ctx.beginPath(); ctx.rect(X, Y, C, C); ctx.clip();
      hatch(ctx, X, Y, C, C, .9, Math.round(10 * (C / 60) ** 2) + 4, r, C / 60);
      ctx.restore();
      ctx.strokeStyle = "#1a1009";
      const w = Math.max(2, C / 16);
      if (!has(x, y - 1)) { inkLine(ctx, X, Y, X + C, Y, w, r); ctx.fillStyle = "rgba(245,230,200,.45)"; ctx.fillRect(X + 3, Y + 3, C - 6, Math.max(2, C / 15)); }
      if (!has(x, y + 1)) inkLine(ctx, X, Y + C, X + C, Y + C, w, r);
      if (!has(x - 1, y)) inkLine(ctx, X, Y, X, Y + C, w, r);
      if (!has(x + 1, y)) inkLine(ctx, X + C, Y, X + C, Y + C, w, r);
    }
  }

  function drawStatic(b) {
    const [c, g] = canvas();
    g.save();
    const gw = b.cols * L.cell, gh = b.rows * L.cell;
    if (INDOOR.has(b.floor)) {
      // the rock round the delve: hatching that fades away from the edge
      for (let ring = 1; ring <= 3; ring++) {
        const alpha = [0, .95, .55, .22][ring];
        for (let x = -ring; x < b.cols + ring; x++) for (let y = -ring; y < b.rows + ring; y++) {
          const d = Math.max(-x, x - b.cols + 1, -y, y - b.rows + 1);
          if (d === ring) hatch(g, wx(x), wy(y), L.cell, L.cell, alpha, ring === 1 ? 7 : ring === 2 ? 4 : 2, rng(x * 31 + y * 17 + 3), L.cell / 60);
        }
      }
    }
    g.drawImage(floorLayer(b), 0, 0);
    g.strokeStyle = "rgba(50,32,16,.16)"; g.lineWidth = 1; g.setLineDash([2, 4]);
    for (let x = 0; x <= b.cols; x++) { g.beginPath(); g.moveTo(wx(x) + .5, L.oy); g.lineTo(wx(x) + .5, L.oy + gh); g.stroke(); }
    for (let y = 0; y <= b.rows; y++) { g.beginPath(); g.moveTo(L.ox, wy(y) + .5); g.lineTo(L.ox + gw, wy(y) + .5); g.stroke(); }
    g.setLineDash([]);
    for (const [x, y] of b.water) {
      g.fillStyle = "rgba(70,96,110,.32)"; g.fillRect(wx(x), wy(y), L.cell, L.cell);
      g.strokeStyle = "rgba(40,60,72,.55)"; g.lineWidth = 1.1;
      for (let k = 1; k <= 3; k++) {
        const yy = wy(y) + k * L.cell / 4; g.beginPath();
        for (let t = 0; t <= 6; t++) { const xx = wx(x) + 4 + t * (L.cell - 8) / 6; g.lineTo(xx, yy + Math.sin(t * 1.7 + x + k) * 2); }
        g.stroke();
      }
    }
    for (const [x, y, z] of b.elevation) {
      if (z < 0) {
        g.fillStyle = "rgba(30,18,8,.45)"; g.fillRect(wx(x), wy(y), L.cell, L.cell);
        hatch(g, wx(x), wy(y), L.cell, L.cell, .9, 8, rng(x * 13 + y * 7), L.cell / 60);
      } else {
        g.fillStyle = "rgba(40,25,10,.22)"; g.fillRect(wx(x) + 4, wy(y) + 6, L.cell, L.cell);
        g.fillStyle = "rgba(250,238,210,.35)"; g.fillRect(wx(x), wy(y), L.cell, L.cell);
        g.strokeStyle = "#2a1a0c"; g.lineWidth = 1.6; g.strokeRect(wx(x) + 1, wy(y) + 1, L.cell - 2, L.cell - 2);
      }
    }
    drawWalls(g, b, new Set(b.walls.map(([x, y]) => K(x, y))));
    if (INDOOR.has(b.floor)) {
      g.strokeStyle = "#1a1009";
      const w = Math.max(2.5, L.cell / 15), rr = rng(5);
      inkLine(g, L.ox, L.oy, L.ox + gw, L.oy, w, rr); inkLine(g, L.ox + gw, L.oy, L.ox + gw, L.oy + gh, w, rr);
      inkLine(g, L.ox + gw, L.oy + gh, L.ox, L.oy + gh, w, rr); inkLine(g, L.ox, L.oy + gh, L.ox, L.oy, w, rr);
    } else {
      g.strokeStyle = "rgba(42,26,12,.85)"; g.lineWidth = 2.2; g.strokeRect(L.ox - 10, L.oy - 10, gw + 20, gh + 20);
      g.lineWidth = .9; g.strokeRect(L.ox - 15, L.oy - 15, gw + 30, gh + 30);
    }
    g.restore();
    return c;
  }

  const SUB = 4;          // mask pixels a cell: the edges soften over a quarter cell, not a whole one
  const PAD = 4;          // cells of margin the fog also covers: the rock round a delve shows only where it was seen
  function cellGrid(colorOf) {
    const [s, sm] = canvas((L.cols + 2 * PAD) * SUB, (L.rows + 2 * PAD) * SUB);
    for (let x = -PAD; x < L.cols + PAD; x++) for (let y = -PAD; y < L.rows + PAD; y++) {
      const c = colorOf(Math.min(Math.max(x, 0), L.cols - 1), Math.min(Math.max(y, 0), L.rows - 1));
      if (c) { sm.fillStyle = c; sm.fillRect((x + PAD) * SUB, (y + PAD) * SUB, SUB, SUB); }
    }
    return s;
  }
  function blurUp(small, ctx, px) {
    ctx.save(); ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = "high";
    ctx.filter = `blur(${px}px)`;
    ctx.drawImage(small, L.ox - PAD * L.cell, L.oy - PAD * L.cell, (L.cols + 2 * PAD) * L.cell, (L.rows + 2 * PAD) * L.cell);
    ctx.restore();
  }

  function fogAndLight(g, s) {
    const vis = new Set(s.visible.map(([x, y]) => K(x, y)));
    const seen = new Set(s.seen.map(([x, y]) => K(x, y)));
    const level = new Map(s.light.map(([x, y, v]) => [K(x, y), v]));
    const blur = Math.max(3, L.cell * .12);
    const grid = new Path2D(); grid.rect(0, 0, WW, WH);

    // the light, as a multiply layer: dark where the side sees little, untouched where it never looked
    const sh = cellGrid((x, y) => {
      const k = K(x, y);
      let c;
      if (vis.has(k)) {
        const v = level.has(k) ? level.get(k) : .55, t = Math.pow(v, .8);
        c = [108 + (255 - 108) * t, 90 + (250 - 90) * t, 70 + (238 - 70) * t];
      } else if (seen.has(k)) c = [222, 208, 184];
      else c = [255, 255, 255];
      return `rgb(${c.map(Math.round).join(",")})`;
    });
    const [lit, lc] = canvas(); blurUp(sh, lc, blur);
    g.save(); g.clip(grid); g.globalCompositeOperation = "multiply"; g.drawImage(lit, 0, 0); g.restore();

    const [mem, mc] = canvas();
    mc.strokeStyle = "rgba(90,60,30,.16)"; mc.lineWidth = 1;
    for (let k = -WH; k < WW; k += 7) { mc.beginPath(); mc.moveTo(k, 0); mc.lineTo(k + WH, WH); mc.stroke(); }
    mc.globalCompositeOperation = "destination-in";
    blurUp(cellGrid((x, y) => seen.has(K(x, y)) ? "#fff" : null), mc, blur);
    g.save(); g.clip(grid); g.drawImage(mem, 0, 0); g.restore();

    // never seen: plain paper laid over the board
    const [unk, u] = canvas();
    u.drawImage(worldPaper, 0, 0);
    const r = rng(77);
    for (let i = 0; i < 260; i++) {
      const x = L.ox + r() * L.cols * L.cell, y = L.oy + r() * L.rows * L.cell;
      u.strokeStyle = `rgba(90,65,40,${.04 + r() * .07})`; u.lineWidth = .8;
      u.beginPath(); u.moveTo(x, y); u.lineTo(x + 8 + r() * 14, y - 2 - r() * 8); u.stroke();
    }
    u.globalCompositeOperation = "destination-in";
    blurUp(cellGrid((x, y) => !vis.has(K(x, y)) && !seen.has(K(x, y)) ? "#fff" : null), u, blur);
    g.save(); g.clip(grid); g.drawImage(unk, 0, 0); g.restore();

    // the glow of what burns
    g.save(); g.globalCompositeOperation = "screen";
    const glow = (x, y, rad, a) => {
      const gr = g.createRadialGradient(x, y, 0, x, y, rad);
      gr.addColorStop(0, `rgba(255,140,55,${a})`); gr.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = gr; g.fillRect(x - rad, y - rad, 2 * rad, 2 * rad);
    };
    for (const [x, y] of s.board.fire) glow(wx(x) + L.cell / 2, wy(y) + L.cell / 2, L.cell * 1.8, .3);
    for (const p of s.props) if (p.kind === "torch" && !p.remembered) glow(wx(p.pos[0]) + L.cell / 2, wy(p.pos[1]) + L.cell / 2, L.cell * 1.3, .32);
    for (const t of s.units) if (t.torch) glow(wx(t.pos[0]) + L.cell * t.fp / 2, wy(t.pos[1]) + L.cell * t.fp / 2, L.cell * 1.2, .22);
    g.restore();
  }

  function flame(g, px, py, h, w, r) {
    const gr = g.createLinearGradient(0, py - h, 0, py);
    gr.addColorStop(0, "#fff4c2"); gr.addColorStop(.35, "#f6b04a"); gr.addColorStop(.75, "#d4561f"); gr.addColorStop(1, "#7a2012");
    g.fillStyle = gr; g.strokeStyle = "#2a1006"; g.lineWidth = Math.max(1, h / 30);
    g.beginPath(); g.moveTo(px - w, py);
    g.bezierCurveTo(px - w - w * .35, py - h * .45, px - w * .2, py - h * .55, px - w * .5, py - h * .8);
    g.bezierCurveTo(px - w * .1, py - h * .62, px + w * .2, py - h * .9, px + (r() - .4) * w * .3, py - h);
    g.bezierCurveTo(px + w * .7, py - h * .7, px + w * 1.25, py - h * .4, px + w, py);
    g.closePath(); g.fill(); g.stroke();
    g.fillStyle = "rgba(255,250,215,.85)"; g.beginPath(); g.ellipse(px, py - h * .28, w * .35, h * .18, 0, 0, 7); g.fill();
  }

  function drawProps(g, s) {
    const C = L.cell;
    for (const [x, y] of s.board.fire) {
      const r = rng(x * 41 + y * 7 + (s.round || 0));
      const X = wx(x), Y = wy(y);
      const sc = g.createRadialGradient(X + C / 2, Y + C / 2, 2, X + C / 2, Y + C / 2, C * .7);
      sc.addColorStop(0, "rgba(25,12,4,.7)"); sc.addColorStop(1, "rgba(25,12,4,0)");
      g.fillStyle = sc; g.fillRect(X - C * .2, Y - C * .2, C * 1.4, C * 1.4);
      for (let i = 0; i < 3; i++) flame(g, X + C * (.22 + i * .28) + (r() - .5) * C * .08, Y + C * (.75 + r() * .15), C * (.5 + r() * .3), C * (.15 + r() * .06), r);
    }
    for (const p of s.props) {
      const [x, y] = p.pos, X = wx(x), Y = wy(y), r = rng(x * 19 + y * 23);
      g.globalAlpha = p.remembered ? .55 : 1;
      if (p.kind === "corpse") {
        const m = (p.size || 1) * C, bx = X + m / 2, by = Y + m / 2;
        for (let i = 0; i < 12; i++) { g.fillStyle = `rgba(118,30,20,${.45 + r() * .35})`; g.beginPath(); g.arc(bx + (r() - .5) * m * .7, by + (r() - .5) * m * .55, (1.5 + r() * 5) * C / 60, 0, 7); g.fill(); }
        g.fillStyle = "rgba(118,30,20,.7)"; g.beginPath(); g.ellipse(bx, by + m * .08, m * .26, m * .16, .4, 0, 7); g.fill();
        g.strokeStyle = "#3a1008"; g.lineWidth = Math.max(2, C / 22); const k = m * .15;
        g.beginPath(); g.moveTo(bx - k, by - k); g.lineTo(bx + k, by + k); g.moveTo(bx + k, by - k); g.lineTo(bx - k, by + k); g.stroke();
      } else if (p.kind === "torch") {
        g.fillStyle = "#3a2612"; g.fillRect(X + C * .46, Y + C * .5, C * .08, C * .32);
        flame(g, X + C / 2, Y + C * .54, C * .36, C * .11, r);
      } else if (p.kind === "chest") {
        g.fillStyle = "#b08a52"; g.strokeStyle = "#1d140a"; g.lineWidth = Math.max(1.5, C / 30);
        g.fillRect(X + C * .22, Y + C * .32, C * .56, C * .38); g.strokeRect(X + C * .22, Y + C * .32, C * .56, C * .38);
        g.beginPath(); g.moveTo(X + C * .22, Y + C * .45); g.lineTo(X + C * .78, Y + C * .45); g.stroke();
        g.fillStyle = "#e8c66a"; g.fillRect(X + C * .47, Y + C * .42, C * .06, C * .08);
      } else if (p.kind === "trap") {
        g.strokeStyle = "#3a1008"; g.lineWidth = Math.max(1.5, C / 28);
        g.beginPath(); g.arc(X + C / 2, Y + C / 2, C * .22, 0, 7); g.stroke();
        for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2; g.beginPath(); g.moveTo(X + C / 2 + Math.cos(a) * C * .22, Y + C / 2 + Math.sin(a) * C * .22); g.lineTo(X + C / 2 + Math.cos(a) * C * .3, Y + C / 2 + Math.sin(a) * C * .3); g.stroke(); }
      } else {
        g.fillStyle = "#d8c39b"; g.strokeStyle = "#2a1a0c"; g.lineWidth = 1.4;
        g.beginPath(); g.ellipse(X + C / 2, Y + C * .6, C * .16, C * .1, -.4, 0, 7); g.fill(); g.stroke();
        g.beginPath(); g.moveTo(X + C * .38, Y + C * .7); g.lineTo(X + C * .68, Y + C * .4); g.stroke();
      }
      g.globalAlpha = 1;
    }
  }

  async function draw(s) {
    await ready;
    const b = s.board;
    if (layout(b.cols, b.rows) || !worldPaper) { const [pc, p] = canvas(); paper(p, WW, WH, "#e6d5b0", 13); worldPaper = pc; }
    if (!paperCanvas) { const [pc, p] = canvas(W, H); paper(p, W, H, "#e6d5b0", 11); paperCanvas = pc; }
    const key = [b.cols, b.rows, L.cell, b.floor, b.walls.length, b.water.length, b.elevation.length].join("|");
    if (key !== staticKey) { staticCanvas = drawStatic(b); staticKey = key; }
    const [wc, g] = canvas();
    g.drawImage(staticCanvas, 0, 0);
    drawProps(g, s);
    fogAndLight(g, s);
    worldCanvas = wc;
    blit();
  }

  function blit() {
    base.clearRect(0, 0, W, H);
    if (!paperCanvas) return;
    base.drawImage(paperCanvas, 0, 0);
    if (!worldCanvas) return;
    base.save(); deckle(base, rng(7919)); base.clip();
    base.imageSmoothingEnabled = true; base.imageSmoothingQuality = "high";
    base.drawImage(worldCanvas, V.x, V.y, WW * V.s, WH * V.s);
    base.restore();
  }

  let onView = null;
  function moved() { clamp(); blit(); if (onView) onView(); }
  function zoomAt(px, py, factor) {
    const ns = Math.min(V.max, Math.max(V.fit, V.s * factor));
    if (ns === V.s) return;
    V.x = px - (px - V.x) * ns / V.s; V.y = py - (py - V.y) * ns / V.s; V.s = ns;
    moved();
  }
  function panBy(dx, dy) { V.x += dx; V.y += dy; moved(); }
  function centerOn([x, y], fp = 1) {
    V.x = W / 2 - (wx(x) + L.cell * fp / 2) * V.s; V.y = H / 2 - (wy(y) + L.cell * fp / 2) * V.s;
    moved();
  }
  // bring `cell` on screen when it is off it or within a cell of the edge; true when the camera moved
  function reveal(cell, fp = 1) {
    const x0 = cx(cell[0]), y0 = cy(cell[1]), m = V.cell;
    if (x0 >= MARGIN + m && x0 + V.cell * fp <= W - MARGIN - m && y0 >= MARGIN + m && y0 + V.cell * fp <= H - MARGIN - m) return false;
    centerOn(cell, fp);
    return true;
  }

  function overlay(s, ui) {
    over.clearRect(0, 0, W, H);
    const C = V.cell;
    if (s && s.setup && !s.handoff) {
      over.fillStyle = "rgba(201,163,94,.28)"; over.strokeStyle = "rgba(125,92,40,.85)"; over.lineWidth = 1.5;
      for (const [x, y] of s.setup.cells) { over.fillRect(cx(x) + 1, cy(y) + 1, C - 2, C - 2); over.strokeRect(cx(x) + 3.5, cy(y) + 3.5, C - 7, C - 7); }
      return;
    }
    if (!s || !s.my_turn) return;
    if (ui.aim) {
      const col = {attack: "201,71,58", demo: "128,70,150", heal: "90,140,70", move: "70,110,150", spell: "201,163,94", throw: "214,120,40"}[ui.aim.kind] || "201,163,94";
      over.fillStyle = `rgba(${col},.22)`; over.strokeStyle = `rgba(${col},.75)`; over.lineWidth = 1.5;
      for (const [x, y] of ui.aim.cells) { over.fillRect(cx(x) + 1, cy(y) + 1, C - 2, C - 2); over.strokeRect(cx(x) + 3.5, cy(y) + 3.5, C - 7, C - 7); }
      return;
    }
    const reach = new Set(s.reach.map(([x, y]) => K(x, y)));
    over.fillStyle = "rgba(176,132,48,.16)";
    for (const [x, y] of s.reach) over.fillRect(cx(x), cy(y), C, C);
    over.strokeStyle = "rgba(125,92,40,.8)"; over.lineWidth = 2; over.setLineDash([5, 4]);
    for (const [x, y] of s.reach) {
      if (!reach.has(K(x, y - 1))) { over.beginPath(); over.moveTo(cx(x), cy(y)); over.lineTo(cx(x + 1), cy(y)); over.stroke(); }
      if (!reach.has(K(x, y + 1))) { over.beginPath(); over.moveTo(cx(x), cy(y + 1)); over.lineTo(cx(x + 1), cy(y + 1)); over.stroke(); }
      if (!reach.has(K(x - 1, y))) { over.beginPath(); over.moveTo(cx(x), cy(y)); over.lineTo(cx(x), cy(y + 1)); over.stroke(); }
      if (!reach.has(K(x + 1, y))) { over.beginPath(); over.moveTo(cx(x + 1), cy(y)); over.lineTo(cx(x + 1), cy(y + 1)); over.stroke(); }
    }
    over.setLineDash([]);
    const fp = s.active ? (s.units.find(u => u.id === s.active.id) || {fp: 1}).fp : 1;
    const mid = ([x, y]) => [cx(x) + C * fp / 2, cy(y) + C * fp / 2];
    for (let i = 0; i < s.trail.length - 1; i++) {
      const [ax, ay] = mid(s.trail[i]), [bx, by] = mid(s.trail[i + 1]);
      for (let t = .25; t < 1; t += .5) {
        over.fillStyle = "rgba(42,26,12,.6)"; over.beginPath();
        over.ellipse(ax + (bx - ax) * t, ay + (by - ay) * t + (t < .5 ? -4 : 4), C / 11, C / 16, Math.atan2(by - ay, bx - ax), 0, 7); over.fill();
      }
    }
    if (ui.route && ui.route.path.length >= 2) {
      over.strokeStyle = "rgba(42,26,12,.85)"; over.lineWidth = Math.max(2, C / 20); over.setLineDash([C / 7, C / 9]); over.lineCap = "round";
      over.beginPath(); ui.route.path.forEach((c, i) => { const [x, y] = mid(c); i ? over.lineTo(x, y) : over.moveTo(x, y); }); over.stroke();
      over.setLineDash([]);
      const [ex, ey] = mid(ui.route.path[ui.route.path.length - 1]);
      over.beginPath(); over.arc(ex, ey, C * .32, 0, 7); over.strokeStyle = "rgba(42,26,12,.85)"; over.lineWidth = 2; over.stroke();
      if (ui.route.cost != null) {
        over.fillStyle = "#2a1c10"; over.beginPath(); over.arc(ex + C * .3, ey - C * .3, C * .17, 0, 7); over.fill();
        over.fillStyle = "#f0d79e"; over.font = `700 ${Math.round(C * .2)}px Cinzel`; over.textAlign = "center"; over.textBaseline = "middle";
        over.fillText(ui.route.cost, ex + C * .3, ey - C * .29);
      }
    }
  }

  function cellAt(px, py) {
    const x = Math.floor((px - cx(0)) / V.cell), y = Math.floor((py - cy(0)) / V.cell);
    return x >= 0 && y >= 0 && x < L.cols && y < L.rows ? [x, y] : null;
  }

  return {draw, overlay, cellAt, layout: V, cx, cy, zoomAt, panBy, centerOn, reveal,
          zoomed: () => V.s > V.fit + 1e-6, set onView(fn) { onView = fn; }};
})();

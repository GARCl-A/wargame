// The board painted as an inked map: paper, hatched rock, the floor of the place, and over it
// the fog (the dark table where the side has never looked) and the light, smoothed from the
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
  const IMG = {};
  const ready = Promise.all(["flagstones.jpg", "rock.jpg", "grass.jpg", "sand.jpg", "boulder.png",
                             "tree_1.png", "tree_2.png", "tree_3.png"].map(f => new Promise(r => {
    const im = new Image(); im.onload = () => { IMG[f.split(".")[0]] = im; r(); }; im.onerror = r;
    im.src = "/client/img/" + f;
  })));
  // One value scale holds every layer apart: what was seen before is pale paper, the lit floor sits
  // mid, the never seen is the dark table, walls are dark and the tokens carry the strongest contrast. Each place tints one texture:
  // `hue` gives it the place's colour (a "color" blend keeps the engraving's values), `mul` then
  // pulls it down into the floor's band. `cells` is the texture's span on the board.
  const FLOORS = {
    stone:  {tex: "flagstones", cells: 7, hue: "#7c7f85", mul: "#8d8b88"},
    cobble: {tex: "flagstones", cells: 4, hue: "#7c766c", mul: "#8a8478"},
    cave:   {tex: "rock",       cells: 6, hue: "#6f7a86", mul: "#b4bcc4"},
    arena:  {tex: "sand",       cells: 8, hue: "#b98a52", mul: "#c9a57a"},
    earth:  {tex: "sand",       cells: 7, hue: "#8c6a46", mul: "#a3876a"},
    grass:  {tex: "grass",      cells: 5, hue: "#7d8a5e", mul: "#c3c6a8"},
  };
  // walls by kind: the masonry's fill, and the tint (as the floors') that sinks a tree or a boulder into the dark band
  const WALL = {block: "#4b3f33", tree: {hue: "#4e5f3c", mul: "#9da38c"}, rock: {hue: "#6d6f73", mul: "#8e8b86"}};

  let staticKey = null, staticCanvas = null, paperCanvas = null, worldVoid = null, worldCanvas = null, mips = [];

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
  // world-sized canvases a state's paint reuses: allocating four of them per state cost more than drawing them
  const scratches = new Map();
  function scratch(name) {
    let e = scratches.get(name);
    if (!e || e[0].width !== WW || e[0].height !== WH) scratches.set(name, e = canvas());
    const ctx = e[1];
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1; ctx.filter = "none";
    ctx.clearRect(0, 0, WW, WH);
    return e;
  }
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
    const st = FLOORS[b.floor] || FLOORS.stone, tex = IMG[st.tex];
    f.save(); f.beginPath(); f.rect(L.ox, L.oy, gw, gh); f.clip();
    const ts = st.cells * L.cell;
    for (let x = L.ox; x < L.ox + gw; x += ts) for (let y = L.oy; y < L.oy + gh; y += ts) f.drawImage(tex, x, y, ts, ts);
    f.globalCompositeOperation = "color"; f.fillStyle = st.hue; f.fillRect(0, 0, WW, WH);
    f.globalCompositeOperation = "multiply"; f.fillStyle = st.mul; f.fillRect(0, 0, WW, WH);
    // broad patches of light and shade, so a big board does not read as one repeated tile
    for (let i = 0; i < gw * gh / (L.cell * L.cell * 6); i++) {
      const x = L.ox + r() * gw, y = L.oy + r() * gh, rad = L.cell * (2 + r() * 4);
      const gr = f.createRadialGradient(x, y, 0, x, y, rad);
      gr.addColorStop(0, r() < .5 ? `rgba(60,48,36,${.25 + r() * .25})` : `rgba(255,250,235,${.2 + r() * .2})`);
      gr.addColorStop(1, "rgba(255,255,255,0)");
      f.globalCompositeOperation = "soft-light"; f.fillStyle = gr; f.fillRect(x - rad, y - rad, 2 * rad, 2 * rad);
    }
    f.restore();
    return c;
  }

  // a tree or a boulder from the art, turned at random and sunk into the walls' dark band
  function sprite(ctx, im, X, Y, C, scale, r, tint) {
    const s = C * scale, a = r() * Math.PI * 2;
    const [sc, sg] = canvas(Math.ceil(s), Math.ceil(s));
    sg.translate(s / 2, s / 2); sg.rotate(a); sg.drawImage(im, -s / 2, -s / 2, s, s);
    sg.setTransform(1, 0, 0, 1, 0, 0);
    sg.globalCompositeOperation = "color"; sg.fillStyle = tint.hue; sg.fillRect(0, 0, s, s);
    sg.globalCompositeOperation = "multiply"; sg.fillStyle = tint.mul; sg.fillRect(0, 0, s, s);
    sg.globalCompositeOperation = "destination-in"; sg.translate(s / 2, s / 2); sg.rotate(a); sg.drawImage(im, -s / 2, -s / 2, s, s);
    ctx.drawImage(sc, X + C / 2 - s / 2, Y + C / 2 - s / 2);
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
      if (kind === "tree" || kind === "rock") {
        const tree = kind === "tree", im = tree ? IMG["tree_" + (1 + Math.floor(hash(x, y) * 3))] : IMG.boulder;
        sprite(ctx, im, X, Y, C, (tree ? 1.2 : 1.05) + r() * .15, r, WALL[kind]);
        continue;
      }
      ctx.fillStyle = WALL.block; ctx.fillRect(X, Y, C, C);
      ctx.save(); ctx.beginPath(); ctx.rect(X, Y, C, C); ctx.clip();
      hatch(ctx, X, Y, C, C, .9, Math.round(10 * (C / 60) ** 2) + 4, r, C / 60);
      ctx.restore();
      ctx.strokeStyle = "#140c06";
      const w = Math.max(2, C / 16);
      if (!has(x, y - 1)) { inkLine(ctx, X, Y, X + C, Y, w, r); ctx.fillStyle = "rgba(220,200,165,.35)"; ctx.fillRect(X + 3, Y + 3, C - 6, Math.max(2, C / 15)); }
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
        g.fillStyle = "rgba(16,9,4,.30)"; g.fillRect(wx(x), wy(y), L.cell, L.cell);
        g.save(); g.beginPath(); g.rect(wx(x), wy(y), L.cell, L.cell); g.clip();
        g.strokeStyle = "rgba(26,16,9,.22)"; g.lineWidth = 1.2;
        const gap = L.cell * .14;
        for (let k = -L.cell; k < L.cell; k += gap) {
          g.beginPath(); g.moveTo(wx(x) + k, wy(y) + L.cell); g.lineTo(wx(x) + k + L.cell, wy(y)); g.stroke();
        }
        g.restore();
      } else {
        g.fillStyle = "rgba(40,25,10,.22)"; g.fillRect(wx(x) + 4, wy(y) + 6, L.cell, L.cell);
        g.fillStyle = "rgba(250,238,210,.35)"; g.fillRect(wx(x), wy(y), L.cell, L.cell);
        g.strokeStyle = "#2a1a0c"; g.lineWidth = 1.6; g.strokeRect(wx(x) + 1, wy(y) + 1, L.cell - 2, L.cell - 2);
      }
    }
    drawPitLips(g, b);
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

  function drawPitLips(g, b) {
    const Z = new Map(b.elevation.filter(e => e[2] < 0).map(([x, y, z]) => [K(x, y), z]));
    if (!Z.size) return;
    const zAt = (x, y) => Z.get(K(x, y)) ?? 0, c = L.cell;
    g.save(); g.strokeStyle = "#2a1a0c"; g.lineCap = "round";
    for (const [k, z] of Z) {
      const [x, y] = k.split(",").map(Number);
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        if (zAt(x + dx, y + dy) <= z) continue;
        const px = wx(x), py = wy(y);
        g.lineWidth = Math.max(2, c * .052); g.beginPath();
        if (dx) { const X = dx > 0 ? px + c : px; g.moveTo(X, py); g.lineTo(X, py + c); }
        else { const Y = dy > 0 ? py + c : py; g.moveTo(px, Y); g.lineTo(px + c, Y); }
        g.stroke(); g.lineWidth = Math.max(1.4, c * .036);
        for (const t of [.25, .75]) {
          g.beginPath();
          if (dx) { const X = dx > 0 ? px + c : px; g.moveTo(X, py + t * c); g.lineTo(X - dx * c * .2, py + t * c); }
          else { const Y = dy > 0 ? py + c : py; g.moveTo(px + t * c, Y); g.lineTo(px + t * c, Y - dy * c * .2); }
          g.stroke();
        }
      }
    }
    const seen = new Set();
    g.font = `700 ${Math.round(c * .34)}px "Cinzel", Georgia, serif`; g.textAlign = "center"; g.textBaseline = "middle";
    g.shadowColor = "#000"; g.shadowBlur = 3; g.fillStyle = "#f0d79e";
    for (const k of Z.keys()) {
      if (seen.has(k)) continue;
      const cells = [], stack = [k]; seen.add(k);
      while (stack.length) {
        const cur = stack.pop(); cells.push(cur.split(",").map(Number));
        const [x, y] = cells[cells.length - 1];
        for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          const n = K(x + dx, y + dy);
          if (Z.has(n) && !seen.has(n)) { seen.add(n); stack.push(n); }
        }
      }
      const mx = cells.reduce((s, p) => s + p[0], 0) / cells.length, my = cells.reduce((s, p) => s + p[1], 0) / cells.length;
      const [lx, ly] = cells.reduce((best, p) => Math.hypot(p[0] - mx, p[1] - my) < Math.hypot(best[0] - mx, best[1] - my) ? p : best);
      g.fillText("−" + -Z.get(k), wx(lx) + c / 2, wy(ly) + c / 2);
    }
    g.restore();
  }

  const SUB = 4;         // mask pixels a cell: the edges soften over a quarter cell, not a whole one
  const PAD = 4;          // cells of margin the fog also covers: the rock round a delve shows only where it was seen
  function cellGrid(colorOf) {
    const [s, sm] = canvas((L.cols + 2 * PAD) * SUB, (L.rows + 2 * PAD) * SUB);
    for (let x = -PAD; x < L.cols + PAD; x++) for (let y = -PAD; y < L.rows + PAD; y++) {
      const c = colorOf(Math.min(Math.max(x, 0), L.cols - 1), Math.min(Math.max(y, 0), L.rows - 1));
      if (c) { sm.fillStyle = c; sm.fillRect((x + PAD) * SUB, (y + PAD) * SUB, SUB, SUB); }
    }
    return s;
  }
  // the blur runs on the small grid and the upscale smooths the rest: blurring the world-sized canvas
  // instead was most of a state's paint
  const edge = () => Math.max(3, L.cell * .12);     // px the fog's and the light's edges soften over
  function blurUp(small, ctx, px) {
    const [b, bc] = canvas(small.width, small.height);
    bc.filter = `blur(${px * SUB / L.cell}px)`; bc.drawImage(small, 0, 0);
    ctx.save(); ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = "high";
    ctx.drawImage(b, L.ox - PAD * L.cell, L.oy - PAD * L.cell, (L.cols + 2 * PAD) * L.cell, (L.rows + 2 * PAD) * L.cell);
    ctx.restore();
  }

  const DARK = [12, 14, 22], DIM = [190, 196, 210], SUN = "#fff4e2";
  // a light's colour, and how its reach fades: full to `core` of the way, gone at the edge (as `lighting._falloff`)
  const POOL = {torch: {rgb: "255,206,140", core: .3}, fire: {rgb: "255,150,70", core: .25}};

  // the floor a light reaches: a polygon cast from the cell's middle and stopped by the walls the side
  // knows, with a little past each hit so the face of a wall takes the light
  function pool(x, y, r, walls) {
    const C = L.cell, ox = wx(x) + C / 2, oy = wy(y) + C / 2, R = (r + .5) * C;
    const segs = [], angles = [];
    for (let i = 0; i < 72; i++) angles.push(i / 72 * Math.PI * 2);
    for (let cx0 = x - r - 1; cx0 <= x + r + 1; cx0++) for (let cy0 = y - r - 1; cy0 <= y + r + 1; cy0++) {
      if (!walls.has(K(cx0, cy0))) continue;
      const X0 = wx(cx0), Y0 = wy(cy0), X1 = X0 + C, Y1 = Y0 + C;
      // only the faces turned to the light and not against another wall can stop a ray first
      if (oy < Y0 && !walls.has(K(cx0, cy0 - 1))) segs.push([X0, Y0, X1, Y0]);
      if (oy > Y1 && !walls.has(K(cx0, cy0 + 1))) segs.push([X0, Y1, X1, Y1]);
      if (ox < X0 && !walls.has(K(cx0 - 1, cy0))) segs.push([X0, Y0, X0, Y1]);
      if (ox > X1 && !walls.has(K(cx0 + 1, cy0))) segs.push([X1, Y0, X1, Y1]);
    }
    for (const [x1, y1, x2, y2] of segs) for (const [px, py] of [[x1, y1], [x2, y2]]) {
      const a = Math.atan2(py - oy, px - ox);
      angles.push(a - 1e-4, a + 1e-4);
    }
    angles.sort((a, b) => a - b);
    const path = new Path2D();
    angles.forEach((a, i) => {
      const dx = Math.cos(a), dy = Math.sin(a);
      let t = R;
      for (const [x1, y1, x2, y2] of segs) {
        const sx = x2 - x1, sy = y2 - y1, den = dx * sy - dy * sx;
        if (Math.abs(den) < 1e-9) continue;
        const u = ((x1 - ox) * sy - (y1 - oy) * sx) / den, v = ((x1 - ox) * dy - (y1 - oy) * dx) / den;
        if (u > 0 && v >= 0 && v <= 1 && u < t) t = u;
      }
      if (t < R) t = Math.min(R, t + C * .3);
      i ? path.lineTo(ox + dx * t, oy + dy * t) : path.moveTo(ox + dx * t, oy + dy * t);
    });
    path.closePath();
    return {path, ox, oy, R};
  }

  // a pool's warm falloff in `rgb`, `k` times as strong
  function falloff(ctx, p, look, rgb = look.rgb, k = 1) {
    const gr = ctx.createRadialGradient(p.ox, p.oy, 0, p.ox, p.oy, p.R);
    gr.addColorStop(0, `rgba(${rgb},${k})`); gr.addColorStop(look.core, `rgba(${rgb},${.95 * k})`);
    gr.addColorStop(.65, `rgba(${rgb},${.3 * k})`); gr.addColorStop(1, `rgba(${rgb},0)`);
    ctx.fillStyle = gr; ctx.fill(p.path);
  }

  // by day the sun stands up and to the left: every wall the side knows throws a soft shadow down and right
  let sunKey = null, sunCanvas = null;
  function sunShadows(s) {
    const key = staticKey + "|" + s.board.walls.length;
    if (key === sunKey) return sunCanvas;
    const C = L.cell, tree = s.board.wall_kind === "tree";
    const [sh, sg] = canvas();
    sg.fillStyle = "#000";
    for (const [x, y] of s.board.walls) for (let t = .15; t <= 1; t += .085) {
      const X = wx(x) + t * C * .75, Y = wy(y) + t * C * .55;
      if (tree) { sg.beginPath(); sg.arc(X + C / 2, Y + C / 2, C * .5, 0, 7); sg.fill(); }
      else sg.fillRect(X, Y, C, C);
    }
    sg.globalCompositeOperation = "destination-out";
    for (const [x, y] of s.board.walls) {
      if (tree) { sg.beginPath(); sg.arc(wx(x) + C / 2, wy(y) + C / 2, C * .6, 0, 7); sg.fill(); }
      else sg.fillRect(wx(x), wy(y), C, C);
    }
    const [c, cg] = canvas();
    cg.fillStyle = "#fff"; cg.fillRect(0, 0, WW, WH);
    cg.globalAlpha = .38; cg.filter = `blur(${Math.max(2, C * .14)}px)`; cg.drawImage(sh, 0, 0);
    sunKey = key; sunCanvas = c;
    return c;
  }

  // `layer` showing only where the cell mask `grid` is white, its edges softened over `blur` px; the
  // canvas it returns is the next call's too, so draw it before masking again
  function masked(layer, grid, blur) {
    const [c, cc] = scratch("mask");
    blurUp(grid, cc, blur);
    cc.globalCompositeOperation = "source-in"; cc.drawImage(layer, 0, 0);
    return c;
  }

  // seen before: the same ground washed to sepia and sunk below the lit floor, hatched like a map's old
  // survey; washed once per board, since a canvas filter over the whole world is dear
  let memKey = null, memCanvas = null;
  function memory(g, s) {
    if (memKey !== staticKey) {
      const [m, mc] = canvas();
      mc.filter = "grayscale(1) sepia(.8) brightness(1.55) contrast(.4)";
      mc.drawImage(staticCanvas, 0, 0); mc.filter = "none";
      memKey = staticKey; memCanvas = m;
    }
    const seen = new Set(s.seen.map(([x, y]) => K(x, y)));
    g.drawImage(masked(memCanvas, cellGrid((x, y) => seen.has(K(x, y)) ? "#fff" : null), edge()), 0, 0);
  }

  // the lights the side sees and the cells in sight, kept from the last paint so the flicker can play
  // over it frame by frame without painting it again
  let flames = [], sight = null;
  const FLICKER_MS = 66, STILL = matchMedia("(prefers-reduced-motion: reduce)").matches;

  function flicker(now) {
    if (!flames.length || STILL) return;
    base.save(); deckle(base, rng(7919)); base.clip();
    base.setTransform(V.s, 0, 0, V.s, V.x, V.y); base.clip(sight);
    for (const f of flames) {
      const t = now / 1000 + f.phase, fire = f.look === POOL.fire;
      const n = .55 * Math.sin(t * 7.3) + .3 * Math.sin(t * 13.1 + 1.7) + .15 * Math.sin(t * 23.7 + .4);
      const amp = (fire ? .2 : .13) * n;
      if (amp > 0) { base.globalCompositeOperation = "lighter"; falloff(base, f.p, f.look, f.look.rgb, amp * .5); }
      else { base.globalCompositeOperation = "source-over"; falloff(base, f.p, f.look, "20,10,4", -amp); }
    }
    base.restore();
  }

  let lastFrame = 0, running = false;
  function animate(now) {
    if (!flames.length || STILL) { running = false; return; }
    if (now - lastFrame >= FLICKER_MS) { lastFrame = now; blit(now); }
    requestAnimationFrame(animate);
  }

  function fogAndLight(g, s) {
    flames = [];
    const vis = new Set(s.visible.map(([x, y]) => K(x, y)));
    const seen = new Set(s.seen.map(([x, y]) => K(x, y)));
    const level = new Map(s.light.map(([x, y, v]) => [K(x, y), v]));
    const blur = edge();

    // the light, as a multiply layer over the cells in sight; elsewhere it leaves the board alone
    const [lit, lc] = scratch("light");
    if (s.daylight) {
      lc.fillStyle = SUN; lc.fillRect(0, 0, WW, WH);
      lc.globalCompositeOperation = "multiply"; lc.drawImage(sunShadows(s), 0, 0);
    } else {
      // what the server leaves to the cells (the eyes' own sight, the glow of a light out of sight) is cool
      // and dim; each light the side sees is drawn here, warm, and cut by the walls it knows
      blurUp(cellGrid((x, y) => {
        const t = Math.pow(level.get(K(x, y)) || 0, .9);
        return `rgb(${DARK.map((d, i) => Math.round(d + (DIM[i] - d) * t)).join(",")})`;
      }), lc, blur);
      lc.globalCompositeOperation = "lighten";      // lights overlap as the rules do: the brightest wins
      const walls = new Set(s.board.walls.map(([x, y]) => K(x, y)));
      for (const [x, y, r, kind] of s.lights) {
        const p = pool(x, y, r, walls), look = POOL[kind] || POOL.torch;
        falloff(lc, p, look);
        flames.push({p, look, phase: hash(x, y, 5) * 100});
      }
    }
    sight = new Path2D();
    for (const [x, y] of s.visible) sight.rect(wx(x), wy(y), L.cell, L.cell);
    lc.globalCompositeOperation = "destination-in";
    blurUp(cellGrid((x, y) => vis.has(K(x, y)) ? "#fff" : null), lc, blur);
    lc.globalCompositeOperation = "destination-over"; lc.fillStyle = "#fff"; lc.fillRect(0, 0, WW, WH);
    g.save(); g.beginPath(); g.rect(L.ox, L.oy, L.cols * L.cell, L.rows * L.cell); g.clip();
    g.globalCompositeOperation = "multiply"; g.drawImage(lit, 0, 0); g.restore();

    // never seen: the dark table, empty
    g.drawImage(masked(worldVoid, cellGrid((x, y) => !vis.has(K(x, y)) && !seen.has(K(x, y)) ? "#fff" : null), blur), 0, 0);

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
    if (layout(b.cols, b.rows) || !worldVoid) {
      const [pc, p] = canvas(); paper(p, WW, WH, "#0e0b08", 13);
      const r = rng(77);
      for (let i = 0; i < 260; i++) {
        const x = L.ox + r() * L.cols * L.cell, y = L.oy + r() * L.rows * L.cell;
        p.strokeStyle = `rgba(150,115,70,${.03 + r() * .04})`; p.lineWidth = .8;
        p.beginPath(); p.moveTo(x, y); p.lineTo(x + 8 + r() * 14, y - 2 - r() * 8); p.stroke();
      }
      worldVoid = pc;
    }
    if (!paperCanvas) { const [pc, p] = canvas(W, H); paper(p, W, H, "#16110c", 11); paperCanvas = pc; }
    const key = [b.cols, b.rows, L.cell, b.floor, b.walls.length, b.water.length, b.elevation.length].join("|");
    if (key !== staticKey) { staticCanvas = drawStatic(b); staticKey = key; }
    const [wc, g] = scratch("world");
    g.drawImage(staticCanvas, 0, 0);
    memory(g, s);
    drawProps(g, s);
    fogAndLight(g, s);
    worldCanvas = wc; mips = [wc];
    blit();
    if (flames.length && !STILL && !running) { running = true; requestAnimationFrame(animate); }
  }

  function blit(now = performance.now()) {
    base.clearRect(0, 0, W, H);
    if (!paperCanvas) return;
    base.drawImage(paperCanvas, 0, 0);
    if (!worldCanvas) return;
    base.save(); deckle(base, rng(7919)); base.clip();
    base.imageSmoothingEnabled = true; base.imageSmoothingQuality = "high";
    const k = mipLevel(V.s);
    base.drawImage(mips[k], V.x, V.y, WW * V.s, WH * V.s);
    base.restore();
    flicker(now);
  }

  // one drawImage shrinks by 2x at most without aliasing: a smaller view steps the world down by halves, each cached until the next paint
  function mipLevel(s) {
    const k = Math.max(0, Math.floor(Math.log2(1 / s)));
    for (let i = mips.length; i <= k; i++) {
      const prev = mips[i - 1];
      const [c, g] = canvas(Math.max(1, Math.ceil(prev.width / 2)), Math.max(1, Math.ceil(prev.height / 2)));
      g.imageSmoothingEnabled = true; g.imageSmoothingQuality = "high";
      g.drawImage(prev, 0, 0, c.width, c.height);
      mips[i] = c;
    }
    return k;
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

// What the browser itself measures as broken on the page it is showing. Run by tests/layout.py as
// `(source)(options)`; the answer is a list of {kind, where, text, by}.
//   scroll     a box named in `fit` holds more than it shows (a card that must be read whole)
//   clipped    words cut by a box that hides its overflow
//   ellipsis   the same, where the box ends the line with "..." (asked for with `ellipsis: true`)
//   spill      words past the edge of the painted box they sit in (a button, a plate, a card)
//   offscreen  words past the edge of the window
//   overlap    two runs of words drawn over each other
//   crowded    two runs of words from different boxes on one line with no gap between them
// A node that breaks a rule on purpose says so where it is written: data-layout-ok="why".
(opt = {}) => {
  const root = document.querySelector(opt.root || "body");
  if (!root) return [{kind: "missing", where: opt.root, text: "", by: 0}];
  const EPS = 1.5, GAP = 3, found = [], seen = new Set();
  const path = el => {
    const parts = [];
    for (let e = el; e && e !== document.body && parts.length < 4; e = e.parentElement) {
      if (e.id) { parts.unshift("#" + e.id); break; }
      const cls = [...e.classList].slice(0, 2).map(c => "." + c).join("");
      parts.unshift(e.tagName.toLowerCase() + cls);
    }
    return parts.join(" > ");
  };
  const words = el => (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 70);
  const report = (kind, el, by, other) => {
    const where = path(el) + (other ? "  x  " + path(other) : "");
    const id = kind + "|" + where + "|" + words(el);
    if (seen.has(id)) return;
    seen.add(id);
    found.push({kind, where, text: words(el) + (other ? "  x  " + words(other) : ""), by: Math.round(by)});
    if (opt.mark) for (const e of [el, other]) if (e) { e.style.outline = "3px solid #ff2a2a"; e.style.outlineOffset = "1px"; }
  };
  const allowed = el => !!el.closest("[data-layout-ok]");
  const shown = el => el.checkVisibility({opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true});
  const over = (r, box) => Math.max(box.left - r.left, r.right - box.right, box.top - r.top, r.bottom - box.bottom);
  const inner = el => {
    const r = el.getBoundingClientRect(), sx = r.width / (el.offsetWidth || r.width || 1), sy = r.height / (el.offsetHeight || r.height || 1);
    return {left: r.left + el.clientLeft * sx, top: r.top + el.clientTop * sy,
            right: r.left + (el.clientLeft + el.clientWidth) * sx, bottom: r.top + (el.clientTop + el.clientHeight) * sy};
  };
  const painted = cs => cs.backgroundImage !== "none" || !/rgba\(.*, 0\)|transparent/.test(cs.backgroundColor) ||
    ["Top", "Right", "Bottom", "Left"].some(s => parseFloat(cs[`border${s}Width`]) > 0 && cs[`border${s}Style`] !== "none");

  for (const sel of opt.fit || []) for (const el of document.querySelectorAll(sel)) {
    const by = Math.max(el.scrollHeight - el.clientHeight, el.scrollWidth - el.clientWidth);
    if (shown(el) && by > 1 && !allowed(el)) report("scroll", el, by);
  }

  // every run of words: a text node's line boxes, with the element that owns it
  const stage = document.getElementById("stage");
  const zoom = stage && stage.offsetWidth ? stage.getBoundingClientRect().width / stage.offsetWidth : 1;
  const runs = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const el = n.parentElement;
    if (!n.nodeValue.trim() || !el || !shown(el) || allowed(el) || /^(SCRIPT|STYLE|TITLE|OPTION)$/.test(el.tagName)) continue;
    range.selectNodeContents(n);
    // a line box is as tall as the font's own metrics, taller than a tight line-height: the ink is the
    // middle of it, about the font size
    const ink = parseFloat(getComputedStyle(el).fontSize) * zoom * 0.8;
    const rects = [...range.getClientRects()].filter(r => r.width > 1 && r.height > 1).map(r => {
      const cut = Math.max(0, (r.height - ink) / 2);
      return {left: r.left, right: r.right, top: r.top + cut, bottom: r.bottom - cut, width: r.width, height: r.height - 2 * cut};
    });
    if (rects.length) runs.push({el, rects});
  }

  const view = {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
  for (const run of runs) {
    let scrolled = false, boxed = false;
    for (let a = run.el; a && a !== document.documentElement; a = a.parentElement) {
      const cs = getComputedStyle(a);
      const ox = cs.overflowX, oy = cs.overflowY, cuts = ox !== "visible" || oy !== "visible";
      const box = cuts ? inner(a) : a.getBoundingClientRect();
      const worst = Math.max(...run.rects.map(r => over(r, cuts ? {
        left: ox === "visible" ? -1e9 : box.left, right: ox === "visible" ? 1e9 : box.right,
        top: oy === "visible" ? -1e9 : box.top, bottom: oy === "visible" ? 1e9 : box.bottom} : box)));
      if (cuts) {
        if (/auto|scroll/.test(ox + oy)) { scrolled = true; break; }
        if (worst > EPS) {
          const dots = cs.textOverflow === "ellipsis" || getComputedStyle(run.el).textOverflow === "ellipsis" || cs.webkitLineClamp !== "none";
          if (!dots) report("clipped", run.el, worst);
          else if (opt.ellipsis) report("ellipsis", run.el, worst);
          scrolled = true;
          break;
        }
      } else if (!boxed && cs.display !== "inline" && cs.display !== "contents") {
        // the box the words were laid out in, then each one around it up to the first that is painted
        if (worst > EPS) { report("spill", run.el, worst); boxed = true; }
        if (painted(cs)) boxed = true;
      }
      if (/absolute|fixed/.test(cs.position)) boxed = true;
    }
    if (!scrolled) {
      const out = Math.max(...run.rects.map(r => over(r, view)));
      if (out > EPS) report("offscreen", run.el, out);
    }
  }

  const kin = (a, b) => a === b || a.contains(b) || b.contains(a);
  const block = el => { while (el.parentElement && getComputedStyle(el).display === "inline") el = el.parentElement; return el; };
  for (const run of runs) run.block = block(run.el);
  for (let i = 0; i < runs.length; i++) for (let j = i + 1; j < runs.length; j++) {
    const a = runs[i], b = runs[j];
    if (kin(a.el, b.el)) continue;
    for (const p of a.rects) for (const q of b.rects) {
      const w = Math.min(p.right, q.right) - Math.max(p.left, q.left), h = Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top);
      if (h <= 0.4 * Math.min(p.height, q.height)) continue;
      if (w > 3) report("overlap", a.el, Math.min(w, h), b.el);
      else if (w > -GAP && a.block !== b.block) report("crowded", a.el, GAP + w, b.el);
    }
  }
  return found;
}

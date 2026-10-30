// The pieces two or more screens draw, one function each, taking plain data and giving back HTML; their
// styles are kit.css. A screen builds from these instead of writing its own copy.
"use strict";

const ico = (path, cls = "ico") => path ? `<span class="${cls} mask" style="--icon:url(/assets/icons/${path}.svg)"></span>` : "";
const money = n => "$" + Number(n).toLocaleString("en-US");
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const sign = n => n >= 0 ? "+" + n : "−" + (-n);
const kg = (q, w) => { const t = q * w; return t < 0.05 ? "—" : t.toFixed(1) + " kg"; };

// the attribute that gives an element the game's tooltip: `kind` "" is plain lines, "item" an item's name
// over its lines, "sum" a breakdown (a title, "label: value" rows, "= total")
const tip = (text, kind = "") => text ? ` data-tip${kind ? "-" + kind : ""}="${esc(text)}"` : "";

// a pointer event in the 1920x1080 screen's own pixels
function stagePoint(e) {
  const r = $("screen").getBoundingClientRect(), s = r.width / 1920;
  return [(e.clientX - r.left) / s, (e.clientY - r.top) / s];
}

// a popup menu opened at the pointer, kept on the screen
function popAt(m, e) {
  const [x, y] = stagePoint(e);
  m.hidden = false;
  m.style.left = Math.min(x, 1920 - m.offsetWidth - 12) + "px";
  m.style.top = Math.min(y, 1080 - m.offsetHeight - 12) + "px";
}

// the element a drag hovers lit as the drop target: one marker per screen, called with null to clear
function dropMarker() {
  let over = null;
  return el => {
    if (over === el) return;
    if (over) over.classList.remove("drop");
    over = el;
    if (over) over.classList.add("drop");
  };
}

const Kit = {
  // − n + : `n` in the middle, the screen reads `data-q` on a press
  stepper: n => `<div class="qty stepper"><span data-q="-1">−</span><span class="n">${n}</span><span data-q="1">+</span></div>`,

  // one item in a pack on leather: icon, name (after its worn slot's label), tags, quantity, weight;
  // an empty worn slot when `it` has no name
  item(owner, it, loc, slot, {sel = false, tags = ""} = {}) {
    if (!it || !it.name)
      return `<div class="it empty" data-owner="${owner}" data-zone="${slot.zone}">${ico("item/knapsack")}<div class="n"><span class="slotname">${esc(slot.label)}</span>empty</div><span></span><span></span></div>`;
    const q = it.qty || 1;
    return `<div class="it ${it.coin ? "coin" : ""} ${sel ? "sel" : ""}" data-owner="${owner}" data-loc="${loc}" ${slot ? `data-zone="${slot.zone}"` : ""}${tip(it.tip, "item")}>
      ${ico(it.glyph)}<div class="n">${slot ? `<span class="slotname">${esc(slot.label)}</span>` : ""}${esc(it.name)}${tags}</div>
      <span class="q">${q > 1 ? "×" + q : ""}</span><span class="kg">${kg(q, it.kg)}</span></div>`;
  },
  tag: (on, text, cls = "") => on ? `<span class="tag ${cls}">${text}</span>` : "",

  // one pack as a leather column (a shop's or a stash's shoppers): the portrait or the store's glyph, the
  // purse and the load (with `add` kg about to come in striped), the worn slots, the pack and a foot line;
  // `row(p, it, loc, slot)` draws each item
  column(p, {add = 0, foot = "", voice = "", row}) {
    const head = p.store ? `<div class="med store">${ico(p.glyph)}</div>`
      : `<div class="med ${p.hurt ? "hurt" : ""}" data-sheet="${p.id}"${tip(`Open ${p.name}'s sheet`)}>${face(p.portrait, p.name)}</div>`;
    const tight = p.kg > p.normal, over = p.kg + add > p.max;
    const pct = x => Math.min(100, x / p.max * 100).toFixed(1);
    const worn = p.worn.length ? `<div class="psec lbl">Worn</div>` + p.worn.map(w => row(p, w.name ? w : null, w.zone, w)).join("") : "";
    const rows = p.pack.length ? p.pack.map(r => row(p, r, r.loc, null)).join("")
      : `<div class="it empty"><span></span><div class="n">nothing carried</div><span></span><span></span></div>`;
    return `<div class="col pack" data-owner="${p.id}">
      <div class="chead">${head}<div style="min-width:0"><h3${tip(p.name)}>${esc(p.name)}</h3><div class="race">${esc(p.sub)}</div>${voice ? `<span class="voice">${esc(voice)}</span>` : ""}</div></div>
      <div class="cstat"><div class="money"><i class="coindot"></i>${p.money}</div>
        <div class="load ${over ? "over" : tight ? "tight" : ""}"><b>${(p.kg + add).toFixed(1)}</b> / ${p.max} kg</div></div>
      <div class="bar"><i class="${tight ? "tight" : ""}" style="width:${pct(p.kg)}%"></i>${add ? `<i class="add" style="width:${pct(add)}%"></i>` : ""}<em style="left:${pct(p.normal)}%"></em></div>
      ${worn}<div class="psec lbl">Pack</div><div class="packlist">${rows}</div>
      ${foot ? `<div class="cfoot">${foot}</div>` : ""}</div>`;
  },

  // the button that shares a band's load out by what each can carry; the screen answers `#spread`
  distribute: (cls = "ghost-btn") => `<div class="${cls}" id="spread"${tip("Share the load out by what each can carry")}>Distribute load</div>`,

  // the common purse across the bottom of a shop or a stash: the sum (and what it would be after `after`),
  // each holder's share, the Distribute button when `spread`, and Done
  purse({sum, after = null, bad = false, packs, spread = false}) {
    const shares = packs.filter(p => !p.store || p.money).map(p =>
      `<div class="share"><span>${esc(p.name.split(" ")[0])}</span><b>${p.money}</b></div>`).join("");
    return `<div class="leather" id="purse"><div><div class="lbl">Common purse</div>
      <div class="sum"><b>${money(sum)}</b>${after === null ? "" : `<s class="${bad ? "bad" : ""}">${money(after)}</s>`}</div></div>
      <div class="split">${shares}</div>${spread ? `<div class="tools">${Kit.distribute()}</div>` : ""}
      <div class="brass-btn" id="done"><div>${ico("gui/exit-door")}<b>Done</b></div></div></div>`;
  },
};

// the game's tooltip: a paper note that opens after a short rest on any element carrying a data-tip
// (see `tip`), on the whole element, inside the sheet's book too, and stays inside the window
const Tip = (() => {
  const SEL = "[data-tip],[data-tip-item],[data-tip-sum]";
  const DELAY = 380;
  let note = null, at = null, timer = 0, last = [0, 0];
  const line = l => {
    const m = /^([^:]{1,32}): (.+)$/.exec(l);
    return m ? `<p><b>${esc(m[1])}</b> ${esc(m[2])}</p>` : `<p>${esc(l)}</p>`;
  };
  function body(el) {
    const d = el.dataset;
    if (d.tipItem !== undefined) {
      const [head, ...rest] = d.tipItem.split("\n");
      return `<h4>${esc(head)}</h4>${rest.filter(Boolean).map(line).join("")}`;
    }
    if (d.tipSum !== undefined) {
      const [head, ...rest] = d.tipSum.split("\n");
      return `<h4>${esc(head)}</h4><div class="sum">${rest.map(l => {
        if (l.startsWith("= ")) return `<div class="tot"><span>Total</span><b>${esc(l.slice(2))}</b></div>`;
        const i = l.lastIndexOf(": ");
        return i < 0 ? `<div class="note">${esc(l)}</div>` : `<div><span>${esc(l.slice(0, i))}</span><b>${esc(l.slice(i + 2))}</b></div>`;
      }).join("")}</div>`;
    }
    return d.tip.split("\n").map(l => `<p>${esc(l)}</p>`).join("");
  }
  function hide() {
    clearTimeout(timer);
    at = null;
    if (note) note.hidden = true;
  }
  function show() {
    if (!at || !at.isConnected) return hide();
    const st = $("stage"), s = st.getBoundingClientRect().width / st.offsetWidth;
    note = note || st.appendChild(Object.assign(document.createElement("div"), {id: "tip", className: "paper"}));
    note.innerHTML = body(at);
    note.hidden = false;
    const [x, y] = [last[0] / s, last[1] / s], w = note.offsetWidth, h = note.offsetHeight;
    note.style.left = Math.max(8, x + 18 + w > st.offsetWidth - 8 ? x - w - 14 : x + 18) + "px";
    note.style.top = Math.max(8, y + 24 + h > st.offsetHeight - 8 ? y - h - 12 : y + 24) + "px";
  }
  addEventListener("pointermove", e => {
    last = [e.clientX, e.clientY];
    const el = e.buttons ? null : e.composedPath()[0]?.closest?.(SEL) || null;
    if (el === at) return;
    const open = note && !note.hidden;
    hide();
    if (!el) return;
    at = el;
    if (open) show();
    else timer = setTimeout(show, DELAY);
  }, true);
  for (const type of ["pointerdown", "wheel", "keydown"]) addEventListener(type, hide, true);
  document.documentElement.addEventListener("mouseleave", hide);
  return {hide};
})();

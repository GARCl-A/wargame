// A stash tab, the Bank's VAULT or the house's THE HOUSE: the stash on paper where the shop's shelf sits,
// one leather column per pack, the services under it (the Bankers', or the house's tax, oven and debt) and
// the common purse. Drag an item onto the chest to stow it,
// onto a pack or a worn slot to hand it over; a chest row's stepper takes part of the stack. A click
// picks, a second click on the chest or a pack drops; Shift picks several. Right-click an item for its
// menu (where to send it; at the bank, on a coin stack, mint or melt gold). The server does every move, as
// the pygame stash does it.
"use strict";

const Vault = (() => {
  let V = null, picks = null, drag = null, over = null;
  const take = {};
  let CHEST = null;
  const kg = (q, w) => { const t = q * w; return t < 0.05 ? "—" : t.toFixed(1) + " kg"; };
  const short = name => name.split(" ")[0];
  const pack = id => V.packs.find(p => p.id === id);
  const chestRow = loc => V.chest.rows.find(r => r.loc === loc);

  function item(owner, loc) {
    if (owner === CHEST) {
      const r = chestRow(loc);
      return r ? {from: CHEST, loc, name: r.name, qty: Math.min(r.qty, take[loc] || r.qty), kg: r.kg, glyph: r.glyph} : null;
    }
    const p = pack(owner);
    const it = typeof loc === "string" ? p.worn.find(w => w.zone === loc) : p.pack.find(r => r.loc === loc);
    return it && it.name ? {from: owner, loc, name: it.name, qty: it.qty || 1, kg: it.kg, glyph: it.glyph} : null;
  }
  const same = (a, b) => a.from === b.from && a.loc === b.loc;
  const picked = (owner, loc) => picks && picks.some(p => p.from === owner && p.loc === loc);
  const weight = list => list.reduce((a, p) => a + p.kg * p.qty, 0);

  // ---------------------------------------------------------------- the strongbox
  function chestLine(r) {
    const q = Math.min(r.qty, take[r.loc] || r.qty);
    const step = r.qty > 1
      ? `<div class="qty"><span data-q="-1">−</span><span class="n">${q}</span><span data-q="1">+</span></div>` : "<span></span>";
    return `<div class="row ${picked(CHEST, r.loc) ? "picked" : ""}" data-owner="${CHEST}" data-loc="${r.loc}" title="${esc(r.tip)}">
      <div class="ico mask" style="--icon:url(/assets/icons/${r.glyph}.svg)"></div>
      <div style="min-width:0"><div class="nm">${esc(r.name)}</div><div class="use">${esc(kg(r.qty, r.kg))} in all</div></div>
      <div class="wt r">${r.kg.toFixed(r.kg < 0.1 ? 3 : 1)} <small>kg</small></div>
      <div class="stk c">×${r.qty}</div><span></span>${step}</div>`;
  }

  function chest() {
    const c = V.chest;
    if (!c.open)
      return `<div class="paper" id="shelf"><div class="kicker">${esc(c.title)} <em>${esc(c.where)}</em></div>
        <div class="shelfhead"><h3>${esc(c.closed)}</h3></div>
        <p class="vaultnote">${esc(c.closed_line)}</p></div>`;
    const pct = Math.min(100, c.load / c.capacity * 100).toFixed(1);
    const add = picks ? weight(picks.filter(p => p.from !== CHEST)) : 0;
    const rows = c.rows.length ? c.rows.map(chestLine).join("") : `<p class="vaultnote">${esc(c.title)} is empty. Drag what the band can spare onto it.</p>`;
    return `<div class="paper" id="shelf"><div class="kicker">${esc(c.title)} <em>${c.rows.length} stacks · ${esc(c.where)}</em></div>
      <div class="shelfhead"><h3>${c.load.toFixed(1)} / ${c.capacity} kg</h3><div class="chestbar"><i style="width:${pct}%"></i>${add ? `<i class="add ${c.load + add > c.capacity ? "over" : ""}" style="width:${Math.min(100 - pct, add / c.capacity * 100).toFixed(1)}%"></i>` : ""}</div></div>
      <div class="cols"><span></span><span>Stack</span><span class="r">Each</span><span class="c">Held</span><span></span><span class="r">Take</span></div>
      <div id="rows">${rows}</div>
      <div class="shelffoot"><b>Drag</b> an item here to stow it · out of it onto a pack or a worn slot${V.gold ? " · <b>right-click</b> a coin stack to mint or melt gold" : ""}</div></div>`;
  }

  // ---------------------------------------------------------------- the packs
  function itemRow(p, it, loc, slot) {
    if (!it || !it.name)
      return `<div class="it empty" data-owner="${p.id}" data-zone="${slot.zone}">${ico("item/knapsack")}<div class="n"><span class="slotname">${esc(slot.label)}</span>empty</div><span></span><span></span></div>`;
    const zone = slot ? `data-zone="${slot.zone}"` : "";
    return `<div class="it ${it.coin ? "coin" : ""} ${picked(p.id, loc) ? "sel" : ""}" data-owner="${p.id}" data-loc="${loc}" ${zone} title="${esc(it.tip || "")}">
      ${ico(it.glyph)}<div class="n">${slot ? `<span class="slotname">${esc(slot.label)}</span>` : ""}${esc(it.name)}</div>
      <span class="q">${(it.qty || 1) > 1 ? "×" + it.qty : ""}</span><span class="kg">${kg(it.qty || 1, it.kg)}</span></div>`;
  }

  function foot(p) {
    const mine = picks ? picks.filter(x => x.from === p.id) : [];
    if (mine.length) return `${mine.length === 1 ? esc(mine[0].name) : mine.length + " items"} picked · drag onto ${esc(V.chest.label)} or another pack`;
    if (picks) {
      const after = p.kg + weight(picks);
      return `Click here to hand the pick to ${esc(short(p.name))}${after > p.max ? " · <b>won't fit</b>" : ""}`;
    }
    if (p.kg > p.normal) return `Burdened: <b>${(p.kg - p.normal).toFixed(1)} kg</b> past the easy load`;
    return "";
  }

  function column(p) {
    const head = p.store
      ? `<div class="med store">${ico(p.glyph)}</div>`
      : `<div class="med ${p.hurt ? "hurt" : ""}">${face(p.portrait, p.name)}</div>`;
    const tight = p.kg > p.normal, pct = x => Math.min(100, x / p.max * 100).toFixed(1);
    const worn = p.worn.length ? `<div class="sec lbl">Worn</div>` + p.worn.map(w => itemRow(p, w.name ? w : null, w.zone, w)).join("") : "";
    const rows = p.pack.length ? p.pack.map(r => itemRow(p, r, r.loc, null)).join("")
      : `<div class="it empty"><span></span><div class="n">nothing carried</div><span></span><span></span></div>`;
    const f = foot(p);
    return `<div class="col" data-owner="${p.id}">
      <div class="chead">${head}<div style="min-width:0"><h3>${esc(p.name)}</h3><div class="race">${esc(p.sub)}</div></div></div>
      <div class="cstat"><div class="money"><i class="coindot"></i>${p.money}</div>
        <div class="load ${p.kg > p.max ? "over" : tight ? "tight" : ""}"><b>${p.kg.toFixed(1)}</b> / ${p.max} kg</div></div>
      <div class="bar"><i class="${tight ? "tight" : ""}" style="width:${pct(p.kg)}%"></i><em style="left:${pct(p.normal)}%"></em></div>
      ${worn}<div class="sec lbl">Pack</div><div class="packlist">${rows}</div>
      ${f ? `<div class="cfoot">${f}</div>` : ""}</div>`;
  }

  // ---------------------------------------------------------------- the bottom
  function services() {
    const g = V.gold;
    if (!V.services.length && !g)
      return `<div class="leather" id="sell">${ico("item/locked-chest")}<div><h4>${esc(V.chest.title)}</h4>
        <p>Nothing owed and nothing to buy: what is stowed here stays in the City for any band that comes by.</p></div></div>`;
    if (!V.services.length)
      return `<div class="leather" id="sell">${ico("item/two-coins")}<div><h4>The exchange</h4>
        <p>Right-click a coin stack to mint gold (<b>$${g.price}</b> a coin) or melt it (<b>$${g.payout}</b> back): the Bankers keep $${g.fee} a coin each way.</p></div></div>`;
    return `<div class="leather svcs" id="sell"><div class="svclist">${V.services.map(s =>
      `<div class="svc ${s.on ? "" : "off"}" data-svc="${s.key}"><div><h4>${esc(s.label.toLowerCase())}</h4><p>${esc(s.sub)}</p></div>
        <div class="ghost-btn">${s.on ? "Agree" : "Not yet"}</div></div>`).join("")}</div></div>`;
  }

  function purse() {
    const shares = V.packs.filter(p => !p.store || p.money).map(p =>
      `<div class="share"><span>${esc(short(p.name))}</span><b>${p.money}</b></div>`).join("");
    const tools = V.distribute && V.packs.length > 1 ? `<div class="tools"><div class="ghost-btn" id="spread" title="Share the load out by what each can carry">Distribute load</div></div>` : "";
    return `<div class="leather" id="purse"><div><div class="lbl">Common purse</div>
      <div class="sum"><b>${money(V.purse)}</b></div></div>
      <div class="split">${shares}</div>${tools}
      <div class="brass-btn" id="done"><div>${ico("gui/exit-door")}<b>Done</b></div></div></div>`;
  }

  // ---------------------------------------------------------------- drawing
  function draw(st) {
    V = st;
    CHEST = V.chest.owner;
    const keep = {rows: $("rows") ? $("rows").scrollTop : 0, band: $("band") ? $("band").scrollLeft : 0, lists: {}};
    document.querySelectorAll(".col").forEach(c => { keep.lists[c.dataset.owner] = c.querySelector(".packlist").scrollTop; });
    cards(V.cards);
    $("body").innerHTML = chest() + `<div id="band">${V.packs.map(column).join("")}</div>` + services() + purse();
    if ($("rows")) $("rows").scrollTop = keep.rows;
    $("band").scrollLeft = keep.band;
    document.querySelectorAll(".col").forEach(c => { c.querySelector(".packlist").scrollTop = keep.lists[c.dataset.owner] || 0; });
    toast(V.notice);
  }
  const redraw = () => draw(V);

  async function act(verb, body) {
    const before = V.purse;
    picks = null;
    for (const k in take) delete take[k];
    const r = await post(verb, body);
    if (r && r.vault) Sound.play(r.vault.purse !== before ? "coins" : "click");
  }

  // ---------------------------------------------------------------- what the person does
  const wire = list => list.map(({from, loc, qty}) => ({from, loc, qty}));

  function drop(el, it) {
    if (!el) return;
    const list = picks && picks.some(p => same(p, it)) ? picks : [it];
    if (el.closest("#shelf")) {
      if (list.every(x => x.from === CHEST)) return;
      return act("vault_move", {picks: wire(list.filter(x => x.from !== CHEST)), to: CHEST});
    }
    const col = el.closest(".col");
    if (!col) return;
    const slot = el.closest(".it[data-zone]"), p = pack(col.dataset.owner);
    const zone = slot && !p.store ? slot.dataset.zone : "pack";
    if (zone === "pack" && list.every(x => x.from === col.dataset.owner && typeof x.loc === "number")) return;
    act("vault_move", {picks: wire(list), to: col.dataset.owner, zone});
  }

  function source(el) {
    if (el.closest(".qty")) return null;
    const it = el.closest("[data-loc]");
    if (!it) return null;
    const loc = /^\d+$/.test(it.dataset.loc) ? Number(it.dataset.loc) : it.dataset.loc;
    return item(it.dataset.owner, loc);
  }

  function click(el, e) {
    const it = source(el);
    if (it) {
      const list = picks || [];
      if (e.shiftKey) {
        const rest = list.filter(p => !same(p, it));
        picks = rest.length === list.length ? [...list, it] : rest.length ? rest : null;
        return redraw();
      }
      if (list.length && !list.some(p => p.from === it.from)) return drop(el, list[0]);
      picks = list.length === 1 && same(list[0], it) ? null : [it];
      return redraw();
    }
    if (picks && (el.closest(".col") || el.closest("#shelf"))) return drop(el, picks[0]);
    if (picks && !el.closest("#menu")) { picks = null; redraw(); }
  }

  function ghost(it) {
    const list = picks && picks.some(p => same(p, it)) ? picks : [it];
    const name = list.length > 1 ? `${list.length} items` : it.qty > 1 ? `${it.name} ×${it.qty}` : it.name;
    $("ghost").innerHTML = `${ico(list[0].glyph)}<div><b>${esc(name)}</b><span>${esc(kg(1, weight(list)))}</span></div>`;
  }

  function stagePoint(e) {
    const r = $("screen").getBoundingClientRect(), s = r.width / 1920;
    return [(e.clientX - r.left) / s, (e.clientY - r.top) / s];
  }

  const target = el => el && (el.closest(".it[data-zone]") || el.closest(".col") || (V.chest.open && el.closest("#shelf")));

  function mark(el) {
    if (over === el) return;
    if (over) over.classList.remove("drop");
    over = el;
    if (over) over.classList.add("drop");
  }

  // ---------------------------------------------------------------- the item menu
  function menu(e, it) {
    const m = $("menu");
    const row = it.from === CHEST ? chestRow(it.loc) : typeof it.loc === "number" ? pack(it.from).pack.find(r => r.loc === it.loc) : null;
    const rows = [], acts = [];
    const add = (html, fn) => { rows.push(html); acts.push(fn); };
    const gold = (n, melt) => () => act("vault_gold", {from: it.from, n, melt});
    if (row && row.mint) {
      add(`Mint 1 gold coin <b>−${money(V.gold.price)}</b>`, gold(1, false));
      if (row.mint > 1) add(`Mint ${row.mint} gold coins <b>−${money(V.gold.price * row.mint)}</b>`, gold(row.mint, false));
    }
    if (row && row.melt) {
      add(`Melt 1 gold coin <b>+${money(V.gold.payout)}</b>`, gold(1, true));
      if (row.melt > 1) add(`Melt ${row.melt} gold coins <b>+${money(V.gold.payout * row.melt)}</b>`, gold(row.melt, true));
    }
    let html = rows.map((r, i) => `<div data-i="${i}">${r}</div>`).join("");
    if (rows.length) html += "<hr>";
    const send = (to, q) => () => act("vault_move", {picks: [{from: it.from, loc: it.loc, ...(q ? {qty: q} : {qty: it.qty})}], to});
    const dests = [...(it.from !== CHEST && V.chest.open ? [{id: CHEST, name: V.chest.label}] : []),
      ...V.packs.filter(p => p.id !== it.from || typeof it.loc === "string")];
    html += dests.map(o => {
      const all = acts.push(send(o.id)) - 1, one = it.qty > 1 ? acts.push(send(o.id, 1)) - 1 : null;
      return `<div class="give"><span>To ${esc(o.id === CHEST ? o.name : short(o.name))}</span>${one === null ? "" : `<em data-i="${one}">1</em>`}<em data-i="${all}">${it.qty > 1 ? "all" : "give"}</em></div>`;
    }).join("");
    m.innerHTML = html;
    m.onclick = ev => {
      const d = ev.target.closest("[data-i]");
      if (!d) return;
      m.hidden = true;
      acts[Number(d.dataset.i)]();
    };
    const [x, y] = stagePoint(e);
    m.hidden = false;
    m.style.left = Math.min(x, 1920 - m.offsetWidth - 12) + "px";
    m.style.top = Math.min(y, 1080 - m.offsetHeight - 12) + "px";
  }

  // ---------------------------------------------------------------- the pointer
  const live = () => V && H && H.vault;
  const body = $("body");
  body.addEventListener("pointerdown", e => {
    if (e.button !== 0 || !live()) return;
    $("menu").hidden = true;
    const q = e.target.closest(".qty [data-q]");
    if (q) {
      const loc = Number(q.closest(".row").dataset.loc), r = chestRow(loc);
      const step = Number(q.dataset.q) * (e.shiftKey ? 5 : 1);
      take[loc] = Math.max(1, Math.min(r.qty, (take[loc] || r.qty) + step));
      if (picks) picks = picks.map(p => p.from === CHEST && p.loc === loc ? item(CHEST, loc) : p);
      return redraw();
    }
    drag = {src: source(e.target), x: e.clientX, y: e.clientY, moving: false};
  });
  addEventListener("pointermove", e => {
    if (!drag || !drag.src || !live()) return;
    if (!drag.moving && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 6) return;
    if (!drag.moving) { drag.moving = true; ghost(drag.src); $("ghost").hidden = false; }
    const [x, y] = stagePoint(e), g = $("ghost");
    g.style.left = x + "px";
    g.style.top = y + "px";
    mark(target(document.elementFromPoint(e.clientX, e.clientY)));
  });
  addEventListener("pointerup", e => {
    if (!drag || !live()) return;
    const d = drag;
    drag = null;
    $("ghost").hidden = true;
    mark(null);
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (d.moving) drop(el, d.src);
    else if (el && el.closest("#body")) click(el, e);
  });
  body.addEventListener("click", e => {
    if (!live()) return;
    const s = e.target.closest(".svc:not(.off)");
    if (s) act("vault_service", {key: s.dataset.svc});
    else if (e.target.closest("#done")) back();
    else if (e.target.closest("#spread")) act("vault_distribute", {});
  });
  body.addEventListener("contextmenu", e => {
    if (!live()) return;
    e.preventDefault();
    const it = source(e.target);
    if (it) menu(e, it);
  });

  function escape() {
    if (!$("menu").hidden) { $("menu").hidden = true; return true; }
    if (picks) { picks = null; redraw(); return true; }
    return false;
  }

  return {draw, escape};
})();

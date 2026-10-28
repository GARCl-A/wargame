// The shop tab: the shelf on paper, one leather column per pack, the sell plate and the common purse.
// Drag a ware onto a pack to buy it there (onto a worn slot to wear it, onto the purse to share it out
// by room); drag a pack item onto another pack or slot to hand it over, onto the shelf or Sell to sell
// it. A click picks, a second click on a pack drops; Shift picks several. Right-click an item for its
// menu. The server does every trade (`trade.Counter`).
"use strict";

const Shop = (() => {
  let S = null, cat = null, picks = null, drag = null, over = null;
  const qty = {};
  const kg = (q, w) => { const t = q * w; return t < 0.05 ? "—" : t.toFixed(1) + " kg"; };
  const allRows = () => S.shelf.flatMap(c => c.rows);
  const ware = name => allRows().find(r => r.name === name);
  const pack = id => S.packs.find(p => p.id === id);
  const short = name => name.split(" ")[0];

  function item(owner, loc) {
    const p = pack(owner);
    const it = typeof loc === "string" ? p.worn.find(w => w.zone === loc) : p.pack.find(r => r.loc === loc);
    return it && it.name ? {from: owner, loc, name: it.name, qty: it.qty || 1, sell: it.sell, kg: it.kg, glyph: it.glyph} : null;
  }
  const same = (a, b) => a.from === b.from && a.loc === b.loc;
  const picked = (owner, loc) => picks && picks.items && picks.items.some(p => p.from === owner && p.loc === loc);
  const sellTotal = list => list.reduce((a, p) => a + (p.sell || 0) * p.qty, 0);

  // ---------------------------------------------------------------- the keeper's cards
  function cards() {
    const d = S.deal, v = d.voice;
    const who = v ? `<div class="vm">${face(v.portrait, v.name)}</div>` : "";
    const line = v ? `<p><b>${esc(v.name)}</b> speaks for the band</p>` : `<p>${esc(d.headline.charAt(0).toUpperCase() + d.headline.slice(1))}</p>`;
    const marks = d.marks.map(m => `<span class="mark ${m.good ? "good" : "bad"}">${esc(m.text)}</span>`).join("");
    const till = S.till === null ? "" : `<div class="vsep"></div><div class="till">
      <div class="stack"><i style="top:29px"></i><i style="top:21px"></i><i style="top:13px"></i><i style="top:5px"></i></div>
      <div><div class="lbl">In the till</div><b>${money(S.till)}</b><small>refills at dawn; a sale above it is refused</small></div></div>`;
    $("cards").innerHTML = `<div class="vsep"></div><div class="deal">${who}<div><div class="lbl">The deal</div>${line}<div class="marks">${marks}</div></div></div>
      <div class="rate"><b>${d.pay}%</b><span class="lbl">You pay</span></div>
      <div class="rate"><b>${d.get}%</b><span class="lbl">They pay</span></div>${till}`;
  }

  // ---------------------------------------------------------------- the shelf
  function wareRow(r) {
    const out = r.stock !== null && r.stock <= 0, q = qty[r.name] || 1;
    const sel = picks && picks.ware === r.name;
    const pips = r.target && r.target <= 8
      ? `<div class="pips">${Array.from({length: r.target}, (_, k) => `<i class="${k < r.stock ? "" : "off"}"></i>`).join("")}</div>` : "";
    const stock = r.stock === null ? "—" : `${r.stock}${r.target ? ` <small>/ ${r.target}</small>` : ""}`;
    const tone = r.price < r.list ? "off" : r.price > r.list ? "up" : "";
    const buy = out ? `<div class="soldout">Sold out</div>`
      : `<div class="qty"><span data-q="-1">−</span><span class="n">${q}</span><span data-q="1">+</span></div>`;
    return `<div class="row ${out ? "out" : ""} ${sel ? "picked" : ""}" data-ware="${esc(r.name)}" title="${esc(r.tip)}">
      <div class="ico mask" style="--icon:url(/assets/icons/${r.glyph}.svg)"></div>
      <div style="min-width:0"><div class="nm">${esc(r.name)}</div><div class="use">${esc(r.use)}</div></div>
      <div class="wt r">${r.weight.toFixed(1)} <small>kg</small></div>
      <div class="stk c">${stock}${pips}</div>
      <div class="price r ${tone}">${r.price}</div>${buy}</div>`;
  }

  function shelf() {
    const c = S.shelf.find(x => x.key === cat) || S.shelf[0];
    const tabs = S.shelf.length > 1
      ? `<div class="cats">${S.shelf.map(x => `<span class="${x.key === c.key ? "on" : ""}" data-cat="${x.key}">${esc(x.label)}</span>`).join("")}</div>` : "";
    return `<div class="paper" id="shelf"><div class="kicker">The shelf <em>${allRows().length} wares · restocked each day</em></div>
      <div class="shelfhead"><h3>${esc(c ? c.label : "Nothing for sale")}</h3>${tabs}</div>
      <div class="cols"><span></span><span>Ware</span><span class="r">Weight</span><span class="c">Stock</span><span class="r">Price</span><span class="r">Buy</span></div>
      <div id="rows">${c ? c.rows.map(wareRow).join("") : ""}</div>
      <div class="shelffoot"><b>Drag</b> a ware onto a shopper to buy it · onto the <b>purse</b> to share it out by room · <b>Shift</b> picks several</div></div>`;
  }

  // ---------------------------------------------------------------- the packs
  function itemRow(p, it, loc, slot) {
    if (!it || !it.name)
      return `<div class="it empty" data-owner="${p.id}" data-zone="${slot.zone}">${ico("item/knapsack")}<div class="n"><span class="slotname">${esc(slot.label)}</span>empty</div><span></span><span></span></div>`;
    const zone = slot ? `data-zone="${slot.zone}"` : "";
    const tags = (it.locked ? `<span class="tag">locked</span>` : "") + (it.marked ? `<span class="tag auto">auto-sell</span>` : "");
    return `<div class="it ${it.coin ? "coin" : ""} ${picked(p.id, loc) ? "sel" : ""}" data-owner="${p.id}" data-loc="${loc}" ${zone} title="${esc(it.tip || "")}">
      ${ico(it.glyph)}<div class="n">${slot ? `<span class="slotname">${esc(slot.label)}</span>` : ""}${esc(it.name)}${tags}</div>
      <span class="q">${(it.qty || 1) > 1 ? "×" + it.qty : ""}</span><span class="kg">${kg(it.qty || 1, it.kg)}</span></div>`;
  }

  function foot(p) {
    if (picks && picks.ware) {
      const r = ware(picks.ware), q = qty[r.name] || 1, after = p.kg + r.weight * q;
      const tail = after > p.max ? ` · <b>won't fit</b>` : after > p.normal ? ` · burdened past ${p.normal} kg` : "";
      return `Buy ${q > 1 ? q + " " : ""}${esc(r.name)} here · <b>${money(r.price * q)}</b> from the purse, <b>${(r.weight * q).toFixed(1)} kg</b>${tail}`;
    }
    const mine = picks && picks.items ? picks.items.filter(x => x.from === p.id) : [];
    if (mine.length) return `${mine.length === 1 ? esc(mine[0].name) : mine.length + " items"} picked · drag to another pack or onto <b>Sell</b>`;
    if (picks && picks.items) return `Click here to hand the pick to ${esc(short(p.name))}`;
    if (p.kg > p.normal) return `Burdened: <b>${(p.kg - p.normal).toFixed(1)} kg</b> past the easy load`;
    if (p.max - p.kg < 2) return `Near the limit: <b>${(p.max - p.kg).toFixed(1)} kg</b> left`;
    return "";
  }

  function column(p) {
    const head = p.store
      ? `<div class="med store">${ico(p.glyph)}</div>`
      : `<div class="med ${p.hurt ? "hurt" : ""}">${face(p.portrait, p.name)}</div>`;
    let add = 0;
    if (picks && picks.ware) add = ware(picks.ware).weight * (qty[picks.ware] || 1);
    const tight = p.kg > p.normal, over = p.kg + add > p.max;
    const pct = x => Math.min(100, x / p.max * 100).toFixed(1);
    const worn = p.worn.length ? `<div class="sec lbl">Worn</div>` + p.worn.map(w => itemRow(p, w.name ? w : null, w.zone, w)).join("") : "";
    const rows = p.pack.length ? p.pack.map(r => itemRow(p, r, r.loc, null)).join("")
      : `<div class="it empty"><span></span><div class="n">nothing carried</div><span></span><span></span></div>`;
    const f = foot(p);
    return `<div class="col" data-owner="${p.id}">
      <div class="chead">${head}<div style="min-width:0"><h3>${esc(p.name)}</h3><div class="race">${esc(p.sub)}</div>${p.voice ? `<span class="voice">Speaks for the band</span>` : ""}</div></div>
      <div class="cstat"><div class="money"><i class="coindot"></i>${p.money}</div>
        <div class="load ${over ? "over" : tight ? "tight" : ""}"><b>${(p.kg + add).toFixed(1)}</b> / ${p.max} kg</div></div>
      <div class="bar"><i class="${tight ? "tight" : ""}" style="width:${pct(p.kg)}%"></i>${add ? `<i class="add" style="width:${pct(add)}%"></i>` : ""}<em style="left:${pct(p.normal)}%"></em></div>
      ${worn}<div class="sec lbl">Pack</div><div class="packlist">${rows}</div>
      ${f ? `<div class="cfoot">${f}</div>` : ""}</div>`;
  }

  // ---------------------------------------------------------------- the bottom
  function sellPlate() {
    const goods = picks && picks.items ? picks.items.filter(p => p.sell) : [];
    let line, ready = false;
    if (goods.length) {
      const what = goods.length === 1 ? `${goods[0].qty > 1 ? goods[0].qty + " " : ""}${goods[0].name}` : `${goods.length} stacks`;
      line = `Sell ${esc(what)} for <b>${money(sellTotal(goods))}</b>: click here, or drop them here.`;
      ready = true;
    } else if (S.marked.length) {
      const names = S.marked.length > 4 ? `${S.marked.slice(0, 4).join(", ")} and ${S.marked.length - 4} more` : S.marked.join(", ");
      line = `Auto-sell: ${esc(names)}. ${S.marked_total ? `Click to sell them all for <b>${money(S.marked_total)}</b>.` : "None in the packs."}`;
      ready = S.marked_total > 0;
    } else {
      line = `Drop an item from any pack here. ${esc(H.keeper.name || "The shop")} pays ${S.deal.get}% of the price.`;
    }
    return `<div class="leather ${ready ? "ready" : ""}" id="sell">${ico("action/trade")}<div><h4>Sell</h4><p>${line}</p></div></div>`;
  }

  function purse() {
    let after = null, bad = false;
    if (picks && picks.ware) {
      const r = ware(picks.ware);
      after = S.purse - r.price * (qty[r.name] || 1);
      bad = after < 0;
    } else if (picks && picks.items) {
      const t = sellTotal(picks.items);
      if (t) after = S.purse + t;
    }
    const shares = S.packs.filter(p => !p.store || p.money).map(p =>
      `<div class="share"><span>${esc(short(p.name))}</span><b>${p.money}</b></div>`).join("");
    const members = S.packs.filter(p => !p.store).length;
    const tools = members > 1 ? `<div class="tools"><div class="ghost-btn" id="spread" title="Share the load out by what each can carry">Distribute load</div></div>` : "";
    return `<div class="leather" id="purse"><div><div class="lbl">Common purse</div>
      <div class="sum"><b>${money(S.purse)}</b>${after === null ? "" : `<s class="${bad ? "bad" : ""}">${money(after)}</s>`}</div></div>
      <div class="split">${shares}</div>${tools}
      <div class="brass-btn" id="done"><div>${ico("gui/exit-door")}<b>Done</b></div></div></div>`;
  }

  // ---------------------------------------------------------------- drawing
  function draw(st) {
    S = st;
    if (!S.shelf.some(c => c.key === cat)) cat = S.shelf.length ? S.shelf[0].key : null;
    const keep = {rows: $("rows") ? $("rows").scrollTop : 0, band: $("band") ? $("band").scrollLeft : 0, lists: {}};
    document.querySelectorAll(".col").forEach(c => { keep.lists[c.dataset.owner] = c.querySelector(".packlist").scrollTop; });
    cards();
    $("body").innerHTML = shelf() + `<div id="band">${S.packs.map(column).join("")}</div>` + sellPlate() + purse();
    $("rows").scrollTop = keep.rows;
    $("band").scrollLeft = keep.band;
    document.querySelectorAll(".col").forEach(c => { c.querySelector(".packlist").scrollTop = keep.lists[c.dataset.owner] || 0; });
    toast(S.notice);
  }
  const redraw = () => draw(S);

  async function act(verb, body) {
    const before = S.purse;
    picks = null;
    const r = await post(verb, body);
    if (r && r.shop) Sound.play(r.shop.purse !== before ? "coins" : "click");
  }

  // ---------------------------------------------------------------- what the person does
  function buy(name, to, zone) {
    act("buy", {name, qty: qty[name] || 1, to: to ?? null, zone: zone || "pack"});
  }

  function drop(el, src) {
    if (!el) return;
    if (src.ware) {
      const col = el.closest(".col");
      if (col) {
        const slot = el.closest(".it[data-zone]"), p = pack(col.dataset.owner);
        buy(src.ware, col.dataset.owner, slot && !p.store ? slot.dataset.zone : "pack");
      } else if (el.closest("#purse")) buy(src.ware, null);
      return;
    }
    const list = picks && picks.items && picks.items.some(p => same(p, src.item)) ? picks.items : [src.item];
    if (el.closest("#sell") || el.closest("#shelf")) {
      if (list.some(p => p.sell)) act("sell", {picks: list.map(({from, loc, qty: q}) => ({from, loc, qty: q}))});
      else toast("the shop does not buy coin");
      return;
    }
    const col = el.closest(".col");
    if (!col) return;
    const slot = el.closest(".it[data-zone]"), p = pack(col.dataset.owner);
    const zone = slot && !p.store ? slot.dataset.zone : "pack";
    if (zone === "pack" && list.every(x => x.from === col.dataset.owner && typeof x.loc === "number")) return;
    act("move", {picks: list.map(({from, loc, qty: q}) => ({from, loc, qty: q})), to: col.dataset.owner, zone});
  }

  function source(el) {
    if (el.closest(".qty") || el.closest(".cats")) return null;
    const w = el.closest(".row[data-ware]");
    if (w) return w.classList.contains("out") ? null : {ware: w.dataset.ware};
    const it = el.closest(".it[data-loc]");
    if (!it) return null;
    const loc = /^\d+$/.test(it.dataset.loc) ? Number(it.dataset.loc) : it.dataset.loc;
    const found = item(it.dataset.owner, loc);
    return found ? {item: found} : null;
  }

  function click(el, e) {
    const src = source(el);
    if (src && src.ware) {
      picks = picks && picks.ware === src.ware ? null : {ware: src.ware};
      return redraw();
    }
    if (src && src.item) {
      const it = src.item, list = picks && picks.items ? picks.items : [];
      if (e.shiftKey) {
        const rest = list.filter(p => !same(p, it));
        picks = rest.length === list.length ? {items: [...list, it]} : rest.length ? {items: rest} : null;
        return redraw();
      }
      if (picks && picks.ware) return drop(el, {ware: picks.ware});
      if (list.length && !list.some(p => p.from === it.from)) return drop(el, {item: list[0]});
      picks = list.length === 1 && same(list[0], it) ? null : {items: [it]};
      return redraw();
    }
    if (el.closest("#sell")) {
      if (picks && picks.items) return drop(el, {item: picks.items[0]});
      if (S.marked_total) act("sell_marked", {});
      return;
    }
    if (picks && (el.closest(".col") || (picks.ware && el.closest("#purse"))))
      return drop(el, picks.ware ? {ware: picks.ware} : {item: picks.items[0]});
    if (picks && !el.closest("#menu")) { picks = null; redraw(); }
  }

  // the slip that follows the pointer while a ware or an item is dragged
  function ghost(src) {
    let glyph, name, line, tag, gain = false;
    if (src.ware) {
      const r = ware(src.ware), q = qty[r.name] || 1;
      [glyph, name, line, tag] = [r.glyph, q > 1 ? `${r.name} ×${q}` : r.name, `${r.use} · ${(r.weight * q).toFixed(1)} kg`, money(r.price * q)];
    } else {
      const list = picks && picks.items && picks.items.some(p => same(p, src.item)) ? picks.items : [src.item];
      const it = list[0], t = sellTotal(list);
      [glyph, name, line] = [it.glyph, list.length > 1 ? `${list.length} items` : it.qty > 1 ? `${it.name} ×${it.qty}` : it.name, kg(it.qty, it.kg)];
      tag = t ? "+" + money(t) : "";
      gain = true;
    }
    $("ghost").innerHTML = `${ico(glyph)}<div><b>${esc(name)}</b><span>${esc(line)}</span></div>${tag ? `<em class="${gain ? "gain" : ""}">${tag}</em>` : ""}`;
  }

  function stagePoint(e) {
    const r = $("screen").getBoundingClientRect(), s = r.width / 1920;
    return [(e.clientX - r.left) / s, (e.clientY - r.top) / s];
  }

  function target(el) {
    if (!el) return null;
    if (drag.src.ware) return el.closest(".it[data-zone]") || el.closest(".col") || el.closest("#purse");
    return el.closest(".it[data-zone]") || el.closest(".col") || el.closest("#sell") || el.closest("#shelf");
  }

  function mark(el) {
    if (over === el) return;
    if (over) over.classList.remove("drop");
    over = el;
    if (over) over.classList.add("drop");
  }

  // ---------------------------------------------------------------- the item menu
  function menu(e, it) {
    const m = $("menu"), others = S.packs.filter(p => p.id !== it.from);
    const p = pack(it.from), row = typeof it.loc === "number" ? p.pack.find(r => r.loc === it.loc) : null;
    const rows = [];
    if (it.sell) {
      if (it.qty > 1) rows.push([`Sell 1 <b>+${money(it.sell)}</b>`, () => act("sell", {picks: [{from: it.from, loc: it.loc, qty: 1}]})]);
      rows.push([`Sell ${it.qty > 1 ? "all ×" + it.qty : ""} <b>+${money(it.sell * it.qty)}</b>`, () => act("sell", {picks: [{from: it.from, loc: it.loc}]})]);
    }
    if (row) {
      rows.push([row.locked ? "Unlock" : "Lock (never sold or shared out)", () => act("lock", {owner: it.from, name: it.name})]);
      if (!row.coin) rows.push([row.marked ? "Unmark auto-sell" : "Mark to auto-sell", () => act("mark", {name: it.name})]);
    }
    if (rows.length && others.length) rows.push(null);
    const give = (o, q) => () => act("move", {picks: [{from: it.from, loc: it.loc, ...(q ? {qty: q} : {})}], to: o.id});
    let html = rows.map((r, i) => r ? `<div data-i="${i}">${r[0]}</div>` : "<hr>").join("");
    const acts = rows.map(r => r && r[1]);
    html += others.map(o => {
      const all = acts.push(give(o)) - 1, one = it.qty > 1 ? acts.push(give(o, 1)) - 1 : null;
      return `<div class="give"><span>To ${esc(short(o.name))}</span>${one === null ? "" : `<em data-i="${one}">1</em>`}<em data-i="${all}">${it.qty > 1 ? "all" : "give"}</em></div>`;
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
  const body = $("body");
  body.addEventListener("pointerdown", e => {
    if (e.button !== 0 || !S || !H.shop) return;
    $("menu").hidden = true;
    const q = e.target.closest(".qty [data-q]");
    if (q) {
      const name = q.closest(".row").dataset.ware, r = ware(name);
      const step = Number(q.dataset.q) * (e.shiftKey ? 5 : 1);
      const cap = r.stock === null ? 99 : r.stock;
      qty[name] = Math.max(1, Math.min(cap, (qty[name] || 1) + step));
      return redraw();
    }
    const c = e.target.closest(".cats [data-cat]");
    if (c) { cat = c.dataset.cat; Sound.play("click"); return redraw(); }
    drag = {src: source(e.target), x: e.clientX, y: e.clientY, moving: false};
  });
  addEventListener("pointermove", e => {
    if (!drag || !drag.src) return;
    if (!drag.moving && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 6) return;
    if (!drag.moving) { drag.moving = true; ghost(drag.src); $("ghost").hidden = false; }
    const [x, y] = stagePoint(e), g = $("ghost");
    g.style.left = x + "px";
    g.style.top = y + "px";
    mark(target(document.elementFromPoint(e.clientX, e.clientY)));
  });
  addEventListener("pointerup", e => {
    if (!drag) return;
    const d = drag;
    drag = null;
    $("ghost").hidden = true;
    mark(null);
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (d.moving) drop(el, d.src);
    else if (el && el.closest("#body")) click(el, e);
  });
  body.addEventListener("click", e => {
    if (!S || !H.shop) return;
    if (e.target.closest("#done")) back();
    else if (e.target.closest("#spread")) act("distribute", {});
  });
  body.addEventListener("contextmenu", e => {
    if (!S || !H.shop) return;
    e.preventDefault();
    const src = source(e.target);
    if (src && src.item) menu(e, src.item);
  });
  addEventListener("pointerdown", e => { if (!e.target.closest("#menu")) $("menu").hidden = true; }, true);

  function escape() {
    if (!$("menu").hidden) { $("menu").hidden = true; return true; }
    if (picks) { picks = null; redraw(); return true; }
    return false;
  }

  return {draw, escape};
})();

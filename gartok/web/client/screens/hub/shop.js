// The shop tab: the shelf on paper, one leather column per pack, the sell plate and the common purse.
// Drag a ware onto a pack to buy it there (onto a worn slot to wear it, onto the purse to share it out
// by room); drag a pack item onto another pack or slot to hand it over, onto the shelf or Sell to sell
// it. A click picks, a second click on a pack drops; Shift picks several. Right-click an item for its
// menu. The server does every trade (`trade.Counter`).
"use strict";

const Shop = (() => {
  let S = null, cat = null, picks = null, drag = null;
  const qty = {}, chosen = {}, mark = dropMarker();
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
    const line = v ? `<p>${tr("shop.speaks", {name: esc(v.name)})}</p>` : `<p>${esc(d.headline.charAt(0).toUpperCase() + d.headline.slice(1))}</p>`;
    const marks = d.marks.map(m => `<span class="mark ${m.good ? "good" : "bad"}">${esc(m.text)}</span>`).join("");
    const till = S.till === null ? "" : `<div class="vsep"></div><div class="till">
      <div class="stack"><i style="top:29px"></i><i style="top:21px"></i><i style="top:13px"></i><i style="top:5px"></i></div>
      <div><div class="lbl">${tr("shop.till")}</div><b>${money(S.till)}</b><small>${tr("shop.till_note")}</small></div></div>`;
    $("cards").innerHTML = `<div class="vsep"></div><div class="deal">${who}<div><div class="lbl">${tr("shop.deal")}</div>${line}<div class="marks">${marks}</div></div></div>
      <div class="rate"><b>${d.pay}%</b><span class="lbl">${tr("shop.you_pay")}</span></div>
      <div class="rate"><b>${d.get}%</b><span class="lbl">${tr("shop.they_pay")}</span></div>${till}`;
  }

  // ---------------------------------------------------------------- the shelf
  // A weapon or armor comes in several sizes, one row each from the server; the shelf shows one row per family and a
  // toggle for the cuts it keeps, starting on the size the person last chose, else the band's leader's body.
  const ORDER = ["Tiny", "Small", "Medium", "Large", "Huge"];
  function families(rows) {
    const out = [], seen = {};
    rows.forEach(r => {
      if (!r.base) return out.push(r);
      (seen[r.base] = seen[r.base] || (out.push({base: r.base, cuts: []}), out[out.length - 1])).cuts.push(r);
    });
    return out.map(f => {
      if (!f.cuts) return f;
      const want = ORDER.indexOf(chosen[f.base] || S.size);
      const row = f.cuts.reduce((a, b) => Math.abs(ORDER.indexOf(b.size) - want) < Math.abs(ORDER.indexOf(a.size) - want) ? b : a);
      return {...row, cuts: f.cuts};
    });
  }

  function sizes(r) {
    if (!r.cuts || r.cuts.length < 2) return "";
    return `<span class="szs">${r.cuts.map(c => `<i class="${c.size === r.size ? "on" : ""}" data-base="${esc(r.base)}" data-size="${c.size}"${tip(nm("size", c.size))}>${esc(nm("size", c.size).slice(0, 3))}</i>`).join("")}</span>`;
  }

  function wareRow(r) {
    const out = r.stock !== null && r.stock <= 0, q = qty[r.name] || 1;
    const sel = picks && picks.ware === r.name;
    const pips = r.target && r.target <= 8
      ? `<div class="pips">${Array.from({length: r.target}, (_, k) => `<i class="${k < r.stock ? "" : "off"}"></i>`).join("")}</div>` : "";
    const stock = r.stock === null ? "—" : `${r.stock}${r.target ? ` <small>/ ${r.target}</small>` : ""}`;
    const tone = r.price < r.list ? "off" : r.price > r.list ? "up" : "";
    const buy = out ? `<div class="soldout">${tr("shop.sold_out")}</div>`
      : Kit.stepper(q);
    return `<div class="row ${out ? "out" : ""} ${sel ? "picked" : ""}" data-ware="${esc(r.name)}"${tip(r.tip, "item")}>
      <div class="ico mask" style="--icon:url(/assets/icons/${r.glyph}.svg)"></div>
      <div style="min-width:0"><div class="nm">${esc(nm("item", r.name))}</div><div class="use"><span class="t">${esc(r.use)}</span>${sizes(r)}</div></div>
      <div class="wt r">${r.weight.toFixed(1)} <small>${tr("kit.kg")}</small></div>
      <div class="stk c">${stock}${pips}</div>
      <div class="price r ${tone}">${r.price}</div>${buy}</div>`;
  }

  function shelf() {
    const c = S.shelf.find(x => x.key === cat) || S.shelf[0];
    const tabs = S.shelf.length > 1
      ? `<div class="cats">${S.shelf.map(x => `<span class="${x.key === c.key ? "on" : ""}" data-cat="${x.key}">${esc(lab(x.label))}</span>`).join("")}</div>` : "";
    return `<div class="paper" id="shelf"><div class="kicker">${tr("shop.shelf")} <em>${trn("shop.wares", S.shelf.reduce((n, x) => n + families(x.rows).length, 0))}</em></div>
      <div class="shelfhead"><h3>${esc(c ? lab(c.label) : tr("shop.nothing"))}</h3>${tabs}</div>
      <div class="cols"><span></span><span>${tr("shop.ware")}</span><span class="r">${tr("shop.weight")}</span><span class="c">${tr("shop.stock")}</span><span class="r">${tr("shop.price")}</span><span class="r">${tr("shop.buy")}</span></div>
      <div id="rows">${c ? families(c.rows).map(wareRow).join("") : ""}</div>
      <div class="shelffoot">${tr("shop.foot")}</div></div>`;
  }

  // ---------------------------------------------------------------- the packs
  function itemRow(p, it, loc, slot) {
    const tags = it && Kit.tag(it.locked, tr("shop.locked")) + Kit.tag(it.marked, tr("shop.auto_sell"), "auto");
    return Kit.item(p.id, it, loc, slot, {sel: picked(p.id, loc), tags});
  }

  function foot(p) {
    if (picks && picks.ware) {
      const r = ware(picks.ware), q = qty[r.name] || 1, after = p.kg + r.weight * q;
      const tail = after > p.max ? tr("shop.tail_full") : after > p.normal ? tr("shop.tail_burdened", {kg: p.normal}) : "";
      return tr("shop.buy_here", {what: (q > 1 ? q + " " : "") + esc(r.name), price: money(r.price * q), kg: (r.weight * q).toFixed(1), tail});
    }
    const mine = picks && picks.items ? picks.items.filter(x => x.from === p.id) : [];
    if (mine.length) return mine.length === 1 ? tr("shop.picked_one", {name: esc(mine[0].name)}) : tr("shop.picked_many", {items: trn("unit.item", mine.length)});
    if (picks && picks.items) return tr("shop.hand", {name: esc(short(p.name))});
    if (p.kg > p.normal) return tr("shop.burdened", {kg: (p.kg - p.normal).toFixed(1)});
    if (p.max - p.kg < 2) return tr("shop.near", {kg: (p.max - p.kg).toFixed(1)});
    return "";
  }

  function column(p) {
    const add = picks && picks.ware ? ware(picks.ware).weight * (qty[picks.ware] || 1) : 0;
    return Kit.column(p, {add, foot: foot(p), voice: p.voice ? tr("shop.voice") : "", row: itemRow});
  }

  // ---------------------------------------------------------------- the bottom
  function sellPlate() {
    const goods = picks && picks.items ? picks.items.filter(p => p.sell != null) : [];
    let line, ready = false;
    if (goods.length) {
      const what = goods.length === 1 ? `${goods[0].qty > 1 ? goods[0].qty + " " : ""}${goods[0].name}` : trn("unit.stack", goods.length);
      const t = sellTotal(goods);
      line = t ? tr("shop.sell_line", {what: esc(what), price: money(t)}) : tr("shop.worthless", {what: esc(what)});
      ready = true;
    } else if (S.marked.length) {
      const names = S.marked.length > 4 ? tr("shop.more", {names: S.marked.slice(0, 4).join(", "), n: S.marked.length - 4}) : S.marked.join(", ");
      line = tr("shop.auto_line", {names: esc(names), rest: S.marked_total ? tr("shop.auto_all", {price: money(S.marked_total)}) : S.marked_held ? tr("shop.auto_throw") : tr("shop.auto_none")});
      ready = S.marked_held;
    } else {
      line = tr("shop.drop_line", {keeper: esc(H.keeper.name || tr("shop.the_shop")), pct: S.deal.get});
    }
    return `<div class="leather ${ready ? "ready" : ""}" id="sell">${ico("action/trade")}<div><h4>${tr("shop.sell")}</h4><p>${line}</p></div></div>`;
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
    return Kit.purse({sum: S.purse, after, bad, packs: S.packs, spread: S.packs.filter(p => !p.store).length > 1});
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
    if (r && r.shop && r.shop.purse !== before) Sound.play("coins");
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
      if (list.some(p => p.sell != null)) act("sell", {picks: list.map(({from, loc, qty: q}) => ({from, loc, qty: q}))});
      else toast(tr("shop.no_coin"));
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
    if (el.closest(".qty") || el.closest(".cats") || el.closest(".szs")) return null;
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
      if (S.marked_held) act("sell_marked", {});
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
      [glyph, name, line, tag] = [r.glyph, q > 1 ? `${nm("item", r.name)} ×${q}` : nm("item", r.name), `${r.use} · ${(r.weight * q).toFixed(1)} kg`, money(r.price * q)];
    } else {
      const list = picks && picks.items && picks.items.some(p => same(p, src.item)) ? picks.items : [src.item];
      const it = list[0], t = sellTotal(list);
      [glyph, name, line] = [it.glyph, list.length > 1 ? trn("unit.item", list.length) : it.qty > 1 ? `${nm("item", it.name)} ×${it.qty}` : nm("item", it.name), kg(it.qty, it.kg)];
      tag = t ? "+" + money(t) : "";
      gain = true;
    }
    $("ghost").innerHTML = `${ico(glyph)}<div><b>${esc(name)}</b><span>${esc(line)}</span></div>${tag ? `<em class="${gain ? "gain" : ""}">${tag}</em>` : ""}`;
  }

  function target(el) {
    if (!el) return null;
    if (drag.src.ware) return el.closest(".it[data-zone]") || el.closest(".col") || el.closest("#purse");
    return el.closest(".it[data-zone]") || el.closest(".col") || el.closest("#sell") || el.closest("#shelf");
  }

  // ---------------------------------------------------------------- the item menu
  function menu(e, it) {
    const m = $("menu"), others = S.packs.filter(p => p.id !== it.from);
    const p = pack(it.from), row = typeof it.loc === "number" ? p.pack.find(r => r.loc === it.loc) : null;
    const rows = [];
    if (it.sell === 0) rows.push([it.qty > 1 ? tr("shop.throw_all", {n: it.qty}) : tr("shop.throw"), () => act("sell", {picks: [{from: it.from, loc: it.loc}]})]);
    else if (it.sell) {
      if (it.qty > 1) rows.push([tr("shop.sell_one", {price: money(it.sell)}), () => act("sell", {picks: [{from: it.from, loc: it.loc, qty: 1}]})]);
      rows.push([it.qty > 1 ? tr("shop.sell_all", {n: it.qty, price: money(it.sell * it.qty)}) : tr("shop.sell_menu", {price: money(it.sell)}), () => act("sell", {picks: [{from: it.from, loc: it.loc}]})]);
    }
    if (row) {
      rows.push([row.locked ? tr("shop.unlock") : tr("shop.lock"), () => act("lock", {owner: it.from, name: it.name})]);
      if (!row.coin) rows.push([row.marked ? tr("shop.unmark") : tr("shop.mark"), () => act("mark", {name: it.name})]);
    }
    if (rows.length && others.length) rows.push(null);
    const give = (o, q) => () => act("move", {picks: [{from: it.from, loc: it.loc, ...(q ? {qty: q} : {})}], to: o.id});
    let html = rows.map((r, i) => r ? `<div data-i="${i}">${r[0]}</div>` : "<hr>").join("");
    const acts = rows.map(r => r && r[1]);
    html += others.map(o => {
      const all = acts.push(give(o)) - 1, one = it.qty > 1 ? acts.push(give(o, 1)) - 1 : null;
      return `<div class="give"><span>${tr("kit.to", {name: esc(short(o.name))})}</span>${one === null ? "" : `<em data-i="${one}">1</em>`}<em data-i="${all}">${it.qty > 1 ? tr("kit.all") : tr("kit.give")}</em></div>`;
    }).join("");
    m.innerHTML = html;
    m.onclick = ev => {
      const d = ev.target.closest("[data-i]");
      if (!d) return;
      m.hidden = true;
      acts[Number(d.dataset.i)]();
    };
    popAt(m, e);
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
    const z = e.target.closest(".szs [data-size]");
    if (z) { chosen[z.dataset.base] = z.dataset.size; picks = null; return redraw(); }
    const c = e.target.closest(".cats [data-cat]");
    if (c) { cat = c.dataset.cat; return redraw(); }
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

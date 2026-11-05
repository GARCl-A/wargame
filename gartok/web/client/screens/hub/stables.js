// The Farm's STABLES and the Carpenter's WAGONS: on leather what the band keeps (each animal with its tack
// and job, each wagon with its cargo and what pulls it) and sells back; on paper what is for sale. The
// party pays out of its pooled coin, richest first; a sale back pays the leader. The house's GARAGE is the
// same page: on leather what is parked at the house, on paper the bays and what the band can park.
"use strict";

const Stables = (() => {
  const medal = o => o.portrait ? `<div class="medal">${face(o.portrait, o.name)}</div>`
    : `<div class="medal store">${ico(o.glyph)}</div>`;

  function offer(o, verb, key, purse) {
    const why = o.why || (o.can ? "" : tr("stables.party_has", {amount: money(purse)}));
    return `<div class="shift offer ${o.can ? "" : "off"}">
      ${medal(o)}
      <div><div class="nm">${esc(o.name)}</div><div class="use">${esc(o.sub)}</div>${why ? `<div class="why">${esc(why)}</div>` : ""}</div>
      <div class="price">${money(o.price)}</div>
      <div class="btn ${o.can ? "" : "off"}" data-verb="${verb}" data-key="${esc(o.name)}" data-body="${key}">${tr("stables.buy")}</div></div>`;
  }

  const sellBtn = (verb, k) => k.loaded ? `<span class="chip">${tr("stables.unload")}</span>`
    : `<div class="ghost-btn" data-verb="${verb}" data-uid="${esc(k.uid)}">${tr("stables.sell", {price: money(k.resale)})}</div>`;

  function animal(a) {
    const fits = a.fits.map(f => `<div class="ghost-btn ${f.can ? "" : "off"}" data-verb="fit" data-uid="${esc(a.uid)}" data-tack="${esc(f.tack)}">${esc(f.tack)} · ${money(f.price)}</div>`).join("");
    const chips = [`<span class="chip">${esc(a.job)}</span>`];
    if (a.unfed) chips.push(`<span class="chip bad">${trn("stables.unfed", a.unfed)}</span>`);
    return `<div class="worker kept">
      ${medal(a)}
      <div class="who"><h3>${esc(a.name)}${a.tack ? ` <small>· ${esc(a.tack)}</small>` : ""}</h3><div class="race">${esc(a.sub)}</div>
        <div class="chips">${chips.join("")}</div></div>
      <div class="keep">${fits}${sellBtn("sell_animal", a)}</div></div>`;
  }

  function wagon(w) {
    const pulled = w.pulled.length ? tr("stables.pulled_by", {names: w.pulled.join(" + ")}) : tr("stables.no_pull");
    const chips = [`<span class="chip ${w.pulled.length ? "" : "bad"}">${esc(pulled)}</span>`,
      `<span class="chip">${tr("stables.cargo", {have: w.cargo, cap: w.capacity})}</span>`];
    if (w.broken) chips.push(`<span class="chip bad">${tr("stables.broken")}</span>`);
    return `<div class="worker kept">
      ${medal(w)}
      <div class="who"><h3>${esc(w.name)}</h3><div class="race">${esc(w.sub)}</div><div class="chips">${chips.join("")}</div></div>
      <div class="keep">${sellBtn("sell_wagon", w)}</div></div>`;
  }

  function page(S, kept, empty, ledger, foot) {
    cards(S.cards);
    $("body").innerHTML = `<div class="leather lcol">${kept.head}
        <p class="hint">${tr("stables.hint")}</p>
        <div class="crew">${kept.rows || `<p class="hint">${empty}</p>`}</div></div>
      <div class="paper ledger"><div class="kicker">${tr("stables.for_sale")} <em>${ledger.line}</em></div>
        <div class="shifts">${ledger.rows}</div>
        <div class="ledgerfoot"><p>${foot}</p></div></div>`;
    toast(S.notice);
  }

  function animals(S) {
    const head = `<div class="lbl">${tr("stables.herd", {load: S.load, cap: S.capacity})}</div>` +
      (S.full ? `<p class="hint warn">${tr("stables.full", {keeper: esc(S.keeper)})}</p>` : "");
    page(S, {head, rows: S.herd.map(animal).join("")}, tr("stables.no_animals"),
      {line: tr("stables.line_animals"), rows: S.offers.map(o => offer(o, "buy_animal", "species", S.purse)).join("")},
      tr("stables.foot_animals"));
  }

  function wagons(W) {
    page(W, {head: `<div class="lbl">${tr("stables.group_wagons")}</div>`, rows: W.wagons.map(wagon).join("")},
      tr("stables.no_wagon"),
      {line: tr("stables.line_wagons"), rows: W.offers.map(o => offer(o, "buy_wagon", "kind", W.purse)).join("")},
      tr("stables.foot_wagons"));
  }

  function repairBtn(o) {
    const r = o.repair;
    return r ? `<div class="ghost-btn ${r.can ? "" : "off"}" data-verb="garage_repair" data-uid="${esc(o.uid)}"${tip(r.can ? tr("stables.repair_ok") : tr("stables.repair_no", {item: r.item}))}>${tr("stables.repair")}</div>` : "";
  }
  const mend = o => o.repair ? ` · ${tr("stables.mends", {cost: o.repair.cost, item: esc(o.repair.item)})}` : "";

  function parked(o) {
    const chips = o.broken ? [`<span class="chip bad">${tr("stables.broken")}</span>`] : [];
    if (o.unfed) chips.push(`<span class="chip bad">${trn("stables.unfed", o.unfed)}</span>`);
    const take = o.can ? `<div class="ghost-btn" data-verb="garage_take" data-uid="${esc(o.uid)}">${tr("stables.take_out")}</div>`
      : `<span class="chip">${esc(o.why)}</span>`;
    return `<div class="worker kept">${medal(o)}
      <div class="who"><h3>${esc(o.name)}</h3><div class="race">${esc(o.sub)}${mend(o)}</div>${chips.length ? `<div class="chips">${chips.join("")}</div>` : ""}</div>
      <div class="keep">${take}${repairBtn(o)}</div></div>`;
  }

  function kept(o) {
    return `<div class="shift offer ${o.can ? "" : "off"}">${medal(o)}
      <div><div class="nm">${esc(o.name)}${o.broken ? ` <small>· ${tr("stables.broken")}</small>` : ""}</div><div class="use">${esc(o.sub)}${mend(o)}</div>${o.why ? `<div class="why">${esc(o.why)}</div>` : ""}</div>
      <div class="price">${o.repair ? repairBtn(o) : ""}</div>
      <div class="btn ${o.can ? "" : "off"}" data-verb="garage_park" data-uid="${esc(o.uid)}">${o.portrait ? tr("stables.stable") : tr("stables.park")}</div></div>`;
  }

  function claimGarage(G) {
    const held = `${trn("unit.wagon", G.wagons)} · ${trn("unit.animal", G.animals)}`;
    const risk = G.watch ? `<p class="aside bad">${tr("stables.bolt", {watch: G.watch})}</p>`
      : `<p class="aside">${tr("stables.garrisoned")}</p>`;
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${tr("stables.at_claim", {held: esc(held)})}</div>
        <p class="hint">${tr("stables.claim_hint")}</p>
        <div class="crew">${G.parked.map(parked).join("") || `<p class="hint">${tr("stables.nothing_parked")}</p>`}</div></div>
      <div class="paper ledger"><div class="kicker">${tr("stables.claim_garage")} <em>${tr("stables.claim_note")}</em></div>
        ${risk}<div class="shifts">${G.kept.map(kept).join("")}</div>
        <div class="ledgerfoot"><p>${tr(G.kept.length ? "stables.claim_foot" : "stables.claim_foot_none")}</p></div></div>`;
    toast(G.notice);
  }

  function garage(G) {
    cards(G.cards);
    if (G.claim) { claimGarage(G); return; }
    const held = G.open ? tr("stables.bays_held", {wagons: G.wagons, animals: G.animals, tier: G.tier}) : tr("stables.no_bays");
    const bay = `<div class="shift offer ${G.can_bay ? "" : "off"}"><div class="medal store">${ico("item/old-wagon")}</div>
      <div><div class="nm">${G.open ? tr("stables.add_bay") : tr("stables.build_garage")}</div><div class="use">${tr("stables.bay_use")}</div>
      ${G.can_bay ? "" : `<div class="why">${tr("stables.party_has", {amount: money(G.purse)})}</div>`}</div>
      <div class="price">${money(G.price)}</div>
      <div class="btn ${G.can_bay ? "" : "off"}" data-verb="garage_bay">${tr("stables.build")}</div></div>`;
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${tr("stables.in_garage", {held: esc(held)})}</div>
        <p class="hint">${tr("stables.garage_hint")}</p>
        <div class="crew">${G.parked.map(parked).join("") || `<p class="hint">${tr("stables.nothing_parked")}</p>`}</div></div>
      <div class="paper ledger"><div class="kicker">${tr("stables.bays")} <em>${esc(held)}</em></div>
        <div class="shifts">${bay}${G.kept.map(kept).join("") || ""}</div>
        <div class="ledgerfoot"><p>${tr(G.kept.length ? "stables.garage_foot" : "stables.garage_foot_none")}</p></div></div>`;
    toast(G.notice);
  }

  $("body").addEventListener("click", async e => {
    if (!H || !(H.stable || H.wagons || H.garage)) return;
    const b = e.target.closest("[data-verb]");
    if (!b || b.classList.contains("off")) return;
    const d = b.dataset;
    const body = d.body ? {[d.body]: d.key} : d.tack ? {uid: d.uid, tack: d.tack} : d.uid ? {uid: d.uid} : {};
    const r = await post(d.verb, body);
    if (r && (!d.verb.startsWith("garage_") || d.verb === "garage_bay")) Sound.play("coins");
  });

  return {animals, wagons, garage};
})();

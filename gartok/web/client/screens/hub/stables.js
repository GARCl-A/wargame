// The Farm's STABLES and the Carpenter's WAGONS: on leather what the band keeps (each animal with its tack
// and job, each wagon with its cargo and what pulls it) and sells back; on paper what is for sale. The
// party pays out of its pooled coin, richest first; a sale back pays the leader. The house's GARAGE is the
// same page: on leather what is parked at the house, on paper the bays and what the band can park.
"use strict";

const Stables = (() => {
  const medal = o => o.portrait ? `<div class="medal">${face(o.portrait, o.name)}</div>`
    : `<div class="medal store">${ico(o.glyph)}</div>`;

  function offer(o, verb, key, purse) {
    const why = o.why || (o.can ? "" : `the party has ${money(purse)}`);
    return `<div class="shift offer ${o.can ? "" : "off"}">
      ${medal(o)}
      <div><div class="nm">${esc(o.name)}</div><div class="use">${esc(o.sub)}</div>${why ? `<div class="why">${esc(why)}</div>` : ""}</div>
      <div class="price">${money(o.price)}</div>
      <div class="btn ${o.can ? "" : "off"}" data-verb="${verb}" data-key="${esc(o.name)}" data-body="${key}">Buy</div></div>`;
  }

  const sellBtn = (verb, k) => k.loaded ? `<span class="chip">unload it to sell</span>`
    : `<div class="ghost-btn" data-verb="${verb}" data-uid="${esc(k.uid)}">Sell · ${money(k.resale)}</div>`;

  function animal(a) {
    const fits = a.fits.map(f => `<div class="ghost-btn ${f.can ? "" : "off"}" data-verb="fit" data-uid="${esc(a.uid)}" data-tack="${esc(f.tack)}">${esc(f.tack)} · ${money(f.price)}</div>`).join("");
    const chips = [`<span class="chip">${esc(a.job)}</span>`];
    if (a.unfed) chips.push(`<span class="chip bad">unfed ${a.unfed} day${a.unfed === 1 ? "" : "s"}</span>`);
    return `<div class="worker kept">
      ${medal(a)}
      <div class="who"><h3>${esc(a.name)}${a.tack ? ` <small>· ${esc(a.tack)}</small>` : ""}</h3><div class="race">${esc(a.sub)}</div>
        <div class="chips">${chips.join("")}</div></div>
      <div class="keep">${fits}${sellBtn("sell_animal", a)}</div></div>`;
  }

  function wagon(w) {
    const pulled = w.pulled.length ? `pulled by ${w.pulled.join(" + ")}` : "nothing pulls it";
    const chips = [`<span class="chip ${w.pulled.length ? "" : "bad"}">${esc(pulled)}</span>`,
      `<span class="chip">cargo ${w.cargo} / ${w.capacity} kg</span>`];
    if (w.broken) chips.push(`<span class="chip bad">broken</span>`);
    return `<div class="worker kept">
      ${medal(w)}
      <div class="who"><h3>${esc(w.name)}</h3><div class="race">${esc(w.sub)}</div><div class="chips">${chips.join("")}</div></div>
      <div class="keep">${sellBtn("sell_wagon", w)}</div></div>`;
  }

  function page(S, kept, empty, ledger, foot) {
    cards(S.cards);
    $("body").innerHTML = `<div class="leather lcol">${kept.head}
        <p class="hint">Hitching and riding are set on the group's gear screen.</p>
        <div class="crew">${kept.rows || `<p class="hint">${empty}</p>`}</div></div>
      <div class="paper ledger"><div class="kicker">For sale <em>${ledger.line}</em></div>
        <div class="shifts">${ledger.rows}</div>
        <div class="ledgerfoot"><p>${foot}</p></div></div>`;
    toast(S.notice);
  }

  function animals(S) {
    const head = `<div class="lbl">The herd · ${S.load} / ${S.capacity}</div>` +
      (S.full ? `<p class="hint warn">Full: ${esc(S.keeper)} controls no more.</p>` : "");
    page(S, {head, rows: S.herd.map(animal).join("")}, "No animals yet.",
      {line: "animals; wagons are the Carpenter's", rows: S.offers.map(o => offer(o, "buy_animal", "species", S.purse)).join("")},
      "Every animal eats a ration a day; tack decides what it does: a Harness pulls a wagon, a Pack Saddle carries cargo. A sale back pays half to the leader.");
  }

  function wagons(W) {
    page(W, {head: `<div class="lbl">The group's wagons</div>`, rows: W.wagons.map(wagon).join("")},
      "No wagon. Cargo in a wagon never goes into a fight and feeds the group on the road; animals in a Harness pull it.",
      {line: "wagons; the animals that pull them are the Farm's", rows: W.offers.map(o => offer(o, "buy_wagon", "kind", W.purse)).join("")},
      "The road wears a wagon down; a broken one is mended with Lumber. Only an empty wagon sells back, for half its price.");
  }

  function repairBtn(o) {
    const r = o.repair;
    return r ? `<div class="ghost-btn ${r.can ? "" : "off"}" data-verb="garage_repair" data-uid="${esc(o.uid)}" title="${r.can ? "an hour and an INT check" : `the band carries too little ${esc(r.item)}`}">Repair</div>` : "";
  }
  const mend = o => o.repair ? ` · mends with ${o.repair.cost} ${esc(o.repair.item)}` : "";

  function parked(o) {
    const chips = o.broken ? [`<span class="chip bad">broken</span>`] : [];
    if (o.unfed) chips.push(`<span class="chip bad">unfed ${o.unfed} day${o.unfed === 1 ? "" : "s"}</span>`);
    const take = o.can ? `<div class="ghost-btn" data-verb="garage_take" data-uid="${esc(o.uid)}">Take out</div>`
      : `<span class="chip">${esc(o.why)}</span>`;
    return `<div class="worker kept">${medal(o)}
      <div class="who"><h3>${esc(o.name)}</h3><div class="race">${esc(o.sub)}${mend(o)}</div>${chips.length ? `<div class="chips">${chips.join("")}</div>` : ""}</div>
      <div class="keep">${take}${repairBtn(o)}</div></div>`;
  }

  function kept(o) {
    return `<div class="shift offer ${o.can ? "" : "off"}">${medal(o)}
      <div><div class="nm">${esc(o.name)}${o.broken ? " <small>· broken</small>" : ""}</div><div class="use">${esc(o.sub)}${mend(o)}</div>${o.why ? `<div class="why">${esc(o.why)}</div>` : ""}</div>
      <div class="price">${o.repair ? repairBtn(o) : ""}</div>
      <div class="btn ${o.can ? "" : "off"}" data-verb="garage_park" data-uid="${esc(o.uid)}">${o.portrait ? "Stable" : "Park"}</div></div>`;
  }

  function claimGarage(G) {
    const held = `${G.wagons} wagon${G.wagons === 1 ? "" : "s"} · ${G.animals} animal${G.animals === 1 ? "" : "s"}`;
    const risk = G.watch ? `<p class="aside bad">Nobody is garrisoned: each day the animals may bolt and take it all (${G.watch} a day).</p>`
      : `<p class="aside">A garrison stands here: what is parked is safe, and a raid is a fight.</p>`;
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">At the claim · ${esc(held)}</div>
        <p class="hint">What is parked stays at the claim with no limit, fed from the garrison's food, off the herd limit.</p>
        <div class="crew">${G.parked.map(parked).join("") || `<p class="hint">Nothing parked.</p>`}</div></div>
      <div class="paper ledger"><div class="kicker">The claim garage <em>safe only while a garrison stands here</em></div>
        ${risk}<div class="shifts">${G.kept.map(kept).join("")}</div>
        <div class="ledgerfoot"><p>${G.kept.length ? "" : "The band has no wagon or animal with it to park. "}A wagon parked keeps its cargo. With nobody garrisoned the animals may bolt, and a seized claim loses everything parked there.</p></div></div>`;
    toast(G.notice);
  }

  function garage(G) {
    cards(G.cards);
    if (G.claim) { claimGarage(G); return; }
    const held = G.open ? `${G.wagons} / ${G.tier} wagons · ${G.animals} / ${G.tier} animals` : "no bays yet";
    const bay = `<div class="shift offer ${G.can_bay ? "" : "off"}"><div class="medal store">${ico("item/old-wagon")}</div>
      <div><div class="nm">${G.open ? "Add a bay" : "Build a garage"}</div><div class="use">one more wagon and one more animal kept at the house</div>
      ${G.can_bay ? "" : `<div class="why">the party has ${money(G.purse)}</div>`}</div>
      <div class="price">${money(G.price)}</div>
      <div class="btn ${G.can_bay ? "" : "off"}" data-verb="garage_bay">Build</div></div>`;
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">In the garage · ${esc(held)}</div>
        <p class="hint">What is parked belongs to the house: safe, fed from the house stash, off the herd limit.</p>
        <div class="crew">${G.parked.map(parked).join("") || `<p class="hint">Nothing parked.</p>`}</div></div>
      <div class="paper ledger"><div class="kicker">The bays <em>${esc(held)}</em></div>
        <div class="shifts">${bay}${G.kept.map(kept).join("") || ""}</div>
        <div class="ledgerfoot"><p>${G.kept.length ? "" : "The band has no wagon or animal with it to park. "}A wagon parked keeps its cargo; an animal in the garage eats from the house stash, and with no food it starves. Lose the house and you lose the garage.</p></div></div>`;
    toast(G.notice);
  }

  $("body").addEventListener("click", async e => {
    if (!H || !(H.stable || H.wagons || H.garage)) return;
    const b = e.target.closest("[data-verb]");
    if (!b || b.classList.contains("off")) return;
    const d = b.dataset;
    const body = d.body ? {[d.body]: d.key} : d.tack ? {uid: d.uid, tack: d.tack} : d.uid ? {uid: d.uid} : {};
    const r = await post(d.verb, body);
    if (r) Sound.play(d.verb.startsWith("garage_") && d.verb !== "garage_bay" ? "click" : "coins");
  });

  return {animals, wagons, garage};
})();

// The Wilds Claim's own tab: the band here on leather (what each one carries toward the claim), on paper the
// six stages as a track, the one in hand with its work, and the hearth once the region is swept. The two
// fights and the garrison leave the claim; everything else is done here and the tab stays up.
"use strict";

const Claim = (() => {
  function member(u) {
    const held = u.held.map(h => `<span class="chip money">${h.qty} ${esc(h.name)}</span>`).join("");
    return `<div class="worker">
      <div class="medal">${face(u.portrait, u.name)}</div>
      <div class="who"><h3>${esc(u.name)}</h3><div class="race">${esc(u.sub)}</div>
        ${held ? `<div class="chips">${held}</div>` : ""}</div></div>`;
  }

  const track = C => `<div class="csteps">${C.steps.map((s, i) =>
    `<div class="cstep ${s.state}"><i>${s.state === "done" ? "✓" : i + 1}</i><span>${esc(s.label)}</span></div>`).join("")}</div>`;

  function progress(C) {
    if (C.lumber) {
      const L = C.lumber, pct = Math.min(100, 100 * L.have / L.need);
      return `<div class="prog cprog"><div class="bar"><i style="width:${pct}%"></i></div>
        <span>${tr("claim.lumber", {have: L.have, need: L.need, carried: L.carried})}</span></div>`;
    }
    if (C.days_left != null) {
      const cls = C.garrison ? "money" : "bad", days = plural(C.days_left, "day");
      return `<p class="aside ${cls}">${C.garrison ? tr("claim.left_held", {days, who: esc(C.garrison)}) : tr("claim.left_none", {days})}</p>`;
    }
    return "";
  }

  function job(C) {
    if (!C.here) return "";
    return `<p class="aside">${tr("claim.garrisons")}</p>`;
  }

  const action = a => `<div class="brass-btn ${a.can ? "" : "off"}" data-claim="${a.verb}"${tip(a.why || "")}><div><b>${esc(a.label)}</b></div></div>`;

  function hearth(C) {
    const h = C.hearth;
    if (!h) return "";
    if (h.can_cook) {
      return `<div class="sec dark"><span class="lbl">${tr("claim.hearth")}</span></div>
        <p class="aside">${tr(h.oven && h.lit ? "claim.cook_both" : h.oven ? "claim.cook_oven" : "claim.cook_fire")}</p>`;
    }
    const row = (verb, glyph, name, use, why, can) => `<div class="shift offer ${can ? "" : "off"}">
      <div class="medal store">${ico(glyph)}</div>
      <div><div class="nm">${name}</div><div class="use">${use}</div>${can ? "" : `<div class="why">${why}</div>`}</div>
      <div class="price"></div>
      <div class="btn ${can ? "" : "off"}" data-claim="${verb}">${tr("claim.build")}</div></div>`;
    return `<div class="sec dark"><span class="lbl">${tr("claim.hearth")}</span></div><div class="shifts">
      ${row("campfire", "item/log", tr("claim.campfire"), tr("claim.campfire_use", {fuel: esc(h.fuel), hours: h.fire_hours, dc: h.dc}),
            tr("claim.campfire_why", {fuel: esc(h.fuel)}), h.can_fire)}
      ${row("oven", "item/brick-pile", tr("claim.oven"), tr("claim.oven_use", {need: h.bricks_need, brick: esc(h.brick), hours: h.oven_hours}),
            tr("claim.oven_why", {have: h.bricks_have, need: h.bricks_need, brick: esc(h.brick)}), h.can_oven)}</div>`;
  }

  function draw(C) {
    cards(C.cards);
    const report = C.report.length
      ? `<div class="report"><div class="kicker">${tr("claim.report")}</div>${C.report.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";
    const foot = C.watch ? `<p class="warn">${tr("claim.bolt", {watch: C.watch})}</p>` : "";
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${tr("claim.here", {members: plural(C.members.length, "member")})}</div>
        <p class="hint">${tr("claim.fences")}</p>
        <div class="crew">${C.members.map(member).join("")}</div></div>
      <div class="paper ledger"><div class="kicker">${tr("claim.title")} <em>${C.seized ? tr("claim.seized") : esc(C.stage.toLowerCase())}</em></div>
        ${track(C)}
        <div class="cstage ${C.seized ? "bad" : ""}">${C.lines.map(l => `<p>${esc(l)}</p>`).join("")}</div>
        ${progress(C)}${job(C)}
        <div class="cacts">${C.actions.map(action).join("")}</div>
        ${hearth(C)}${report}
        <div class="ledgerfoot">${foot}<p>${tr("claim.foot")}</p></div></div>`;
  }

  $("body").addEventListener("click", async e => {
    if (!H || !H.claim) return;
    const b = e.target.closest("[data-claim]");
    if (!b || b.classList.contains("off")) return;
    const verb = b.dataset.claim;
    if (verb.startsWith("fight_")) post("claim_fight", {verb});
    else if (verb === "garrison") post("claim_garrison");
    else post("claim", {verb});
  });

  return {draw};
})();

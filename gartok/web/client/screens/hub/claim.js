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
        <span>${L.have} / ${L.need} Lumber banked · ${L.carried} carried here</span></div>`;
    }
    if (C.days_left != null) {
      const cls = C.garrison ? "money" : "bad";
      const who = C.garrison ? `${esc(C.garrison)} holds it` : "nobody holds it: the count is not moving";
      return `<p class="aside ${cls}">${plural(C.days_left, "day")} left · ${who}.</p>`;
    }
    if (C.banked != null) return `<p class="aside">${C.banked ? `${plural(C.banked, "Lumber")} banked here by the garrison.` : "Nothing banked yet."}</p>`;
    return "";
  }

  function job(C) {
    if (!C.here) return "";
    return `<p class="aside">This band garrisons the claim: ${C.job === "hold" ? "it holds and rests" : "it gathers Lumber"}.</p>`;
  }

  const action = a => `<div class="brass-btn ${a.can ? "" : "off"}" data-claim="${a.verb}"${tip(a.why || "")}><div><b>${esc(a.label)}</b></div></div>`;

  function hearth(C) {
    const h = C.hearth;
    if (!h) return "";
    if (h.can_cook) {
      const by = [h.oven && "an oven", h.lit && "a fire"].filter(Boolean).join(" and ");
      return `<div class="sec dark"><span class="lbl">The hearth</span></div>
        <p class="aside">The claim has ${by}: the band cooks in the Kitchen tab.${h.oven ? "" : " The fire stays lit while a garrison is here."}</p>`;
    }
    const row = (verb, glyph, name, use, why, can) => `<div class="shift offer ${can ? "" : "off"}">
      <div class="medal store">${ico(glyph)}</div>
      <div><div class="nm">${name}</div><div class="use">${use}</div>${can ? "" : `<div class="why">${why}</div>`}</div>
      <div class="price"></div>
      <div class="btn ${can ? "" : "off"}" data-claim="${verb}">Build</div></div>`;
    return `<div class="sec dark"><span class="lbl">The hearth</span></div><div class="shifts">
      ${row("campfire", "item/log", "A campfire", `burns 1 ${esc(h.fuel)}, ${h.fire_hours} h, a WIS check (DC ${h.dc}); it stays lit while a garrison is here`,
            `the band carries no ${esc(h.fuel)}`, h.can_fire)}
      ${row("oven", "item/brick-pile", "An oven", `${h.bricks_need} ${esc(h.brick)} and ${h.oven_hours} h; it never goes out`,
            `the band carries ${h.bricks_have} / ${h.bricks_need} ${esc(h.brick)}`, h.can_oven)}</div>`;
  }

  function draw(C) {
    cards(C.cards);
    const report = C.report.length
      ? `<div class="report"><div class="kicker">The claim</div>${C.report.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";
    const foot = C.watch ? `<p class="warn">Nobody is garrisoned and the garage holds something: each day the animals may bolt and take it all (${C.watch} a day).</p>` : "";
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">Here · ${plural(C.members.length, "member")}</div>
        <p class="hint">The Lumber and the Stone Brick the band carries count toward the fences and the oven.</p>
        <div class="crew">${C.members.map(member).join("")}</div></div>
      <div class="paper ledger"><div class="kicker">The Wilds Claim <em>${C.seized ? "seized" : esc(C.stage.toLowerCase())}</em></div>
        ${track(C)}
        <div class="cstage ${C.seized ? "bad" : ""}">${C.lines.map(l => `<p>${esc(l)}</p>`).join("")}</div>
        ${progress(C)}${job(C)}
        <div class="cacts">${C.actions.map(action).join("")}</div>
        ${hearth(C)}${report}
        <div class="ledgerfoot">${foot}<p>Six stages: scout, clear, fence, sweep, then a garrison that holds it ten whole days. A lost raid or a garrison pulled out early starts the count over.</p></div></div>`;
  }

  $("body").addEventListener("click", async e => {
    if (!H || !H.claim) return;
    const b = e.target.closest("[data-claim]");
    if (!b || b.classList.contains("off")) return;
    const verb = b.dataset.claim;
    Sound.play("click");
    if (verb.startsWith("fight_")) post("claim_fight", {verb});
    else if (verb === "garrison") post("claim_garrison");
    else post("claim", {verb});
  });

  return {draw};
})();

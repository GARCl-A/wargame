// A work node's two tabs: WORK (the crew on leather with each one's tool and wage, the shifts on paper)
// and GATHERING (the licence and what the ground gives on leather, the shifts that keep the haul on
// paper). A paid shift runs the clock and stays here with what it paid; a gathering shift goes back to
// the map, where the clock runs.
"use strict";

const Labor = (() => {
  function shiftRow(glyph, s, sub, price, tone, verb, label, on) {
    return `<div class="shift ${on ? "" : "off"}">
      <div class="ico mask" style="--icon:url(/assets/icons/${glyph}.svg)"></div>
      <div><div class="nm">${s.hours} hours</div><div class="use">${sub}</div></div>
      <div class="price ${tone}">${price}</div>
      <div class="btn ${on ? "" : "off"}" data-verb="${verb}" data-hours="${s.hours}">${label}</div></div>`;
  }

  function work(W) {
    cards(W.cards);
    const crew = W.crew.map(u => `<div class="worker">
      <div class="medal">${face(u.portrait, u.name)}</div>
      <div class="who"><h3>${esc(u.name)}</h3><div class="race">${esc(u.sub)}</div>${u.note ? `<p>${esc(u.note)}</p>` : ""}</div>
      <div class="pay ${u.own ? "good" : ""}"><b>${money(u.pay)}</b><span class="lbl">per ${W.day} h</span></div></div>`).join("");
    const report = W.report.length
      ? `<div class="report"><div class="kicker">The last shift</div>${W.report.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">The crew</div>
        <p class="hint">Their own ${esc(W.tool.toLowerCase())} pays more than the foreman's.</p><div class="crew">${crew}</div></div>
      <div class="paper ledger"><div class="kicker">Shifts <em>trade hours of the day for money: pays little, but it's sure</em></div>
        <div class="shifts">${W.shifts.map(s => shiftRow(W.glyph, s, "paid by the block; leftover hours earn nothing",
          money(s.wage), "", "work", "Work", true)).join("")}</div>
        <p class="aside">The licence on the Gathering tab trades the wage for what the crew finds.</p>${report}</div>`;
  }

  function gather(G) {
    cards(G.cards);
    const status = G.held
      ? `<div class="fact"><span class="lbl">Status</span><b class="good">held: every band gathers here</b></div>`
      : `<div class="fact"><span class="lbl">Status</span><b>not held · ${money(G.price)}</b></div>
         <div class="fact"><span class="lbl">Purse</span><b class="${G.short ? "bad" : ""}">${G.short ? `the band is short ${money(G.short)}` : "the band can pay it now"}</b></div>
         <div class="brass-btn wide ${G.short ? "off" : ""}" id="licence"><div><b>Buy the licence · ${money(G.price)}</b></div></div>`;
    const crew = G.crew.map(u => `<div class="worker slim ${u.tool ? "" : "guard"}">
      <div class="medal">${face(u.portrait, u.name)}</div>
      <div class="who"><h3>${esc(u.name)}</h3><div class="race">${esc(u.sub)} · wage ${money(u.wage)}</div>
        <p class="${u.tool ? "" : "bad"}">${esc(u.note)}</p></div>
      <div class="pay ${u.good ? "good" : u.tool ? "" : "bad"}"><b>${u.tool ? "~" + money(u.haul) : "guard"}</b><span class="lbl">${u.tool ? `per ${G.day} h` : `no ${esc(G.tool.toLowerCase())}`}</span></div></div>`).join("");
    const tool = esc(G.tool), names = G.guards.map(esc).join(", ");
    const guards = !G.guards.length ? ""
      : !G.can ? `<p class="warn">No one in the band carries a ${tool}: nobody can gather.</p>`
      : `<p class="warn">${names} ${G.guards.length > 1 ? "have" : "has"} no ${tool}: ${G.guards.length > 1 ? "they stand" : "stands"} guard, with no haul and no work XP. Split them off on the map if they should earn elsewhere.</p>`;
    const drops = G.drops.map(d => `<div class="it">${ico(d.glyph)}<div class="n">${esc(d.name)} <small>sells for ${money(d.sell)}</small></div>
      <span class="q">${d.pct}%</span><span></span></div>`).join("");
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">The licence</div>
        <p class="hint">One licence covers the whole guild.</p>${status}
        <div class="sec"><span class="lbl">The crew</span></div><p class="hint">Only those with their own ${tool} gather, each keeping what they find and learning up to work level ${G.level + 1}; the rest stand guard.</p>
        <div class="crew">${crew}</div>
        <div class="sec"><span class="lbl">What the ground gives</span></div><p class="hint">${esc(G.rolls)}</p>${drops}</div>
      <div class="paper ledger"><div class="kicker">Shifts <em>the crew keeps what it finds instead of a wage</em></div>
        <div class="shifts">${G.shifts.map(s => shiftRow(G.glyph, s, `the same hours' wage ${money(s.wage)} · ${s.risk}% ambush`,
          "~" + money(s.haul), s.good ? "good" : "", "gather", "Gather", G.held && G.can)).join("")}</div>
        ${G.held ? "" : `<p class="aside">Gathering needs the licence.</p>`}
        <div class="ledgerfoot">${guards}<p class="warn">A pack may ambush the crew: the fight must be won to keep the haul.</p><p>${esc(G.payback)}</p></div></div>`;
    toast(G.notice);
  }

  async function act(verb, body) {
    const r = await post(verb, body);
    if (r) Sound.play(verb === "work" || verb === "licence" ? "coins" : "click");
  }

  $("body").addEventListener("click", e => {
    if (!H || !(H.work || H.gather)) return;
    const b = e.target.closest("[data-verb]");
    if (b && !b.classList.contains("off")) { act(b.dataset.verb, {hours: +b.dataset.hours}); return; }
    const l = e.target.closest("#licence");
    if (l && !l.classList.contains("off")) act("licence");
  });

  return {work, gather};
})();

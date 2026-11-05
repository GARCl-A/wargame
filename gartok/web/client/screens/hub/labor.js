// A work node's two tabs: WORK (the crew on leather with each one's tool and wage, the shifts on paper)
// and GATHERING (the licence and what the ground gives on leather, the shifts that keep the haul on
// paper). A shift runs the clock and stays here with what it paid or found.
"use strict";

const Labor = (() => {
  function shiftRow(glyph, s, sub, price, tone, verb, label, on) {
    return `<div class="shift ${on ? "" : "off"}">
      <div class="ico mask" style="--icon:url(/assets/icons/${glyph}.svg)"></div>
      <div><div class="nm">${trn("unit.hour", s.hours)}</div><div class="use">${sub}</div></div>
      <div class="price ${tone}">${price}</div>
      <div class="btn ${on ? "" : "off"}" data-verb="${verb}" data-hours="${s.hours}">${label}</div></div>`;
  }

  function work(W) {
    cards(W.cards);
    const crew = W.crew.map(u => `<div class="worker">
      <div class="medal">${face(u.portrait, u.name)}</div>
      <div class="who"><h3>${esc(u.name)}</h3><div class="race">${esc(u.sub)}</div>${u.note ? `<p>${esc(u.note)}</p>` : ""}</div>
      <div class="pay ${u.own ? "good" : ""}"><b>${money(u.pay)}</b><span class="lbl">${tr("labor.per", {n: W.day})}</span></div></div>`).join("");
    const report = W.report.length
      ? `<div class="report"><div class="kicker">${tr("labor.last_shift")}</div>${W.report.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${tr("labor.the_crew")}</div>
        <p class="hint">${tr("labor.own_tool", {tool: esc(W.tool.toLowerCase())})}</p><div class="crew">${crew}</div></div>
      <div class="paper ledger"><div class="kicker">${tr("labor.shifts")} <em>${tr("labor.shifts_work")}</em></div>
        <div class="shifts">${W.shifts.map(s => shiftRow(W.glyph, s, tr("labor.paid_block"),
          money(s.wage), "", "work", tr("labor.work"), true)).join("")}</div>
        <p class="aside">${tr("labor.licence_aside")}</p>${report}</div>`;
  }

  function gather(G) {
    cards(G.cards);
    const free = G.price == null;
    const status = free
      ? `<div class="fact"><span class="lbl">${tr("labor.status")}</span><b class="good">${tr("labor.free")}</b></div>`
      : G.held
      ? `<div class="fact"><span class="lbl">${tr("labor.status")}</span><b class="good">${tr("labor.held")}</b></div>`
      : `<div class="fact"><span class="lbl">${tr("labor.status")}</span><b>${tr("labor.not_held", {price: money(G.price)})}</b></div>
         <div class="fact"><span class="lbl">${tr("labor.purse")}</span><b class="${G.short ? "bad" : ""}">${G.short ? tr("labor.short", {amount: money(G.short)}) : tr("labor.can_pay")}</b></div>
         <div class="brass-btn wide ${G.short ? "off" : ""}" id="licence"><div><b>${tr("labor.buy", {price: money(G.price)})}</b></div></div>`;
    const crew = G.crew.map(u => `<div class="worker slim ${u.tool ? "" : "guard"}">
      <div class="medal">${face(u.portrait, u.name)}</div>
      <div class="who"><h3>${esc(u.name)}</h3><div class="race">${esc(u.sub)}</div>
        <p class="${u.tool ? "" : "bad"}">${esc(u.note)}</p></div>
      <div class="pay ${u.tool ? "" : "bad"}"><b>${u.tool ? "~" + money(u.haul) : tr("labor.guard")}</b><span class="lbl">${u.tool ? tr("labor.per", {n: G.day}) : tr("labor.no_tool", {tool: esc(G.tool.toLowerCase())})}</span></div></div>`).join("");
    const tool = esc(G.tool), names = G.guards.map(esc).join(", ");
    const guards = !G.guards.length ? ""
      : !G.can ? `<p class="warn">${tr("labor.none_carry", {tool})}</p>`
      : `<p class="warn">${trn("labor.guards", G.guards.length, {names, tool})}</p>`;
    const drops = G.drops.map(d => `<div class="it">${ico(d.glyph)}<div class="n">${esc(d.name)} <small>${tr("labor.sells_for", {price: money(d.sell)})}</small></div>
      <span class="q">${d.pct}%</span><span></span></div>`).join("");
    const bonus = G.bonus ? `<p class="hint">${tr("labor.bonus", {pct: G.bonus.pct, name: esc(G.bonus.name), price: money(G.bonus.sell)})}</p>` : "";
    const report = G.report.length
      ? `<div class="report"><div class="kicker">${tr("labor.last_shift")}</div>${G.report.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${free ? tr("labor.the_ground") : tr("labor.the_licence")}</div>
        ${free ? "" : `<p class="hint">${tr("labor.one_licence")}</p>`}${status}
        <div class="sec"><span class="lbl">${tr("labor.the_crew")}</span></div><p class="hint">${tr("labor.only_tool", {tool, level: G.level + 1})}</p>
        <div class="crew">${crew}</div>
        <div class="sec"><span class="lbl">${tr("labor.gives")}</span></div><p class="hint">${esc(G.rolls)}</p>${drops}${bonus}</div>
      <div class="paper ledger"><div class="kicker">${tr("labor.shifts")} <em>${tr("labor.shifts_gather")}</em></div>
        <div class="shifts">${G.shifts.map(s => shiftRow(G.glyph, s, tr("labor.ambush", {pct: s.risk}),
          "~" + money(s.haul), "", "gather", tr("labor.gather"), (free || G.held) && G.can)).join("")}</div>
        ${free || G.held ? "" : `<p class="aside">${tr("labor.needs_licence")}</p>`}
        <div class="ledgerfoot">${guards}<p class="warn">${tr("labor.ambush_warn")}</p><p>${esc(G.payback)}</p></div>${report}</div>`;
    toast(G.notice);
  }

  async function act(verb, body) {
    const r = await post(verb, body);
    if (r && (verb === "work" || verb === "gather" || verb === "licence")) Sound.play("coins");
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

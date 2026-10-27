// A sanctuary's INITIATION tab: the band on leather (click who stays to board for the rite; each with
// where they stand in it, or why the school will not take them), the school's terms on paper and the
// button that leaves the picked one boarding. The pick lives on the server.
"use strict";

const Initiation = (() => {
  function member(u) {
    const chip = u.initiated ? `<span class="chip good">initiated</span>`
      : u.started ? `<span class="chip money">${esc(u.stage)} ${u.done} / ${u.total}</span>` : "";
    const note = u.note && !u.initiated ? `<p>${esc(u.note)}</p>` : "";
    return `<div class="worker patient ${u.picked ? "on" : ""} ${u.on ? "" : "out"}" data-uid="${esc(u.uid)}">
      <div class="medal">${face(u.portrait, u.name)}</div>
      <div class="who"><h3>${esc(u.name)}</h3><div class="race">${esc(u.sub)}</div>
        <div class="chips">${chip}</div>${note}</div></div>`;
  }

  function standing(I) {
    const u = I.members.find(m => m.picked);
    if (!u) return `<p class="aside">Pick who stays to board on the left.</p>`;
    return `<div class="rstand"><div class="nm">${esc(u.name)}</div>
        <div class="prog"><div class="bar"><i style="width:${Math.min(100, 100 * u.done / Math.max(1, u.total))}%"></i></div>
        <span>${esc(u.stage)}</span></div>
        <p class="use">${esc(u.status)}</p></div>
      <div class="brass-btn wide" id="begin"><div><b>${esc(I.action)} · ${esc(u.name)}</b></div></div>`;
  }

  function draw(I) {
    cards(I.cards);
    const terms = I.terms.map(t =>
      `<div class="billrow rterm"><span class="lbl">${esc(t.label)}</span><span class="${t.ok ? "" : "bad"}">${esc(t.value)}</span></div>`).join("");
    const report = I.report.length
      ? `<div class="report"><div class="kicker">The sanctuary</div>${I.report.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">Who stays</div>
        <p class="hint">Click a member to leave them boarding for the rite.</p>
        <div class="crew">${I.members.map(member).join("")}</div></div>
      <div class="paper ledger"><div class="kicker">The ${esc(I.school)} rite <em>${esc(I.faction)}</em></div>
        <div class="bill">${terms}</div>${standing(I)}${report}
        <div class="ledgerfoot"><p>Reputation is the door, not the price: it is never spent. Leave the rite and the points are kept.</p></div></div>`;
    toast(I.notice);
  }

  $("body").addEventListener("click", async e => {
    if (!H || !H.initiation) return;
    const p = e.target.closest("[data-uid]");
    if (p) { Sound.play("click"); post("novice", {uid: p.dataset.uid}); return; }
    if (e.target.closest("#begin")) { Sound.play("click"); post("begin_rite"); }
  });

  return {draw};
})();

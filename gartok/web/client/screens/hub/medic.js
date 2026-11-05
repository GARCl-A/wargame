// The Apothecary's MEDIC tab: the ward on leather (each patient with what ails them and the price; click
// to pick), the bill on paper (the picked ones itemised, the total, who waits) and the button that treats
// them. Visits combine; a hospital stay is picked alone. The pick lives on the server.
"use strict";

const Medic = (() => {
  const chip = p => `<span class="chip">${esc(p.label)}</span>`;

  function patient(u) {
    return `<div class="worker patient ${u.picked ? "on" : ""}" data-uid="${esc(u.uid)}">
      <div class="medal">${face(u.portrait, u.name)}</div>
      <div class="who"><h3>${esc(u.name)}</h3><div class="race">${esc(u.sub)}</div>
        <div class="chips">${u.parts.map(chip).join("")}${u.stay ? `<span class="chip bad">${tr("medic.stay")}</span>` : ""}</div></div>
      <div class="pay"><b>${money(u.cost)}</b><span class="lbl">${tr("unit.h", {n: u.hours})}</span></div></div>`;
  }

  function bill(M) {
    const picked = M.ward.filter(u => u.picked);
    if (!picked.length) return `<p class="aside">${tr("medic.pick_left")}</p>`;
    const rows = picked.map(u => `<div class="billwho">${esc(u.name)}</div>` + u.parts.map(p =>
      `<div class="billrow"><span>${esc(p.label)}</span><span class="h">${tr("unit.h", {n: p.hours})}</span><b>${money(p.cost)}</b></div>`).join("")).join("");
    const who = M.stay || tr("medic.group_waits");
    const label = M.can_pay ? tr(M.stay ? "medic.admit" : "medic.treat", {cost: money(M.cost)}) : tr("medic.cannot_pay");
    return `<div class="bill">${rows}</div>
      <div class="billtotal"><span>${tr("medic.total")}</span><span class="h">${tr("unit.h", {n: M.hours})}</span><b class="${M.can_pay ? "" : "bad"}">${money(M.cost)}</b></div>
      <p class="aside">${esc(who.charAt(0).toUpperCase() + who.slice(1))}.</p>
      <div class="brass-btn wide ${M.can_pay ? "" : "off"}" id="treat"><div><b>${label}</b></div></div>`;
  }

  function draw(M) {
    cards(M.cards);
    const ward = M.ward.length ? M.ward.map(patient).join("") : `<p class="hint">${tr("medic.nobody")}</p>`;
    const fine = M.fine.length ? `<p class="hint">${tr("medic.fine", {names: esc(M.fine.join(", "))})}</p>` : "";
    const report = M.report.length
      ? `<div class="report"><div class="kicker">${tr("medic.last_visit")}</div>${M.report.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${tr("medic.ward")}</div>
        <p class="hint">${tr("medic.ward_hint")}</p><div class="crew">${ward}</div>${fine}</div>
      <div class="paper ledger"><div class="kicker">${tr("medic.bill")} <em>${tr("medic.bill_note")}</em></div>
        ${bill(M)}${report}
        <div class="ledgerfoot"><p>${tr("medic.foot", {hours: M.max_hours})}</p></div></div>`;
    toast(M.notice);
  }

  $("body").addEventListener("click", async e => {
    if (!H || !H.medic) return;
    const p = e.target.closest("[data-uid]");
    if (p) { post("patient", {uid: p.dataset.uid}); return; }
    const t = e.target.closest("#treat");
    if (t && !t.classList.contains("off")) {
      const r = await post("treat");
      if (r) Sound.play("coins");
    }
  });

  return {draw};
})();

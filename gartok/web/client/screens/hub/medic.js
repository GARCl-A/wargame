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
        <div class="chips">${u.parts.map(chip).join("")}${u.stay ? `<span class="chip bad">hospital stay</span>` : ""}</div></div>
      <div class="pay"><b>${money(u.cost)}</b><span class="lbl">${u.hours} h</span></div></div>`;
  }

  function bill(M) {
    const picked = M.ward.filter(u => u.picked);
    if (!picked.length) return `<p class="aside">Pick who to treat on the left.</p>`;
    const rows = picked.map(u => `<div class="billwho">${esc(u.name)}</div>` + u.parts.map(p =>
      `<div class="billrow"><span>${esc(p.label)}</span><span class="h">${p.hours} h</span><b>${money(p.cost)}</b></div>`).join("")).join("");
    const who = M.stay || "the whole group waits while they are treated";
    const label = M.can_pay ? `${M.stay ? "Admit" : "Treat"} · ${money(M.cost)}` : "Cannot pay";
    return `<div class="bill">${rows}</div>
      <div class="billtotal"><span>Total</span><span class="h">${M.hours} h</span><b class="${M.can_pay ? "" : "bad"}">${money(M.cost)}</b></div>
      <p class="aside">${esc(who.charAt(0).toUpperCase() + who.slice(1))}.</p>
      <div class="brass-btn wide ${M.can_pay ? "" : "off"}" id="treat"><div><b>${label}</b></div></div>`;
  }

  function draw(M) {
    cards(M.cards);
    const ward = M.ward.length ? M.ward.map(patient).join("") : `<p class="hint">Nobody here needs treating.</p>`;
    const fine = M.fine.length ? `<p class="hint">In good health: ${esc(M.fine.join(", "))}.</p>` : "";
    const report = M.report.length
      ? `<div class="report"><div class="kicker">The last visit</div>${M.report.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">The ward</div>
        <p class="hint">Click a patient to add them to the bill.</p><div class="crew">${ward}</div>${fine}</div>
      <div class="paper ledger"><div class="kicker">The bill <em>potions and doses at a discount while the group waits</em></div>
        ${bill(M)}${report}
        <div class="ledgerfoot"><p>Past ${M.max_hours} h a treatment is a hospital stay: the patient leaves the group until cured, or the whole group waits with no free group slot.</p></div></div>`;
    toast(M.notice);
  }

  $("body").addEventListener("click", async e => {
    if (!H || !H.medic) return;
    const p = e.target.closest("[data-uid]");
    if (p) { Sound.play("click"); post("patient", {uid: p.dataset.uid}); return; }
    const t = e.target.closest("#treat");
    if (t && !t.classList.contains("off")) {
      const r = await post("treat");
      if (r) Sound.play("coins");
    }
  });

  return {draw};
})();

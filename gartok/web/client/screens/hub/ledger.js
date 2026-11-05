// Ledger Hold's desk: the band here on leather (who carries the Bankers' chest or the letter), on paper the
// desk's panels side by side: the chest to hand over, Commander Varkas's mentorship, the frontier supply run,
// or the gatehouse. The supply run leaves for the map; the rest is done here and the tab stays up.
"use strict";

const Ledger = (() => {
  function member(u) {
    const chips = [u.chest && `<span class="chip money">${tr("ledger.chest")}</span>`,
                   u.letter && `<span class="chip">${tr("ledger.letter")}</span>`].filter(Boolean).join("");
    return `<div class="worker slim">
      <div class="medal">${face(u.portrait, u.name)}</div>
      <div class="who"><h3>${esc(u.name)}</h3><div class="race">${esc(u.sub)}</div>
        ${chips ? `<div class="chips">${chips}</div>` : ""}</div></div>`;
  }

  function panel(p) {
    const rows = p.rows.map(r =>
      `<div class="dfact"><span class="lbl">${esc(r.label)}</span><b class="${r.tone || ""}">${esc(r.value)}</b></div>`).join("");
    const lines = p.lines.map(l => `<p>${esc(l)}</p>`).join("");
    const b = p.button;
    const btn = b ? `<div class="brass-btn ${b.can ? "" : "off"}" data-desk="${b.key}"><div><b>${esc(b.label)}</b></div></div>` : "";
    return `<div class="desk"><h3>${esc(p.title)}</h3>${p.aside ? `<div class="daside">${esc(p.aside)}</div>` : ""}
      ${lines ? `<div class="cstage">${lines}</div>` : ""}${rows}${btn}
      ${p.warn ? `<p class="dwarn">${esc(p.warn)}</p>` : ""}</div>`;
  }

  function draw(L) {
    cards(L.cards);
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${tr("ledger.here", {members: trn("unit.member", L.members.length)})}</div>
        <p class="hint">${tr("ledger.hint")}</p>
        <div class="crew">${L.members.map(member).join("")}</div></div>
      <div class="paper ledger"><div class="kicker">${tr("ledger.desk")} <em>${tr("ledger.place")}</em></div>
        <div class="desks">${L.panels.map(panel).join("")}</div>
        <div class="ledgerfoot"><p>${tr("ledger.foot")}</p></div></div>`;
    toast(L.notice);
  }

  $("body").addEventListener("click", e => {
    if (!H || !H.ledger) return;
    const b = e.target.closest("[data-desk]");
    if (!b || b.classList.contains("off")) return;
    post("ledger", {key: b.dataset.desk});
  });

  return {draw};
})();

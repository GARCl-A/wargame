// A giver's JOBS tab: the board on paper (each job with what it asks, pays and when it is due, its state
// and its button) and, on leather, who signs for the band and what the packs already carry toward each
// goal. A keeper who buys dragon eggs offers the sale under it. Every verb answers the whole hub.
"use strict";

const Jobs = (() => {
  const tag = t => `<span class="tag ${t.tone}">${esc(t.label)}</span>`;

  function job(j) {
    const b = j.button;
    const state = j.taken ? (j.ready ? "ready" : "taken") : j.out ? "out" : "";
    return `<div class="job ${state}">
      <div class="ico mask" style="--icon:url(/assets/icons/${j.glyph}.svg)"></div>
      <div class="jbody"><div class="jhead"><span class="nm">${esc(j.name)}</span>${j.tags.map(tag).join("")}</div>
        ${j.blurb ? `<p class="use">${esc(j.blurb)}</p>` : ""}
        <div class="terms">${j.detail.map(d => `<span>${esc(d)}</span>`).join("")}</div></div>
      <div class="btn ${b.on ? "" : "off"}" data-job="${esc(j.id)}" data-verb="${b.verb}">${esc(b.label)}</div></div>`;
  }

  function carried(c) {
    const who = c.who.length ? c.who.join(", ") : "nobody carries any";
    return `<div class="it carry"><span class="ico mask" style="--icon:url(/assets/icons/${c.glyph}.svg)"></span>
      <span class="nm">${esc(c.item)}<small>${esc(who)}</small></span>
      <b class="${c.have >= c.goal ? "good" : ""}">${c.have} / ${c.goal}</b></div>`;
  }

  function draw(J) {
    cards(J.cards);
    const s = J.signer;
    const egg = J.egg
      ? `<div class="brass-btn wide ${J.egg.on ? "" : "off"}" id="egg"><div><b>${esc(J.egg.label)}</b></div></div>` : "";
    const packs = J.carried.length ? `<div class="carrying"><div class="lbl">In the packs</div>
        <p class="hint">What the band already carries toward each job on the board.</p>${J.carried.map(carried).join("")}</div>` : "";
    const board = J.jobs.length ? J.jobs.map(job).join("") : `<p class="aside">Nothing on offer here right now.</p>`;
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">Who signs</div>
        <div class="crew"><div class="worker"><div class="medal">${face(s.portrait, s.name)}</div>
          <div class="who"><h3>${esc(s.name)}</h3><div class="race">${esc(s.sub)}</div></div></div></div>
        <p class="hint">The leader signs, and the job travels with them: whichever band they walk with hands it over.</p>
        ${packs}${egg}</div>
      <div class="paper ledger"><div class="kicker">The board <em>${esc(J.line)}</em></div>
        <div class="jobs">${board}</div>
        <div class="ledgerfoot"><p>A job is taken once. The pay is split across the band that hands it over; past its deadline it fails.</p></div></div>`;
    toast(J.notice);
  }

  $("body").addEventListener("click", async e => {
    if (!H || !H.jobs) return;
    const b = e.target.closest("[data-job]");
    if (b && !b.classList.contains("off")) {
      const r = await post(b.dataset.verb, {id: b.dataset.job});
      if (r) Sound.play(b.dataset.verb === "turn_in" ? "coins" : "click");
      return;
    }
    const egg = e.target.closest("#egg");
    if (egg && !egg.classList.contains("off")) {
      const r = await post("sell_egg");
      if (r) Sound.play("coins");
    }
  });

  return {draw};
})();

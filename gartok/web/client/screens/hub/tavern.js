// The Tavern's three tabs. RECRUIT: the strangers drinking here on leather (click to read one), the picked
// one's dossier on paper with who makes the pitch and the button that rolls it. STUDY: the rooms on leather,
// each member's study target on paper (a scroll or dictionary the band carries). PERFORM: who plays on leather
// (click to seat or stand down), the show's length and its tips on paper. The City Prison's cells are RECRUIT
// with a bail. Every verb answers the whole hub.
"use strict";

const Tavern = (() => {
  let picking = null;               // the member whose study target list is open
  const status = s => `<span class="tstat ${s.tone}">${esc(s.text)}</span>`;
  const chips = list => list.length
    ? `<div class="chips">${list.map(c => `<span class="chip ${c.tone}"${tip(c.tip)}>${esc(c.label)}</span>`).join("")}</div>` : "";
  const report = (title, lines) => lines.length
    ? `<div class="report"><div class="kicker">${title}</div>${lines.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";

  function stranger(c) {
    return `<div class="worker patient ${c.picked ? "on" : ""}" data-cand="${esc(c.uid)}">
      <div class="medal">${face(c.portrait, c.name)}</div>
      <div class="who"><h3>${esc(c.name)}</h3><div class="race">${esc(c.sub)}</div>
        <div class="race">${esc(c.note)}</div>${chips(c.chips)}</div>
      <div class="pay">${status(c.status)}</div></div>`;
  }

  function signed(s) {
    return `<div class="signed"><div class="medal">${face(s.portrait, s.name)}</div>
      <div><div class="lbl">${tr("tavern.signed_lbl", {by: esc(s.by)})}</div>
        <p class="line">${esc(s.name)}: “${esc(s.line)}”</p><p class="use">${esc(s.sub)}</p></div>
      <b class="mark">✕ ${esc(s.name)}</b></div>`;
  }

  function last(l) {
    if (!l) return "";
    if (!l.ours) return `<p class="lastpitch bad">${esc(l.by)}: ${esc(l.line)}</p>`;
    return `<p class="lastpitch ${l.ok ? "good" : "bad"}">${tr(l.ok ? "tavern.pitch_signed" : "tavern.pitch_down", {by: esc(l.by), lang: esc(l.lang), ours: esc(l.ours), ours_total: l.ours_total, theirs: esc(l.theirs), theirs_total: l.theirs_total})}</p>`;
  }

  function dossier(d) {
    const facts = d.facts.map(([k, v]) => `<span><em>${esc(k)}</em>${esc(v)}</span>`).join("");
    const kit = d.kit.map(i => `<span class="ico mask"${tip(i.name)} style="--icon:url(/assets/icons/${i.glyph}.svg)"></span>`).join("");
    const pitchers = d.pitchers.map(m => `<div class="pitcher ${m.picked ? "on" : ""} ${m.signed ? "signed" : ""}" data-pitcher="${esc(m.uid)}">
        <div class="medal">${face(m.portrait, m.name)}</div>
        <div><div class="nm">${esc(m.name)}${m.signed ? ` · ${tr("tavern.signed")}` : ""}</div><div class="use">${esc(m.sub)}</div></div>
        ${status(m.status)}</div>`).join("");
    return `<div class="dossier"><div class="medal">${face(d.portrait, d.name)}</div>
        <div><div class="jhead"><span class="nm">${esc(d.name)}</span></div><p class="use">${esc(d.sub)}</p>
          <div class="dfacts">${facts}<span class="kit">${kit}</span></div>
          <div class="chips">${d.chips.map(c => `<span class="tag ${c.tone}"${tip(c.tip)}>${esc(c.label)}</span>`).join("")}</div>
          <p class="ability"><b>${esc(d.ability.name)}</b> ${esc(d.ability.effect)}</p></div></div>
      ${d.bail ? `<div class="offer ${d.bail.ok ? "" : "bad"}"><div class="line">
          <span class="was">${tr("tavern.bail")} <b>${esc(d.bail.base)}</b></span><span class="dot">·</span><span class="lbl">${tr("tavern.offering")}</span>
          <div class="btn ${d.bail.less ? "" : "off"}" id="bail_less"${tip(tr("tavern.halve"))}>÷2</div>
          <b class="sum">${esc(d.bail.cost)}</b>
          <div class="btn ${d.bail.more ? "" : "off"}" id="bail_more"${tip(tr("tavern.double"))}>×2</div>
          <span class="lbl">${tr("tavern.for")}</span><b class="plus">+${d.bail.bonus}</b><span class="lbl">${tr("tavern.on_pitch")}</span></div>
        <p class="note">${tr("tavern.bail_note", {held: esc(d.bail.held)})}</p></div>` : ""}
      ${last(d.last)}
      <div class="sec dark"><span class="lbl">${tr("tavern.who_pitches")}</span></div>
      <div class="pitchers">${pitchers}</div>
      <div class="pterms">${d.terms.map(t => `<div class="fact"><span class="lbl">${esc(t.label)}</span><b class="${t.tone}">${esc(t.value)}</b><span class="use">${esc(t.note)}</span></div>`).join("")}</div>
      ${d.hint ? `<p class="aside ${d.hint.tone}">${esc(d.hint.text.charAt(0).toUpperCase() + d.hint.text.slice(1))}</p>` : ""}
      <div class="brass-btn wide ${d.button.on ? "" : "off"}" id="convince"><div><b>${esc(d.button.label)}</b></div></div>`;
  }

  function recruits(R) {
    const list = R.strangers.length ? R.strangers.map(stranger).join("") : `<p class="hint">${esc(R.empty)}</p>`;
    const body = R.dossier ? dossier(R.dossier)
      : `<p class="aside">${R.signed ? "" : tr("tavern.pick_stranger")}</p>`;
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${R.prison ? tr("tavern.prisoners") : tr("tavern.strangers")}</div>
        <p class="hint">${tr(R.prison ? "tavern.tie_prisoner" : "tavern.tie_stranger")}</p>
        <div class="crew">${list}</div></div>
      <div class="paper ledger recruit"><div class="kicker">${tr("tavern.dossier")} <em>${tr("tavern.dossier_note")}</em></div>
        <div class="rbody">${R.signed ? signed(R.signed) : ""}${body}</div>
        <div class="ledgerfoot"><p>${esc(R.foot)}</p></div></div>`;
    const fresh = $("body").querySelector(".pitcher.signed");
    if (fresh) fresh.scrollIntoView({block: "nearest"});
  }

  function student(m) {
    const t = m.target;
    const target = t
      ? `<div><div class="nm good">${esc(t.name)}</div><div class="prog"><div class="bar"><i style="width:${Math.min(100, 100 * t.progress / Math.max(1, t.needed))}%"></i></div>
           <span>${tr("tavern.pts", {have: t.progress, need: t.needed})}</span></div></div>`
      : `<div><div class="use">${tr("tavern.no_target")}</div><div class="use faint">${tr("tavern.idle")}</div></div>`;
    const btns = (t ? `<div class="btn" data-stop="${esc(m.uid)}">${tr("tavern.stop")}</div>` : "")
      + `<div class="btn" data-pick="${esc(m.uid)}">${t ? tr("tavern.change") : tr("tavern.set_target")}</div>`;
    let opts = "";
    if (picking === m.uid) {
      opts = m.options.length
        ? m.options.map(o => `<div class="opt"><div><div class="nm">${esc(o.name)}</div><div class="use">${esc(o.desc)}</div></div>
            <div class="btn" data-uid="${esc(m.uid)}" data-target="${esc(o.id)}">${tr("tavern.select")}</div></div>`).join("")
        : `<div class="opt none"><p class="use">${m.affinity ? tr("tavern.no_fit") : tr("tavern.no_affinity", {name: esc(m.name)})}
            ${tr("tavern.opts_note")}</p></div>`;
      opts = `<div class="opts">${opts}</div>`;
    }
    return `<div class="student ${picking === m.uid ? "open" : ""}"><div class="medal">${face(m.portrait, m.name)}</div>
      <div><div class="nm">${esc(m.name)}</div><div class="use">${esc(m.sub)}</div></div>${target}<div class="sbtns">${btns}</div></div>${opts}`;
  }

  function rooms(S) {
    const act = S.studying
      ? `<div class="fact"><span class="lbl">${tr("tavern.now")}</span><b class="good">${tr("tavern.studies_daily")}</b></div>
         <div class="brass-btn wide" id="cancel_study"><div><b>${tr("tavern.cancel_study")}</b></div></div>`
      : `<div class="brass-btn wide ${S.studiers ? "" : "off"}" id="rent_study"><div><b>${tr("tavern.rent_rooms")}</b></div></div>
         ${S.studiers ? "" : `<p class="hint">${tr("tavern.set_target_first")}</p>`}`;
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${tr("tavern.study_rooms")}</div>
        <p class="hint">${tr("tavern.rooms_hint")}</p>
        <div class="fact"><span class="lbl">${tr("tavern.rent")}</span><b>${tr("tavern.rent_val", {cost: money(S.cost)})}</b></div>
        <div class="fact"><span class="lbl">${tr("tavern.today")}</span><b>${tr("tavern.today_val", {cost: money(S.today), n: S.studiers})}</b></div>
        <div class="fact"><span class="lbl">${tr("tavern.progress")}</span><b>${tr("tavern.progress_val")}</b></div>
        ${act}</div>
      <div class="paper ledger"><div class="kicker">${tr("tavern.who_studies")} <em>${tr("tavern.who_studies_note")}</em></div>
        <div class="students">${S.students.map(student).join("")}</div>
        <div class="ledgerfoot"><p>${tr("tavern.rooms_foot")}</p></div></div>`;
  }

  function perform(P) {
    const players = P.players.map(m => `<div class="worker ${m.has ? "patient" : "out"} ${m.on ? "on" : ""}" ${m.has ? `data-seat="${esc(m.uid)}"` : ""}>
        <div class="medal">${face(m.portrait, m.name)}</div>
        <div class="who"><h3>${esc(m.name)}</h3><div class="race">${esc(m.sub)}</div></div>
        <div class="pay ${m.on && m.tips ? "good" : ""}">${m.on ? `<b>~${money(m.tips)}</b><span class="lbl">${tr("tavern.on_average")}</span>`
          : `<span class="tstat faint">${m.has ? tr("tavern.sitting_out") : tr("tavern.no_item", {item: esc(P.item.toLowerCase())})}</span>`}</div></div>`).join("");
    const lengths = P.lengths.map(h => `<div class="btn ${h === P.hours ? "on" : ""}" data-show="${h}">${tr("unit.h", {n: h})}</div>`).join("");
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${tr("tavern.performers")}</div>
        <p class="hint">${tr("tavern.perform_hint", {item: esc(P.item)})}</p>
        <div class="crew">${players}</div></div>
      <div class="paper ledger"><div class="kicker">${tr("tavern.stage")} <em>${tr("tavern.stage_note")}</em></div>
        <div class="terms stage"><span><b>${tr("tavern.test")}</b> ${tr("tavern.test_val", {base: P.base})}</span>
          <span><b>${tr("tavern.tips")}</b> ${tr("tavern.tips_val", {step: P.step, base: P.base})}</span>
          <span><b>${tr("tavern.needs")}</b> ${tr("tavern.needs_val", {item: esc(P.item)})}</span></div>
        <div class="hrow show"><span class="lbl">${tr("tavern.show_length")}</span>${lengths}</div>
        <div class="brass-btn wide ${P.can ? "" : "off"}" id="perform"><div><b>${P.can ? tr("tavern.play", {n: P.hours}) : tr("tavern.nobody_plays")}</b></div></div>
        ${report(tr("tavern.last_show"), P.report)}
        <div class="ledgerfoot"><p>${tr("tavern.perform_foot")}</p></div></div>`;
  }

  function draw(T, tab) {
    cards(T.cards);
    if (tab !== "rooms") picking = null;
    if (tab === "recruits" || tab === "prison") recruits(T);
    else if (tab === "rooms") rooms(T);
    else perform(T);
    toast(T.notice);
  }

  async function act(verb, body, sound = null) {
    const r = await post(verb, body);
    if (r && sound) Sound.play(sound);
    return r;
  }

  $("body").addEventListener("click", e => {
    if (!H || !H.tavern) return;
    const on = sel => { const el = e.target.closest(sel); return el && !el.classList.contains("off") ? el : null; };
    let el;
    if ((el = on("[data-cand]"))) act("candidate", {uid: el.dataset.cand});
    else if ((el = on("[data-pitcher]"))) act("recruiter", {uid: el.dataset.pitcher});
    else if (on("#bail_more")) act("raise_bail", {delta: 1});
    else if (on("#bail_less")) act("raise_bail", {delta: -1});
    else if (on("#convince")) act("convince");
    else if ((el = on("[data-target]"))) { picking = null; act("study_target", {uid: el.dataset.uid, id: el.dataset.target}); }
    else if ((el = on("[data-pick]"))) { picking = picking === el.dataset.pick ? null : el.dataset.pick; rooms(H.tavern); }
    else if ((el = on("[data-stop]"))) act("stop_study", {uid: el.dataset.stop});
    else if (on("#rent_study")) act("rent_study");
    else if (on("#cancel_study")) act("cancel_study");
    else if ((el = on("[data-seat]"))) act("seat", {uid: el.dataset.seat});
    else if ((el = on("[data-show]"))) act("show_hours", {hours: +el.dataset.show});
    else if (on("#perform")) act("perform", {}, "coins");
  });

  return {draw};
})();

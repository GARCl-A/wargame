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
    ? `<div class="chips">${list.map(c => `<span class="chip ${c.tone}" title="${esc(c.tip)}">${esc(c.label)}</span>`).join("")}</div>` : "";
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
      <div><div class="lbl">Contract signed · joins ${esc(s.by)}'s roster</div>
        <p class="line">${esc(s.name)}: “${esc(s.line)}”</p><p class="use">${esc(s.sub)}</p></div>
      <b class="mark">✕ ${esc(s.name)}</b></div>`;
  }

  function last(l) {
    if (!l) return "";
    if (!l.ours) return `<p class="lastpitch bad">${esc(l.by)}: ${esc(l.line)}</p>`;
    return `<p class="lastpitch ${l.ok ? "good" : "bad"}">${esc(l.by)}'s pitch in ${esc(l.lang)}: ${esc(l.ours)} = <b>${l.ours_total}</b>
      against ${esc(l.theirs)} = <b>${l.theirs_total}</b> · ${l.ok ? "signed" : "turned down"}</p>`;
  }

  function dossier(d) {
    const facts = d.facts.map(([k, v]) => `<span><em>${esc(k)}</em>${esc(v)}</span>`).join("");
    const kit = d.kit.map(i => `<span class="ico mask" title="${esc(i.name)}" style="--icon:url(/assets/icons/${i.glyph}.svg)"></span>`).join("");
    const pitchers = d.pitchers.map(m => `<div class="pitcher ${m.picked ? "on" : ""} ${m.signed ? "signed" : ""}" data-pitcher="${esc(m.uid)}">
        <div class="medal">${face(m.portrait, m.name)}</div>
        <div><div class="nm">${esc(m.name)}${m.signed ? " · signed" : ""}</div><div class="use">${esc(m.sub)}</div></div>
        ${status(m.status)}</div>`).join("");
    return `<div class="dossier"><div class="medal">${face(d.portrait, d.name)}</div>
        <div><div class="jhead"><span class="nm">${esc(d.name)}</span></div><p class="use">${esc(d.sub)}</p>
          <div class="dfacts">${facts}<span class="kit">${kit}</span></div>
          <div class="chips">${d.chips.map(c => `<span class="tag ${c.tone}" title="${esc(c.tip)}">${esc(c.label)}</span>`).join("")}</div>
          <p class="ability"><b>${esc(d.ability.name)}</b> ${esc(d.ability.effect)}</p></div></div>
      ${d.bail ? `<p class="lastpitch ${d.bail.ok ? "money" : "bad"}">Bail <b>${esc(d.bail.cost)}</b> · the band holds ${esc(d.bail.held)}</p>` : ""}
      ${last(d.last)}
      <div class="sec dark"><span class="lbl">Who makes the pitch</span></div>
      <div class="pitchers">${pitchers}</div>
      ${d.hint ? `<p class="aside ${d.hint.tone}">${esc(d.hint.text.charAt(0).toUpperCase() + d.hint.text.slice(1))}</p>` : ""}
      <div class="brass-btn wide ${d.button.on ? "" : "off"}" id="convince"><div><b>${esc(d.button.label)}</b></div></div>`;
  }

  function recruits(R) {
    const list = R.strangers.length ? R.strangers.map(stranger).join("") : `<p class="hint">${esc(R.empty)}</p>`;
    const body = R.dossier ? dossier(R.dossier)
      : `<p class="aside">${R.signed ? "" : "Pick a stranger on the left to read their dossier and make a pitch."}</p>`;
    const foot = R.prison
      ? "The bail is paid before the pitch and buys +2 on it. Turned down, the prisoner walks free with the coin, and the one who pitched may not try them again until the cells turn over."
      : "Opposite alignment docks the pitch a point a step, and so does every member past the second. Turned down, the one who pitched may not try that stranger again until the crowd changes.";
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${R.prison ? "Prisoners in the cells" : "Strangers in the tavern"}</div>
        <p class="hint">Charisma against Charisma, in a tongue both speak; a tie goes to the ${R.prison ? "prisoner" : "stranger"}.</p>
        <div class="crew">${list}</div></div>
      <div class="paper ledger"><div class="kicker">Dossier <em>who they are and who could talk them into the guild</em></div>
        ${R.signed ? signed(R.signed) : ""}${body}
        <div class="ledgerfoot"><p>${foot}</p></div></div>`;
  }

  function student(m) {
    const t = m.target;
    const target = t
      ? `<div><div class="nm good">${esc(t.name)}</div><div class="prog"><div class="bar"><i style="width:${Math.min(100, 100 * t.progress / Math.max(1, t.needed))}%"></i></div>
           <span>${t.progress} / ${t.needed} pts</span></div></div>`
      : `<div><div class="use">No study target</div><div class="use faint">idle in the study hours, no progress</div></div>`;
    const btns = (t ? `<div class="btn" data-stop="${esc(m.uid)}">Stop</div>` : "")
      + `<div class="btn" data-pick="${esc(m.uid)}">${t ? "Change" : "Set target"}</div>`;
    let opts = "";
    if (picking === m.uid) {
      opts = m.options.length
        ? m.options.map(o => `<div class="opt"><div><div class="nm">${esc(o.name)}</div><div class="use">${esc(o.desc)}</div></div>
            <div class="btn" data-uid="${esc(m.uid)}" data-target="${esc(o.id)}">Select</div></div>`).join("")
        : `<div class="opt none"><p class="use">${m.affinity ? "No scroll or dictionary the band carries fits." : `${esc(m.name)} has no magical affinity and the band carries no dictionary they lack.`}
            A scroll needs a matching affinity; a dictionary teaches a foreign language. Write one at the Library with paper and ink, or find scrolls in the ruins.</p></div>`;
      opts = `<div class="opts">${opts}</div>`;
    }
    return `<div class="student ${picking === m.uid ? "open" : ""}"><div class="medal">${face(m.portrait, m.name)}</div>
      <div><div class="nm">${esc(m.name)}</div><div class="use">${esc(m.sub)}</div></div>${target}<div class="sbtns">${btns}</div></div>${opts}`;
  }

  function rooms(S) {
    const act = S.studying
      ? `<div class="fact"><span class="lbl">Now</span><b class="good">the band studies here daily</b></div>
         <div class="brass-btn wide" id="cancel_study"><div><b>Cancel the study order</b></div></div>`
      : `<div class="brass-btn wide ${S.studiers ? "" : "off"}" id="rent_study"><div><b>Rent rooms</b></div></div>
         ${S.studiers ? "" : `<p class="hint">Set a study target for someone before renting rooms.</p>`}`;
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">Study rooms</div>
        <p class="hint">A quiet room for the day: anyone with a study target makes progress.</p>
        <div class="fact"><span class="lbl">Rent</span><b>${money(S.cost)} a day for each member who studies</b></div>
        <div class="fact"><span class="lbl">Today</span><b>${money(S.today)} for ${S.studiers} studying</b></div>
        <div class="fact"><span class="lbl">Progress</span><b>a daily roll on Intelligence toward the target's points</b></div>
        ${act}</div>
      <div class="paper ledger"><div class="kicker">Who studies <em>a scroll or a dictionary the band carries, one target each</em></div>
        <div class="students">${S.students.map(student).join("")}</div>
        <div class="ledgerfoot"><p>Renting the rooms puts the band on a post here: the days pass on the map, each one paid and rolled, until it is recalled.</p></div></div>`;
  }

  function perform(P) {
    const players = P.players.map(m => `<div class="worker ${m.has ? "patient" : "out"} ${m.on ? "on" : ""}" ${m.has ? `data-seat="${esc(m.uid)}"` : ""}>
        <div class="medal">${face(m.portrait, m.name)}</div>
        <div class="who"><h3>${esc(m.name)}</h3><div class="race">${esc(m.sub)}</div></div>
        <div class="pay ${m.on && m.tips ? "good" : ""}">${m.on ? `<b>~${money(m.tips)}</b><span class="lbl">on average</span>`
          : `<span class="tstat faint">${m.has ? "sitting out" : `no ${esc(P.item.toLowerCase())}`}</span>`}</div></div>`).join("");
    const lengths = P.lengths.map(h => `<div class="btn ${h === P.hours ? "on" : ""}" data-show="${h}">${h} h</div>`).join("");
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">Performers</div>
        <p class="hint">Click to seat or stand down; only who carries a ${esc(P.item)} can play.</p>
        <div class="crew">${players}</div></div>
      <div class="paper ledger"><div class="kicker">The stage <em>every hour on stage is a Charisma test the crowd tips on</em></div>
        <div class="terms stage"><span><b>Test</b> d20 + Charisma each hour: beat ${P.base} and the crowd tips</span>
          <span><b>Tips</b> one more coin for every ${P.step} points over ${P.base}</span>
          <span><b>Needs</b> a ${esc(P.item)} in the pack</span></div>
        <div class="hrow show"><span class="lbl">Show length</span>${lengths}</div>
        <div class="brass-btn wide ${P.can ? "" : "off"}" id="perform"><div><b>${P.can ? `Play ${P.hours} h` : "Nobody seated can play"}</b></div></div>
        ${report("The last show", P.report)}
        <div class="ledgerfoot"><p>The clock runs while the band plays: the whole band waits out the show, and eats as it goes.</p></div></div>`;
  }

  function draw(T, tab) {
    cards(T.cards);
    if (tab !== "rooms") picking = null;
    if (tab === "recruits" || tab === "prison") recruits(T);
    else if (tab === "rooms") rooms(T);
    else perform(T);
    toast(T.notice);
  }

  async function act(verb, body, sound = "click") {
    const r = await post(verb, body);
    if (r) Sound.play(sound);
    return r;
  }

  $("body").addEventListener("click", e => {
    if (!H || !H.tavern) return;
    const on = sel => { const el = e.target.closest(sel); return el && !el.classList.contains("off") ? el : null; };
    let el;
    if ((el = on("[data-cand]"))) act("candidate", {uid: el.dataset.cand});
    else if ((el = on("[data-pitcher]"))) act("recruiter", {uid: el.dataset.pitcher});
    else if (on("#convince")) act("convince");
    else if ((el = on("[data-target]"))) { picking = null; act("study_target", {uid: el.dataset.uid, id: el.dataset.target}); }
    else if ((el = on("[data-pick]"))) { picking = picking === el.dataset.pick ? null : el.dataset.pick; Sound.play("click"); rooms(H.tavern); }
    else if ((el = on("[data-stop]"))) act("stop_study", {uid: el.dataset.stop});
    else if (on("#rent_study")) act("rent_study");
    else if (on("#cancel_study")) act("cancel_study");
    else if ((el = on("[data-seat]"))) act("seat", {uid: el.dataset.seat});
    else if ((el = on("[data-show]"))) act("show_hours", {hours: +el.dataset.show});
    else if (on("#perform")) act("perform", {}, "coins");
  });

  return {draw};
})();

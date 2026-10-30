// The arena: pick the bout, pick who fights, stake and fight; after a boss falls, the offer to recruit them.
"use strict";

let A = null, busy = false;
const TAGS = {champion: "the title", boss: "the Games' capstone", brawl: "the Games", ctf: "the Games"};

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.hidden = true; }, 2600);
}

async function post(verb, body = {}) {
  if (busy) return;
  busy = true;
  try {
    const r = await api(`/api/arena/${verb}`, body);
    if (r.screen && r.screen !== "arena") { location.reload(); return; }
    render(r);
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
  }
}

function topBar() {
  $("title").textContent = A.place;
  $("subtitle").innerHTML = `<b>${esc(A.band)}</b> · day ${A.day}, ${esc(A.at)}`;
  if (!A.stake) { $("topright").innerHTML = ""; return; }
  const B = A.bouts.find(b => b.picked);
  $("topright").innerHTML = `<div class="stat"><b>${esc(A.stake.held_text)}</b><span>the band's purses</span></div>
    <div class="stat"><b>${esc(B.purse_text)}</b><span>the purse</span></div>`;
}

function boutsPage() {
  const K = A.keeper;
  let h = K ? `<div class="master"><div class="medal">${face(K.portrait, K.name)}</div>
    <div><b>${esc(K.name)}</b><div class="cap">${esc(K.caption)}</div>${K.line ? `<q>${esc(K.line)}</q>` : ""}</div></div>` : "";
  h += `<div class="kicker">The bouts<em>${A.bouts.length} on the board today</em></div>`;
  for (const b of A.bouts) {
    h += `<div class="bout ${b.picked ? "on" : ""}" data-i="${b.i}">
      <h3>${esc(b.name)}${TAGS[b.kind] ? `<span class="tag">${TAGS[b.kind]}</span>` : ""}</h3>
      <p>${esc(b.blurb)}</p>
      <div class="terms"><span><b>${esc(b.entry_text)}</b>a head</span><span class="purse"><b>${esc(b.purse_text)}</b>purse</span>
        <span><b>${b.foes}</b>${b.foes === 1 ? "foe" : "foes"}</span><span><b>${esc(b.levels)}</b></span></div></div>`;
  }
  $("bouts").innerHTML = h;
  for (const el of $("bouts").querySelectorAll(".bout")) el.onclick = () => post("bout", {i: +el.dataset.i});
}

function member(m) {
  const hurt = m.hp[0] < m.hp[1] ? "hurt" : "";
  const mark = m.unfit ? "unfit" : m.picked ? "fights" : "click to add";
  return `<div class="mem ${m.picked ? "on" : ""} ${m.unfit ? "unfit" : ""}" data-uid="${esc(m.uid)}">
    <div class="mark">${mark}</div>
    <div class="who"><div class="medal">${face(m.portrait, m.name)}</div>
      <div><b>${esc(m.name)}</b><span>${esc(m.race)} ${esc(m.occupation.toLowerCase())}</span></div></div>
    <div class="vit"><div class="${hurt}"><b>${m.hp[0]}/${m.hp[1]}</b><span>HP</span></div><div><b>${m.ac}</b><span>AC</span></div>
      <div><b>${m.md}</b><span>MD</span></div><div><b>${m.speed}</b><span>SPD</span></div></div>
    <div class="arm"><span>${esc(m.weapon)} <em>${esc(m.dmg)}</em></span><span>${esc(m.money_text)} · <em>${esc(m.level)}</em></span></div>
    <div class="flags">${m.title ? `<span class="flag good">Champion of the Pit</span>` : ""}${m.flags.map(f => `<span class="flag ${f.tone}">${esc(f.text)}</span>`).join("")}</div>
  </div>`;
}

function band() {
  const S = A.stake;
  let h = `<div class="head"><span class="lbl">Who fights</span><i>one fighter for each foe they field</i>
    <div class="count">${S.fighters}<small>of ${S.cap}</small></div></div>`;
  if (A.defense) h += `<div class="defnote">${esc(A.defense.line)}</div>`;
  h += `<div class="grid">${A.members.map(member).join("")}</div>`;
  const B = A.bouts.find(b => b.picked);
  h += `<div class="foot"><div class="ledger">
      <div class="sum">${esc(S.cost_text)}<small>the stake</small></div>
      <div class="line">${esc(B.entry_text)} a head × ${S.fighters} ${S.fighters === 1 ? "fighter" : "fighters"}, paid from the whole band's purses (${esc(S.held_text)}). Win and one fighter pockets ${esc(B.purse_text)}.</div>
      ${A.why ? `<div class="why">${esc(A.why)}.</div>` : ""}</div>
    <div class="ghost-btn" id="back">Back to the map</div>
    <div class="seal ${A.why ? "off" : ""}" id="fight">${ico("body/sword-tie")}<b>Stake</b><small>and fight</small></div></div>`;
  $("band").innerHTML = h;
  for (const el of $("band").querySelectorAll(".mem")) el.onclick = () => post("pick", {uid: el.dataset.uid});
  $("back").onclick = () => post("back");
  $("fight").onclick = () => { if (!A.why) post("fight"); };
}

function offer() {
  const R = A.recruit;
  $("offer").hidden = false;
  $("offer").innerHTML = `<div class="paper card"><div class="kicker">${esc(A.place)} · ${esc(A.band)}</div>
    <h2>${esc(R.title)}</h2>
    <div class="faces">${R.faces.map(f => `<div><div class="medal">${face(f.portrait, f.name)}</div><b>${esc(f.name)}</b><span>${esc(f.race)}</span></div>`).join("")}</div>
    ${R.lines.map(l => `<p>${esc(l)}</p>`).join("")}
    <div class="acts"><div class="btn" id="recruit">${esc(R.button)}</div><div class="ghost-btn" id="leave">${esc(R.leave)}</div></div></div>`;
  $("recruit").onclick = () => post("recruit");
  $("leave").onclick = () => post("leave");
}

function render(state) {
  A = state;
  topBar();
  if (A.recruit) { offer(); return; }
  boutsPage();
  band();
}

api("/api/arena/state").then(render);
addEventListener("keydown", e => {
  if (!A) return;
  if (A.recruit) {
    if (e.key === "Enter") post("recruit");
    else if (e.key === "Escape") post("leave");
  } else if (e.key === "Escape") post("back");
  else if (e.key === "Enter" && !A.why) post("fight");
});

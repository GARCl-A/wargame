// The talk before a fight: they speak (the bestiary page), you answer (the cards), who answers (the band).
"use strict";

let T = null, busy = false;
const caps = s => String(s || "").toLowerCase().replace(/(^|\s)\S/g, c => c.toUpperCase());
const stamps = verb => {
  const k = ["bluff", "persuade", "intimidate", "teach"].includes(verb) ? verb : "other";
  return [tr(`talk.stamp.${k}.yes`), tr(`talk.stamp.${k}.no`)];
};
const VCLASS = {attack: "steel", bribe: "purse", surrender: "yield", leave: "yield"};
const ring = () => T.kind === "guard" ? "guard" : "foe";

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
    const r = await api(`/api/talk/${verb}`, body);
    if (r.screen && r.screen !== "talk") { location.reload(); return; }
    render(r, verb === "choose");
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
  }
}

// ---------- the top ----------
function topBar() {
  $("seal").className = "tseal " + T.kind;
  $("seal").innerHTML = ico(T.seal);
  $("title").textContent = T.title;
  $("subtitle").innerHTML = T.kind === "boss"
    ? tr("talk.arena", {band: esc(T.band)})
    : tr("talk.where", {place: esc(T.place), band: esc(T.band), day: T.day, at: T.at});
  $("topright").innerHTML = `<div class="still">${tr("talk.still")}</div>` + (T.kind === "boss" ? ""
    : `<div class="stat"><b>${T.foes.length}</b><span>${tr("talk.facing_you")}</span></div><div class="stat"><b>${esc(T.purse_text)}</b><span>${tr("talk.purses")}</span></div>`);
}

// ---------- they speak ----------
function foePage() {
  const L = T.leader;
  if (!L) return "";
  const m = T.line.match(/^\s*"([^"]+)"\s*(.*)$/);
  const said = m ? m[1] : T.line, narr = m ? m[2] : "";
  const boss = T.kind === "boss";
  const now = boss ? T.lines.findIndex(l => l.at === "now") + 1 : 0;
  const head = boss ? tr("talk.speaks_now") : T.kind === "guard" ? tr("talk.sergeant") : tr("talk.speaks_for");
  let h = `<div class="kicker">${head}<em>${boss ? tr("talk.of", {a: now, b: T.lines.length}) : tr("talk.follow")}</em></div>
    <div class="plate"><div class="medal ${ring()}">${face(L.portrait, L.name)}</div>
      <div class="who"><b>${esc(L.name)}</b><div class="cap">${esc(caps(L.caption))}</div>
      <div class="meta">${L.languages.length ? tr("talk.speaks_langs", {langs: esc(L.languages.join(", "))}) : tr("talk.no_tongue")}<br>${esc(L.alignment.toLowerCase())}</div></div></div>
    <div class="speech">${esc(said)}</div>${narr ? `<div class="narr">${esc(narr)}</div>` : ""}`;
  const others = boss ? T.lines : T.foes;
  h += `<div class="pack"><div class="kicker">${boss ? tr("talk.in_pit") : tr("talk.facing")}<em>${others.length}</em></div>`;
  for (const u of others) {
    const tag = boss ? (u.at === "now" ? tr("talk.speaks") : "") : u.speaks ? tr("talk.speaks") : "";
    h += `<div class="row"><div class="medal ${ring()}">${face(u.portrait, u.name)}</div><div><b>${esc(u.name)}</b><span>${esc(boss ? u.caption : u.race)}</span></div>${tag ? `<div class="tag">${tag}</div>` : ""}</div>`;
  }
  h += `</div>`;
  if (T.kind === "ambush" && T.edge) {
    const more = T.edge > 0;
    h += `<div class="scale"><b>${tr("talk.sizing")}</b>${tr(more ? "talk.edge_more" : "talk.edge_less", {n: Math.abs(T.edge)})}</div>`;
  }
  if (T.kind === "guard" && T.wanted.length) {
    h += `<div class="scale"><b>${tr("talk.wanted")}</b>${T.wanted.map(u => tr("talk.wanted_one", {name: esc(u.name), n: u.crime})).join("; ")}. ${tr("talk.wanted_note")}</div>`;
  }
  return h;
}

// ---------- you answer ----------
function pips(need) {
  let s = "";
  for (let i = 1; i <= 20; i++) s += `<i class="${i >= need ? "on" : ""}"></i>`;
  return `<div class="pips">${s}</div>`;
}

function card(o) {
  let right;
  if (o.odds !== null) {
    right = `<div class="pct">${Math.round(o.odds * 100)}<small>%</small></div><div class="chk">${esc(o.check)}</div>${pips(o.need)}
      <div class="need">${o.need <= 20 ? tr("talk.need", {n: o.need}) : tr("talk.no_roll_lands")}</div>`;
  } else if (o.verb === "bribe") {
    right = `<div class="price"><span class="coin"></span>${esc(o.check)}</div><div class="cost">${tr("talk.bribe_cost", {purse: esc(T.purse_text)})}</div>`;
  } else if (o.verb === "attack") {
    right = `<div class="verdict red">${tr("talk.initiative")}</div>`;
  } else {
    right = `<div class="verdict blue">${tr("talk.no_roll")}</div>`;
  }
  const body = o.block ? `<div class="blocked">${esc(o.block)}</div>`
    : o.odds === null && o.verb !== "bribe" ? `<div class="if">${esc(o.pass)}</div>`
    : `<div class="if pass">${esc(o.pass)}</div>${o.miss ? `<div class="if miss">${esc(o.miss)}</div>` : ""}`;
  return `<div class="card ${VCLASS[o.verb] || ""} ${o.block ? "closed" : ""}" data-verb="${o.verb}"><div class="disc">${ico(o.icon)}</div>
    <div class="cbody"><h3>${esc(o.label)}</h3>${body}</div><div class="odds">${right}</div></div>`;
}

function slip(r, rolled) {
  const p = r.played;
  let h = p ? `<div class="midhead"><span class="lbl">${tr("talk.tried", {speaker: esc(p.speaker)})}</span><i>${tr("talk.dice_spoken")}</i></div>
    <div class="card played ${VCLASS[p.verb] || ""}"><div class="disc">${ico(p.icon)}</div><div class="cbody"><h3>${esc(p.label)}</h3><div class="if">${esc(p.note)}</div></div><div class="odds"><div class="chk">${esc(p.check)}</div></div></div>`
    : `<div class="midhead"><span class="lbl">${tr("talk.how_went")}</span><i>${tr("talk.talk_over")}</i></div>`;
  h += `<div class="slip">`;
  if (r.roll) {
    const {nat, mod, total, dc} = r.roll;
    const what = p && p.check ? p.check.split(" ")[0] : tr("talk.modifier");
    h += `<div class="dice"><div class="d20 ${rolled ? "rolling" : ""}"><svg viewBox="0 0 100 100"><polygon points="50,3 93,27 93,73 50,97 7,73 7,27" fill="#7a2218" stroke="#3a0c06" stroke-width="3"/><polygon points="50,22 77,66 23,66" fill="#9a2f22" stroke="#e8c9a8" stroke-opacity=".35" stroke-width="1.5"/><path d="M50 3 50 22M93 27 77 66M7 27 23 66M50 97 23 66M50 97 77 66M7 73 23 66M93 73 77 66M7 27 50 22M93 27 50 22" stroke="#e8c9a8" stroke-opacity=".35" stroke-width="1.5" fill="none"/></svg><b id="nat">${nat}</b></div>
      <div class="sum">${nat} ${mod < 0 ? "−" : "+"} ${Math.abs(mod)} = ${total}<span class="vs">${tr("talk.vs")}</span>${dc}<small>${tr("talk.dice_note", {of: p ? tr("talk.dice_of", {speaker: esc(p.speaker), what: esc(what)}) : esc(what)})}</small></div></div>`;
  }
  h += `<div class="tells">${esc(r.text)}</div>`;
  if (r.roll) {
    const [yes, no] = stamps(p ? p.verb : "");
    h += `<div class="stamp ${r.won ? "good" : ""}">${r.won ? yes : no}</div>`;
  }
  if (r.opening.length) {
    h += `<div class="opens"><div class="kicker">${tr("talk.opens")}</div>${r.opening.map(o =>
      `<div class="row"><div class="disc">${ico(o.icon)}</div><div><b>${esc(o.title)}</b><span>${esc(o.line)}</span></div></div>`).join("")}</div>`;
  }
  const fight = r.kind === "fight";
  h += `<div class="go"><small>${fight ? tr("talk.fight_note") : r.kind === "next" ? tr("talk.goes_on") : ""}</small>
    <div class="bigbtn ${fight ? "" : "brass"}" id="goon">${fight ? ico("item/broadsword") : ""}${esc(r.button)}</div></div></div>`;
  return h;
}

function script() {
  let h = `<div class="midhead"><span class="lbl">${tr("talk.before_bout")}</span><i>${tr("talk.word_each")}</i></div><div class="script">`;
  for (const l of T.lines) {
    const what = l.at === "now" ? `${tr("talk.now")} <span>· ${tr("talk.page_left")}</span>` : l.at === "said" ? tr("talk.has_spoken") : tr("talk.waits");
    h += `<div class="line ${l.at}"><div class="medal">${face(l.portrait, l.name)}</div><div><b>${esc(l.name)}</b><em>${esc(l.caption)}</em><p>${what}</p></div></div>`;
  }
  const r = T.result;
  h += `</div><div class="next"><i>${esc(r ? r.text : "")}</i><div class="bigbtn brass" id="goon">${esc(r ? r.button : tr("talk.go_on"))}</div></div>
    <div class="footnote">${tr("talk.no_answer")}</div>`;
  return h;
}

function mid(rolled) {
  if (T.kind === "boss") return script();
  if (T.result) return slip(T.result, rolled);
  const who = T.members.find(u => u.uid === T.speaker);
  let h = `<div class="midhead"><span class="lbl">${tr("talk.answers", {name: esc(who ? who.name : tr("talk.nobody"))})}</span><i>${tr("talk.pick_reply")}</i></div>`;
  h += T.options.map(card).join("");
  h += `<div class="footnote">${T.kind === "guard"
    ? tr("talk.foot_guard")
    : T.kind === "wildfire" ? tr("talk.foot_wildfire")
    : tr("talk.foot_tongue")}</div>`;
  return h;
}

// ---------- who answers ----------
function band() {
  const reading = T.kind === "boss" || !!T.result;
  const tongue = T.leader ? T.leader.languages : [];
  let h = `<div class="bandhead"><span class="lbl">${T.kind === "boss" ? tr("talk.your_squad") : tr("talk.who_speaks")}</span><i>${T.kind === "boss" ? esc(T.band) : T.result ? tr("talk.cast") : tr("talk.click_member")}</i></div><div class="mems">`;
  for (const u of T.members) {
    const sel = T.kind !== "boss" && u.uid === T.speaker;
    const mute = T.kind !== "boss" && !u.understood;
    const tags = [];
    if (u.crime !== null) tags.push(`<span class="mark bad">${tr("talk.wanted_mark", {n: u.crime})}</span>`);
    if (sel) tags.push(`<span class="mark warn">${T.result ? tr("talk.spoke") : tr("talk.speaks")}</span>`);
    let langs = u.languages.map(l => l.shared ? `<u>${esc(l.name)}</u>` : esc(l.name)).join(", ") || tr("talk.no_language");
    if (mute && tongue.length) langs += ` <em>· ${tr("talk.no_tongue_of", {tongue: esc(tongue[0])})}</em>`;
    h += `<div class="mem ${sel ? "sel" : ""} ${mute ? "mute" : ""} ${reading ? "" : "pick"}" data-uid="${u.uid}">
      <div class="medal ours">${face(u.portrait, u.name)}</div>
      <div class="nm"><b>${esc(u.name)}</b><span>${esc(u.race)}</span><div class="tongues">${langs}</div></div>
      <div class="mods"><div class="mod lead"><b>${sign(u.cha)}</b><span>CHA</span></div><div class="mod"><b>${sign(u.int)}</b><span>INT</span></div></div>
      ${tags.length ? `<div class="tagrow">${tags.join("")}</div>` : ""}</div>`;
  }
  const hp = T.members.reduce((a, u) => a + u.hp[0], 0), hpm = T.members.reduce((a, u) => a + u.hp[1], 0);
  h += `</div><div class="bandfoot"><span>${trn("talk.souls", T.members.length)}</span><span>${tr("talk.hit_points", {hp, max: hpm})}</span><span>${tr("talk.carried", {purse: esc(T.purse_text)})}</span></div>`;
  return h;
}

function render(state, rolled = false) {
  T = state;
  topBar();
  $("foe").innerHTML = foePage();
  $("mid").innerHTML = mid(rolled);
  $("band").innerHTML = band();
  if (rolled && T.result) Sound.play(T.result.paid ? "coins" : T.result.won ? "level_up" : "miss");
}

$("mid").addEventListener("click", e => {
  if (e.target.closest("#goon")) { post("go_on"); return; }
  const c = e.target.closest(".card[data-verb]");
  if (c && !c.classList.contains("closed")) post("choose", {verb: c.dataset.verb});
});
$("band").addEventListener("click", e => {
  const m = e.target.closest(".mem.pick");
  if (m && m.dataset.uid !== T.speaker) post("speaker", {uid: m.dataset.uid});
});
addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && T && T.result) { e.preventDefault(); post("go_on"); }
});

api("/api/talk/state").then(s => render(s));

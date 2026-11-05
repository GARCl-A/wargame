// The hunt: who minds the wagon, what to look for and for how long, each stretch, the ambush, the haul.
"use strict";

let H = null, busy = false;

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
    const r = await api(`/api/hunt/${verb}`, body);
    if (r.screen && r.screen !== "hunt") { location.reload(); return; }
    render(r);
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
  }
}

function topBar() {
  $("sealicon").style.setProperty("--icon", `url(/assets/icons/${H.icon}.svg)`);
  $("title").textContent = H.title;
  $("subtitle").innerHTML = tr("hunt.where", {band: esc(H.band), place: esc(H.place), day: H.day, at: esc(H.at)});
  $("topright").innerHTML = H.yields ? `<div class="stat"><b>${esc(H.yields.line)}</b>
    ${H.yields.ambush_mult ? `<span>${esc(H.yields.ambush_mult)}</span>` : ""}</div>` : "";
}

const events = () => H.events.length ? `<div class="kicker">${tr("hunt.away")}</div>
  <ul class="events">${H.events.map(l => `<li class="${/starved|did not eat|died/.test(l) ? "bad" : ""}">${esc(l)}</li>`).join("")}</ul>` : "";

function watchPage() {
  const W = H.watch;
  const risk = Math.round(W.risk * 100);
  return `<div class="kicker">${tr("hunt.who_minds")}</div>
    <p class="lead">${tr("hunt.wagon_lead")}</p>
    <div class="verdict ${W.guarded ? "safe" : "risk"}">${W.guarded ? tr("hunt.guarded") : tr("hunt.alone", {risk})}</div>
    <div class="parts"><span><b>${Math.round(W.place_risk * 100)}%</b>${tr("hunt.the_place")}</span><span><b>${Math.round(W.flight * 100)}%</b>${tr("hunt.bolt")}</span></div>`;
}

function choices(S) {
  let h = "";
  if (S.targets.length) {
    h += `<div class="kicker">${tr("hunt.look_for")}</div><div class="chips two">`;
    h += S.targets.map(t => `<div class="chip ${t.on ? "on" : ""}" data-target="${t.id}"><b>${esc(t.name)}</b><span>${esc(t.sub)}</span></div>`).join("");
    h += `</div>`;
  }
  h += `<div class="kicker">${tr(H.tracking ? "hunt.how_long_track" : "hunt.how_long")}</div><div class="chips">`;
  h += S.shifts.map(s => `<div class="chip ${s.on ? "on" : ""}" data-hours="${s.hours}"><b>${tr("unit.h", {n: s.hours})}</b><span>${esc(s.sub)}</span></div>`).join("");
  h += `</div><p class="note">${esc(S.note)}</p>`;
  if (S.why) h += `<p class="why">${esc(S.why)}</p>`;
  return h;
}

function ambushPage() {
  const A = H.ambush;
  let h = `<div class="kicker red">${esc(A.title)}</div><p class="lead red">${esc(A.lead)}</p>`;
  if (A.line) h += `<p class="lead">${esc(A.line)}</p>`;
  if (A.foes.length) h += `<div class="foes">${A.foes.map(f => `<div class="foe"><div class="medal">${face(f.portrait, f.name)}</div>
    <div><b>${esc(f.name)}</b><span>${esc(f.race)} · ${esc(f.weapon)}</span></div></div>`).join("")}</div>`;
  return h + events();
}

function page() {
  let h;
  if (H.phase === "watch") h = watchPage();
  else if (H.phase === "setup") h = choices(H.setup);
  else if (H.phase === "interlude") h = `<div class="kicker">${tr("hunt.goes_on")}</div><p class="lead">${esc(H.interlude.line)}</p>${events()}`;
  else if (H.phase === "ambush") h = ambushPage();
  else h = `<div class="kicker">${esc(H.done.title)}</div><ul class="haul">${H.done.lines.map(l => `<li>${esc(l)}</li>`).join("")}</ul>${events()}`;
  $("page").innerHTML = h;
  for (const el of $("page").querySelectorAll("[data-target]")) el.onclick = () => post("target", {target: el.dataset.target});
  for (const el of $("page").querySelectorAll("[data-hours]")) el.onclick = () => post("hours", {hours: +el.dataset.hours});
}

function watcher(m) {
  return `<div class="mem ${m.goes ? "on" : "out"}" data-uid="${esc(m.uid)}">
    <div class="mark">${tr(m.goes ? "hunt.goes_in" : "hunt.minds")}</div>
    <div class="who"><div class="medal">${face(m.portrait, m.name)}</div><div><b>${esc(m.name)}</b><span>${esc(m.what)} · ${esc(m.level)}</span></div></div></div>`;
}

function hunter(m) {
  const hurt = m.hp[0] < m.hp[1] ? "hurt" : "";
  const heavy = m.load[0] > m.load[1] ? "hurt" : "";
  const w = m.work.span ? Math.round(100 * m.work.into / m.work.span) : 100;
  return `<div class="mem on">
    ${m.picks ? `<div class="pick" data-talents="${esc(m.uid)}">${tr("hunt.level_up", {n: m.picks})}</div>` : ""}
    <div class="who"><div class="medal">${face(m.portrait, m.name)}</div><div><b>${esc(m.name)}</b><span>${esc(m.race)}</span></div></div>
    <div class="vit"><div class="${hurt}"><b>${m.hp[0]}/${m.hp[1]}</b><span>${tr("stat.hp")}</span></div><div><b>${m.ac}</b><span>${tr("stat.ac")}</span></div>
      <div class="${heavy}"><b>${m.load[0]}</b><span>${tr("hunt.of_kg", {n: m.load[1]})}</span></div><div><b>${m.rations}</b><span>${tr("hunt.rations")}</span></div></div>
    <div class="work"><span>${tr("hunt.work", {n: m.work.level})}</span><div class="bar"><i style="width:${w}%"></i></div><span>${tr("hunt.wis", {n: (m.wis >= 0 ? "+" : "") + m.wis})}</span></div>
  </div>`;
}

const ACTS = {
  watch: () => ({back: ["leave", tr("hunt.back")], go: ["go", tr("hunt.go_in"), tr("hunt.going", {n: H.watch.going})]}),
  setup: () => ({back: ["leave", tr("hunt.back")], go: ["start", tr(H.tracking ? "hunt.track" : "hunt.set_out"), tr("unit.h", {n: H.setup.shifts.find(s => s.on)?.hours ?? 0})], off: !!H.setup.why}),
  interlude: () => ({back: ["head_back", tr("hunt.head_back")], go: ["hunt_on", tr("hunt.hunt_on"), tr("hunt.hours_left", {n: H.interlude.hours_left})]}),
  ambush: () => ({go: ["fight", tr("hunt.fight"), H.tracking ? tr("hunt.the_ox") : trn("hunt.foes", H.ambush.foes.length)]}),
  done: () => ({go: ["done", tr("hunt.go_on"), tr("hunt.to_map")]}),
};

function party() {
  const watching = H.phase === "watch";
  const list = watching ? H.watch.members : H.members;
  let h = `<div class="head"><span class="lbl">${tr(watching ? "hunt.who_goes" : "hunt.party")}</span>
    <i>${watching ? tr("hunt.in_out", {in: H.watch.going, out: H.watch.outside}) : H.guards.length ? tr("hunt.minding", {names: esc(H.guards.join(", "))}) : tr("hunt.out_in", {n: list.length, where: tr(H.tracking ? "hunt.fields" : "hunt.wilds")})}</i></div>`;
  h += `<div class="grid">${list.map(watching ? watcher : hunter).join("")}</div>`;
  const A = ACTS[H.phase]();
  h += `<div class="foot"><div class="notice">${esc(H.notice || "")}</div>
    <div class="ghost-btn" id="swift" hidden></div>
    ${H.can_distribute ? `<div class="ghost-btn" id="distribute">${tr("kit.spread")}</div>` : ""}
    ${A.back ? `<div class="ghost-btn" id="back">${esc(A.back[1])}</div>` : ""}
    <div class="seal ${A.off ? "off" : ""} ${H.phase === "ambush" ? "" : "calm"}" id="go">${ico(H.phase === "ambush" ? "body/sword-tie" : H.icon)}<b>${esc(A.go[1])}</b><small>${esc(A.go[2])}</small></div></div>`;
  $("party").innerHTML = h;
  for (const el of $("party").querySelectorAll("[data-uid]")) el.onclick = () => post("watch", {uid: el.dataset.uid});
  for (const el of $("party").querySelectorAll("[data-talents]")) el.onclick = () => post("talents", {uid: el.dataset.talents});
  if ($("distribute")) $("distribute").onclick = () => post("distribute");
  if ($("back")) $("back").onclick = () => post(A.back[0]);
  $("go").onclick = () => { if (!A.off) post(A.go[0]); };
  const sw = H.phase === "ambush" && H.ambush.swift;
  Kit.swift($("swift"), sw, () => api("/api/hunt/state").then(render));
  if (sw && sw.eligible) $("swift").onclick = () => post("swift_win");
}

function render(state) {
  H = state;
  topBar();
  page();
  party();
}

api("/api/hunt/state").then(render);
addEventListener("keydown", e => {
  if (!H) return;
  const A = ACTS[H.phase]();
  if (e.key === "Enter" && !A.off) post(A.go[0]);
  else if (e.key === "Escape" && A.back) post(A.back[0]);
});

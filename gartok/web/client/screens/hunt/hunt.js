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
  $("subtitle").innerHTML = `<b>${esc(H.band)}</b> · ${esc(H.place)} · day ${H.day}, ${esc(H.at)}`;
  $("topright").innerHTML = H.yields ? `<div class="stat"><b>${esc(H.yields.line)}</b>
    ${H.yields.ambush_mult ? `<span>${esc(H.yields.ambush_mult)}</span>` : ""}</div>` : "";
}

const events = () => H.events.length ? `<div class="kicker">While you were out</div>
  <ul class="events">${H.events.map(l => `<li class="${/starved|did not eat|died/.test(l) ? "bad" : ""}">${esc(l)}</li>`).join("")}</ul>` : "";

function watchPage() {
  const W = H.watch;
  const risk = Math.round(W.risk * 100);
  return `<div class="kicker">Who minds the wagon?</div>
    <p class="lead">The wagon cannot go in. Click a member on the right to keep them outside with it; one guard is enough, and guards stay in the band.</p>
    <div class="verdict ${W.guarded ? "safe" : "risk"}">${W.guarded
      ? "Guarded: it is safe while the party is away."
      : `Left alone: ${risk}% chance of losing it, cargo and animals with it.`}</div>
    <div class="parts"><span><b>${Math.round(W.place_risk * 100)}%</b>the place</span><span><b>${Math.round(W.flight * 100)}%</b>the animals bolt</span></div>`;
}

function choices(S) {
  let h = "";
  if (S.targets.length) {
    h += `<div class="kicker">What to look for</div><div class="chips two">`;
    h += S.targets.map(t => `<div class="chip ${t.on ? "on" : ""}" data-target="${t.id}"><b>${esc(t.name)}</b><span>${esc(t.sub)}</span></div>`).join("");
    h += `</div>`;
  }
  h += `<div class="kicker">${H.tracking ? "How long to read the ground" : "How long"}</div><div class="chips">`;
  h += S.shifts.map(s => `<div class="chip ${s.on ? "on" : ""}" data-hours="${s.hours}"><b>${s.hours} h</b><span>${esc(s.sub)}</span></div>`).join("");
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
  else if (H.phase === "interlude") h = `<div class="kicker">The hunt goes on</div><p class="lead">${esc(H.interlude.line)}</p>${events()}`;
  else if (H.phase === "ambush") h = ambushPage();
  else h = `<div class="kicker">${esc(H.done.title)}</div><ul class="haul">${H.done.lines.map(l => `<li>${esc(l)}</li>`).join("")}</ul>${events()}`;
  $("page").innerHTML = h;
  for (const el of $("page").querySelectorAll("[data-target]")) el.onclick = () => post("target", {target: el.dataset.target});
  for (const el of $("page").querySelectorAll("[data-hours]")) el.onclick = () => post("hours", {hours: +el.dataset.hours});
}

function watcher(m) {
  return `<div class="mem ${m.goes ? "on" : "out"}" data-uid="${esc(m.uid)}">
    <div class="mark">${m.goes ? "goes in" : "minds the wagon"}</div>
    <div class="who"><div class="medal">${face(m.portrait, m.name)}</div><div><b>${esc(m.name)}</b><span>${esc(m.what)} · ${esc(m.level)}</span></div></div></div>`;
}

function hunter(m) {
  const hurt = m.hp[0] < m.hp[1] ? "hurt" : "";
  const heavy = m.load[0] > m.load[1] ? "hurt" : "";
  const w = m.work.span ? Math.round(100 * m.work.into / m.work.span) : 100;
  return `<div class="mem on">
    ${m.picks ? `<div class="pick" data-talents="${esc(m.uid)}">Level up (${m.picks})</div>` : ""}
    <div class="who"><div class="medal">${face(m.portrait, m.name)}</div><div><b>${esc(m.name)}</b><span>${esc(m.race)} ${esc(m.occupation.toLowerCase())}</span></div></div>
    <div class="vit"><div class="${hurt}"><b>${m.hp[0]}/${m.hp[1]}</b><span>HP</span></div><div><b>${m.ac}</b><span>AC</span></div>
      <div class="${heavy}"><b>${m.load[0]}</b><span>of ${m.load[1]} kg</span></div><div><b>${m.rations}</b><span>rations</span></div></div>
    <div class="work"><span>Work ${m.work.level}</span><div class="bar"><i style="width:${w}%"></i></div><span>WIS ${m.wis >= 0 ? "+" : ""}${m.wis}</span></div>
  </div>`;
}

const ACTS = {
  watch: () => ({back: ["leave", "Back to the map"], go: ["go", "Go in", `${H.watch.going} going`]}),
  setup: () => ({back: ["leave", "Back to the map"], go: ["start", H.tracking ? "Track" : "Set out", `${H.setup.shifts.find(s => s.on)?.hours ?? 0} h`], off: !!H.setup.why}),
  interlude: () => ({back: ["head_back", "Head back"], go: ["hunt_on", "Hunt on", `${H.interlude.hours_left} h left`]}),
  ambush: () => ({go: ["fight", "Fight", H.tracking ? "the ox" : `${H.ambush.foes.length} foes`]}),
  done: () => ({go: ["done", "Go on", "to the map"]}),
};

function party() {
  const watching = H.phase === "watch";
  const list = watching ? H.watch.members : H.members;
  let h = `<div class="head"><span class="lbl">${watching ? "Who goes in" : "The party"}</span>
    <i>${watching ? `${H.watch.going} in, ${H.watch.outside} outside` : H.guards.length ? `${esc(H.guards.join(", "))} minding the wagon` : `${list.length} out in the ${H.tracking ? "fields" : "wilds"}`}</i></div>`;
  h += `<div class="grid">${list.map(watching ? watcher : hunter).join("")}</div>`;
  const A = ACTS[H.phase]();
  h += `<div class="foot"><div class="notice">${esc(H.notice || "")}</div>
    ${H.can_distribute ? `<div class="ghost-btn" id="distribute">Distribute load</div>` : ""}
    ${A.back ? `<div class="ghost-btn" id="back">${esc(A.back[1])}</div>` : ""}
    <div class="seal ${A.off ? "off" : ""} ${H.phase === "ambush" ? "" : "calm"}" id="go">${ico(H.phase === "ambush" ? "body/sword-tie" : H.icon)}<b>${esc(A.go[1])}</b><small>${esc(A.go[2])}</small></div></div>`;
  $("party").innerHTML = h;
  for (const el of $("party").querySelectorAll("[data-uid]")) el.onclick = () => post("watch", {uid: el.dataset.uid});
  for (const el of $("party").querySelectorAll("[data-talents]")) el.onclick = () => post("talents", {uid: el.dataset.talents});
  if ($("distribute")) $("distribute").onclick = () => post("distribute");
  if ($("back")) $("back").onclick = () => post(A.back[0]);
  $("go").onclick = () => { if (!A.off) post(A.go[0]); };
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

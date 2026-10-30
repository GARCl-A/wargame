// Who minds the wagon at a place it cannot enter; then the party goes in.
"use strict";

let W = null, busy = false;

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
    const r = await api(`/api/watch/${verb}`, body);
    if (r.screen && r.screen !== "watch") { location.reload(); return; }
    render(r);
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
  }
}

function page() {
  const V = W.watch, risk = Math.round(V.risk * 100);
  $("page").innerHTML = `<div class="kicker">What waits inside</div><p class="lead">${esc(W.lead)}</p>
    <div class="kicker">Who minds the wagon?</div>
    <p class="lead">The wagon cannot go in. Click a member on the right to keep them outside with it; one guard is enough, and guards stay in the band.</p>
    <div class="verdict ${V.guarded ? "safe" : "risk"}">${V.guarded
      ? "Guarded: it is safe while the party is away."
      : `Left alone: ${risk}% chance of losing it, cargo and animals with it.`}</div>
    <div class="parts"><span><b>${Math.round(V.place_risk * 100)}%</b>the place</span><span><b>${Math.round(V.flight * 100)}%</b>the animals bolt</span></div>`;
}

function party() {
  const V = W.watch;
  $("party").innerHTML = `<div class="head"><span class="lbl">Who goes in</span><i>${V.going} in, ${V.outside} outside</i></div>
    <div class="grid">${V.members.map(m => `<div class="mem ${m.goes ? "on" : "out"}" data-uid="${esc(m.uid)}">
      <div class="mark">${m.goes ? "goes in" : "minds the wagon"}</div>
      <div class="who"><div class="medal">${face(m.portrait, m.name)}</div><div><b>${esc(m.name)}</b><span>${esc(m.what)} · ${esc(m.level)}</span></div></div></div>`).join("")}</div>
    <div class="foot"><div class="notice"></div><div class="ghost-btn" id="back">Back to the map</div>
      <div class="seal" id="go">${ico("body/sword-tie")}<b>${esc(W.label)}</b><small>${V.going} going</small></div></div>`;
  for (const el of $("party").querySelectorAll("[data-uid]")) el.onclick = () => post("watch", {uid: el.dataset.uid});
  $("back").onclick = () => post("leave");
  $("go").onclick = () => post("go");
}

function render(state) {
  W = state;
  $("sealicon").style.setProperty("--icon", `url(/assets/icons/${W.icon}.svg)`);
  $("title").textContent = W.title;
  $("subtitle").innerHTML = `<b>${esc(W.band)}</b> · day ${W.day}, ${esc(W.at)}`;
  page();
  party();
}

api("/api/watch/state").then(render);
addEventListener("keydown", e => {
  if (!W) return;
  if (e.key === "Enter") post("go");
  else if (e.key === "Escape") post("leave");
});

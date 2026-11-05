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
  $("page").innerHTML = `<div class="kicker">${tr("watch.inside")}</div><p class="lead">${esc(W.lead)}</p>
    <div class="kicker">${tr("hunt.who_minds")}</div>
    <p class="lead">${tr("hunt.wagon_lead")}</p>
    <div class="verdict ${V.guarded ? "safe" : "risk"}">${V.guarded ? tr("hunt.guarded") : tr("hunt.alone", {risk})}</div>
    <div class="parts"><span><b>${Math.round(V.place_risk * 100)}%</b>${tr("hunt.the_place")}</span><span><b>${Math.round(V.flight * 100)}%</b>${tr("hunt.bolt")}</span></div>`;
}

function party() {
  const V = W.watch;
  $("party").innerHTML = `<div class="head"><span class="lbl">${tr("hunt.who_goes")}</span><i>${tr("hunt.in_out", {in: V.going, out: V.outside})}</i></div>
    <div class="grid">${V.members.map(m => `<div class="mem ${m.goes ? "on" : "out"}" data-uid="${esc(m.uid)}">
      <div class="mark">${tr(m.goes ? "hunt.goes_in" : "hunt.minds")}</div>
      <div class="who"><div class="medal">${face(m.portrait, m.name)}</div><div><b>${esc(m.name)}</b><span>${esc(m.what)} · ${esc(m.level)}</span></div></div></div>`).join("")}</div>
    <div class="foot"><div class="notice"></div><div class="ghost-btn" id="back">${tr("hunt.back")}</div>
      <div class="seal" id="go">${ico("body/sword-tie")}<b>${esc(W.label)}</b><small>${tr("hunt.going", {n: V.going})}</small></div></div>`;
  for (const el of $("party").querySelectorAll("[data-uid]")) el.onclick = () => post("watch", {uid: el.dataset.uid});
  $("back").onclick = () => post("leave");
  $("go").onclick = () => post("go");
}

function render(state) {
  W = state;
  $("sealicon").style.setProperty("--icon", `url(/assets/icons/${W.icon}.svg)`);
  $("title").textContent = W.title;
  $("subtitle").innerHTML = tr("watch.where", {band: esc(W.band), day: W.day, at: esc(W.at)});
  page();
  party();
}

api("/api/watch/state").then(render);
addEventListener("keydown", e => {
  if (!W) return;
  if (e.key === "Enter") post("go");
  else if (e.key === "Escape") post("leave");
});

// A place's hub: the keeper's strip, the row of tabs and the tab in view. The shop draws itself
// (shop.js), and so do a work node's shifts (labor.js) and the Medic (medic.js); a tab the browser does
// not draw yet is a note on paper. Every verb answers the whole hub.
"use strict";

let H = null;
const ico = (path, cls = "ico") => `<span class="${cls} mask" style="--icon:url(/assets/icons/${path}.svg)"></span>`;
const money = n => "$" + n;
const card = c => `<div class="hcard"><div class="lbl">${esc(c.label)}</div><b class="${c.tone || ""}">${esc(c.value)}</b></div>`;
const cards = list => { $("cards").innerHTML = `<div class="vsep"></div>` + list.map(card).join(`<div class="vsep"></div>`); };

let toastTimer = null;
function toast(text) {
  if (!text) return;
  const t = $("toast");
  t.textContent = text.charAt(0).toUpperCase() + text.slice(1);
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
}

async function post(verb, body = {}) {
  try {
    const r = await api(`/api/hub/${verb}`, body);
    if (r.screen && r.screen !== "hub") { location.reload(); return null; }
    H = r;
    draw();
    return r;
  } catch (e) {
    toast(e.message);
    return null;
  }
}

function drawFrame() {
  $("place").textContent = H.place;
  $("sub").innerHTML = `<b>${esc(H.band)}</b> · ${esc(H.sub)}`;
  $("tabs").innerHTML = H.tabs.map(t =>
    `<span class="${t.key === H.tab ? "on" : ""} ${t.live ? "" : "away"}" data-tab="${t.key}" title="${t.live ? "" : "played in pygame for now"}">${esc(t.label)}</span>`).join("");
  const k = H.keeper;
  $("kmed").innerHTML = k.portrait ? `<img src="${k.portrait}" draggable="false">` : `<div class="ico">${ico(H.icon, "ico")}</div>`;
  $("kname").textContent = k.name || H.place;
  $("kcap").textContent = [k.caption, k.bent].filter(Boolean).join(" · ");
  $("kline").textContent = k.line || "";
}

function drawAway() {
  $("cards").innerHTML = "";
  $("body").innerHTML = `<div class="paper awaytab"><div class="kicker">${esc(H.place)}</div>
    <h2>${esc(H.away.title)}</h2><p>${esc(H.away.line)}</p></div>`;
}

function draw() {
  drawFrame();
  if (H.shop) Shop.draw(H.shop);
  else if (H.work) Labor.work(H.work);
  else if (H.gather) Labor.gather(H.gather);
  else if (H.medic) Medic.draw(H.medic);
  else drawAway();
}

function nextTab(step) {
  const keys = H.tabs.map(t => t.key), i = keys.indexOf(H.tab);
  post("tab", {key: keys[(i + step + keys.length) % keys.length]});
}

async function back() {
  Sound.play("click");
  await api("/api/hub/back", {});
  location.reload();
}

$("tabs").addEventListener("click", e => {
  const t = e.target.closest("[data-tab]");
  if (t && t.dataset.tab !== H.tab) { Sound.play("click"); post("tab", {key: t.dataset.tab}); }
});
$("back").onclick = back;
addEventListener("keydown", e => {
  if (e.key === "Tab" && H && H.tabs.length > 1) { e.preventDefault(); nextTab(e.shiftKey ? -1 : 1); return; }
  if (e.key === "Escape" && !(H && H.shop && Shop.escape())) back();
});

api("/api/hub/state").then(r => { H = r; draw(); });

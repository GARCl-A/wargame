// The settings: press a choice to keep it; with a guild open, its tutorial cards too.
"use strict";

let S = null, busy = false;

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.hidden = true; }, 3600);
}

async function post(verb, body = {}) {
  if (busy) return;
  busy = true;
  try {
    const r = await api(`/api/settings/${verb}`, body);
    if (r.screen && r.screen !== "settings" || body.key === "language") { location.reload(); return; }
    render(r);
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
  }
}

const opts = (list, on, attr) => `<div class="opts">${list.map(c =>
  `<div class="opt ${c.value === on ? "on" : ""}" ${attr}="${esc(c.value)}">${esc(c.label)}</div>`).join("")}</div>`;

function render(state) {
  S = state;
  Sound.volume = S.volume;
  $("back").textContent = S.back;
  $("rows").innerHTML = S.rows.map(r => `<div class="row" data-key="${r.key}"><div class="txt"><b>${esc(r.label)}</b><span>${esc(r.note)}</span></div>
    ${opts(r.choices, r.value, "data-value")}</div>`).join("");
  $("ver").textContent = S.version;
  $("export").innerHTML = `<div class="kicker">${tr("settings.playtest")}</div>
    <div class="row"><div class="txt"><b>${tr("settings.export")}</b><span>${tr("settings.export_note")}</span></div>
      <a class="pbtn" id="export-btn" href="/api/settings/export" download>${tr("settings.export_btn")}</a></div>`;
  const T = S.tutorial;
  $("tut").innerHTML = T ? `<div class="kicker">${tr("settings.tutorial_of", {guild: esc(S.guild || tr("settings.this_guild"))})}</div>
    <div class="row"><div class="txt"><b>${tr("settings.cards")}</b><span>${tr("settings.cards_note")}</span></div>
      ${opts([{value: "on", label: tr("settings.on")}, {value: "off", label: tr("settings.off")}], T.enabled ? "on" : "off", "data-tut")}</div>
    <div class="row"><div class="txt"><b>${tr("settings.again")}</b><span>${tr("settings.again_note")}</span></div>
      <div class="pbtn ${T.reset ? "done" : ""}" id="reset">${T.reset ? tr("settings.again_done") : tr("settings.again_btn")}</div></div>` : "";
}

document.addEventListener("click", e => {
  const o = e.target.closest(".opt");
  if (o && !o.classList.contains("on")) {
    if (o.dataset.tut !== undefined) post("tutorial");
    else {
      const key = o.closest("[data-key]").dataset.key, row = S.rows.find(r => r.key === key);
      const choice = row.choices.find(c => String(c.value) === o.dataset.value);
      post("set", {key, value: choice.value});
    }
    return;
  }
  if (e.target.closest("#reset") && !S.tutorial.reset) post("reset_tutorial");
  else if (e.target.closest("#back")) post("back");
});
addEventListener("keydown", e => { if (e.key === "Escape") post("back"); });

api("/api/settings/state").then(render).catch(e => toast(e.message));

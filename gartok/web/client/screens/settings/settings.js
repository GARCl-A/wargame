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
    if (r.screen && r.screen !== "settings") { location.reload(); return; }
    render(r);
    Sound.play("click");
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
  const T = S.tutorial;
  $("tut").innerHTML = T ? `<div class="kicker">The tutorial of ${esc(S.guild || "this guild")}</div>
    <div class="row"><div class="txt"><b>Tutorial cards</b><span>The card each screen opens with the first time, kept with the guild's save.</span></div>
      ${opts([{value: "on", label: "On"}, {value: "off", label: "Off"}], T.enabled ? "on" : "off", "data-tut")}</div>
    <div class="row"><div class="txt"><b>Show them again</b><span>Every card comes back, as if each screen were new.</span></div>
      <div class="pbtn ${T.reset ? "done" : ""}" id="reset">${T.reset ? "Shown again" : "Reset the cards"}</div></div>` : "";
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

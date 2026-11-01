// The credits: the authors, licence links and sources of the icons and sounds, with a way back.
"use strict";

let busy = false;

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.hidden = true; }, 3600);
}

async function post(verb) {
  if (busy) return;
  busy = true;
  try {
    const r = await api(`/api/credits/${verb}`, {});
    if (r.screen && r.screen !== "credits") { location.reload(); return; }
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
  }
}

const link = (url, label) => url
  ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>` : esc(label);

function render(S) {
  $("kicker").textContent = S.kicker;
  $("heading").textContent = S.title;
  $("back").textContent = S.back;
  $("sections").innerHTML = S.sections.map(s => `<div class="sec"><b>${esc(s.heading)}</b><p>${esc(s.intro)}</p>
    ${s.people_label ? `<div class="who">${esc(s.people_label)}</div>` : ""}
    <div class="names">${s.people.map(p => `<span>${link(p.url, p.name)}</span>`).join("")}</div>
    <div class="links">${s.links.map(l => link(l.url, l.label)).join("")}</div></div>`).join("");
}

document.addEventListener("click", e => { if (e.target.closest("#back")) post("back"); });
addEventListener("keydown", e => { if (e.key === "Escape") post("back"); });

api("/api/credits/state").then(render).catch(e => toast(e.message));

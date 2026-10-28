// The compendium: pick a chapter, filter it, read its entries; BACK returns where it was opened.
"use strict";

let W = null, busy = false, typed = null;
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"];
const ico = (name, cls = "") => name ? `<span class="${cls} mask" style="--icon:url(/assets/icons/${name}.svg)"></span>` : "";

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
    const r = await api(`/api/wiki/${verb}`, body);
    if (r.screen && r.screen !== "wiki") { location.reload(); return; }
    render(r);
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
  }
}

// the filter's match, marked in what is already escaped
function lit(text) {
  const t = esc(text), q = W.query.trim();
  if (!q) return t;
  const at = t.toLowerCase().indexOf(esc(q).toLowerCase());
  return at < 0 ? t : `${t.slice(0, at)}<mark>${t.slice(at, at + esc(q).length)}</mark>${t.slice(at + esc(q).length)}`;
}

function entry(e) {
  const list = W.chapter === "rules" || e.body.length > 1;
  const body = list ? `<ul>${e.body.map(l => `<li>${lit(l)}</li>`).join("")}</ul>` : e.body.map(l => `<p>${lit(l)}</p>`).join("");
  const track = e.track && e.track.length ? `<p><i>Racial track:</i> ${e.track.map(lit).join(", ")}</p>` : "";
  return `<div class="e"><div class="hd">${ico(e.glyph, "gl")}<div><b>${lit(e.name)}</b>${e.kind ? `<span class="k">${esc(e.kind)}</span>` : ""}</div></div>
    ${e.meta.length ? `<div class="m">${e.meta.map(lit).join(" · ")}</div>` : ""}${body}${track}
    ${e.tags.length ? `<div class="tags">${e.tags.map(t => `<span>${esc(t)}</span>`).join("")}</div>` : ""}</div>`;
}

function render(state) {
  W = state;
  $("back").textContent = W.back;
  $("chapters").innerHTML = W.chapters.map((c, i) =>
    `<div class="ch ${c.id === W.chapter ? "on" : ""}" data-ch="${c.id}"><span class="n">${ROMAN[i]}</span>${esc(c.label)}</div>`).join("");
  const label = W.chapters.find(c => c.id === W.chapter).label;
  $("chapter").textContent = label;
  $("count").textContent = W.query.trim() ? `${W.entries.length} of ${W.total} · “${W.query.trim()}”` : `${W.total} entries`;
  if (document.activeElement !== $("q")) $("q").value = W.query;
  else if ($("q").value.toLowerCase() !== W.query) find();
  const el = $("entries");
  el.className = W.chapter === "rules" ? "rules" : "";
  el.innerHTML = W.entries.length ? `<div class="cols">${W.entries.map(entry).join("")}</div>`
    : `<div class="none">Nothing in ${esc(label.toLowerCase())} reads “${esc(W.query.trim())}”.</div>`;
}

$("chapters").addEventListener("click", e => {
  const t = e.target.closest("[data-ch]");
  if (t && t.dataset.ch !== W.chapter) { Sound.play("click"); $("entries").scrollTop = 0; post("chapter", {chapter: t.dataset.ch}); }
});
// a find dropped while another was on its way is sent again once the answer shows the page behind
function find() {
  clearTimeout(typed);
  typed = setTimeout(() => { $("entries").scrollTop = 0; post("find", {q: $("q").value}); }, 120);
}
$("q").addEventListener("input", find);
$("back").onclick = () => post("back");
addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (document.activeElement === $("q") && $("q").value) { $("q").value = ""; post("find", {q: ""}); }
  else post("back");
});

api("/api/wiki/state").then(render).catch(e => toast(e.message));

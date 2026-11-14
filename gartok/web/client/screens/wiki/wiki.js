// The compendium: pick a chapter, filter it, read its entries; BACK returns where it was opened.
"use strict";

let W = null, busy = false, typed = null;
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI"];

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
  const track = e.track && e.track.length ? `<p><i>${tr("wiki.racial")}</i> ${e.track.map(lit).join(", ")}</p>` : "";
  const tags = e.tags.map(t => `<span>${esc(t)}</span>`).join("")
    + e.links.map(l => `<span class="ref" data-ref="${esc(l.ref)}"${tip(l.tip, "item")}>${lit(l.label)}</span>`).join("");
  return `<div class="e ${e.id === W.focus ? "focus" : ""}" data-id="${esc(e.id)}"><div class="hd">${ico(e.glyph, "gl")}<div><b>${lit(e.name)}</b>${e.kind ? `<span class="k">${esc(e.kind)}</span>` : ""}</div></div>
    ${e.meta.length ? `<div class="m">${e.meta.map(lit).join(" · ")}</div>` : ""}${body}${track}
    ${tags ? `<div class="tags">${tags}</div>` : ""}</div>`;
}

function render(state) {
  W = state;
  const f = W.focus && W.entries.find(e => e.id === W.focus);
  if (f && f.part) shut.delete(f.part);
  $("back").textContent = W.back;
  $("chapters").innerHTML = W.chapters.map((c, i) =>
    `<div class="ch ${c.id === W.chapter ? "on" : ""}" data-ch="${c.id}"><span class="n">${ROMAN[i] || (i + 1)}</span>${esc(c.label)}</div>`).join("");
  const label = W.chapters.find(c => c.id === W.chapter).label;
  $("chapter").textContent = label;
  $("count").textContent = W.query.trim() ? tr("wiki.of_total", {n: W.entries.length, total: W.total, q: W.query.trim()}) : tr("wiki.entries", {n: W.total});
  if (document.activeElement !== $("q")) $("q").value = W.query;
  else if ($("q").value.toLowerCase() !== W.query) find();
  paint(true);
}

// the Rules chapter's parts fold shut; a filter or a link into one opens it
const shut = new Set();

function toc() {
  const parts = [];
  for (const e of W.entries) {
    let p = parts[parts.length - 1];
    if (!p || p.id !== e.part) parts.push(p = {id: e.part, label: e.part_label, items: []});
    p.items.push(e);
  }
  return `<nav class="toc">${parts.map(p => `<div class="tp"><b data-gopart="${esc(p.id)}">${esc(p.label)}</b>${p.items.map(e => `<a data-goto="${esc(e.id)}">${esc(e.name)}</a>`).join("")}</div>`).join("")}</nav>`;
}

function paint(focus) {
  const el = $("entries"), label = W.chapters.find(c => c.id === W.chapter).label, rules = W.chapter === "rules";
  const open = id => !rules || W.query.trim() || !shut.has(id);
  el.className = rules ? "rules" : "";
  const rows = W.entries.map((e, i) => {
    const head = e.part && e.part !== (W.entries[i - 1] || {}).part
      ? `<h3 class="part ${open(e.part) ? "" : "shut"}" data-part="${esc(e.part)}">${esc(e.part_label)}<span class="ct">${W.entries.filter(x => x.part === e.part).length}</span></h3>` : "";
    return head + (!e.part || open(e.part) ? entry(e) : "");
  });
  el.innerHTML = W.entries.length ? `${rules ? toc() : ""}<div class="cols">${rows.join("")}</div>`
    : `<div class="none">${tr("wiki.none", {chapter: esc(label.toLowerCase()), q: esc(W.query.trim())})}</div>`;
  const at = focus && W.focus && [...el.querySelectorAll(".e")].find(x => x.dataset.id === W.focus);
  if (at) at.scrollIntoView({block: "center"});
}

$("chapters").addEventListener("click", e => {
  const t = e.target.closest("[data-ch]");
  if (t && t.dataset.ch !== W.chapter) { $("entries").scrollTop = 0; post("chapter", {chapter: t.dataset.ch}); }
});
$("entries").addEventListener("click", e => {
  const t = e.target.closest("[data-ref]");
  if (t) { post("open", {ref: t.dataset.ref}); return; }
  const gp = e.target.closest("[data-gopart]");
  if (gp) {
    shut.delete(gp.dataset.gopart);
    paint(false);
    const h = [...$("entries").querySelectorAll(".part")].find(x => x.dataset.part === gp.dataset.gopart);
    if (h) h.scrollIntoView({block: "start", behavior: "smooth"});
    return;
  }
  const part = e.target.closest("[data-part]");
  if (part) {
    const id = part.dataset.part;
    if (shut.has(id)) shut.delete(id); else shut.add(id);
    paint(false);
    return;
  }
  const go = e.target.closest("[data-goto]");
  if (go) {
    const hit = W.entries.find(x => x.id === go.dataset.goto);
    if (hit && hit.part) shut.delete(hit.part);
    paint(false);
    const row = [...$("entries").querySelectorAll(".e")].find(x => x.dataset.id === go.dataset.goto);
    if (row) row.scrollIntoView({block: "start", behavior: "smooth"});
  }
});
// a find dropped while another was on its way is sent again once the answer shows the page behind
function find() {
  clearTimeout(typed);
  typed = setTimeout(() => { $("entries").scrollTop = 0; post("find", {q: $("q").value}); }, 120);
}
$("q").placeholder = tr("wiki.filter");
$("q").addEventListener("input", find);
$("back").onclick = () => post("back");
addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (document.activeElement === $("q") && $("q").value) { $("q").value = ""; post("find", {q: ""}); }
  else post("back");
});

api("/api/wiki/state").then(render).catch(e => toast(e.message));

// A workbench tab (the forge, the carpentry, the Apothecary's craft, the Library's writing desk): on
// leather who in the band works here (click to pick) and what the last stint made; on paper the picked
// crafter's recipes, what each uses from the band's packs and what is missing, and the hours to put in,
// with the group waiting (rolled now) or the crafter gone off alone (the map runs the clock).
"use strict";

const Craft = (() => {
  const chip = (text, cls = "") => `<span class="tag ${cls}">${esc(text)}</span>`;

  function uses(r) {
    // a batch under way already took its materials: only the next one would want them
    const mats = r.uses.map(u => `<span class="${u.have >= u.need || r.active ? "" : "short"}">${u.need}× ${esc(nm("item", u.name))} <small>(${u.have})</small></span>`);
    const tools = r.tools.map(t => `<span class="${t.have ? "" : "short"}">${esc(nm("item", t.name))} <small>${tr("craft.tool")}</small></span>`);
    return [...mats, ...tools].join("");
  }

  function hours(label, verb, list, why, r) {
    const btns = why ? `<span class="why">${esc(why)}</span>`
      : list.map(h => `<div class="btn" data-recipe="${esc(r.id)}" data-hours="${h}" data-alone="${verb === "alone" ? 1 : ""}">${tr("unit.h", {n: h})}</div>`).join("");
    return `<div class="hrow"><span class="lbl">${label}</span>${btns}</div>`;
  }

  function recipe(r, C) {
    const chips = [chip(tr("craft.level", {n: r.level}), "money"), chip(r.xp ? tr("craft.xp", {n: r.xp}) : tr("craft.no_xp"))];
    if (r.makes > 1) chips.push(chip(tr("craft.makes", {n: r.makes}), "good"));
    const line = r.active
      ? `<div class="prog"><div class="bar"><i style="width:${Math.min(100, 100 * r.progress / Math.max(1, r.goal))}%"></i></div>
           <span>${tr("craft.progress", {have: r.progress, goal: r.goal})}</span></div>`
      : `<p class="use">${tr("craft.needs", {goal: r.goal, roll: (r.roll >= 0 ? "+" : "") + r.roll})}</p>`;
    const act = r.can
      ? hours(tr("craft.group_waits"), "wait", C.wait_hours, null, r) + hours(tr("craft.alone"), "alone", C.alone_hours, r.alone, r)
      : `<p class="why">${tr("craft.materials")}</p>`;
    return `<div class="recipe ${r.active ? "active" : ""} ${r.can ? "" : "out"}">
      <div class="ico mask" style="--icon:url(/assets/icons/${r.glyph}.svg)"></div>
      <div><div class="jhead"><span class="nm">${esc(nm("item", r.target))}</span>${chips.join("")}</div>
        <div class="mats">${uses(r)}</div>${line}</div>
      <div class="acts">${act}</div></div>`;
  }

  function draw(C) {
    cards(C.cards);
    const crew = C.crafters.length ? C.crafters.map(u => `<div class="worker patient ${u.picked ? "on" : ""}" data-crafter="${esc(u.uid)}">
        <div class="medal">${face(u.portrait, u.name)}</div>
        <div class="who"><h3>${esc(u.name)}</h3><div class="race">${esc(u.sub)}</div>${u.note ? `<p>${esc(u.note)}</p>` : ""}</div></div>`).join("")
      : `<p class="hint">${tr("craft.no_crafter")}</p>`;
    const report = C.report.length
      ? `<div class="report lreport"><div class="lbl">${tr("craft.last_stint")}</div>${C.report.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";
    const list = C.recipes.length ? C.recipes.map(r => recipe(r, C)).join("") : `<p class="aside">${tr("craft.no_recipes")}</p>`;
    $("body").innerHTML = `<div class="leather lcol"><div class="lbl">${tr("craft.crafters")}</div>
        <p class="hint">${tr("craft.crafters_hint")}</p><div class="crew">${crew}</div>${report}</div>
      <div class="paper ledger"><div class="kicker">${tr("craft.recipes")} <em>${C.who ? tr("craft.whose", {who: esc(C.who), what: esc(C.what)}) : esc(C.what)}</em></div>
        <div class="recipes">${list}</div>
        <div class="ledgerfoot"><p class="${C.food.have < C.food.meals ? "why" : ""}">${tr(C.food.meals ? "craft.food_days" : "craft.food", {rations: plural(C.food.have, "ration"), meals: C.food.meals, days: C.food.meals ? plural(Math.floor(C.food.have / C.food.meals), "day") : ""})}</p>
          <p>${tr("craft.foot")}</p></div></div>`;
    toast(C.notice);
  }

  $("body").addEventListener("click", async e => {
    if (!H || !H.craft) return;
    const p = e.target.closest("[data-crafter]");
    if (p) { post("crafter", {uid: p.dataset.crafter}); return; }
    const b = e.target.closest("[data-recipe]");
    if (b) {
      post("craft", {recipe: b.dataset.recipe, hours: +b.dataset.hours, alone: !!b.dataset.alone});
    }
  });

  return {draw};
})();

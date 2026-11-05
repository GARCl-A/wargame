// After a fight, one page per screen in the order they come: the fallen, the report, each level-up,
// then the field (drag a stack onto a pack, or click it and then where) or the arena's purse.
"use strict";

let R = null, busy = false, pick = null, drag = null;
const qty = {};
const g = glyph => glyph ? ico(glyph) : "";
const kilos = v => (Math.round(v * 10) / 10).toString().replace(/\.0$/, "") + " " + tr("kit.kg");
const names = list => list.map(n => `<b>${esc(n)}</b>`).join(list.length > 2 ? ", " : tr("kit.and"));
const SEALS = {memorial: ["head/dead-head", "black"], report: ["action/rally-the-troops", ""], level: ["gui/progression", ""],
  loot: ["item/knapsack", ""], purse: ["item/two-coins", ""], map: ["map/signpost", ""]};

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
    const r = await api(`/api/report/${verb}`, body);
    if (r.screen && r.screen !== "report") { location.reload(); return; }
    const was = R && R.stage;
    render(r);
    if (verb === "give") Sound.play("coins");
    else if (r.stage !== was && r.stage === "level") Sound.play("level_up");
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
  }
}

// ---------------------------------------------------------------- the top
function chain() {
  return `<div class="chain">${R.chain.map(c => `<span class="${c.at === "later" ? "" : c.at}">${esc(c.label)}</span>`).join("<i>›</i>")}</div>`;
}

function where() {
  return tr("report.where", {place: esc(R.place), what: R.what ? ` · ${esc(R.what)}` : "", day: R.day, at: R.at});
}

function header(title, sub, right = "") {
  const [seal, cls] = SEALS[R.stage];
  $("seal").className = "rseal " + cls;
  $("seal").innerHTML = ico(seal);
  $("title").textContent = title;
  $("subtitle").innerHTML = sub;
  $("topright").innerHTML = right + chain();
  $("report").classList.toggle("mourning", R.stage === "memorial");
}

// ---------------------------------------------------------------- the fallen
function memorial() {
  const M = R.memorial;
  header(tr("report.fallen_title"), tr("report.fallen_sub", {where: where(), n: M.length}));
  let h = `<div id="graves" class="${M.length > 2 ? "many" : ""}">`;
  for (const m of M) {
    const k = m.killer;
    h += `<div class="grave"><div class="tag">${tr("report.memoriam")}</div>
      <div class="oval">${face(m.portrait, m.name)}</div>
      <h2>${esc(m.name)}</h2><div class="cap">${esc(m.race)}${m.founder ? ` · ${tr("report.founder")}` : ""}</div>
      <div class="days">${m.days_n}<small>${trn("report.days_with", m.days_n)}</small></div>
      <div class="span">${tr("report.span", {from: m.joined, to: m.died})}</div>
      <div class="rule"></div>
      <div class="cause">${esc(m.cause)}${m.place ? ` · ${esc(m.place)}` : ""}</div>
      ${k ? `<div class="killer"><div class="medal ${k.foe ? "foe" : ""}">${face(k.portrait, k.name)}</div><div><b>${esc(k.name)}</b><span>${tr("report.put_down")}${k.caption ? ` · ${esc(k.caption)}` : ""}</span></div></div>` : ""}
      ${m.line ? `<div class="line">${esc(m.line)}</div>` : ""}
      <div class="left"><b>${tr("report.carried_lbl")}</b>${tr("report.carried")}</div>
    </div>`;
  }
  const last = R.chain[R.chain.findIndex(c => c.id === "memorial") + 1];
  h += `</div><div id="memfoot"><i>${tr("report.fallen_foot")}</i>
    <div class="bigbtn" data-go="next">${last && last.id !== "map" ? tr("kit.to", {name: esc(last.label.toLowerCase())}) : tr("report.go_on")}</div></div>`;
  $("body").innerHTML = h;
}

// ---------------------------------------------------------------- the report
function verdict(P) {
  const fallen = P.rows.filter(r => r.status === "fallen").map(r => r.name);
  const stable = P.rows.filter(r => r.status === "stable").length;
  const place = `<b>${esc(R.place)}</b>`;
  const key = R.result === "VICTORY" ? "won" : R.result === "FLED" ? "fled" : "lost";
  let s = tr("report." + key, {place, n: R.rounds});
  if (fallen.length) s += " " + tr(stable ? "report.did_not_get_up_semi" : "report.did_not_get_up", {names: names(fallen)});
  if (stable) s += " " + trn(fallen.length ? "report.stable_more" : "report.stable_after", stable);
  else if (!fallen.length) s += " " + tr("report.all_well");
  return s;
}

function report() {
  const P = R.report;
  const back = P.rows.filter(r => r.status !== "fallen");
  const dead = P.foes.filter(f => f.status === "fallen").length, down = P.foes.filter(f => f.status === "stable").length;
  const xp = P.rows.reduce((a, r) => a + r.xp_gain, 0);
  header(tr("report.after_title"), tr("report.after_sub", {where: where(), n: R.rounds}),
    `<div class="stat"><b>${back.length} / ${P.rows.length}</b><span>${tr("report.came_back")}</span></div>
     <div class="stat"><b>${dead} + ${down}</b><span>${tr("report.foes_dead_down")}</span></div>
     <div class="stat"><b>+${xp}</b><span>${tr("report.combat_xp_gain")}</span></div>`);
  const rowH = Math.max(72, Math.min(104, Math.floor(620 / Math.max(P.rows.length, P.foes.length, 1))));
  const lv = [...new Set(P.foes.map(f => f.level))].sort((a, b) => a - b);
  let h = `<div class="paper" id="roll">
    <div class="verdict"><div class="stamp ${R.result}">${tr("result." + R.result)}</div><p>${verdict(P)}</p></div>
    <div class="sides"><div><div class="kicker">${tr("report.the_band")}<em>${tr("report.went_in", {n: P.rows.length})}</em></div>`;
  for (const r of P.rows) {
    const gone = r.status === "fallen", up = r.level > r.level_before;
    const was = up ? 0 : r.bar_before * 100;
    const downs = r.downed.length ? tr("report.downs", {n: r.downed.length}) : "";
    h += `<div class="sq ${gone ? "gone" : ""}" data-n="${esc(r.name)}" style="height:${rowH}px">
      <div class="nm"><b>${esc(r.name)}</b><span>${esc(r.race)}</span><div class="st ${r.status}">${tr("report.st." + r.status)}</div></div>
      <div class="bars"><div class="barlbl"><span>${tr("report.xp_lbl", {level: r.level})}</span><b class="${r.xp_gain ? "up" : ""}">${r.xp_gain ? `+${r.xp_gain} · ` : ""}${r.into} / ${r.span}</b></div>
        <div class="bar xp"><i class="gain" data-w="${r.bar * 100}" style="width:${was}%"></i><i class="was" style="width:${was}%"></i></div>
        <div class="downs">${gone ? tr("report.dies_with") : downs}${r.magic_gain ? ` · ${tr("report.magic_gain", {n: r.magic_gain})}` : ""}${up ? `<span class="lvmark">${tr("report.lvmark", {n: r.level})}</span>` : ""}</div></div>
      <div class="medal ${gone ? "dead" : ""}" style="width:${rowH * .6}px;height:${rowH * .6}px">${face(r.portrait, r.name)}</div></div>`;
  }
  h += `</div><div></div><div><div class="kicker">${tr("report.the_pack")}<em>${lv.length ? tr("report.pack_lv", {n: P.foes.length, lv: lv.length > 1 ? `${lv[0]}–${lv[lv.length - 1]}` : lv[0]}) : tr("report.pack_n", {n: P.foes.length})}</em></div>`;
  for (const f of P.foes) {
    h += `<div class="fo" data-n="${esc(f.name)}" style="height:${rowH}px"><div class="medal foe ${f.status === "fallen" ? "dead" : ""}" style="width:${rowH * .54}px;height:${rowH * .54}px">${face(f.portrait, f.name)}</div>
      <div style="min-width:0"><b>${esc(f.name)}</b><span>${esc(f.race)}</span><div class="st ${f.status}">${tr("report.foe_st." + f.status)}</div></div></div>`;
  }
  h += `</div><svg id="blows"></svg></div>
    <div class="legend"><span style="font-style:normal" class="lbl">${tr("report.who_put_down")}</span><span><i style="border-color:var(--blueink)"></i>${tr("report.band_blows")}</span><span><i style="border-color:var(--redink);border-top-style:dashed"></i>${tr("report.pack_blows")}</span></div>
    <div class="rollfoot">${rollfoot(P, down)}</div></div>`;
  h += nextPanel(P);
  $("body").innerHTML = h;
  requestAnimationFrame(() => {
    blows(P);
    document.querySelectorAll(".bar.xp i.gain").forEach(i => { i.style.width = i.dataset.w + "%"; });
  });
}

function rollfoot(P, down) {
  const parts = [`<span><b>${tr("report.deeds")}</b>${P.deeds.length ? P.deeds.map(d => tr("report.deed_row", {name: esc(d.name), rep: d.rep, faction: esc(d.faction)})).join("; ") : tr("report.no_deeds")}</span>`];
  if (P.captives.length) parts.push(`<span><b>${tr("report.bound")}</b>${P.captives.map(esc).join(" ")}</span>`);
  else if (down) parts.push(`<span><b>${tr("report.down_not_dead")}</b>${trn("report.left_down", down)}</span>`);
  if (P.title_note) parts.push(`<span><b>${tr("report.the_title")}</b>${esc(P.title_note)}</span>`);
  return parts.join("");
}

const STEP_ICON = {memorial: "head/dead-head", report: "action/rally-the-troops", level: "gui/progression",
  loot: "item/knapsack", purse: "item/two-coins", map: "map/signpost"};

function nextPanel(P) {
  let h = `<div class="leather" id="next"><div class="kicker">${tr("report.follows")}<em>${tr("report.in_order")}</em></div>`;
  R.steps.forEach((s, i) => {
    h += `<div class="step ${s.at}"><div class="n">${s.at === "done" ? "✓" : i + 1}</div><div class="d">${ico(STEP_ICON[s.id])}</div>
      <div class="tx"><b>${esc(s.title)}</b><span>${esc(s.line)}</span></div>
      ${s.faces.length ? `<div class="faces">${s.faces.map(f => `<div class="medal">${face(f, "")}</div>`).join("")}</div>` : ""}</div>`;
  });
  if (P.hp.length) {
    h += `<div class="cond"><div class="kicker">${tr("report.walk_away")}<em>${tr("report.hp_after")}</em></div>`;
    for (const u of P.hp) {
      const low = u.hp * 3 < u.hp_max;
      h += `<div class="row"><div class="medal">${face(u.portrait, u.name)}</div><b>${esc(u.name)}</b>
        <div class="bar hp ${low ? "low" : ""}"><i style="width:${u.hp / u.hp_max * 100}%"></i></div>
        <em class="${low ? "red" : ""}">${u.hp} / ${u.hp_max}${u.stable ? ` · ${tr("report.stable_tag")}` : ""}</em></div>`;
    }
    h += `</div>`;
  }
  const hurt = P.hp.filter(u => u.hp * 3 < u.hp_max).length;
  const hint = !hurt ? "" : hurt === P.hp.length ? (hurt === 1 ? tr("report.hint_one") : tr("report.hint_all", {n: hurt}))
    : tr("report.hint_some", {n: hurt, total: P.hp.length});
  return h + `<div class="nextfoot"><i>${hint}</i><div class="bigbtn" data-go="next">${tr("report.continue")}</div></div></div>`;
}

// the blows, drawn once the rows are laid out: blue from the band, dashed red from the pack
function blows(P) {
  const svg = $("blows");
  if (!svg) return;
  const box = svg.getBoundingClientRect(), s = box.width / svg.clientWidth || 1;
  const at = (n, sel, side) => {
    const el = document.querySelector(`${sel}[data-n="${CSS.escape(n)}"] .medal`);
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return [((side === "r" ? b.right + 8 : b.left - 8) - box.left) / s, (b.top + b.height / 2 - box.top) / s];
  };
  let paths = "";
  P.takedowns.forEach(([who, whom, mine], i) => {
    const a = mine ? at(who, ".fo", "l") : at(who, ".sq", "r"), b = mine ? at(whom, ".sq", "r") : at(whom, ".fo", "l");
    if (!a || !b) return;
    const mx = (a[0] + b[0]) / 2, off = (i % 3 - 1) * 10;
    paths += `<path d="M${a[0]} ${a[1] + off / 3} C ${mx} ${a[1] + off}, ${mx} ${b[1] + off}, ${b[0]} ${b[1]}" fill="none"
      stroke="${mine ? "#8e2a1e" : "#2b4f78"}" stroke-width="2.2" ${mine ? 'stroke-dasharray="7 5"' : ""} marker-end="url(#${mine ? "r" : "b"})" opacity=".85"/>`;
  });
  svg.innerHTML = `<defs><marker id="b" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 10 5 0 10z" fill="#2b4f78"/></marker>
    <marker id="r" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 10 5 0 10z" fill="#8e2a1e"/></marker></defs>` + paths;
}

// ---------------------------------------------------------------- the level-up
const GAIN = {"Combat level": "combat", "Work level": "work", "Magic level": "magic", "Racial level": "racial", "Hit dice": "dice", "Max HP": "hp"};
const gainLbl = l => GAIN[l] ? tr(`report.gain.${GAIN[l]}.l`) : l;
const gainWhy = l => GAIN[l] ? tr(`report.gain.${GAIN[l]}.why`) : "";

function level() {
  const L = R.level;
  header(tr("report.level_title"), tr("report.level_sub", {name: esc(L.name), after: esc(L.after)}));
  const head = L.gains.find(([l]) => l.toUpperCase().startsWith(L.track)) || L.gains[0];
  const delta = (l, a, b) => l === "Max HP" ? tr("report.delta_hp", {n: b - a}) : `+${b - a}`;
  const next = L.next ? `<div class="tonext"><div class="barlbl"><span>${tr("report.toward", {n: L.level + 1})}</span><b>${tr("report.xp_of", {a: L.next[0], b: L.next[1]})}</b></div>
      <div class="bar xp"><i class="gain" style="width:${L.next[0] / L.next[1] * 100}%"></i></div></div>` : "";
  const picks = L.picks ? `<div class="picks"><div class="d">${ico("gui/family-tree")}</div><div class="tx"><b>${trn("report.picks", L.picks)}</b>
      <span>${tr("report.picks_wait")}</span></div>
      <div class="bigbtn small" data-go="talents">${tr("report.pick_talents")}</div></div>` : "";
  $("body").innerHTML = `<div class="paper" id="sheet">
    <div class="plate"><div class="tag">${esc(L.tag)}</div><div class="big">${face(L.portrait, L.name)}</div>
      <div class="wax"><b>${L.level}</b><span>${esc(L.track)}</span></div>
      <h2>${esc(L.name)}</h2><div class="cap">${esc(L.race)}</div></div>
    <div class="gains"><div class="kicker">${head ? tr("report.gain_kicker", {track: tr("report.track." + L.track), from: head[1], to: head[2]}) : tr("report.gain_kicker_one", {track: tr("report.track." + L.track), n: L.level})}<em>${tr("report.what_rose")}</em></div>
      <h3>${tr("report.is_now", {name: esc(L.name), n: L.level, role: tr("report.role." + L.track)})}${L.track === "COMBAT" && L.xp_gain
        ? `<small>${tr("report.carried_over", {xp: L.xp_gain, place: esc(R.place)})}</small>` : ""}</h3>
      <div class="ledger">${L.gains.map(([l, a, b]) => `<div class="row"><div class="l">${esc(gainLbl(l))}<small>${gainWhy(l)}</small></div>
        <div class="a">${a}</div><div class="ar">→</div><div class="b">${b}</div><div class="dl">${delta(l, a, b)}</div></div>`).join("")}</div>
      ${next}${picks}</div>
    <div class="lvfoot"><i>${L.gains.some(([l]) => l === "Max HP") ? tr("report.hp_now", {a: L.hp[0], b: L.hp[1]}) : ""}</i>
      <div class="bigbtn" data-go="next">${tr("report.continue")}</div></div></div>`;
}

// ---------------------------------------------------------------- the field
const isPicked = (from, loc) => pick && pick.from === from && pick.loc === loc;

function ware(w) {
  const on = isPicked("field", w.loc), n = qty[w.name] ?? w.qty;
  return `<div class="ware ${on ? "on" : ""} ${w.coin ? "coins" : ""}" data-from="field" data-loc="${w.loc}"${tip(w.tip, "item")}>
    <span class="g">${g(w.glyph)}</span><span class="nm">${esc(nm("item", w.name))}${w.coin ? `<small>${money(w.coin)}</small>` : ""}</span>
    <span class="q">×${w.qty}</span><span class="kg">${kilos(w.qty * w.kg)}</span>
    <span class="take"><i data-q="-1">−</i><b>${on ? Math.min(n, w.qty) : "·"}</b><i data-q="1">+</i></span></div>`;
}

function column(p, refused) {
  const row = (q, it, loc, slot) => {
    const got = it && it.name ? (it.new || 0) : 0;
    const html = Kit.item(q.id, it, loc, slot, {sel: isPicked(q.id, loc), tags: got ? Kit.tag(true, tr("report.new")) : ""});
    return got ? html.replace('class="it ', 'class="it new ') : html;
  };
  const html = Kit.column(p, {row, foot: refused ? `<b>${tr("report.wont_fit")}</b>${esc(refused.why)}` : ""});
  return refused ? html.replace('class="col pack"', 'class="col pack refuse"').replace('class="cfoot"', 'class="cfoot why"') : html;
}

function loot() {
  const L = R.loot;
  header(tr("report.field_title"), tr("report.field_sub", {where: where()}));
  let h = `<div class="paper" id="field" data-col="field"><div class="kicker">${tr("report.left_on_field")}<em>${tr("report.drag_hint")}</em></div>
    <div class="fhead"><b>${plural(L.stacks, "stack")}</b><span>${tr("report.things", {things: L.things, kg: kilos(L.kg)})}<br>${tr("report.field_kit")}</span></div><div class="wares">`;
  if (!L.cats.length) h += `<div class="empty-field">${tr("report.field_empty")}</div>`;
  for (const c of L.cats) h += `<div class="cat">${esc(c.label)}</div>` + c.rows.map(ware).join("");
  h += `</div><div class="fieldfoot"><p>${tr("report.field_foot")}</p></div></div><div id="packs">`;
  for (const p of L.packs) h += column(p, L.refused && L.refused.uid === p.uid ? L.refused : null);
  const took = L.taken.map(t => tr("report.took", {items: t.items.map(([n, q]) => tr(q > 1 ? "report.took_n" : "report.took_the", {q, name: esc(n)})).join(", "), who: esc(t.name)})).join(" · ");
  h += `</div><div class="leather" id="lootfoot"><div class="bigbtn ghost small" data-go="auto">${ico("item/knapsack")}${tr("report.take_fits")}</div>
    ${L.can_distribute ? `<div class="bigbtn ghost small" data-go="distribute"${tip(tr("kit.spread_tip"))}>${ico("action/rally-the-troops")}${tr("kit.spread")}</div>` : ""}
    <i>${took ? `${took} · ` : ""}${L.stacks ? trn("report.still", L.stacks) : tr("report.bare")}</i>
    <div class="bigbtn" data-go="next">${tr(L.stacks ? "report.leave_rest" : "report.go_on")}</div></div>`;
  $("body").innerHTML = h;
}

function wareOf(loc) {
  for (const c of R.loot.cats) for (const w of c.rows) if (w.loc === loc) return w;
  return null;
}

function itemOf(from, loc) {
  if (from === "field") return wareOf(loc);
  const p = R.loot.packs.find(x => x.uid === from);
  if (!p) return null;
  return typeof loc === "string" ? p.worn.find(w => w.zone === loc) : p.pack.find(r => r.loc === loc);
}

function sourceAt(el) {
  const s = el.closest("[data-from], .it[data-loc]");
  if (!s) return null;
  const from = s.dataset.from || s.dataset.owner;
  const loc = from === "field" || /^\d+$/.test(s.dataset.loc) ? +s.dataset.loc : s.dataset.loc;
  return {from, loc};
}

function give(src, el) {
  const col = el.closest("[data-col], .col.pack[data-owner]");
  if (!col) return false;
  const to = col.dataset.col || col.dataset.owner;
  if (to === "field" && src.from === "field") return false;
  if (to === src.from) return false;
  const slot = el.closest(".it[data-zone]");
  const w = src.from === "field" ? wareOf(src.loc) : null;
  const body = {picks: [{from: src.from, loc: src.loc, qty: w ? Math.min(qty[w.name] ?? w.qty, w.qty) : undefined}], to,
    zone: slot && to !== "field" ? slot.dataset.zone : "pack"};
  pick = null;
  post("take", body);
  return true;
}

function fieldDown(e) {
  const step = e.target.closest("[data-q]");
  if (step) {
    const w = wareOf(+step.closest(".ware").dataset.loc);
    const cur = isPicked("field", w.loc) ? (qty[w.name] ?? w.qty) : (+step.dataset.q > 0 ? 0 : w.qty + 1);
    qty[w.name] = Math.max(1, Math.min(w.qty, cur + +step.dataset.q));
    pick = {from: "field", loc: w.loc};
    render(R);
    return;
  }
  const src = sourceAt(e.target);
  if (src) {
    drag = {src, x: e.clientX, y: e.clientY, moving: false};
    return;
  }
  if (pick && give(pick, e.target)) return;
  if (pick) { pick = null; render(R); }
}

function slip(src) {
  const it = itemOf(src.from, src.loc);
  if (!it) return;
  const s = $("slip");
  s.innerHTML = `<span class="g">${g(it.glyph)}</span><div><b>${esc(nm("item", it.name))}</b><br><span>${tr(src.from === "field" ? "report.from_field" : "report.from_pack")}</span></div>`;
  s.hidden = false;
}

function moveSlip(e) {
  const st = $("screen").getBoundingClientRect(), k = st.width / 1920;
  $("slip").style.left = (e.clientX - st.left) / k + 14 + "px";
  $("slip").style.top = (e.clientY - st.top) / k + 10 + "px";
  document.querySelectorAll(".target").forEach(t => t.classList.remove("target"));
  const el = document.elementFromPoint(e.clientX, e.clientY);
  const over = el && (el.closest(".it[data-zone]") || el.closest("[data-col], .col.pack[data-owner]"));
  if (over) over.classList.add("target");
}

addEventListener("pointermove", e => {
  if (!drag) return;
  if (!drag.moving && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 6) return;
  if (!drag.moving) { drag.moving = true; slip(drag.src); }
  moveSlip(e);
});

addEventListener("pointerup", e => {
  if (!drag) return;
  const d = drag;
  drag = null;
  $("slip").hidden = true;
  document.querySelectorAll(".target").forEach(t => t.classList.remove("target"));
  if (d.moving) {
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (el) give(d.src, el);
    return;
  }
  if (pick && !(pick.from === d.src.from && pick.loc === d.src.loc) && give(pick, e.target)) return;
  pick = isPicked(d.src.from, d.src.loc) ? null : d.src;
  render(R);
});

// ---------------------------------------------------------------- the purse
function purse() {
  const P = R.purse, stake = P.entry * P.fighters, net = P.amount - stake;
  header(tr("report.purse_title"), tr("report.purse_sub", {bout: esc(P.bout || R.place), day: R.day}),
    `<div class="stat"><b>${money(P.amount)}</b><span>${tr("report.the_purse")}</span></div><div class="stat"><b>${money(net)}</b><span>${tr("report.over_stake")}</span></div>`);
  const deeds = P.deeds.map(d => `<div class="deedline">${tr("report.deed_line", {name: esc(d.name), blurb: esc(d.blurb), rep: d.rep, faction: esc(d.faction)})}</div>`).join("");
  let h = `<div class="paper" id="pit"><div class="pile"><div><b>${money(P.amount)}</b><span>${tr("report.in_copper")}</span></div></div>
    <div><h2>${tr(P.paid_to ? "report.pocketed" : "report.who_pockets")}</h2><p>${tr("report.purse_lands")}</p>
    <div class="sums"><div>${tr("report.staked")}<b>${money(stake)}</b></div><div>${trn("report.fighters_x", P.fighters, {entry: money(P.entry)})}</div><div>${tr("report.won_lbl")}<b class="good">${money(P.amount)}</b></div>
      <div>${tr("report.net")}<b class="${net >= 0 ? "good" : "bad"}">${net >= 0 ? "+" : "−"}${money(Math.abs(net))}</b></div></div>${deeds}
      ${P.note ? `<div class="deedline" style="color:#7d5c37">${esc(P.note)}</div>` : ""}</div></div><div id="hands">`;
  for (const m of P.members) {
    const paid = P.paid_to === m.uid;
    h += `<div class="leather hand ${paid ? "paid" : P.paid_to ? "spent" : ""}" data-uid="${m.uid}"><div class="medal">${face(m.portrait, m.name)}</div>
      <b>${esc(m.name)}</b><span>${esc(m.sub)}</span>
      <div class="was">${tr("report.carries")}<b class="${paid ? "after" : ""}">${money(m.money)}</b></div>
      ${P.paid_to ? "" : `<div class="give"><div class="bigbtn ghost small" data-give="${m.uid}">${ico("item/two-coins")}${tr("report.give", {amount: money(P.amount)})}</div></div>`}</div>`;
  }
  h += `</div><div id="pursefoot"><i>${tr(P.paid_to ? "report.spoken" : "report.opens")}</i>
    <div class="bigbtn ${P.paid_to ? "" : "ghost off"}" data-go="next">${tr("report.continue")}</div></div>`;
  $("body").innerHTML = h;
}

// ---------------------------------------------------------------- wiring
function render(state) {
  R = state;
  ({memorial, report, level, loot, purse})[R.stage]();
}

$("body").addEventListener("pointerdown", e => {
  if (R.stage === "loot" && !e.target.closest("[data-go]")) fieldDown(e);
});
$("body").addEventListener("wheel", e => {
  const packs = e.target.closest("#packs");
  if (!packs || e.target.closest(".packlist") || packs.scrollWidth <= packs.clientWidth) return;
  e.preventDefault();
  packs.scrollLeft += e.deltaY || e.deltaX;
}, {passive: false});
$("body").addEventListener("click", e => {
  const go = e.target.closest("[data-go]");
  if (go && !go.classList.contains("off")) { post(go.dataset.go); return; }
  const giveTo = e.target.closest("[data-give]");
  if (giveTo) post("give", {uid: giveTo.dataset.give});
});
$("body").addEventListener("mouseover", e => {
  const h = e.target.closest(".hand[data-uid]");
  document.querySelectorAll(".hand.hot").forEach(x => x !== h && x.classList.remove("hot"));
  if (h && R.stage === "purse" && !R.purse.paid_to) h.classList.add("hot");
});
addEventListener("keydown", e => {
  if (e.key !== "Enter" && e.key !== " ") return;
  if (R.stage === "purse" && !R.purse.paid_to) return;
  e.preventDefault();
  post("next");
});

api("/api/report/state").then(render);

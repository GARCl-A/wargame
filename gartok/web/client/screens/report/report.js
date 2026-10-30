// After a fight, one page per screen in the order they come: the fallen, the report, each level-up,
// then the field (drag a stack onto a pack, or click it and then where) or the arena's purse.
"use strict";

let R = null, busy = false, pick = null, drag = null;
const qty = {};
const ico = name => `<span class="ico mask" style="--icon:url(/assets/icons/${name}.svg)"></span>`;
const g = glyph => glyph ? ico(glyph) : "";
const money = v => "$" + Number(v).toLocaleString("en-US");
const kg = v => (Math.round(v * 10) / 10).toString().replace(/\.0$/, "") + " kg";
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const names = list => list.map(n => `<b>${esc(n)}</b>`).join(list.length > 2 ? ", " : " and ");
const STATUS = {standing: "Standing", stable: "Down, stable", fallen: "Fallen", fled: "Fled", bound: "Bound"};
const FOE_STATUS = {standing: "Standing", stable: "Down, stable", fallen: "Dead", fled: "Fled", bound: "Bound"};
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
  return `<b>${esc(R.place)}</b>${R.what ? ` · ${esc(R.what)}` : ""} · day ${R.day}, ${R.at}`;
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
  header("The fallen", `${where()} · <b>${M.length}</b> of the band did not get up`);
  let h = `<div id="graves" class="${M.length > 2 ? "many" : ""}">`;
  for (const m of M) {
    const k = m.killer;
    h += `<div class="grave"><div class="tag">In memoriam</div>
      <div class="oval">${face(m.portrait, m.name)}</div>
      <h2>${esc(m.name)}</h2><div class="cap">${esc(m.race)} ${esc(m.occupation)}${m.founder ? " · one of the founders" : ""}</div>
      <div class="days">${m.days_n}<small>${m.days_n === 1 ? "day" : "days"} with the guild</small></div>
      <div class="span">day ${m.joined} to day ${m.died}</div>
      <div class="rule"></div>
      <div class="cause">${esc(m.cause)}${m.place ? ` · ${esc(m.place)}` : ""}</div>
      ${k ? `<div class="killer"><div class="medal ${k.foe ? "foe" : ""}">${face(k.portrait, k.name)}</div><div><b>${esc(k.name)}</b><span>put them down${k.caption ? ` · ${esc(k.caption)}` : ""}</span></div></div>` : ""}
      ${m.line ? `<div class="line">${esc(m.line)}</div>` : ""}
      <div class="left"><b>What they carried</b>lies on the field with the foes' gear: the band can take it up after the report.</div>
    </div>`;
  }
  const last = R.chain[R.chain.findIndex(c => c.id === "memorial") + 1];
  h += `</div><div id="memfoot"><i>The fallen lie together: one page for every death of the fight.</i>
    <div class="bigbtn" data-go="next">${last && last.id !== "map" ? `To ${esc(last.label.toLowerCase())}` : "Go on"}</div></div>`;
  $("body").innerHTML = h;
}

// ---------------------------------------------------------------- the report
function verdict(P) {
  const fallen = P.rows.filter(r => r.status === "fallen").map(r => r.name);
  const stable = P.rows.filter(r => r.status === "stable").length;
  const place = `<b>${esc(R.place)}</b>`;
  let s = R.result === "VICTORY" ? `The pack is broken on the ${place} after ${R.rounds} rounds.`
    : R.result === "FLED" ? `The band runs from the ${place} after ${R.rounds} rounds.`
    : `The band is beaten on the ${place} after ${R.rounds} rounds.`;
  if (fallen.length) s += ` ${names(fallen)} did not get up;`;
  if (stable) s += ` ${fallen.length ? stable : plural(stable, "member")} ${fallen.length ? "more " : ""}${stable === 1 ? "lies" : "lie"} down, stable, and walk${stable === 1 ? "s" : ""} on hurt.`;
  else if (fallen.length) s = s.replace(/;$/, ".");
  else s += " Everyone walks away.";
  return s;
}

function report() {
  const P = R.report;
  const back = P.rows.filter(r => r.status !== "fallen");
  const dead = P.foes.filter(f => f.status === "fallen").length, down = P.foes.filter(f => f.status === "stable").length;
  const xp = P.rows.reduce((a, r) => a + r.xp_gain, 0);
  header("After the fight", `${where()} · <b>${R.rounds}</b> rounds`,
    `<div class="stat"><b>${back.length} / ${P.rows.length}</b><span>came back</span></div>
     <div class="stat"><b>${dead} + ${down}</b><span>foes dead + down</span></div>
     <div class="stat"><b>+${xp}</b><span>combat XP</span></div>`);
  const rowH = Math.max(72, Math.min(104, Math.floor(620 / Math.max(P.rows.length, P.foes.length, 1))));
  const lv = [...new Set(P.foes.map(f => f.level))].sort((a, b) => a - b);
  let h = `<div class="paper" id="roll">
    <div class="verdict"><div class="stamp ${R.result}">${esc(R.result)}</div><p>${verdict(P)}</p></div>
    <div class="sides"><div><div class="kicker">The band<em>${P.rows.length} went in</em></div>`;
  for (const r of P.rows) {
    const gone = r.status === "fallen", up = r.level > r.level_before;
    const was = up ? 0 : r.bar_before * 100;
    const downs = r.downed.length ? `${r.downed.length} put down` : "";
    h += `<div class="sq ${gone ? "gone" : ""}" data-n="${esc(r.name)}" style="height:${rowH}px">
      <div class="nm"><b>${esc(r.name)}</b><span>${esc(r.race)}</span><div class="st ${r.status}">${STATUS[r.status]}</div></div>
      <div class="bars"><div class="barlbl"><span>Combat XP · level ${r.level}</span><b class="${r.xp_gain ? "up" : ""}">${r.xp_gain ? `+${r.xp_gain} · ` : ""}${r.into} / ${r.span}</b></div>
        <div class="bar xp"><i class="gain" data-w="${r.bar * 100}" style="width:${was}%"></i><i class="was" style="width:${was}%"></i></div>
        <div class="downs">${gone ? "what they earned dies with them" : downs}${r.magic_gain ? ` · +${r.magic_gain} magic` : ""}${up ? `<span class="lvmark">level ${r.level}</span>` : ""}</div></div>
      <div class="medal ${gone ? "dead" : ""}" style="width:${rowH * .6}px;height:${rowH * .6}px">${face(r.portrait, r.name)}</div></div>`;
  }
  h += `</div><div></div><div><div class="kicker">The pack<em>${P.foes.length}${lv.length ? `, racial level ${lv.length > 1 ? `${lv[0]}–${lv[lv.length - 1]}` : lv[0]}` : ""}</em></div>`;
  for (const f of P.foes) {
    h += `<div class="fo" data-n="${esc(f.name)}" style="height:${rowH}px"><div class="medal foe ${f.status === "fallen" ? "dead" : ""}" style="width:${rowH * .54}px;height:${rowH * .54}px">${face(f.portrait, f.name)}</div>
      <div style="min-width:0"><b>${esc(f.name)}</b><span>${esc(f.race)} ${esc(f.occupation)}</span><div class="st ${f.status}">${FOE_STATUS[f.status]}</div></div></div>`;
  }
  h += `</div><svg id="blows"></svg></div>
    <div class="legend"><span style="font-style:normal" class="lbl">Who put down whom</span><span><i style="border-color:var(--blueink)"></i>the band's blows</span><span><i style="border-color:var(--redink);border-top-style:dashed"></i>the pack's blows</span></div>
    <div class="rollfoot">${rollfoot(P, down)}</div></div>`;
  h += nextPanel(P);
  $("body").innerHTML = h;
  requestAnimationFrame(() => {
    blows(P);
    document.querySelectorAll(".bar.xp i.gain").forEach(i => { i.style.width = i.dataset.w + "%"; });
  });
}

function rollfoot(P, down) {
  const parts = [`<span><b>Deeds</b>${P.deeds.length ? P.deeds.map(d => `${esc(d.name)} · +${d.rep} with ${esc(d.faction)}`).join("; ") : "none this fight"}</span>`];
  if (P.captives.length) parts.push(`<span><b>Bound</b>${P.captives.map(esc).join(" ")}</span>`);
  else if (down) parts.push(`<span><b>Down, not dead</b>${down} of the pack lie stable: they could have been bound and led away (Capture), and are left.</span>`);
  if (P.title_note) parts.push(`<span><b>The title</b>${esc(P.title_note)}</span>`);
  return parts.join("");
}

const STEP_ICON = {memorial: "head/dead-head", report: "action/rally-the-troops", level: "gui/progression",
  loot: "item/knapsack", purse: "item/two-coins", map: "map/signpost"};

function nextPanel(P) {
  let h = `<div class="leather" id="next"><div class="kicker">What follows<em>in this order</em></div>`;
  R.steps.forEach((s, i) => {
    h += `<div class="step ${s.at}"><div class="n">${s.at === "done" ? "✓" : i + 1}</div><div class="d">${ico(STEP_ICON[s.id])}</div>
      <div class="tx"><b>${esc(s.title)}</b><span>${esc(s.line)}</span></div>
      ${s.faces.length ? `<div class="faces">${s.faces.map(f => `<div class="medal">${face(f, "")}</div>`).join("")}</div>` : ""}</div>`;
  });
  if (P.hp.length) {
    h += `<div class="cond"><div class="kicker">How they walk away<em>hit points after the fight</em></div>`;
    for (const u of P.hp) {
      const low = u.hp * 3 < u.hp_max;
      h += `<div class="row"><div class="medal">${face(u.portrait, u.name)}</div><b>${esc(u.name)}</b>
        <div class="bar hp ${low ? "low" : ""}"><i style="width:${u.hp / u.hp_max * 100}%"></i></div>
        <em class="${low ? "red" : ""}">${u.hp} / ${u.hp_max}${u.stable ? " · stable" : ""}</em></div>`;
    }
    h += `</div>`;
  }
  const hurt = P.hp.filter(u => u.hp * 3 < u.hp_max).length;
  const hint = hurt ? `Rest or the Medic before the next road: ${hurt === P.hp.length ? (hurt === 1 ? "the one" : `all ${hurt}`) : `${hurt} of ${P.hp.length}`} walk on badly hurt.` : "";
  return h + `<div class="nextfoot"><i>${hint}</i><div class="bigbtn" data-go="next">Continue</div></div></div>`;
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
const WHY = {"Combat level": "from the fight's XP", "Work level": "from the work done", "Magic level": "from the spells cast",
  "Racial level": "one level of each track is one of the race's", "Hit dice": "one more die of hit points", "Max HP": "the new die, rolled"};
const ROLE = {COMBAT: "fighter", WORK: "worker", MAGIC: "caster"};

function level() {
  const L = R.level;
  header("Level up", `<b>${esc(L.name)}</b> · after ${esc(L.after)}`);
  const head = L.gains.find(([l]) => l.toUpperCase().startsWith(L.track)) || L.gains[0];
  const delta = (l, a, b) => l === "Max HP" ? `+${b - a} HP` : `+${b - a}`;
  const next = L.next ? `<div class="tonext"><div class="barlbl"><span>Toward level ${L.level + 1}</span><b>${L.next[0]} / ${L.next[1]} XP</b></div>
      <div class="bar xp"><i class="gain" style="width:${L.next[0] / L.next[1] * 100}%"></i></div></div>` : "";
  const picks = L.picks ? `<div class="picks"><div class="d">${ico("gui/family-tree")}</div><div class="tx"><b>${plural(L.picks, "talent")} to pick</b>
      <span>The pick waits on the sheet if you go on: it is spent from the talent tree whenever you open it.</span></div>
      <div class="bigbtn small" data-go="talents">Pick talents</div></div>` : "";
  $("body").innerHTML = `<div class="paper" id="sheet">
    <div class="plate"><div class="tag">${esc(L.tag)}</div><div class="big">${face(L.portrait, L.name)}</div>
      <div class="wax"><b>${L.level}</b><span>${esc(L.track)}</span></div>
      <h2>${esc(L.name)}</h2><div class="cap">${esc(L.race)} ${esc(L.occupation)}</div></div>
    <div class="gains"><div class="kicker">${esc(L.track.toLowerCase())} level ${head ? `${head[1]} to ${head[2]}` : L.level}<em>what rose</em></div>
      <h3>${esc(L.name)} is now a level ${L.level} ${ROLE[L.track]}${L.track === "COMBAT" && L.xp_gain
        ? `<small>${L.xp_gain} XP from the ${esc(R.place)} carried them over the line.</small>` : ""}</h3>
      <div class="ledger">${L.gains.map(([l, a, b]) => `<div class="row"><div class="l">${esc(l)}<small>${WHY[l] || ""}</small></div>
        <div class="a">${a}</div><div class="ar">→</div><div class="b">${b}</div><div class="dl">${delta(l, a, b)}</div></div>`).join("")}</div>
      ${next}${picks}</div>
    <div class="lvfoot"><i>${L.gains.some(([l]) => l === "Max HP") ? `${L.hp[0]} / ${L.hp[1]} HP now: the new die raised the cap, not the wounds.` : ""}</i>
      <div class="bigbtn" data-go="next">Continue</div></div></div>`;
}

// ---------------------------------------------------------------- the field
const isPicked = (from, loc) => pick && pick.from === from && pick.loc === loc;

function ware(w) {
  const on = isPicked("field", w.loc), n = qty[w.name] ?? w.qty;
  return `<div class="ware ${on ? "on" : ""} ${w.coin ? "coins" : ""}" data-from="field" data-loc="${w.loc}" title="${esc(w.tip)}">
    <span class="g">${g(w.glyph)}</span><span class="nm">${esc(w.name)}${w.coin ? `<small>${money(w.coin)}</small>` : ""}</span>
    <span class="q">×${w.qty}</span><span class="kg">${kg(w.qty * w.kg)}</span>
    <span class="take"><i data-q="-1">−</i><b>${on ? Math.min(n, w.qty) : "·"}</b><i data-q="1">+</i></span></div>`;
}

function column(p, refused) {
  const hp = p.hp[0] * 3 < p.hp[1], over = p.kg > p.normal;
  const worn = p.worn.map(w => `<div class="slot ${w.name ? "" : "empty"} ${w.new ? "new" : ""} ${isPicked(p.uid, w.zone) ? "on" : ""}" data-zone="${w.zone}"
      ${w.name ? `data-from="${p.uid}" data-loc="${w.zone}"` : ""} title="${esc(w.tip)}"><span class="g">${g(w.glyph)}</span><div><em>${esc(w.label)}</em><b>${esc(w.name || "empty")}</b></div></div>`).join("");
  const rows = p.pack.map(r => `<div class="row-it ${r.new ? "new" : ""} ${isPicked(p.uid, r.loc) ? "on" : ""}" data-from="${p.uid}" data-loc="${r.loc}" title="${esc(r.tip)}">
      <span class="g">${g(r.glyph)}</span><span>${esc(r.name)}</span>${r.qty > 1 || r.new ? `<small>×${r.qty}${r.new ? ` <b>+${r.new}</b>` : ""}</small>` : ""}<em>${kg(r.qty * r.kg)}</em></div>`).join("");
  return `<div class="leather col ${refused ? "refuse" : ""}" data-col="${p.uid}">
    <div class="who"><div class="medal">${face(p.portrait, p.name)}</div><div><b>${esc(p.name)}</b><span>${esc(p.sub)}</span></div></div>
    <div class="meter"><div class="barlbl"><span>Hit points</span><b class="${hp ? "red" : ""}">${p.hp[0]} / ${p.hp[1]}</b></div>
      <div class="bar hp ${hp ? "low" : ""}"><i style="width:${p.hp[0] / p.hp[1] * 100}%"></i></div>
      <div class="barlbl"><span>Load</span><b class="${over ? "red" : ""}">${kg(p.kg)} / ${kg(p.normal)} · max ${kg(p.max)}</b></div>
      <div class="bar load"><i class="${over ? "over" : ""}" style="width:${Math.min(100, p.kg / p.max * 100)}%"></i><span class="norm" style="left:${p.normal / p.max * 100}%"></span></div></div>
    <div class="slots">${worn}</div><div class="rows">${rows}</div>
    ${refused ? `<div class="why"><b>Won't fit</b>${esc(refused.why)}</div>` : ""}</div>`;
}

function loot() {
  const L = R.loot;
  header("The field", `${where()} · what the dead and the fallen left`);
  let h = `<div class="paper" id="field" data-col="field"><div class="kicker">Left on the field<em>drag to a pack, or click, then click where</em></div>
    <div class="fhead"><b>${plural(L.stacks, "stack")}</b><span>${L.things} things · ${kg(L.kg)}<br>the pack's kit and your own dead's</span></div><div class="wares">`;
  if (!L.cats.length) h += `<div class="empty-field">Nothing is left on the field.</div>`;
  for (const c of L.cats) h += `<div class="cat">${esc(c.label)}</div>` + c.rows.map(ware).join("");
  h += `</div><div class="fieldfoot"><p>Whatever is still here when the band goes on is left behind for good.</p></div></div><div id="packs">`;
  for (const p of L.packs) h += column(p, L.refused && L.refused.uid === p.uid ? L.refused : null);
  const took = L.taken.map(t => `${t.items.map(([n, q]) => `${q > 1 ? q + " " : "the "}${esc(n)}`).join(", ")} to <b>${esc(t.name)}</b>`).join(" · ");
  h += `</div><div class="leather" id="lootfoot"><div class="bigbtn ghost small" data-go="auto">${ico("item/knapsack")}Take what fits</div>
    ${L.can_distribute ? `<div class="bigbtn ghost small" data-go="distribute" title="Share the load out by what each can carry">${ico("action/rally-the-troops")}Distribute load</div>` : ""}
    <i>${took ? `${took} · ` : ""}${L.stacks ? `${plural(L.stacks, "stack")} still on the field` : "the field is bare"}</i>
    <div class="bigbtn" data-go="next">${L.stacks ? "Leave the rest · go on" : "Go on"}</div></div>`;
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
  const s = el.closest("[data-from]");
  if (!s) return null;
  const loc = s.dataset.from === "field" || /^\d+$/.test(s.dataset.loc) ? +s.dataset.loc : s.dataset.loc;
  return {from: s.dataset.from, loc};
}

function give(src, el) {
  const col = el.closest("[data-col]");
  if (!col) return false;
  const to = col.dataset.col;
  if (to === "field" && src.from === "field") return false;
  if (to === src.from) return false;
  const slot = el.closest(".slot[data-zone]");
  const w = src.from === "field" ? wareOf(src.loc) : null;
  const body = {picks: [{from: src.from, loc: src.loc, qty: w ? Math.min(qty[w.name] ?? w.qty, w.qty) : undefined}], to,
    zone: slot && to !== "field" ? slot.dataset.zone : "pack"};
  pick = null;
  Sound.play("click");
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
  s.innerHTML = `<span class="g">${g(it.glyph)}</span><div><b>${esc(it.name)}</b><br><span>${src.from === "field" ? "from the field" : "from a pack"}</span></div>`;
  s.hidden = false;
}

function moveSlip(e) {
  const st = $("screen").getBoundingClientRect(), k = st.width / 1920;
  $("slip").style.left = (e.clientX - st.left) / k + 14 + "px";
  $("slip").style.top = (e.clientY - st.top) / k + 10 + "px";
  document.querySelectorAll(".target").forEach(t => t.classList.remove("target"));
  const el = document.elementFromPoint(e.clientX, e.clientY);
  const over = el && (el.closest(".slot[data-zone]") || el.closest("[data-col]"));
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
  header("The arena pays", `<b>${esc(P.bout || R.place)}</b> · the Pit, after the bout · day ${R.day}`,
    `<div class="stat"><b>${money(P.amount)}</b><span>the purse</span></div><div class="stat"><b>${money(net)}</b><span>over the stake</span></div>`);
  const deeds = P.deeds.map(d => `<div class="deedline">Deed · <b>${esc(d.name)}</b>: ${esc(d.blurb)} +${d.rep} with ${esc(d.faction)}</div>`).join("");
  let h = `<div class="paper" id="pit"><div class="pile"><div><b>${money(P.amount)}</b><span>in copper</span></div></div>
    <div><h2>${P.paid_to ? "The purse is pocketed" : "Who pockets the purse?"}</h2><p>The purse lands whole on one fighter: the guild has no treasury. Hand coin on from the band's sheet afterwards, as any item.</p>
    <div class="sums"><div>Staked<b>${money(stake)}</b></div><div>${P.fighters} fighters × ${money(P.entry)}</div><div>Won<b class="good">${money(P.amount)}</b></div>
      <div>Net<b class="${net >= 0 ? "good" : "bad"}">${net >= 0 ? "+" : "−"}${money(Math.abs(net))}</b></div></div>${deeds}
      ${P.note ? `<div class="deedline" style="color:#7d5c37">${esc(P.note)}</div>` : ""}</div></div><div id="hands">`;
  for (const m of P.members) {
    const paid = P.paid_to === m.uid;
    h += `<div class="leather hand ${paid ? "paid" : P.paid_to ? "spent" : ""}" data-uid="${m.uid}"><div class="medal">${face(m.portrait, m.name)}</div>
      <b>${esc(m.name)}</b><span>${esc(m.sub)}</span>
      <div class="was">Carries<b class="${paid ? "after" : ""}">${money(m.money)}</b></div>
      ${P.paid_to ? "" : `<div class="give"><div class="bigbtn ghost small" data-give="${m.uid}">${ico("item/two-coins")}Give ${money(P.amount)}</div></div>`}</div>`;
  }
  h += `</div><div id="pursefoot"><i>${P.paid_to ? "The purse is spoken for." : "Continue opens once someone holds the purse."}</i>
    <div class="bigbtn ${P.paid_to ? "" : "ghost off"}" data-go="next">Continue</div></div>`;
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
$("body").addEventListener("click", e => {
  const go = e.target.closest("[data-go]");
  if (go && !go.classList.contains("off")) { Sound.play("click"); post(go.dataset.go); return; }
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

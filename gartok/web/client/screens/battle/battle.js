// The battle screen: asks the server for the side's view of the fight, draws it, and sends the
// player's decisions back. Every rule is the server's; this file only shows and asks. The helpers
// ($, api, esc, face, Sound) are the shell's.
"use strict";

const AI_DELAY = 480;      // the pause before an AI turn the side sees, the server's time included
const STEP_MS = 110;       // a token's walk, per cell
const STEP_PAUSE = 260;    // between two steps of one turn
const ICONS = {
  attack: "action/backstab", sneak_attack: "action/backstab", precise_thrust: "action/targeting",
  cleave: "action/crush", repel_strike: "action/riposte", maiming_strike: "action/amputation",
  armor_pierce: "action/disintegrate", power_shot: "action/bowman", extreme_shot: "action/targeting",
  hook_shield: "action/catch", javelin_charge: "action/trench-assault", parry_strike: "action/riposte",
  long_thrust: "action/expander", wrest: "action/snatch", dragon_breath: "action/kindle", tail_sweep: "action/slalom",
  zombie_bite: "action/tearing", grab: "action/grab", escape_grapple: "action/dodging",
  takedown: "action/boot-kick", stand_up: "action/muscle-up",
  throw: "action/throwing-ball", demoralize: "action/screaming", assess: "action/look-at",
  push: "action/push", defend: "body/bell-shield", nonlethal: "action/slap", reload: "gui/clockwise-rotation",
  attack_tongue: "action/swallow", flee: "action/run", delay: "gui/backward-time", end: "gui/halt",
  first_aid: "body/heart-inside", stabilize: "body/heart-organ", capture: "action/arrest",
  drink_potion: "action/drinking", signal_horn: "action/shouting", pick_up: "action/snatch", draw: "action/switch-weapon",
  disarm: "action/drop-weapon", investigate: "action/look-at", jump: "action/jump-across",
  climb: "action/mountain-climbing", drop: "action/stairs-goal", fly_up: "action/flying-fox", fly_down: "action/stairs-goal", swim: "action/drowning",
  share_magic: "action/transfuse", eat_corpse: "action/eating", spin_web: "action/hive-mind",
  mount: "action/leapfrog", dismount: "action/kneeling", lift_rider: "action/muscle-up",
  pixie_dust: "action/fruiting", wake_up: "action/shaking-hands", spells: "action/meditation",
};
const iconOf = id => `url(/assets/icons/${id.startsWith("spell:") ? "action/meditation" : (ICONS[id] || "gui/triangle-target")}.svg)`;
const ROMAN = n => { const m = [[10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]]; let s = ""; for (const [v, r] of m) while (n >= v) { s += r; n -= v; } return s || n; };

let S = null;
const ui = {tab: "combat", aim: null, route: null, hover: null, armed: null, inspect: null, busy: false, error: null,
            turn: null, dragged: false, spellbook: false};
const SEAT = {player: "var(--enamel)", ally: "var(--moss)", enemy: "var(--blood)", third: "var(--violet)"};

async function act(body, path = "/api/battle/act") {
  if (ui.busy) return;
  ui.busy = true;
  try {
    const r = await api(path, {...body, inspect: ui.inspect});
    ui.aim = null; ui.route = null; ui.armed = null; ui.error = null; ui.loot = null; ui.ledger = null; ui.draw = null;
    await playSteps(r.steps);
  } catch (e) {
    ui.error = e.message; renderHint();
  } finally { ui.busy = false; }
  pump();
}

// what the side does not decide plays on its own; a question put to a person stops it
const waiting = () => S.setup || S.talk || S.handoff;

async function pump() {
  if (!S || S.winner || S.my_turn || waiting() || ui.busy) return;
  ui.busy = true;
  try {
    const t0 = performance.now();
    const r = await api("/api/battle/advance", {inspect: ui.inspect});
    if (r.steps.some(shows)) await sleep(AI_DELAY - (performance.now() - t0));
    await playSteps(r.steps);
  } finally { ui.busy = false; }
  pump();
}

const shows = st => st.moves.length || st.fx.length || st.acts.length || st.cues.length;

// one step per decision: the walks first, then the board after it, then what it showed
async function playSteps(steps) {
  for (const [i, st] of steps.entries()) {
    for (const cue of st.sounds) Sound.play(cue);
    if (S && st.moves.length) await walk(st.moves);
    const actor = S && st.acts.length && Board.zoomed() && S.units.find(t => t.id === st.acts[0].actor);
    if (actor) Board.reveal(actor.pos, actor.fp);
    await apply(st.state, st);
    if (shows(st) && i < steps.length - 1) await sleep(STEP_PAUSE);
  }
}

async function walk(moves) {
  const box = $("tokens"), runs = [];
  const lead = S.units.find(t => t.id === moves[0].id);
  if (lead && Board.zoomed()) Board.reveal(moves[0].path.at(-1), lead.fp);
  for (const m of moves) {
    const el = box.querySelector(`[data-id="${m.id}"]`), u = S.units.find(t => t.id === m.id);
    if (!el || !u) continue;
    const d = el.offsetWidth, half = Board.layout.cell * u.fp / 2;
    const pts = m.path.map(([x, y]) => ({left: `${Board.cx(x) + half - d / 2}px`, top: `${Board.cy(y) + half - d / 2}px`}));
    const anim = el.animate(pts, {duration: STEP_MS * (pts.length - 1), easing: "linear"});
    runs.push(anim.finished.then(() => { el.style.left = pts.at(-1).left; el.style.top = pts.at(-1).top; }));
  }
  await Promise.all(runs);
}

async function apply(state, events) {
  const first = !S;
  S = state;
  if (ui.inspect && !S.inspect) ui.inspect = null;
  await Board.draw(S);
  const mine = S.my_turn && S.active ? S.active.id : null;
  if (mine && mine !== ui.turn && Board.zoomed()) {
    const u = S.units.find(t => t.id === mine);
    if (u) Board.reveal(u.pos, u.fp);
  }
  ui.turn = mine;
  renderAll();
  if (events) playEvents(events);
  if (first) pump();
}

// everyone in one cell, the one standing first: a fighter may stand on a body (dying or stable)
function unitsAt(cell) {
  if (!S || !cell) return [];
  const [x, y] = cell;
  return S.units.filter(u => x >= u.pos[0] && x < u.pos[0] + u.fp && y >= u.pos[1] && y < u.pos[1] + u.fp)
    .sort((a, b) => a.downed - b.downed);
}

// [size as a share of the cell, x, y offset in 1/100 cells]: the top one up and right, the bodies down and left
const STACK = [[[.8, 9, -9], [.8, -11, 11]], [[.78, 0, -10], [.7, -13, 13], [.7, 14, 13]]];
function stackSlot(n, i) {
  const set = STACK[n > 2 ? 1 : 0];
  return set[i] || [.62, (i - 2) * 11, 16];
}

function arc(d, frac, col) {
  const r = d / 2 + 8, c = 2 * Math.PI * r, span = .36 * c;
  return `<svg class="arc" width="${2 * r}" height="${2 * r}" style="left:${d / 2 - r}px;top:${d / 2 - r}px"><g transform="rotate(${90 - .18 * 360} ${r} ${r})">
    <circle cx="${r}" cy="${r}" r="${r - 1}" fill="none" stroke="rgba(26,18,10,.85)" stroke-width="6" stroke-dasharray="${span} ${c}" stroke-linecap="round"/>
    <circle cx="${r}" cy="${r}" r="${r - 1}" fill="none" stroke="${col}" stroke-width="3" stroke-dasharray="${span * Math.max(0, frac)} ${c}" stroke-linecap="round"/></g></svg>`;
}

// the condition gems on a token's rim, the heaviest first; the last slot counts what does not fit
const GEMS = 4;
function gems(u, d) {
  const g = Math.max(14, Math.min(18, Math.round(d * .3))), r = d / 2 + 1;
  const step = Math.max(24, 1.15 * g / r * 180 / Math.PI);
  const spot = i => {
    const a = (-118 + step * i) * Math.PI / 180;
    return `left:${d / 2 + r * Math.cos(a) - g / 2}px;top:${d / 2 + r * Math.sin(a) - g / 2}px;width:${g}px;height:${g}px`;
  };
  const marks = u.marks || [];
  const shown = marks.slice(0, marks.length > GEMS ? GEMS - 1 : GEMS);
  const rest = marks.length - shown.length;
  return shown.map((m, i) => `<div class="gem hz c-${m.cls}" data-zone="cond:${u.id}" style="${spot(i)}">${ico(m.icon)}</div>`).join("")
    + (rest ? `<div class="gem more hz" data-zone="cond:${u.id}" style="${spot(shown.length)}">+${rest}</div>` : "");
}

function renderTokens() {
  const box = $("tokens"), L = Board.layout, seen = new Set();
  const offered = new Set(ui.aim ? ui.aim.targets : []);
  const stacks = new Map();
  for (const u of S.units) if (u.fp === 1) {
    const k = u.pos.join(",");
    stacks.set(k, [...(stacks.get(k) || []), u]);
  }
  for (const list of stacks.values()) list.sort((a, b) => a.downed - b.downed);
  const offerCol = {attack: "#c9473a", demo: "#9a5cc0", heal: "#6ea65a", move: "#5b8fc0", spell: "#f0d79e", throw: "#e0882c"}[ui.aim && ui.aim.kind] || "#f0d79e";
  for (const u of S.units) {
    seen.add(u.id);
    let el = box.querySelector(`[data-id="${u.id}"]`);
    if (!el) { el = document.createElement("div"); el.dataset.id = u.id; box.appendChild(el); }
    const pile = u.fp === 1 ? stacks.get(u.pos.join(",")) : null, n = pile ? pile.length : 1, at = pile ? pile.indexOf(u) : 0;
    const [k, ox, oy] = n > 1 ? stackSlot(n, at) : [u.fp > 1 ? .9 : .84, 0, 0];
    const d = Math.round(L.cell * u.fp * k + (u.active ? 4 : 0));
    const sc = L.cell / 100;
    const x = Board.cx(u.pos[0]) + L.cell * u.fp / 2 - d / 2 + ox * sc, y = Board.cy(u.pos[1]) + L.cell * u.fp / 2 - d / 2 + oy * sc;
    const cls = ["tok", "seat-" + u.seat];
    if (u.active) cls.push("active");
    if (offered.has(u.id)) cls.push("offered");
    else if (ui.armed === u.id || (ui.inspect === u.id && u.side === "foe")) cls.push("target");
    if (u.downed) cls.push("downed", "is-" + u.state);
    if (ui.lift === u.id) cls.push("lift");
    el.className = cls.join(" ");
    el.style.cssText = `left:${x}px;top:${y}px;width:${d}px;height:${d}px;z-index:${n - at};--offer:${offerCol}`;
    const col = u.hp_frac > .5 ? "#7fa557" : "#d0493a";
    const badge = n === 1 && (u.dying || u.altitude) ? `<div class="badge">${esc(u.dying || "↑" + u.altitude)}</div>` : "";
    const nameplate = (u.active && S.my_turn) || ui.armed === u.id || ui.inspect === u.id
      ? `<div class="nameplate ${u.side}">${esc(u.name)}</div>` : "";
    const carried = u.carries ? `<div class="flagbadge ${u.carries}"${tip(tr(u.carries === "ally" ? "battle.flag_ally" : "battle.flag_foe"))}>⚑</div>` : "";
    const html = face(u.portrait, u.name) + arc(d, u.hp_frac, col) + (u.seat === "player" ? `<div class="pennant"></div>` : "") + badge + gems(u, d) + carried + nameplate;
    if (el._html !== html) { el.innerHTML = html; el._html = html; }
  }
  for (const f of S.ctf || []) {
    const id = "flag-" + f.side;
    seen.add(id);
    let el = box.querySelector(`[data-id="${id}"]`);
    if (!f.pos || f.carrier) { if (el) el.hidden = true; continue; }
    if (!el) { el = document.createElement("div"); el.dataset.id = id; el.textContent = "⚑"; box.appendChild(el); }
    el.hidden = false;
    el.className = "flagmark " + f.side;
    el.style.cssText = `left:${Board.cx(f.pos[0])}px;top:${Board.cy(f.pos[1])}px;width:${L.cell}px;height:${L.cell}px;font-size:${Math.round(L.cell * .6)}px`;
  }
  const lying = new Map(), fallen = new Map();
  for (const t of S.under) lying.set(t.pos.join(","), [...(lying.get(t.pos.join(",")) || []), t]);
  for (const list of stacks.values()) if (list.length > 1 && list.some(u => u.downed)) fallen.set(list[0].pos.join(","), list.filter(u => u.downed));
  const medal = (id, cell, kind, icon, count, dx, dy) => {
    const [x, y] = cell.split(",").map(Number), d = Math.max(17, Math.round(L.cell * .34));
    seen.add(id);
    let el = box.querySelector(`[data-id="${id}"]`);
    if (!el) { el = document.createElement("div"); el.dataset.id = id; box.appendChild(el); }
    el.className = "medal hz " + kind;
    el.dataset.zone = `${kind}:${cell}`;
    el.style.cssText = `left:${Board.cx(x) + L.cell * dx - d / 2}px;top:${Board.cy(y) + L.cell * dy - d / 2}px;--d:${d}px`;
    const html = icon + (count > 1 ? `<b>${count}</b>` : "");
    if (el._html !== html) { el.innerHTML = html; el._html = html; }
  };
  for (const [cell, list] of lying) medal("items-" + cell, cell, "items", lootIcon(list[0]), list.length, .84, .16);
  for (const [cell, list] of fallen) medal("bodies-" + cell, cell, "bodies", ico("head/dead-head"), list.length, .84, .84);
  for (const el of [...box.children]) if (!seen.has(el.dataset.id)) el.remove();
}

function pips(marks) {
  if (!marks.length) return "";
  const shown = marks.slice(0, marks.length > 3 ? 2 : 3), rest = marks.length - shown.length;
  return `<div class="pips">${shown.map(m => `<i class="c-${m.cls}">${ico(m.icon)}</i>`).join("")}${rest ? `<i class="more">+${rest}</i>` : ""}</div>`;
}

function renderTop() {
  $("place").textContent = S.meta.name || tr("battle.title");
  $("sub").innerHTML = S.campaign ? esc(S.meta.sub) : tr("battle.sub_lab", {level: esc(S.meta.level), squad: esc(S.meta.squad), seed: esc(S.meta.seed)});
  const coins = S.initiative.map(c => {
    if (!c.id) return `<div class="coin unknown">?</div>`;
    const hp = c.hp_frac == null ? "" : `<div class="hp" style="--c:${c.hp_frac > .5 ? "#7fa557" : "#d0493a"}"><i style="width:${c.hp_frac * 100}%"></i></div>`;
    const mark = {dying: c.dying, stable: "♥", dead: "✝"}[c.state];
    const what = {dying: tr("battle.dying", {n: c.dying}), stable: tr("battle.down_stable"), dead: tr("battle.dead")}[c.state];
    return `<div class="coin seat-${c.seat}${c.active ? " now" : ""}${c.state && c.state !== "up" ? " is-" + c.state : ""}"${tip(what ? tr("battle.coin_tip", {name: c.name, what}) : c.name)}>${face(c.portrait, c.name)}${c.state === "dead" ? "" : hp}${pips(c.marks || [])}${mark ? `<div class="mk">${esc(mark)}</div>` : ""}</div>`;
  }).join("");
  $("init").innerHTML = `<div class="round"><div><small>${tr("battle.round")}</small><span>${ROMAN(S.round)}</span></div></div><div class="chain">${coins}</div>`;
}

const tier = (label, facts) => `<section class="tier"><span>${esc(label)}</span><div class="facts">${facts}</div></section>`;
const weaponFacts = w => `<span><b>${esc(w.name)}</b>${w.damage ? " " + esc(w.damage) : ""}</span>${w.action ? `<span${tip(w.action_tip, "item")}>${esc(w.action)}</span>` : ""}`;
const foeHead = (t, chips, extra) => `<div class="foehead"><div class="med" style="--side:${SEAT[t.seat] || "var(--blood)"}">${face(t.portrait, t.name)}</div>
  <div><h2>${esc(t.name)}</h2>${chips}${extra || ""}</div></div>`;
const lootIcon = t => t.glyph ? ico(t.glyph) : `<i class="flagico ${t.flag}">⚑</i>`;
const groundTier = t => t.loot && t.loot.length ? tier(tr("battle.on_ground"), t.loot.map(l => `<span class="lootrow">${lootIcon(l)}<b>${esc(l.name)}</b></span>`).join("")) : "";
const chipRow = (names, cls = "chip") => `<div class="chips">${names.filter(Boolean).map(c => `<span class="${cls}">${esc(c)}</span>`).join("")}</div>`;

function renderInspect() {
  const box = $("inspect"), t = S.inspect;
  const card = (kicker, head, sections, foot = "") =>
    box.innerHTML = `<div class="kicker">${kicker}</div><div class="bscroll">${head}<div class="known">${sections}</div>${foot}</div>`;
  if (!t) {
    box.innerHTML = `<div class="kicker">${tr("battle.bestiary")}</div><div class="empty">${tr("battle.empty")}</div>`;
    return;
  }
  if (t.kind === "ally") {
    card(tr("battle.your_squad"),
      foeHead(t, `<div class="race">${esc(t.race)} · · ${esc(t.alignment)}</div>${chipRow(t.conditions || [], "chip muted")}`),
      tier(tr("battle.vitals"), `<span>${tr("battle.hp")} <b>${t.hp}/${t.hp_max}</b></span><span>${tr("battle.ac")} <b>${t.ac}</b></span><span>${tr("battle.md")} <b>${t.md}</b></span><span>${tr("battle.speed")} <b>${t.speed}</b></span>`)
        + (t.weapon ? tier(tr("battle.weapon"), weaponFacts(t.weapon)) : "") + groundTier(t),
      S.active && S.active.id === t.id && t.loot.length ? `<div class="assess">${tr("battle.pick_up_note")}</div>` : "");
    return;
  }
  const bars = Array.from({length: t.steps_max}, (_, i) => `<i class="${i < t.steps ? "on" : ""}"></i>`).join("");
  const bands = t.bands.map(b => tier(b.label, b.rows.map(r => r.value == null ? `<span class="q">${esc(r.label)}</span>` : `<span>${esc(r.label)} <b>${esc(r.value)}</b></span>`).join(""))).join("");
  card(tr(ui.armed === t.id ? "battle.bestiary_target" : "battle.bestiary_foe"),
    foeHead(t, `<div class="race">${esc(t.race)} · ${esc(t.alignment)}</div>${chipRow([t.size, ...(t.conditions || [])])}`, `<div class="health">${bars}</div>`),
    tier(tr("battle.arms"), weaponFacts({...t.weapon, damage: ""}) + t.equipment.map(([k, v]) => `<span>${esc(k)} <b>${esc(v)}</b></span>`).join("")) + groundTier(t) + bands,
    `<div class="assess">${tr("battle.assess", {read: esc(t.read)})}</div>`);
}

function renderLog() {
  const names = new Map(S.units.map(u => [u.name, u.side]));
  const box = $("log"), pinned = box.scrollHeight - box.scrollTop - box.clientHeight < 24;
  const lines = S.log.map(line => {
    const m = /^-+\s*Round\s+(\d+)\s*-+$/i.exec(line.trim());
    if (m) return `<div class="rnd">${tr("battle.round")} ${ROMAN(+m[1])}</div>`;
    let html = esc(line);
    for (const [n, side] of [...names].sort((a, b) => b[0].length - a[0].length))
      html = html.split(esc(n)).join(`<span class="${side === "ally" ? "a" : "f"}">${esc(n)}</span>`);
    return `<p>${html}</p>`;
  });
  box.innerHTML = lines.join("");
  if (pinned) box.scrollTop = box.scrollHeight;
}

function renderUnit() {
  const a = S.active, box = $("unit");
  if (!a) { box.innerHTML = `<div class="waiting">${tr("battle.out_of_sight")}</div>`; return; }
  const own = a.side === "ally" && a.hp != null;
  const hp = own
    ? (a.hp_max <= 10 ? `<div class="drops">${Array.from({length: a.hp_max}, (_, i) => `<i class="${i < a.hp ? "" : "off"}"></i>`).join("")}</div>`
       : `<div class="hpbar"><i style="width:${a.hp_frac * 100}%"></i></div>`)
    : `<div class="hpbar"><i style="width:${a.hp_frac * 100}%"></i></div>`;
  const w = a.weapon;
  const lvl = a.level == null ? "" : `<div class="lvl"${tip(tr("battle.level_tip", {level: a.level, combat: a.tracks.combat, work: a.tracks.work, magic: a.tracks.magic}))}><small>${tr("battle.lv")}</small>${a.level}</div>`;
  box.innerHTML = `<div class="med" style="--side:${SEAT[a.seat]}">${face(a.portrait, a.name)}</div>${lvl}
    <div class="body"><h1>${esc(a.name)}</h1><div class="race">${esc(a.race)} · · ${esc(a.alignment)}</div>
    ${S.my_turn ? `<div class="stats"><div class="stat hp"><span>${tr("battle.hit_points")}${own ? ` · ${a.hp}/${a.hp_max}` : ""}</span>${hp}</div>
      <div class="stat"><span>${tr("battle.ac")}</span><b>${a.ac ?? "?"}</b></div><div class="stat"><span>${tr("battle.md")}</span><b>${a.md ?? "?"}</b></div><div class="stat"><span>${tr("battle.speed")}</span><b>${a.speed}</b></div></div>
      ${w ? `<div class="weapon"><b>${esc(w.name)}</b>${esc(w.damage || "")}${w.thrown ? ` · ${tr("battle.thrown", {n: w.thrown})}` : ""}${w.range ? ` · ${tr("battle.range", {n: w.range})}` : ""}${w.action ? `<em>${esc(w.action)}</em>` : ""}${a.off_hand ? ` · ${tr("battle.off_hand", {name: esc(a.off_hand)})}` : ""}</div>` : `<div class="weapon">${tr("battle.unarmed")}${a.off_hand ? ` · ${tr("battle.off_hand", {name: esc(a.off_hand)})}` : ""}</div>`}`
      : `<div class="race" style="margin-top:22px;font-size:20px">${tr(S.setup ? "battle.waits_begin" : a.side === "ally" ? "battle.fights_alone" : "battle.taking_turn")}</div>`}</div>
    ${S.my_turn ? `<div class="ap"><span>${tr("battle.action")}</span><div class="coins">${Array.from({length: a.ap_max}, (_, i) => `<i class="${i < a.ap_max - a.ap ? "spent" : ""}"></i>`).join("")}</div></div>` : ""}`;
}

function plate(a, {id = a.id, name = a.toggle ? a.label : a.name, sel = ui.aim && ui.aim.id === a.id, sub = ""} = {}) {
  const cls = ["plate", a.enabled ? "" : "off", sel ? "sel" : "", a.toggle && /ON/.test(a.label) ? "on" : ""].join(" ");
  return `<div class="${cls}" data-action="${esc(id)}"${tip(a.why ? `${a.label} — ${a.why}` : a.label)}>
    <div class="key">${a.hotkey ?? ""}</div><div class="cost">${"<i></i>".repeat(a.cost)}</div>
    <div class="ico mask" style="--icon:${iconOf(id)}"></div><div class="nm">${esc(name)}${sub ? `<small>${esc(sub)}</small>` : ""}</div></div>`;
}

// the row: the spells folded into one plate, then the tab's actions; Delay sits apart, always in reach
function renderPlates() {
  const all = [...S.actions.combat, ...S.actions.utility];
  const spells = ui.tab === "combat" ? S.actions.combat.filter(a => a.id.startsWith("spell:")) : [];
  const list = (S.actions[ui.tab] || []).filter(a => a.id !== "end" && a.id !== "delay" && !a.id.startsWith("spell:"));
  document.querySelectorAll("#tabs span").forEach(t => t.classList.toggle("on", t.dataset.tab === ui.tab));
  const aimingSpell = ui.aim && ui.aim.id.startsWith("spell:");
  const book = spells.length ? plate({label: tr("battle.cast_spell"), cost: 0, enabled: spells.some(a => a.enabled)},
                                     {id: "spells", name: tr("battle.spells"), sel: ui.spellbook || aimingSpell}) : "";
  $("plates").innerHTML = book + list.map(a => plate(a)).join("");
  const delay = all.find(a => a.id === "delay");
  $("fixed").innerHTML = delay ? plate(delay, {sub: tr("battle.others_first")}) : "";
  const open = ui.spellbook && spells.length && S.my_turn;
  $("spellbook").hidden = !open;
  if (open) $("spellbook").innerHTML = `<div class="kicker">${tr("battle.spells")}</div>` + spells.map(a =>
    `<div class="row ${a.enabled ? "" : "off"} ${ui.aim && ui.aim.id === a.id ? "sel" : ""}" data-action="${esc(a.id)}">
      <div class="ico mask" style="--icon:${iconOf(a.id)};width:22px;height:22px;color:#5a2116"></div>${esc(a.name)}
      <div class="cost">${"<i></i>".repeat(a.cost)}</div></div>`).join("");
  const sel = $("plates").querySelector(".sel");
  if (sel) {
    const p = $("plates");
    if (sel.offsetLeft < p.scrollLeft) p.scrollLeft = sel.offsetLeft - 30;
    else if (sel.offsetLeft + sel.offsetWidth > p.scrollLeft + p.clientWidth) p.scrollLeft = sel.offsetLeft + sel.offsetWidth - p.clientWidth + 30;
  }
  nudges();
  $("seal").classList.toggle("off", !S.my_turn);
}

function nudges() {
  const p = $("plates");
  $("nudgeL").hidden = p.scrollLeft <= 1;
  $("nudgeR").hidden = p.scrollLeft + p.clientWidth >= p.scrollWidth - 1;
}

function renderHint() {
  let h;
  if (ui.error) h = ui.error;
  else if (S.winner) h = tr("battle.hint_over");
  else if (S.setup && S.setup.kind === "flag") h = tr("battle.hint_flag");
  else if (S.setup) h = tr("battle.hint_trap", {name: S.setup.name});
  else if (S.talk) h = tr("battle.hint_talk");
  else if (!S.my_turn) h = tr("battle.hint_other");
  else if (ui.aim) h = tr(ui.aim.cellTarget ? "battle.hint_aim_cell" : "battle.hint_aim_target", {name: ui.aim.name});
  else if (S.flags.mopping_up) h = tr("battle.hint_mopping");
  else if (S.flags.binding) h = tr("battle.hint_binding");
  else if (S.flags.ctf) h = tr("battle.hint_ctf");
  else if (S.flags.can_flee) h = tr("battle.hint_flee");
  else h = tr("battle.hint_default");
  $("hint").textContent = h;
}

function renderAll() {
  renderTop(); renderTokens(); renderInspect(); renderLog(); renderUnit(); renderPlates(); renderHint();
  Board.overlay(S, ui);
  $("withdraw").hidden = !S.flags.can_withdraw;
  $("skiptraps").hidden = !(S.setup && S.setup.kind === "trap");
  renderLoot();
  renderDraw();
  renderLedger();
  renderDialog();
  if (S.winner) showEnd();
}

// the questions the fight waits on: the next person taking the seat, or a challenge to answer
function renderDialog() {
  const d = $("dialog");
  if (ui.picking) return;
  d.classList.toggle("opaque", !!S.handoff);
  if (S.handoff) {
    d.innerHTML = `<div class="paper ask" style="text-align:center"><div class="kicker">${tr("battle.hand_over")}</div>
      <h2 style="margin-top:16px">${tr(S.handoff === "player" ? "battle.turn_first" : "battle.turn_second")}</h2>
      <p class="line">${tr("battle.hand_line")}</p>
      <div class="row" style="justify-content:center"><div class="btn" data-seat>${tr("battle.seat")}</div></div></div>`;
  } else if (S.talk) {
    const t = S.talk, lead = t.leader;
    const body = t.result
      ? `<div class="result ${esc(t.result.kind)}">${esc(t.result.text)}</div><div class="row"><div class="btn" data-goon>${tr("battle.go_on")}</div></div>`
      : `<div class="cols"><div>${t.speakers.map(s => `<div class="who ${s.selected ? "sel" : ""}" data-speaker="${s.id}"><b>${esc(s.name)}</b><small>${esc(s.caption)}</small></div>`).join("")}</div>
         <div>${t.options.map(o => `<div class="opt ${o.block ? "off" : ""}" data-verb="${esc(o.id)}"><span class="check">${esc(o.check)}${o.odds != null ? ` · ${Math.round(o.odds * 100)}%` : ""}</span>
           <b>${esc(o.label)}</b><small>${esc(o.block || o.note)}</small></div>`).join("")}</div></div>`;
    d.innerHTML = `<div class="paper ask"><div class="kicker">${esc(t.title)}</div>
      <div class="head">${lead ? `<div class="face">${face(lead.portrait, lead.name)}</div>` : ""}
      <div>${lead ? `<h2>${esc(lead.name)}</h2><div class="race">${esc(lead.caption)}</div>` : ""}
      <p class="line">${esc(t.line)}</p><div class="foes">${t.foes.map(esc).join(" · ")}</div></div></div>${body}</div>`;
  }
  d.hidden = !(S.handoff || S.talk);
}

// a choice between a few values (the disk's height): resolves to the one picked, or null
function pick(title, options) {
  const d = $("dialog");
  ui.picking = true;
  d.classList.remove("opaque");
  d.innerHTML = `<div class="paper ask" style="width:560px"><div class="kicker">${esc(title)}</div>
    <div class="heights" style="margin-top:18px">${options.map(([v, label]) => `<div class="opt" data-pick="${v}"><b>${esc(label)}</b></div>`).join("")}</div>
    <div class="row"><div class="ghost-btn" data-pick="">${tr("battle.cancel")}</div></div></div>`;
  d.hidden = false;
  return new Promise(done => {
    d.onclick = e => {
      const p = e.target.closest("[data-pick]");
      if (!p) return;
      d.onclick = null; d.hidden = true; ui.picking = false;
      done(p.dataset.pick === "" ? null : Number(p.dataset.pick));
    };
  });
}

function center(cell, fp = 1) {
  const L = Board.layout;
  return [Board.cx(cell[0]) + L.cell * fp / 2, Board.cy(cell[1]) + L.cell * fp / 2];
}

function playEvents(ev) {
  const box = $("fx");
  const add = (html, cls, [x, y], ms) => {
    const el = document.createElement("div");
    el.className = cls; el.innerHTML = html; el.style.left = x + "px"; el.style.top = y + "px";
    box.appendChild(el); setTimeout(() => el.remove(), ms);
  };
  ev.fx.forEach((f, i) => setTimeout(() => {
    const [x, y] = center(f.pos);
    add(esc(f.text), `float ${f.kind === "ok" && /^\+/.test(f.text) ? "heal" : f.kind}`, [x, y - Board.layout.cell * .3], 1300);
  }, i * 90));
  for (const c of ev.cues) {
    const [x, y] = center(c.pos);
    add(tr(c.kind === "crit" ? "battle.critical" : "battle.miss"), `float ${c.kind === "crit" ? "crit" : "faint"}`, [x, y - Board.layout.cell * .7], 1300);
  }
  if (ev.cues.some(c => c.kind === "crit")) {
    const b = $("banner");
    b.textContent = tr("battle.crit_banner");
    b.classList.remove("on"); void b.offsetWidth; b.classList.add("on");
  }
  for (const a of ev.acts) {
    const u = S.units.find(t => t.id === a.actor);
    if (!u) continue;
    const from = center(u.pos, u.fp);
    if (a.name) add(esc(a.name), "callout", [from[0], from[1] - Board.layout.cell * .55], 1600);
    if (a.aim) missile(from, center(a.aim));
  }
}

function missile([x0, y0], [x1, y1]) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", 1384); svg.setAttribute("height", 780);
  svg.style.cssText = "position:absolute;left:0;top:0;overflow:visible";
  const mx = (x0 + x1) / 2, my = Math.min(y0, y1) - Math.hypot(x1 - x0, y1 - y0) * .25;
  const p = document.createElementNS(svg.namespaceURI, "path");
  p.setAttribute("d", `M${x0},${y0} Q${mx},${my} ${x1},${y1}`);
  p.setAttribute("fill", "none"); p.setAttribute("stroke", "rgba(150,40,26,.9)"); p.setAttribute("stroke-width", "3");
  p.setAttribute("stroke-dasharray", "10 7"); p.setAttribute("stroke-linecap", "round");
  svg.appendChild(p); $("fx").appendChild(svg);
  const len = p.getTotalLength();
  p.animate([{strokeDashoffset: len, opacity: 1}, {strokeDashoffset: 0, opacity: 1}, {opacity: 0}], {duration: 900, easing: "ease-out"});
  setTimeout(() => svg.remove(), 900);
}

async function showEnd(picker = false) {
  const m = $("modal");
  const fights = Shell.lab ? await api("/api/lab/fights") : null;
  const won = S.result === "VICTORY";
  m.innerHTML = `<div class="paper endcard">${picker ? `<h1 style="font-size:40px">${tr("battle.new_fight_h")}</h1>` : `<h1 class="${won ? "" : "lost"}">${tr("result." + S.result)}</h1>`}
    <p>${tr(picker ? "battle.pick_lab" : won ? "battle.won" : S.result === "FLED" ? "battle.fled" : "battle.lost")}</p>
    ${fights ? `<div class="row"><select id="fightsel">${fights.map(f => `<option value="${f.id}" ${f.id === S.meta.fight ? "selected" : ""}>${esc(f.name)}</option>`).join("")}</select>
    <select id="playersel"><option value="1">${tr("battle.one_player")}</option><option value="2" ${S.meta.players === 2 ? "selected" : ""}>${tr("battle.two_players")}</option></select>
    <div class="btn" id="again">${tr("battle.fight")}</div>${picker ? `<div class="ghost-btn" id="cancel">${tr("battle.cancel")}</div>` : ""}</div>` : ""}
    ${S.campaign ? `<div class="row"><div class="btn" id="goon">${tr("battle.go_on")}</div></div>` : ""}</div>`;
  m.hidden = false;
  if (S.campaign) $("goon").onclick = async () => { await api("/api/battle/done", {}); location.reload(); };
  if (!fights) return;
  $("again").onclick = async () => {
    const f = fights.find(x => x.id === $("fightsel").value);
    m.hidden = true; ui.inspect = null; ui.aim = null; ui.armed = null;
    const r = await api("/api/lab/new", {fight: f.id, level: S.meta.level, squad: f.squad > 3 ? f.squad : S.meta.squad,
                                     players: Number($("playersel").value)});
    S = null; $("tokens").innerHTML = "";
    await apply(r.steps.at(-1).state);
  };
  if (picker) $("cancel").onclick = () => { m.hidden = true; };
}

function sheetPoint(e) {
  const r = $("sheet").getBoundingClientRect();
  return [(e.clientX - r.left) * 1384 / r.width, (e.clientY - r.top) * 780 / r.height];
}

async function inspect(id) {
  ui.inspect = id;
  S = await api(`/api/battle/state${id ? `?inspect=${id}` : ""}`);
  renderAll();
}

async function selectAction(id) {
  if (!S.my_turn || ui.busy) return;
  if (id === "spells") { ui.spellbook = !ui.spellbook; renderAll(); return; }
  ui.spellbook = false;
  const a = [...S.actions.combat, ...S.actions.utility].find(x => x.id === id);
  if (!a || !a.enabled) return;
  if (a.id === "end") return act({action: "end"});
  if (a.id === "draw") {
    ui.draw = ui.draw ? null : {sel: Math.max(0, S.draws.findIndex(r => r.ok && !r.stow))};
    ui.aim = null; renderAll();
    return;
  }
  if (a.id === "pick_up" && S.pickups.length > 1) {
    const u = S.units.find(t => t.id === S.active.id);
    if (ui.loot && ui.loot.mode === "pick") return closeLoot();
    return openLoot(u.pos, "pick");
  }
  if (a.aimed || a.target === "cell") {
    if (ui.aim && ui.aim.id === id) { ui.aim = null; renderAll(); return; }
    const aim = await api(`/api/battle/aim?action=${encodeURIComponent(id)}`);
    ui.aim = {...aim, id, name: a.name, cellTarget: a.target === "cell"};
    ui.route = null; renderAll();
    return;
  }
  act({action: id});
}

// the card of a cell with a body in it: one row per occupant, the ones the armed action takes lit
function pileRows(cell) {
  return unitsAt(cell).map(u => {
    const legal = ui.aim ? ui.aim.targets.includes(u.id) : !!u.attackable;
    const state = u.state === "dying" ? tr("battle.st_dying", {n: u.dying}) : tr(u.state === "stable" ? "battle.st_stable" : u.state === "broken" ? "battle.st_broken" : "battle.st_standing");
    const why = legal ? (ui.aim ? ui.aim.name : tr("battle.strike")) : u.side === "ally" ? tr("battle.why_ally") : tr(u.downed ? "battle.why_not_target" : "battle.why_not_downed");
    return {u, legal, state, why};
  });
}

function openPile(cell, rows = pileRows(cell)) {
  const first = rows.findIndex(r => r.legal);
  ui.pile = {cell, rows, sel: Math.max(0, first)};
  renderPile();
}

function closePile() { ui.pile = null; ui.lift = null; renderPile(); renderTokens(); }

function renderPile() {
  const box = $("pile");
  if (!ui.pile) { box.hidden = true; box.innerHTML = ""; return; }
  const {cell, rows, sel} = ui.pile, L = Board.layout;
  const left = Board.cx(cell[0]) + L.cell + 10, flip = left + 330 > 1384;
  box.style.left = `${flip ? Board.cx(cell[0]) - 340 : left}px`;
  box.style.top = `${Math.min(Math.max(Board.cy(cell[1]) - 20, 4), 780 - 60 - rows.length * 58)}px`;
  box.innerHTML = `<h3>${tr("battle.pile_who", {name: esc(ui.aim ? ui.aim.name : tr("battle.strike"))})}</h3>` + rows.map((r, i) =>
    `<div class="prow ${r.legal ? "" : "off"} ${i === sel ? "sel" : ""}" data-i="${i}"><div class="pface seat-${r.u.seat}">${face(r.u.portrait, r.u.name)}</div>
      <div><b>${esc(r.u.name)}</b><span>${esc(r.state)}</span></div><em>${esc(r.why)}</em></div>`).join("");
  box.hidden = false;
}

async function takePile(i) {
  const r = ui.pile && ui.pile.rows[i];
  if (!r || !r.legal) return;
  const aim = ui.aim;
  closePile();
  return act(aim ? {action: aim.id, target: r.u.id} : {action: "attack", target: r.u.id});
}

$("pile").addEventListener("click", e => {
  const row = e.target.closest(".prow");
  if (row) takePile(Number(row.dataset.i));
});
$("pile").addEventListener("mouseover", e => {
  const row = e.target.closest(".prow");
  if (!row || !ui.pile) return;
  ui.lift = ui.pile.rows[Number(row.dataset.i)].u.id;
  renderTokens();
});

// the things lying on a cell, as a flag by its corner: opened by hovering or clicking the mark, or by Pick up
// when it has more than one thing to lift
const lootAt = cell => S.under.filter(t => t.pos[0] === cell[0] && t.pos[1] === cell[1]);

// the hover zone under the pointer: a condition gem ("cond", key is the token) or a medallion ("items"/"bodies", key is the cell)
function zoneAt(e) {
  let best = null, bestD = Infinity;
  for (const el of $("tokens").querySelectorAll(".hz")) {
    const r = el.getBoundingClientRect();
    if (e.clientX < r.left - 3 || e.clientX > r.right + 3 || e.clientY < r.top - 3 || e.clientY > r.bottom + 3) continue;
    const d = Math.hypot(e.clientX - (r.left + r.right) / 2, e.clientY - (r.top + r.bottom) / 2);
    if (d < bestD) { bestD = d; best = el; }
  }
  if (!best) return null;
  const [kind, key] = best.dataset.zone.split(":");
  return {kind, key, cell: kind === "cond" ? null : key.split(",").map(Number)};
}

function where(p) {
  const u = S.units.find(t => S.active && t.id === S.active.id);
  if (!u) return "";
  const dx = p[0] < u.pos[0] ? -1 : p[0] >= u.pos[0] + u.fp ? 1 : 0, dy = p[1] < u.pos[1] ? -1 : p[1] >= u.pos[1] + u.fp ? 1 : 0;
  return tr("battle.dir." + (!dx && !dy ? "here" : ({"-1,-1": "NW", "0,-1": "N", "1,-1": "NE", "-1,0": "W", "1,0": "E", "-1,1": "SW", "0,1": "S", "1,1": "SE"})[`${dx},${dy}`]));
}

const bodyRows = cell => pileRows(cell).filter(r => r.u.downed).map(r => ({...r.u, state: r.state}));
function openLoot(cell, mode = "hover", kind = "items") {
  ui.loot = {cell, mode, kind, sel: 0};
  renderLoot();
}
function closeLoot() { ui.loot = null; renderLoot(); }

function renderLoot() {
  const box = $("loot"), l = ui.loot;
  const rows = !l ? [] : l.mode === "pick" ? S.pickups.map(p => ({...p, hint: where(p.pos)})) : l.kind === "bodies" ? bodyRows(l.cell) : lootAt(l.cell);
  if (!rows.length) { ui.loot = null; box.hidden = true; box.innerHTML = ""; return; }
  const L = Board.layout, pick = l.mode === "pick", left = Board.cx(l.cell[0]) + L.cell + 10, flip = left + 250 > 1384;
  box.style.left = `${flip ? Board.cx(l.cell[0]) - 260 : left}px`;
  box.style.top = `${Math.min(Math.max(Board.cy(l.cell[1]) - 20, 4), 780 - 60 - rows.length * 44)}px`;
  box.style.pointerEvents = pick ? "auto" : "none";
  box.innerHTML = `<h3>${tr(pick ? "battle.pick_which" : l.kind === "bodies" ? "battle.medal_bodies" : "battle.on_ground")}</h3>` + rows.map((r, i) =>
    l.kind === "bodies" && !pick ? `<div class="lrow"><div class="pface seat-${r.seat}">${face(r.portrait, r.name)}</div><b>${esc(r.name)}</b><em>${esc(r.state)}</em></div>` :
    `<div class="lrow ${pick ? "pick" : ""} ${pick && i === l.sel ? "sel" : ""}" data-i="${i}">${lootIcon(r)}<b>${esc(r.name)}</b>${r.hint ? `<em>${esc(r.hint)}</em>` : ""}</div>`).join("");
  box.hidden = false;
}

// Draw: what the pack offers the hands, hung beside the acting token, with what the hovered choice leaves in them
function renderDraw() {
  const box = $("draw"), rows = S && S.my_turn ? S.draws : [];
  if (!ui.draw || !rows.length) { ui.draw = null; box.hidden = true; box.innerHTML = ""; return; }
  const u = S.units.find(t => S.active && t.id === S.active.id), L = Board.layout;
  const sel = Math.min(ui.draw.sel, rows.length - 1), r = rows[sel];
  const left = Board.cx(u.pos[0] + u.fp - 1) + L.cell + 10, flip = left + 380 > 1384;
  box.style.left = `${flip ? Board.cx(u.pos[0]) - 390 : left}px`;
  box.style.top = `${Math.min(Math.max(Board.cy(u.pos[1]) - 30, 4), 780 - 120 - rows.length * 44)}px`;
  const hand = h => tr(h === "weapon" ? "battle.hand_weapon" : "battle.hand_off");
  const empty = `<i>${tr("battle.hand_empty")}</i>`;
  box.innerHTML = `<h3>${tr("battle.draw_which")}</h3>` + rows.map((x, i) =>
    `<div class="lrow dr ${x.ok ? "pick" : "off"} ${i === sel ? "sel" : ""}" data-i="${i}">${ico(x.glyph)}<b>${esc(x.name)}${x.qty > 1 ? `<small> ×${x.qty}</small>` : ""}</b><em>${esc(x.why)}</em></div>`).join("")
    + `<div class="after"><div class="k">${tr("battle.draw_after")}</div>` + r.after.map(a =>
      `<div class="hl"><span>${hand(a.hand)}</span><div><s>${a.was ? esc(a.was) : empty}</s> → <b>${a.now ? esc(a.now) : empty}</b></div></div>`).join("")
    + (r.then ? `<div class="then">${esc(r.then)}</div>` : "") + `</div>`;
  box.hidden = false;
}

function takeDraw(i) {
  const r = S.draws[i];
  if (!r || !r.ok) return;
  ui.draw = null;
  return act({action: "draw", item: r.id});
}
$("draw").addEventListener("click", e => {
  const row = e.target.closest(".lrow.pick");
  if (row) takeDraw(Number(row.dataset.i));
});
$("draw").addEventListener("mouseover", e => {
  const row = e.target.closest(".lrow.dr");
  if (!row || !ui.draw || ui.draw.sel === Number(row.dataset.i)) return;
  ui.draw.sel = Number(row.dataset.i); renderDraw();
});

function takeLoot(i) {
  const r = ui.loot && ui.loot.mode === "pick" && S.pickups[i];
  if (!r) return;
  closeLoot();
  return act({action: "pick_up", item: r.id});
}
$("loot").addEventListener("click", e => {
  const row = e.target.closest(".lrow.pick");
  if (row) takeLoot(Number(row.dataset.i));
});
$("loot").addEventListener("mouseover", e => {
  const row = e.target.closest(".lrow.pick");
  if (!row || !ui.loot) return;
  ui.loot.sel = Number(row.dataset.i); renderLoot();
});
$("overlay").addEventListener("mousemove", e => {
  if (!S || (drag && drag.moved)) return;
  const z = zoneAt(e), lootHover = !ui.loot || ui.loot.mode === "hover", ledgerHover = !ui.ledger || ui.ledger.mode === "hover";
  if (lootHover) {
    const kind = z && z.kind !== "cond" ? z.kind : null;
    if (kind && (!ui.loot || ui.loot.kind !== kind || ui.loot.cell[0] !== z.cell[0] || ui.loot.cell[1] !== z.cell[1])) openLoot(z.cell, "hover", kind);
    else if (!kind && ui.loot) closeLoot();
  }
  if (ledgerHover) {
    if (z && z.kind === "cond") { if (!ui.ledger || ui.ledger.id !== z.key) openLedger(z.key); }
    else if (ui.ledger) closeLedger();
  }
});

// a token's conditions as a slip: what each one is and what it does, opened from its gems
function openLedger(id, mode = "hover") { ui.ledger = {id, mode}; renderLedger(); }
function closeLedger() { ui.ledger = null; renderLedger(); }
const markRule = m => m.id === "sleeping" && m.args.turns ? tr("cond.sleeping.rule_turns", m.args) : tr(`cond.${m.id}.rule`, m.args);

function renderLedger() {
  const box = $("ledger"), u = ui.ledger && S.units.find(t => t.id === ui.ledger.id);
  if (!u || !u.marks.length) { ui.ledger = null; box.hidden = true; box.innerHTML = ""; return; }
  const L = Board.layout, left = Board.cx(u.pos[0]) + L.cell * u.fp + 14, flip = left + 300 > 1384;
  box.style.left = `${flip ? Board.cx(u.pos[0]) - 310 : left}px`;
  box.innerHTML = `<h3>${esc(u.name)}</h3>` + u.marks.map(m =>
    `<div class="crow c-${m.cls}"><div class="cic">${ico(m.icon)}</div><div><b>${esc(tr(`cond.${m.id}.name`))}</b><span>${esc(markRule(m))}</span></div></div>`).join("");
  box.hidden = false;
  box.style.top = `${Math.min(Math.max(Board.cy(u.pos[1]) - 20, 4), 780 - 8 - box.offsetHeight)}px`;
}

$("overlay").addEventListener("click", async e => {
  if (ui.dragged) { ui.dragged = false; return; }
  if (!S || ui.busy || S.winner) return;
  if (ui.pile) { closePile(); return; }
  const cell = Board.cellAt(...sheetPoint(e)), z = zoneAt(e);
  const sameCell = c => z && z.cell && c && z.cell[0] === c[0] && z.cell[1] === c[1];
  if (ui.loot) {
    const pinned = ui.loot.mode === "pin" && z && z.kind === ui.loot.kind && sameCell(ui.loot.cell);
    const picking = ui.loot.mode === "pick";
    closeLoot();
    if (picking || pinned) return;
  }
  if (ui.ledger) {
    const pinned = ui.ledger.mode === "pin" && z && z.kind === "cond" && z.key === ui.ledger.id;
    closeLedger();
    if (pinned) return;
  }
  if (z) {
    if (z.kind === "cond") return openLedger(z.key, "pin");
    if (z.kind === "items") return openLoot(z.cell, "pin");
    if (!S.setup) return openPile(z.cell);
  }
  if (!cell) return;
  const pile = unitsAt(cell), u = pile[0] || null;
  const marked = cells => cells.some(([x, y]) => x === cell[0] && y === cell[1]);
  if (S.setup) {
    if (marked(S.setup.cells)) return act({action: S.setup.kind === "flag" ? "plant_flag" : "plant_trap", cell});
    return;
  }
  if (ui.aim) {
    const legal = pile.filter(t => ui.aim.targets.includes(t.id));
    if (legal.length > 1) return openPile(cell);
    if (legal.length) return act({action: ui.aim.id, target: legal[0].id});
    if (ui.aim.cellTarget && marked(ui.aim.cells)) {
      const heights = ui.aim.heights && ui.aim.heights[cell.join(",")];
      if (!heights) return act({action: ui.aim.id, cell});
      const z = await pick(tr("battle.how_high", {name: ui.aim.name}), heights);
      return z == null ? undefined : act({action: ui.aim.id, cell, elevation: z});
    }
    ui.aim = null; renderAll(); return;
  }
  if (u && u.side === "foe" && !u.downed) {
    if (S.my_turn && ui.armed === u.id && u.attackable) return act({action: "attack", target: u.id});
    ui.armed = S.my_turn && u.attackable ? u.id : null;
    return inspect(u.id);
  }
  if (u && u.side === "ally" && (!u.active || S.under.some(l => l.pos[0] === u.pos[0] && l.pos[1] === u.pos[1]))) return inspect(u.id);
  if (S.my_turn && S.reach.some(([x, y]) => x === cell[0] && y === cell[1])) return act({action: "move", cell});
});

$("overlay").addEventListener("mousemove", async e => {
  if (!S || !S.my_turn || ui.aim || (drag && drag.moved)) return;
  const cell = Board.cellAt(...sheetPoint(e));
  const key = cell ? cell.join(",") : null;
  if (key === ui.hover) return;
  ui.hover = key;
  const reachable = cell && S.reach.some(([x, y]) => x === cell[0] && y === cell[1]);
  ui.route = reachable ? await api(`/api/battle/route?x=${cell[0]}&y=${cell[1]}`) : null;
  if (ui.hover === key) Board.overlay(S, ui);
});

// the camera: the wheel zooms round the cursor, a drag with any button pans
Board.onView = () => { if (S) { renderTokens(); Board.overlay(S, ui); } };
let drag = null;
$("sheet").addEventListener("wheel", e => {
  e.preventDefault();
  Board.zoomAt(...sheetPoint(e), e.deltaY < 0 ? 1.15 : 1 / 1.15);
}, {passive: false});
$("sheet").addEventListener("contextmenu", e => e.preventDefault());
$("overlay").addEventListener("pointerdown", e => {
  drag = {x: e.clientX, y: e.clientY, moved: false, button: e.button};
  $("overlay").setPointerCapture(e.pointerId);
});
$("overlay").addEventListener("pointermove", e => {
  if (!drag) return;
  const k = 1384 / $("sheet").getBoundingClientRect().width;
  const dx = (e.clientX - drag.x) * k, dy = (e.clientY - drag.y) * k;
  if (!drag.moved && Math.hypot(dx, dy) < 6) return;
  drag.moved = true; drag.x = e.clientX; drag.y = e.clientY;
  Board.panBy(dx, dy);
});
$("overlay").addEventListener("pointerup", () => {
  if (drag && drag.moved && drag.button === 0) ui.dragged = true;
  drag = null;
});

for (const box of ["plates", "fixed", "spellbook"])
  $(box).addEventListener("click", e => { const p = e.target.closest("[data-action]"); if (p && !p.classList.contains("off")) selectAction(p.dataset.action); });
$("plates").addEventListener("scroll", nudges);
$("plates").addEventListener("wheel", e => { e.preventDefault(); $("plates").scrollLeft += e.deltaY || e.deltaX; }, {passive: false});
$("nudgeL").addEventListener("click", () => { $("plates").scrollLeft -= 400; });
$("nudgeR").addEventListener("click", () => { $("plates").scrollLeft += 400; });
$("tabs").addEventListener("click", e => {
  const t = e.target.closest("span");
  if (t) { ui.tab = t.dataset.tab; ui.aim = null; ui.spellbook = false; $("plates").scrollLeft = 0; renderAll(); }
});
$("seal").addEventListener("click", () => S && S.my_turn && act({action: "end"}));
$("withdraw").addEventListener("click", () => act({action: "withdraw"}));
$("skiptraps").addEventListener("click", () => act({action: "skip_traps"}));
$("dialog").addEventListener("click", e => {
  if (ui.picking || !S) return;
  const t = e.target.closest("[data-seat],[data-goon],[data-speaker],[data-verb]");
  if (!t) return;
  if (t.dataset.seat !== undefined) return act({}, "/api/battle/seat");
  if (t.dataset.goon !== undefined) return act({go_on: true}, "/api/battle/talk");
  if (t.dataset.speaker !== undefined) return act({speaker: Number(t.dataset.speaker)}, "/api/battle/talk");
  if (!t.classList.contains("off")) return act({verb: t.dataset.verb}, "/api/battle/talk");
});
$("newfight").hidden = !Shell.lab;
$("newfight").addEventListener("click", () => S && showEnd(true));

document.addEventListener("keydown", e => {
  if (!S || !$("modal").hidden || !$("dialog").hidden) return;
  if (ui.draw) {
    const n = S.draws.length, step = d => { let i = ui.draw.sel; do i = (i + d + n) % n; while (!S.draws[i].ok && i !== ui.draw.sel); ui.draw.sel = i; renderDraw(); };
    if (e.key === "Escape") { ui.draw = null; return renderDraw(); }
    if (e.key === "Tab" || e.key === "ArrowDown") { e.preventDefault(); return step(1); }
    if (e.key === "ArrowUp") { e.preventDefault(); return step(-1); }
    if (e.key === "Enter") return takeDraw(ui.draw.sel);
    if (/^[1-9]$/.test(e.key) && Number(e.key) <= n) return takeDraw(Number(e.key) - 1);
    return;
  }
  if (ui.loot && ui.loot.mode === "pick") {
    const n = S.pickups.length;
    if (e.key === "Escape") return closeLoot();
    if (e.key === "Tab" || e.key === "ArrowDown") { e.preventDefault(); ui.loot.sel = (ui.loot.sel + 1) % n; return renderLoot(); }
    if (e.key === "ArrowUp") { e.preventDefault(); ui.loot.sel = (ui.loot.sel + n - 1) % n; return renderLoot(); }
    if (e.key === "Enter") return takeLoot(ui.loot.sel);
    if (/^[1-9]$/.test(e.key) && Number(e.key) <= n) return takeLoot(Number(e.key) - 1);
    return;
  }
  if (ui.pile) {
    const n = ui.pile.rows.length;
    if (e.key === "Escape") return closePile();
    if (e.key === "Tab" || e.key === "ArrowDown") { e.preventDefault(); ui.pile.sel = (ui.pile.sel + 1) % n; return renderPile(); }
    if (e.key === "ArrowUp") { e.preventDefault(); ui.pile.sel = (ui.pile.sel + n - 1) % n; return renderPile(); }
    if (e.key === "Enter") return takePile(ui.pile.sel);
    if (/^[1-9]$/.test(e.key) && Number(e.key) <= n) return takePile(Number(e.key) - 1);
    return;
  }
  if (e.key === "Escape") { ui.aim = null; ui.armed = null; ui.ledger = null; ui.spellbook = false; renderAll(); return; }
  const pan = {ArrowLeft: [160, 0], ArrowRight: [-160, 0], ArrowUp: [0, 160], ArrowDown: [0, -160]}[e.key];
  if (pan) { e.preventDefault(); return Board.panBy(...pan); }
  if (e.key === "+" || e.key === "=") return Board.zoomAt(692, 390, 1.25);
  if (e.key === "-") return Board.zoomAt(692, 390, 1 / 1.25);
  if (e.key === "c" || e.key === "C") {
    const u = S.active && S.units.find(t => t.id === S.active.id);
    if (u) Board.centerOn(u.pos, u.fp);
    return;
  }
  if (!S.my_turn) return;
  if (e.key === " ") { e.preventDefault(); return act({action: "defend_end"}); }
  if (e.key === "Tab") { e.preventDefault(); ui.tab = ui.tab === "combat" ? "utility" : "combat"; ui.aim = null; ui.spellbook = false; $("plates").scrollLeft = 0; renderAll(); return; }
  if (e.key === "Enter" && ui.armed) return act({action: "attack", target: ui.armed});
  if (/^[0-9]$/.test(e.key)) {
    const a = (S.actions[ui.tab] || []).find(x => String(x.hotkey) === e.key)
      || [...S.actions.combat, ...S.actions.utility].find(x => String(x.hotkey) === e.key && (x.id === "delay" || x.id === "end"));
    if (a) selectAction(a.id);
  }
});

api("/api/battle/state").then(s => apply(s));

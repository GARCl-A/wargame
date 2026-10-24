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
  long_thrust: "action/expander", dragon_breath: "action/kindle", tail_sweep: "action/slalom",
  zombie_bite: "action/tearing", grab: "action/grab", escape_grapple: "action/dodging",
  throw: "action/throwing-ball", demoralize: "action/screaming", assess: "action/look-at",
  push: "action/push", defend: "body/bell-shield", nonlethal: "action/slap", reload: "gui/clockwise-rotation",
  attack_tongue: "action/swallow", flee: "action/run", delay: "gui/backward-time", end: "gui/halt",
  first_aid: "body/heart-inside", stabilize: "body/heart-organ", capture: "action/arrest",
  drink_potion: "action/drinking", signal_horn: "action/shouting", pick_up: "action/snatch",
  disarm: "action/drop-weapon", investigate: "action/look-at", jump: "action/jump-across",
  climb: "action/mountain-climbing", drop: "action/stairs-goal", swim: "action/drowning",
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
    ui.aim = null; ui.route = null; ui.armed = null; ui.error = null;
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

function unitAt(cell) {
  if (!S || !cell) return null;
  const [x, y] = cell;
  return S.units.find(u => x >= u.pos[0] && x < u.pos[0] + u.fp && y >= u.pos[1] && y < u.pos[1] + u.fp) || null;
}

function arc(d, frac, col) {
  const r = d / 2 + 8, c = 2 * Math.PI * r, span = .36 * c;
  return `<svg class="arc" width="${2 * r}" height="${2 * r}" style="left:${d / 2 - r}px;top:${d / 2 - r}px"><g transform="rotate(${90 - .18 * 360} ${r} ${r})">
    <circle cx="${r}" cy="${r}" r="${r - 1}" fill="none" stroke="rgba(26,18,10,.85)" stroke-width="6" stroke-dasharray="${span} ${c}" stroke-linecap="round"/>
    <circle cx="${r}" cy="${r}" r="${r - 1}" fill="none" stroke="${col}" stroke-width="3" stroke-dasharray="${span * Math.max(0, frac)} ${c}" stroke-linecap="round"/></g></svg>`;
}

function renderTokens() {
  const box = $("tokens"), L = Board.layout, seen = new Set();
  const offered = new Set(ui.aim ? ui.aim.targets : []);
  const offerCol = {attack: "#c9473a", demo: "#9a5cc0", heal: "#6ea65a", move: "#5b8fc0", spell: "#f0d79e", throw: "#e0882c"}[ui.aim && ui.aim.kind] || "#f0d79e";
  for (const u of S.units) {
    seen.add(u.id);
    let el = box.querySelector(`[data-id="${u.id}"]`);
    if (!el) { el = document.createElement("div"); el.dataset.id = u.id; box.appendChild(el); }
    const d = Math.round(L.cell * u.fp * (u.fp > 1 ? .9 : .84) + (u.active ? 4 : 0));
    const x = Board.cx(u.pos[0]) + L.cell * u.fp / 2 - d / 2, y = Board.cy(u.pos[1]) + L.cell * u.fp / 2 - d / 2;
    const cls = ["tok", "seat-" + u.seat];
    if (u.active) cls.push("active");
    if (offered.has(u.id)) cls.push("offered");
    else if (ui.armed === u.id || (ui.inspect === u.id && u.side === "foe")) cls.push("target");
    if (u.downed) cls.push("downed");
    el.className = cls.join(" ");
    el.style.cssText = `left:${x}px;top:${y}px;width:${d}px;height:${d}px;--offer:${offerCol}`;
    const col = u.hp_frac > .5 ? "#7fa557" : "#d0493a";
    const badge = u.dying ? `<div class="badge">${esc(u.dying)}</div>` : u.defending ? `<div class="badge">◈</div>` : "";
    const nameplate = (u.active && S.my_turn) || ui.armed === u.id || ui.inspect === u.id
      ? `<div class="nameplate ${u.side}">${esc(u.name)}</div>` : "";
    const html = face(u.portrait, u.name) + arc(d, u.hp_frac, col) + (u.seat === "player" ? `<div class="pennant"></div>` : "") + badge + nameplate;
    if (el._html !== html) { el.innerHTML = html; el._html = html; }
  }
  for (const el of [...box.children]) if (!seen.has(el.dataset.id)) el.remove();
}

function renderTop() {
  $("place").textContent = S.meta.name || "Battle";
  $("sub").innerHTML = `Level ${esc(S.meta.level)} · squad of ${esc(S.meta.squad)} · seed ${esc(S.meta.seed)}`;
  const coins = S.initiative.map(c => {
    if (!c.id) return `<div class="coin unknown">?</div>`;
    const hp = c.hp_frac == null ? "" : `<div class="hp" style="--c:${c.hp_frac > .5 ? "#7fa557" : "#d0493a"}"><i style="width:${c.hp_frac * 100}%"></i></div>`;
    return `<div class="coin seat-${c.seat}${c.active ? " now" : ""}" title="${esc(c.name)}">${face(c.portrait, c.name)}${hp}</div>`;
  }).join("");
  $("init").innerHTML = `<div class="round"><div><small>Round</small><span>${ROMAN(S.round)}</span></div></div><div class="chain">${coins}</div>`;
}

function renderInspect() {
  const box = $("inspect"), t = S.inspect;
  if (!t) {
    box.innerHTML = `<div class="kicker">Bestiary</div><div class="empty">Click a foe to read what your squad knows of it. Click it again to strike.</div>`;
    return;
  }
  if (t.kind === "ally") {
    box.innerHTML = `<div class="kicker">Your squad</div>
      <div class="foehead"><div class="med" style="--side:${SEAT[t.seat]}">${face(t.portrait, t.name)}</div>
      <div><h2>${esc(t.name)}</h2><div class="race">${esc(t.race)} · ${esc(t.occupation)} · ${esc(t.alignment)}</div>
      <div class="chips">${(t.conditions || []).map(c => `<span class="chip muted">${esc(c)}</span>`).join("")}</div></div></div>
      <div class="known"><div class="tier"><span>Vitals</span><div class="facts"><span>HP <b>${t.hp}/${t.hp_max}</b></span><span>AC <b>${t.ac}</b></span><span>MD <b>${t.md}</b></span><span>Speed <b>${t.speed}</b></span></div></div>
      ${t.weapon ? `<div class="tier"><span>Weapon</span><div class="facts"><span><b>${esc(t.weapon.name)}</b> ${esc(t.weapon.damage || "")}</span>${t.weapon.action ? `<span>${esc(t.weapon.action)}</span>` : ""}</div></div>` : ""}</div>`;
    return;
  }
  const bars = Array.from({length: t.steps_max}, (_, i) => `<i class="${i < t.steps ? "on" : ""}"></i>`).join("");
  const chips = [t.size, ...(t.conditions || [])].filter(Boolean).map(c => `<span class="chip">${esc(c)}</span>`).join("");
  const bands = t.bands.map(b => `<div class="tier"><span>${esc(b.label)}</span><div class="facts">${
    b.rows.map(r => r.value == null ? `<span class="q">${esc(r.label)}</span>` : `<span>${esc(r.label)} <b>${esc(r.value)}</b></span>`).join("")}</div></div>`).join("");
  box.innerHTML = `<div class="kicker">Bestiary · ${ui.armed === t.id ? "target" : "foe"}</div>
    <div class="foehead"><div class="med" style="--side:${SEAT[t.seat] || "var(--blood)"}">${face(t.portrait, t.name)}</div>
    <div><h2>${esc(t.name)}</h2><div class="race">${esc(t.race)} · ${esc(t.alignment)}</div>
    <div class="chips">${chips}</div><div class="health">${bars}</div></div></div>
    <div class="known"><div class="tier"><span>Arms</span><div class="facts"><span><b>${esc(t.weapon.name)}</b></span>${t.weapon.action ? `<span>${esc(t.weapon.action)}</span>` : ""}
    ${t.equipment.map(([k, v]) => `<span>${esc(k)} <b>${esc(v)}</b></span>`).join("")}</div></div>${bands}</div>
    <div class="assess">${esc(t.read)} — Assess to read more.</div>`;
}

function renderLog() {
  const names = new Map(S.units.map(u => [u.name, u.side]));
  const lines = S.log.slice(-26).map(line => {
    const m = /^-+\s*Round\s+(\d+)\s*-+$/i.exec(line.trim());
    if (m) return `<div class="rnd">Round ${ROMAN(+m[1])}</div>`;
    let html = esc(line);
    for (const [n, side] of [...names].sort((a, b) => b[0].length - a[0].length))
      html = html.split(esc(n)).join(`<span class="${side === "ally" ? "a" : "f"}">${esc(n)}</span>`);
    return `<p>${html}</p>`;
  });
  $("log").innerHTML = lines.join("");
}

function renderUnit() {
  const a = S.active, box = $("unit");
  if (!a) { box.innerHTML = `<div class="waiting">The fight goes on out of sight…</div>`; return; }
  const own = a.side === "ally" && a.hp != null;
  const hp = own
    ? (a.hp_max <= 10 ? `<div class="drops">${Array.from({length: a.hp_max}, (_, i) => `<i class="${i < a.hp ? "" : "off"}"></i>`).join("")}</div>`
       : `<div class="hpbar"><i style="width:${a.hp_frac * 100}%"></i></div>`)
    : `<div class="hpbar"><i style="width:${a.hp_frac * 100}%"></i></div>`;
  const w = a.weapon;
  const lvl = a.level == null ? "" : `<div class="lvl" title="Racial level ${a.level} (hit dice) · combat ${a.tracks.combat} · work ${a.tracks.work} · magic ${a.tracks.magic}"><small>LV</small>${a.level}</div>`;
  box.innerHTML = `<div class="med" style="--side:${SEAT[a.seat]}">${face(a.portrait, a.name)}</div>${lvl}
    <div class="body"><h1>${esc(a.name)}</h1><div class="race">${esc(a.race)} · ${esc(a.occupation)} · ${esc(a.alignment)}</div>
    ${S.my_turn ? `<div class="stats"><div class="stat hp"><span>Hit points${own ? ` · ${a.hp}/${a.hp_max}` : ""}</span>${hp}</div>
      <div class="stat"><span>AC</span><b>${a.ac ?? "?"}</b></div><div class="stat"><span>MD</span><b>${a.md ?? "?"}</b></div><div class="stat"><span>Speed</span><b>${a.speed}</b></div></div>
      ${w ? `<div class="weapon"><b>${esc(w.name)}</b>${esc(w.damage || "")}${w.thrown ? ` · thrown ${w.thrown}` : ""}${w.range ? ` · range ${w.range}` : ""}${w.action ? `<em>${esc(w.action)}</em>` : ""}</div>` : `<div class="weapon">Unarmed</div>`}`
      : `<div class="race" style="margin-top:22px;font-size:20px">${S.setup ? "waits for the fight to begin" : a.side === "ally" ? "fights on its own" : "is taking its turn…"}</div>`}</div>
    ${S.my_turn ? `<div class="ap"><span>Action</span><div class="coins">${Array.from({length: a.ap_max}, (_, i) => `<i class="${i < a.ap_max - a.ap ? "spent" : ""}"></i>`).join("")}</div></div>` : ""}`;
}

function plate(a, {id = a.id, name = a.toggle ? a.label : a.name, sel = ui.aim && ui.aim.id === a.id} = {}) {
  const cls = ["plate", a.enabled ? "" : "off", sel ? "sel" : "", a.toggle && /ON/.test(a.label) ? "on" : ""].join(" ");
  return `<div class="${cls}" data-action="${esc(id)}" title="${esc(a.label)}">
    <div class="key">${a.hotkey ?? ""}</div><div class="cost">${"<i></i>".repeat(a.cost)}</div>
    <div class="ico mask" style="--icon:${iconOf(id)}"></div><div class="nm">${esc(name)}</div></div>`;
}

// the row: the spells folded into one plate, then the tab's actions; Delay sits apart, always in reach
function renderPlates() {
  const all = [...S.actions.combat, ...S.actions.utility];
  const spells = ui.tab === "combat" ? S.actions.combat.filter(a => a.id.startsWith("spell:")) : [];
  const list = (S.actions[ui.tab] || []).filter(a => a.id !== "end" && a.id !== "delay" && !a.id.startsWith("spell:"));
  document.querySelectorAll("#tabs span").forEach(t => t.classList.toggle("on", t.dataset.tab === ui.tab));
  const aimingSpell = ui.aim && ui.aim.id.startsWith("spell:");
  const book = spells.length ? plate({label: "Cast a spell", cost: 0, enabled: spells.some(a => a.enabled)},
                                     {id: "spells", name: "Spells", sel: ui.spellbook || aimingSpell}) : "";
  $("plates").innerHTML = book + list.map(a => plate(a)).join("");
  const delay = all.find(a => a.id === "delay");
  $("fixed").innerHTML = delay ? plate(delay) : "";
  const open = ui.spellbook && spells.length && S.my_turn;
  $("spellbook").hidden = !open;
  if (open) $("spellbook").innerHTML = `<div class="kicker">Spells</div>` + spells.map(a =>
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
  else if (S.winner) h = "The fight is over.";
  else if (S.setup && S.setup.kind === "flag") h = "Plant your flag: click a marked cell on your half.";
  else if (S.setup) h = `${S.setup.name} sets a trap: click a marked cell, or Skip traps.`;
  else if (S.talk) h = "A patrol challenges the squad.";
  else if (!S.my_turn) h = "The other side is moving…";
  else if (ui.aim) h = `${ui.aim.name}: ${ui.aim.cellTarget ? "click a marked cell" : "click a marked target"} — Esc to cancel.`;
  else if (S.flags.mopping_up) h = "Enemies down — stabilize the downed, or Space to let the counter run.";
  else if (S.flags.binding) h = "Enemies down — Capture a fallen foe, or Space to let the round run out.";
  else if (S.flags.ctf) h = "Carry their flag home to win, and guard your own.";
  else if (S.flags.can_flee) h = "At the edge of the field: you can Flee.";
  else h = "Click a marked cell to move · a foe twice to strike · Space: defend and end the turn · wheel zooms, drag pans.";
  $("hint").textContent = h;
}

function renderAll() {
  renderTop(); renderTokens(); renderInspect(); renderLog(); renderUnit(); renderPlates(); renderHint();
  Board.overlay(S, ui);
  $("withdraw").hidden = !S.flags.can_withdraw;
  $("skiptraps").hidden = !(S.setup && S.setup.kind === "trap");
  renderDialog();
  if (S.winner) showEnd();
}

// the questions the fight waits on: the next person taking the seat, or a challenge to answer
function renderDialog() {
  const d = $("dialog");
  if (ui.picking) return;
  d.classList.toggle("opaque", !!S.handoff);
  if (S.handoff) {
    d.innerHTML = `<div class="paper ask" style="text-align:center"><div class="kicker">Hand over</div>
      <h2 style="margin-top:16px">${S.handoff === "player" ? "First" : "Second"} player's turn</h2>
      <p class="line">The other player looks away. Take the seat when you are ready.</p>
      <div class="row" style="justify-content:center"><div class="btn" data-seat>I have the seat</div></div></div>`;
  } else if (S.talk) {
    const t = S.talk, lead = t.leader;
    const body = t.result
      ? `<div class="result ${esc(t.result.kind)}">${esc(t.result.text)}</div><div class="row"><div class="btn" data-goon>Go on</div></div>`
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
    <div class="row"><div class="ghost-btn" data-pick="">Cancel</div></div></div>`;
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
    add(c.kind === "crit" ? "Critical!" : "Miss", `float ${c.kind === "crit" ? "crit" : "faint"}`, [x, y - Board.layout.cell * .7], 1300);
  }
  if (ev.cues.some(c => c.kind === "crit")) {
    const b = $("banner");
    b.textContent = "Critical hit";
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
  m.innerHTML = `<div class="paper endcard">${picker ? `<h1 style="font-size:40px">New fight</h1>` : `<h1 class="${won ? "" : "lost"}">${esc(S.result)}</h1>`}
    <p>${picker ? "Pick a fight from the combat lab." : won ? "The field is yours." : S.result === "FLED" ? "You live to fight again." : "Your squad has fallen."}</p>
    ${fights ? `<div class="row"><select id="fightsel">${fights.map(f => `<option value="${f.id}" ${f.id === S.meta.fight ? "selected" : ""}>${esc(f.name)}</option>`).join("")}</select>
    <select id="playersel"><option value="1">One player</option><option value="2" ${S.meta.players === 2 ? "selected" : ""}>Two players</option></select>
    <div class="btn" id="again">Fight</div>${picker ? `<div class="ghost-btn" id="cancel">Cancel</div>` : ""}</div>` : ""}</div>`;
  m.hidden = false;
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
  if (a.aimed || a.target === "cell") {
    if (ui.aim && ui.aim.id === id) { ui.aim = null; renderAll(); return; }
    const aim = await api(`/api/battle/aim?action=${encodeURIComponent(id)}`);
    ui.aim = {...aim, id, name: a.name, cellTarget: a.target === "cell"};
    ui.route = null; renderAll();
    return;
  }
  act({action: id});
}

$("overlay").addEventListener("click", async e => {
  if (ui.dragged) { ui.dragged = false; return; }
  if (!S || ui.busy || S.winner) return;
  const cell = Board.cellAt(...sheetPoint(e));
  if (!cell) return;
  const u = unitAt(cell);
  const marked = cells => cells.some(([x, y]) => x === cell[0] && y === cell[1]);
  if (S.setup) {
    if (marked(S.setup.cells)) return act({action: S.setup.kind === "flag" ? "plant_flag" : "plant_trap", cell});
    return;
  }
  if (ui.aim) {
    if (u && ui.aim.targets.includes(u.id)) return act({action: ui.aim.id, target: u.id});
    if (ui.aim.cellTarget && marked(ui.aim.cells)) {
      const heights = ui.aim.heights && ui.aim.heights[cell.join(",")];
      if (!heights) return act({action: ui.aim.id, cell});
      const z = await pick(`${ui.aim.name}: how high`, heights);
      return z == null ? undefined : act({action: ui.aim.id, cell, elevation: z});
    }
    ui.aim = null; renderAll(); return;
  }
  if (u && u.side === "foe" && !u.downed) {
    if (S.my_turn && ui.armed === u.id && u.attackable) return act({action: "attack", target: u.id});
    ui.armed = S.my_turn && u.attackable ? u.id : null;
    return inspect(u.id);
  }
  if (u && u.side === "ally" && !u.active) return inspect(u.id);
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
  if (e.key === "Escape") { ui.aim = null; ui.armed = null; ui.spellbook = false; renderAll(); return; }
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

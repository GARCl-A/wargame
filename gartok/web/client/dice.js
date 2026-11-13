// The one die of the game: draws a d4..d20 and rolls what the server says was rolled onto a tray. Battle
// and, later, the map and the talk screen feed it the same records; the numbers that go over a
// character (`17 +3 = 20`, the difficulty chip) are the caller's, through `onStop` and `onVerdict`.
"use strict";

const Dice = (() => {
  // the time a roll takes, in ms: the author found 420 / 120 / 280 far too quick to follow, so a full roll
  // is about 1.4 s on a miss and 2 s on a hit, a short one (a foe's) about 0.6 s
  const TUMBLE = 1000, TUMBLE_SHORT = 450;    // the d20 turning before it stops
  const VERDICT = 400, VERDICT_SHORT = 150;   // the stop to the colour
  const DAMAGE = 650;                          // the damage dice turning
  const STAGGER = 140;                         // between two dice thrown in one step
  const FLICKER = 50, SLOWING = 1.14;          // a turning die changes its number, each change a little later
  const REST_SCALE = .5;                       // matches .dstage.rest in dice.css
  const TABLE_HOLD = 1600;                     // a check's dice stay this long once stopped
  const REST = 1400;                           // the dice at rest go to the corner of the field after this
  const STILL = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SHAPES = {
    4: "50,6 94,88 6,88", 6: "10,10 90,10 90,90 10,90", 8: "50,3 93,50 50,97 7,50", 10: "50,3 92,40 50,97 8,40",
    12: "50,4 95,38 78,92 22,92 5,38", 20: "50,3 93,27 93,73 50,97 7,73 7,27",
  };
  const EDGES = "M50 3 50 22M93 27 77 66M7 27 23 66M50 97 23 66M50 97 77 66M7 73 23 66M93 73 77 66M7 27 50 22M93 27 50 22";
  const MAX_DAMAGE_DICE = 8;
  const VS = {get ac() { return tr("battle.dice_ac"); }, get md() { return tr("battle.dice_md"); }, get dc() { return tr("battle.dice_dc"); }, get contest() { return tr("battle.dice_contest"); }};

  const mode = () => (typeof Shell !== "undefined" && Shell.dice) || "full";
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const face = faces => Math.ceil(Math.random() * faces);

  function svg(faces) {
    const inner = faces === 20
      ? `<polygon points="50,22 77,66 23,66" class="in"/><path d="${EDGES}" class="edge"/>` : "";
    return `<svg viewBox="0 0 100 100"><polygon points="${SHAPES[faces] || SHAPES[20]}" class="body"/>${inner}</svg>`;
  }

  function die(faces, value, cls = "") {
    const el = document.createElement("div");
    el.className = `die d${faces} ${cls}`;
    el.innerHTML = `${svg(faces)}<b>${value}</b>`;
    return el;
  }

  // "17 +3 = 20" for the number over whoever acted and under a die with no one to carry it
  const sum = r => `${r.nat} ${sign(r.mod)} = ${r.total}`;

  // the difficulty: a small shield with its number, or the wax seal of a difficulty not read yet
  function chip(r) {
    if (r.dc == null) return "";
    if (r.dc === "?") {
      return `<span class="dchip seal"${tip(tr("battle.dice_unread"))}><i class="mask" style="--icon:url(/assets/icons/gui/uncertainty.svg)"></i></span>`;
    }
    return `<span class="dchip"><i>${esc(VS[r.vs])}</i>${esc(r.dc)}</span>`;
  }

  const verdict = r => r.vs === "free" ? "plain" : r.outcome;

  // turns `el`'s number until `ms` is up (or the roll is snapped), then leaves it on `value`
  async function turn(el, faces, value, ms, wait) {
    el.classList.add("rolling");
    el.style.setProperty("--turn", ms + "ms");
    const b = el.querySelector("b");
    let gap = FLICKER, t;
    const flick = () => { b.textContent = face(faces); gap *= SLOWING; t = setTimeout(flick, gap); };
    flick();
    await wait(ms);
    clearTimeout(t);
    b.textContent = value;
    el.classList.remove("rolling");
  }

  function settle(el, cls) {
    el.classList.add("stopped");
    if (cls) el.classList.add(cls);
  }

  async function damage(tray, d, quick, wait) {
    const row = document.createElement("div");
    row.className = "dmg";
    tray.appendChild(row);
    const each = (d.each || d.rolls.map(x => [x])).flat().slice(0, MAX_DAMAGE_DICE), faces = d.faces || 6;
    const dice = each.map(v => { const el = die(faces, quick ? v : face(faces), "dd"); row.appendChild(el); return el; });
    if (!quick) await Promise.all(dice.map((el, i) => turn(el, faces, each[i], DAMAGE, wait)));
    dice.forEach(el => settle(el));
  }

  async function one(tray, r, o, quick, wait) {
    const cell = document.createElement("div");
    cell.className = "throw";
    const spare = (r.spare || []).map(() => die(20, face(20), "d20 spare"));
    spare.forEach(el => cell.appendChild(el));
    const mine = die(20, face(20), "d20");
    cell.appendChild(mine);
    let theirs = null;
    if (r.theirs) {
      theirs = die(20, face(20), "d20 theirs");
      cell.appendChild(theirs);
    }
    tray.appendChild(cell);
    if (typeof Sound !== "undefined" && mode() !== "off") Sound.play("dice");
    await Promise.all([...spare.map((el, i) => turn(el, 20, r.spare[i], quick ? TUMBLE_SHORT : TUMBLE, wait)),
                       turn(mine, 20, r.nat, quick ? TUMBLE_SHORT : TUMBLE, wait),
                       theirs ? turn(theirs, 20, r.theirs.nat, quick ? TUMBLE_SHORT : TUMBLE, wait) : null]);
    spare.forEach(el => settle(el));
    settle(mine, r.nat === 20 ? "nat20" : r.nat === 1 ? "nat1" : "");
    if (theirs) settle(theirs);
    if (o.onStop) o.onStop(r);
    await wait(quick ? VERDICT_SHORT : VERDICT);
    const v = verdict(r);
    mine.classList.add(v);
    if (theirs) theirs.classList.add(v === "hit" || v === "crit" ? "miss" : "hit");
    cell.insertAdjacentHTML("beforeend", `<div class="cap">${r.label ? `<em>${esc(r.label)}</em>` : ""}${r.actor ? "" : sum(r) + chip(r)}</div>`);
    if (r.vs === "contest") cell.querySelector(".cap").innerHTML = `${r.label ? `<em>${esc(r.label)}</em>` : ""}<span>${r.total}<i> ${esc(tr("battle.dice_contest"))} </i>${r.theirs.total}</span>`;
    if (o.onVerdict) o.onVerdict(r, v);
    if (r.damage && (r.outcome === "hit" || r.outcome === "crit")) await damage(cell, r.damage, quick, wait);
  }

  // Throws `rolls` onto `tray`; resolves when the last one has settled. A click or a key snaps the rest
  // to its result (only the turning is lost). `short` is the quick version, for what the player did not
  // choose; the `Dice` setting can make every roll short ("quick") or stop them all ("off").
  async function roll(tray, rolls, o = {}) {
    if (!rolls.length) return;
    const m = mode(), quick = o.short || m === "quick" || m === "off" || STILL;
    clearTimeout(tray._rest);
    tray.parentElement.style.removeProperty("--held");
    const stage = document.createElement("div");
    stage.className = "dstage";
    tray.replaceChildren(stage);
    let snap = () => {};
    const snapped = new Promise(res => { snap = res; });
    const wait = ms => (m === "off" || STILL) ? Promise.resolve() : Promise.race([sleep(ms), snapped]);
    const arm = () => { addEventListener("pointerdown", snap, true); addEventListener("keydown", snap, true); };
    const disarm = () => { removeEventListener("pointerdown", snap, true); removeEventListener("keydown", snap, true); };
    arm();
    try {
      await Promise.all(rolls.map(async (r, i) => { await wait(i * STAGGER); await one(stage, r, o, quick, wait); }));
    } finally { disarm(); }
    if (o.table) return;
    tray._rest = setTimeout(() => {
      stage.classList.add("rest");
      tray.parentElement.style.setProperty("--held", `${Math.ceil(stage.offsetWidth * REST_SCALE) + 40}px`);
    }, STILL || m === "off" ? 0 : REST);
  }

  // a log line's "d20(12)" and "2d6(3+4)" drawn as the dice themselves, small, with the number on them
  const inline = (n, v) => `<span class="die d${n} sm">${svg(+n)}<b>${v}</b></span>`;
  function inkLine(html) {
    return html.replace(/(\d*)d(\d+)\(([\d+]+)\)/g, (m, n, faces, vals) =>
      vals.split("+").map(v => inline(faces, v)).join(""));
  }

  // the checks a player's order rolled outside a fight: a small tray slides onto whatever screen is open,
  // rolls, and leaves. A click or a key snaps it, as in a fight.
  // the rolls wait in sessionStorage until they have played: an answer that changes screen reloads the page
  // before the tray could finish, and the next page throws them (`resume`)
  const KEEP = "dice.pending";
  const keep = rolls => { try { sessionStorage.setItem(KEEP, JSON.stringify(rolls)); } catch (e) {} };
  const drop = () => { try { sessionStorage.removeItem(KEEP); } catch (e) {} };
  function resume() {
    try {
      const rolls = JSON.parse(sessionStorage.getItem(KEEP) || "null");
      drop();
      if (Array.isArray(rolls)) table(rolls);
    } catch (e) {}
  }

  async function table(rolls) {
    if (!rolls.length) return;
    if (mode() === "off") { drop(); return; }
    keep(rolls);
    let tray = document.getElementById("dicetable");
    if (!tray) {
      tray = document.createElement("div");
      tray.id = "dicetable";
      tray.className = "tray table";
      document.body.appendChild(tray);
    }
    clearTimeout(tray._gone);
    tray.classList.remove("leave");
    tray.classList.add("in");
    await roll(tray, rolls, {short: rolls.length > 1, table: true});
    drop();
    tray._gone = setTimeout(() => {
      tray.classList.add("leave");
      tray._gone = setTimeout(() => { tray.classList.remove("in", "leave"); tray.replaceChildren(); }, 500);
    }, STILL ? 1200 : TABLE_HOLD);
  }

  const spin = (el, faces, value) => mode() === "full" && !STILL ? turn(el, faces, value, TUMBLE, sleep) : Promise.resolve();

  return {roll, svg, die, sum, chip, mode, inkLine, table, spin, resume};
})();

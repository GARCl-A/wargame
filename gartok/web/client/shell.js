// The shell every screen runs in: the stage scaled to the window, the helpers and sounds the screens
// share, and the router that opens the screen the server says is open.
"use strict";

const $ = id => document.getElementById(id);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

// the game's text in the language of the settings: `ui.*` keys the server serves once (/api/locale), read
// with tr() ("{name}" fields), trn() (a "one"/"other" pair) and, in a screen's HTML, data-t="key"
const Locale = {lang: "en", text: {}, names: {}};
const fill = (text, p) => p ? text.replace(/\{(\w+)\}/g, (m, k) => k in p ? p[k] : m) : text;
const tr = (key, p) => fill(Locale.text[key] ?? key, p);
// the shown name of a catalog thing (`name.<kind>.<id>`): the id itself when no one wrote one
const nm = (kind, id) => Locale.names[`${kind}.${id}`] ?? Locale.names[`${kind}.${id}.name`] ?? id;
// a label the server writes in English as an id ("Purse", "rations"): `ui.lab.<lowercase>`, itself when none
const lab = s => {
  const t = Locale.text[`lab.${String(s).toLowerCase()}`];
  if (t === undefined || Locale.lang === "en") return s;
  return s.length > 1 && s === s.toUpperCase() ? t.toUpperCase() : /^[a-z]/.test(s) ? t[0].toLowerCase() + t.slice(1) : t;
};
const trn = (key, n, p = {}) => tr(`${key}.${n === 1 ? "one" : "other"}`, {n, ...p});
function translate(root) {
  for (const el of root.querySelectorAll("[data-t]")) el.textContent = tr(el.dataset.t);
  for (const el of root.querySelectorAll("[data-t-tip]")) el.dataset.tip = tr(el.dataset.tTip);
}

let pending = 0;      // answers on their way: a screen is not ready while one is

async function api(path, body) {
  pending++;
  let res, data;
  try {
    res = await fetch(path, body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    data = await res.json();
    if (res.ok) await preload(data);
  } finally { pending--; }
  Tutorial.sync(res.headers.get("X-Tutorial"));
  if (!res.ok) {
    Sound.play("miss");
    throw new Error(data.error || res.statusText);
  }
  return data;
}

// the cues `sound.py` plays in pygame; silent until the browser allows audio. Every screen's click is played
// here, before any screen's own listener can stop it: on whatever the styles mark clickable (a pointer or a
// zoom-in cursor, which `.off` turns back to default) and on a drag let go over a marked drop target;
// data-silent keeps an element quiet. A screen plays only the cue its answer picks (coins, level up)
const Sound = (() => {
  let bank = null, level = {}, volume = 0, ctx = null;
  const AC = window.AudioContext || window.webkitAudioContext;
  // decoded buffers start in a fraction of a millisecond; an <audio> element reloads its file at every play
  const unlock = () => { if (ctx && ctx.state === "suspended") ctx.resume().catch(() => {}); };
  api("/api/sounds").then(async r => {
    level = r.level;
    ctx = new AC({latencyHint: "interactive"});
    const decoded = {};
    await Promise.all(Object.entries(r.cues).map(async ([cue, urls]) => {
      decoded[cue] = (await Promise.all(urls.map(u =>
        fetch(u).then(x => x.arrayBuffer()).then(b => ctx.decodeAudioData(b)).catch(() => null)))).filter(Boolean);
    }));
    bank = decoded;
  }).catch(() => {});
  function play(cue) {
    const list = bank && bank[cue];
    if (!list || !list.length || volume <= 0) return;
    unlock();
    const src = ctx.createBufferSource(), gain = ctx.createGain();
    src.buffer = list[Math.floor(Math.random() * list.length)];
    gain.gain.value = Math.min(1, volume * (level[cue] ?? 1));
    src.connect(gain).connect(ctx.destination);
    src.start();
  }
  addEventListener("pointerdown", unlock, true);
  addEventListener("keydown", unlock, true);
  const CLICKABLE = new Set(["pointer", "zoom-in"]);
  addEventListener("click", e => {
    const el = e.composedPath()[0];
    if (!(el instanceof Element) || el.closest("[data-silent]")) return;
    if (el.closest("button:not(.off)") || CLICKABLE.has(getComputedStyle(el).cursor)) play("click");
  }, true);
  let down = null;
  addEventListener("pointerdown", e => { down = e.button === 0 ? [e.clientX, e.clientY] : null; }, true);
  addEventListener("pointerup", e => {
    const moved = down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) >= 6;
    down = null;
    if (moved && $("screen").querySelector(".drop, .target")) play("click");
  }, true);
  return {
    set volume(v) { volume = v / 100; },
    play,
  };
})();

// the open screen's tutorial card, named in every answer's X-Tutorial header ("key|1" while it is up):
// a veiled card that swallows every click and key until it is closed, then a ? that opens it again: at the
// end of the screen's header when it has one (#top), else in the window's corner
const Tutorial = (() => {
  let key = null, up = false, shown = null;
  // what the card's copy cannot hold: a stamp (or a picture), its rule and what it is for
  const rows = list => !list?.length ? "" : `<div class="tut-rows">${list.map(r => `<div class="trow">
    ${r.image ? `<img src="${esc(r.image)}" draggable="false">` : ""}<span class="tstamp ${esc(r.stamp?.style)}">${esc(r.stamp?.label)}</span>
    <div><b>${esc(r.rule)}</b><span>${esc(r.text)}</span></div></div>`).join("")}</div>`;
  const card = c => `<div id="tut-card" class="paper"><div class="kicker">${tr("tutorial.notes")}</div>
    <h2>${esc(c.title)}</h2>${c.body.map(p => `<p>${esc(p)}</p>`).join("")}${rows(c.rows)}
    ${c.suggestion ? `<p class="next">${esc(c.suggestion)}</p>` : ""}<div class="btn">${esc(c.button)}</div></div>`;
  const node = id => document.getElementById(id) || $("stage").appendChild(Object.assign(document.createElement("div"), {id}));
  const drop = id => document.getElementById(id)?.remove();
  function show(c) {
    if (c.key !== key || !up) return;
    drop("tut-badge");
    const veil = node("tut-veil");
    veil.innerHTML = card(c);
    veil.onclick = close;
  }
  async function close() {
    if (!up) return;
    up = false;
    drop("tut-veil");
    shown = null;
    const r = await api("/api/tutorial/dismiss", {});
    if (r.screen && r.screen !== Shell.screen) location.reload();
  }
  function place() {
    const b = document.getElementById("tut-badge"), top = $("screen").querySelector("#top");
    if (b && top && b.parentNode !== top) top.appendChild(b);
  }
  function badge() {
    const b = node("tut-badge");
    b.textContent = "?";
    b.dataset.tip = tr("tutorial.badge");
    b.onclick = () => api("/api/tutorial/reopen", {}).catch(() => {});
    place();
  }
  addEventListener("keydown", e => {
    if (!up) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (["Enter", " ", "Escape"].includes(e.key)) close();
  }, true);
  return {
    place,
    sync(header) {
      const [k, flag] = (header || "").split("|");
      key = k || null;
      up = key !== null && flag === "1";
      if (!key) { drop("tut-veil"); drop("tut-badge"); shown = null; return; }
      if (!up) { drop("tut-veil"); shown = null; badge(); return; }
      if (shown !== key) { shown = key; fetch("/api/tutorial").then(r => r.json()).then(c => Shell.ready.then(() => show(c))).catch(() => {}); }
    },
  };
})();

// a portrait, or the name's initial when there is none
function face(src, name, cls = "") {
  return src ? `<img src="${src}" class="${cls}" draggable="false">` : `<div class="initial ${cls}">${esc((name || "?")[0])}</div>`;
}

// a member's (or an animal's) sheet as an open book: its two pages, and the modal any screen opens on a
// portrait marked data-sheet="<uid>" (the screen's `sheet` verb answers who it shows)
const Sheet = (() => {
  const hpcls = (h, m) => h / m < .34 ? "low" : h / m < .67 ? "mid" : "";
  const nameSize = n => { const w = Math.max(...n.split(" ").map(p => p.length)); return w > 15 ? "xlong" : w > 11 ? "long" : ""; };
  function memberPages(u) {
    const lowAll = u.attrs.some(a => a.low);
    const where = u.band ? tr("sheet.rides", {band: `<b>${esc(u.band)}</b>`, where: esc(u.where), task: esc(u.task)}) : esc(u.where);
    const L = `<div class="who"><div class="plate">${face(u.portrait, u.name)}</div><div>
        <h1 class="${nameSize(u.name)}"${tip(u.name)}>${esc(u.name)}</h1>
        <div class="race"><b>${esc(u.race)}</b><br>${tr("sheet.age_align", {age: u.age, align: esc(u.align)})}</div>
        <div class="pos">${where}</div>
        <div class="stamps">${u.stamps.map(s => `<span class="stamp ${s.tone}">${esc(s.text)}</span>`).join("")}</div>
      </div></div>
      <div class="sec2"><div class="kicker">${tr("sheet.attributes")}${lowAll ? `<em>${tr("sheet.hungry")}</em>` : ""}</div>
      <div class="boxes attrs">${u.attrs.map(a => `<div class="box ${a.low ? "low" : ""}"><div class="k">${a.k}</div><div class="v">${a.v}</div><div class="m">${sign(a.mod)}</div></div>`).join("")}</div></div>
      <div class="sec2"><div class="kicker">${tr("sheet.in_fight")}${u.status.length ? `<em>${esc(u.status.join(", "))}</em>` : ""}</div>
      <div class="boxes vitals">
        <div class="box"${tip(u.hp_tip, "sum")}><div class="k">${tr("sheet.hp")}</div><div class="hp"><span class="v">${u.hp[0]}</span><small>/ ${u.hp[1]}</small></div><div class="hpline"><i class="${hpcls(...u.hp)}" style="width:${u.hp[0] / u.hp[1] * 100}%"></i></div></div>
        ${u.stats.map(s => `<div class="box"${tip(s.tip, "sum")}><div class="k">${lab(s.k)}</div><div class="v">${esc(String(s.v).replace("-", "−"))}</div></div>`).join("")}
      </div>
      <div class="weapon">${ico(u.weapon.glyph)}<div><h3>${esc(nm("item", u.weapon.name))}</h3><div class="tags">${esc(u.weapon.tags.replace(/ {2}· {2}/g, " · "))} · ${esc(u.weapon.crit)}</div></div></div>
      <div class="chips">${u.weapon.chips.map(c => `<div class="chip"${tip(c.tip)}><span>${lab(c.k)}</span><b>${esc(c.v)}</b></div>`).join("")}${u.weapon.action ? `<div class="chip act"${tip(u.weapon.action_tip, "item")}><span>${tr("sheet.action")}</span><b>${esc(u.weapon.action)}</b></div>` : ""}</div></div>
      <div class="sec2"><div class="kicker">${tr("sheet.kit")}</div><div class="kit">
        ${u.kit.map(r => `<div class="r"><span>${lab(r.k)}</span><b>${r.k === "Purse" ? `<i class="coindot"></i> ` : ""}${esc(r.v)}</b><em class="${r.bad ? "bad" : ""}">${esc(r.note)}</em></div>`).join("")}
      </div></div>
      <div class="sec2"><div class="kicker">${tr("sheet.of_race", {race: esc(u.race)})}</div>
        <div class="ab"><b>${esc(u.ability[0])}</b>: <i>${esc(u.ability[1])}</i></div>
        <div class="ab"><b>${tr("sheet.speaks")}</b>: <i>${esc(u.langs.join(", "))}</i></div></div>`;
    const R = `<div class="kicker">${tr("sheet.career")}<em>${tr("sheet.racial_level", {n: u.racial})}</em></div>
      ${u.tracks.map(t => {
        const [lv, ...rest] = t.value.split("  ");
        return `<div class="track"${tip(t.tip)}><div class="h"><b>${esc(t.label)}</b><span>${esc(lv.replace("LVL", "Lv"))}<small>${esc(rest.join(" ").replace(/[()]/g, ""))}</small></span></div>
          <div class="bar2"><i style="width:${Math.max(2, t.frac * 100)}%"></i></div><p>${esc(t.text)}</p></div>`;
      }).join("")}
      <div class="sec2"><div class="kicker">${tr("sheet.talents")}<em>${tr("sheet.talents_taken", {n: u.talents.length})}</em></div>
      ${u.talents.length ? `<div class="tal">${u.talents.map(t => `<div><span><b>${esc(t.name)}</b><br><em>${esc(t.desc)}</em></span></div>`).join("")}</div>`
        : `<div class="none">${tr("sheet.no_talents")}</div>`}</div>
      ${u.record.length ? `<div class="sec2"><div class="kicker">${tr("sheet.record")}</div><div class="rec">${u.record.map(p => `<p>${esc(p)}</p>`).join("")}</div></div>` : ""}`;
    return [L, R];
  }

  function animalPages(a) {
    const L = `<div class="who"><div class="plate">${face(a.portrait, a.name)}</div><div>
        <h1 class="${nameSize(a.name)}"${tip(a.name)}>${esc(a.name)}</h1><div class="race"><b>${esc(a.sub)}</b></div>
        <div class="pos">${a.band ? tr("sheet.kept_by", {band: `<b>${esc(a.band)}</b>`, where: esc(a.where)}) : esc(a.where)}</div></div></div>
      <div class="sec2"><div class="kicker">${tr("sheet.attributes")}</div>
      <div class="boxes attrs">${a.attrs.map(x => `<div class="box"><div class="k">${x.k}</div><div class="v">${x.v}</div><div class="m">${sign(x.mod)}</div></div>`).join("")}</div></div>
      <div class="sec2"><div class="kicker">${tr("sheet.body")}</div><div class="boxes vitals">
        <div class="box"><div class="k">${tr("sheet.hp")}</div><div class="hp"><span class="v">${a.hp[0]}</span><small>/ ${a.hp[1]}</small></div><div class="hpline"><i class="${hpcls(...a.hp)}" style="width:${a.hp[0] / a.hp[1] * 100}%"></i></div></div>
        <div class="box"><div class="k">${tr("sheet.spd")}</div><div class="v">${esc(a.speed)}</div></div></div></div>
      ${a.ability ? `<div class="sec2"><div class="kicker">${tr("sheet.nature")}</div><div class="ab"><b>${esc(a.ability[0])}</b>: <i>${esc(a.ability[1])}</i></div></div>` : ""}`;
    const R = `<div class="kicker">${tr("sheet.at_work")}</div>${a.work.map(w => `<div class="kit"><div class="r"><span>${esc(w.k)}</span><b style="white-space:normal;font-weight:400;color:${w.tone === "bad" ? "#8e2a1e" : "#24170c"}">${esc(w.v)}</b><em></em></div></div>`).join("")}`;
    return [L, R];
  }

  // the book lies in a shadow root with the shell's styles only: the open screen's own classes never reach it
  function close() { document.getElementById("sheet-veil")?.remove(); }
  async function open(uid) {
    const u = await api(`/api/${Shell.screen}/sheet?uid=${encodeURIComponent(uid)}`);
    const [L, R] = u.beast ? animalPages(u) : memberPages(u);
    close();
    const host = $("stage").appendChild(Object.assign(document.createElement("div"), {id: "sheet-veil"}));
    const root = host.attachShadow({mode: "open"});
    root.innerHTML = `<link rel="stylesheet" href="/client/shell.css"><div class="veil">
      <div class="paper book"><div class="shut" data-tip="${tr("sheet.close")}">✕</div><div class="lpage">${L}</div><div class="rpage">${R}</div></div></div>`;
    root.addEventListener("click", e => {
      if (e.target.classList.contains("veil") || e.target.closest(".shut")) close();
    });
  }
  addEventListener("keydown", e => {
    if (e.key === "Escape" && document.getElementById("sheet-veil")) { e.stopImmediatePropagation(); close(); }
  }, true);
  // a screen's own drag starts on pointerdown and acts on pointerup: a press that starts on a portrait is the
  // sheet's, from the press to the click; a drag from elsewhere still drops onto it
  let pressed = null;
  const hit = e => e.target.closest?.("[data-sheet]");
  for (const type of ["pointerdown", "pointerup", "click"]) addEventListener(type, e => {
    if (e.button !== 0) return;
    const el = hit(e);
    if (type === "pointerdown") pressed = el;
    if (!el || el !== pressed) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (type === "click") { pressed = null; open(el.dataset.sheet).catch(() => {}); }
  }, true);
  return {pages: u => u.beast ? animalPages(u) : memberPages(u), open, close};
})();

// the server stops once the window is closed; a reload onto another screen asks again before it does
addEventListener("pagehide", () => navigator.sendBeacon("/api/bye"));

let reveal;
// ready: the screen's answers are in, its fonts loaded and its pictures decoded, so it fades in whole and
// the tutorial card (which waits for it) never lands on an empty table
const Shell = {screen: null, lab: false, ready: new Promise(r => { reveal = r; })};

// each screen lives in screens/<id>/: screen.html, then these stylesheets and scripts in order
const SCREENS = {
  title: {css: ["title.css"], js: ["../map/sheet.js", "title.js"]},
  draft: {css: ["draft.css"], js: ["draft.js"]},
  battle: {css: ["battle.css"], js: ["board.js", "battle.js"]},
  map: {css: ["map.css"], js: ["sheet.js", "map.js"]},
  hub: {css: ["hub.css"], js: ["shop.js", "labor.js", "medic.js", "jobs.js", "craft.js", "stables.js", "tavern.js", "initiation.js", "vault.js", "claim.js", "ledger.js", "hub.js"]},
  guild: {css: ["guild.css", "routines.css"], js: ["bands.js", "routines.js", "guild.js"]},
  talk: {css: ["talk.css"], js: ["talk.js"]},
  report: {css: ["report.css"], js: ["report.js"]},
  talents: {css: ["talents.css"], js: ["talents.js"]},
  arena: {css: ["arena.css"], js: ["arena.js"]},
  hunt: {css: ["hunt.css"], js: ["hunt.js"]},
  watch: {css: ["watch.css"], js: ["watch.js"]},
  wiki: {css: ["wiki.css"], js: ["wiki.js"]},
  settings: {css: ["settings.css"], js: ["settings.js"]},
  credits: {css: ["credits.css"], js: ["credits.js"]},
};

// the screens are laid out on 1920x1080, centred; a window off 16:9 gets the backdrop's bleed, not black bars
function fit() {
  const s = Math.min(innerWidth / 1920, innerHeight / 1080), st = $("stage");
  const w = innerWidth / s, h = innerHeight / s;
  Object.assign(st.style, {transform: `scale(${s})`, width: w + "px", height: h + "px"});
  st.style.setProperty("--bx", (w - 1920) / 2 + "px");
  st.style.setProperty("--by", (h - 1080) / 2 + "px");
}
addEventListener("resize", fit);
fit();

const attach = (tag, attrs) => new Promise((ok, fail) => {
  const el = Object.assign(document.createElement(tag), attrs);
  el.onload = ok;
  el.onerror = () => fail(new Error(`could not load ${attrs.src || attrs.href}`));
  (tag === "link" ? document.head : document.body).appendChild(el);
});

// the pictures a screen draws that no <img> holds (backgrounds, masks), loaded once each
const warmed = new Set();
function pictures(root) {
  const urls = new Set();
  for (const el of root.querySelectorAll("*")) {
    const cs = getComputedStyle(el);
    for (const v of [cs.backgroundImage, cs.maskImage, cs.webkitMaskImage])
      for (const m of (v || "").matchAll(/url\("?([^")]+)"?\)/g)) if (!m[1].startsWith("data:") && !warmed.has(m[1])) urls.add(m[1]);
  }
  const imgs = [...root.querySelectorAll("img")].filter(i => !i.complete).map(i => i.decode().catch(() => {}));
  urls.forEach(u => warmed.add(u));
  return [...imgs, ...[...urls].map(u => Object.assign(new Image(), {src: u}).decode().catch(() => {}))];
}

// the portraits and icons an answer names, decoded before the screen that draws them swaps in: on a slow machine
// a stage that brings new faces would otherwise paint them empty first (a cap keeps a dead file from holding the answer)
function preload(data, cap = 2500) {
  const urls = new Set();
  (function walk(v) {
    if (typeof v === "string") { if (/^\/assets\/(portraits|icons)\//.test(v) && !warmed.has(v)) urls.add(v); }
    else if (v && typeof v === "object") Object.values(v).forEach(walk);
  })(data);
  urls.forEach(u => warmed.add(u));
  return Promise.race([sleep(cap), Promise.all([...urls].map(u => Object.assign(new Image(), {src: u}).decode().catch(() => {})))]);
}

// waits until a round finds nothing left to wait for; `cap` keeps a screen that never goes quiet (or a
// window the browser holds hidden, which draws no frames) from staying veiled
async function settle(cap = 2500) {
  const frame = () => new Promise(r => requestAnimationFrame(() => r()));
  const quiet = async () => { while (pending > 0) await sleep(16); };
  await Promise.race([sleep(cap), (async () => {
    for (let waited = true; waited;) {
      await quiet();
      await frame();
      const work = pictures($("screen"));
      waited = work.length > 0 || pending > 0;
      await Promise.all([...work, document.fonts.ready]);
    }
  })()]);
}

// a screen's scripts declare their names at the top level, so one opens once per page load:
// moving to another screen reloads the page on it
async function open(id) {
  const spec = SCREENS[id];
  if (!spec) throw new Error(`no screen called ${id}`);
  const dir = `/client/screens/${id}/`;
  document.body.dataset.screen = id;
  // everything the screen needs is asked for at once: a request that waits on another costs a round trip each
  spec.js.forEach(f => document.head.appendChild(Object.assign(document.createElement("link"), {rel: "preload", as: "script", href: dir + f})));
  const [, res] = await Promise.all([
    Promise.all(spec.css.map(f => attach("link", {rel: "stylesheet", href: dir + f}))),
    fetch(dir + "screen.html"),
  ]);
  if (!res.ok) throw new Error(`could not load ${dir}screen.html`);
  $("screen").innerHTML = await res.text();
  translate($("screen"));
  Tutorial.place();
  await document.fonts.ready;
  // async=false: downloaded together, run in the listed order (a script uses the names the one before declares)
  await Promise.all(spec.js.map(f => attach("script", {src: dir + f, async: false})));
  await settle();
}

Promise.all([api("/api/screen"), api("/api/locale")]).then(([info, loc]) => {
  Object.assign(Locale, loc);
  document.documentElement.lang = loc.lang;
  document.querySelector("title").textContent = tr("app.title");
  Object.assign(Shell, {screen: info.screen, lab: info.lab});
  Sound.volume = info.volume ?? 70;
  return open(info.screen);
}).catch(e => { $("screen").innerHTML = `<div id="failed">${esc(e.message)}</div>`; })
  .finally(() => { document.body.classList.add("ready"); reveal(); });

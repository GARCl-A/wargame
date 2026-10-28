// The shell every screen runs in: the stage scaled to the window, the helpers and sounds the screens
// share, and the router that opens the screen the server says is open.
"use strict";

const $ = id => document.getElementById(id);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const data = await res.json();
  Tutorial.sync(res.headers.get("X-Tutorial"));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

// the open screen's tutorial card, named in every answer's X-Tutorial header ("key|1" while it is up):
// a veiled card that swallows every click and key until it is closed, then a ? that opens it again
const Tutorial = (() => {
  let key = null, up = false, shown = null;
  const card = c => `<div id="tut-card" class="paper"><div class="kicker">The guild's notes</div>
    <h2>${esc(c.title)}</h2>${c.body.map(p => `<p>${esc(p)}</p>`).join("")}
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
  function badge() {
    const b = node("tut-badge");
    b.textContent = "?";
    b.title = "How this screen works";
    b.onclick = () => api("/api/tutorial/reopen", {}).catch(() => {});
  }
  addEventListener("keydown", e => {
    if (!up) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (["Enter", " ", "Escape"].includes(e.key)) close();
  }, true);
  return {
    sync(header) {
      const [k, flag] = (header || "").split("|");
      key = k || null;
      up = key !== null && flag === "1";
      if (!key) { drop("tut-veil"); drop("tut-badge"); shown = null; return; }
      if (!up) { drop("tut-veil"); shown = null; badge(); return; }
      if (shown !== key) { shown = key; fetch("/api/tutorial").then(r => r.json()).then(show).catch(() => {}); }
    },
  };
})();

// a portrait, or the name's initial when there is none
function face(src, name, cls = "") {
  return src ? `<img src="${src}" class="${cls}" draggable="false">` : `<div class="initial ${cls}">${esc((name || "?")[0])}</div>`;
}

// the cues `sound.py` plays in pygame; silent until the browser allows audio
const Sound = (() => {
  let bank = null, level = {}, volume = 0;
  api("/api/sounds").then(r => {
    level = r.level;
    bank = Object.fromEntries(Object.entries(r.cues).map(([cue, urls]) => [cue, urls.map(u => new Audio(u))]));
  }).catch(() => {});
  return {
    set volume(v) { volume = v / 100; },
    play(cue) {
      const list = bank && bank[cue];
      if (!list || volume <= 0) return;
      const a = list[Math.floor(Math.random() * list.length)].cloneNode();
      a.volume = Math.min(1, volume * (level[cue] ?? 1));
      a.play().catch(() => {});
    },
  };
})();

// the server stops once the window is closed; a reload onto another screen asks again before it does
addEventListener("pagehide", () => navigator.sendBeacon("/api/bye"));

const Shell = {screen: null, lab: false};

// each screen lives in screens/<id>/: screen.html, then these stylesheets and scripts in order
const SCREENS = {
  title: {css: ["title.css"], js: ["../map/sheet.js", "title.js"]},
  draft: {css: ["draft.css"], js: ["draft.js"]},
  battle: {css: ["battle.css"], js: ["board.js", "battle.js"]},
  map: {css: ["map.css"], js: ["sheet.js", "map.js"]},
  hub: {css: ["hub.css"], js: ["shop.js", "labor.js", "medic.js", "jobs.js", "craft.js", "stables.js", "tavern.js", "initiation.js", "vault.js", "claim.js", "ledger.js", "hub.js"]},
  guild: {css: ["guild.css"], js: ["bands.js", "guild.js"]},
  talk: {css: ["talk.css"], js: ["talk.js"]},
  report: {css: ["report.css"], js: ["report.js"]},
  talents: {css: ["talents.css"], js: ["talents.js"]},
  arena: {css: ["arena.css"], js: ["arena.js"]},
  hunt: {css: ["hunt.css"], js: ["hunt.js"]},
  watch: {css: ["watch.css"], js: ["watch.js"]},
  wiki: {css: ["wiki.css"], js: ["wiki.js"]},
  settings: {css: ["settings.css"], js: ["settings.js"]},
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

// a screen's scripts declare their names at the top level, so one opens once per page load:
// moving to another screen reloads the page on it
async function open(id) {
  const spec = SCREENS[id];
  if (!spec) throw new Error(`no screen called ${id}`);
  const dir = `/client/screens/${id}/`;
  document.body.dataset.screen = id;
  await Promise.all(spec.css.map(f => attach("link", {rel: "stylesheet", href: dir + f})));
  const res = await fetch(dir + "screen.html");
  if (!res.ok) throw new Error(`could not load ${dir}screen.html`);
  $("screen").innerHTML = await res.text();
  await document.fonts.ready;
  for (const f of spec.js) await attach("script", {src: dir + f});
}

api("/api/screen").then(info => {
  Object.assign(Shell, {screen: info.screen, lab: info.lab});
  Sound.volume = info.volume ?? 70;
  return open(info.screen);
}).catch(e => { $("screen").innerHTML = `<div id="failed">${esc(e.message)}</div>`; });

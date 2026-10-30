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
// a veiled card that swallows every click and key until it is closed, then a ? that opens it again: at the
// end of the screen's header when it has one (#top), else in the window's corner
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
  function place() {
    const b = document.getElementById("tut-badge"), top = $("screen").querySelector("#top");
    if (b && top && b.parentNode !== top) top.appendChild(b);
  }
  function badge() {
    const b = node("tut-badge");
    b.textContent = "?";
    b.title = "How this screen works";
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
      if (shown !== key) { shown = key; fetch("/api/tutorial").then(r => r.json()).then(show).catch(() => {}); }
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
  const ico = path => `<span class="ico mask" style="--icon:url(/assets/icons/${path}.svg)"></span>`;
  const sign = n => n >= 0 ? "+" + n : "−" + (-n);
  const hpcls = (h, m) => h / m < .34 ? "low" : h / m < .67 ? "mid" : "";
  const nameSize = n => { const w = Math.max(...n.split(" ").map(p => p.length)); return w > 15 ? "xlong" : w > 11 ? "long" : ""; };
  function memberPages(u) {
    const lowAll = u.attrs.some(a => a.low);
    const where = u.band ? `Rides with <b>${esc(u.band)}</b><br>at the ${esc(u.where)}, ${esc(u.task)}` : esc(u.where);
    const L = `<div class="who"><div class="plate">${face(u.portrait, u.name)}</div><div>
        <h1 class="${nameSize(u.name)}" title="${esc(u.name)}">${esc(u.name)}</h1>
        <div class="race"><b>${esc(u.race)} ${esc(u.occ)}</b><br>${u.age} years · ${esc(u.align)}</div>
        <div class="pos">${where}</div>
        <div class="stamps">${u.stamps.map(s => `<span class="stamp ${s.tone}">${esc(s.text)}</span>`).join("")}</div>
      </div></div>
      <div class="sec2"><div class="kicker">Attributes${lowAll ? "<em>hungry: they count lower</em>" : ""}</div>
      <div class="boxes attrs">${u.attrs.map(a => `<div class="box ${a.low ? "low" : ""}"><div class="k">${a.k}</div><div class="v">${a.v}</div><div class="m">${sign(a.mod)}</div></div>`).join("")}</div></div>
      <div class="sec2"><div class="kicker">In a fight${u.status.length ? `<em>${esc(u.status.join(", "))}</em>` : ""}</div>
      <div class="boxes vitals">
        <div class="box" title="${esc(u.hp_tip)}"><div class="k">HIT POINTS</div><div class="hp"><span class="v">${u.hp[0]}</span><small>/ ${u.hp[1]}</small></div><div class="hpline"><i class="${hpcls(...u.hp)}" style="width:${u.hp[0] / u.hp[1] * 100}%"></i></div></div>
        ${u.stats.map(s => `<div class="box" title="${esc(s.tip)}"><div class="k">${s.k}</div><div class="v">${esc(String(s.v).replace("-", "−"))}</div></div>`).join("")}
      </div>
      <div class="weapon">${ico(u.weapon.glyph)}<div><h3>${esc(u.weapon.name)}</h3><div class="tags">${esc(u.weapon.tags.replace(/ {2}· {2}/g, " · "))} · ${esc(u.weapon.crit)}</div></div></div>
      <div class="chips">${u.weapon.chips.map(c => `<div class="chip" title="${esc(c.tip)}"><span>${c.k}</span><b>${esc(c.v)}</b></div>`).join("")}${u.weapon.action ? `<div class="chip act"><span>ACTION</span><b>${esc(u.weapon.action)}</b></div>` : ""}</div></div>
      <div class="sec2"><div class="kicker">Kit</div><div class="kit">
        ${u.kit.map(r => `<div class="r"><span>${r.k}</span><b>${r.k === "Purse" ? `<i class="coindot"></i> ` : ""}${esc(r.v)}</b><em class="${r.bad ? "bad" : ""}">${esc(r.note)}</em></div>`).join("")}
      </div></div>
      <div class="sec2"><div class="kicker">Of the ${esc(u.race)}</div>
        <div class="ab"><b>${esc(u.ability[0])}</b>: <i>${esc(u.ability[1])}</i></div>
        <div class="ab"><b>Speaks</b>: <i>${esc(u.langs.join(", "))}</i></div></div>`;
    const R = `<div class="kicker">Career<em>racial level ${u.racial}</em></div>
      ${u.tracks.map(t => {
        const [lv, ...rest] = t.value.split("  ");
        return `<div class="track" title="${esc(t.tip)}"><div class="h"><b>${esc(t.label)}</b><span>${esc(lv.replace("LVL", "Lv"))}<small>${esc(rest.join(" ").replace(/[()]/g, ""))}</small></span></div>
          <div class="bar2"><i style="width:${Math.max(2, t.frac * 100)}%"></i></div><p>${esc(t.text)}</p></div>`;
      }).join("")}
      <div class="sec2"><div class="kicker">Talents<em>${u.talents.length} taken</em></div>
      ${u.talents.length ? `<div class="tal">${u.talents.map(t => `<div><span><b>${esc(t.name)}</b><br><em>${esc(t.desc)}</em></span></div>`).join("")}</div>`
        : `<div class="none">None taken yet.</div>`}</div>
      ${u.record.length ? `<div class="sec2"><div class="kicker">Record</div><div class="rec">${u.record.map(p => `<p>${esc(p)}</p>`).join("")}</div></div>` : ""}`;
    return [L, R];
  }

  function animalPages(a) {
    const L = `<div class="who"><div class="plate">${face(a.portrait, a.name)}</div><div>
        <h1 class="${nameSize(a.name)}" title="${esc(a.name)}">${esc(a.name)}</h1><div class="race"><b>${esc(a.sub)}</b></div>
        <div class="pos">${a.band ? `Kept by <b>${esc(a.band)}</b><br>at the ${esc(a.where)}` : esc(a.where)}</div></div></div>
      <div class="sec2"><div class="kicker">Attributes</div>
      <div class="boxes attrs">${a.attrs.map(x => `<div class="box"><div class="k">${x.k}</div><div class="v">${x.v}</div><div class="m">${sign(x.mod)}</div></div>`).join("")}</div></div>
      <div class="sec2"><div class="kicker">Body</div><div class="boxes vitals">
        <div class="box"><div class="k">HIT POINTS</div><div class="hp"><span class="v">${a.hp[0]}</span><small>/ ${a.hp[1]}</small></div><div class="hpline"><i class="${hpcls(...a.hp)}" style="width:${a.hp[0] / a.hp[1] * 100}%"></i></div></div>
        <div class="box"><div class="k">SPD</div><div class="v">${esc(a.speed)}</div></div></div></div>
      ${a.ability ? `<div class="sec2"><div class="kicker">Its nature</div><div class="ab"><b>${esc(a.ability[0])}</b>: <i>${esc(a.ability[1])}</i></div></div>` : ""}`;
    const R = `<div class="kicker">At work</div>${a.work.map(w => `<div class="kit"><div class="r"><span>${esc(w.k)}</span><b style="white-space:normal;font-weight:400;color:${w.tone === "bad" ? "#8e2a1e" : "#24170c"}">${esc(w.v)}</b><em></em></div></div>`).join("")}`;
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
      <div class="paper book"><div class="shut" title="Close">✕</div><div class="lpage">${L}</div><div class="rpage">${R}</div></div></div>`;
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
  Tutorial.place();
  await document.fonts.ready;
  for (const f of spec.js) await attach("script", {src: dir + f});
}

api("/api/screen").then(info => {
  Object.assign(Shell, {screen: info.screen, lab: info.lab});
  Sound.volume = info.volume ?? 70;
  return open(info.screen);
}).catch(e => { $("screen").innerHTML = `<div id="failed">${esc(e.message)}</div>`; });

// The guild's sheet: the frame (banner, tabs, the way back) and three of its tabs. MEMBERS is the roster on
// leather, the picked member's sheet as an open book and what can be done for them; THE GUILD the charter and
// the holdings; REPUTATIONS the objectives and the factions. BANDS draws itself (bands.js). Every verb answers
// the whole sheet.
"use strict";

let G = null;
const ico = (path, cls = "ico") => `<span class="${cls} mask" style="--icon:url(/assets/icons/${path}.svg)"></span>`;
const money = n => "$" + n;
const sign = n => n >= 0 ? "+" + n : "−" + (-n);
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const hpcls = (h, m) => h / m < .34 ? "low" : h / m < .67 ? "mid" : "";
const rgb = c => `rgb(${c.join(",")})`;
const showing = new Set();          // holdings opened to look inside

let toastTimer = null;
function toast(text) {
  if (!text) return;
  const t = $("toast");
  t.textContent = text.charAt(0).toUpperCase() + text.slice(1);
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
}

async function post(verb, body = {}) {
  try {
    const r = await api(`/api/guild/${verb}`, body);
    if (r.screen && r.screen !== "guild") { location.reload(); return null; }
    G = r;
    draw();
    return r;
  } catch (e) {
    toast(e.message);
    return null;
  }
}

function bannerStyle() {
  const c = G.banner;
  return c ? `background:radial-gradient(circle at 38% 32%,${rgb(c.map(v => Math.min(255, v + 40)))},${rgb(c)} 55%,${rgb(c.map(v => v * .55 | 0))})` : "";
}

function drawFrame() {
  $("banner").setAttribute("style", bannerStyle());
  $("banner").innerHTML = G.emblem ? ico(G.emblem) : "";
  $("gname").textContent = G.name;
  $("gsub").innerHTML = `Day <b>${G.day}</b> · <b>${G.won}</b> victories · <b>${G.count}</b> members in <b>${G.band_count}</b> bands`;
  $("tabs").innerHTML = G.tabs.map(t =>
    `<span class="${t.key === G.tab ? "on" : ""}" data-tab="${t.key}">${esc(t.label)}${t.badge ? `<i>${t.badge}</i>` : ""}</span>`).join("");
}

// ---------------------------------------------------------------- MEMBERS
function roster(M) {
  const filters = M.filters.map(f => `<span class="${f.mode === M.filter ? "on" : ""}" data-filter="${f.mode}" title="${esc(f.tip)}">${esc(f.label)}${f.mode === "alerts" && G.alerts ? `<em>${G.alerts}</em>` : ""}</span>`).join("");
  let h = "";
  for (const b of M.roster) {
    h += `<div class="bandh" data-fold="${b.gid}"><span class="caret">${b.folded ? "▸" : "▾"}</span><b>${esc(b.name)}</b><span>${esc(b.where)} · ${esc(b.task.toLowerCase())}</span><small>${b.count}</small></div>`;
    if (b.folded) continue;
    for (const m of b.rows) {
      const med = `<div class="medal ${m.beast ? "beastmed" : ""} ${m.hurt ? "hurt" : ""}">${face(m.portrait, m.name)}</div>`;
      h += `<div class="mem ${m.selected ? "sel" : ""}" data-uid="${m.uid}">${med}<div style="min-width:0"><div class="nm">${esc(m.name)}</div><div class="sb">${esc(m.sub)}</div>
        <div class="hpbar"><i class="${hpcls(...m.hp)}" style="width:${m.hp[0] / m.hp[1] * 100}%"></i></div></div>
        <div class="bdg">${m.badges.map(x => `<span class="mark ${x.tone}">${esc(x.text)}</span>`).join("")}</div></div>`;
    }
  }
  if (!M.roster.length) h = `<div class="empty-note" style="margin:20px 6px">Nobody here.</div>`;
  return `<div class="leather" id="roster"><div class="filters">${filters}</div><div class="rlist">${h}</div>
    <div class="rfoot"><b>${G.count}</b> members · <b>${M.slots[0]}</b> of <b>${M.slots[1]}</b> bands in the field</div></div>`;
}

function memberActs(u) {
  const role = r => `<div class="role" title="${esc(r.tip)}"><div class="t"><b>${esc(r.title)}</b>${r.current ? `<span class="mark good">current</span>` : ""}</div>
      <p>${esc(r.sub)}</p>${r.action ? `<div class="act"><div class="ghost-btn ${r.action.on ? "" : "off"}" data-role="${r.key}">${esc(r.action.label)}</div></div>` : ""}</div>`;
  const tree = `<div class="tree ${u.picks ? "ready" : ""}" id="tree">${ico("action/skills")}<div><b>Talent tree</b><span>${u.picks ? `${plural(u.picks, "pick")} waiting` : "Review the build"}</span></div></div>`;
  const open = u.band ? `<div class="acts-foot"><div class="ghost-btn" data-open="${u.gid}">${ico("item/knapsack")}Open ${esc(u.band)}</div></div>` : "";
  return `<div class="leather" id="acts">${tree}<div class="lbl" style="margin:24px 2px 0">Roles</div>${u.roles.map(role).join("")}${open}</div>`;
}

function animalActs(a) {
  return `<div class="leather" id="acts"><div class="lbl" style="margin:4px 2px 0">An animal of the band</div>
    <div class="empty-note">It has no talents or roles. Its tack, its load and what it pulls are set on the band's table.</div>
    ${a.band ? `<div class="acts-foot"><div class="ghost-btn" data-open="${a.gid}">${ico("item/knapsack")}Open ${esc(a.band)}</div></div>` : ""}</div>`;
}

function drawMembers() {
  const M = G.members, u = M.sheet;
  const pages = u ? Sheet.pages(u) : ["", ""];
  const acts = !u ? "" : u.beast ? animalActs(u) : memberActs(u);
  const keep = $("roster") ? $("roster").querySelector(".rlist").scrollTop : 0;
  $("body").innerHTML = roster(M) + `<div class="paper book" id="sheet"><div class="lpage">${pages[0]}</div><div class="rpage">${pages[1]}</div></div>` + acts;
  $("roster").querySelector(".rlist").scrollTop = keep;
}

// ---------------------------------------------------------------- THE GUILD
const HOLD_ICON = {"City house": "gui/house", "The Claim": "map/claim", "Strongbox": "item/locked-chest"};

function drawCharter() {
  const C = G.guild, v = C.vocation;
  const max = Math.max(7, ...C.standing.map(f => f.rep));
  const voc = v ? `<div class="voc"><div class="row1">${ico("map/signpost")}<b>${esc(v.name)}</b><span class="mark ${v.dormant ? "dorm" : ""}">${v.dormant ? "dormant" : "founding trade"}</span></div><p>${esc(v.perk)}</p></div>` : "";
  const standing = C.standing.length ? C.standing.map(f => `<div class="r"><b>${esc(f.name)}</b><div class="pips">${Array.from({length: max}, (_, i) => `<i class="${i < f.rep ? "" : "off"}"></i>`).join("")}</div><span>${f.rep}</span></div>`).join("")
    : `<div class="none">No faction knows the guild yet.</div>`;
  const rows = C.groups.map(b => {
    const full = b.size >= b.capacity;
    return `<tr data-band="${b.gid}"><td><b>${esc(b.name)}</b>${b.note ? `<small class="bad">${esc(b.note)}</small>` : ""}</td><td>${esc(b.where)}</td><td>${esc(b.task)}</td>
      <td class="${full ? "full" : ""}">${b.size} of ${b.capacity}${b.over ? `<small>over by ${b.over}: no seat for them</small>` : full ? "<small>full: the leader holds no more</small>" : ""}</td></tr>`;
  }).join("");
  const notices = C.notices.length ? C.notices.map(n => `<div class="quiet ${n.tone}">${esc(n.text)}</div>`).join("")
    : `<div class="quiet">All quiet. Nobody has given notice, no band is over its hold, and every herd follows its keepers.</div>`;
  const charter = `<div class="paper" id="charter">
    <div class="chead"><div class="banner" style="${bannerStyle()}">${G.emblem ? ico(G.emblem) : ""}</div>
      <div><h1>${esc(G.name)}</h1><p>A guild of ${G.count}, ${plural(G.day, "day")} on the road · ${plural(G.won, "fight")} won</p></div>${voc}</div>
    <div class="cgrid">
      <div>
        <div class="kicker">Fame</div>
        <div class="fame"><b>${C.fame}</b><span>the sum of every faction's regard;<br>${C.fame_next ? `${C.fame_next} more opens another band` : "every band seat is open"}</span></div>
        <div class="slots">${Array.from({length: C.slots[1]}, (_, i) => `<i class="${i < C.slots[0] ? "on" : ""}"></i>`).join("")}</div>
        <p>${C.slots[0]} of ${C.slots[1]} bands in the field. A band past its leader's hold, with no seat free, starts to lose its weakest.</p>
        <div class="kicker" style="margin-top:30px">Standing</div><div class="stand">${standing}</div>
      </div>
      <div>
        <div class="kicker">The bands</div>
        <table class="btab"><tr><th>BAND</th><th>WHERE</th><th>DOING</th><th>MEMBERS</th></tr>${rows}</table>
        <div class="kicker" style="margin-top:34px">Notices</div>${notices}
      </div>
    </div>
    <div class="cfootnote">Fame never buys anything: it is how many bands the guild can keep on the road at once.</div></div>`;
  const tone = {muted: "", good: "good", warn: "warn", bad: "bad"};
  const holds = C.holdings.map(h => {
    const look = h.inside ? `<div class="loadbar"><i style="width:${h.load[0] / h.load[1] * 100}%"></i></div>
      <div class="act"><div class="ghost-btn" data-look="${esc(h.name)}">${showing.has(h.name) ? "Close it" : "Look inside"}</div></div>
      ${showing.has(h.name) ? `<div class="inside">${h.inside.length ? h.inside.map(it => `<div class="it">${ico(it.glyph)}<div class="n">${esc(it.name)}</div><span class="q">${it.qty > 1 ? "×" + it.qty : ""}</span><span></span></div>`).join("")
        : `<div class="empty-note">Empty.</div>`}<div class="empty-note">Taking things out needs a band at the Bank in the City.</div></div>` : ""}` : "";
    return `<div class="hold ${tone[h.tone]}">${ico(HOLD_ICON[h.name] || "item/locked-chest")}<div>
      <h3>${esc(h.name)}<span class="mark ${tone[h.tone]}">${esc(h.status.toLowerCase())}</span></h3><p>${esc(h.detail)}</p>${look}</div></div>`;
  }).join("");
  $("body").innerHTML = charter + `<div class="leather" id="holds"><div class="lbl" style="margin:4px 2px 0">Holdings</div>${holds}</div>`;
}

// ---------------------------------------------------------------- REPUTATIONS
function drawReputations() {
  const R = G.reputations, o = R.objectives;
  const objs = [...o.rows.filter(d => !d.done), ...o.rows.filter(d => d.done)];
  const page = `<div class="paper" id="objs"><div class="kicker">Objectives</div>
    <div class="objhead"><h2>Guild Objectives</h2><b>${o.done}<small> / ${o.total}</small></b></div>
    <div class="objblurb">${esc(o.blurb)}</div>
    <div class="objs">${objs.map(d => `<div class="ob ${d.done ? "done" : ""}"><span class="box2"></span><div><b>${esc(d.name)}</b><p>${esc(d.blurb)}</p></div></div>`).join("")}</div></div>`;
  const facs = R.factions.map(f => `<div class="paper fac">
      <div class="top2"><div><div class="kicker">Faction</div><h2>${esc(f.name)}</h2></div><div class="rep ${f.rep ? "" : "zero"}">${f.rep}</div></div>
      <div class="bl">${esc(f.blurb)}</div>
      <div style="margin-top:8px">${f.deeds.map(d => `<div class="ob ${d.state}"><span class="box2"></span><div><b>${esc(d.name)}</b><span class="pt">+${d.rep}</span><p>${esc(d.blurb)}</p></div></div>`).join("")}</div>
      ${f.unlocks.map(u => `<div class="unl ${u.open ? "" : "shut"}"><span class="lk">${u.open ? "open" : "at " + u.need}</span><span><b>${esc(u.title)}</b>: <i>${esc(u.text)}</i></span></div>`).join("")}
    </div>`).join("") || `<div class="paper fac"><div class="bl">No faction has heard of the guild yet.</div></div>`;
  $("body").innerHTML = page + `<div id="facs">${facs}</div>`;
}

// ---------------------------------------------------------------- the frame
function draw() {
  drawFrame();
  if (G.tab === "members") drawMembers();
  else if (G.tab === "guild") drawCharter();
  else if (G.tab === "reputations") drawReputations();
  else Bands.draw(G.bands);
  toast(G.notice);
}

async function back() {
  Sound.play("click");
  await api("/api/guild/back", {});
  location.reload();
}

$("tabs").addEventListener("click", e => {
  const t = e.target.closest("[data-tab]");
  if (t && t.dataset.tab !== G.tab) { Sound.play("click"); post("tab", {key: t.dataset.tab}); }
});
$("back").onclick = back;
$("body").addEventListener("click", e => {
  if (!G || G.tab === "bands") return;
  const el = e.target;
  const f = el.closest("[data-filter]");
  if (f) return post("filter", {mode: f.dataset.filter});
  const fold = el.closest("[data-fold]");
  if (fold) return post("fold", {gid: fold.dataset.fold});
  const m = el.closest(".mem[data-uid]");
  if (m) { Sound.play("click"); return post("member", {uid: m.dataset.uid}); }
  const r = el.closest("[data-role]");
  if (r && !r.classList.contains("off")) { Sound.play("click"); return post("role", {key: r.dataset.role}); }
  if (el.closest("#tree")) { Sound.play("click"); return post("talents", {}); }
  const o = el.closest("[data-open]");
  if (o) { Sound.play("click"); return post("band", {gid: o.dataset.open}); }
  const look = el.closest("[data-look]");
  if (look) {
    const k = look.dataset.look;
    showing.has(k) ? showing.delete(k) : showing.add(k);
    return draw();
  }
  const row = el.closest("tr[data-band]");
  if (row && row.dataset.band) { Sound.play("click"); post("band", {gid: row.dataset.band}); }
});
addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  if (e.key === "Tab" && G) {
    e.preventDefault();
    const keys = G.tabs.map(t => t.key), i = keys.indexOf(G.tab);
    post("tab", {key: keys[(i + (e.shiftKey ? -1 : 1) + keys.length) % keys.length]});
    return;
  }
  if (e.key === "Escape" && !(G && G.tab === "bands" && Bands.escape())) back();
});

api("/api/guild/state").then(r => { G = r; draw(); });

// The campaign map: the bands, the places and pawns over the sheet, the picked band's inspector and the
// seal. Every order goes to the server, which runs the clock as the pygame map does and answers with the
// map again, or with another screen to open.
"use strict";

let M = null, sel = null, splitting = null, picks = new Set(), hoverNode = null;
const previews = new Map();
const ico = (path, cls = "ico") => `<span class="${cls} mask" style="--icon:url(/assets/icons/${path}.svg)"></span>`;
const band = gid => M.groups.find(b => b.gid === gid);
const node = id => M.nodes.find(n => n.id === id);
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const title = s => s.toLowerCase().replace(/(^|[\s(·-])(\w)/g, (m, a, b) => a + b.toUpperCase());

// a portrait ringed by its health, with the leader's crown and a hunger mark
function ring(m) {
  const f = m.hp_max ? m.hp / m.hp_max : 0, c = f < .34 ? "#c9473a" : f < .67 ? "#c9a35e" : "#7fa557";
  return `conic-gradient(${c} 0 ${f * 360}deg, rgba(0,0,0,.55) ${f * 360}deg 360deg)`;
}
const medal = m => `<div class="fm${m.hungry ? " hungry" : ""}${m.lead ? " lead" : ""}" style="background:${ring(m)}" title="${esc(m.name)}">${face(m.portrait, m.name)}</div>`;

// ---------------------------------------------------------------- the top bar
function shade(rgb, k) { return `rgb(${rgb.map(v => Math.max(0, Math.min(255, Math.round(v * k)))).join(",")})`; }
function drawTop() {
  const t = M.meta;
  $("guildname").textContent = t.name;
  $("guildsub").textContent = t.subtitle;
  if (t.banner) {
    const s = document.querySelector(".shield .body").style;
    s.setProperty("--banner-hi", shade(t.banner, 1.25)); s.setProperty("--banner", shade(t.banner, 1)); s.setProperty("--banner-lo", shade(t.banner, .55));
  }
  $("emblem").style.setProperty("--icon", `url(/assets/icons/${t.emblem || "body/sword-tie"}.svg)`);
  $("day").textContent = t.day;
  $("time").textContent = t.time;
  $("part").textContent = `${t.part} · ${t.turn}`;
  $("dial").innerHTML = dial(t.hour);
  $("alerts").innerHTML = M.alerts.map(a => `<div class="alert ${a.tone === "warn" ? "warn" : ""}" title="${esc(a.text)}">${ico(a.icon)}
    <div><b>${esc(a.title)}</b><small>${esc(a.text)}</small></div></div>`).join("");
  $("ledger").innerHTML = M.ledger.map(([k, v]) => `<div><b>${esc(v)}</b><span class="lbl">${esc(k)}</span></div>`).join("");
  $("guildlbl").textContent = t.level_ups ? `Guild · ${t.level_ups} level up` : "Guild";
  $("guildbtn").classList.toggle("lit", !!t.level_ups);
}

// the sun (or the moon) on its arc from dawn to dusk
function dial(hour) {
  const day = hour >= 6 && hour < 18, f = day ? (hour - 6) / 12 : ((hour + 6) % 24) / 12;
  const a = Math.PI * (1 - f), x = 43 + Math.cos(a) * 38, y = 42 - Math.sin(a) * 38;
  const arc = `<path d="M5 42 A38 38 0 0 1 81 42" fill="none" stroke="rgba(201,163,94,.35)" stroke-width="1.5" stroke-dasharray="2 4"/>
    <path d="M5 42 A38 38 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}" fill="none" stroke="#c9a35e" stroke-width="2"/>
    <line x1="0" y1="42" x2="86" y2="42" stroke="rgba(201,163,94,.4)" stroke-width="1"/>`;
  const body = day
    ? `<circle cx="${x}" cy="${y}" r="7" fill="#f0d79e" stroke="#7d5c28" stroke-width="1.5"/>`
    : `<circle cx="${x}" cy="${y}" r="7" fill="#cfd6dc" stroke="#55606a" stroke-width="1.5"/><circle cx="${x + 3}" cy="${y - 2}" r="6" fill="#20170f"/>`;
  return arc + body;
}

// ---------------------------------------------------------------- the bands
// the stops ahead along a line, the band's mark part-way along the first leg
function tripBar(t) {
  const total = t.stops[t.stops.length - 1].hours || 1, pct = h => `${(h / total * 100).toFixed(1)}%`;
  const meAt = t.share * t.stops[0].hours / total * 100;
  let html = `<div class="line"></div><div class="done" style="width:${meAt.toFixed(1)}%"></div><i style="left:0"></i>`;
  html += t.stops.map((s, k) => `<i class="${k === t.stops.length - 1 ? "end" : ""}" style="left:${pct(s.hours)}"></i>`).join("");
  html += `<i class="me" style="left:${meAt.toFixed(1)}%"></i><span class="first" style="left:0">${esc(t.from_name)}</span>`;
  const next = t.stops[0];
  if (t.stops.length > 1 || next.hours / total < .7)
    html += `<span class="next" style="left:${Math.min(Math.max(next.hours / total * 100, 30), 70)}%">${esc(next.name)} ${esc(next.at)}</span>`;
  const last = t.stops[t.stops.length - 1];
  html += `<span class="last" style="left:100%">${esc(t.stops.length > 1 ? last.name : last.at)}</span>`;
  return `<div class="trip">${html}</div>`;
}

function doing(b) {
  if (b.blocked) return `<b>${esc(b.chip)}</b> at ${esc(node(b.node).name)}`;
  if (b.idle) return `Waiting at the <b>${esc(node(b.node).name)}</b>`;
  if (b.trip) {
    const last = b.trip.stops[b.trip.stops.length - 1], via = b.trip.stops.slice(0, -1).map(s => s.name);
    return `→ <b>${esc(last.name)}</b>${via.length ? " by " + esc(via.join(", ")) : ""}`;
  }
  return esc(b.detail.charAt(0).toUpperCase() + b.detail.slice(1));
}

function bandCard(b) {
  const isSel = b.gid === sel, cls = ["band", isSel ? "sel" : "", b.blocked ? "bad" : ""].join(" ");
  if (splitting === b.gid) return splitCard(b, cls);
  const foot = `<div class="bfoot"><span class="${b.rations ? "" : "bad"}">${ico("action/eating")}${plural(b.rations, "ration")}</span>
    <span>${ico("gui/wallet")}${esc(b.money)}</span><span class="tail">${b.trip ? `${b.trip.stops[0].hours} h to the next stop` : isSel ? "picked" : ""}</span></div>`;
  let actions = "";
  if (isSel && !b.blocked && (!b.busy || b.chip === "garrison")) {
    const canSplit = b.members.length > 1 && !b.can_split;
    actions = `${b.mates.length ? '<div class="lk sub">Merge <em>a band standing here</em></div>' : ""}
      ${b.mates.map(m => { const o = band(m.gid); return `<div class="mate">${o ? medal(o.members.find(x => x.lead) || o.members[0]) : ""}
        <div><b>${esc(m.name)}</b><small>${o ? plural(o.members.length, "soul") + " · " + esc(o.chip.toLowerCase()) : ""} · here</small></div>
        <div class="brass-btn" data-merge="${m.gid}">Fold in</div></div>`; }).join("")}
      <div class="bactions"><div class="ghost-btn ${canSplit ? "" : "off"}" data-split="${b.gid}" title="${esc(b.can_split || (b.members.length > 1 ? "" : "one soul cannot split"))}">${ico("body/split-body")}Split</div>
      ${b.mates.length ? "" : `<div class="ghost-btn off">${ico("body/three-friends")}Merge · none here</div>`}</div>`;
  }
  return `<div class="${cls}" data-band="${b.gid}">
    <div class="row1"><h3>${esc(b.name)}</h3><span class="chip ${b.tone}">${esc(b.chip)}</span></div>
    <div class="led">led by ${esc(b.lead)} · ${esc(b.kit)}</div>
    <div class="doing">${doing(b)}</div>
    ${b.trip ? tripBar(b.trip) : ""}
    <div class="faces">${b.members.map(medal).join("")}</div>
    ${foot}${actions}</div>`;
}

function splitCard(b, cls) {
  const goes = b.split.filter(x => picks.has(x.uid)), stays = b.members.length - goes.filter(x => b.members.some(m => m.uid === x.uid)).length;
  const lead = goes.find(x => b.members.some(m => m.uid === x.uid));
  const sum = !goes.length ? "Pick who walks off as a band of their own."
    : stays === 0 ? "Someone must stay."
    : !lead ? "A new band needs at least one soul."
    : `<b>${goes.length} leave${goes.length === 1 ? "s" : ""}</b> → a new band at ${esc(node(b.node).name)}, led by ${esc(lead.name)}. It takes 1 of ${M.meta.slots_free} free slots; no time passes.`;
  const ok = goes.length && stays > 0 && lead;
  return `<div class="${cls}" data-band="${b.gid}">
    <div class="row1"><h3>${esc(b.name)}</h3><span class="chip split">Splitting</span></div>
    <div class="led">pick who walks off as a band of their own</div>
    <div class="pick">${b.split.map(x => { const on = picks.has(x.uid), m = b.members.find(m => m.uid === x.uid);
      return `<div class="pk${on ? " on" : ""}" data-pick="${x.uid}"><div class="box">${on ? "✓" : ""}</div>${m ? medal(m) : `<div class="fm">${ico(x.sub === "wagon" ? "action/journey" : "action/wolf-howl")}</div>`}
        <div><b>${esc(x.name)}</b><small>${esc(x.sub)}</small></div><span class="goes">${on ? "Leaves" : "Stays"}</span></div>`; }).join("")}</div>
    <div class="sumline">${sum}</div>
    <div class="bactions"><div class="ghost-btn" data-cancel-split>Cancel</div><div class="brass-btn ${ok ? "" : "off"}" data-confirm-split ${ok ? "" : 'style="opacity:.5"'}>${ico("body/split-body")}Split off ${goes.length || ""}</div></div></div>`;
}

function drawBands() {
  const idle = M.groups.filter(b => b.idle).length;
  const waits = idle === 0 ? "none waits for" : idle === 1 ? "1 awaits" : `${idle} await`;
  $("bandsnote").textContent = `${waits} orders · ${plural(M.meta.slots_free, "slot")} free`;
  $("bandlist").innerHTML = M.groups.map(bandCard).join("");
  document.querySelector(".band.sel")?.scrollIntoView({block: "nearest"});
  $("hours").innerHTML = M.hours.map(h => `<div class="${h.now ? "now" : ""}"><b>${esc(h.at)}</b><span>${esc(h.text)}${!h.now && h.day !== M.meta.day ? ` <i>day ${h.day}</i>` : ""}</span></div>`).join("");
}

// ---------------------------------------------------------------- places and pawns
const NAME_W = 7.6;   // px per letter of a place's label, for keeping labels off each other
function placeLabels() {
  const boxes = M.nodes.map(n => { const [x, y] = Sheet.P(n.id); const r = n.id === "city" ? 30 : 20; return [x - r, y - r, x + r, y + r]; });
  const hit = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
  const out = {};
  for (const n of M.nodes) {
    const [x, y] = Sheet.P(n.id), w = n.name.length * (n.id === "city" ? 10 : NAME_W), big = n.id === "city" ? 12 : 0;
    const opts = {"": [x - w / 2, y + 22 + big, x + w / 2, y + 40 + big], up: [x - w / 2, y - 40 - big, x + w / 2, y - 22 - big],
                  r: [x + 24, y - 10, x + 24 + w, y + 8], l: [x - 24 - w, y - 10, x - 24, y + 8]};
    const pick = Object.keys(opts).find(k => !boxes.some(b => hit(opts[k], b))) ?? "";
    boxes.push(opts[pick]); out[n.id] = pick;
  }
  return out;
}

function drawPlaces() {
  const b = band(sel), side = placeLabels();
  let html = M.nodes.map(n => {
    const [x, y] = Sheet.P(n.id);
    const cls = ["node", n.id === "city" ? "city" : "", /fort|outpost/.test(n.icon || "") || n.id === "ledger_hold" ? "fort" : "",
                 n.ethereal ? "ethereal" : "", b && b.node === n.id ? "here" : "", hoverNode === n.id ? "hover" : ""].join(" ");
    return `<div class="${cls}" data-node="${n.id}" style="left:${x}px;top:${y}px"><div class="m">${n.icon ? ico(n.icon) : ""}</div>
      <div class="n ${side[n.id]}">${esc(n.name)}</div>${n.alert ? '<div class="wax">!</div>' : ""}</div>`;
  }).join("");
  const at = {};
  for (const g of M.groups) {
    const key = typeof g.at === "string" ? g.at : g.at.join();
    (at[key] = at[key] || []).push(g);
  }
  for (const list of Object.values(at)) list.forEach((g, i) => {
    const [x, y] = Sheet.bandPoint(g), dx = (i - (list.length - 1) / 2) * 46;
    const lead = g.members.find(m => m.lead) || g.members[0];
    html += `<div class="pawn ${g.gid === sel ? "sel" : ""} ${g.blocked ? "bad" : ""}" data-band="${g.gid}" title="${esc(g.name)}"
      style="left:${x + dx}px;top:${y + (typeof g.at === "string" ? -6 : 14)}px"><div class="pin"></div><div class="p">${face(lead.portrait, lead.name)}</div></div>`;
  });
  $("nodes").innerHTML = html;
  drawSlip();
}

// the slip over a hovered place: the walk there and when the picked band gets in
function drawSlip() {
  const slip = $("slip");
  if (!hoverNode || !sel) { slip.hidden = true; return; }
  const key = sel + "|" + hoverNode, p = previews.get(key), n = node(hoverNode);
  if (!n) { slip.hidden = true; return; }
  const [x, y] = Sheet.P(hoverNode);
  slip.style.left = Math.min(x + 30, 1060 - 310) + "px";
  slip.style.top = (y + 26 > 946 - 180 ? y - 190 : y + 26) + "px";
  const b = band(sel);
  let body;
  if (!p) body = `<p>${esc(n.blurb)}</p>`;
  else if (!p.path.length) body = `<p>${esc(n.blurb)}</p><div class="click no">${esc(p.why || "")}</div>`;
  else {
    const via = p.via.length ? ` by ${esc(p.via.join(", "))}` : "";
    body = `<p>Walk ${esc(b.name)} there: <b>${p.hours} h</b>${via}, in by <b>${esc(p.at)}</b>${p.day !== M.meta.day ? ` on day ${p.day}` : ""}. ${esc(n.blurb)}</p>
      ${p.why ? `<div class="click no">${esc(p.why)}</div>` : `<div class="click">Click<span>to give the order</span></div>`}`;
  }
  slip.innerHTML = `<h4>${esc(n.name)}</h4>${body}`;
  slip.hidden = false;
}

async function hover(id) {
  if (hoverNode === id) return;
  hoverNode = id;
  document.querySelectorAll(".node.hover").forEach(e => e.classList.remove("hover"));
  if (!id || !sel) { Sheet.hover(null); drawSlip(); return; }
  document.querySelector(`.node[data-node="${id}"]`)?.classList.add("hover");
  const key = sel + "|" + id;
  if (!previews.has(key)) {
    drawSlip();
    try { previews.set(key, await api(`/api/map/preview?gid=${encodeURIComponent(sel)}&node=${encodeURIComponent(id)}`)); } catch (e) { return; }
  }
  if (hoverNode !== id) return;
  const p = previews.get(key);
  Sheet.hover(p.path.length && !p.why ? p.path : null);
  drawSlip();
}

// ---------------------------------------------------------------- the inspector
function block(k) {
  if (k.t === "section") return `<div class="kicker psec">${esc(k.label)}</div>`;
  if (k.t === "note") return `<div class="pnote-line ${k.tone}">${esc(k.text)}</div>`;
  return `<div class="pbtn ${k.danger ? "danger" : ""} ${k.enabled ? "" : "off"}" data-act="${esc(k.key)}" title="${esc(k.sub || "")}">${esc(title(k.label))}</div>`;
}

function drawInspector() {
  const b = band(sel);
  if (!b) return;
  const ins = b.inspector, pl = ins.place;
  // the place's own way in is the brass button; the rest are paper buttons under it
  const main = !b.busy && !b.blocked && ins.blocks.find(k => k.t === "button" && k.enabled && !k.danger && (k.primary || !/search|explore|scout/i.test(k.key)));
  $("place").innerHTML = `<div class="kicker">Where ${esc(b.name)} stands <em>${esc(b.blocked ? "stopped" : b.busy ? b.chip.toLowerCase() : "no orders")}</em></div>
    <div class="phead"><div class="m">${pl.icon ? ico(pl.icon) : ""}</div><div><h2>${esc(pl.name)}</h2><small>${esc(pl.blurb)}</small></div></div>
    ${pl.stats.length ? `<div class="pnote">${pl.stats.map(s => `<div><b class="${s.no ? "no" : ""}">${esc(s.value)}</b><span>${esc(s.label)}</span></div>`).join("")}</div>` : ""}
    ${main ? `<div class="brass-btn" data-act="${esc(main.key)}">${pl.icon ? ico(pl.icon) : ""}${esc(title(main.label))}</div>` : ""}
    ${ins.blocks.filter(k => k !== main).map(block).join("")}`;

  const hurt = b.members.filter(m => m.hp < m.hp_max || m.sick || m.poisoned).length;
  $("party").innerHTML = `<div class="lk">The party <em>${b.members.length}${hurt ? ` · ${hurt} wounded` : " · all hale"}</em></div>` +
    b.members.map(m => { const f = m.hp_max ? m.hp / m.hp_max : 0, low = f < .34 ? "low" : f < .67 ? "mid" : "";
      return `<div class="mem">${medal(m)}<div class="who"><b>${esc(m.name)}${m.lead ? "<em>Leads</em>" : ""}${m.sick ? '<em class="ill">Sick</em>' : ""}${m.poisoned ? '<em class="ill">Poisoned</em>' : ""}</b><small>${esc(m.sub)}</small></div>
        <div class="hp"><div class="bar"><i class="${low}" style="width:${f * 100}%"></i></div><span class="${low === "low" ? "low" : ""}">${m.hp} / ${m.hp_max} HP</span></div></div>`; }).join("") +
    (ins.camp && ins.camp.hurt.length ? `<div class="warn"><b>${esc(ins.camp.hurt[0])}</b> Rest, or the Medic at the Apothecary treats them at once.</div>` : "");

  const c = ins.camp;
  if (!c) {
    $("camp").innerHTML = `<div class="lk">Camp <em>${b.blocked ? "no going on" : "on the way"}</em></div>
      <div class="busy">${b.blocked ? "Face the fight first; the seal below opens it." : esc(b.detail.charAt(0).toUpperCase() + b.detail.slice(1)) + ". Its camp waits until it stops."}</div>`;
  } else {
    $("camp").innerHTML = `<div class="lk">Camp <em>no time passes</em></div>
      <div class="duo"><div class="tile" data-act="manage_group"><div class="t">${ico("gui/checklist")}Gear &amp; quests</div><small>packs, loads, the jobs held</small></div>
        <div class="tile ${c.fire.enabled ? "" : "off"} ${/burning/.test(c.fire.sub) ? "lit" : ""}" ${c.fire.enabled ? 'data-act="campfire_cook"' : ""}><div class="t">${ico("body/fire-silhouette")}Campfire</div><small>${esc(c.fire.sub)}</small></div></div>
      <div class="lk sub">Travel <em>how the band walks</em></div>
      <div class="seg">${c.stance.map(s => `<div class="${s.on ? "on" : ""}" data-act="${s.key}" title="${esc(s.tip)}"><b>${esc(s.label)}</b><small>${esc(s.sub)}</small></div>`).join("")}</div>
      <div class="lk sub">Rest <em>eat first, then sleep</em></div>
      <div class="seg ${c.starving ? "starving" : ""}">${c.rest.map(r => `<div class="${r.rec ? "rec" : ""} ${r.enabled ? "" : "off"}" ${r.enabled ? `data-act="${r.key}"` : ""} title="${esc(r.tip || r.sub || "")}"><b>${esc(r.label)}</b><small>${esc(r.sub || "")}</small></div>`).join("")}</div>`;
  }

  const t = M.cta, seal = $("seal");
  $("ctatext").innerHTML = t.key === "cycle_idle" && /^The clock waits on /.test(t.text)
    ? `<b>The clock waits</b><br>${esc(t.text.replace(/^The clock waits /, ""))}` : esc(t.text);
  seal.className = `seal ${t.enabled ? "" : "cold"} ${t.key === "advance_world" ? "calm" : ""}`;
  seal.innerHTML = `<div><b>${esc(t.label).replace(" ", "<br>")}</b><small>${esc(t.sub || "")}</small></div>`;
}

// ---------------------------------------------------------------- news and errors
function news(lines, bad = false) {
  if (!lines.length) return;
  const n = $("news");
  n.innerHTML = `<div class="kicker">${bad ? "Not so" : "Since the last order"}</div>${lines.slice(-12).map(l => `<p class="${bad ? "bad" : ""}">${esc(l)}</p>`).join("")}<div class="click">click to put it away</div>`;
  n.hidden = false;
}
$("news").onclick = () => { $("news").hidden = true; };

// ---------------------------------------------------------------- the loop
function show(state) {
  if (state.screen && state.screen !== "map") { location.reload(); return; }
  M = state;
  previews.clear();
  if (state.focus && band(state.focus)) sel = state.focus;
  if (!band(sel)) sel = (M.groups.find(b => b.blocked) || M.groups.find(b => b.idle) || M.groups[0] || {}).gid;
  if (splitting && !band(splitting)) splitting = null;
  Sheet.selected = sel;
  Sheet.set(M);
  drawTop(); drawBands(); drawPlaces(); drawInspector();
  news(state.notices || []);
  $("wiped").hidden = !M.wiped;
  if (hoverNode) { const h = hoverNode; hoverNode = null; hover(h); }
}

function redraw() {
  Sheet.selected = sel;
  Sheet.draw(); drawBands(); drawInspector();
}

let busy = false;
async function post(verb, body) {
  if (busy) return;
  busy = true;
  try { show(await api(`/api/map/${verb}`, body)); }
  catch (e) { news([e.message], true); }
  finally { busy = false; }
}

function pickBand(gid) {
  if (!gid || gid === sel) return;
  sel = gid; splitting = null; hoverNode = null; Sheet.hover(null);
  redraw();
}

Sheet.onmove = () => { if (M) drawPlaces(); };

document.addEventListener("click", e => {
  const t = e.target.closest("[data-act],[data-band],[data-node],[data-split],[data-merge],[data-pick],[data-cancel-split],[data-confirm-split]");
  if (!t || !M) return;
  if (t.dataset.split !== undefined) {
    if (t.classList.contains("off")) return;
    splitting = t.dataset.split; picks = new Set(); drawBands(); return;
  }
  if (t.dataset.cancelSplit !== undefined) { splitting = null; drawBands(); return; }
  if (t.dataset.pick !== undefined) { picks.has(t.dataset.pick) ? picks.delete(t.dataset.pick) : picks.add(t.dataset.pick); drawBands(); return; }
  if (t.dataset.confirmSplit !== undefined) {
    if (t.classList.contains("off")) return;
    const gid = splitting; splitting = null;
    post("split", {gid, uids: [...picks]}); return;
  }
  if (t.dataset.merge !== undefined) { post("merge", {gid: sel, other: t.dataset.merge}); return; }
  if (t.dataset.act !== undefined) { if (!t.classList.contains("off")) post("act", {gid: sel, key: t.dataset.act}); return; }
  if (t.dataset.node !== undefined) {
    if (performance.now() - Sheet.dragged < 200) return;
    const b = band(sel);
    if (b && b.node !== t.dataset.node && b.idle) post("travel", {gid: sel, node: t.dataset.node});
    return;
  }
  if (t.dataset.band !== undefined) pickBand(t.dataset.band);
});

$("nodes").addEventListener("pointerover", e => { const n = e.target.closest(".node"); hover(n ? n.dataset.node : null); });
$("nodes").addEventListener("pointerleave", () => hover(null));

$("guildbtn").onclick = () => post("act", {gid: sel, key: "guild"});
$("seal").onclick = () => {
  const t = M && M.cta;
  if (!t || !t.enabled) return;
  if (t.key === "cycle_idle") {
    const i = t.idle.indexOf(sel);
    pickBand(t.idle[(i + 1) % t.idle.length]);
  } else if (t.key === "advance_world") post("advance", {});
  else post("act", {gid: t.gid, key: "resolve_event"});
};

addEventListener("keydown", e => {
  if (e.key === "Escape" && splitting) { splitting = null; drawBands(); }
  else if (e.key === "+" || e.key === "=") Sheet.zoomIn();
  else if (e.key === "-") Sheet.zoomOut();
  else if (e.key === "f" || e.key === "F") Sheet.fit();
});

api("/api/map/state").then(show).catch(e => news([e.message], true));

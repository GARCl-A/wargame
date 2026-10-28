// The BANDS tab: one band at a time, so a trade never crosses places. A chip per band across the top (the
// picked one carries the rename pencil), the band's load, rations and pace and what it can do; one leather
// column per member and animal; the wagons, the jobs in hand and the captives at the right. Drag an item onto a
// column or a worn slot to hand it over (an animal's header onto a wagon's to hitch it); a click picks, a click
// on another column drops; Shift picks several; right-click an item for its menu. A band with a fight due is
// read-only.
"use strict";

const Bands = (() => {
  let B = null, picks = null, drag = null, over = null, naming = false;
  const kg = (q, w) => { const t = q * w; return t < 0.05 ? "—" : t.toFixed(1) + " kg"; };
  const owners = () => [...B.packs, ...B.wagons];
  const owner = id => owners().find(p => p.id === id);
  const same = (a, b) => a.from === b.from && a.loc === b.loc;
  const picked = (id, loc) => picks && picks.some(p => p.from === id && p.loc === loc);

  function item(id, loc) {
    const p = owner(id);
    if (loc === "hitch") return {from: id, loc, name: p.name, qty: 1, glyph: "map/ox", kg: 0};
    const it = typeof loc === "string" ? (p.worn || []).find(w => w.zone === loc) : p.pack.find(r => r.loc === loc);
    return it && it.name ? {from: id, loc, name: it.name, qty: it.qty || 1, kg: it.kg, glyph: it.glyph} : null;
  }

  // ---------------------------------------------------------------- the bar
  function chip(c) {
    const on = c.gid === B.gid;
    const name = on && naming
      ? `<input id="rename" maxlength="24" value="${esc(B.custom)}" placeholder="${esc(B.name)}">`
      : `<b>${esc(c.name)}${on ? `<i class="pen" id="pen" title="Rename the band">✎</i>` : ""}</b>`;
    return `<div class="bchip ${on ? "on" : ""} ${c.locked ? "fight" : ""}" data-band="${c.gid}">
      <div class="medals">${c.faces.map(f => `<div class="medal">${face(f, c.name)}</div>`).join("")}</div>
      <div>${name}<span>${esc(c.where)} · ${esc(c.task)} · ${c.size} of ${c.capacity}</span></div></div>`;
  }

  function bar() {
    const [l, n] = B.load, tight = l > n * .9;
    const acts = B.actions.map(a => `<div class="ghost-btn ${a.on && !B.locked ? "" : "off"}" data-btn="${a.key}" title="${esc(a.tip)}">${ico(a.glyph)}${esc(a.label)}</div>`).join("");
    return `<div class="leather" id="bar"><div class="chips2">${B.chips.map(chip).join("")}</div><div class="vline"></div>
      <div class="metric ${l > n ? "bad" : tight ? "tight" : ""}"><span class="lbl">Band load</span><b>${l} <small>/ ${n} kg</small></b></div>
      <div class="metric ${B.rations ? "" : "bad"}"><span class="lbl">Rations</span><b>${plural(B.rations, "day")}</b></div>
      <div class="metric"><span class="lbl">Pace</span><b>${esc(B.speed)}</b></div>
      ${B.over ? `<div class="metric bad" title="Past the leader's hold: −${B.over} mental defense"><span class="lbl">Over its hold</span><b>${B.over}</b></div>` : ""}
      <div class="acts">${acts}</div></div>`;
  }

  // ---------------------------------------------------------------- the columns
  function row(p, it, loc, slot) {
    if (!it || !it.name)
      return `<div class="it empty" data-owner="${p.id}" data-zone="${slot.zone}">${ico("item/knapsack")}<div class="n"><span class="slotname">${esc(slot.label)}</span>empty</div><span></span><span></span></div>`;
    const zone = slot ? `data-zone="${slot.zone}"` : "";
    return `<div class="it ${it.coin ? "coin" : ""} ${picked(p.id, loc) ? "sel" : ""}" data-owner="${p.id}" data-loc="${loc}" ${zone} title="${esc(it.tip || "")}">
      ${ico(it.glyph)}<div class="n">${slot ? `<span class="slotname">${esc(slot.label)}</span>` : ""}${esc(it.name)}${it.locked ? `<span class="tag">locked</span>` : ""}</div>
      <span class="q">${(it.qty || 1) > 1 ? "×" + it.qty : ""}</span><span class="kg">${kg(it.qty || 1, it.kg)}</span></div>`;
  }

  function foot(p) {
    const mine = picks ? picks.filter(x => x.from === p.id) : [];
    if (mine.length) return `${mine.length === 1 ? esc(mine[0].name) : mine.length + " items"} picked · drag or click another pack`;
    if (picks) {
      const add = picks.reduce((a, x) => a + x.kg * x.qty, 0);
      return `Hand the pick to ${esc(p.name.split(" ")[0])} · <b>+${add.toFixed(1)} kg</b>`;
    }
    if (p.kg > p.normal) return `<span class="bad">Past a normal load by <b>${(p.kg - p.normal).toFixed(1)} kg</b> · slows the band</span>`;
    if (p.hungry) return p.beast ? `Unfed <b>${plural(p.unfed, "day")}</b>` : "No food reaches them · <b>hungry</b>";
    return "";
  }

  function column(p) {
    const tight = p.kg > p.normal * .85, overload = p.kg > p.normal;
    const med = `<div class="medal ${p.beast ? "beastmed" : ""} ${p.hurt ? "hurt" : ""}" ${p.beast ? `data-owner="${p.id}" data-loc="hitch"` : ""}>${face(p.portrait, p.name)}</div>`;
    const worn = p.worn.length ? `<div class="csec lbl">${p.beast ? "Tack" : "Worn"}</div>` + p.worn.map(w => row(p, w.name ? w : null, w.zone, w)).join("") : "";
    const rows = p.pack.length ? p.pack.map(r => row(p, r, r.loc, null)).join("")
      : `<div class="it empty"><span></span><div class="n">nothing carried</div><span></span><span></span></div>`;
    const btns = [p.ride && `<div class="ghost-btn ${p.ride.on ? "" : "off"}" data-btn="ride:${p.id}" title="${esc(p.ride.tip)}">${esc(p.ride.label)}</div>`,
      p.hitch && `<div class="ghost-btn" data-btn="hitch:${p.id}" title="Hitch it to the next wagon">${esc(p.hitch.label)}</div>`].filter(Boolean).join("");
    const f = foot(p);
    return `<div class="col" data-owner="${p.id}">
      <div class="colh">${med}<div style="min-width:0"><h3>${esc(p.name)}</h3><div class="race">${esc(p.sub)}</div>${p.lead ? `<span class="voice">Leads the band</span>` : ""}</div></div>
      <div class="cst"><div class="money"><i class="coindot"></i>${p.money}</div><div class="load ${overload ? "over" : tight ? "tight" : ""}"><b>${p.kg.toFixed(1)}</b> / ${p.normal} kg</div></div>
      <div class="cbar"><i class="${overload ? "over" : tight ? "tight" : ""}" style="width:${Math.min(100, p.kg / Math.max(p.normal, .1) * 100)}%"></i></div>
      ${btns ? `<div class="cbtn">${btns}</div>` : ""}
      ${worn}<div class="csec lbl">Pack</div><div class="packlist">${rows}</div>
      ${f ? `<div class="cfoot">${f}</div>` : ""}</div>`;
  }

  function wagon(w) {
    const drawn = w.drawn.length ? w.drawn.map(a => `<div class="beast"><div class="medal">${face(a.portrait, a.name)}</div><div><b>${esc(a.name)}</b> <span class="mark" style="font-size:8px">${esc((a.tack || "no tack").toLowerCase())}</span>
        <p class="${a.unfed ? "bad" : ""}">${a.unfed ? `unfed ${plural(a.unfed, "day")}` : "fed"}</p></div></div>`).join("")
      : `<div class="empty-note">Nothing pulls it. Drag a harnessed animal's portrait here.</div>`;
    const rows = w.pack.length ? w.pack.map(r => row(w, r, r.loc, null)).join("") : `<div class="empty-note">No cargo.</div>`;
    const repair = w.repair ? `<div class="cbtn"><div class="ghost-btn ${w.repair.on ? "" : "off"}" data-btn="repair:${w.id}" title="${w.repair.cost} ${esc(w.repair.item)} and ${w.repair.hours} h, then an INT check">Repair · ${w.repair.cost} ${esc(w.repair.item)}</div></div>` : "";
    return `<div class="col wag" data-owner="${w.id}" data-hitch="${w.id}">
      <div class="colh"><div class="medal beastmed">${ico(w.glyph)}</div><div style="min-width:0"><h3>${esc(w.name)}</h3><div class="race">${w.drawn.length ? "pulled by the " + esc(w.drawn.map(a => a.name.toLowerCase()).join(" and ")) : "nothing hitched"}</div></div></div>
      <div class="whp">${Array.from({length: w.hp[1]}, (_, i) => `<i class="${i < w.hp[0] ? "" : "off"}"></i>`).join("")}</div>
      <div class="wnote ${w.broken ? "bad" : ""}">${w.hp[0]} of ${w.hp[1]} hull${w.broken ? " · broken" : " · the road wears it"}${w.riders.length ? ` · riding: ${esc(w.riders.join(", "))}` : ""}</div>
      ${repair}<div class="csec lbl">Hitched</div>${drawn}
      <div class="csec lbl">Cargo <em style="font-style:normal;letter-spacing:0;margin-left:auto">${w.kg} / ${w.budget} kg</em></div><div class="packlist">${rows}</div></div>`;
  }

  function side() {
    const jobs = B.jobs.length ? B.jobs.map(j => `<div class="job"><b>${esc(j.name)}</b><p>held by ${esc(j.by)}${j.days !== null && j.days !== undefined ? ` · ${plural(j.days, "day")} left` : ""}${j.progress ? ` · ${j.progress[0]} / ${j.progress[1]} ${esc(j.progress[2])}` : ""}</p></div>`).join("")
      : `<div class="empty-note">No job taken by anyone in this band. A giver's board lists what is on offer.</div>`;
    const caps = B.captives.length ? B.captives.map(c => `<div class="job"><b>${esc(c.name)}</b><p>${esc(c.race)} · dies in ${plural(c.days, "day")}</p><div class="ghost-btn" data-btn="release:${c.uid}">Release</div></div>`).join("")
      : `<div class="empty-note">Nobody bound. A captive walks with the band, counts on the herd and dies seven days after the fight.</div>`;
    return B.wagons.map(wagon).join("") + `<div class="col" style="flex:1 0 auto">
      <div class="csec lbl" style="margin-top:2px">Jobs in hand</div>${jobs}
      <div class="csec lbl">Captives</div>${caps}</div>`;
  }

  // ---------------------------------------------------------------- drawing
  function draw(st) {
    B = st;
    if (picks && picks.some(p => !item(p.from, p.loc))) picks = null;
    const keep = {cols: $("cols") ? $("cols").scrollLeft : 0, lists: {}};
    document.querySelectorAll(".col[data-owner]").forEach(c => { const l = c.querySelector(".packlist"); if (l) keep.lists[c.dataset.owner] = l.scrollTop; });
    const locked = B.locked ? "locked" : "";
    $("body").innerHTML = bar() + (B.locked ? `<div class="lockline">${esc(B.lock_tip)}</div>` : "")
      + `<div id="cols" class="${locked}">${B.packs.map(column).join("")}</div><div id="side" class="${locked}">${side()}</div>`;
    $("cols").scrollLeft = keep.cols;
    document.querySelectorAll(".col[data-owner]").forEach(c => { const l = c.querySelector(".packlist"); if (l) l.scrollTop = keep.lists[c.dataset.owner] || 0; });
    const input = $("rename");
    if (input) {
      input.focus();
      input.select();
      input.onkeydown = e => {
        if (e.key === "Enter") { naming = false; post("rename", {name: input.value}); }
        else if (e.key === "Escape") { naming = false; redraw(); e.stopPropagation(); }
      };
      input.onblur = () => { if (naming) { naming = false; redraw(); } };
    }
  }
  const redraw = () => draw(B);

  async function act(verb, body) {
    picks = null;
    const r = await post(verb, body);
    if (r) Sound.play("click");
  }

  // ---------------------------------------------------------------- what the person does
  const wire = list => list.map(({from, loc}) => ({from, loc}));

  function drop(el, src) {
    if (!el || B.locked) return;
    const list = picks && picks.some(p => same(p, src)) ? picks : [src];
    if (src.loc === "hitch") {
      const w = el.closest("[data-hitch]");
      if (w) act("move", {picks: wire([src]), to: w.dataset.hitch, zone: "hitch"});
      return;
    }
    const col = el.closest(".col[data-owner]");
    if (!col) return;
    const slot = el.closest(".it[data-zone]");
    const zone = slot ? slot.dataset.zone : "pack";
    if (zone === "pack" && list.every(x => x.from === col.dataset.owner && typeof x.loc === "number")) return;
    act("move", {picks: wire(list), to: col.dataset.owner, zone});
  }

  function source(el) {
    const it = el.closest("[data-loc]");
    if (!it || B.locked) return null;
    const loc = /^\d+$/.test(it.dataset.loc) ? Number(it.dataset.loc) : it.dataset.loc;
    return item(it.dataset.owner, loc);
  }

  function click(el, e) {
    const c = el.closest(".bchip[data-band]");
    if (el.closest("#pen")) { naming = true; return redraw(); }
    if (c) {
      if (c.dataset.band !== B.gid) { picks = null; Sound.play("click"); post("band", {gid: c.dataset.band}); }
      return;
    }
    const b = el.closest("[data-btn]");
    if (b) {
      if (!b.classList.contains("off") && !B.locked) act("button", {key: b.dataset.btn});
      return;
    }
    const it = source(el);
    if (it) {
      const list = picks || [];
      if (e.shiftKey) {
        const rest = list.filter(p => !same(p, it));
        picks = rest.length === list.length ? [...list, it] : rest.length ? rest : null;
        return redraw();
      }
      if (list.length && !list.some(p => p.from === it.from)) return drop(el, list[0]);
      picks = list.length === 1 && same(list[0], it) ? null : [it];
      return redraw();
    }
    if (picks && el.closest(".col[data-owner]")) return drop(el, picks[0]);
    if (picks && !el.closest("#menu")) { picks = null; redraw(); }
  }

  function ghost(src) {
    const list = picks && picks.some(p => same(p, src)) ? picks : [src];
    const it = list[0];
    $("ghost").innerHTML = `${ico(it.glyph)}<div><b>${esc(list.length > 1 ? list.length + " items" : it.qty > 1 ? `${it.name} ×${it.qty}` : it.name)}</b><span>${src.loc === "hitch" ? "onto a wagon to pull it" : kg(it.qty, it.kg)}</span></div>`;
  }

  function stagePoint(e) {
    const r = $("stage").getBoundingClientRect(), s = r.width / 1920;
    return [(e.clientX - r.left) / s, (e.clientY - r.top) / s];
  }

  function target(el) {
    if (!el) return null;
    if (drag.src.loc === "hitch") return el.closest("[data-hitch]");
    return el.closest(".it[data-zone]") || el.closest(".col[data-owner]");
  }

  function mark(el) {
    if (over === el) return;
    if (over) over.classList.remove("drop");
    over = el;
    if (over) over.classList.add("drop");
  }

  // ---------------------------------------------------------------- the item menu: a paper slip
  async function menu(e, it) {
    let M;
    try { M = await api("/api/guild/menu", {pick: {from: it.from, loc: it.loc}}); } catch (err) { return toast(err.message); }
    const m = $("menu"), p = owner(it.from);
    const run = r => act("menu_run", {pick: {from: it.from, loc: it.loc}, row: r});
    const rows = M.rows.filter(r => r.kind !== "member").map(r => `<div class="o" data-row="${r.row}">${esc(r.label)}</div>`);
    if (M.held > 1) rows.push(`<div class="o" data-split="1">Split the stack…</div>`);
    if (M.lockable) rows.push(`<div class="o" data-lock="1">${M.locked ? "Unlock it" : "Lock it in this pack"}</div>`);
    const to = M.rows.filter(r => r.kind === "member").map(r =>
      `<div class="o" data-row="${r.row}">${esc(r.label)}<small class="${r.free < 0 ? "bad" : ""}">${r.free < 0 ? "already over" : r.free.toFixed(1) + " kg free"}</small></div>`);
    m.innerHTML = `<div class="mh">${esc(it.name)}${it.qty > 1 ? " ×" + it.qty : ""} · ${esc(p.name)}</div>${rows.join("")}${to.length ? "<hr>" + to.join("") : ""}`;
    m.onclick = ev => {
      const d = ev.target.closest(".o");
      if (!d) return;
      if (d.dataset.split) return splitter(it, M.held);
      m.hidden = true;
      if (d.dataset.lock) return act("lock", {owner: it.from, name: it.name});
      run(Number(d.dataset.row));
    };
    place(m, e);
  }

  function splitter(it, held) {
    const m = $("menu");
    let n = Math.max(1, held >> 1);
    const paint = () => {
      m.innerHTML = `<div class="mh">Split ${esc(it.name)} ×${held}</div>
        <div class="qty"><span data-q="-1">−</span><b>${n}</b><span data-q="1">+</span><em data-go="1">Split</em></div>
        <div class="o" style="cursor:default;font-size:14px;color:#6b5233">${n} into a stack of their own, ${held - n} stay</div>`;
    };
    paint();
    m.onclick = ev => {
      const q = ev.target.closest("[data-q]");
      if (q) { n = Math.max(1, Math.min(held - 1, n + Number(q.dataset.q) * (ev.shiftKey ? 5 : 1))); return paint(); }
      if (ev.target.closest("[data-go]")) { m.hidden = true; act("split", {pick: {from: it.from, loc: it.loc}, qty: n}); }
    };
  }

  function place(m, e) {
    const [x, y] = stagePoint(e);
    m.hidden = false;
    m.style.left = Math.min(x, 1920 - m.offsetWidth - 12) + "px";
    m.style.top = Math.min(y, 1080 - m.offsetHeight - 12) + "px";
  }

  // ---------------------------------------------------------------- the pointer
  const body = $("body");
  body.addEventListener("pointerdown", e => {
    if (e.button !== 0 || !B || G.tab !== "bands" || e.target.closest("input")) return;
    $("menu").hidden = true;
    drag = {src: source(e.target), x: e.clientX, y: e.clientY, moving: false};
  });
  addEventListener("pointermove", e => {
    if (!drag || !drag.src) return;
    if (!drag.moving && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 6) return;
    if (!drag.moving) { drag.moving = true; ghost(drag.src); $("ghost").hidden = false; }
    const [x, y] = stagePoint(e), g = $("ghost");
    g.style.left = x + "px";
    g.style.top = y + "px";
    mark(target(document.elementFromPoint(e.clientX, e.clientY)));
  });
  addEventListener("pointerup", e => {
    if (!drag) return;
    const d = drag;
    drag = null;
    $("ghost").hidden = true;
    mark(null);
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (d.moving) drop(el, d.src);
    else if (el && el.closest("#body")) click(el, e);
  });
  body.addEventListener("contextmenu", e => {
    if (!B || G.tab !== "bands") return;
    e.preventDefault();
    const it = source(e.target);
    if (it && it.loc !== "hitch") menu(e, it);
  });
  addEventListener("pointerdown", e => { if (!e.target.closest("#menu")) $("menu").hidden = true; }, true);

  function escape() {
    if (!$("menu").hidden) { $("menu").hidden = true; return true; }
    if (picks) { picks = null; redraw(); return true; }
    return false;
  }

  return {draw, escape};
})();

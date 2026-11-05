// The ROUTINES tab, the Book of routines: the routines the player has written, one on paper as a stack of
// sentences with inline fields (after references/routines_mockup). A "+" between two lines adds a block, a
// line moves by its grip, any underlined word changes it. The page is the `routines.dump` shape the server
// keeps: an edit changes the working copy and posts the whole page, and the server's answer redraws the tab
// (a refusal puts the page back as it was). The same editor writes the copy a band was given, on the BANDS
// tab's routine view (`group`): there it adjusts fields and blocks, never the Book's page.
"use strict";

const Book = (() => {
  let R = null, P = null, menu = null, refOpen = null, drag = null, sure = false, mode = "book", AT = null, STOP = null, BAND = null, keepTop = 0;
  const OPS = ["<", "<=", ">", ">="], OPL = {"<": "<", "<=": "≤", ">": ">", ">=": "≥"};
  const DOING = ["gather", "work", "craft", "rest", "travel"];
  const doing = k => DOING.includes(k) ? tr(`routine.doing.${k}`) : k;
  const SIGN = {Wait: "⏳", Take: "⤓", HandOver: "⇄", Repeat: "↻", Trade: "¤", Travel: "➜", Gather: "⛏", Work: "⚒", Craft: "✎", Study: "✧", Repair: "🔧", Store: "⤒", Fetch: "⤓", Rest: "☾"};
  const GROUPS = [["move", ["Travel", "Gather", "Work", "Craft", "Study", "Repair", "Rest"]],
    ["goods", ["Take", "HandOver", "Store", "Fetch", "Trade"]], ["flow", ["Wait", "Repeat"]]];
  const kind = k => k.toLowerCase();

  const ref = (how, arg = null) => ({_: "Ref", how, arg});
  const cond = (metric, r, op, value, item = null) => ({_: "Cond", metric, ref: r, item, op, value});
  const fresh = {
    Travel: () => ({_: "Travel", node: R.vocab.nodes[0][0]}),
    Gather: () => ({_: "Gather", hours: 16}),
    Work: () => ({_: "Work", hours: 16}),
    Craft: () => ({_: "Craft", recipe: R.vocab.recipes[0], hours: 8}),
    Study: () => ({_: "Study", target: R.vocab.studies[0][0], days: 1}),
    Repair: () => ({_: "Repair", wagon: R.vocab.wagons[0] || "Cart"}),
    Store: () => ({_: "Store", place: "house", item: "Lumber", count: null}),
    Fetch: () => ({_: "Fetch", place: "house", item: "Lumber", count: null}),
    Rest: () => ({_: "Rest", hours: 8}),
    Wait: () => ({_: "Wait", cond: cond("coins", ref("own"), ">=", 1)}),
    Take: () => ({_: "Take", source: other(), item: "Lumber", count: null, until_days: null}),
    HandOver: () => ({_: "HandOver", to: other(), item: "Lumber", count: null, fallback: true}),
    Trade: () => ({_: "Trade", sell: [], buy: [], food_days: null, food: "Potato", max_spend: null}),
    Repeat: () => ({_: "Repeat", cond: cond("coins", ref("own"), "<", 500), body: [], until: false}),
  };
  const other = () => ref("here");

  // ---------------------------------------------------------------- the stack: paths are "0,2" = blocks[0].body[2]
  const listOf = p => p === "" ? P.blocks : blockAt(p).body;
  const blockAt = p => {
    let list = P.blocks, b = null;
    for (const i of p.split(",").map(Number)) { b = list[i]; list = b.body; }
    return b;
  };
  const refName = r => r.how === "own" ? tr("routine.this_group") : r.how === "named" ? r.arg : r.how === "doing" ? tr("routine.group_doing", {doing: doing(r.arg)}) : tr("routine.any_other");

  const select = (opts, val, f) => `<select class="fld" data-f="${f}">${opts.map(o => {
    const [v, l] = Array.isArray(o) ? o : [o, o];
    return `<option value="${esc(v)}"${String(v) === String(val) ? " selected" : ""}>${esc(l)}</option>`;
  }).join("")}</select>`;
  const itemSelect = (val, f) => `<select class="fld" data-f="${f}">${R.vocab.items.map(([kind, names]) =>
    `<optgroup label="${esc(kind)}">${names.map(n => `<option${n === val ? " selected" : ""}>${esc(n)}</option>`).join("")}</optgroup>`).join("")}</select>`;
  const wagonSelect = val => select([...new Set([...R.vocab.wagons, val])], val, "wagon");
  const places = () => [["house", tr("routine.place_house")], ["bank", tr("routine.place_bank")], ["garage", tr("routine.place_garage")]];
  const num = (val, f, ph = "") => `<input class="fld num" data-f="${f}" value="${val ?? ""}" placeholder="${ph}" size="2" inputmode="decimal">`;

  function refField(r, key, ownOk) {
    const open = refOpen === key, cur = (how, arg) => r.how === how && (arg === undefined || r.arg === arg) ? " cur" : "";
    const pop = !open ? "" : `<div class="refpop">
      ${ownOk ? `<div class="o${cur("own")}" data-set="${key}" data-how="own">${tr("routine.this_group_o")}<small>${tr("routine.this_group_note")}</small></div><hr>` : ""}
      <h6>${tr("routine.by_name")}</h6>${R.vocab.groups.map(g => `<div class="o${cur("named", g)}" data-set="${key}" data-how="named" data-arg="${esc(g)}">${esc(g)}</div>`).join("")}
      <div class="note">${tr("routine.follows_name")}</div><hr>
      <h6>${tr("routine.doing_h")}</h6>${DOING.slice(0, 4).map(k => `<div class="o${cur("doing", k)}" data-set="${key}" data-how="doing" data-arg="${k}">${tr("routine.group_doing", {doing: doing(k)})}</div>`).join("")}
      <div class="note">${tr("routine.follows_doing")}</div><hr>
      <div class="o${cur("here")}" data-set="${key}" data-how="here">${tr("routine.any_other_o")}<small>${tr("routine.any_other_note")}</small></div></div>`;
    return `<span class="refw${open ? " open" : ""}"><button class="ref" data-ref="${key}">${esc(refName(r))}</button>${pop}</span>`;
  }

  const whatOf = c => c.metric === "items" ? "i:" + c.item : c.metric;
  function condText(c, p) {
    const whats = [...R.vocab.items.flatMap(([, names]) => names).map(n => ["i:" + n, n]), ["coins", tr("routine.coins")], ["hp", tr("routine.lowest_hp")], ["food_days", tr("routine.food_days")]];
    const held = c.metric === "items" || c.metric === "coins";
    return tr(held ? "routine.cond_held" : "routine.cond_of", {what: select(whats, whatOf(c), "cond.what"), ref: refField(c.ref, p + "|cond.ref", true),
      op: select(OPS.map(o => [o, OPL[o]]), c.op, "cond.op"), value: num(c.value, "cond.value")});
  }

  const chips = (list, f, pairs) => list.map((x, i) => `<span class="chip">${pairs ? num(x[1], `${f}.${i}.1`) + " " + esc(x[0]) : esc(x)}<i data-x="${f}.${i}">×</i></span>`).join("")
    + `<select class="fld" data-add="${f}"><option value="">${tr("routine.add_item")}</option>${R.vocab.items.map(([kind, names]) =>
      `<optgroup label="${esc(kind)}">${names.map(n => `<option>${esc(n)}</option>`).join("")}</optgroup>`).join("")}</select>`;

  const takeMode = b => b.until_days != null ? "food" : b.count != null ? "n" : "all";
  function sentence(b, p) {
    switch (b._) {
      case "Travel": return tr("routine.travel", {node: select(R.vocab.nodes, b.node, "node")});
      case "Gather": return tr("routine.gather", {hours: num(b.hours, "hours")});
      case "Work": return tr("routine.work", {hours: num(b.hours, "hours")});
      case "Rest": return tr("routine.rest", {hours: num(b.hours, "hours")});
      case "Craft": return tr("routine.craft", {recipe: select(R.vocab.recipes, b.recipe, "recipe"), hours: num(b.hours, "hours")});
      case "Study": return tr("routine.study", {target: select(R.vocab.studies, b.target, "target"), days: num(b.days, "days")});
      case "Repair": return tr("routine.repair", {wagon: wagonSelect(b.wagon)});
      case "Store": case "Fetch": {
        const m = b.count != null ? "n" : "all";
        return tr(b._ === "Store" ? "routine.store" : "routine.fetch", {mode: select([["all", tr("routine.all")], ["n", tr("routine.number")]], m, "mode") + (m === "n" ? " " + num(b.count, "count") : ""),
          item: itemSelect(b.item, "item"), place: select(places(), b.place, "place")});
      }
      case "Wait": return tr("routine.wait", {cond: condText(b.cond, p)});
      case "Take": {
        const m = takeMode(b), mode = select([["all", tr("routine.all")], ["n", tr("routine.number")], ["food", tr("routine.enough")]], m, "mode");
        return tr("routine.take", {mode: m === "n" ? mode + " " + num(b.count, "count") : m === "food" ? tr("routine.food_mode", {mode, n: num(b.until_days, "until_days")}) : mode,
          item: itemSelect(b.item, "item"), source: refField(b.source, p + "|source", false)});
      }
      case "HandOver": {
        const m = b.count != null ? "n" : "all";
        return `<span class="row">${tr("routine.handover", {mode: select([["all", tr("routine.all")], ["n", tr("routine.number")]], m, "mode") + (m === "n" ? " " + num(b.count, "count") : ""),
          item: itemSelect(b.item, "item"), to: refField(b.to, p + "|to", false)})}</span>
          <span class="row"><span class="tog" data-tog="fallback"${tip(tr("routine.fallback_tip"))}><span class="sw${b.fallback ? " on" : ""}"></span>${tr("routine.fallback")}</span></span>`;
      }
      case "Trade": return `<span class="row">${tr("routine.trade_here")} <span class="plain">${tr("routine.sell_all")}</span> ${chips(b.sell, "sell")}</span>
        <span class="row"><span class="plain">${tr("routine.buy")}</span> ${chips(b.buy, "buy", true)}</span>
        <span class="row"><span class="plain">${tr("routine.food_for")}</span> ${num(b.food_days, "food_days", "—")} ${tr("routine.days")} · <span class="plain">${tr("routine.spend")}</span> ${num(b.max_spend, "max_spend", tr("routine.no_limit"))} ${tr("routine.spend_coins")}</span>`;
      case "Repeat": return tr("routine.repeat", {until: select([["while", tr("routine.while")], ["until", tr("routine.until")]], b.until ? "until" : "while", "until"), cond: condText(b.cond, p)});
    }
    return "";
  }

  function gap(list, i) {
    const id = `${list}|${i}`, open = menu === id;
    const m = !open ? "" : `<div class="menu">${GROUPS.map(([g, l]) => `<h6>${tr(`routine.group.${g}`)}</h6>` + l.map(k =>
      `<div class="o" data-new="${k}" data-list="${list}" data-i="${i}"><span class="g">${SIGN[k]}</span>${tr(`routine.kind.${kind(k)}`)}<small>${tr(`routine.hint.${kind(k)}`)}</small></div>`).join("")).join("")}</div>`;
    return `<div class="gap${open ? " open" : ""}" data-list="${list}" data-i="${i}"><span class="plus" data-plus="${id}"${tip(tr("routine.add_block"))}>+</span>${m}</div>`;
  }

  function stack(blocks, list) {
    let h = gap(list, 0);
    blocks.forEach((b, i) => {
      const p = list === "" ? "" + i : `${list},${i}`;
      const now = AT === p ? (STOP ? " stop" : " now") : "";
      h += `<div class="blk${now}" data-p="${p}"><span class="grip" draggable="true" data-move="${p}"${tip(tr("routine.drag_line"))}>⠿</span><span class="glyph">${SIGN[b._]}</span>
        <div class="sent">${sentence(b, p)}${AT === p && STOP ? `<p class="why">${tr("routine.stopped_why", {why: esc(STOP)})}</p>` : ""}</div><span class="del" data-del="${p}"${tip(tr("routine.remove"))}>×</span>${now ? `<span class="where">${STOP ? tr("routine.stopped") : tr("routine.here")}</span>` : ""}</div>`;
      if (b._ === "Repeat") h += `<div class="body">${stack(b.body, p)}</div>`;
      h += gap(list, i + 1);
    });
    return h;
  }

  // ---------------------------------------------------------------- the tab
  function seats() {
    const [used, slots] = R.seats;
    const pips = Array.from({length: slots}, (_, i) => `<span class="pip${i < used ? " used" : ""}"></span>`).join("");
    const nxt = `<span class="next">${tr("routine.next_seat", {n: R.next})}</span>`;
    return `<div class="leather" id="bseats"><div><div class="lbl">${tr("routine.book")}</div><div class="sub">${tr("routine.book_note")}</div></div>
      <div class="pips">${pips}</div><div class="count">${tr("routine.seats_taken", {used, slots})}</div>${nxt}</div>`;
  }

  function list() {
    const cards = R.pages.map((p, i) => `<div class="rcard${i === R.pick ? " on" : ""}" data-pick="${i}"><b>${esc(p.name)}</b>${p.note ? `<p>${esc(p.note)}</p>` : ""}</div>`).join("");
    return `<div class="leather" id="blist"><div class="lbl" style="padding:0 20px 14px">${tr("routine.written")}</div>${cards}
      <div class="ghost-btn" id="bnew">${tr("routine.new")}</div>
      <div class="note-l">${tr("routine.written_note")}</div></div>`;
  }

  function page() {
    if (!P) return `<div class="paper" id="bpage"><div class="kicker">${tr("routine.kicker")}</div><div class="desc" style="margin-top:24px">${tr("routine.nothing")}</div></div>`;
    return `<div class="paper" id="bpage"><div class="kicker">${tr("routine.kicker")}</div>
      <div class="bhead"><input class="title" id="bname" maxlength="32" value="${esc(P.name)}" placeholder="${tr("routine.name_ph")}">
        <div class="ghost-btn${sure ? " warn" : ""}" id="btear">${sure ? tr("routine.tear_sure") : tr("routine.tear")}</div></div>
      <input class="desc" id="bnote" maxlength="120" value="${esc(P.note)}" placeholder="${tr("routine.note_ph")}">
      <div class="stack">${stack(P.blocks, "")}</div></div>`;
  }

  function draw(routines) {
    mode = "book";
    AT = STOP = null;
    R = routines;
    const src = R.pages[R.pick];
    P = src ? JSON.parse(JSON.stringify(src)) : null;
    drag = null;
    const keep = $("bpage") ? $("bpage").scrollTop : 0;
    $("body").innerHTML = seats() + list() + page();
    if ($("bpage")) $("bpage").scrollTop = keep;
    const pop = document.querySelector(".menu, .refpop");        // a popup that would run off the sheet opens upward
    if (pop && pop.getBoundingClientRect().bottom > $("screen").getBoundingClientRect().bottom - 16) pop.classList.add("up");
  }

  async function save() {
    menu = refOpen = null;
    if (mode === "group") {
      if (!await post("routine_save", {blocks: P.blocks})) redraw();
      return;
    }
    const r = await post("book_save", {i: R.pick, name: P.name, note: P.note, blocks: P.blocks});
    if (!r) draw(G.routines);
  }

  // ---------------------------------------------------------------- a band's own copy
  function group(st) {
    mode = "group";
    BAND = st;
    R = st.routine || {vocab: null};
    keepTop = $("bpage") ? $("bpage").scrollTop : 0;
    if (!st.routine) {
      P = null;
      const [used, slots] = st.equip.seats, pages = st.equip.pages;
      const cards = pages.map(([i, n]) => `<div class="rcard" data-equip="${i}"><b>${esc(n)}</b></div>`).join("");
      return `<div class="paper" id="bpage" style="left:32px;top:196px;width:1856px;height:852px"><div class="kicker">${tr("routine.no_routine")}</div>
        <div class="desc" style="margin-top:20px">${!pages.length ? tr("routine.nothing_book") : used >= slots ? tr("routine.seats_full") : tr("routine.pick_one")}</div>
        <div class="pages">${cards}</div></div>`;
    }
    P = JSON.parse(JSON.stringify(st.routine));
    AT = P.at;
    STOP = P.paused;
    const state = STOP ? `<div class="ghost-btn go" id="bcont">${tr("routine.continue")}</div>` : `<span class="mark good">${tr("routine.running")}</span>`;
    return `<div class="leather" id="gbar"><span class="lbl">${tr("routine.equipped")}</span>
        <div class="eq"><b>${esc(P.name || tr("routine.a_routine"))}</b><i>${tr("routine.copy")}</i></div>
        <div class="ghost-btn" id="bback"${tip(tr("routine.save_back_tip"))}>${tr("routine.save_back")}</div>
        <span class="sp"></span>${state}
        <div class="ghost-btn${sure ? " warn" : ""}" id="btake">${sure ? tr("routine.take_sure") : tr("routine.take_off")}</div></div>
      <div class="paper" id="bpage" style="left:32px;top:276px;width:1856px;height:772px"><div class="kicker">${tr("routine.on_band")}</div>
      ${P.note ? `<div class="desc ro">${esc(P.note)}</div>` : ""}
      <div class="stack">${stack(P.blocks, "")}</div></div>`;
  }

  function settle() {
    drag = null;
    if ($("bpage")) $("bpage").scrollTop = keepTop;
    const pop = document.querySelector(".menu, .refpop");
    if (pop && pop.getBoundingClientRect().bottom > $("screen").getBoundingClientRect().bottom - 16) pop.classList.add("up");
  }
  const redraw = () => mode === "group" ? Bands.draw(BAND) : draw(R);

  // ---------------------------------------------------------------- the verbs
  const body = $("body");
  const mine = () => G && R && (mode === "group" ? G.tab === "bands" && G.bands.view === "routine" : G.tab === "routines");
  function holder(p, f) {
    const b = blockAt(p);
    return f.startsWith("cond.") ? b.cond : b;
  }
  function setRef(key, how, arg) {
    const [p, f] = key.split("|");
    holder(p, f)[f.split(".").pop()] = ref(how, how === "own" || how === "here" ? null : arg);
  }

  body.addEventListener("click", e => {
    if (!mine()) return;
    const t = e.target.closest("[data-plus],[data-new],[data-ref],[data-set],[data-del],[data-x],[data-pick],[data-tog],#bnew,#btear,#bback,#btake,#bcont,[data-equip]");
    if (!t) {
      if (menu || refOpen || sure) { menu = refOpen = null; sure = false; redraw(); }
      return;
    }
    const d = t.dataset;
    if (d.equip != null) return post("equip", {i: +d.equip});
    if (t.id === "bback") return post("save_back");
    if (t.id === "bcont") return post("continue_routine");
    if (t.id === "btake") {
      if (!sure) { sure = true; return redraw(); }
      sure = false;
      return post("take_off");
    }
    if (t.id === "bnew") return post("book_new", {});
    if (t.id === "btear") {
      if (!sure) { sure = true; return redraw(); }
      sure = false;
      return post("book_tear", {i: R.pick});
    }
    sure = false;
    if (d.pick != null) return post("book_pick", {i: +d.pick});
    if (d.plus != null) { menu = menu === d.plus ? null : d.plus; refOpen = null; return redraw(); }
    if (d.ref != null) { refOpen = refOpen === d.ref ? null : d.ref; menu = null; return redraw(); }
    if (d.new) { listOf(d.list).splice(+d.i, 0, fresh[d.new]()); return save(); }
    if (d.set) { setRef(d.set, d.how, d.arg); return save(); }
    if (d.del != null) {
      const a = d.del.split(",").map(Number), i = a.pop();
      (a.length ? blockAt(a.join(",")).body : P.blocks).splice(i, 1);
      return save();
    }
    if (d.x) {
      const b = blockAt(t.closest("[data-p]").dataset.p), [k, i] = d.x.split(".");
      b[k].splice(+i, 1);
      return save();
    }
    if (d.tog) { const b = blockAt(t.closest("[data-p]").dataset.p); b.fallback = !b.fallback; return save(); }
  });

  const number = v => v === "" ? null : Math.max(0, Number(v) || 0);
  body.addEventListener("change", e => {
    if (!mine()) return;
    const el = e.target;
    if (el.id === "bname") { P.name = el.value; return save(); }
    if (el.id === "bnote") { P.note = el.value; return save(); }
    const blk = el.closest("[data-p]");
    if (!blk) return;
    const b = blockAt(blk.dataset.p), f = el.dataset.f;
    if (el.dataset.add != null) {
      if (!el.value) return;
      const k = el.dataset.add;
      b[k].push(k === "buy" ? [el.value, 1] : el.value);
      return save();
    }
    if (!f) return;
    const v = el.tagName === "INPUT" ? number(el.value) : el.value;
    if (f === "until") b.until = v === "until";
    else if (f === "cond.what") {
      const c = b.cond;
      if (v.startsWith("i:")) { c.metric = "items"; c.item = v.slice(2); } else { c.metric = v; c.item = null; }
    } else if (f === "mode") {
      if (b._ === "Take") { b.count = v === "n" ? 1 : null; b.until_days = v === "food" ? 3 : null; if (v === "food") b.item = "Potato"; }
      else b.count = v === "n" ? 1 : null;
    } else if (f.split(".").length === 3) { const [k, i, j] = f.split("."); b[k][+i][+j] = v ?? 1; }
    else if (f.startsWith("cond.")) b.cond[f.slice(5)] = v;
    else b[f] = v;
    save();
  });

  // a line moves by its grip onto another gap; a Repeat never goes into itself
  const shift = (path, fromList, from) => {
    const parts = path.split(","), d = fromList === "" ? 0 : fromList.split(",").length;
    if (+parts[d] > from) parts[d] = +parts[d] - 1;
    return parts.join(",");
  };
  body.addEventListener("dragstart", e => {
    const g = e.target.closest("[data-move]");
    if (!mine() || !g) return;
    drag = g.dataset.move;
    e.dataTransfer.setData("text/plain", drag);
    g.closest(".blk").classList.add("moving");
    $("bpage").classList.add("dragging");
  });
  body.addEventListener("dragover", e => {
    const g = e.target.closest(".gap");
    if (!g || drag == null) return;
    e.preventDefault();
    document.querySelectorAll(".gap.over").forEach(x => x !== g && x.classList.remove("over"));
    g.classList.add("over");
  });
  body.addEventListener("drop", e => {
    const g = e.target.closest(".gap");
    if (!g || drag == null) return;
    e.preventDefault();
    const a = drag.split(",").map(Number), from = a.pop(), fromList = a.join(","), toList = g.dataset.list;
    let to = +g.dataset.i;
    const inside = toList === drag || toList.startsWith(drag + ",");
    drag = null;
    if (inside) return redraw();
    const [blk] = listOf(fromList).splice(from, 1);
    if (fromList === toList && from < to) to--;
    listOf(fromList === toList || !toList.startsWith(fromList) ? toList : shift(toList, fromList, from)).splice(to, 0, blk);
    save();
  });
  body.addEventListener("dragend", () => { if (drag != null) { drag = null; redraw(); } });

  function escape() {
    if (!menu && !refOpen && !sure) return false;
    menu = refOpen = null;
    sure = false;
    redraw();
    return true;
  }

  return {draw, escape, group, settle};
})();

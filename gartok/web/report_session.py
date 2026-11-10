"""After a fight in the browser: the fallen on one page, the report with its blows in ink, each
level-up, then the field's loot or the arena's purse, then the map -- in the order `app_battle` played
them. It reads `campaign.absorb_battle`'s outcome (`aftermath.py`); the loot's moves are `spoils.Spoils`,
the purse lands whole on one fighter.

`campaign_fight` opens it once a campaign fight is settled."""

from types import SimpleNamespace
from typing import ClassVar

from .. import art_files, factions, i18n, item_icon, items, progression, world
from ..aftermath import card
from ..constants import fmt_money
from ..spoils import Spoils
from .map_session import _portrait, _when
from .session import Session, asset_url
from .shop_tab import SLOTS, _tip

LABELS = {k: f"report_session.label.{k}" for k in ("memorial", "report", "level", "loot", "purse", "map")}
CATEGORIES = (("coin", lambda d: items.is_coin(d.name)),
              ("weapons", lambda d: d.type == items.ItemType.WEAPON),
              ("armour", lambda d: d.type in (items.ItemType.ARMOR, items.ItemType.SHIELD)),
              ("other", lambda d: True))


def _face(race, pid):
    return asset_url(art_files.portrait_path(race, pid))


def _names_line(names):
    line = names[0] if names else ""
    for n in names[1:]:
        line = i18n.t("report_session.names_and", first=line, second=n)
    return line


def _foe_status(c):
    if c.captured:
        return "bound"
    if c.dead:
        return "fallen"
    if c.fled:
        return "fled"
    return "stable" if c.downed else "standing"


def _kg(v):
    return f"{v:.1f}".removesuffix(".0") + " kg"


class ReportSession(Session):
    screen = "report"
    labels: ClassVar[dict] = LABELS
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "next": lambda s, b: s.next(),
        "talents": lambda s, b: s.talents(),
        "take": lambda s, b: s.take(b.get("picks", []), b["to"], b.get("zone", "pack")),
        "auto": lambda s, b: s.auto(),
        "distribute": lambda s, b: s.distribute(),
        "give": lambda s, b: s.give(b["uid"]),
    }

    def __init__(self, map_session, group, battle, outcome, *, place=None, what=None, offer=None, then=None):
        self.map = map_session
        self.guild = map_session.guild
        self.group = group
        self.outcome = outcome
        self.place = place or ""
        self.what = what
        self.offer = offer
        self.then = then or map_session.back     # where the chain ends
        self.rounds = battle.round_no
        self.foes = list(battle.foe_units)
        self.bodies = {c.name: c for c in battle.units}
        self.day, self.at = _when(self.guild, 0)
        o = outcome
        stages = [("memorial", None)] if o.memorials else []
        if not o.campaign_over:
            stages.append(("report", None))
            stages += [("level", i) for i in range(len(o.level_ups))]
            if o.arena_reward is not None:
                stages.append(("purse", None))
            elif o.loot_pool and o.survivors:
                stages.append(("loot", None))
        self.stages = [*stages, ("map", None)]
        self.at_stage = 0
        self.loot = (Spoils(list(o.survivors), list(o.loot_pool))
                     if ("loot", None) in self.stages else None)
        self.taken = {}                          # uid -> {item: qty} taken off the field this screen
        self.refused = None                      # {"uid", "item", "why"}: the last drop that would not fit
        self.paid_to = None

    def sheet_units(self):
        return list(self.outcome.survivors)

    def tutorial_key(self):
        return {"memorial": "memorial", "report": "report", "level": "level_up", "purse": "reward",
                "loot": "loot"}.get(self.stage[0])

    @property
    def stage(self):
        return self.stages[self.at_stage]

    # ------------------------------------------------------------------ #
    # what the person does                                                #
    # ------------------------------------------------------------------ #
    def next(self):
        kind, _ = self.stage
        if kind == "purse" and self.paid_to is None:
            raise ValueError(i18n.t("report_session.someone_must_pocket_purse_first"))
        self.at_stage += 1
        self.refused = None
        if self.stage[0] == "map":
            return self.then()
        return self.state()

    def talents(self):
        from .talent_session import TalentSession
        kind, i = self.stage
        if kind != "level":
            raise ValueError(i18n.t("report_session.no_level_up_on_table"))
        unit = self.outcome.level_ups[i].unit
        if not unit.pending_picks:
            raise ValueError(i18n.t("report_session.has_no_talent_to_pick", name=unit.name))
        chain = []
        for c in self._chain():
            chain.append({**c, "at": "done"} if c["id"] == "level" else c)
            if c["id"] == "level":
                chain.append({"id": "talents", "label": i18n.lab("Talents"), "at": "now"})
        self.map.game.open(TalentSession(self.map, unit, self.outcome.survivors, self._resume,
                                         back_label=i18n.t("report_session.back_to_level_up"), chain=chain))
        return {"screen": TalentSession.screen}

    def _resume(self):
        self.map.game.open(self)
        return {"screen": self.screen, **self.state()}

    def _member(self, uid):
        u = next((u for u in self.outcome.survivors if u.uid == uid), None)
        if u is None:
            raise ValueError(i18n.t("report_session.no_such_member"))
        return u

    def _pick(self, b):
        """`(owner, loc)` for a field stack (`from: "field"`, `loc` its index), a pack row or a worn slot."""
        ls = self.loot
        if b["from"] == "field":
            loc = int(b["loc"])
            if not 0 <= loc < len(ls.pool):
                raise ValueError(i18n.t("report_session.no_such_stack_on_field"))
            owner = "pool"
            held = ls.pool[loc][1]
        else:
            owner, loc = self._member(b["from"]), b["loc"]
            if isinstance(loc, str):
                if loc not in dict(SLOTS) or ls._item_at(owner, loc) is None:
                    raise ValueError(i18n.t("report_session.nothing_in_that_slot", loc=loc))
                return owner, loc
            if not 0 <= loc < len(owner._base_inventory):
                raise ValueError(i18n.t("report_session.no_such_stack"))
            held = owner._base_inventory[loc][1]
        ls._sel_qty[(owner, loc)] = max(1, min(held, int(b.get("qty") or held)))
        return owner, loc

    def take(self, picks, to, zone="pack"):
        """Move `picks` onto `to` (a member's pack or worn `zone`, or back to the field), by
        `Spoils._give_many`; a load the member cannot carry is refused with why."""
        ls = self.loot
        if self.stage[0] != "loot" or ls is None:
            raise ValueError(i18n.t("report_session.field_is_not_on_table"))
        if zone not in ("pack", *dict(SLOTS)):
            raise ValueError(i18n.t("report_session.no_such_slot", zone=zone))
        ls.selected, ls._sel_qty = [], {}
        ls.selected = [self._pick(b) for b in picks]
        if not ls.selected:
            raise ValueError(i18n.t("report_session.nothing_picked"))
        if to == "field" and any(owner == "pool" for owner, _ in ls.selected):
            raise ValueError(i18n.t("report_session.that_is_on_field_already"))
        moving = [(ls._item_at(*p), ls._qty_at(*p), p[0]) for p in ls.selected]
        dst = "pool" if to == "field" else self._member(to)
        before = None if dst == "pool" else self._counts(dst)
        self.refused = None
        ls._give_many(dst, zone)
        ls.notice = None
        if dst != "pool" and ls.selected:        # `_give_many` keeps the picks when it refuses them
            self.refused = self._why(dst, zone, moving)
        elif dst != "pool":
            self._note_taken(dst, before, moving)
        else:
            for name, qty, owner in moving:
                got = self.taken.get(owner.uid, {})
                got[name] = max(0, got.get(name, 0) - qty)
        ls.selected, ls._sel_qty = [], {}
        return self.state()

    def _why(self, dst, zone, moving):
        name = moving[0][0]
        if zone != "pack" and not self.loot._fits_slot(dst, zone, name):
            size = items.get(name).size
            made_for_a_body = (zone == "armor" and items.is_armor(name)) or (zone == "offhand" and items.is_shield(name)) \
                or (zone in ("hand", "tongue") and items.is_weapon(name))
            if size is not None and made_for_a_body:
                return {"uid": dst.uid, "item": name, "why": i18n.t("report_session.wrong_size", name=dst.name, item=i18n.Ref("item", name),
                                                                     item_size=i18n.name("size", size), size=i18n.name("size", dst.size))}
            return {"uid": dst.uid, "item": name, "why": i18n.t("report_session.cannot_take_in_that_slot", name=dst.name, item=i18n.Ref("item", name))}
        add = sum(items.item_weight(n) * q for n, q, owner in moving if owner == "pool")
        what = i18n.t("report_session.s", name=name, kg=_kg(add)) if len(moving) == 1 else i18n.t("report_session.these", kg=_kg(add))
        return {"uid": dst.uid, "item": name,
                "why": i18n.t("report_session.already_carries_of_limit_would", name=dst.name, load=_kg(dst.load), limit=_kg(dst.carry_max), what=what, total=_kg(dst.load + add))}

    def _counts(self, u):
        out = {}
        for e in u._base_inventory:
            out[items.stack_name(e)] = out.get(items.stack_name(e), 0) + e[1]
        for zone, _ in SLOTS:
            name = self.loot._item_at(u, zone)
            if name:
                out[name] = out.get(name, 0) + 1
        return out

    def _note_taken(self, dst, before, moving):
        after = self._counts(dst)
        got = self.taken.setdefault(dst.uid, {})
        for name, _qty, owner in moving:
            if owner == "pool":
                got[name] = got.get(name, 0) + max(0, after.get(name, 0) - before.get(name, 0))

    def auto(self):
        ls = self.loot
        if self.stage[0] != "loot" or ls is None:
            raise ValueError(i18n.t("report_session.field_is_not_on_table"))
        before = {u.uid: self._counts(u) for u in ls.survivors}
        ls._auto_pick()
        for u in ls.survivors:
            after, got = self._counts(u), self.taken.setdefault(u.uid, {})
            for name, n in after.items():
                if n > before[u.uid].get(name, 0):
                    got[name] = got.get(name, 0) + n - before[u.uid].get(name, 0)
        self.refused = None
        return self.state()

    def distribute(self):
        """The packs evened out; what came off the field stays marked on whoever holds it now."""
        ls = self.loot
        if self.stage[0] != "loot" or ls is None:
            raise ValueError(i18n.t("report_session.field_is_not_on_table"))
        owed = {}
        for got in self.taken.values():
            for name, n in got.items():
                owed[name] = owed.get(name, 0) + n
        ls.distribute()
        self.taken = {}
        for u in ls.survivors:
            for name, held in self._counts(u).items():
                n = min(held, owed.get(name, 0))
                if n:
                    self.taken.setdefault(u.uid, {})[name] = n
                    owed[name] -= n
        self.refused = None
        return self.state()

    def give(self, uid):
        """The purse lands whole on one fighter."""
        if self.stage[0] != "purse":
            raise ValueError(i18n.t("report_session.there_is_no_purse_on"))
        if self.paid_to is not None:
            raise ValueError(i18n.t("report_session.already_pockets_purse", name=self.paid_to.name))
        u = self._member(uid)
        u.money += self.outcome.arena_reward
        self.paid_to = u
        self.map._save()
        return self.state()

    # ------------------------------------------------------------------ #
    # the screen                                                          #
    # ------------------------------------------------------------------ #
    def state(self):
        kind, i = self.stage
        out = {"stage": kind, "place": self.place, "what": self.what, "day": self.day, "at": self.at,
               "band": self.group.display_name, "rounds": self.rounds, "result": self.outcome.result,
               "chain": self._chain(), "steps": self._steps()}
        out[kind] = {"memorial": self._memorials, "report": self._report, "level": lambda: self._level(i),
                     "loot": self._loot, "purse": self._purse}[kind]()
        return out

    def _chain(self):
        """The screens in the order they come, one entry per kind (the level-ups are one)."""
        out = []
        for kind in dict.fromkeys(k for k, _ in self.stages):
            at = [n for n, (k, _) in enumerate(self.stages) if k == kind]
            out.append({"id": kind, "label": i18n.t(self.labels[kind]),
                        "at": "done" if self.at_stage > at[-1] else "now" if self.at_stage >= at[0] else "later"})
        return out

    def _steps(self):
        """What follows, one row per screen, as the report's leather panel reads it."""
        o, rows = self.outcome, []
        for n, (kind, i) in enumerate(self.stages):
            at = "done" if n < self.at_stage else "now" if n == self.at_stage else "later"
            faces = []
            if kind == "memorial":
                line = _names_line([m.name for m in o.memorials])
                title, line = i18n.t("report_session.fallen"), i18n.t("report_session.memorial_seen", names=line) if at == "done" else line
            elif kind == "report":
                title, line = i18n.t("report_session.report"), i18n.t("report_session.this_page") if at == "now" else i18n.t("report_session.who_stood_who_fell")
            elif kind == "level":
                lu = o.level_ups[i]
                track, level = lu.headline
                picks = len(lu.unit.pending_picks)
                title = i18n.t("report_session.reaches_level", name=lu.unit.name, lower=track.lower(), level=level)
                line = i18n.plural("report_session.number_rise", len(lu.gains))
                line += i18n.plural("report_session.talent_to_pick", picks) if picks else ""
                faces = [_portrait(lu.unit)]
            elif kind == "loot":
                stacks = self.loot.pool
                n_things = sum(q for _, q in stacks)
                weight = sum(items.item_weight(nm) * q for nm, q in stacks)
                title = i18n.t("report_session.field")
                line = (i18n.plural("report_session.stacks_take_what_packs", len(stacks), n_things=n_things, kg=_kg(weight)))
            elif kind == "purse":
                title, line = i18n.t("report_session.purse"), i18n.t("report_session.to_one_fighter", fmt_money=fmt_money(o.arena_reward))
            else:
                title, line = i18n.t("report_session.map"), i18n.t("report_session.goes_back_to_map", display_name=self.group.display_name)
            rows.append({"id": kind, "title": title, "line": line, "at": at, "faces": faces})
        return rows

    def _memorials(self):
        out = []
        for m in self.outcome.memorials:
            c = card(m)
            k = self.bodies.get(m.killer)
            c.update(portrait=_face(m.race, m.portrait_id), days_n=m.days_lived, joined=m.joined_day, died=m.day,
                     founder=m.joined_day <= 1,
                     killer=None if m.killer is None else {
                         "name": m.killer, "portrait": _portrait(k.char) if k is not None else None,
                         "caption": k.char.race_label if k is not None else "",
                         "foe": k is not None and k.team != "player"})
            c.pop("portrait_id", None)
            out.append(c)
        return out

    def _report(self):
        o, curve = self.outcome, progression.COMBAT_XP_THRESHOLDS
        rows = []
        for r in o.report:
            before, after = r.xp_before, r.xp_before + r.xp_gain
            into, span = progression.to_next(curve, after)
            was_into, was_span = progression.to_next(curve, before)
            rows.append({"name": r.name, "race": i18n.name("race", r.race), "portrait": _face(r.race, r.portrait_id), "status": r.status,
                         "downed": list(r.downed), "xp_gain": r.xp_gain, "magic_gain": r.magic_gain,
                         "level_before": curve.level(before), "level": curve.level(after),
                         "into": into, "span": span, "bar": into / span if span else 1.0,
                         "bar_before": was_into / was_span if was_span else 1.0})
        foes = [{"name": c.name, "race": c.char.race_label,                  "portrait": _portrait(c.char), "status": _foe_status(c), "level": c.char.racial_level}
                for c in self.foes]
        deeds = ([{"name": d.name, "blurb": d.blurb, "rep": d.rep, "faction": factions.faction(d.faction).name}
                  for d in o.deeds_earned] if o.arena_reward is None else [])
        hp = [{"name": u.name, "portrait": _portrait(u), "hp": u.hp, "hp_max": u.hp_max,
               "stable": next((r.status == "stable" for r in o.report if r.name == u.name), False)}
              for u in o.survivors]
        return {"rows": rows, "foes": foes, "takedowns": [list(t) for t in o.takedowns], "deeds": deeds,
                "hp": hp, "captives": list(o.captive_notes), "title_note": o.arena_title_event}

    def _level(self, i):
        o = self.outcome
        lu = o.level_ups[i]
        u = lu.unit
        track, level = lu.headline
        row = next((r for r in o.report if r.name == u.name), None)
        nxt = None
        if track == "COMBAT":
            into, span = progression.to_next(progression.COMBAT_XP_THRESHOLDS, u.combat_xp)
            nxt = [into, span]
        total = sum(1 for k, _ in self.stages if k == "level")
        return {"uid": u.uid, "name": u.name, "race": u.race_label,                 "portrait": _portrait(u), "track": track, "level": level,
                "tag": i18n.t("report_session.level_up") if total <= 1 else i18n.t("report_session.level_up_of", value=i + 1, total=total), "after": self._after(lu),
                "gains": [[label, a, b] for label, a, b in lu.gains], "next": nxt,
                "xp_gain": row.xp_gain if row else 0, "picks": len(u.pending_picks), "hp": [u.hp, u.hp_max]}

    def _after(self, lu):
        return i18n.t("report_session.fight_on", place=self.place)

    def _loot(self):
        ls = self.loot
        cats, seen = [], set()
        for cat, test in CATEGORIES:
            rows = []
            for idx, (name, qty) in enumerate(ls.pool):
                d = items.get(name)
                if idx in seen or d is None and cat != "other" or d is not None and not test(d):
                    continue
                seen.add(idx)
                rows.append({"loc": idx, "name": name, "qty": qty, "glyph": item_icon.glyph(name),
                             "kg": items.item_weight(name), "coin": items.COIN_VALUE.get(name, 0) * qty,
                             "tip": _tip(name)})
            if rows:
                cats.append({"label": i18n.t(f"report_session.cat.{cat}"), "rows": rows})
        return {"cats": cats, "stacks": len(ls.pool), "things": sum(q for _, q in ls.pool),
                "kg": round(sum(items.item_weight(n) * q for n, q in ls.pool), 2),
                "packs": [self._column(u) for u in ls.survivors], "refused": self.refused,
                "can_distribute": len(ls.survivors) > 1,
                "taken": [{"name": u.name, "items": [[n, q] for n, q in self.taken.get(u.uid, {}).items() if q > 0]}
                          for u in ls.survivors if any(q > 0 for q in self.taken.get(u.uid, {}).values())]}

    def _column(self, u):
        ls, got = self.loot, self.taken.get(u.uid, {})
        w = items.get(u.equipped_weapon)
        worn = []
        for zone, label in SLOTS:
            if zone == "offhand" and w and w.hands >= 2:
                continue
            if zone == "tongue" and not u.has_tongue:
                continue
            name = ls._item_at(u, zone)
            worn.append({"zone": zone, "label": i18n.lab(label), "name": name, "glyph": item_icon.glyph(name) if name else None,
                         "tip": _tip(name) if name else "", "new": int(bool(name and got.get(name))),
                         "kg": items.item_weight(name) if name else 0})
        pack = [{"loc": idx, "name": items.stack_name(e), "qty": e[1], "glyph": item_icon.glyph(items.stack_name(e)),
                 "kg": items.item_weight(items.stack_name(e)), "tip": _tip(items.stack_name(e)),
                 "new": got.get(items.stack_name(e), 0)} for idx, e in enumerate(u._base_inventory)]
        return {"uid": u.uid, "id": u.uid, "name": u.name, "portrait": _portrait(u), "money": u.money,
                "hurt": u.hp * 3 < u.hp_max, "sub": u.race_label, "hp": [u.hp, u.hp_max],
                "kg": round(u.load, 2), "normal": u.carry_normal, "max": u.carry_max, "worn": worn, "pack": pack}

    def _purse(self):
        o, offer = self.outcome, self.offer
        entry = getattr(offer, "entry", 0) or 0
        return {"amount": o.arena_reward, "entry": entry, "fighters": o.squad_size,
                "bout": getattr(offer, "name", "") or "", "paid_to": self.paid_to.uid if self.paid_to else None,
                "members": [{"uid": u.uid, "name": u.name, "sub": u.race_label,
                             "portrait": _portrait(u), "money": u.money} for u in o.survivors],
                "deeds": [{"name": d.name, "blurb": d.blurb, "rep": d.rep,
                           "faction": factions.faction(d.faction).name} for d in o.deeds_earned],
                "note": o.arena_title_event}


AFTER = {k: f"report_session.after.{k}" for k in ("WORK", "MAGIC", "COMBAT")}


class LevelUps(ReportSession):
    """The level-ups the clock brought (a work shift, a study), a page each as after a fight, then `then`
    (the map, or the work tab that ran the shift), as pygame's `_chain_level_ups` played them."""

    labels: ClassVar[dict] = {"level": "report_session.label.level", "map": "report_session.go_on"}

    def __init__(self, map_session, level_ups, then):
        self.map = map_session
        self.guild = map_session.guild
        self.outcome = SimpleNamespace(level_ups=list(level_ups), report=[],
                                       survivors=[lu.unit for lu in level_ups])
        self.then = then
        self.day, self.at = _when(self.guild, 0)
        self.stages = [*(("level", i) for i in range(len(level_ups))), ("map", None)]
        self.at_stage = 0

    def state(self):
        _, i = self.stage
        return {"stage": "level", "day": self.day, "at": self.at, "chain": self._chain(), "level": self._level(i)}

    def _after(self, lu):
        g = self.guild.group_of(lu.unit)
        where = world.node(g.node).name if g is not None and g.node else i18n.t("report_session.guild")
        return i18n.t(AFTER[lu.headline[0]], where=where)

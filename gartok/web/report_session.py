"""After a fight in the browser: the fallen on one page, the report with its blows in ink, each
level-up, then the field's loot or the arena's purse, then the map -- in the order `app_battle` played
them. It reads `campaign.absorb_battle`'s outcome (`aftermath.py`); the loot's moves are `spoils.Spoils`,
the purse lands whole on one fighter.

`campaign_fight` opens it once a campaign fight is settled."""

from typing import ClassVar

from .. import art_files, factions, item_icon, items, progression
from ..aftermath import card
from ..constants import fmt_money
from ..spoils import Spoils
from .map_session import _portrait, _when
from .session import Session, asset_url
from .shop_tab import SLOTS, _tip

LABELS = {"memorial": "The fallen", "report": "The report", "level": "Level up", "loot": "The field",
          "purse": "The purse", "map": "The map"}
CATEGORIES = (("Coin", lambda d: items.is_coin(d.name)),
              ("Weapons", lambda d: d.type == items.ItemType.WEAPON),
              ("Armour", lambda d: d.type in (items.ItemType.ARMOR, items.ItemType.SHIELD)),
              ("Everything else", lambda d: True))


def _face(race, pid):
    return asset_url(art_files.portrait_path(race, pid))


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
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "next": lambda s, b: s.next(),
        "talents": lambda s, b: s.talents(),
        "take": lambda s, b: s.take(b.get("picks", []), b["to"], b.get("zone", "pack")),
        "auto": lambda s, b: s.auto(),
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
            raise ValueError("someone must pocket the purse first")
        self.at_stage += 1
        self.refused = None
        if self.stage[0] == "map":
            return self.then()
        return self.state()

    def talents(self):
        from .talent_session import TalentSession
        kind, i = self.stage
        if kind != "level":
            raise ValueError("no level-up on the table")
        unit = self.outcome.level_ups[i].unit
        if not unit.pending_picks:
            raise ValueError(f"{unit.name} has no talent to pick")
        chain = []
        for c in self._chain():
            chain.append({**c, "at": "done"} if c["id"] == "level" else c)
            if c["id"] == "level":
                chain.append({"id": "talents", "label": "Talents", "at": "now"})
        self.map.game.open(TalentSession(self.map, unit, self.outcome.survivors, self._resume,
                                         back_label="Back to the level-up", chain=chain))
        return {"screen": TalentSession.screen}

    def _resume(self):
        self.map.game.open(self)
        return {"screen": self.screen, **self.state()}

    def _member(self, uid):
        u = next((u for u in self.outcome.survivors if u.uid == uid), None)
        if u is None:
            raise ValueError("no such member")
        return u

    def _pick(self, b):
        """`(owner, loc)` for a field stack (`from: "field"`, `loc` its index), a pack row or a worn slot."""
        ls = self.loot
        if b["from"] == "field":
            loc = int(b["loc"])
            if not 0 <= loc < len(ls.pool):
                raise ValueError("no such stack on the field")
            owner = "pool"
            held = ls.pool[loc][1]
        else:
            owner, loc = self._member(b["from"]), b["loc"]
            if isinstance(loc, str):
                if loc not in dict(SLOTS) or ls._item_at(owner, loc) is None:
                    raise ValueError(f"nothing in that {loc} slot")
                return owner, loc
            if not 0 <= loc < len(owner._base_inventory):
                raise ValueError("no such stack")
            held = owner._base_inventory[loc][1]
        ls._sel_qty[(owner, loc)] = max(1, min(held, int(b.get("qty") or held)))
        return owner, loc

    def take(self, picks, to, zone="pack"):
        """Move `picks` onto `to` (a member's pack or worn `zone`, or back to the field), by
        `Spoils._give_many`; a load the member cannot carry is refused with why."""
        ls = self.loot
        if self.stage[0] != "loot" or ls is None:
            raise ValueError("the field is not on the table")
        if zone not in ("pack", *dict(SLOTS)):
            raise ValueError(f"no such slot: {zone}")
        ls.selected, ls._sel_qty = [], {}
        ls.selected = [self._pick(b) for b in picks]
        if not ls.selected:
            raise ValueError("nothing picked")
        if to == "field" and any(owner == "pool" for owner, _ in ls.selected):
            raise ValueError("that is on the field already")
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
        if zone != "pack":
            return {"uid": dst.uid, "item": name, "why": f"{dst.name} cannot take the {name} in that slot."}
        add = sum(items.item_weight(n) * q for n, q, owner in moving if owner == "pool")
        what = f"the {name}'s {_kg(add)}" if len(moving) == 1 else f"these {_kg(add)}"
        return {"uid": dst.uid, "item": name,
                "why": f"{dst.name} already carries {_kg(dst.load)} of a {_kg(dst.carry_max)} limit; "
                       f"{what} would put them at {_kg(dst.load + add)}."}

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
            raise ValueError("the field is not on the table")
        before = {u.uid: self._counts(u) for u in ls.survivors}
        ls._auto_pick()
        for u in ls.survivors:
            after, got = self._counts(u), self.taken.setdefault(u.uid, {})
            for name, n in after.items():
                if n > before[u.uid].get(name, 0):
                    got[name] = got.get(name, 0) + n - before[u.uid].get(name, 0)
        self.refused = None
        return self.state()

    def give(self, uid):
        """The purse lands whole on one fighter."""
        if self.stage[0] != "purse":
            raise ValueError("there is no purse on the table")
        if self.paid_to is not None:
            raise ValueError(f"{self.paid_to.name} already pockets the purse")
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
            out.append({"id": kind, "label": LABELS[kind],
                        "at": "done" if self.at_stage > at[-1] else "now" if self.at_stage >= at[0] else "later"})
        return out

    def _steps(self):
        """What follows, one row per screen, as the report's leather panel reads it."""
        o, rows = self.outcome, []
        for n, (kind, i) in enumerate(self.stages):
            at = "done" if n < self.at_stage else "now" if n == self.at_stage else "later"
            faces = []
            if kind == "memorial":
                title, line = "The fallen", " and ".join(m.name for m in o.memorials)
                line += ", seen" if at == "done" else ""
            elif kind == "report":
                title, line = "The report", "this page" if at == "now" else "who stood, who fell"
            elif kind == "level":
                lu = o.level_ups[i]
                track, level = lu.headline
                picks = len(lu.unit.pending_picks)
                title = f"{lu.unit.name} reaches {track.lower()} level {level}"
                line = f"{len(lu.gains)} number{'s' if len(lu.gains) != 1 else ''} rise"
                line += f", {picks} talent{'s' if picks != 1 else ''} to pick" if picks else ""
                faces = [_portrait(lu.unit)]
            elif kind == "loot":
                stacks = self.loot.pool
                n_things = sum(q for _, q in stacks)
                weight = sum(items.item_weight(nm) * q for nm, q in stacks)
                title = "The field"
                line = (f"{len(stacks)} stack{'s' if len(stacks) != 1 else ''}, {n_things} things, {_kg(weight)}: "
                        "take what the packs can carry")
            elif kind == "purse":
                title, line = "The purse", f"{fmt_money(o.arena_reward)} to one fighter"
            else:
                title, line = "The map", f"{self.group.display_name} goes back to the map"
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
                         "caption": f"{k.char.race['name']} {k.char.occupation['name']}" if k is not None else "",
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
            rows.append({"name": r.name, "race": r.race, "portrait": _face(r.race, r.portrait_id), "status": r.status,
                         "downed": list(r.downed), "xp_gain": r.xp_gain, "magic_gain": r.magic_gain,
                         "level_before": curve.level(before), "level": curve.level(after),
                         "into": into, "span": span, "bar": into / span if span else 1.0,
                         "bar_before": was_into / was_span if was_span else 1.0})
        foes = [{"name": c.name, "race": c.char.race["name"], "occupation": c.char.occupation["name"],
                 "portrait": _portrait(c.char), "status": _foe_status(c), "level": c.char.racial_level}
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
        return {"uid": u.uid, "name": u.name, "race": u.race["name"], "occupation": u.occupation["name"],
                "portrait": _portrait(u), "track": track, "level": level,
                "tag": "Level up" if total <= 1 else f"Level up · {i + 1} of {total}",
                "gains": [[label, a, b] for label, a, b in lu.gains], "next": nxt,
                "xp_gain": row.xp_gain if row else 0, "picks": len(u.pending_picks), "hp": [u.hp, u.hp_max]}

    def _loot(self):
        ls = self.loot
        cats, seen = [], set()
        for label, test in CATEGORIES:
            rows = []
            for idx, (name, qty) in enumerate(ls.pool):
                d = items.get(name)
                if idx in seen or d is None and label != "Everything else" or d is not None and not test(d):
                    continue
                seen.add(idx)
                rows.append({"loc": idx, "name": name, "qty": qty, "glyph": item_icon.glyph(name),
                             "kg": items.item_weight(name), "coin": items.COIN_VALUE.get(name, 0) * qty,
                             "tip": _tip(name)})
            if rows:
                cats.append({"label": label, "rows": rows})
        return {"cats": cats, "stacks": len(ls.pool), "things": sum(q for _, q in ls.pool),
                "kg": round(sum(items.item_weight(n) * q for n, q in ls.pool), 2),
                "packs": [self._column(u) for u in ls.survivors], "refused": self.refused,
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
            worn.append({"zone": zone, "label": label, "name": name, "glyph": item_icon.glyph(name) if name else None,
                         "tip": _tip(name) if name else "", "new": bool(name and got.get(name))})
        pack = [{"loc": idx, "name": items.stack_name(e), "qty": e[1], "glyph": item_icon.glyph(items.stack_name(e)),
                 "kg": items.item_weight(items.stack_name(e)), "tip": _tip(items.stack_name(e)),
                 "new": got.get(items.stack_name(e), 0)} for idx, e in enumerate(u._base_inventory)]
        return {"uid": u.uid, "name": u.name, "portrait": _portrait(u),
                "sub": f"{u.race['name']} · {u.occupation['name']}", "hp": [u.hp, u.hp_max],
                "kg": round(u.load, 2), "normal": u.carry_normal, "max": u.carry_max, "worn": worn, "pack": pack}

    def _purse(self):
        o, offer = self.outcome, self.offer
        entry = getattr(offer, "entry", 0) or 0
        return {"amount": o.arena_reward, "entry": entry, "fighters": o.squad_size,
                "bout": getattr(offer, "name", "") or "", "paid_to": self.paid_to.uid if self.paid_to else None,
                "members": [{"uid": u.uid, "name": u.name, "sub": f"{u.race['name']} · {u.occupation['name']}",
                             "portrait": _portrait(u), "money": u.money} for u in o.survivors],
                "deeds": [{"name": d.name, "blurb": d.blurb, "rep": d.rep,
                           "faction": factions.faction(d.faction).name} for d in o.deeds_earned],
                "note": o.arena_title_event}

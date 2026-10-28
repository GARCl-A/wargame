"""The guild's sheet in the browser: one screen with four tabs, after references/sheets_mockup/.

    MEMBERS      the roster by band, the picked member's character sheet and what can be done for them
    BANDS        one band at a time: each member's kit as a column, the animals, the wagons, the jobs
                 in hand and the captives; an item moves only inside the band, so no trade crosses places
    THE GUILD    the charter (founding trade, fame and band slots, standing, the bands, the notices)
                 and the holdings
    REPUTATIONS  the objectives and each known faction's deeds and unlocks

The reads and the rules are pygame's own: `GuildScreen` for the roster, the sheet, the roles, the charter
and the reputations, `GroupScreen` for the band's kit (the moves, the item menu, the wagon and the herd),
both held headless as the hub's tabs hold theirs, until step 10 of `docs/plans/web_frontend.md`.
"""

from typing import ClassVar

from .. import (
    artwork,
    data,
    factions,
    item_icon,
    items,
    missions,
    objectives,
    store_column,
    talents,
)
from .. import wagon as wagon_mod
from ..animals import Animal
from ..combatant import Combatant
from ..constants import fmt_money
from ..group_screen import GroupScreen
from ..guild_screen import (
    ATTRIBUTE_LABELS,
    FIGHT_DUE_TIP,
    FILTERS,
    GuildScreen,
    _needs_attention,
    _node_label,
)
from ..ui.inspector_panel import role_for
from ..ui.sheet_card import unit_to_ch
from ..ui.tokens import T
from .map_session import _icon, _portrait
from .session import Session
from .stable_tab import WAGON_GLYPH, _face

TABS = (("members", "Members"), ("bands", "Bands"), ("guild", "The Guild"), ("reputations", "Reputations"))
TONES = {T.BRASS: "warn", T.BLOOD: "bad", T.GREEN: "good"}
ZONES = ("pack", "hand", "offhand", "tongue", "artifact", "armor", "tack", "hitch")
WORN = (("hand", "Hand"), ("offhand", "Hand"), ("tongue", "Tongue"), ("armor", "Body"), ("artifact", "Artifact"))


def _breakdown(title, terms, total):
    lines = [title] + [f"{label}: {v}" if i == 0 else f"{label}: {v:+}" for i, (label, v) in enumerate(terms)]
    return "\n".join([*lines, f"= {total}"])


def _hp_tip(u):
    b = u.hp_breakdown()
    lines = [f"{b['hit_dice']} hit dice of d{b['hd']}: {b['dice_sum']}", f"CON {b['con_total']:+}"]
    if b["talent_total"]:
        lines.append(f"Talents {b['talent_total']:+}")
    if b["ability_bonus"]:
        lines.append(f"{b['ability_name']} {b['ability_bonus']:+}")
    if b["starving"]:
        lines.append("Starving: held at 1")
    return "\n".join([*lines, f"= {b['final_max']}"])


def _tip(name):
    return "\n".join(items.item_tooltip(name))


class GuildSession(Session):
    screen = "guild"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "tab": lambda s, b: s.pick_tab(b["key"]),
        "member": lambda s, b: s.pick_member(b["uid"]),
        "filter": lambda s, b: s.set_filter(b["mode"]),
        "fold": lambda s, b: s.fold(b["gid"]),
        "role": lambda s, b: s.role(b["key"]),
        "talents": lambda s, b: s.talents(),
        "band": lambda s, b: s.pick_band(b["gid"]),
        "rename": lambda s, b: s.rename(b.get("name", "")),
        "move": lambda s, b: s.move(b["picks"], b["to"], b.get("zone", "pack")),
        "menu": lambda s, b: s.menu(b["pick"]),
        "menu_run": lambda s, b: s.menu_run(b["pick"], int(b["row"])),
        "split": lambda s, b: s.split(b["pick"], int(b["qty"])),
        "lock": lambda s, b: s.lock(b["owner"], b["name"]),
        "button": lambda s, b: s.button(b["key"]),
        "back": lambda s, b: s.map.back(),
    }

    def __init__(self, map_session, tab="members", gid=None):
        self.map = map_session
        self.guild = map_session.guild
        self.sheet = GuildScreen(None, self.guild, on_back=lambda: None)
        self.tab = tab
        self.notice = None
        self.gear = None
        self._set_band(gid or self._default_band())
        if tab == "bands" and self.gear.group.members:
            self.sheet.member = self.gear.group.members[0]

    # ------------------------------------------------------------------ #
    # the frame                                                           #
    # ------------------------------------------------------------------ #
    def _default_band(self):
        g = self.sheet._group_of(self.sheet.member) if self.sheet.member is not None else None
        return (g or self.guild.groups[0]).gid

    def state(self):
        g = self.guild
        notice, self.notice = self.notice, None
        if self.gear is not None and self.gear.notice:
            notice, self.gear.notice = self.gear.notice, None
        pending = sum(1 for u in g.roster if u.pending_picks)
        alerts = sum(1 for u in self.sheet._everyone() if self._alert(u))
        out = {
            "name": g.name or "The Guild",
            "banner": list(g.banner_color) if g.banner_color else None,
            "emblem": _icon(next(((c, s) for c, s, _ in artwork.BANNER_ICONS if s == g.banner_icon), None)),
            "day": g.clock.day, "won": g.battles_won, "count": len(g.roster),
            "band_count": len([gr for gr in g.groups if not gr.empty]), "pending": pending,
            "tabs": [{"key": k, "label": label, "badge": pending if k == "members" and pending else 0}
                     for k, label in TABS],
            "tab": self.tab, "alerts": alerts, "notice": notice,
        }
        out[self.tab] = {"members": self._members, "bands": self._bands, "guild": self._charter,
                         "reputations": self._reputations}[self.tab]()
        return out

    def pick_tab(self, key):
        if key not in dict(TABS):
            raise ValueError(f"no such tab: {key}")
        self.tab = key
        return self.state()

    # ------------------------------------------------------------------ #
    # MEMBERS                                                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _alert(u):
        return bool(u.unfed_days) if isinstance(u, Animal) else _needs_attention(u)

    def _row(self, d, u):
        hurt = u.hp < u.hp_max
        return {"uid": d["key"], "name": d["name"], "sub": d["sub"], "selected": d["selected"],
                "hp": list(d["hp"]), "hurt": hurt, "beast": isinstance(u, Animal),
                "portrait": _face(u.species, u.uid) if isinstance(u, Animal) else _portrait(u),
                "badges": [{"text": t.lower(), "tone": TONES.get(c, "")} for t, c in d["badges"]]}

    def _members(self):
        s = self.sheet
        if s.member not in s._everyone():
            s.member = s.roster[0] if s.roster else None
        by_uid = {u.uid: u for u in s._everyone()}
        bands = [{"gid": b["key"], "name": b["name"], "where": b["where"], "task": self._task(b["key"]),
                  "folded": b["collapsed"], "count": b["count"],
                  "rows": [self._row(d, by_uid[d["key"]]) for d in b["members"]]} for b in s._roster_bands()]
        m = s.member
        return {"filters": [{"mode": k, "label": label.title(), "tip": tip} for k, label, tip in FILTERS],
                "filter": s.filter_mode, "roster": bands,
                "slots": [len(self.guild.groups), self.guild.group_slots],
                "sheet": None if m is None else self._animal_sheet(m) if isinstance(m, Animal) else self._sheet(m)}

    def _task(self, gid):
        return self.map._chip(self.map._group(gid))[0]

    def pick_member(self, uid):
        u = next((u for u in self.sheet._everyone() if u.uid == uid), None)
        if u is None:
            raise ValueError("no such member")
        self.sheet.member = u
        return self.state()

    def set_filter(self, mode):
        if mode not in {k for k, _, _ in FILTERS}:
            raise ValueError(f"no such filter: {mode}")
        self.sheet.filter_mode = mode
        return self.state()

    def fold(self, gid):
        self.sheet.collapsed_groups ^= {gid}
        return self.state()

    def _sheet(self, u):
        s, g = self.sheet, self.guild
        c = Combatant(u)
        ch = unit_to_ch(c)
        grp = g.group_of(u)
        w = ch["weapon"]
        weapon = s._weapon_data(u, c, ch)
        gear = s._gear_data(u, c)
        load = gear["load"]
        rations, autotroph = gear["rations"]
        return {
            "uid": u.uid, "name": u.name, "portrait": _portrait(u), "race": u.race["name"],
            "occ": u.occupation["name"], "age": u.age, "align": u.alignment.capitalize(),
            "band": grp.display_name if grp else None, "gid": grp.gid if grp else None,
            "where": _node_label(grp.node) if grp else "Camp",
            "task": self._task(grp.gid) if grp else "no orders",
            "stamps": ([{"text": "Guild leader", "tone": "leader"}] if u is g.leader else [])
                      + ([{"text": "Leads the band", "tone": "leader"}]
                         if u is not g.leader and s._is_group_leader(u) else [])
                      + ([{"text": "Champion of the Pit", "tone": ""}] if getattr(u, "arena_title", False) else []),
            "status": ch["status"],
            "hungry": u.hunger_level > 0,
            "attrs": [{"k": k, "v": v, "mod": mod, "low": low} for k, v, mod, low in ch["attrs"]],
            "hp": list(ch["hp"]), "hp_tip": _hp_tip(u),
            "stats": [{"k": "AC", "v": ch["ac"], "tip": _breakdown("Armour class", u.ac_breakdown(), c.ac)},
                      {"k": "MD", "v": ch["md"], "tip": _breakdown("Mental defense", u.md_breakdown(),
                                                                   c.mental_defense)},
                      {"k": "SPD", "v": ch["spd"], "tip": _breakdown("Speed (squares)", u.speed_breakdown(), c.speed)},
                      {"k": "INIT", "v": ch["init"], "tip": _breakdown("Initiative", u.initiative_breakdown(),
                                                                       ch["init"])}],
            "weapon": {"name": weapon["name"], "tags": weapon["tags"], "crit": w["crit"], "action": w["action"],
                       "glyph": item_icon.glyph(u.equipped_weapon) if u.equipped_weapon else "item/knapsack",
                       "chips": [{"k": k, "v": v, "tip": t} for k, v, t in weapon["chips"]]},
            "kit": [{"k": "Hands", "v": gear["hands"], "note": ""},
                    {"k": "Body", "v": gear["armor"], "note": gear["armor_note"]},
                    {"k": "Purse", "v": fmt_money(gear["coins"]), "note": ""},
                    {"k": "Rations", "v": "Feeds on light" if autotroph else str(rations or "None"),
                     "note": "" if autotroph else "days of food" if rations else "nothing to eat in the pack",
                     "bad": not autotroph and not rations},
                    {"k": "Load", "v": f"{load[0]:.1f} kg",
                     "note": f"of {load[1]:g} at a normal pace, {load[2]:g} at most", "bad": load[0] > load[1]}],
            "ability": list(ch["ability"]), "langs": ch["langs"],
            "racial": u.racial_level,
            "tracks": [{"label": t["label"], "value": t["value"], "frac": t["frac"], "text": t["text"],
                        "tip": t["tip"]} for t in s._tracks(u)],
            "talents": [{"name": n, "desc": d} for n, d in self._talents(u)],
            "record": self._record(u),
            "picks": len(u.pending_picks),
            "roles": [self._role(r) for r in s._role_rows(u, grp)],
            "locked": bool(grp and grp.fight_due),
        }

    @staticmethod
    def _talents(u):
        return [(talents.get(t).name if talents.get(t) else t.title(), talents.get(t).desc if talents.get(t) else "")
                for track in talents.TRACKS for t in u.talents.get(track, [])]

    def _record(self, u):
        s = self.sheet
        who = s._recruited_by(u)
        out = [f"Recruited by {who}." if who else "A founding member of the guild.",
               s._sponsor_line(u)[0].replace(" -- ", ": ") + "."]
        if getattr(u, "arena_title", False):
            out.append("Holds the title Champion of the Pit.")
        if getattr(u, "bio", ""):
            out.append(u.bio)
        return out

    @staticmethod
    def _role(r):
        act = r["action"]
        return {"key": r["key"], "title": r["title"].replace("★ ", ""), "sub": r["sub"].replace(" -- ", ": "),
                "current": bool(r["badge"]), "tip": r["tip"],
                "action": None if act is None else {"label": act[0].capitalize(), "on": act[1]}}

    def _animal_sheet(self, a):
        s = self.sheet
        grp = s._group_of(a)
        pulled = grp.pulling(a) if grp else None
        return {
            "uid": a.uid, "beast": True, "name": a.species, "portrait": _face(a.species, a.uid),
            "sub": f"{a.size} animal", "band": grp.display_name if grp else None, "gid": grp.gid if grp else None,
            "where": _node_label(grp.node) if grp else "Camp",
            "hp": [max(0, a.hp), a.hp_max],
            "attrs": [{"k": k, "v": a.attributes[n], "mod": data.mod(a.attributes[n]), "low": False}
                      for k, n in ATTRIBUTE_LABELS],
            "speed": f"{a.speed:g} m",
            "ability": [a.ability.name, a.ability.effect] if a.race["ability"] else None,
            "work": [{"k": k.title(), "v": v, "tone": TONES.get(c, "")} for k, v, c in s._animal_work_rows(a, pulled)],
        }

    def role(self, key):
        s = self.sheet
        rows = {r["key"]: r for r in s._role_rows(s.member, s._group_of(s.member))} \
            if s.member is not None and not isinstance(s.member, Animal) else {}
        row = rows.get(key)
        if row is None or row["action"] is None or not row["action"][1]:
            raise ValueError(row["tip"] if row else "no such role")
        s._press(key)
        self.map._save()
        return self.state()

    def talents(self):
        """The talent tree is its own screen, still pygame's: the away card says so and comes back here."""
        from .away_session import AwaySession
        m = self.sheet.member
        if m is None or isinstance(m, Animal):
            raise ValueError("pick a member first")
        self.map.game.open(AwaySession(self.map, self.guild.group_of(m), None, title="The talent tree",
                                       what=f"{m.name}'s talent tree", resume=self._resume))
        return {"screen": AwaySession.screen}

    def _resume(self):
        self.map.game.open(self)
        return {"screen": self.screen, **self.state()}

    # ------------------------------------------------------------------ #
    # BANDS                                                               #
    # ------------------------------------------------------------------ #
    def _set_band(self, gid):
        g = next((g for g in self.guild.groups if g.gid == gid and not g.empty), None)
        if g is None:
            raise ValueError("no such band")
        self.gear = GroupScreen(None, self.guild, g, on_back=lambda: None, on_tick=self.map.tick_outside)

    def pick_band(self, gid):
        self._set_band(gid)
        self.tab = "bands"
        return self.state()

    @property
    def group(self):
        return self.gear.group

    def _check_free(self):
        if self.group.fight_due:
            raise ValueError(FIGHT_DUE_TIP)

    def _item(self, owner, loc, name, qty):
        return {"loc": loc, "name": name, "qty": qty, "glyph": item_icon.glyph(name), "kg": items.item_weight(name),
                "coin": items.is_coin(name), "locked": owner.locked_of(name) > 0, "tip": _tip(name)}

    def _pack(self, owner):
        return [self._item(owner, i, items.stack_name(e), e[1]) for i, e in enumerate(owner._base_inventory)]

    def _column(self, u):
        g, gear = self.group, self.gear
        w = items.get(u.equipped_weapon)
        worn = []
        for zone, label in WORN:
            if (zone == "offhand" and w and w.hands >= 2) or (zone == "tongue" and not u.has_tongue):
                continue
            name = gear._item_at(u, zone)
            worn.append({"zone": zone, "label": label, "name": name,
                         "glyph": item_icon.glyph(name) if name else None,
                         "kg": items.item_weight(name) if name else 0, "tip": _tip(name) if name else ""})
        ride = None
        if g.wagons:
            riding = u in g.riders
            ride = {"label": "Rides" if riding else "Walks", "on": riding or u.afoot,
                    "tip": "Make them walk" if riding else "Let them ride" if u.afoot else "No room on the wagons"}
        hunger = u.hunger_level > 0
        return {"id": u.uid, "name": u.name, "portrait": _portrait(u), "store": False,
                "sub": f"{u.race['name']} {u.occupation['name']}", "role": role_for(u.occupation),
                "lead": u is g.leader, "hurt": u.hp < u.hp_max, "hungry": hunger,
                "money": u.money, "kg": round(u.load, 2), "normal": u.carry_normal, "max": u.carry_max,
                "worn": worn, "pack": self._pack(u), "ride": ride}

    def _animal_column(self, a):
        g = self.group
        pulled = g.pulling(a)
        job = f"pulls the {pulled.kind.lower()}" if pulled else "unhitched" if a.role == "draft" else a.role or "no tack"
        return {"id": a.uid, "name": a.species, "portrait": _face(a.species, a.uid), "store": True, "beast": True,
                "sub": job, "hungry": bool(a.unfed_days), "unfed": a.unfed_days,
                "money": a.money, "kg": round(a.load, 2), "normal": a.carry_normal, "max": a.carry_max,
                "worn": [{"zone": "tack", "label": "Tack", "name": a.tack,
                          "glyph": item_icon.glyph(a.tack) if a.tack else None,
                          "kg": items.item_weight(a.tack) if a.tack else 0, "tip": _tip(a.tack) if a.tack else ""}],
                "pack": self._pack(a),
                "hitch": ({"label": f"Pulls the {pulled.kind.lower()}" if pulled else "Hitch it", "on": True}
                          if a.role == "draft" and g.wagons else None)}

    def _wagon(self, w):
        g = self.group
        have = sum(u.count_of(wagon_mod.REPAIR_ITEM) for u in g.members)
        return {"id": w.uid, "name": w.kind, "glyph": WAGON_GLYPH, "hp": [w.hp, w.hp_max], "broken": w.broken,
                "drawn": [{"uid": a.uid, "name": a.species, "portrait": _face(a.species, a.uid), "tack": a.tack,
                           "unfed": a.unfed_days} for a in w.draft],
                "riders": [u.name for u in w.passengers],
                "kg": round(w.load + w.passenger_weight, 2), "budget": w.budget, "free": round(w.stash.free, 2),
                "pack": self._pack(w),
                "repair": ({"cost": w.repair_cost, "item": wagon_mod.REPAIR_ITEM, "hours": wagon_mod.REPAIR_HOURS,
                            "on": have >= w.repair_cost} if w.needs_repair else None)}

    def _jobs(self):
        g = self.group
        uids = {u.uid: u for u in g.members}
        out = []
        for m in self.guild.missions:
            if m.state != "active" or m.unit_uid not in uids:
                continue
            t = missions.template_of(m)
            out.append({"name": t.name, "by": uids[m.unit_uid].name, "days": missions.days_left(self.guild, m),
                        "progress": [missions.progress(self.guild, m), t.goal_qty, t.goal_item] if t.goal_qty > 0
                        else None})
        return out

    def _actions(self):
        g, gear, now = self.group, self.gear, self.guild.clock.seconds
        out = [{"key": "distribute", "label": "Distribute", "glyph": "action/rally-the-troops",
                "on": len(g.members) > 1, "tip": "Share the unlocked pack items out by what each can carry"}]
        if gear._can_treat_sickness():
            out.append({"key": "treat_sickness", "label": "Treat sickness", "glyph": "body/arm-bandage", "on": True,
                        "tip": "A bandmate with a first-aid kit tends the sick"})
        if gear._can_treat_poison():
            out.append({"key": "treat_poison", "label": "Use antidote", "glyph": "action/drinking", "on": True,
                        "tip": "A bandmate's Antidote for the poisoned"})
        lit = g.has_campfire(now)
        out.append({"key": "campfire_cook", "label": f"Campfire ({g.campfire_hours_left(now):g} h)" if lit else "Campfire",
                    "glyph": "action/kindle", "on": lit or g.can_light_campfire(),
                    "tip": "Cook at the band's fire" if lit
                    else "Light a fire to cook: Flint and Steel, 1 Lumber and 1 Coal" if g.can_light_campfire()
                    else "A campfire needs Flint and Steel, 1 Lumber and 1 Coal in the packs"})
        return out

    def _chip(self, g):
        return {"gid": g.gid, "name": g.display_name, "where": _node_label(g.node), "task": self._task(g.gid),
                "size": len(g.members), "capacity": g.capacity, "faces": [_portrait(u) for u in g.members[:4]],
                "locked": g.fight_due}

    def _bands(self):
        g = self.group
        if g.empty or g not in self.guild.groups:
            self._set_band(self.guild.groups[0].gid)
            g = self.group
        today = self.guild.clock.day
        return {
            "chips": [self._chip(gr) for gr in self.guild.groups if not gr.empty],
            "gid": g.gid, "name": g.display_name, "custom": g.name or "",
            "locked": g.fight_due, "lock_tip": FIGHT_DUE_TIP if g.fight_due else "",
            "load": [round(g.total_load, 1), g.total_carry_normal, g.total_carry_max],
            "rations": g.rations_days, "speed": f"{g.speed:g} m",
            "over": g.overextension,
            "actions": self._actions(),
            "packs": [*(self._column(u) for u in g.members), *(self._animal_column(a) for a in g.herd)],
            "wagons": [self._wagon(w) for w in g.wagons],
            "jobs": self._jobs(),
            "captives": [{"uid": c.unit.uid, "name": c.name, "race": c.unit.race["name"], "days": c.days_left(today)}
                         for c in g.captives],
        }

    def rename(self, name):
        self.group.name = name.strip()[:24] or None
        self.map._save()
        return self.state()

    def _owner(self, oid):
        o = self.gear._owners_by_uid().get(oid)
        if o is None:
            raise ValueError("no such pack in this band")
        return o

    def _pick(self, b):
        owner, loc = self._owner(b["from"]), b["loc"]
        if isinstance(loc, str):
            if loc not in dict(WORN) and loc not in ("tack", "hitch"):
                raise ValueError(f"no such slot: {loc}")
            if loc == "hitch" and not isinstance(owner, Animal):
                raise ValueError("only an animal is hitched")
            if loc != "hitch" and self.gear._item_at(owner, loc) is None:
                raise ValueError(f"nothing in that {loc} slot")
        elif not 0 <= loc < len(owner._base_inventory):
            raise ValueError("no such stack")
        return owner, loc

    def move(self, picks, to, zone="pack"):
        self._check_free()
        if zone not in ZONES:
            raise ValueError(f"no such slot: {zone}")
        gear = self.gear
        gear.selected = [self._pick(p) for p in picks]
        gear._unit_by_uid = gear._owners_by_uid()
        gear._give_many(self._owner(to), zone)
        if gear.selected and zone != "pack":
            gear.selected = []
            raise ValueError("that does not fit there")
        gear.selected = []
        return self.state()

    def _menu_rows(self, pick):
        gear = self.gear
        gear._unit_by_uid = gear._owners_by_uid()
        p = self._pick(pick)
        return p, gear._menu_rows([p])

    def menu(self, pick):
        self._check_free()
        (owner, loc), rows = self._menu_rows(pick)
        dests = {o.uid: o for o in self.gear._owners()}
        out = []
        for i, (kind, label, arg) in enumerate(rows):
            row = {"row": i, "kind": kind, "label": label[0].upper() + label[1:].lower() if label.isupper() else label}
            if kind == "member":
                o = dests[arg]
                row["label"] = f"to {o.name}"
                row["free"] = round(o.stash.free if store_column.is_store(o) else o.carry_normal - o.load, 1)
            out.append(row)
        split = self.gear._splittable((owner, loc))
        return {"rows": out, "held": owner._base_inventory[loc][1] if split else 0,
                "lockable": isinstance(loc, int), "locked": isinstance(loc, int)
                and owner.locked_of(owner._base_inventory[loc][0]) > 0}

    def menu_run(self, pick, row):
        self._check_free()
        p, rows = self._menu_rows(pick)
        if not 0 <= row < len(rows):
            raise ValueError("no such choice")
        kind, _, arg = rows[row]
        self.gear._menu_run([p], kind, arg)
        self.gear.selected = []
        self.map._save()
        return self.state()

    def split(self, pick, qty):
        self._check_free()
        owner, loc = self._pick(pick)
        if self.gear._splittable((owner, loc)) is None or not owner.split_pack(loc, qty):
            raise ValueError("that stack will not split so")
        self.notice = f"split {qty} {owner._base_inventory[loc][0]} into a stack of their own"
        return self.state()

    def lock(self, oid, name):
        self._owner(oid).toggle_lock(name)
        return self.state()

    def button(self, key):
        self._check_free()
        g, gear = self.group, self.gear
        kind, _, uid = key.partition(":")
        if kind in ("ride", "hitch", "repair", "release"):
            known = {"ride": g.members, "hitch": g.herd, "repair": g.wagons}.get(kind)
            if known is not None and not any(x.uid == uid for x in known):
                raise ValueError("nothing by that id in this band")
            if kind == "release" and not any(c.unit.uid == uid for c in g.captives):
                raise ValueError("no such captive")
            if kind == "ride":
                u = next(x for x in g.members if x.uid == uid)
                if u not in g.riders and not u.afoot:
                    raise ValueError("no room on the wagons")
        elif key == "campfire_cook":
            return self.map.act(g.gid, "campfire_cook")
        elif key not in {a["key"] for a in self._actions() if a["on"]}:
            raise ValueError("that cannot be done now")
        gear._unit_by_uid = gear._owners_by_uid()
        gear._handle_button(key)
        if self.map.wiped or g.empty:
            self.map.game.open(self.map)
            return self.map._land()
        self.map._save()
        return self.state()

    # ------------------------------------------------------------------ #
    # THE GUILD                                                           #
    # ------------------------------------------------------------------ #
    def _charter(self):
        g, s = self.guild, self.sheet
        known = factions.known(g)
        bank = g.bank
        holds = s._holdings()
        for h in holds:
            if h["name"] == "Strongbox" and bank.open:
                h["load"] = [round(bank.load, 1), bank.capacity]
                h["inside"] = [{"name": items.stack_name(e), "qty": e[1], "glyph": item_icon.glyph(items.stack_name(e))}
                               for e in bank.items]
        return {
            "vocation": s._vocation() and {k: v for k, v in s._vocation().items() if k != "icon"},
            "fame": g.fame, "fame_next": g.fame_to_next_slot, "slots": [len(g.groups), g.group_slots],
            "standing": [{"name": f.name, "rep": g.reputation.get(f.id, 0)} for f in known],
            "groups": [{**r, "gid": gr.gid, "task": self._task(gr.gid).capitalize()}
                       for r, gr in zip(s._group_rows(), g.groups)],
            "notices": [{"text": t.replace(" -- ", ": "), "tone": tone} for t, tone in s._notices()],
            "holdings": holds,
        }

    # ------------------------------------------------------------------ #
    # REPUTATIONS                                                         #
    # ------------------------------------------------------------------ #
    def _reputations(self):
        g = self.guild
        done = set(g.deeds_done)
        card = objectives.card_data(g)
        n, total = card["rep"].split("/")
        return {
            "objectives": {"done": int(n), "total": int(total), "blurb": card["blurb"].replace(" -- ", ": "),
                           "rows": [{"name": nm, "blurb": b, "done": st == "done"} for nm, b, _, st in card["deeds"]]},
            "factions": [{"name": f.name, "blurb": f.blurb, "rep": g.reputation.get(f.id, 0),
                          "deeds": [{"name": d.name, "blurb": d.blurb, "rep": d.rep,
                                     "state": "done" if d.id in done else "failed" if factions.failed(g, d) else "open"}
                                    for d in factions.DEEDS_BY_FACTION[f.id]],
                          "unlocks": [{"title": u.title, "text": u.description, "open": g.reputation.get(f.id, 0)
                                       >= u.rep_required, "need": u.rep_required} for u in factions.get_unlocks(f.id)]}
                         for f in factions.known(g)],
        }

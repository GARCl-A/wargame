"""The Tavern's three tabs in the browser: RECRUIT (the strangers drinking here on leather, the picked
one's dossier and who makes the pitch on paper), STUDY (the rooms to rent and each member's study
target) and PERFORM (the stage: the show's length and who plays); the City Prison's cells are RECRUIT
with a bail paid before the pitch (`PrisonScreen`).

The rules are pygame's own `TavernaScreen`, held headless as `jobs_tab` holds a board: the pool, the
pitch, the bars, the study targets and the show stay one source until step 10 of
`docs/plans/web_frontend.md` moves them here. The verb that runs the clock (`perform`) lives on
`HubSession`, which holds the map.
"""

from .. import economy, item_icon, magic, recruit
from ..archetypes import unit_archetypes
from ..constants import fmt_money
from ..prison_screen import PrisonScreen
from ..taverna_draw import _ARCHETYPE_TONE
from ..taverna_screen import TavernaScreen
from .shop_tab import _portrait

TABS = ("recruits", "rooms", "perform")


def _chips(u, limit=None):
    tags = unit_archetypes(u)
    return [{"label": label, "tone": _ARCHETYPE_TONE.get(style, "muted"), "tip": desc}
            for label, style, desc in (tags[:limit] if limit else tags)]


def _kind(u):
    return f"{u.race['name']} {u.occupation['name'].lower()}"


class TavernTab:
    def __init__(self, guild, group, node, prison=False, candidates=None):
        if prison:
            self.s = PrisonScreen(None, guild, list(group.members), node, lambda: None, group=group)
        else:
            self.s = TavernaScreen(None, guild, list(group.members), node, lambda: None, group=group, hide_tabs=True,
                                   candidates=candidates)
        self.prison = prison
        self.guild, self.group, self.node = guild, group, node
        self.report = []                    # what the last show said

    def _member(self, uid):
        self.s.sync_group()
        m = next((m for m in self.s.party if m.uid == uid), None)
        if m is None:
            raise ValueError("no such member in the band")
        return m

    def candidate(self, uid):
        i = next((i for i, c in enumerate(self.s.candidates) if c.uid == uid), None)
        if i is None:
            raise ValueError("no such stranger in the tavern")
        self.s._pick_candidate(i)

    def recruiter(self, uid):
        self.s.selected_recruiter = self._member(uid)

    def convince(self):
        s = self.s
        if s.sel is None or s.selected_recruiter is None:
            raise ValueError("pick a stranger and who makes the pitch")
        s._pitch(s.selected_recruiter)

    def _stranger(self, i, c):
        s = self.s
        text, tone = s._cand_status(c)
        bail = s._bail(c)
        return {"uid": c.uid, "name": c.name, "portrait": _portrait(c),
                "sub": f"{_kind(c)} · resists CHA {c.mod_charisma:+}",
                "note": f"Speaks {', '.join(c.languages)}" + (f" · bail {fmt_money(bail)}" if bail else ""),
                "chips": _chips(c, 3), "status": {"text": text, "tone": tone}, "picked": i == s.sel}

    def _last(self, c):
        if c.uid not in self.s.last:
            return None
        p, who = self.s.last[c.uid]
        if not p.recruiter_roll:
            return {"ok": False, "by": who.name, "line": p.reason}
        mods = [f"{v:+} {label}" for v, label in p.modifiers if v]
        return {"ok": p.ok, "by": who.name, "lang": p.language,
                "ours": f"d20 {p.recruiter_roll} {who.mod_charisma:+} CHA" + "".join(f" {m}" for m in mods),
                "ours_total": p.recruiter_total, "theirs": f"d20 {p.candidate_roll} {c.mod_charisma:+} CHA",
                "theirs_total": p.candidate_total}

    def _dossier(self, c):
        kit = [n for n in (c.equipped_weapon, c.armor_name) if n] + [i.name for i in c.inventory]
        return {"uid": c.uid, "name": c.name, "portrait": _portrait(c), "sub": f"{_kind(c)} · {c.alignment}",
                "chips": _chips(c), "facts": [("HP", str(c.hp_max)), ("AC", str(c.ac)), ("Speed", f"{c.speed} sq"),
                                              ("Attack", c.weapon_name or "Unarmed")],
                "kit": [{"name": n, "glyph": item_icon.glyph(n)} for n in kit],
                "ability": {"name": c.ability.name, "effect": c.ability.effect}, "last": self._last(c),
                "bail": self._bail(c)}

    def _bail(self, c):
        cost = self.s._bail(c)
        if not cost:
            return None
        held = self.s._wealth()
        return {"cost": fmt_money(cost), "held": fmt_money(held), "ok": held >= cost}

    def _pitch(self, c):
        s, who = self.s, self.s.selected_recruiter
        signed = s.signed
        pitchers = []
        for m in s.party:
            text, tone = s._pitch_condition(c, m)
            pitchers.append({"uid": m.uid, "name": m.name, "portrait": _portrait(m),
                             "sub": f"CHA {m.mod_charisma:+} · speaks {', '.join(m.languages)}",
                             "status": {"text": text, "tone": tone}, "picked": m is who,
                             "signed": signed is not None and signed["unit"] is m})
        can = (who is not None and recruit.can_pitch(who, c) and not s._barred(c, who)
               and recruit.slots_free(self.guild, who) > 0)
        bail = s._bail(c)
        label = f"Pay the {fmt_money(bail)} bail and convince" if bail else "Convince to join the guild"
        if bail and can and s._wealth() < bail:
            can, label = False, f"Cannot afford the {fmt_money(bail)} bail"
        elif who is not None and not can:
            label = f"{who.name} cannot pitch: {s._pitch_condition(c, who)[0]}"
        hint = None
        if not s._eligible(c):
            hint = {"text": recruit.pitch_block_reason(self.guild, s.party, c, lambda g, x, m: s._barred(x, m)),
                    "tone": "bad"}
        elif can:
            warn = recruit.overflow_warning(self.guild, who)
            hint = {"text": warn, "tone": "money"} if warn else None
        return {"pitchers": pitchers, "button": {"label": label, "on": can}, "hint": hint}

    def _signed(self):
        sg = self.s.signed
        if sg is None:
            return None
        u = sg["unit"]
        return {"name": u.name, "portrait": _portrait(u), "by": sg["by"].name, "line": sg["line"],
                "sub": f"{_kind(u)} · HP {u.hp_max} · AC {u.ac}"}

    def _recruits(self):
        s = self.s
        out = {"strangers": [self._stranger(i, c) for i, c in enumerate(s.candidates)],
               "empty": s.EMPTY_LIST.replace("\n", " "), "signed": self._signed(), "dossier": None,
               "prison": self.prison}
        if s.sel is not None and s.sel < len(s.candidates):
            c = s.candidates[s.sel]
            out["dossier"] = {**self._dossier(c), **self._pitch(c)}
        return out

    def set_target(self, uid, target):
        m = self._member(uid)
        opt = next((o for o in self.s._available_study_options(m) if o["id"] == target), None)
        if opt is None:
            raise ValueError(f"{m.name} cannot study {target!r} from what the band carries")
        self.s._set_target(m, opt)

    def stop_study(self, uid):
        m = self._member(uid)
        if not m.study_target:
            raise ValueError(f"{m.name} studies nothing")
        self.s._stop_study(m)

    def rent(self):
        if self.s._studying():
            raise ValueError("the band already studies here")
        self.s._rent_study()

    def cancel(self):
        if not self.s._studying():
            raise ValueError("the band is not studying")
        self.s._cancel_study()

    def _student(self, m):
        target = None
        if m.study_target:
            if m.study_target in magic.SPELLS:
                spell = magic.SPELLS[m.study_target]
                name, needed = f"Scroll of {spell.name}", magic.points_to_learn(spell.level)
            else:
                name, needed = f"Dictionary of {m.study_target}", magic.points_to_learn(0)
            target = {"name": name, "progress": m.study_progress, "needed": needed}
        schools = "/".join(x.capitalize() for x in m.magic_sources) + " magic" if m.magic_sources else "no magic"
        return {"uid": m.uid, "name": m.name, "portrait": _portrait(m),
                "sub": f"{_kind(m)} · INT {m.mod_intelligence:+} · {schools} · ${m.money}", "target": target,
                "options": [{"id": o["id"], "name": o["name"], "desc": o["desc"]}
                            for o in self.s._available_study_options(m)],
                "affinity": bool(m.magic_sources)}

    def _rooms(self):
        s = self.s
        cost = economy.TAVERN_STUDY_COST_PER_DAY
        studiers = sum(1 for m in s.party if m.study_target)
        return {"cost": cost, "today": studiers * cost, "studiers": studiers, "studying": s._studying(),
                "students": [self._student(m) for m in s.party]}

    def hours(self, h):
        if h not in economy.PERFORM_SHIFT_HOURS:
            raise ValueError(f"no {h} h show")
        self.s.perform_hours = h

    def seat(self, uid):
        m = self._member(uid)
        if not economy.can_perform(m):
            raise ValueError(f"{m.name} has no {economy.PERFORM_ITEM.lower()}")
        self.s.perform_off ^= {m}

    def perform(self):
        self.s.sync_group()
        self.report = self.s._perform()
        if self.report:
            self.s.notice = None        # the lines show as the last show, not as a toast

    def _player(self, m):
        s = self.s
        has = economy.can_perform(m)
        on = has and m not in s.perform_off
        tips = economy.perform_expected(s.perform_hours, m.mod_charisma) if on else 0
        return {"uid": m.uid, "name": m.name, "portrait": _portrait(m),
                "sub": f"{_kind(m)} · CHA {m.mod_charisma:+}", "has": has, "on": on, "tips": round(tips, 1)}

    def _stage(self):
        s = self.s
        return {"hours": s.perform_hours, "lengths": list(economy.PERFORM_SHIFT_HOURS),
                "base": economy.PERFORM_TIP_BASE, "step": economy.PERFORM_TIP_STEP, "item": economy.PERFORM_ITEM,
                "players": [self._player(m) for m in s.party], "can": bool(s._performers()),
                "report": self.report}

    def state(self, tab):
        s = self.s
        s.tab = tab
        s.sync_group()
        notice, s.notice = s.notice, None
        body = self._recruits() if tab == "recruits" else self._rooms() if tab == "rooms" else self._stage()
        return {"cards": s.hub_cards(), "notice": notice, **body}

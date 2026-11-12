"""The Tavern's three tabs in the browser: RECRUIT (the strangers drinking here on leather, the picked
one's dossier and who makes the pitch on paper), STUDY (the rooms to rent and each member's study
target) and PERFORM (the stage: the show's length and who plays); the City Prison's cells are RECRUIT
with a bail taken only if the pitch wins, doubled for +1 each time (`tavern.Prison`).

The rules are `tavern.Tavern`'s: the pool, the pitch, the bars, the study targets and the show. The
verb that runs the clock (`perform`) lives on `HubSession`, which holds the map.
"""

from .. import economy, i18n, item_icon, magic, recruit
from ..archetypes import unit_archetypes
from ..constants import fmt_money
from ..tavern import ARCHETYPE_TONE, BAIL_BONUS, BAIL_STEP, Prison, Tavern
from .shop_tab import _portrait

TABS = ("recruits", "rooms", "perform")


def _chips(u, limit=None):
    tags = unit_archetypes(u)
    return [{"label": label, "tone": ARCHETYPE_TONE.get(style, "muted"), "tip": desc}
            for label, style, desc in (tags[:limit] if limit else tags)]


def _kind(u):
    return u.race_label


class TavernTab:
    def __init__(self, guild, group, node, prison=False, candidates=None):
        self.s = Prison(guild, group) if prison else Tavern(guild, group, candidates)
        self.prison = prison
        self.guild, self.group, self.node = guild, group, node
        self.report = []                    # what the last show said

    def _member(self, uid):
        self.s.sync_group()
        m = next((m for m in self.s.party if m.uid == uid), None)
        if m is None:
            raise ValueError(i18n.t("tavern_tab.no_such_member_in_band"))
        return m

    def candidate(self, uid):
        i = next((i for i, c in enumerate(self.s.candidates) if c.uid == uid), None)
        if i is None:
            raise ValueError(i18n.t("tavern_tab.no_such_stranger_in_tavern"))
        self.s._pick_candidate(i)

    def recruiter(self, uid):
        self.s.selected_recruiter = self._member(uid)

    def raise_bail(self, delta):
        if delta not in (-1, 1):
            raise ValueError(i18n.t("tavern_tab.offer_moves_one_doubling_at"))
        self.s._raise(delta)

    def joint(self):
        self.s.joint = not self.s.joint

    def convince(self):
        s = self.s
        if s.sel is None or s.selected_recruiter is None:
            raise ValueError(i18n.t("tavern_tab.pick_stranger_and_who_makes"))
        s._pitch(s.selected_recruiter)

    def _stranger(self, i, c):
        s = self.s
        text, tone = s._cand_status(c)
        bail = s._bail(c)
        return {"uid": c.uid, "name": c.name, "portrait": _portrait(c),
                "sub": i18n.t("tavern_tab.resists_cha", kind=_kind(c), mod_charisma=c.mod_charisma),
                "note": i18n.t("tavern_tab.speaks", join=', '.join(i18n.names("language", c.languages))) + (i18n.t("tavern_tab.bail", fmt_money=fmt_money(bail)) if bail else ""),
                "chips": _chips(c, 3), "status": {"text": text, "tone": tone}, "picked": i == s.sel}

    def _last(self, c):
        if c.uid not in self.s.last:
            return None
        p, who = self.s.last[c.uid]
        if not p.recruiter_roll:
            return {"ok": False, "by": who.name, "line": p.reason}
        mods = [f"{v:+} {label}" for v, label in p.modifiers if v]
        dice = " · ".join(str(r) for r in p.rolls) if len(p.rolls) > 1 else None
        return {"ok": p.ok, "dice": dice, "by": who.name, "lang": p.language,
                "ours": i18n.t("tavern_tab.d_cha", recruiter_roll=p.recruiter_roll, mod_charisma=who.mod_charisma) + "".join(f" {m}" for m in mods),
                "ours_total": p.recruiter_total, "theirs": i18n.t("tavern_tab.d_cha_2", candidate_roll=p.candidate_roll, mod_charisma=c.mod_charisma),
                "theirs_total": p.candidate_total}

    def _dossier(self, c):
        kit = [n for n in (c.equipped_weapon, c.armor_name) if n] + [i.name for i in c.inventory]
        return {"uid": c.uid, "name": c.name, "portrait": _portrait(c), "sub": f"{_kind(c)} · {i18n.name('alignment', c.alignment)}",
                "chips": _chips(c), "facts": [(i18n.lab("HP"), str(c.hp_max)), (i18n.lab("AC"), str(c.ac)), (i18n.lab("Speed"), i18n.t("tavern_tab.sq", speed=c.speed)),
                                              (i18n.lab("Attack"), i18n.name("item", c.weapon.name))],
                "kit": [{"name": n, "glyph": item_icon.glyph(n)} for n in kit],
                "ability": {"name": c.ability.name, "effect": c.ability.effect}, "last": self._last(c),
                "bail": self._bail(c)}

    def _bail(self, c):
        base = self.s._bail(c)
        if not base:
            return None
        k, due, held = self.s.raise_k, self.s._due(c), self.s._wealth()
        return {"base": fmt_money(base), "cost": fmt_money(due), "held": fmt_money(held), "ok": held >= due,
                "bonus": BAIL_BONUS[0] + k * BAIL_STEP, "k": k, "more": held >= base << (k + 1), "less": k > 0}

    def _pitch(self, c):
        s, who = self.s, self.s.selected_recruiter
        signed = s.signed
        pitchers = []
        for m in s.party:
            text, tone = s._pitch_condition(c, m)
            pitchers.append({"uid": m.uid, "name": m.name, "portrait": _portrait(m),
                             "sub": i18n.t("tavern_tab.cha_speaks", mod_charisma=m.mod_charisma, join=', '.join(i18n.names("language", m.languages))),
                             "status": {"text": text, "tone": tone}, "picked": m is who,
                             "signed": signed is not None and signed["unit"] is m})
        can = (who is not None and recruit.can_pitch(who, c) and not s._barred(c, who)
               and recruit.slots_free(self.guild, who) > 0)
        bail = s._due(c)
        label = i18n.t("tavern_tab.convince_bail_if_it_works", fmt_money=fmt_money(bail)) if bail else i18n.t("tavern_tab.convince_to_join_guild")
        if bail and can and s._wealth() < bail:
            can, label = False, i18n.t("tavern_tab.cannot_afford_bail", fmt_money=fmt_money(bail))
        elif who is not None and not can:
            label = i18n.t("tavern_tab.cannot_pitch", name=who.name, pitch_condition=s._pitch_condition(c, who)[0])
        hint = None
        if not s._eligible(c):
            hint = {"text": recruit.pitch_block_reason(self.guild, s.party, c, lambda g, x, m: s._barred(x, m)),
                    "tone": "bad"}
        elif can:
            warn = recruit.overflow_warning(self.guild, who)
            hint = {"text": warn, "tone": "money"} if warn else None
        return {"pitchers": pitchers, "button": {"label": label, "on": can}, "hint": hint,
                "terms": self._terms(who), "joint": self._joint(c, who)}

    def _joint(self, c, who):
        """The Joint Pitch choice, or None: who would roll beside the one pitching, and whether it is on."""
        if who is None:
            return None
        allies = recruit.joint_allies(self.guild, self.s.party, c, who, self.s._barred)
        return {"on": self.s.joint, "names": [m.name for m in allies]} if allies else None

    def _terms(self, who):
        """The two numbers a pitch is weighed by before the roll: the crowd penalty and the room in
        the group the recruit would join."""
        size = len(self.guild.roster)
        pen, cut = recruit.size_penalty(size, who), recruit.size_cut(size, who)
        note = i18n.t("tavern_tab.guild_of_on_every_pitch", size=size, size_penalty=recruit.SIZE_PENALTY, free_slots=recruit.FREE_SLOTS)
        if cut:
            note += i18n.t("tavern_tab.crowd_cut", plain=pen + cut, cut=cut)
        crowd = {"label": i18n.lab("Crowd"), "value": f"-{pen}" if pen else "0", "tone": "bad" if pen else "good",
                 "note": note}
        grp = (self.guild.group_of(who) if who is not None else None) or self.group
        (base, base_lbl), *rest = grp.capacity_terms()
        sum_line = " ".join([f"{base} {i18n.lab(base_lbl)}", *(f"{v:+} {i18n.lab(lbl)}" for v, lbl in rest)])
        n, cap = len(grp.members), grp.capacity
        room = {"label": i18n.lab("Group"), "value": i18n.t("tavern_tab.of", n=n, cap=cap), "tone": "good" if n < cap else "money",
                "note": i18n.t("tavern_tab.holds", display_name=grp.display_name, sum_line=sum_line)}
        return [crowd, room]

    def _foot(self):
        if self.prison:
            return (i18n.t("tavern_tab.bail_buys_on_pitch_and", bail_bonus=BAIL_BONUS[0]))
        return (i18n.t("tavern_tab.opposite_alignment_docks_pitch_step", alignment_penalty=recruit.ALIGNMENT_PENALTY, free_slots=recruit.FREE_SLOTS, size_penalty=recruit.SIZE_PENALTY))

    def _signed(self):
        sg = self.s.signed
        if sg is None:
            return None
        u = sg["unit"]
        return {"name": u.name, "portrait": _portrait(u), "by": sg["by"].name, "line": sg["line"],
                "sub": i18n.t("tavern_tab.hp_ac", kind=_kind(u), hp_max=u.hp_max, ac=u.ac)}

    def _recruits(self):
        s = self.s
        out = {"strangers": [self._stranger(i, c) for i, c in enumerate(s.candidates)],
               "empty": i18n.t(s.EMPTY_LIST), "signed": self._signed(), "dossier": None,
               "prison": self.prison, "foot": self._foot()}
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
            raise ValueError(i18n.t("tavern_tab.studies_nothing", name=m.name))
        self.s._stop_study(m)

    def rent(self):
        if self.s._studying():
            raise ValueError(i18n.t("tavern_tab.band_already_studies_here"))
        self.s._rent_study()

    def cancel(self):
        if not self.s._studying():
            raise ValueError(i18n.t("tavern_tab.band_is_not_studying"))
        self.s._cancel_study()

    def _student(self, m):
        target = None
        if m.study_target:
            if m.study_target in magic.SPELLS:
                spell = magic.SPELLS[m.study_target]
                name, needed = i18n.t("tavern_tab.scroll_of", name=spell.name), magic.points_to_learn(spell.level)
            elif recipe := magic.recipe_of(m.study_target):
                name, needed = recipe.name, magic.points_to_learn(recipe.level)
            else:
                name, needed = i18n.t("tavern_tab.dictionary_of", study_target=m.study_target), magic.points_to_learn(0)
            target = {"name": name, "progress": m.study_progress.get(m.study_target, 0), "needed": needed}
        schools = "/".join(x.capitalize() for x in m.magic_sources) + " magic" if m.magic_sources else i18n.t("tavern_tab.no_magic")
        return {"uid": m.uid, "name": m.name, "portrait": _portrait(m),
                "sub": i18n.t("tavern_tab.int", kind=_kind(m), mod_intelligence=m.mod_intelligence, schools=schools, money=m.money), "target": target,
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
            raise ValueError(i18n.t("tavern_tab.no_h_show", h=h))
        self.s.perform_hours = h

    def seat(self, uid):
        m = self._member(uid)
        if not economy.can_perform(m):
            raise ValueError(i18n.t("tavern_tab.has_no", name=m.name, lower=i18n.name("item", economy.PERFORM_ITEM).lower()))
        self.s.perform_off ^= {m}

    def show(self):
        self.s.sync_group()
        return self.s._show()

    def _player(self, m):
        s = self.s
        has = economy.can_perform(m)
        on = has and m not in s.perform_off
        tips = economy.perform_expected(s.perform_hours, m.mod_charisma) if on else 0
        return {"uid": m.uid, "name": m.name, "portrait": _portrait(m),
                "sub": i18n.t("tavern_tab.cha", kind=_kind(m), mod_charisma=m.mod_charisma), "has": has, "on": on, "tips": round(tips, 1)}

    def _stage(self):
        s = self.s
        return {"hours": s.perform_hours, "lengths": list(economy.PERFORM_SHIFT_HOURS),
                "base": economy.PERFORM_TIP_BASE, "step": economy.PERFORM_TIP_STEP, "item": i18n.name("item", economy.PERFORM_ITEM),
                "players": [self._player(m) for m in s.party], "can": bool(s._performers()),
                "report": self.report}

    def state(self, tab):
        s = self.s
        s.tab = tab
        s.sync_group()
        notice, s.notice = s.notice, None
        body = self._recruits() if tab == "recruits" else self._rooms() if tab == "rooms" else self._stage()
        return {"cards": s.hub_cards(), "notice": notice, **body}

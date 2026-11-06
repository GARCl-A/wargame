"""The Tavern's counter, with no pygame: talk a stranger into joining the guild, rent quiet rooms to
study, or play the stage for tips. `Prison` is the City Prison's cells: the same counter with a bail
that is taken only when the pitch wins.

The strangers drinking here are the guild's weekly pool (`recruit.refresh_pool` -- same faces every
visit until seven days pass, then a fresh set). Pick one, then the member who makes the pitch:
`recruit.convince` rolls that member's Charisma against the stranger's, docked for opposite alignment
and for how crowded the guild already is; a tie goes to the stranger. Win and they sign on (bound to
the recruiter via `recruited_by`, and out of the pool). Lose and that recruiter is barred from pitching
that same stranger until the pool turns over -- another member can still try.

The stage puts anyone carrying a Musical Instrument on for a few hours: each hour is a Charisma test
the crowd tips on (`economy.perform_pay`). The rooms are the garrison job "study": a member with a
study target (a scroll or dictionary the band carries) gains daily progress toward a spell or a
language.
"""

from . import economy, i18n, magic, orders, recorder, recruit, stints
from .constants import fmt_money
from .data import alignment_distance

ARCHETYPE_TONE = {"brass": "money", "green": "good", "muted": "muted"}
BAIL_BONUS = (2, "tavern.paid_bail")


class Tavern:
    REJECTED_LABEL = "tavern.rejected_this_week"
    EMPTY_LIST = "tavern.empty_list"
    PITCH_BONUS = ()                      # (value, label) mods added to every pitch roll
    SEEN_KEY = "taverna"

    def __init__(self, guild, group, candidates=None):
        recruit.mark_seen(guild, self.SEEN_KEY)
        self.guild = guild
        self.group = group
        self.party = list(group.members)
        self.candidates = list(candidates) if candidates is not None else self._pool()
        self.sel = 0 if self.candidates else None
        self.selected_recruiter = self.party[0] if self.party else None
        self.last = {}                         # candidate uid -> (recruit.Pitch, member) of the last try
        self.notice = None
        self.tab = "recruits"               # "recruits", "rooms" or "perform"
        self.perform_hours = economy.PERFORM_SHIFT_HOURS[-1]
        self.perform_off = set()            # members who sit the show out
        self.signed = None                  # {"unit", "by", "pitch", "line"} of the most recent sign-on
        self.raise_k = 0                    # doublings of the bail on offer (Prison)

    def _pool(self):
        return recruit.refresh_pool(self.guild)

    def sync_group(self):
        self.party = list(self.group.members)
        if self.selected_recruiter not in self.party:
            self.selected_recruiter = self.party[0] if self.party else None

    def hub_cards(self):
        purse = {"label": i18n.t("tavern.party_purse"), "value": fmt_money(self._wealth()), "tone": "money"}
        if self.tab != "recruits":
            return [purse]
        size = len(self.guild.roster)
        days = recruit.REFRESH_DAYS - (self.guild.clock.day - 1) % recruit.REFRESH_DAYS
        return [{"label": i18n.t("tavern.guild_size"), "value": str(size)},
                {"label": i18n.t("tavern.crowd_penalty"), "value": f"-{recruit.size_penalty(size)}"},
                {"label": i18n.t("tavern.new_faces_in"), "value": i18n.plural("tavern.days", days)},
                purse]

    def _barred(self, cand, member):
        return recruit.barred(self.guild, cand, member)

    def _bar(self, cand, member):
        recruit.bar(self.guild, cand, member)

    def _bail(self, cand):
        """Copper the base bail costs; paid only when the pitch wins."""
        return 0

    def _due(self, cand):
        """Copper taken if the pitch wins: the bail, doubled once per raise."""
        return self._bail(cand) << self.raise_k

    def _raise_mods(self):
        return [(self.raise_k, i18n.t("tavern.extra_bail"))] if self.raise_k else []

    def _raise(self, delta):
        """Move the offer one doubling up (while the purse covers it) or down."""
        cand = self.candidates[self.sel] if self.sel is not None and self.sel < len(self.candidates) else None
        if cand is None or not self._bail(cand):
            return
        k = self.raise_k + delta
        if k < 0 or (delta > 0 and self._wealth() < self._bail(cand) << k):
            return
        self.raise_k = k

    def _wealth(self):
        stores = self.group.stores
        return sum(m.money for m in (*self.party, *stores))

    def _eligible(self, cand):
        """Party members who could still pitch `cand` (share a tongue, not yet
        barred for failing on them this week, and still have room to sponsor
        someone new)."""
        return [m for m in self.party
                if recruit.can_pitch(m, cand) and not self._barred(cand, m)
                and recruit.slots_free(self.guild, m) > 0]

    def _net(self, m, cand):
        """The pitch's net Charisma modifier for `m` against `cand`."""
        raw = alignment_distance(m.alignment, cand.alignment)
        dist = max(0, raw - int(m.talent_bonus("align_distance_reduction")))
        return (m.mod_charisma - recruit.ALIGNMENT_PENALTY * dist
                - recruit.size_penalty(len(self.guild.roster))
                + m.talent_bonus("recruit_cha") + sum(v for v, _ in self.PITCH_BONUS)
                + self.raise_k)

    def _best(self, cand):
        """(member, net modifier) for the strongest pitch still open, or None."""
        opts = [(m, self._net(m, cand)) for m in self._eligible(cand)]
        return max(opts, key=lambda t: t[1]) if opts else None

    def _cand_status(self, cand):
        if cand.uid in self.last:
            pitch, _who = self.last[cand.uid]
            if pitch.ok:
                return "enlisted", "good"
            if self._best(cand) is None:
                return i18n.t(self.REJECTED_LABEL), "bad"
        best = self._best(cand)
        if best is not None:
            return i18n.t("tavern.can_pitch", name=best[0].name), "good"
        return i18n.t("tavern.cannot_pitch"), "bad"

    def _pitch_condition(self, cand, m):
        if recruit.slots_free(self.guild, m) <= 0:
            return i18n.t("tavern.no_recruitment_slot"), "bad"
        if self._barred(cand, m):
            return i18n.t("tavern.already_tried_this_week"), "bad"
        if not recruit.can_pitch(m, cand):
            return i18n.t("tavern.no_shared_language"), "bad"
        return i18n.t("tavern.d_vs_d", net=self._net(m, cand), mod_charisma=cand.mod_charisma), "good"

    def _pick_candidate(self, i):
        """Read candidate `i`'s dossier; the one pitching moves to the strongest pitch still open
        unless the one picked can still pitch them."""
        self.sel = i
        self.raise_k = 0
        self.signed = None
        self.notice = None
        cand = self.candidates[i]
        best = self._best(cand)
        if best is not None and not (self.selected_recruiter and self.selected_recruiter in self._eligible(cand)):
            self.selected_recruiter = best[0]

    def _studying(self):
        o = self.group.order
        return o is not None and o.kind == "garrison" and o.job == "study"

    def _rent_study(self):
        if not any(m.study_target for m in self.party):
            self.notice = i18n.t("tavern.set_study_target_for_someone")
            return
        self.group.order = orders.garrison("study")
        self.notice = i18n.t("tavern.party_rented_quiet_rooms_and")

    def _cancel_study(self):
        self.group.order = None
        self.notice = i18n.t("tavern.study_order_cancelled_party_is")

    def _set_target(self, member, opt):
        magic.begin_study(member, opt["id"], self._study_holders())
        self.notice = i18n.t("tavern.begins_studying", name=member.name, opt=opt['name'])

    def _stop_study(self, member):
        magic.end_study(member)
        self.notice = i18n.t("tavern.stopped_studying", name=member.name)

    def _performers(self):
        return [m for m in self.party if m in self.guild.roster and economy.can_perform(m)
                and m not in self.perform_off]

    def _show(self):
        """The show the picked players put on: a `perform` stint for the band, or None (the notice says why)."""
        crew = self._performers()
        if not crew:
            self.notice = i18n.t("tavern.pick_someone_with_musical_instrument")
            return None
        hours = self.perform_hours
        return stints.order("perform", hours, crew, clock_hours=hours * self.guild.work_speedup(crew))

    @staticmethod
    def _signed_line(cand):
        align = getattr(cand, "alignment", "")
        if "Good" in align:
            return i18n.t("tavern.you_have_my_word_and")
        if "Evil" in align:
            return i18n.t("tavern.pay_my_share_on_time")
        if "Lawful" in align:
            return i18n.t("tavern.fair_contract_tell_me_where")
        if "Chaotic" in align:
            return i18n.t("tavern.better_than_drinking_alone_let")
        return i18n.t("tavern.my_kit_is_packed_lead")

    def _pitch(self, member):
        if self.sel is None or self.sel >= len(self.candidates):
            return
        cand = self.candidates[self.sel]
        if recruit.slots_free(self.guild, member) <= 0:
            self.notice = i18n.t("tavern.has_no_recruitment_slots_available", name=member.name)
            return
        if not recruit.can_pitch(member, cand):
            self.notice = i18n.t("tavern.and_share_no_language", name=member.name, other=cand.name)
            return
        if self._barred(cand, member):
            self.notice = i18n.t("tavern.already_tried_this_week_2", name=member.name, other=cand.name)
            return
        cost = self._due(cand)
        if cost and self._wealth() < cost:
            self.notice = i18n.t("tavern.not_enough_coin_to_pay", name=cand.name, fmt_money=fmt_money(cost))
            return
        pitch = recruit.convince(member, cand, len(self.guild.roster), day=self.guild.clock.day,
                                 extra_mods=[*((v, i18n.t(label)) for v, label in self.PITCH_BONUS), *self._raise_mods()])
        self.last[cand.uid] = (pitch, member)
        paid = cost if pitch.ok else 0
        raised, self.raise_k = self.raise_k, 0
        recorder.emit("recruit", pitcher=member.name, candidate=cand.name, bail=paid, raised=raised,
                      ok=bool(pitch.ok))
        if pitch.ok:
            if paid:
                economy.charge_richest_first((*self.party, *self.group.stores), paid)
            recruit.enlist(self.guild, cand, member)
            from . import objectives
            objectives.complete(self.guild, "obj_recruit_prison" if cost else "obj_recruit_tavern")
            if cand not in self.party:
                self.party.append(cand)
            self.sync_group()
            if cand in self.candidates:
                self.candidates.remove(cand)
            self.signed = {"unit": cand, "by": member, "pitch": pitch, "line": self._signed_line(cand)}
            self.notice = i18n.t("tavern.signed_bail" if cost else "tavern.signed", name=cand.name, by=member.name)
            if self.candidates:
                self.sel = min(self.sel, len(self.candidates) - 1)
            else:
                self.sel = None
        else:
            self._bar(cand, member)
            if cost:
                self.notice = i18n.t("tavern.turns_down_bail_stays_in", name=cand.name, other=member.name)
            else:
                self.notice = i18n.t("tavern.turns_down_they_can_only", name=cand.name, other=member.name)

    def _study_holders(self):
        """Whoever may hold a study item: the group's members, then its wagons and animals."""
        return [*self.group.members, *self.group.wagons, *self.group.herd]

    def _available_study_options(self, student):
        """Finds all scrolls and dictionaries carried by any member in the party/group
        that `student` can study."""
        options = []
        seen = set()
        for m in self._study_holders():
            for item in m.inventory:
                spell = magic.spell_for_scroll(item)
                if spell and magic.can_study_spell(student, spell):
                    if spell.id not in seen:
                        seen.add(spell.id)
                        pts = magic.points_to_learn(spell.level)
                        options.append({
                            "kind": "spell",
                            "id": spell.id,
                            "name": i18n.t("tavern.scroll_of", name=spell.name),
                            "holder": m.name,
                            "level": spell.level,
                            "desc": i18n.t("tavern.spell_lvl_pts_to_master", level=spell.level, sources=spell.sources, pts=pts, name=m.name)
                        })
                lang = magic.language_for_dictionary(item)
                if lang and lang.name not in student.languages:
                    if lang.name not in seen:
                        seen.add(lang.name)
                        pts = magic.points_to_learn(0)
                        options.append({
                            "kind": "lang",
                            "id": lang.name,
                            "name": i18n.t("tavern.dictionary_of", name=lang.name),
                            "holder": m.name,
                            "level": 0,
                            "desc": i18n.t("tavern.language_pts_to_learn_carried", pts=pts, name=m.name)
                        })
        return options


class Prison(Tavern):
    """The cells: the strangers are the guild's weekly `prison_pool`. The bail on offer buys +2 on the
    Charisma contest and each doubling of it +1 more; it is taken only if the pitch wins."""

    REJECTED_LABEL = "tavern.walked_free_this_week"
    EMPTY_LIST = "tavern.empty_prison"
    PITCH_BONUS = (BAIL_BONUS,)
    SEEN_KEY = "prison"

    def _pool(self):
        return recruit.refresh_prison_pool(self.guild)

    def _barred(self, cand, member):
        return recruit.prison_barred(self.guild, cand, member)

    def _bar(self, cand, member):
        recruit.prison_bar(self.guild, cand, member)

    def _bail(self, cand):
        return recruit.bail_cost(cand)

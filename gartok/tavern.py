"""The Tavern's counter, with no pygame: talk a stranger into joining the guild, rent quiet rooms to
study, or play the stage for tips. `Prison` is the City Prison's cells: the same counter with a bail.

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

from . import economy, magic, orders, recorder, recruit
from .constants import fmt_money
from .data import alignment_distance

ARCHETYPE_TONE = {"brass": "money", "green": "good", "muted": "muted"}
BAIL_BONUS = (2, "paid bail")


class Tavern:
    REJECTED_LABEL = "REJECTED THIS WEEK"
    EMPTY_LIST = "No one looking for work right now. Come back when the crowd changes."
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

    def _pool(self):
        return recruit.refresh_pool(self.guild)

    def sync_group(self):
        self.party = list(self.group.members)
        if self.selected_recruiter not in self.party:
            self.selected_recruiter = self.party[0] if self.party else None

    def hub_cards(self):
        purse = {"label": "party purse", "value": fmt_money(self._wealth()), "tone": "money"}
        if self.tab != "recruits":
            return [purse]
        size = len(self.guild.roster)
        days = recruit.REFRESH_DAYS - (self.guild.clock.day - 1) % recruit.REFRESH_DAYS
        return [{"label": "guild size", "value": str(size)},
                {"label": "crowd penalty", "value": f"-{recruit.size_penalty(size)}"},
                {"label": "new faces in", "value": f"{days} day{'s' if days != 1 else ''}"},
                purse]

    def _barred(self, cand, member):
        return recruit.barred(self.guild, cand, member)

    def _bar(self, cand, member):
        recruit.bar(self.guild, cand, member)

    def _bail(self, cand):
        """Copper that must be paid before a pitch is even rolled."""
        return 0

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
                + m.talent_bonus("recruit_cha") + sum(v for v, _ in self.PITCH_BONUS))

    def _best(self, cand):
        """(member, net modifier) for the strongest pitch still open, or None."""
        opts = [(m, self._net(m, cand)) for m in self._eligible(cand)]
        return max(opts, key=lambda t: t[1]) if opts else None

    def _cand_status(self, cand):
        if cand.uid in self.last:
            pitch, _who = self.last[cand.uid]
            return ("enlisted", "good") if pitch.ok else (self.REJECTED_LABEL.lower(), "bad")
        best = self._best(cand)
        if best is not None:
            return f"{best[0].name} can pitch", "good"
        return "cannot pitch", "bad"

    def _pitch_condition(self, cand, m):
        if recruit.slots_free(self.guild, m) <= 0:
            return "no recruitment slot", "bad"
        if self._barred(cand, m):
            return "already tried this week", "bad"
        if not recruit.can_pitch(m, cand):
            return "no shared language", "bad"
        return f"1d20{self._net(m, cand):+} vs 1d20{cand.mod_charisma:+}", "good"

    def _pick_candidate(self, i):
        """Read candidate `i`'s dossier; the one pitching moves to the strongest pitch still open
        unless the one picked can still pitch them."""
        self.sel = i
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
            self.notice = "Set a study target for someone before renting rooms."
            return
        self.group.order = orders.garrison("study")
        self.notice = "Party rented quiet rooms and begins studying daily."

    def _cancel_study(self):
        self.group.order = None
        self.notice = "Study order cancelled. Party is now idle."

    def _set_target(self, member, opt):
        magic.begin_study(member, opt["id"], self._study_holders())
        self.notice = f"{member.name} begins studying {opt['name']}."

    def _stop_study(self, member):
        magic.end_study(member)
        self.notice = f"{member.name} stopped studying."

    def _performers(self):
        return [m for m in self.party if m in self.guild.roster and economy.can_perform(m)
                and m not in self.perform_off]

    def _perform(self):
        crew = self._performers()
        if not crew:
            self.notice = "Pick someone with a Musical Instrument to play."
            return []
        events, _ = self.guild.perform_shift(crew, self.perform_hours)
        self.notice = "  ".join(events)
        return events

    @staticmethod
    def _signed_line(cand):
        align = getattr(cand, "alignment", "")
        if "Good" in align:
            return "You have my word and my blade. Point the way."
        if "Evil" in align:
            return "Pay my share on time and nobody else bleeds."
        if "Lawful" in align:
            return "A fair contract. Tell me where I stand in the line."
        if "Chaotic" in align:
            return "Better than drinking alone. Let's see what you're walking into."
        return "My kit is packed. Lead on."

    def _pitch(self, member):
        if self.sel is None or self.sel >= len(self.candidates):
            return
        cand = self.candidates[self.sel]
        if recruit.slots_free(self.guild, member) <= 0:
            self.notice = f"{member.name} has no recruitment slots available."
            return
        if not recruit.can_pitch(member, cand):
            self.notice = f"{member.name} and {cand.name} share no language."
            return
        if self._barred(cand, member):
            self.notice = f"{member.name} already tried {cand.name} this week."
            return
        cost = self._bail(cand)
        if cost and self._wealth() < cost:
            self.notice = f"Not enough coin to pay {cand.name}'s bail ({fmt_money(cost)})."
            return
        if cost:
            stores = self.group.stores
            economy.charge_richest_first((*self.party, *stores), cost)
        pitch = recruit.convince(member, cand, len(self.guild.roster), day=self.guild.clock.day,
                                 extra_mods=list(self.PITCH_BONUS))
        self.last[cand.uid] = (pitch, member)
        recorder.emit("recruit", pitcher=member.name, candidate=cand.name, bail=cost, ok=bool(pitch.ok))
        if pitch.ok:
            recruit.enlist(self.guild, cand, member)
            from . import objectives
            objectives.complete(self.guild, "obj_recruit_prison" if cost else "obj_recruit_tavern")
            if cand not in self.party:
                self.party.append(cand)
            self.sync_group()
            if cand in self.candidates:
                self.candidates.remove(cand)
            self.signed = {"unit": cand, "by": member, "pitch": pitch, "line": self._signed_line(cand)}
            paid = "Bail paid! " if cost else ""
            self.notice = f"{paid}{cand.name} signs with the guild (recruited by {member.name})!"
            if self.candidates:
                self.sel = min(self.sel, len(self.candidates) - 1)
            else:
                self.sel = None
        else:
            self._bar(cand, member)
            if cost:
                self.notice = f"Bail paid, but {cand.name} walks away free. You lost {fmt_money(cost)}."
            else:
                self.notice = f"{cand.name} turns {member.name} down. They can only try again next week."

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
                            "name": f"Scroll of {spell.name}",
                            "holder": m.name,
                            "level": spell.level,
                            "desc": f"Spell Lvl {spell.level} ({spell.sources}) · {pts} pts to master · carried by {m.name}"
                        })
                lang = magic.language_for_dictionary(item)
                if lang and lang.name not in student.languages:
                    if lang.name not in seen:
                        seen.add(lang.name)
                        pts = magic.points_to_learn(0)
                        options.append({
                            "kind": "lang",
                            "id": lang.name,
                            "name": f"Dictionary of {lang.name}",
                            "holder": m.name,
                            "level": 0,
                            "desc": f"Language · {pts} pts to learn · carried by {m.name}"
                        })
        return options


class Prison(Tavern):
    """The cells: the strangers are the guild's weekly `prison_pool`, and their bail is paid before the
    pitch is rolled, for a +2 on the Charisma contest. A failed pitch walks free with the money."""

    REJECTED_LABEL = "WALKED FREE THIS WEEK"
    EMPTY_LIST = "The cells are empty right now. Come back when the crowd changes."
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

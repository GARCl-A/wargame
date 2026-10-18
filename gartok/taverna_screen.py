"""Taverna: talk a stranger into joining the guild, or rent quiet rooms to study.

The strangers drinking here are the guild's weekly pool (`recruit.refresh_pool`
-- same faces every visit until seven days pass, then a fresh set). Pick one,
then pick the party member who makes the pitch: `recruit.convince` rolls that
member's Charisma against the stranger's, docked for opposite alignment and for
how crowded the guild already is; a tie goes to the stranger.

Win and they sign on (bound to the recruiter via `recruited_by`, and out of the
pool). Lose and that recruiter is barred from pitching that same stranger until
the pool turns over -- another member can still try.

The perform tab puts anyone carrying a Musical Instrument on the stage for a few
hours: each hour on stage is a Charisma test the crowd tips on (`economy.perform_pay`).

The study tab lets the party rent rooms for the garrison job "study". Any member
with a study target (scroll or dictionary carried by the party) accumulates
daily progress toward learning new spells or languages.

Modernized to the `gartok/ui/` design system.
"""

import pygame

from . import economy, magic, orders, recorder, recruit
from .constants import fmt_money
from .data import alignment_distance
from .screen import Screen
from .taverna_draw import TavernaDrawMixin
from .ui.primitives import draw_button
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class TavernaScreen(TavernaDrawMixin, Screen):
    """The recruiting screen; `PrisonScreen` is the same screen with a bail to pay
    first, so everything that differs is a hook or a label here."""

    native = True

    LIST_LABEL = "CANDIDATES IN THE TAVERN"
    EMPTY_LIST = "No one looking for work right now.\nCome back when the crowd changes."
    REJECTED_LABEL = "REJECTED THIS WEEK"
    PITCH_BONUS = ()                      # (value, label) mods added to every pitch roll
    SEEN_KEY = "taverna"

    def __init__(self, fonts, guild, party, node, on_done, candidates=None, title=None, group=None, hide_tabs=False):
        super().__init__()
        self.hide_tabs = hide_tabs
        recruit.mark_seen(guild, self.SEEN_KEY)
        self.fonts = fonts
        self._F = fonts if (isinstance(fonts, dict) and "body" in fonts) else ui_fonts()
        self.guild = guild
        self.party = list(party)
        self.group = group                    # backing Group, for the rooms/study order (None if not applicable)
        self.node = node
        self.on_done = on_done
        self.candidates = list(candidates) if candidates is not None else recruit.refresh_pool(guild)
        self.title = title or "TAVERN"
        self.sel = 0 if self.candidates else None # index of selected candidate
        self.selected_recruiter = self.party[0] if self.party else None
        self.last = {}                         # candidate uid -> (recruit.Pitch, member) of the last try
        self.notice = None
        self.cand_cards = []                 # [(rect, index)]
        self.party_cards = []                # [(rect, member)]
        self.buttons = []                   # [(key, rect)]
        self._hot = False
        self.tab = "recruits"               # "recruits", "rooms" or "perform"
        self.perform_hours = economy.PERFORM_SHIFT_HOURS[-1]
        self.perform_off = set()            # members who sit the show out (default: everyone plays)
        self.study_modal_member = None      # Unit for whom we are picking a study target
        self.modal_buttons = []             # [(key, rect, action_arg)]
        self._tooltips = []                 # [(rect, text)]
        self.signed = None                  # {"unit", "by", "pitch", "line"} of the most recent sign-on

    def sync_group(self):
        if self.group is not None:
            self.party = list(self.group.members)
            if self.selected_recruiter not in self.party:
                self.selected_recruiter = self.party[0] if self.party else None

    # ------------------------------------------------------------------ #
    # tutorial (screen.py)                                               #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "taverna"

    def tutorial_badge_rect(self, size):
        W, H = size
        return pygame.Rect(W - T.S * 3 - 28, T.S * 2, 28, 28)

    def handle_escape(self):
        if self.study_modal_member is not None:
            self.study_modal_member = None
            return True
        self.on_done()
        return True

    # ------------------------------------------------------------------ #
    def add_button(self, surf, rect, key, label, enabled=True, primary=False, danger=False):
        self.buttons.append((key, rect))
        if rect.collidepoint(self.mouse):
            self._hot = True
        return draw_button(surf, self._F, rect, label, primary=primary, enabled=enabled,
                           danger=danger, mpos=self.mouse)

    # ------------------------------------------------------------------ #
    def _barred(self, cand, member):
        return recruit.barred(self.guild, cand, member)

    def _bar(self, cand, member):
        recruit.bar(self.guild, cand, member)

    def _bail(self, cand):
        """Copper that must be paid before a pitch is even rolled."""
        return 0

    def _leave_label(self):
        return "LEAVE THE TAVERN" if self.title == "TAVERN" else "DONE"

    def _sub_extra(self):
        """Text appended to the recruit tab's subtitle."""
        return ""

    def _wealth(self):
        stores = getattr(self.group, "stores", ()) if self.group is not None else ()
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

    # ------------------------------------------------------------------ #
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            px = event.pos

            # If study modal is open, modal intercepts all clicks
            if self.study_modal_member is not None:
                for key, rect, arg in self.modal_buttons:
                    if rect.collidepoint(px):
                        if key == "set_target":
                            magic.begin_study(self.study_modal_member, arg["id"], self._study_holders())
                            self.notice = f"{self.study_modal_member.name} begins studying {arg['name']}."
                            self.study_modal_member = None
                        elif key == "clear_target":
                            magic.end_study(self.study_modal_member)
                            self.notice = f"{self.study_modal_member.name} stopped studying."
                            self.study_modal_member = None
                        elif key == "cancel":
                            self.study_modal_member = None
                        return
                # Clicking anywhere outside closes the modal
                self.study_modal_member = None
                return

            # Check general buttons
            for key, rect in self.buttons:
                if rect.collidepoint(px):
                    if key == "done":
                        self.on_done()
                    elif key == "tab_recruits":
                        self.tab = "recruits"
                    elif key == "tab_rooms":
                        self.tab = "rooms"
                    elif key == "tab_perform":
                        self.tab = "perform"
                    elif key.startswith("perf_hours_"):
                        self.perform_hours = int(key.split("_")[-1])
                    elif key.startswith("perf_toggle_"):
                        m = self.party[int(key.split("_")[-1])]
                        self.perform_off ^= {m}
                    elif key == "perform_go":
                        self._perform()
                    elif key == "rent_study" and self.group is not None:
                        if not any(m.study_target for m in self.party):
                            self.notice = "Set a study target for someone before renting rooms."
                        else:
                            self.group.order = orders.garrison("study")
                            self.notice = "Party rented quiet rooms and begins studying daily."
                    elif key == "cancel_study" and self.group is not None:
                        self.group.order = None
                        self.notice = "Study order cancelled. Party is now idle."
                    elif key == "convince" and self.selected_recruiter is not None:
                        self._pitch(self.selected_recruiter)
                    elif key.startswith("choose_target_"):
                        idx = int(key.split("_")[-1])
                        self.study_modal_member = self.party[idx]
                    elif key.startswith("stop_study_"):
                        idx = int(key.split("_")[-1])
                        m = self.party[idx]
                        magic.end_study(m)
                        self.notice = f"{m.name} stopped studying."
                    return

            # Candidate card click in recruit tab
            if self.tab == "recruits":
                for rect, i in self.cand_cards:
                    if rect.collidepoint(px):
                        self.sel = i
                        self.signed = None
                        self.notice = None
                        cand = self.candidates[i]
                        best = self._best(cand)
                        if best is not None and not (self.selected_recruiter and self.selected_recruiter in self._eligible(cand)):
                            self.selected_recruiter = best[0]
                        return

                for rect, member in self.party_cards:
                    if rect.collidepoint(px):
                        self.selected_recruiter = member
                        return

    # ------------------------------------------------------------------ #
    def _performers(self):
        return [m for m in self.party if m in self.guild.roster and economy.can_perform(m)
                and m not in self.perform_off]

    def _perform(self):
        crew = self._performers()
        if not crew:
            self.notice = "Pick someone with a Musical Instrument to play."
            return
        events, _ = self.guild.perform_shift(crew, self.perform_hours)
        self.notice = "  ".join(events)

    # ------------------------------------------------------------------ #
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
            stores = getattr(self.group, "stores", ()) if self.group is not None else ()
            economy.charge_richest_first((*self.party, *stores), cost)
        pitch = recruit.convince(member, cand, len(self.guild.roster), day=self.guild.clock.day,
                                 extra_mods=list(self.PITCH_BONUS))
        self.last[cand.uid] = (pitch, member)
        recorder.emit("recruit", pitcher=member.name, candidate=cand.name, bail=cost, ok=bool(pitch.ok))
        if pitch.ok:
            recruit.enlist(self.guild, cand, member)
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

    # ------------------------------------------------------------------ #
    def _study_holders(self):
        """Whoever may hold a study item: the group's members, then its wagons and animals."""
        if self.group is None:
            return list(self.party)
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

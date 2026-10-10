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
from .archetypes import unit_archetypes
from .constants import fmt_money
from .data import alignment_distance
from .screen import Screen
from .ui.primitives import (
    FOOTER_H,
    caps,
    draw_button,
    draw_tooltip,
    footer_bar,
    format_tooltip,
    header,
    hline,
    panel,
    text,
    token_badge,
)
from .ui.tokens import ARCHETYPE_COLORS, T, mix
from .ui.tokens import fonts as ui_fonts


class TavernaScreen(Screen):
    """The recruiting screen; `PrisonScreen` is the same screen with a bail to pay
    first, so everything that differs is a hook or a label here."""

    native = True

    LIST_LABEL = "CANDIDATES IN THE TAVERN"
    EMPTY_LIST = "No one looking for work right now.\nCome back when the crowd changes."
    REJECTED_LABEL = "REJECTED THIS WEEK"
    PITCH_BONUS = ()                      # (value, label) mods added to every pitch roll
    SEEN_KEY = "taverna"

    def __init__(self, fonts, guild, party, node, on_done, candidates=None, title=None, group=None):
        super().__init__()
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
        return sum(m.money for m in self.party)

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
                            magic.begin_study(self.study_modal_member, arg["id"], self.party)
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
            economy.charge_richest_first(self.party, cost)
        pitch = recruit.convince(member, cand, len(self.guild.roster), day=self.guild.clock.day,
                                 extra_mods=list(self.PITCH_BONUS))
        self.last[cand.uid] = (pitch, member)
        recorder.emit("recruit", pitcher=member.name, candidate=cand.name, bail=cost, ok=bool(pitch.ok))
        if pitch.ok:
            recruit.enlist(self.guild, cand, member)
            if cand in self.candidates:
                self.candidates.remove(cand)
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
    def _available_study_options(self, student):
        """Finds all scrolls and dictionaries carried by any member in the party/group
        that `student` can study."""
        options = []
        seen = set()
        members = self.group.members if self.group is not None else self.party
        for m in members:
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

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.buttons.clear()
        self.cand_cards.clear()
        self.party_cards.clear()
        self._tooltips.clear()
        self._hot = False

        is_tavern = (self.title == "TAVERN")
        days_left = recruit.REFRESH_DAYS - (self.guild.clock.day - 1) % recruit.REFRESH_DAYS

        if self.tab == "recruits":
            sub = f"Guild size {len(self.guild.roster)} · crowd penalty -{recruit.size_penalty(len(self.guild.roster))}"
            if is_tavern:
                sub += f" · new faces in {days_left} day(s)"
            sub += self._sub_extra()
        elif self.tab == "perform":
            sub = "Play the stage with a Musical Instrument · every hour is a Charisma test"
        else:
            sub = "Rent a quiet room for the day · anyone with a study target will make daily progress"

        tabs_list = ["RECRUIT", "STUDY", "PERFORM"] if is_tavern else []
        active_tab_label = {"recruits": "RECRUIT", "rooms": "STUDY", "perform": "PERFORM"}[self.tab]
        header_rect = pygame.Rect(0, 0, W, 72)
        tab_hits = header(screen, F, header_rect, self.title if not is_tavern else "THE TAVERN",
                          sub, tabs_list, active_tab_label, mpos=self.mouse, has_tutorial=True)

        for tab_name, r in tab_hits.items():
            if tab_name == "RECRUIT" and self.tab != "recruits":
                self.buttons.append(("tab_recruits", r))
            elif tab_name == "STUDY" and self.tab != "rooms":
                self.buttons.append(("tab_rooms", r))
            elif tab_name == "PERFORM" and self.tab != "perform":
                self.buttons.append(("tab_perform", r))

        content_top = 88
        content_bottom = H - FOOTER_H - 12
        content_h = content_bottom - content_top

        if self.tab == "recruits":
            self._draw_recruits_master_detail(screen, content_top, content_h)
        elif self.tab == "rooms":
            self._draw_study_hub(screen, content_top, content_h)
        elif self.tab == "perform":
            self._draw_perform(screen, content_top, content_h)

        # Study target modal if active
        if self.study_modal_member is not None:
            self._draw_study_modal(screen)

        # Footer
        self._draw_footer(screen, F)

        # Draw any hovering tooltip
        for t_rect, t_text in self._tooltips:
            if t_rect.collidepoint(self.mouse):
                draw_tooltip(screen, F, t_text, self.mouse)
                break

    # ------------------------------------------------------------------ #
    def _draw_recruits_master_detail(self, screen, top, height):
        F = self._F
        W, H = screen.get_size()
        pad = T.S * 3

        # Left panel: candidate list
        left_w = 420
        left_rect = pygame.Rect(pad, top, left_w, height)
        panel(screen, left_rect)
        caps(screen, F["micro"], f"{self.LIST_LABEL} ({len(self.candidates)})",
             (left_rect.x + 16, left_rect.y + 12), T.TX_MUTED)

        if not self.candidates:
            text(screen, F["body_sm"], self.EMPTY_LIST,
                 (left_rect.x + 16, left_rect.y + 40), T.TX_FAINT)
        else:
            cy = left_rect.y + 36
            card_h = 124
            for i, cand in enumerate(self.candidates):
                cr = pygame.Rect(left_rect.x + 12, cy, left_w - 24, card_h)
                self.cand_cards.append((cr, i))
                sel = (i == self.sel)
                hov = cr.collidepoint(self.mouse)
                if hov:
                    self._hot = True

                bg = mix(T.BRASS, T.TABLE, 0.9) if sel else T.STEEL if hov else T.TABLE
                border = T.BRASS if sel else T.STEEL_HI if hov else T.STEEL_LINE
                pygame.draw.rect(screen, bg, cr, border_radius=4)
                pygame.draw.rect(screen, border, cr, 2 if sel else 1, border_radius=4)

                # Candidate token
                tok_c = (cr.x + 28, cr.y + 36)
                token_badge(screen, F, tok_c, cand, r=18)

                tx = cr.x + 58
                text(screen, F["bodyb"], cand.name, (tx, cr.y + 10), T.TX)
                caps(screen, F["micro"], f"{cand.race['name']} · {cand.occupation['name']}",
                     (tx, cr.y + 28), T.TX_MUTED)
                text(screen, F["body_sm"], f"Resists CHA {cand.mod_charisma:+} · Speaks {', '.join(cand.languages)}",
                     (cr.x + 12, cr.y + 48), T.TX_FAINT)
                bail = self._bail(cand)
                if bail:
                    caps(screen, F["microb"], f"BAIL {fmt_money(bail)}", (cr.right - 12, cr.y + 12),
                         T.BRASS, right=True)

                # Archetype badges
                tags = unit_archetypes(cand)
                tag_x = cr.x + 12
                for label, style, desc in tags[:3]:
                    tcol = ARCHETYPE_COLORS.get(style, T.TX_MUTED)
                    tw = F["microb"].size(label)[0] + 10
                    pill = pygame.Rect(tag_x, cr.y + 70, tw, 16)
                    pygame.draw.rect(screen, T.STEEL_HI, pill, border_radius=3)
                    pygame.draw.rect(screen, tcol, pill, 1, border_radius=3)
                    text(screen, F["microb"], label, pill.center, tcol, center=True)
                    if pill.collidepoint(self.mouse):
                        self._tooltips.append((pill, format_tooltip(label, desc, F)))
                    tag_x += tw + 6

                # Best pitch or blocked status
                best = self._best(cand)
                if cand.uid in self.last:
                    pitch, who = self.last[cand.uid]
                    st_col = T.GREEN if pitch.ok else T.BLOOD
                    st_label = "ENLISTED" if pitch.ok else self.REJECTED_LABEL
                elif best is not None:
                    st_label = f"PITCH OPEN ({best[0].name})"
                    st_col = T.GREEN
                else:
                    st_label = "CANNOT PITCH"
                    st_col = T.BLOOD

                caps(screen, F["microb"], st_label, (cr.x + 12, cr.bottom - 18), st_col)

                badge_label = "SELECTED" if sel else "INSPECT"
                b_col = T.BRASS if sel else T.TX_MUTED
                caps(screen, F["microb"], badge_label, (cr.right - 12, cr.bottom - 18), b_col, right=True)

                cy += card_h + 8

        # Right panel: dossier & recruiter selection
        right_x = left_rect.right + 16
        right_w = W - pad - right_x
        right_rect = pygame.Rect(right_x, top, right_w, height)
        panel(screen, right_rect)

        if self.sel is None or self.sel >= len(self.candidates):
            text(screen, F["body"], "Select a candidate from the left to view their dossier and make a pitch.",
                 (right_rect.x + 24, right_rect.y + 24), T.TX_FAINT)
            return

        cand = self.candidates[self.sel]
        caps(screen, F["micro"], "SELECTED CANDIDATE DOSSIER", (right_rect.x + 20, right_rect.y + 12), T.TX_MUTED)

        # Candidate banner
        cx = right_rect.x + 20
        cy = right_rect.y + 36
        token_badge(screen, F, (cx + 30, cy + 30), cand, r=28)

        tx = cx + 72
        text(screen, F["head"], cand.name, (tx, cy), T.TX)
        caps(screen, F["micro"], f"{cand.race['name'].upper()} · {cand.occupation['name'].upper()} · ALIGNMENT: {cand.alignment.upper()}",
             (tx, cy + 28), T.BRASS)

        cy += 70
        vit_str = f"HP {cand.hp_max}   AC {cand.ac}   Speed {cand.speed} squares   Attack: {cand.weapon_name or 'Unarmed'}"
        text(screen, F["bodyb"], vit_str, (cx, cy), T.TX)
        cy += 24
        bail = self._bail(cand)
        if bail:
            text(screen, F["bodyb"], f"Bail: {fmt_money(bail)}  ·  party holds {fmt_money(self._wealth())}", (cx, cy),
                 T.BRASS if self._wealth() >= bail else T.BLOOD)
            cy += 24
        text(screen, F["body_sm"], f"Racial Ability: {cand.ability.name} — {cand.ability.effect}", (cx, cy), T.TX_MUTED)
        cy += 24

        # Candidate archetypes in dossier
        tags = unit_archetypes(cand)
        if tags:
            caps(screen, F["micro"], "ARCHETYPES:", (cx, cy + 3), T.TX_MUTED)
            atx = cx + 84
            for label, style, desc in tags:
                tcol = ARCHETYPE_COLORS.get(style, T.TX_MUTED)
                tw = F["microb"].size(label)[0] + 12
                pill = pygame.Rect(atx, cy, tw, 18)
                pygame.draw.rect(screen, T.STEEL_HI, pill, border_radius=3)
                pygame.draw.rect(screen, tcol, pill, 1, border_radius=3)
                text(screen, F["microb"], label, pill.center, tcol, center=True)
                if pill.collidepoint(self.mouse):
                    self._tooltips.append((pill, format_tooltip(label, desc, F)))
                atx += tw + 6
            cy += 26
        else:
            cy += 6

        hline(screen, right_rect.x + 20, right_rect.right - 20, cy)
        cy += 14

        # Recruiter list
        caps(screen, F["micro"], "SELECT WHO MAKES THE PITCH (GUILD RECRUITER):", (cx, cy), T.TX_MUTED)
        cy += 20

        rw = right_w - 40
        for m in self.party:
            mr = pygame.Rect(cx, cy, rw, 56)
            self.party_cards.append((mr, m))
            is_recruiter = (self.selected_recruiter == m)
            m_hov = mr.collidepoint(self.mouse)
            if m_hov:
                self._hot = True

            rbg = mix(T.BRASS, T.TABLE, 0.9) if is_recruiter else T.STEEL if m_hov else T.TABLE
            rborder = T.BRASS if is_recruiter else T.STEEL_HI if m_hov else T.STEEL_LINE
            pygame.draw.rect(screen, rbg, mr, border_radius=4)
            pygame.draw.rect(screen, rborder, mr, 2 if is_recruiter else 1, border_radius=4)

            # Recruiter token
            token_badge(screen, F, (mr.x + 26, mr.centery), m, r=16)

            rtx = mr.x + 52
            text(screen, F["bodyb"], m.name, (rtx, mr.y + 8), T.TX)

            free_slots = recruit.slots_free(self.guild, m)
            slot_col = T.BLOOD if free_slots <= 0 else T.TX_MUTED
            caps(screen, F["micro"], f"CHA {m.mod_charisma:+} · Speaks: {', '.join(m.languages)}",
                 (rtx, mr.y + 30), T.TX_MUTED)

            # Eligibility / Odds
            if free_slots <= 0:
                cond_text, cond_col = "NO RECRUITMENT SLOTS (0)", T.BLOOD
            elif self._barred(cand, m):
                cond_text, cond_col = "ALREADY TRIED THIS WEEK", T.BLOOD
            elif not recruit.can_pitch(m, cand):
                cond_text, cond_col = "NO SHARED LANGUAGE", T.BLOOD
            else:
                cond_text = f"PITCH: 1d20{self._net(m, cand):+} vs 1d20{cand.mod_charisma:+}"
                cond_col = T.GREEN

            caps(screen, F["microb"], cond_text, (mr.right - 14, mr.centery - 6), cond_col, right=True)
            cy += 64

        # Action Pitch Button
        can_pitch = False
        if self.selected_recruiter is not None:
            can_pitch = (recruit.can_pitch(self.selected_recruiter, cand)
                         and not self._barred(cand, self.selected_recruiter)
                         and recruit.slots_free(self.guild, self.selected_recruiter) > 0)

        cy += 8
        btn_rect = pygame.Rect(cx, cy, rw, 42)
        bail = self._bail(cand)
        btn_label = (f"PAY {bail} CP BAIL AND CONVINCE (ROLL CHARISMA)" if bail
                     else "CONVINCE TO JOIN GUILD (ROLL CHARISMA)")
        if bail and can_pitch and self._wealth() < bail:
            can_pitch, btn_label = False, f"CANNOT AFFORD THE {bail} CP BAIL"
        elif self.selected_recruiter is not None and not can_pitch:
            if recruit.slots_free(self.guild, self.selected_recruiter) <= 0:
                btn_label = "RECRUITER CANNOT PITCH (NO RECRUITMENT SLOTS)"
            elif self._barred(cand, self.selected_recruiter):
                btn_label = "RECRUITER CANNOT PITCH (ALREADY TRIED)"
            elif not recruit.can_pitch(self.selected_recruiter, cand):
                btn_label = "RECRUITER CANNOT PITCH (NO COMMON LANGUAGE)"

        self.add_button(screen, btn_rect, "convince", btn_label, primary=True, enabled=can_pitch)

        hint = hint_col = None
        if not self._eligible(cand):
            hint, hint_col = recruit.pitch_block_reason(
                self.guild, self.party, cand, lambda g, c, m: self._barred(c, m)), T.BLOOD
        elif can_pitch:
            hint, hint_col = recruit.overflow_warning(self.guild, self.selected_recruiter), T.BRASS
        if hint:
            text(screen, F["body_sm"], hint[0].upper() + hint[1:], (btn_rect.x, btn_rect.bottom + 8), hint_col)

    # ------------------------------------------------------------------ #
    def _draw_study_hub(self, screen, top, height):
        F = self._F
        W, H = screen.get_size()
        pad = T.S * 3

        area = pygame.Rect(pad, top, W - 2 * pad, height)
        panel(screen, area)

        # Header area: Garrison order status and room cost
        cost = economy.TAVERN_STUDY_COST_PER_DAY
        studiers = sum(1 for m in self.party if m.study_target)
        total_cost = studiers * cost

        caps(screen, F["micro"], "ROOMS & STUDY GARRISON", (area.x + 20, area.y + 14), T.TX_MUTED)

        cx = area.x + 20
        cy = area.y + 36
        text(screen, F["bodyb"], f"Daily Study Rent: {fmt_money(cost)} per studying member ({fmt_money(total_cost)} per day now)", (cx, cy), T.TX)
        text(screen, F["body_sm"], "Only members with a study target pay rent and roll daily progress (Intelligence modifier).",
             (cx, cy + 22), T.TX_MUTED)

        # Rent button / Status
        btn_w = 260
        btn_r = pygame.Rect(area.right - 20 - btn_w, area.y + 28, btn_w, 38)
        if self.group is None:
            caps(screen, F["micro"], "PARTY NOT GARRISONED HERE", (btn_r.right, btn_r.centery - 6), T.TX_FAINT, right=True)
        else:
            is_studying = (self.group.order is not None and self.group.order.kind == "garrison"
                           and self.group.order.job == "study")
            if is_studying:
                caps(screen, F["microb"], "CURRENTLY STUDYING", (btn_r.x - 16, btn_r.centery - 6), T.GREEN, right=True)
                self.add_button(screen, btn_r, "cancel_study", "CANCEL STUDY ORDER", primary=False)
            else:
                self.add_button(screen, btn_r, "rent_study", "RENT ROOMS (STUDY)", primary=True)

        cy += 60
        hline(screen, area.x + 20, area.right - 20, cy)
        cy += 16

        # Party roster study cards
        caps(screen, F["micro"], "PARTY MEMBERS STUDY ROSTER", (cx, cy), T.TX_MUTED)
        cy += 20

        rw = area.w - 40
        card_h = 76
        for i, m in enumerate(self.party):
            mr = pygame.Rect(cx, cy, rw, card_h)
            hov = mr.collidepoint(self.mouse)
            if hov:
                self._hot = True

            pygame.draw.rect(screen, T.STEEL if hov else T.TABLE, mr, border_radius=4)
            pygame.draw.rect(screen, T.STEEL_HI if hov else T.STEEL_LINE, mr, 1, border_radius=4)

            # Character token
            token_badge(screen, F, (mr.x + 28, mr.centery), m, r=20)

            # Left stats
            tx = mr.x + 60
            text(screen, F["bodyb"], m.name, (tx, mr.y + 12), T.TX)
            magic_tag = f"Magic: {m.magic_source.capitalize()}" if m.magic_source else "No Magic Affinity"
            caps(screen, F["micro"], f"{m.race['name']} · {m.occupation['name']} · INT {m.mod_intelligence:+} · {magic_tag} · {fmt_money(m.money)}",
                 (tx, mr.y + 36), T.TX_MUTED)

            # Middle: Study target progress
            mid_x = mr.x + 340
            if m.study_target:
                if m.study_target in magic.SPELLS:
                    spell = magic.SPELLS[m.study_target]
                    t_name = f"Scroll of {spell.name}"
                    needed = magic.points_to_learn(spell.level)
                else:
                    t_name = f"Dictionary of {m.study_target}"
                    needed = magic.points_to_learn(0)

                caps(screen, F["micro"], f"STUDYING: {t_name.upper()}", (mid_x, mr.y + 14), T.BRASS)

                # Progress bar
                bw = 180
                bar_r = pygame.Rect(mid_x, mr.y + 36, bw, 8)
                pygame.draw.rect(screen, T.TABLE, bar_r)
                pygame.draw.rect(screen, T.STEEL_LINE, bar_r, 1)

                frac = min(1.0, max(0.0, m.study_progress / max(1, needed)))
                if frac > 0:
                    fill_r = pygame.Rect(bar_r.x, bar_r.y, round(bw * frac), 8)
                    pygame.draw.rect(screen, T.BRASS, fill_r)

                text(screen, F["micro"], f"{m.study_progress} / {needed} pts", (bar_r.right + 12, mr.y + 32), T.TX_MUTED)

                # Buttons
                btn_w = 110
                r_btn = pygame.Rect(mr.right - btn_w - 12, mr.y + 20, btn_w, 36)
                self.add_button(screen, r_btn, f"choose_target_{i}", "CHANGE")

                r_stop = pygame.Rect(mr.right - btn_w * 2 - 20, mr.y + 20, btn_w, 36)
                self.add_button(screen, r_stop, f"stop_study_{i}", "STOP")
            else:
                caps(screen, F["micro"], "NO STUDY TARGET SET", (mid_x, mr.y + 16), T.TX_MUTED)
                text(screen, F["body_sm"], "Idle during study hours (earns no progress)", (mid_x, mr.y + 36), T.TX_FAINT)

                btn_w = 140
                r_btn = pygame.Rect(mr.right - btn_w - 12, mr.y + 20, btn_w, 36)
                self.add_button(screen, r_btn, f"choose_target_{i}", "SET TARGET")

            cy += card_h + 10

    # ------------------------------------------------------------------ #
    def _draw_perform(self, screen, top, height):
        F = self._F
        W, H = screen.get_size()
        pad = T.S * 3
        area = pygame.Rect(pad, top, W - 2 * pad, height)
        panel(screen, area)

        caps(screen, F["micro"], "THE STAGE", (area.x + 20, area.y + 14), T.TX_MUTED)
        cx, cy = area.x + 20, area.y + 36
        text(screen, F["bodyb"],
             f"Every hour on stage is a Charisma test (d20 + modifier): beat {economy.PERFORM_TIP_BASE} and the crowd tips.",
             (cx, cy), T.TX)
        text(screen, F["body_sm"],
             f"Needs a {economy.PERFORM_ITEM} in the pack. Every {economy.PERFORM_TIP_STEP} points over {economy.PERFORM_TIP_BASE} is one more coin.",
             (cx, cy + 22), T.TX_MUTED)
        cy += 56

        caps(screen, F["micro"], "SHOW LENGTH", (cx, cy + 10), T.TX_MUTED)
        bx = cx + 110
        for h in economy.PERFORM_SHIFT_HOURS:
            self.add_button(screen, pygame.Rect(bx, cy, 72, 32), f"perf_hours_{h}", f"{h} H",
                            primary=h == self.perform_hours, enabled=h != self.perform_hours)
            bx += 80
        crew = self._performers()
        go_r = pygame.Rect(area.right - 20 - 260, cy - 4, 260, 38)
        self.add_button(screen, go_r, "perform_go", f"PLAY {self.perform_hours} H", primary=True,
                        enabled=bool(crew))
        cy += 48
        hline(screen, area.x + 20, area.right - 20, cy)
        cy += 16

        caps(screen, F["micro"], "PERFORMERS", (cx, cy), T.TX_MUTED)
        cy += 20
        rw, card_h = area.w - 40, 64
        for i, m in enumerate(self.party):
            mr = pygame.Rect(cx, cy, rw, card_h)
            has = economy.can_perform(m)
            on = has and m not in self.perform_off
            hov = mr.collidepoint(self.mouse)
            if has:
                self.buttons.append((f"perf_toggle_{i}", mr))
                if hov:
                    self._hot = True
            bg = mix(T.BRASS, T.TABLE, 0.9) if on else T.STEEL if hov and has else T.TABLE
            pygame.draw.rect(screen, bg, mr, border_radius=4)
            pygame.draw.rect(screen, T.BRASS if on else T.STEEL_LINE, mr, 2 if on else 1, border_radius=4)
            token_badge(screen, F, (mr.x + 28, mr.centery), m, r=18)
            tx = mr.x + 60
            text(screen, F["bodyb"], m.name, (tx, mr.y + 10), T.TX)
            caps(screen, F["micro"], f"{m.race['name']} · {m.occupation['name']} · CHA {m.mod_charisma:+}",
                 (tx, mr.y + 36), T.TX_MUTED)
            if not has:
                caps(screen, F["microb"], f"NO {economy.PERFORM_ITEM.upper()}", (mr.right - 14, mr.centery - 6),
                     T.TX_FAINT, right=True)
            else:
                tips = economy.perform_expected(self.perform_hours, m.mod_charisma)
                label = f"TIPS ~{fmt_money(round(tips, 1))} AVG" if on else "SITTING OUT"
                col = (T.GREEN if tips else T.TX_MUTED) if on else T.TX_FAINT
                caps(screen, F["microb"], label, (mr.right - 14, mr.centery - 6), col, right=True)
            cy += card_h + 8

    # ------------------------------------------------------------------ #
    def _draw_study_modal(self, screen):
        F = self._F
        W, H = screen.get_size()
        student = self.study_modal_member
        self.modal_buttons.clear()

        # Dim backdrop
        backdrop = pygame.Surface((W, H), pygame.SRCALPHA)
        backdrop.fill((0, 0, 0, 160))
        screen.blit(backdrop, (0, 0))

        # Modal dialog card
        dialog_w, dialog_h = 640, 480
        dialog = pygame.Rect((W - dialog_w) // 2, (H - dialog_h) // 2, dialog_w, dialog_h)
        panel(screen, dialog)
        pygame.draw.rect(screen, T.BRASS, dialog, 1, border_radius=4)

        cx = dialog.x + 24
        cy = dialog.y + 20
        caps(screen, F["micro"], "STUDY MATERIAL SELECTION", (cx, cy), T.BRASS)
        cy += 20
        text(screen, F["head"], f"Study for {student.name}", (cx, cy), T.TX)
        cy += 28
        text(screen, F["body_sm"], "Select any scroll or dictionary carried by the party to begin daily study.", (cx, cy), T.TX_MUTED)
        cy += 32
        hline(screen, dialog.x + 20, dialog.right - 20, cy)
        cy += 16

        options = self._available_study_options(student)
        if not options:
            if not student.magic_source:
                text(screen, F["body"], f"{student.name} has no magical affinity and carries no unlearned dictionaries.", (cx, cy + 20), T.TX)
            else:
                text(screen, F["body"], "No eligible scrolls or dictionaries carried by the party.", (cx, cy + 20), T.TX)
            text(screen, F["body_sm"],
                 "• Scrolls require matching magical affinity to study.\n• Dictionaries teach foreign languages.\n• Buy paper & ink to write dictionaries at the Library or find scrolls in ruins.",
                 (cx, cy + 50), T.TX_FAINT)
        else:
            rw = dialog_w - 48
            for opt in options[:4]:
                opt_r = pygame.Rect(cx, cy, rw, 56)
                hov = opt_r.collidepoint(self.mouse)
                if hov:
                    self._hot = True

                pygame.draw.rect(screen, T.STEEL if hov else T.TABLE, opt_r, border_radius=4)
                pygame.draw.rect(screen, T.BRASS if hov else T.STEEL_LINE, opt_r, 1, border_radius=4)

                text(screen, F["bodyb"], opt["name"], (opt_r.x + 14, opt_r.y + 10), T.TX)
                text(screen, F["body_sm"], opt["desc"], (opt_r.x + 14, opt_r.y + 30), T.TX_MUTED)

                btn_w = 90
                action_r = pygame.Rect(opt_r.right - btn_w - 10, opt_r.y + 12, btn_w, 32)
                draw_button(screen, F, action_r, "SELECT", primary=hov, mpos=self.mouse)
                self.modal_buttons.append(("set_target", opt_r, opt))

                cy += 64

        # Modal bottom buttons
        by = dialog.bottom - 52
        if student.study_target:
            clear_r = pygame.Rect(cx, by, 180, 36)
            draw_button(screen, F, clear_r, "STOP STUDYING", danger=True, mpos=self.mouse)
            self.modal_buttons.append(("clear_target", clear_r, None))

        cancel_r = pygame.Rect(dialog.right - 24 - 120, by, 120, 36)
        draw_button(screen, F, cancel_r, "CANCEL", mpos=self.mouse)
        self.modal_buttons.append(("cancel", cancel_r, None))

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen, F):
        col = T.GREEN if (self.notice and ("signs" in self.notice or "begins" in self.notice)) else T.TX_MUTED
        if self.notice and ("lost" in self.notice or "Not enough" in self.notice):
            col = T.BLOOD
        btn_label = self._leave_label()
        footer_bar(self, screen, F, primary=("done", btn_label),
                   notice=self.notice, notice_color=col)

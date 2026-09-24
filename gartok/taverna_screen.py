"""Taverna: talk a stranger into joining the guild.

The strangers drinking here are the guild's weekly pool (`recruit.refresh_pool`
-- same faces every visit until seven days pass, then a fresh set). Pick one,
then pick the party member who makes the pitch: `recruit.convince` rolls that
member's Charisma against the stranger's, docked for opposite alignment and for
how crowded the guild already is; a tie goes to the stranger.

Win and they sign on (bound to the recruiter via `recruited_by`, and out of the
pool). Lose and that recruiter is barred from pitching that same stranger until
the pool turns over -- another member can still try.

No money changes hands: a signing bonus would just land in the recruit's own
pack. `on_done` returns to the map (which autosaves).
"""

import pygame

from . import economy, orders, recruit, magic
from .data import alignment_distance
from .screen import Screen
from .theme import (ACCENT, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE, LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, panel, section,
                    token_badge, text, tracked, wrap_lines)
from .ui.tokens import T
from .ui.combat_card import draw_combat_card, draw_party_row
from .widgets import ButtonsMixin, footer_bar

CANDIDATES = 3          # layout width; the live pool may hold fewer after a hire


class TavernaScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, party, node, on_done, candidates=None, title=None, group=None):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.party = party
        self.group = group                    # backing Group, for the rooms/study order (None if not applicable)
        self.node = node
        self.on_done = on_done
        self.candidates = list(candidates) if candidates is not None else recruit.refresh_pool(guild)
        self.title = title or "TAVERN"
        self.sel = None                       # index of the stranger being pitched, or None
        self.last = {}                         # candidate uid -> (recruit.Pitch, member) of the last try
        self.notice = None
        self.cand_cards = []                 # [(rect, index)]
        self.party_cards = []                # [(rect, member)]
        self.buttons = []                   # [(key, rect)]
        self._hot = False
        self.tab = "recruits"               # "recruits" or "rooms"

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "taverna"

    # ------------------------------------------------------------------ #
    def _eligible(self, cand):
        """Party members who could still pitch `cand` (share a tongue, not yet
        barred for failing on them this week, and still have room to sponsor
        someone new)."""
        return [m for m in self.party
                if recruit.can_pitch(m, cand) and not recruit.barred(self.guild, cand, m)
                and recruit.slots_free(self.guild, m) > 0]

    def _best(self, cand):
        """(member, net modifier) for the strongest pitch still open, or None."""
        pen = recruit.size_penalty(len(self.guild.roster))
        def _dist(m):
            raw = alignment_distance(m.alignment, cand.alignment)
            return max(0, raw - int(m.talent_bonus("align_distance_reduction")))
        opts = [(m, m.mod_charisma
                 - recruit.ALIGNMENT_PENALTY * _dist(m)
                 - pen
                 + m.talent_bonus("recruit_cha"))
                for m in self._eligible(cand)]
        return max(opts, key=lambda t: t[1]) if opts else None

    # ------------------------------------------------------------------ #
    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "done":
                    self.on_done()
                elif key == "tab_recruits":
                    self.tab = "recruits"
                    self.sel = None
                elif key == "tab_rooms":
                    self.tab = "rooms"
                    self.sel = None
                elif key == "rent_study" and self.group is not None:
                    self.group.order = orders.garrison("study")
                return

        if self.tab == "recruits":
            if self.sel is None:
                for rect, i in self.cand_cards:
                    if rect.collidepoint(px):
                        self.sel = i
                        self.notice = None
                        return
                return

            for rect, member in self.party_cards:
                if rect.collidepoint(px):
                    self._pitch(member)
                    return
            for rect, i in self.cand_cards:        # click another stranger: switch the pitch
                if rect.collidepoint(px):
                    self.sel = i
                    return
            self.sel = None                       # clicked nowhere useful: cancel

    def _pitch(self, member):
        cand = self.candidates[self.sel]
        if not recruit.can_pitch(member, cand):
            self.notice = f"{member.name} and {cand.name} share no language."
            return
        if recruit.barred(self.guild, cand, member):
            self.notice = f"{member.name} already tried {cand.name} this week."
            return
        if recruit.slots_free(self.guild, member) <= 0:
            self.notice = f"{member.name} has no room to sponsor anyone else."
            return
        pitch = recruit.convince(member, cand, len(self.guild.roster), day=self.guild.clock.day)
        self.last[cand.uid] = (pitch, member)
        if pitch.ok:
            recruit.enlist(self.guild, cand, member)
            if cand in self.candidates:            # enlist() may already have removed it,
                self.candidates.remove(cand)       # when self.candidates IS guild.taverna_pool
            self.notice = f"{cand.name} signs with the guild (recruited by {member.name})."
        else:
            recruit.bar(self.guild, cand, member)
            self.notice = f"{cand.name} turns {member.name} down. They can only try again next week."
        self.sel = None

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self.cand_cards = []
        self.party_cards = []
        self._reset_buttons()

        text(screen, self.title, f.title, INK, (MARGIN, MARGIN - 2))

        is_tavern = self.title == "TAVERN"
        days_left = recruit.REFRESH_DAYS - (self.guild.clock.day - 1) % recruit.REFRESH_DAYS
        if self.tab == "recruits":
            if self.sel is not None:
                cand = self.candidates[self.sel]
                sub, col = (f"pitching {cand.name}  ·  click who from the party speaks  ·  "
                            "click outside to cancel", ACCENT)
            else:
                sub, col = (f"guild of {len(self.guild.roster)}  ·  size penalty "
                            f"-{recruit.size_penalty(len(self.guild.roster))}", INK_DIM)
                if is_tavern:
                    sub += f"  ·  new faces in {days_left} day(s)"
        else:
            sub, col = ("rent a quiet room for the day  ·  anyone with a study target will make progress", INK_DIM)
        
        text(screen, sub, f.body, col, (MARGIN, MARGIN + 36))

        y = MARGIN + 64
        if is_tavern:
            # Tabs
            tr_rect = pygame.Rect(MARGIN, y, 120, 30)
            tr_hov = tr_rect.collidepoint(self.mouse)
            tr_on = self.tab == "recruits"
            panel(screen, tr_rect, fill=SURFACE_3 if tr_on else (SURFACE_2 if tr_hov else SURFACE_1),
                  border=ACCENT if tr_on else LINE, width=2 if tr_on else 1, radius=4)
            text(screen, "RECRUITS", f.label, ACCENT if tr_on else INK_DIM, tr_rect.center, center=True)
            self.buttons.append(("tab_recruits", tr_rect))
    
            room_rect = pygame.Rect(MARGIN + 130, y, 120, 30)
            rm_hov = room_rect.collidepoint(self.mouse)
            rm_on = self.tab == "rooms"
            panel(screen, room_rect, fill=SURFACE_3 if rm_on else (SURFACE_2 if rm_hov else SURFACE_1),
                  border=ACCENT if rm_on else LINE, width=2 if rm_on else 1, radius=4)
            text(screen, "ROOMS", f.label, ACCENT if rm_on else INK_DIM, room_rect.center, center=True)
            self.buttons.append(("tab_rooms", room_rect))
            
            y += 45

        if self.tab == "recruits":
            self._draw_recruits(screen, y)
        elif self.tab == "rooms":
            self._draw_rooms(screen, y)

        self._draw_footer(screen)

    def _draw_recruits(self, screen, top):
        f = self.fonts
        party_h = 120
        gap = SP3
        cand_h = screen.get_height() - top - party_h - gap - 80
        cw = (screen.get_width() - 2 * MARGIN - (CANDIDATES - 1) * gap) // CANDIDATES

        if not self.candidates:
            text(screen, "No one looking for work right now. Come back when the crowd changes.",
                 f.body, INK_DIM, (MARGIN, top + 20))
        for i, cand in enumerate(self.candidates):
            rect = pygame.Rect(MARGIN + i * (cw + gap), top, cw, cand_h)
            self._draw_candidate(screen, rect, i, cand)
            self.cand_cards.append((rect, i))

        py = top + cand_h + gap
        self._draw_party(screen, pygame.Rect(MARGIN, py, screen.get_width() - 2 * MARGIN, party_h))

    def _draw_rooms(self, screen, top):
        f = self.fonts

        W, H = screen.get_width(), screen.get_height()
        area = pygame.Rect(MARGIN, top, W - 2 * MARGIN, H - top - 80)
        panel(screen, area, fill=SURFACE_1, border=LINE, radius=RADIUS)

        cost = economy.TAVERN_STUDY_COST_PER_DAY
        total_cost = len(self.party) * cost

        y = area.y + SP3
        text(screen, f"cost: {cost} copper per member / day (total: {total_cost} copper)", f.body, INK, (area.x + SP3, y))
        y += 30

        text(screen, "STUDY TARGETS:", f.label, INFO, (area.x + SP3, y))
        y += 20

        studying_count = 0
        for m in self.party:
            if m.study_target:
                studying_count += 1
                text(screen, f"{m.name}", f.body_bd, INK, (area.x + SP3, y))
                text(screen, f"studying {m.study_target}", f.body, ACCENT, (area.x + SP3 + 120, y))
                
                target_level = 0
                if m.study_target in magic.SPELLS:
                    target_level = magic.SPELLS[m.study_target].level
                total_needed = magic.points_to_learn(target_level)
                
                text(screen, f"{m.study_progress} / {total_needed} points", f.mono_sm, INK_DIM, (area.x + SP3 + 320, y))
                y += 24

        if studying_count == 0:
            text(screen, "no one has a study target set (select a scroll or dictionary in the character sheet)",
                 f.body, INK_FAINT, (area.x + SP3, y))
            y += 24

        y += SP3
        if self.group is None:
            text(screen, "this party isn't garrisoned here -- no rooms to rent.",
                 f.body, INK_FAINT, (area.x + SP3, y))
            return

        btn_rect = pygame.Rect(area.x + SP3, y, 200, 36)
        is_studying = (self.group.order is not None and self.group.order.kind == "garrison"
                       and self.group.order.job == "study")

        if is_studying:
            panel(screen, btn_rect, fill=SURFACE_3, border=OK, width=2, radius=RADIUS)
            text(screen, "STUDYING", f.body_bd, OK, btn_rect.center, center=True)
        else:
            self.add_button(screen, btn_rect, "rent_study", "RENT ROOMS (STUDY)")

    # ------------------------------------------------------------------ #
    def _draw_candidate(self, screen, rect, i, cand):
        f = self.fonts
        last = self.last.get(cand.uid)
        picking = self.sel == i
        hov = rect.collidepoint(self.mouse) and self.sel is None
        
        ch = {
            "name": cand.name,
            "race": cand.race["name"],
            "occ": cand.occupation["name"],
            "hp": cand.hp_max,
            "hp_max": cand.hp_max,
            "ac": cand.ac,
            "spd": cand.speed,
            "weapon": cand.weapon_name or "unarmed",
            "dmg": ""
        }
        
        extra = [
            ("RESISTANCE", f"CHA {cand.mod_charisma:+}", T.BRASS),
            ("SPEAKS", ", ".join(cand.languages), T.TX_MUTED),
            ("ABILITY", cand.ability.name, T.TX),
        ]
        
        for ln in wrap_lines([cand.ability.effect], f.body_sm, rect.w - T.S * 6)[:3]:
            extra.append((None, ln, T.TX_FAINT))
            
        if last is not None:
            pitch, who = last
            extra.append(("LAST ATTEMPT", f"{who.name}: {pitch.recruiter_roll} + mods = {pitch.recruiter_total}", T.GREEN if pitch.ok else T.BLOOD))
            extra.append((None, f"vs resistance {pitch.candidate_total} ({pitch.candidate_roll} + CHA)", T.TX_MUTED))
            for val, label in pitch.modifiers:
                extra.append((None, f"{val:+}  {label}", T.BLOOD))
                
        best = self._best(cand)
        if best is not None:
            m, net = best
            extra.append(("PITCH", f"{m.name}  ·  CHA check {net:+}", T.GREEN))
            extra.append((None, f"(1d20{net:+} must beat 1d20 {cand.mod_charisma:+})", T.TX_FAINT))
        else:
            reason = recruit.pitch_block_reason(self.guild, self.party, cand)
            extra.append(("PITCH", reason or "cannot recruit", T.BLOOD))
            
        mark = ("CLICK TO PITCH" if best is not None else "CLICK TO INSPECT") if self.sel is None else "CLICK A PARTY MEMBER"
        
        tooltips, _ = draw_combat_card(screen, rect, ch, action=mark, hovered=hov, selected=picking, extra_lines=extra)
        
        # Tooltip for attributes
        for t_rect, t_text in tooltips:
            if t_rect.collidepoint(self.mouse):
                tw, th = f.body_sm.size(t_text)
                tt_rect = pygame.Rect(self.mouse[0] + 12, self.mouse[1] + 12, tw + 16, th + 8)
                panel(screen, tt_rect, fill=SURFACE_1, border=LINE_SOFT, radius=2)
                text(screen, t_text, f.body_sm, INK, (tt_rect.x + 8, tt_rect.y + 4))
                break

    # ------------------------------------------------------------------ #
    def _draw_party(self, screen, area):
        f = self.fonts
        tracked(screen, "YOUR PARTY", f.label, INFO, (area.x, area.y - 16))
        panel(screen, area, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
        n = max(1, len(self.party))
        gap = SP2
        cw = (area.w - 2 * SP3 - (n - 1) * gap) // n
        for i, m in enumerate(self.party):
            r = pygame.Rect(area.x + SP3 + i * (cw + gap), area.y + SP2, cw, area.h - 2 * SP2)
            self._draw_party_card(screen, r, m)
            self.party_cards.append((r, m))

    def _draw_party_card(self, screen, r, m):
        f = self.fonts
        cand = self.candidates[self.sel] if self.sel is not None else None
        free = recruit.slots_free(self.guild, m)
        state = None
        
        if cand is not None:
            if recruit.barred(self.guild, cand, m):
                state = ("TRIED", T.BLOOD)
            elif not recruit.can_pitch(m, cand):
                state = ("NO LANGUAGE", T.BLOOD)
            elif free <= 0:
                state = ("FULL", T.BLOOD)
            else:
                state = ("CAN SPEAK", T.GREEN)
                
        hov = r.collidepoint(self.mouse) and self.sel is not None
        
        ch = {
            "name": m.name,
            "cha": m.mod_charisma,
            "langs": m.languages,
            "free": free
        }
        
        draw_party_row(screen, r, ch, state=state, hovered=hov)
        
        if r.collidepoint(self.mouse):
            cap = recruit.capacity(self.guild, m)
            used = recruit.slots_used(self.guild, m)
            calc_str = "Cap: 1 (base)"
            if m.mod_charisma != 0: calc_str += f" {m.mod_charisma:+} (CHA)"
            if m is self.guild.leader: calc_str += f" + {m.racial_level} (ldr)"
            calc_str += f" = {cap}  |  Used: {used}"
            
            tw, th = f.body_sm.size(calc_str)
            tt_rect = pygame.Rect(self.mouse[0] + 12, self.mouse[1] + 12, tw + 16, th + 8)
            panel(screen, tt_rect, fill=SURFACE_1, border=LINE_SOFT, radius=2)
            text(screen, calc_str, f.body_sm, INK, (tt_rect.x + 8, tt_rect.y + 4))

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen):
        col = OK if (self.notice and "signs" in self.notice) else INFO
        btn_label = "LEAVE THE TAVERN" if self.title == "TAVERN" else "DONE"
        footer_bar(self, screen, primary=("done", btn_label),
                  notice=self.notice, notice_color=col)

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

from . import recruit
from .data import alignment_distance
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, panel, section,
                    token_badge, text, tracked, wrap_lines)

CANDIDATES = 3          # layout width; the live pool may hold fewer after a hire


class TavernaScreen(Screen):
    native = True

    def __init__(self, fonts, guild, party, node, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.party = party
        self.node = node
        self.on_done = on_done
        self.candidates = recruit.refresh_pool(guild)   # live list on the guild
        self.sel = None                       # index of the stranger being pitched, or None
        self.last = {}                         # candidate uid -> (recruit.Pitch, member) of the last try
        self.notice = None
        self.cand_cards = []                 # [(rect, index)]
        self.party_cards = []                # [(rect, member)]
        self.buttons = []                   # [(key, rect)]

    # ------------------------------------------------------------------ #
    def _eligible(self, cand):
        """Party members who could still pitch `cand` (share a tongue, not yet
        barred for failing on them this week)."""
        return [m for m in self.party
                if recruit.can_pitch(m, cand) and not recruit.barred(self.guild, cand, m)]

    def _best(self, cand):
        """(member, net modifier) for the strongest pitch still open, or None."""
        pen = recruit.size_penalty(len(self.guild.roster))
        opts = [(m, m.mod_charisma
                 - recruit.ALIGNMENT_PENALTY * alignment_distance(m.alignment, cand.alignment)
                 - pen
                 + m.talent_bonus("recruit_cha"))
                for m in self._eligible(cand)]
        return max(opts, key=lambda t: t[1]) if opts else None

    # ------------------------------------------------------------------ #
    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px) and key == "done":
                self.on_done()
                return

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
        pitch = recruit.convince(member, cand, len(self.guild.roster))
        self.last[cand.uid] = (pitch, member)
        if pitch.ok:
            recruit.enlist(self.guild, cand, member)
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
        self.buttons = []

        text(screen, "TAVERN", f.title, INK, (MARGIN, MARGIN - 2))
        days_left = recruit.REFRESH_DAYS - (self.guild.clock.day - 1) % recruit.REFRESH_DAYS
        if self.sel is not None:
            cand = self.candidates[self.sel]
            sub, col = (f"pitching {cand.name}  ·  click who from the party speaks  ·  "
                        "click outside to cancel", ACCENT)
        else:
            sub, col = (f"guild of {len(self.guild.roster)}  ·  size penalty "
                        f"-{recruit.size_penalty(len(self.guild.roster))}  ·  "
                        f"new faces in {days_left} day(s)", INK_DIM)
        text(screen, sub, f.body, col, (MARGIN, MARGIN + 30))

        top = MARGIN + 68
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
        self._draw_footer(screen)

    # ------------------------------------------------------------------ #
    def _draw_candidate(self, screen, rect, i, cand):
        f = self.fonts
        pad = SP3
        last = self.last.get(cand.uid)
        picking = self.sel == i
        open_pitch = self._eligible(cand)

        hovering = rect.collidepoint(self.mouse) and self.sel is None
        border = ACCENT if (picking or hovering) else LINE_SOFT
        panel(screen, rect, fill=SURFACE_2, border=border,
              width=2 if border != LINE_SOFT else 1, radius=RADIUS)

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, cand, f)
        for j, ln in enumerate(wrap_lines([cand.name], f.card_name, rect.w - 74)[:2]):
            text(screen, ln, f.card_name, INK, (tok[0] + 24, rect.y + pad + j * 16))

        y = rect.y + pad + 44
        text(screen, f"{cand.race['name']}  ·  {cand.occupation['name']}", f.body_sm,
             INK_DIM, (rect.x + pad, y)); y += 15
        text(screen, f"{cand.alignment}  ·  {cand.size}", f.body_sm, INK_DIM,
             (rect.x + pad, y)); y += 18

        text(screen, f"HP {cand.hp_max}   AC {cand.ac}   Speed {cand.speed}   "
             f"{cand.weapon_name or 'unarmed'}", f.mono_sm, INK_DIM, (rect.x + pad, y))
        y += 18
        text(screen, f"resistance: CHA {cand.mod_charisma:+}", f.body_sm,
             WARN, (rect.x + pad, y)); y += 15
        text(screen, "speaks " + ", ".join(cand.languages), f.body_sm, INK_DIM,
             (rect.x + pad, y)); y += 18

        y = section(screen, "ABILITY", rect.x + pad, y, rect.w - 2 * pad, f)
        text(screen, cand.ability.name, f.body_bd, INFO, (rect.x + pad, y)); y += 15
        for ln in wrap_lines([cand.ability.effect], f.body_sm, rect.w - 2 * pad)[:3]:
            text(screen, ln, f.body_sm, INK_FAINT, (rect.x + pad, y)); y += 13
        y += SP2

        if last is not None:
            y = self._draw_last(screen, rect, y, last)

        best = self._best(cand)
        y = section(screen, "PITCH", rect.x + pad, y, rect.w - 2 * pad, f)
        if best is not None:
            m, net = best
            text(screen, f"{m.name}  ·  CHA check {net:+}", f.body_sm, OK,
                 (rect.x + pad, y)); y += 15
            text(screen, f"(1d20{net:+} must beat 1d20 {cand.mod_charisma:+})",
                 f.body_sm, INK_FAINT, (rect.x + pad, y))
        elif not open_pitch and any(recruit.can_pitch(m, cand) for m in self.party):
            text(screen, "everyone already tried this week", f.body_sm, DANGER,
                 (rect.x + pad, y))
        else:
            text(screen, "no one in the party can speak with them", f.body_sm, DANGER,
                 (rect.x + pad, y))

        mark = "click to pitch" if self.sel is None else "click a party member"
        text(screen, mark, f.label, INK_FAINT, (rect.x + pad, rect.bottom - 20))

    def _draw_last(self, screen, rect, y, last):
        f = self.fonts
        pad = SP3
        pitch, who = last
        y = section(screen, "LAST ATTEMPT", rect.x + pad, y, rect.w - 2 * pad, f,
                    color=OK if pitch.ok else DANGER)
        text(screen, f"{who.name}: {pitch.recruiter_roll} + mods = {pitch.recruiter_total}",
             f.mono_sm, INK_DIM, (rect.x + pad, y)); y += 13
        text(screen, f"vs resistance {pitch.candidate_total} "
             f"({pitch.candidate_roll} + CHA)", f.mono_sm, INK_DIM, (rect.x + pad, y))
        y += 13
        for val, label in pitch.modifiers:
            text(screen, f"{val:+}  {label}", f.body_sm, DANGER, (rect.x + pad, y))
            y += 13
        return y + SP1

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
        pad = SP2
        cand = self.candidates[self.sel] if self.sel is not None else None
        state = None
        if cand is not None:
            if recruit.barred(self.guild, cand, m):
                state = ("TRIED", DANGER)
            elif recruit.can_pitch(m, cand):
                state = ("CAN SPEAK", OK)
            else:
                state = ("no language", DANGER)
        hov = r.collidepoint(self.mouse) and self.sel is not None
        can = state is not None and state[0] == "CAN SPEAK"
        border = OK if (can and hov) else DANGER if (state and not can and hov) else LINE_SOFT
        panel(screen, r, fill=SURFACE_3 if hov else SURFACE_1, border=border,
              width=2 if border != LINE_SOFT else 1, radius=4)

        tok = (r.x + pad + 11, r.y + pad + 11)
        token_badge(screen, tok, m, f, r=12)
        text(screen, m.name, f.body_bd, INK, (tok[0] + 22, r.y + pad))
        text(screen, f"CAR {m.mod_charisma:+}", f.mono_sm, WARN, (tok[0] + 22, r.y + pad + 16))
        text(screen, ", ".join(m.languages), f.body_sm, INK_FAINT,
             (r.x + pad, r.y + pad + 34))
        if state is not None:
            text(screen, state[0], f.label, state[1], (r.x + pad, r.bottom - 16))

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen):
        f = self.fonts
        y = screen.get_height() - 52
        if self.notice:
            col = OK if "signs" in self.notice else INFO
            text(screen, self.notice, f.body_sm, col, (MARGIN, y - 22))

        d = pygame.Rect(screen.get_width() - MARGIN - 240, y, 240, 36)
        hov = d.collidepoint(self.mouse)
        panel(screen, d, fill=ACCENT if hov else SURFACE_3, border=ACCENT, width=1, radius=RADIUS)
        text(screen, "LEAVE THE TAVERN", f.body_bd, ACCENT_INK if hov else ACCENT,
             d.center, center=True)
        self.buttons.append(("done", d))

"""Prison: pay a minor criminal's bail and try to recruit them.

The strangers here are the guild's weekly `prison_pool`. Pick one, then pick
the party member who makes the pitch. Unlike the taverna, you must pay their
bail (in copper) to even attempt the pitch. The payment gives a +2 bonus to
the Charisma contest, representing their gratitude.

If the pitch fails, they walk free and take your money with them.
"""

import pygame

from . import recruit
from .data import alignment_distance
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE, LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, panel, section,
                    token_badge, text, tracked, wrap_lines)

CANDIDATES = 3


def _party_wealth(party):
    return sum(m.gold for m in party)


def _charge_party(party, amount):
    left = amount
    for m in sorted(party, key=lambda u: u.gold, reverse=True):
        paid = min(m.gold, left)
        m.gold -= paid
        left -= paid
        if left <= 0:
            break


class PrisonScreen(Screen):
    native = True

    def __init__(self, fonts, guild, party, node, on_done, candidates=None, title=None):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.party = party
        self.node = node
        self.on_done = on_done
        self.candidates = list(candidates) if candidates is not None else recruit.refresh_prison_pool(guild)
        self.title = title or "CITY PRISON"
        self.sel = None
        self.last = {}
        self.notice = None
        self.cand_cards = []
        self.party_cards = []
        self.buttons = []

    def tutorial_key(self):
        return None

    def _eligible(self, cand):
        return [m for m in self.party
                if recruit.can_pitch(m, cand) and not recruit.prison_barred(self.guild, cand, m)
                and recruit.slots_free(self.guild, m) > 0]

    def _best(self, cand):
        pen = recruit.size_penalty(len(self.guild.roster))
        def _dist(m):
            raw = alignment_distance(m.alignment, cand.alignment)
            return max(0, raw - int(m.talent_bonus("align_distance_reduction")))
        opts = [(m, m.mod_charisma
                 - recruit.ALIGNMENT_PENALTY * _dist(m)
                 - pen
                 + m.talent_bonus("recruit_cha")
                 + 2)  # +2 from bail
                for m in self._eligible(cand)]
        return max(opts, key=lambda t: t[1]) if opts else None

    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "done":
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
        for rect, i in self.cand_cards:
            if rect.collidepoint(px):
                self.sel = i
                return
        self.sel = None

    def _pitch(self, member):
        cand = self.candidates[self.sel]
        if not recruit.can_pitch(member, cand):
            self.notice = f"{member.name} and {cand.name} share no language."
            return
        if recruit.prison_barred(self.guild, cand, member):
            self.notice = f"{member.name} already tried {cand.name} this week."
            return
        if recruit.slots_free(self.guild, member) <= 0:
            self.notice = f"{member.name} has no room to sponsor anyone else."
            return
        
        cost = recruit.bail_cost(cand)
        if _party_wealth(self.party) < cost:
            self.notice = f"Not enough coin to pay {cand.name}'s bail ({cost} cp)."
            return

        # Pay bail
        _charge_party(self.party, cost)
        
        pitch = recruit.convince(member, cand, len(self.guild.roster), day=self.guild.clock.day,
                                 extra_mods=[(2, "paid bail")])
        self.last[cand.uid] = (pitch, member)
        if pitch.ok:
            recruit.enlist(self.guild, cand, member)
            self.candidates.pop(self.sel)
            self.notice = f"Bail paid! {cand.name} signs with the guild (recruited by {member.name})."
        else:
            recruit.prison_bar(self.guild, cand, member)
            self.notice = f"Bail paid, but {cand.name} walks away free. You lost {cost} cp."
        self.sel = None

    def draw(self, screen):
        f = self.fonts
        screen.fill((20, 20, 22))
        self.cand_cards = []
        self.party_cards = []
        self.buttons = []

        text(screen, self.title, f.title, INK, (MARGIN, MARGIN - 2))
        
        top = MARGIN + 45
        self._draw_recruits(screen, top)
        self._draw_footer(screen)

    def _draw_recruits(self, screen, top):
        f = self.fonts
        days_left = recruit.REFRESH_DAYS - (self.guild.clock.day - 1) % recruit.REFRESH_DAYS
        if self.sel is not None:
            cand = self.candidates[self.sel]
            cost = recruit.bail_cost(cand)
            sub, col = (f"paying {cost} cp bail for {cand.name}  ·  click who from the party speaks  ·  click outside to cancel", ACCENT)
        else:
            wealth = _party_wealth(self.party)
            sub, col = (f"party wealth: {wealth} cp  ·  size penalty -{recruit.size_penalty(len(self.guild.roster))}  ·  new faces in {days_left} day(s)", INK_DIM)
        text(screen, sub, f.body, col, (MARGIN, top - 25))

        party_h = 120
        gap = SP3
        cand_h = screen.get_height() - top - party_h - gap - 80
        cw = (screen.get_width() - 2 * MARGIN - (CANDIDATES - 1) * gap) // CANDIDATES

        if not self.candidates:
            text(screen, "The cells are empty right now. Come back when the crowd changes.",
                 f.body, INK_DIM, (MARGIN, top + 20))
        for i, cand in enumerate(self.candidates):
            rect = pygame.Rect(MARGIN + i * (cw + gap), top, cw, cand_h)
            self._draw_candidate(screen, rect, i, cand)
            self.cand_cards.append((rect, i))

        py = top + cand_h + gap
        self._draw_party(screen, pygame.Rect(MARGIN, py, screen.get_width() - 2 * MARGIN, party_h))

    def _draw_candidate(self, screen, rect, i, cand):
        f = self.fonts
        pad = SP3
        last = self.last.get(cand.uid)
        picking = self.sel == i
        open_pitch = self._eligible(cand)
        cost = recruit.bail_cost(cand)

        hovering = rect.collidepoint(self.mouse) and self.sel is None
        border = ACCENT if (picking or hovering) else LINE_SOFT
        panel(screen, rect, fill=SURFACE_2, border=border,
              width=2 if border != LINE_SOFT else 1, radius=RADIUS)

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, cand, f)
        for j, ln in enumerate(wrap_lines([cand.name], f.card_name, rect.w - 74)[:2]):
            text(screen, ln, f.card_name, INK, (tok[0] + 24, rect.y + pad + j * 16))

        y = rect.y + pad + 44
        text(screen, f"{cand.race['name']}  ·  {cand.occupation['name']}", f.body_sm, INK_DIM, (rect.x + pad, y))
        y += 15
        text(screen, f"BAIL: {cost} cp", f.body_bd, WARN, (rect.x + pad, y))
        y += 18

        text(screen, f"HP {cand.hp_max}   AC {cand.ac}   Speed {cand.speed}   {cand.weapon_name or 'unarmed'}", f.mono_sm, INK_DIM, (rect.x + pad, y))
        y += 18
        text(screen, f"resistance: CHA {cand.mod_charisma:+}", f.body_sm, WARN, (rect.x + pad, y))
        y += 15
        text(screen, "speaks " + ", ".join(cand.languages), f.body_sm, INK_DIM, (rect.x + pad, y))
        y += 18

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
            text(screen, f"{m.name}  ·  CHA check {net:+}", f.body_sm, OK, (rect.x + pad, y))
            y += 15
            text(screen, f"(1d20{net:+} must beat 1d20 {cand.mod_charisma:+})", f.body_sm, INK_FAINT, (rect.x + pad, y))
        elif not open_pitch and any(recruit.can_pitch(m, cand) for m in self.party):
            text(screen, "everyone already tried this week", f.body_sm, DANGER, (rect.x + pad, y))
        else:
            text(screen, "no one in the party can speak with them", f.body_sm, DANGER, (rect.x + pad, y))

        mark = "click to pay bail" if self.sel is None else "click a party member"
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
        free = recruit.slots_free(self.guild, m)
        state = None
        can = False
        
        if cand is not None:
            cost = recruit.bail_cost(cand)
            if recruit.prison_barred(self.guild, cand, m):
                state = ("TRIED", DANGER)
            elif free <= 0:
                state = ("FULL", DANGER)
            elif not recruit.can_pitch(m, cand):
                state = ("no language", DANGER)
            elif _party_wealth(self.party) < cost:
                state = ("CANT AFFORD", DANGER)
            else:
                state = ("CAN SPEAK", OK)
                can = True
                
        hov = r.collidepoint(self.mouse) and self.sel is not None
        border = OK if (can and hov) else DANGER if (state and not can and hov) else LINE_SOFT
        panel(screen, r, fill=SURFACE_3 if hov else SURFACE_1, border=border,
              width=2 if border != LINE_SOFT else 1, radius=4)

        tok = (r.x + pad + 11, r.y + pad + 11)
        token_badge(screen, tok, m, f, r=12)
        text(screen, m.name, f.body_bd, INK, (tok[0] + 22, r.y + pad))
        text(screen, f"CAR {m.mod_charisma:+}", f.mono_sm, WARN, (tok[0] + 22, r.y + pad + 16))
        text(screen, ", ".join(m.languages), f.body_sm, INK_FAINT,
             (r.x + pad, r.y + pad + 34))
        
        slots_col = DANGER if free <= 0 else INK_FAINT
        slots_text = f"{max(0, free)} slot(s) free"
        slots_w = f.body_sm.size(slots_text)[0]
        slots_rect = pygame.Rect(r.x + pad, r.y + pad + 48, max(slots_w, 80), 16)
        text(screen, slots_text, f.body_sm, slots_col, (slots_rect.x, slots_rect.y))
        
        if state is not None:
            text(screen, state[0], f.label, state[1], (r.x + pad, r.bottom - 16))
            
        if slots_rect.collidepoint(self.mouse):
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

    def _draw_footer(self, screen):
        f = self.fonts
        y = screen.get_height() - 52
        if self.notice:
            col = OK if ("signs" in self.notice or "Bail paid!" in self.notice) else INFO
            if "lost" in self.notice or "Not enough" in self.notice:
                col = DANGER
            text(screen, self.notice, f.body_sm, col, (MARGIN, y - 22))

        d = pygame.Rect(screen.get_width() - MARGIN - 240, y, 240, 36)
        hov = d.collidepoint(self.mouse)
        panel(screen, d, fill=ACCENT if hov else SURFACE_3, border=ACCENT, width=1, radius=RADIUS)
        text(screen, "LEAVE THE PRISON", f.body_bd, ACCENT_INK if hov else ACCENT,
             d.center, center=True)
        self.buttons.append(("done", d))

"""Prison: pay a minor criminal's bail and try to recruit them.

The strangers here are the guild's weekly `prison_pool`. Pick one, then pick
the party member who makes the pitch. Unlike the taverna, you must pay their
bail (in copper) to even attempt the pitch. The payment gives a +2 bonus to
the Charisma contest, representing their gratitude.

If the pitch fails, they walk free and take your money with them.
"""

import pygame

from . import economy, recruit
from .data import alignment_distance
from .screen import Screen
from .ui.primitives import (draw_button, footer_bar, panel, section, text,
                            token_badge, tracked, wrap)
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .widgets import ButtonsMixin

CANDIDATES = 3


def _party_wealth(party):
    return sum(m.gold for m in party)


def _charge_party(party, amount):
    economy.charge_richest_first(party, amount)


class PrisonScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, party, node, on_done, candidates=None, title=None):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
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
        self._hot = False

    def tutorial_key(self):
        return None

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False,
                   danger=False, font=None, sub=None):
        """Draws through `ui.primitives.draw_button`, keeping `ButtonsMixin`'s
        own hit-registration bookkeeping (`self.buttons`/`self._hot`) -- see
        `map_screen.MapScreen.add_button` for the precedent."""
        draw_button(surf, self._F, rect, label, sub=sub, primary=primary, danger=danger,
                   enabled=enabled, mpos=self.mouse, fnt=font)
        hov = enabled and rect.collidepoint(self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or hov
        return hov

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
        F = self._F
        m = T.S * 3
        screen.fill(T.TABLE)
        self.cand_cards = []
        self.party_cards = []
        self._reset_buttons()

        text(screen, F["titleb"], self.title, (m, m - 2), T.TX)

        top = m + 45
        self._draw_recruits(screen, top)
        self._draw_footer(screen)

    def _draw_recruits(self, screen, top):
        F = self._F
        m = T.S * 3
        days_left = recruit.REFRESH_DAYS - (self.guild.clock.day - 1) % recruit.REFRESH_DAYS
        if self.sel is not None:
            cand = self.candidates[self.sel]
            cost = recruit.bail_cost(cand)
            sub, col = (f"paying {cost} cp bail for {cand.name}  ·  click who from the party speaks  ·  click outside to cancel", T.BRASS)
        else:
            wealth = _party_wealth(self.party)
            sub, col = (f"party wealth: {wealth} cp  ·  size penalty -{recruit.size_penalty(len(self.guild.roster))}  ·  new faces in {days_left} day(s)", T.TX_MUTED)
        text(screen, F["body"], sub, (m, top - 25), col)

        party_h = 120
        gap = 12
        cand_h = screen.get_height() - top - party_h - gap - 80
        cw = (screen.get_width() - 2 * m - (CANDIDATES - 1) * gap) // CANDIDATES

        if not self.candidates:
            text(screen, F["body"], "The cells are empty right now. Come back when the crowd changes.",
                 (m, top + 20), T.TX_MUTED)
        for i, cand in enumerate(self.candidates):
            rect = pygame.Rect(m + i * (cw + gap), top, cw, cand_h)
            self._draw_candidate(screen, rect, i, cand)
            self.cand_cards.append((rect, i))

        py = top + cand_h + gap
        self._draw_party(screen, pygame.Rect(m, py, screen.get_width() - 2 * m, party_h))

    def _draw_candidate(self, screen, rect, i, cand):
        F = self._F
        pad = 12
        last = self.last.get(cand.uid)
        picking = self.sel == i
        cost = recruit.bail_cost(cand)

        hovering = rect.collidepoint(self.mouse) and self.sel is None
        active = picking or hovering
        panel(screen, rect, hover=active, width=2 if active else 1)

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, F, tok, cand)
        for j, ln in enumerate(wrap(F["head"], cand.name, rect.w - 74)[:2]):
            text(screen, F["head"], ln, (tok[0] + 24, rect.y + pad + j * 16), T.TX)

        y = rect.y + pad + 44
        text(screen, F["body_sm"], f"{cand.race['name']}  ·  {cand.occupation['name']}",
             (rect.x + pad, y), T.TX_MUTED)
        y += 15
        text(screen, F["bodyb"], f"BAIL: {cost} cp", (rect.x + pad, y), T.BRASS)
        y += 18

        text(screen, F["body_sm"],
             f"HP {cand.hp_max}   AC {cand.ac}   Speed {cand.speed}   {cand.weapon_name or 'unarmed'}",
             (rect.x + pad, y), T.TX_MUTED)
        y += 18
        text(screen, F["body_sm"], f"resistance: CHA {cand.mod_charisma:+}", (rect.x + pad, y), T.BRASS)
        y += 15
        text(screen, F["body_sm"], "speaks " + ", ".join(cand.languages), (rect.x + pad, y), T.TX_MUTED)
        y += 18

        y = section(screen, F, "ABILITY", rect.x + pad, y, rect.w - 2 * pad)
        text(screen, F["bodyb"], cand.ability.name, (rect.x + pad, y), T.BRASS); y += 15
        for ln in wrap(F["body_sm"], cand.ability.effect, rect.w - 2 * pad)[:3]:
            text(screen, F["body_sm"], ln, (rect.x + pad, y), T.TX_FAINT); y += 13
        y += T.S

        if last is not None:
            y = self._draw_last(screen, rect, y, last)

        best = self._best(cand)
        y = section(screen, F, "PITCH", rect.x + pad, y, rect.w - 2 * pad)
        if best is not None:
            m2, net = best
            text(screen, F["body_sm"], f"{m2.name}  ·  CHA check {net:+}", (rect.x + pad, y), T.GREEN)
            y += 15
            text(screen, F["body_sm"], f"(1d20{net:+} must beat 1d20 {cand.mod_charisma:+})",
                 (rect.x + pad, y), T.TX_FAINT)
        else:
            reason = recruit.pitch_block_reason(self.guild, self.party, cand, is_prison=True)
            text(screen, F["body_sm"], reason or "cannot recruit", (rect.x + pad, y), T.BLOOD)

        mark = ("click to pay bail" if best is not None else "click to inspect") if self.sel is None else "click a party member"
        text(screen, F["micro"], mark, (rect.x + pad, rect.bottom - 20), T.TX_FAINT)

    def _draw_last(self, screen, rect, y, last):
        F = self._F
        pad = 12
        pitch, who = last
        y = section(screen, F, "LAST ATTEMPT", rect.x + pad, y, rect.w - 2 * pad,
                    color=T.GREEN if pitch.ok else T.BLOOD)
        text(screen, F["body_sm"], f"{who.name}: {pitch.recruiter_roll} + mods = {pitch.recruiter_total}",
             (rect.x + pad, y), T.TX_MUTED); y += 13
        text(screen, F["body_sm"], f"vs resistance {pitch.candidate_total} "
             f"({pitch.candidate_roll} + CHA)", (rect.x + pad, y), T.TX_MUTED)
        y += 13
        for val, label in pitch.modifiers:
            text(screen, F["body_sm"], f"{val:+}  {label}", (rect.x + pad, y), T.BLOOD)
            y += 13
        return y + T.S // 2

    def _draw_party(self, screen, area):
        F = self._F
        tracked(screen, F["micro"], "YOUR PARTY", (area.x, area.y - 16), T.BRASS)
        panel(screen, area)
        n = max(1, len(self.party))
        gap = T.S
        cw = (area.w - 24 - (n - 1) * gap) // n
        for i, m in enumerate(self.party):
            r = pygame.Rect(area.x + 12 + i * (cw + gap), area.y + T.S, cw, area.h - 2 * T.S)
            self._draw_party_card(screen, r, m)
            self.party_cards.append((r, m))

    def _draw_party_card(self, screen, r, m):
        F = self._F
        pad = T.S
        cand = self.candidates[self.sel] if self.sel is not None else None
        free = recruit.slots_free(self.guild, m)
        state = None
        can = False

        if cand is not None:
            cost = recruit.bail_cost(cand)
            if recruit.prison_barred(self.guild, cand, m):
                state = ("TRIED", T.BLOOD)
            elif not recruit.can_pitch(m, cand):
                state = ("no language", T.BLOOD)
            elif free <= 0:
                state = ("FULL", T.BLOOD)
            elif _party_wealth(self.party) < cost:
                state = ("CANT AFFORD", T.BLOOD)
            else:
                state = ("CAN SPEAK", T.GREEN)
                can = True

        hov = r.collidepoint(self.mouse) and self.sel is not None
        fill = T.STEEL_HI if hov else T.STEEL
        border = T.GREEN if (can and hov) else T.BLOOD if (state and not can and hov) else T.STEEL_LINE
        pygame.draw.rect(screen, fill, r)
        pygame.draw.rect(screen, border, r, 2 if border != T.STEEL_LINE else 1)

        tok = (r.x + pad + 11, r.y + pad + 11)
        token_badge(screen, F, tok, m, r=12)
        text(screen, F["bodyb"], m.name, (tok[0] + 22, r.y + pad), T.TX)
        text(screen, F["body_sm"], f"CAR {m.mod_charisma:+}", (tok[0] + 22, r.y + pad + 16), T.BRASS)
        text(screen, F["body_sm"], ", ".join(m.languages), (r.x + pad, r.y + pad + 34), T.TX_FAINT)

        slots_col = T.BLOOD if free <= 0 else T.TX_FAINT
        slots_text = f"{max(0, free)} slot(s) free"
        slots_w = F["body_sm"].size(slots_text)[0]
        slots_rect = pygame.Rect(r.x + pad, r.y + pad + 48, max(slots_w, 80), 16)
        text(screen, F["body_sm"], slots_text, (slots_rect.x, slots_rect.y), slots_col)

        if state is not None:
            text(screen, F["micro"], state[0], (r.x + pad, r.bottom - 16), state[1])

        if slots_rect.collidepoint(self.mouse):
            cap = recruit.capacity(self.guild, m)
            used = recruit.slots_used(self.guild, m)
            calc_str = "Cap: 1 (base)"
            if m.mod_charisma != 0: calc_str += f" {m.mod_charisma:+} (CHA)"
            if m is self.guild.leader: calc_str += f" + {m.racial_level} (ldr)"
            calc_str += f" = {cap}  |  Used: {used}"
            tw, th = F["body_sm"].size(calc_str)
            tt_rect = pygame.Rect(self.mouse[0] + 12, self.mouse[1] + 12, tw + 16, th + 8)
            panel(screen, tt_rect)
            text(screen, F["body_sm"], calc_str, (tt_rect.x + 8, tt_rect.y + 4), T.TX)

    def _draw_footer(self, screen):
        col = T.BRASS
        if self.notice:
            col = T.GREEN if ("signs" in self.notice or "Bail paid!" in self.notice) else T.BRASS
            if "lost" in self.notice or "Not enough" in self.notice:
                col = T.BLOOD
        footer_bar(self, screen, self._F, primary=("done", "LEAVE THE PRISON"),
                  notice=self.notice, notice_color=col)

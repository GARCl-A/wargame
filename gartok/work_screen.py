"""The lumber yard: put the picked members to a shift and pay them by the hour.

Reached from the map's Madeireira through the worker picker (`SquadScreen`).
Pick a shift length -- 4, 8, 12 or 16 h; `CONFIRMAR` runs `Guild.work_shift`,
which drops `economy.lumber_pay(hours)` copper into each worker's purse, banks
the hours toward their work-XP and advances the campaign clock (a long shift can
cross midnight and trigger the daily meal). The result page shows what changed,
then `on_done` returns to the map.
"""

import pygame

from . import economy
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WIN_H, WIN_W, panel, section, text,
                    token_badge, wrap_lines)


class WorkScreen(Screen):
    def __init__(self, fonts, guild, workers, on_done, on_back):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.workers = workers
        self.on_done = on_done
        self.on_back = on_back
        self.hours = economy.LUMBER_SHIFT_HOURS[-1]   # default: a full day
        self.result = None                            # list[str] once the shift is done
        self.chips = []                              # [(rect, hours)]
        self.buttons = []                           # [(key, rect)]

    # ------------------------------------------------------------------ #
    @property
    def pay(self):
        return economy.lumber_pay(self.hours)

    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "back" and self.result is None:
                    self.on_back()
                elif key == "confirm" and self.result is None:
                    self.result = self.guild.work_shift(self.workers, self.hours) or \
                        ["Shift done."]
                elif key == "done" and self.result is not None:
                    self.on_done()
                return
        if self.result is not None:
            return
        for rect, h in self.chips:
            if rect.collidepoint(px):
                self.hours = h
                return

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self.chips = []
        self.buttons = []

        text(screen, "LUMBER YARD", f.title, INK, (MARGIN, MARGIN - 2))
        clock = self.guild.clock
        text(screen, f"{clock.label}   ·   {len(self.workers)} on the crew   ·   "
             f"pay: {economy.LUMBER_WAGE} copper every "
             f"{economy.LUMBER_BLOCK_HOURS} h", f.body, INK_DIM, (MARGIN, MARGIN + 30))

        top = MARGIN + 72
        self._draw_workers(screen, top)

        if self.result is None:
            self._draw_shift_picker(screen, WIN_H - 236)
        else:
            self._draw_result(screen, WIN_H - 236)
        self._draw_footer(screen)

    # ------------------------------------------------------------------ #
    def _draw_workers(self, screen, top):
        f = self.fonts
        n = max(1, len(self.workers))
        gap = SP3
        card_w = min(240, (WIN_W - 2 * MARGIN - (n - 1) * gap) // n)
        card_h = 96
        for i, u in enumerate(self.workers):
            rect = pygame.Rect(MARGIN + i * (card_w + gap), top, card_w, card_h)
            panel(screen, rect, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
            pad = SP3
            tok = (rect.x + pad + 12, rect.y + pad + 12)
            token_badge(screen, tok, u, f)
            text(screen, u.name, f.card_name, INK, (tok[0] + 24, rect.y + pad))
            text(screen, f"{u.race['name']}  ·  {u.occupation['name']}", f.body_sm,
                 INK_DIM, (tok[0] + 24, rect.y + pad + 20))
            y = rect.y + pad + 46
            text(screen, f"{u.gold} copper", f.mono_sm, ACCENT, (rect.x + pad, y))
            text(screen, f"{u.work_xp} work XP", f.mono_sm, INFO,
                 (rect.right - pad, y), right=True)

    def _draw_shift_picker(self, screen, top):
        f = self.fonts
        top = section(screen, "SHIFT", MARGIN, top, WIN_W - 2 * MARGIN, f)
        gap = SP2
        opts = economy.LUMBER_SHIFT_HOURS
        w = (WIN_W - 2 * MARGIN - (len(opts) - 1) * gap) // len(opts)
        for i, h in enumerate(opts):
            r = pygame.Rect(MARGIN + i * (w + gap), top, w, 56)
            sel = h == self.hours
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if (sel or hov) else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=2 if sel else 1,
                  radius=RADIUS)
            text(screen, f"{h} h", f.body_bd, ACCENT if sel else INK,
                 (r.x + SP2, r.y + 8))
            text(screen, f"+{economy.lumber_pay(h)} copper", f.body_sm, INK_DIM,
                 (r.x + SP2, r.y + 30))
            self.chips.append((r, h))
        top += 66

        marks = self.hours // economy.LUMBER_XP_HOURS
        now = self.guild.clock.seconds
        crosses_day = (now + self.hours * 3600) // 86400 != now // 86400
        note = f"{self.hours} h shift  ·  +{self.pay} copper each"
        if marks:
            note += f"  ·  +{marks} work XP"
        if crosses_day:
            note += "  ·  crosses midnight: the day's meal"
        text(screen, note, f.body_sm, INK_FAINT, (MARGIN, top))

    def _draw_result(self, screen, top):
        f = self.fonts
        top = section(screen, "END OF SHIFT", MARGIN, top, WIN_W - 2 * MARGIN, f)
        lines = [w for ln in self.result
                 for w in wrap_lines([ln], f.body_sm, WIN_W - 2 * MARGIN)]
        for ln in lines:
            col = DANGER if "starved" in ln else OK if "copper" in ln else INFO
            text(screen, ln, f.body_sm, col, (MARGIN, top))
            top += 16

    def _draw_footer(self, screen):
        f = self.fonts
        y = WIN_H - 56
        if self.result is None:
            conf = pygame.Rect(WIN_W - MARGIN - 240, y, 240, 36)
            hov = conf.collidepoint(self.mouse)
            panel(screen, conf, fill=ACCENT if hov else SURFACE_3, border=ACCENT,
                  width=1, radius=RADIUS)
            text(screen, "CONFIRM SHIFT", f.body_bd, ACCENT_INK if hov else ACCENT,
                 conf.center, center=True)
            self.buttons.append(("confirm", conf))

            back = pygame.Rect(MARGIN, y, 140, 36)
            hovb = back.collidepoint(self.mouse)
            panel(screen, back, fill=SURFACE_3 if hovb else SURFACE_2,
                  border=LINE_SOFT, width=1, radius=RADIUS)
            text(screen, "back", f.body, INK if hovb else INK_DIM,
                 back.center, center=True)
            self.buttons.append(("back", back))
        else:
            d = pygame.Rect(WIN_W - MARGIN - 240, y, 240, 36)
            hov = d.collidepoint(self.mouse)
            panel(screen, d, fill=ACCENT if hov else SURFACE_3, border=ACCENT,
                  width=1, radius=RADIUS)
            text(screen, "CONTINUE", f.body_bd, ACCENT_INK if hov else ACCENT,
                 d.center, center=True)
            self.buttons.append(("done", d))

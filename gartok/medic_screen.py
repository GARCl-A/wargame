"""The Medic tab of the Apothecary: pick the patients, pay, the clock moves for the group."""

import pygame

from . import medic
from .screen import Screen
from .ui.medic_panel import draw_medic
from .ui.primitives import caps, set_pointer, text, wrap
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class MedicScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.picked = set()
        self.notice = None
        self.row_rects = []
        self.treat_rect = pygame.Rect(0, 0, 0, 0)

    def tutorial_key(self):
        return "medic"

    def handle_escape(self):
        self.on_done()
        return True

    def _quotes(self):
        return [q for q in medic.quotes(self.group.members) if q.needs_care]

    def _picked_quotes(self):
        return [q for q in self._quotes() if q.uid in self.picked and q.offered]

    def _click(self, pos):
        if self.treat_rect.collidepoint(pos):
            patients = [u for u in self.group.members if u.uid in self.picked]
            ok, lines = medic.treat(self.guild, self.group, patients)
            self.notice = "  ".join(lines)
            if ok:
                self.picked.clear()
            return
        for uid, rect in self.row_rects:
            if rect.collidepoint(pos):
                self.picked ^= {uid}
                self.notice = None
                return

    def draw(self, screen):
        F = self.fonts if (isinstance(self.fonts, dict) and "body" in self.fonts) else ui_fonts()
        screen.fill(T.TABLE)
        m = T.S * 3
        caps(screen, F["head"], "THE APOTHECARY (MEDIC)", (m, m), T.TX)
        sub = "Quick treatment: potions and doses at a discount, the whole group waits."
        text(screen, F["body"], sub, (m, m + T.S * 4), T.TX_MUTED)

        top = m + T.S * 8
        notice_h = 0
        if self.notice:
            lines = wrap(F["body_sm"], self.notice, screen.get_width() - 2 * m)
            for i, ln in enumerate(lines):
                text(screen, F["body_sm"], ln, (m, screen.get_height() - m - T.S * 2 - (len(lines) - i) * 18), T.BRASS)
            notice_h = len(lines) * 18 + T.S
        area = pygame.Rect(m, top, screen.get_width() - 2 * m, screen.get_height() - top - m - notice_h)

        picked = self._picked_quotes()
        cost, hours = medic.total(picked)
        rows = [{"key": q.uid, "name": q.name, "lines": [f"{lbl} ${c}" for lbl, c, _ in q.parts],
                 "cost": q.cost, "hours": q.hours, "picked": q.uid in self.picked and q.offered,
                 "enabled": q.offered, "note": "needs a hospital stay (over 24 h)"}
                for q in self._quotes()]
        can_pay = sum(u.money for u in self.group.members) >= cost
        self.row_rects, self.treat_rect = draw_medic(screen, F, area, rows, cost, hours, can_pay, self.mouse)
        set_pointer(any(r.collidepoint(self.mouse) for _, r in self.row_rects) or self.treat_rect.collidepoint(self.mouse))

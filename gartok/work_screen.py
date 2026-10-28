"""The Work tab of a work node (Lumber Yard, Mine): paid shifts with the foreman's tool or your own."""

import pygame

from . import economy, orders
from .constants import fmt_money
from .screen import Screen
from .ui import hub_body as hb
from .ui.hub_frame import MARGIN
from .ui.primitives import set_pointer, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .work_desk import SHIFTS, WorkDesk


class WorkScreen(Screen, WorkDesk):
    native = True
    framed = True           # only ever a hub's tab: the hub draws the keeper, the tabs and the back

    def __init__(self, fonts, guild, group, node, on_done, on_work=None):
        super().__init__()
        WorkDesk.__init__(self, guild, group, node)     # Screen ends the cooperative chain
        self._F = ui_fonts()
        self.on_done = on_done
        self.on_work = on_work          # runs the shift and keeps the tab up (App._work_shift)
        self.buttons = []
        self._hot = False

    def tutorial_key(self):
        return "work"

    def handle_escape(self):
        return False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self.buttons:
                if rect.collidepoint(event.pos):
                    self._on_button(key)
                    return

    def _on_button(self, key):
        if key.startswith("work:"):
            order = orders.work(self.guild, self.group, int(key.split(":")[1]))
            if self.on_work is not None:
                self.on_work(order)
                return
            self.group.order = order
            self.on_done()

    def draw(self, surf):
        W, H = surf.get_size()
        surf.fill(T.TABLE)
        F = self._F
        self.buttons = []
        tool = economy.WORK_TOOLS[self.node.id]
        body = pygame.Rect(MARGIN, 0, W - 2 * MARGIN, H - T.S * 4)
        left_w = max(T.S * 56, min(T.S * 76, round(body.w * 0.42)))

        crew = pygame.Rect(body.x, body.y, left_w, body.h)
        inner = hb.draw_panel(surf, F, crew, "The Crew", f"their own {tool} pays more than the foreman's")
        y = inner.y
        row_h = max(hb.PERSON_H, min(hb.PERSON_H + T.S * 3,
                                     (inner.h + T.S) // max(1, len(self.group.members)) - T.S))
        for u in self.group.members:
            level = economy.work_level(u, self.node.id)
            own = level >= economy.LUMBER_LEVEL_OWN_AXE
            day = economy.work_pay(self.node.id, SHIFTS[-1], level)
            r = pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, row_h)
            if r.bottom > inner.bottom + T.S * 2:
                break
            hb.draw_person(surf, F, r, {
                "face": {"race": u.race["name"], "portrait_id": getattr(u, "portrait_id", None), "token": u.token},
                "name": u.name, "sub": f"own {tool.lower()}" if own else f"the foreman's {tool.lower()}",
                "note": self._crew_note(u, tool),
                "status": (f"{fmt_money(day)} / {SHIFTS[-1]} h", "good" if own else "muted")}, (-1, -1))
            y += r.h + T.S

        shifts = pygame.Rect(crew.right + T.S * 3, body.y, body.right - crew.right - T.S * 3, body.h)
        inner = hb.draw_panel(surf, F, shifts, "Shifts", "trade hours of the day for money: pays little, but it's sure")
        y = inner.y
        for h in SHIFTS:
            r = pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, hb.OFFER_H)
            for b, key in hb.draw_offer(surf, F, r, {
                    "icon": {"item": tool}, "name": f"{h} hours",
                    "sub": "paid by the block; leftover hours earn nothing",
                    "price": fmt_money(self._wage(h)), "price_tone": "money",
                    "buttons": [(f"work:{h}", "Work", True, True)]}, self.mouse):
                self.buttons.append((key, b))
            y += hb.OFFER_H + T.S
        y = text(surf, F["hub_sub"], "The licence on the Gathering tab trades the wage for what the crew finds.",
                 (inner.x, y + T.S), T.TX_FAINT).bottom + T.S * 3
        step = F["hub_body"].get_linesize() + T.S
        fit = max(0, (inner.bottom - y) // step)
        for line in self.report[-fit:] if fit else ():
            y = text(surf, F["hub_body"], line, (inner.x, y), T.BRASS).bottom + T.S

        self._hot = any(r.collidepoint(self.mouse) for _, r in self.buttons)
        set_pointer(self._hot)

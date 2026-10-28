"""The INITIATION tab of a hidden sanctuary: pick who stays to board for the school's rite."""

import pygame

from . import rite, world
from .screen import Screen
from .ui.hub_frame import MARGIN
from .ui.initiation_panel import draw_initiation
from .ui.primitives import caps, set_pointer, text, wrap
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .ui.vendor_panel import draw_vendor, draw_vendor_name


class InitiationScreen(Screen, rite.Initiation):
    native = True

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        rite.Initiation.__init__(self, guild, group)   # Screen ends the cooperative chain
        self.fonts = fonts
        self.on_done = on_done
        keeper = world.vendor(group.node, "shrine")
        self.vendor_card = keeper.card if keeper else None
        self.row_rects = []
        self.begin_rect = pygame.Rect(0, 0, 0, 0)
        self.leave_rect = pygame.Rect(0, 0, 0, 0)

    def tutorial_key(self):
        return "initiation"

    def handle_escape(self):
        self.on_done()
        return True

    def _click(self, pos):
        if self.leave_rect.collidepoint(pos):
            self.on_done()
            return
        if self.begin_rect.collidepoint(pos) and self._action():
            self._begin()
            return
        for uid, rect in self.row_rects:
            if rect.collidepoint(pos):
                self._pick(uid)
                return

    framed = False          # a hub's tab: the hub draws the keeper, the tabs and the back

    def draw(self, screen):
        F = ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        m = MARGIN
        if self.framed:
            top = 0
        else:
            face = draw_vendor(screen, F, (T.S * 3, T.S * 3), self.vendor_card)
            caps(screen, F["head"], f"{world.node(self.group.node).name.upper()}  ·  INITIATION",
                 (T.S * 3 + face, T.S * 3), T.TX)
            draw_vendor_name(screen, F, (T.S * 3 + face, T.S * 7), self.vendor_card)
            top = T.S * 12
        notice_h = 0
        if self.notice:
            lines = wrap(F["hub_body"], self.notice, W - 2 * m)
            lh = F["hub_body"].get_linesize()
            for i, ln in enumerate(lines):
                text(screen, F["hub_body"], ln, (m, H - T.S * 3 - (len(lines) - i) * lh), T.BRASS)
            notice_h = len(lines) * lh + T.S
        area = pygame.Rect(m, top, W - 2 * m, H - top - T.S * 4 - notice_h)
        self.row_rects, self.begin_rect, self.leave_rect = draw_initiation(
            screen, F, area, self._terms(), self._rows(), self._action(),
            None if self.framed else "LEAVE THE SANCTUARY", self.mouse)
        set_pointer(any(r.collidepoint(self.mouse) for _, r in self.row_rects)
                    or self.begin_rect.collidepoint(self.mouse) or self.leave_rect.collidepoint(self.mouse))

"""Ledger Hold: the Bankers' fortified outpost where the trust mission's
sealed chest (`data.MISSION_CHEST_ITEM`) is traded, intact, for a letter of
receipt (`data.LETTER_ITEM`) -- the thing `missions.turn_in` actually counts
back at the City (`trust_screen.py`). No progress bar, no goal_qty -- either
someone in the group is carrying the chest, or there is nothing to hand over.
"""

import pygame

from . import data
from .screen import Screen
from .theme import (INK, INK_DIM, INK_FAINT, LINE_SOFT, MARGIN, RADIUS, SP3,
                    SURFACE_2, panel, text)
from .widgets import ButtonsMixin, footer_bar

CARD_W = 560


class LedgerScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.notice = None
        self.buttons = []              # [(key, rect)]

    def _carrier(self):
        return next((u for u in self.group.members
                    if data.MISSION_CHEST_ITEM in u._base_inventory), None)

    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "exchange":
                carrier = self._carrier()
                if carrier is not None:
                    carrier._base_inventory.remove(data.MISSION_CHEST_ITEM)
                    carrier.give_to_pack(data.LETTER_ITEM)
                    self.notice = (f"{carrier.name} hands over the sealed chest -- the "
                                   "outpost gives a letter of receipt in return.")
            elif key == "done":
                self.on_done()
                return
            return

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self._reset_buttons()

        text(screen, "LEDGER HOLD", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, "\"State your business.\"", f.body, INK_DIM, (MARGIN, MARGIN + 30))

        card = pygame.Rect(MARGIN, MARGIN + 70,
                           min(CARD_W, screen.get_width() - 2 * MARGIN), 110)
        panel(screen, card, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
        x, y, w = card.x + SP3, card.y + SP3, card.w - 2 * SP3
        carrier = self._carrier()

        if carrier is not None:
            text(screen, f"{carrier.name} carries the Bankers' sealed chest.",
                 f.body_sm, INK_DIM, (x, y))
            y += 30
            r = pygame.Rect(x, y, w, 36)
            self.add_button(screen, r, "exchange", "HAND OVER THE CHEST", primary=True)
        else:
            text(screen, "Nothing to hand over here.", f.body_sm, INK_FAINT, (x, y))

        self._draw_footer(screen)

    def _draw_footer(self, screen):
        footer_bar(self, screen, primary=("done", "LEAVE LEDGER HOLD"), notice=self.notice)

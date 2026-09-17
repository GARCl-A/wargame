"""Ledger Hold: the Bankers' fortified outpost where the trust mission's
sealed chest (`data.MISSION_CHEST_ITEM`) is traded, intact, for a letter of
receipt (`data.LETTER_ITEM`) -- the thing `missions.turn_in` actually counts
back at the City (`trust_screen.py`). No progress bar, no goal_qty -- either
someone in the group is carrying the chest, or there is nothing to hand over.
"""

import pygame

from . import data
from .screen import Screen
from .ui.primitives import draw_button, footer_bar, panel, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .widgets import ButtonsMixin

CARD_W = 560


class LedgerScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.notice = None
        self.buttons = []              # [(key, rect)]

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

    def _carrier(self):
        return next((u for u in self.group.members
                    if u.has_item(data.MISSION_CHEST_ITEM)), None)

    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "exchange":
                carrier = self._carrier()
                if carrier is not None:
                    carrier.remove_named(data.MISSION_CHEST_ITEM)
                    carrier.give_to_pack(data.LETTER_ITEM)
                    self.notice = (f"{carrier.name} hands over the sealed chest -- the "
                                   "outpost gives a letter of receipt in return.")
            elif key == "done":
                self.on_done()
                return
            return

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._F
        m = T.S * 3
        screen.fill(T.TABLE)
        self._reset_buttons()

        text(screen, F["titleb"], "LEDGER HOLD", (m, m - 2), T.TX)
        text(screen, F["body"], "\"State your business.\"", (m, m + 30), T.TX_MUTED)

        card = pygame.Rect(m, m + 70, min(CARD_W, screen.get_width() - 2 * m), 110)
        panel(screen, card)
        pad = 12
        x, y, w = card.x + pad, card.y + pad, card.w - 2 * pad
        carrier = self._carrier()

        if carrier is not None:
            text(screen, F["body_sm"], f"{carrier.name} carries the Bankers' sealed chest.",
                 (x, y), T.TX_MUTED)
            y += 30
            r = pygame.Rect(x, y, w, 36)
            self.add_button(screen, r, "exchange", "HAND OVER THE CHEST", primary=True)
        else:
            text(screen, F["body_sm"], "Nothing to hand over here.", (x, y), T.TX_FAINT)

        self._draw_footer(screen)

    def _draw_footer(self, screen):
        footer_bar(self, screen, self._F, primary=("done", "LEAVE LEDGER HOLD"), notice=self.notice)

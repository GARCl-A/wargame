"""Arena purse: pick which member of the winning squad pockets the prize.

Shown after a won arena bout. The purse is copper; it lands whole on the one
member you click (the guild has no shared treasury). `on_done` returns to the map.
"""

import pygame

from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, INFO, INK, INK_DIM, INK_FAINT, LINE_SOFT,
                    MARGIN, RADIUS, SP3, SURFACE_2, SURFACE_3,
                    panel, token_badge, text, tracked)


class RewardScreen(Screen):
    native = True

    def __init__(self, fonts, guild, members, amount, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.members = members
        self.amount = amount
        self.on_done = on_done
        self.paid_to = None                   # member who took the purse
        self.cards = []                      # [(rect, member)]
        self.buttons = []                   # [(key, rect)]

    # ------------------------------------------------------------------ #
    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px) and key == "done" and self.paid_to is not None:
                self.on_done()
                return
        if self.paid_to is not None:
            return
        for rect, member in self.cards:
            if rect.collidepoint(px):
                member.gold += self.amount
                self.paid_to = member
                return

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self.cards = []
        self.buttons = []

        text(screen, "ARENA PURSE", f.title, INK, (MARGIN, MARGIN - 2))
        if self.paid_to is None:
            sub, col = (f"{self.amount} copper  ·  click who pockets the purse", ACCENT)
        else:
            sub, col = (f"{self.paid_to.name} pockets {self.amount} copper "
                        f"(now on {self.paid_to.gold})", INFO)
        text(screen, sub, f.body, col, (MARGIN, MARGIN + 30))

        n = max(1, len(self.members))
        gap = SP3
        top = MARGIN + 80
        card_w = min(260, (screen.get_width() - 2 * MARGIN - (n - 1) * gap) // n)
        card_h = 150
        for i, m in enumerate(self.members):
            rect = pygame.Rect(MARGIN + i * (card_w + gap), top, card_w, card_h)
            self._draw_card(screen, rect, m)
            self.cards.append((rect, m))

        self._draw_footer(screen)

    def _draw_card(self, screen, rect, m):
        f = self.fonts
        pad = SP3
        took = m is self.paid_to
        hov = rect.collidepoint(self.mouse) and self.paid_to is None
        panel(screen, rect, fill=SURFACE_2,
              border=ACCENT if (took or hov) else LINE_SOFT,
              width=2 if (took or hov) else 1, radius=RADIUS)

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, m, f)
        text(screen, m.name, f.card_name, INK, (tok[0] + 24, rect.y + pad))
        text(screen, f"{m.race['name']}  ·  {m.occupation['name']}", f.body_sm,
             INK_DIM, (tok[0] + 24, rect.y + pad + 20))

        y = rect.y + pad + 52
        tracked(screen, "COPPER", f.label, INFO, (rect.x + pad, y))
        text(screen, str(m.gold), f.num, ACCENT if took else INK, (rect.x + pad, y + 14))
        if not took and self.paid_to is None:
            text(screen, "click to hand over the purse", f.label, INK_FAINT,
                 (rect.x + pad, rect.bottom - 22))
        elif took:
            text(screen, f"+{self.amount}", f.body_bd, ACCENT,
                 (rect.right - pad, y + 16), right=True)

    def _draw_footer(self, screen):
        f = self.fonts
        done = self.paid_to is not None
        d = pygame.Rect(screen.get_width() - MARGIN - 240, screen.get_height() - 56, 240, 36)
        hov = d.collidepoint(self.mouse)
        panel(screen, d, fill=ACCENT if (done and hov) else SURFACE_3 if done else SURFACE_2,
              border=ACCENT if done else LINE_SOFT, width=1, radius=RADIUS)
        text(screen, "CONTINUE", f.body_bd,
             ACCENT_INK if (done and hov) else ACCENT if done else INK_FAINT,
             d.center, center=True)
        self.buttons.append(("done", d))

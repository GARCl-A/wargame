"""Arena purse: pick which member of the winning squad pockets the prize.

Shown after a won arena bout. The purse is copper; it lands whole on the one
member you click (the guild has no shared treasury). If the bout also completed
a faction deed (`deeds`), a banner names it above the cards; `note` adds one more
line (the Champion of the Pit title changing hands). `on_done` returns to the map.
"""

import pygame

from . import factions
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .theme import set_pointer, token_badge
from .ui.primitives import caps, draw_button, header, panel, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class RewardScreen(SheetModalMixin, Screen):
    native = True

    def __init__(self, fonts, guild, members, amount, on_done, deeds=(), note=None):
        super().__init__()
        self.fonts = fonts
        self._F = None
        self.guild = guild
        self.members = members
        self.amount = amount
        self.on_done = on_done
        self.deeds = list(deeds)              # factions.Deed completed by this bout
        self.note = note                      # extra one-liner (arena title change), or None
        self.paid_to = None                   # member who took the purse
        self.cards = []                      # [(rect, member)]
        self.info_hits = []                # [(rect, member)] -- the card's 'i' disc opens the sheet
        self.buttons = []                   # [(key, rect)]

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "reward"

    # ------------------------------------------------------------------ #
    def _click(self, px):
        if self.close_sheet_on_click():
            return
        for rect, member in self.info_hits:
            if rect.collidepoint(px):
                self.open_sheet(member)
                return
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
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.cards = []
        self.info_hits = []
        self.buttons = []

        head = pygame.Rect(0, 0, W, T.S * 9)
        if self.paid_to is None:
            sub = f"{self.amount} copper  ·  click who pockets the purse"
        else:
            sub = f"{self.paid_to.name} pockets {self.amount} copper (now on {self.paid_to.gold})"

        header(screen, F, head, "ARENA PURSE", sub, (), None, mpos=self.mouse)

        top = head.bottom + T.S * 3
        for d in self.deeds:
            fac = factions.faction(d.faction).name
            br = pygame.Rect(T.S * 3, top, min(W - T.S * 6, 640), 40)
            panel(screen, br)
            text(screen, F["bodyb"], f"DEED  ·  {d.name}", (br.x + T.S * 2, br.y + 5), T.GREEN)
            text(screen, F["body_sm"], f"{d.blurb}   +{d.rep} reputation with {fac}",
                 (br.x + T.S * 2, br.y + 22), T.TX_MUTED)
            top = br.bottom + T.S * 2

        if self.note:
            nr = pygame.Rect(T.S * 3, top, min(W - T.S * 6, 640), 32)
            panel(screen, nr)
            text(screen, F["body_sm"], self.note, (nr.x + T.S * 2, nr.y + 8), T.BRASS)
            top = nr.bottom + T.S * 2

        n = max(1, len(self.members))
        gap = T.S * 2
        card_w = min(260, (W - 2 * T.S * 3 - (n - 1) * gap) // n)
        card_h = 150
        for i, m in enumerate(self.members):
            rect = pygame.Rect(T.S * 3 + i * (card_w + gap), top, card_w, card_h)
            self._draw_card(screen, F, rect, m)
            self.cards.append((rect, m))

        self._draw_footer(screen, F, W, H)
        self.draw_sheet_modal(screen, self.fonts)

        set_pointer(self._hovering())

    def _hovering(self):
        if any(r.collidepoint(self.mouse) for r, _ in self.info_hits): return True
        if any(r.collidepoint(self.mouse) for r, _ in self.cards) and self.paid_to is None: return True
        if any(r.collidepoint(self.mouse) for k, r in self.buttons if k == "done") and self.paid_to is not None: return True
        return False

    def _draw_card(self, screen, F, rect, m):
        pad = T.S * 2
        took = m is self.paid_to
        hov = rect.collidepoint(self.mouse) and self.paid_to is None
        panel(screen, rect, hover=(took or hov))

        badge = self.sheet_badge(screen, (rect.right - pad, rect.y + pad), self.fonts)
        self.info_hits.append((badge, m))

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, m, self.fonts)
        text(screen, F["head"], m.name, (tok[0] + 24, rect.y + pad), T.TX)
        text(screen, F["body_sm"], f"{m.race['name']}  ·  {m.occupation['name']}",
             (tok[0] + 24, rect.y + pad + 20), T.TX_MUTED)

        y = rect.y + pad + 52
        caps(screen, F["microb"], "COPPER", (rect.x + pad, y), T.BRASS)
        text(screen, F["big"], str(m.gold), (rect.x + pad, y + 14), T.BRASS if took else T.TX)
        if not took and self.paid_to is None:
            text(screen, F["micro"], "click to hand over the purse",
                 (rect.x + pad, rect.bottom - 22), T.TX_FAINT)
        elif took:
            text(screen, F["bodyb"], f"+{self.amount}",
                 (rect.right - pad, y + 16), T.BRASS, right=True)

    def _draw_footer(self, screen, F, W, H):
        done = self.paid_to is not None
        d = pygame.Rect(W - T.S * 3 - 240, H - T.S * 4 - 36, 240, 36)
        draw_button(screen, F, d, "CONTINUE", primary=True, enabled=done, mpos=self.mouse)
        self.buttons.append(("done", d))

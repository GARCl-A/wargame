"""The Gathering tab of a work node (Lumber Yard, Mine): buy licence and pick gathering shifts."""

import pygame

from . import gather, orders
from .constants import fmt_money
from .screen import Screen
from .ui.primitives import caps, draw_button, footer_bar, header, panel, set_pointer, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

SHIFTS = (4, 8, 12, 16)


class GatherScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, node, on_done):
        super().__init__()
        self.fonts = fonts
        self._F = fonts if (isinstance(fonts, dict) and "body" in fonts) else ui_fonts()
        self.guild = guild
        self.group = group
        self.node = node
        self.on_done = on_done
        self.buttons = []
        self._hot = False
        self.notice = None

    def tutorial_key(self):
        return None

    def handle_escape(self):
        self.on_done()
        return True

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self.buttons:
                if rect.collidepoint(event.pos):
                    self._on_button(key)
                    return

    def _on_button(self, key):
        if key == "leave":
            self.on_done()
        elif key == "buy_licence":
            if self.guild.buy_licence(self.node.id, self.group):
                self.notice = f"{self.node.name}: Gathering licence acquired!"
            else:
                self.notice = "Not enough funds to buy the licence."
        elif key.startswith("gather:"):
            hours = int(key.split(":")[1])
            self.group.order = orders.work(self.guild, self.group, hours, gather=True)
            self.on_done()

    def update(self, dt):
        pass

    def add_button(self, surf, rect, key, label, enabled=True, primary=False, danger=False):
        self.buttons.append((key, rect))
        return draw_button(surf, self._F, rect, label, primary=primary, enabled=enabled,
                           danger=danger, mpos=self.mouse)

    def draw(self, surf):
        W, H = surf.get_size()
        surf.fill(T.TABLE)
        F = self._F
        self.buttons.clear()
        self._hot = False

        header(surf, F, pygame.Rect(0, 0, W, 72), f"{self.node.name.upper()} — GATHERING",
               "Harvest materials instead of wages · One licence covers the whole guild",
               (), None, mpos=self.mouse)

        has_lic = self.guild.has_licence(self.node.id)
        price = gather.licence_price(self.node.id)
        shortfall = self.guild.licence_shortfall(self.node.id, self.group)

        pad = T.S * 4
        cw = min(720, W - pad * 2)
        cx = (W - cw) // 2
        cy = 96

        card_rect = pygame.Rect(cx, cy, cw, 460)
        panel(surf, card_rect)

        y = card_rect.y + T.S * 3
        # Licence Status
        caps(surf, F["micro"], "LICENCE STATUS", (cx + T.S * 3, y), T.TX_FAINT)
        y += 24
        if has_lic:
            caps(surf, F["titleb"], "ACTIVE FOR THE GUILD", (cx + T.S * 3, y), T.GREEN)
        else:
            caps(surf, F["titleb"], f"NOT HELD — {fmt_money(price)}", (cx + T.S * 3, y), T.BRASS)
            if shortfall > 0:
                text(surf, F["body_sm"], f"Group is short {fmt_money(shortfall)}", (cx + T.S * 3, y + 28), T.TX_MUTED)
        y += 48

        # Drop Table
        caps(surf, F["micro"], "DROP TABLE (PERCENT PER ROLL)", (cx + T.S * 3, y), T.TX_FAINT)
        y += 20
        drops = gather.drops(self.node.id)
        drop_str = "   ·   ".join(f"{name}: {pct}%" for name, pct in drops)
        text(surf, F["body"], drop_str, (cx + T.S * 3, y), T.TX)
        y += 40

        # Info notes
        text(surf, F["body_sm"], f"Shift yield: {gather.rolls(16):.1f} rolls/worker for 16 h · Pro-rated for shorter shifts.",
             (cx + T.S * 3, y), T.TX_MUTED)
        y += 24
        text(surf, F["body_sm"], "A pack may ambush the crew · Fight must be won to secure the haul.",
             (cx + T.S * 3, y), T.BLOOD)
        y += 44

        # Action buttons
        if not has_lic:
            btn_r = pygame.Rect(cx + T.S * 3, y, 320, 44)
            can_buy = shortfall == 0
            self.add_button(surf, btn_r, "buy_licence", f"BUY LICENCE ({fmt_money(price)})",
                            primary=can_buy, enabled=can_buy)
        else:
            caps(surf, F["micro"], "START A GATHERING SHIFT", (cx + T.S * 3, y), T.TX_FAINT)
            y += 24
            btn_w = (cw - T.S * 6 - (len(SHIFTS) - 1) * T.S * 2) // len(SHIFTS)
            for i, h in enumerate(SHIFTS):
                btn_r = pygame.Rect(cx + T.S * 3 + i * (btn_w + T.S * 2), y, btn_w, 40)
                self.add_button(surf, btn_r, f"gather:{h}", f"{h} HOURS", primary=True)

        if self.notice:
            text(surf, F["body"], self.notice, (cx + T.S * 3, card_rect.bottom - 40), T.BRASS)

        footer_bar(self, surf, F, back=("leave", "BACK TO MAP"))
        set_pointer(any(r.collidepoint(self.mouse) for _, r in self.buttons))

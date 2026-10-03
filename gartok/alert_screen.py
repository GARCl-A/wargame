"""Generic alert popup used for starvation, death, and hunger notifications.

Modernized to the `gartok/ui/` design system using `modal_card`.
"""

import pygame

from .screen import Screen
from .ui.tokens import T, fonts as ui_fonts
from .ui.primitives import modal_card, text, caps, draw_button, hline, wrap


class AlertScreen(Screen):
    native = True

    def __init__(self, fonts, resume_to, title, messages, on_done, is_danger=False):
        super().__init__()
        self.fonts = fonts
        self._F = fonts if (isinstance(fonts, dict) and "body" in fonts) else ui_fonts()
        self.resume_to = resume_to
        self.native = getattr(resume_to, "native", True)
        self.title = title
        self.messages = list(messages) if isinstance(messages, (list, tuple)) else [str(messages)]
        self.on_done = on_done
        self.is_danger = is_danger
        self.buttons = []
        self._hot = False

    def handle_escape(self):
        self.on_done()
        return True

    def on_button(self, key):
        if key == "ok":
            self.on_done()

    def _click(self, pos):
        for key, rect in self.buttons:
            if rect.collidepoint(pos):
                self.on_button(key)
                return

    def card_rect(self, size):
        W, H = size
        box_w = min(500, W - 48)
        inner_w = box_w - 48
        wrapped = []
        for m in self.messages:
            for ln in wrap(self._F["body"], m, inner_w):
                wrapped.append(ln)
        line_h = 24
        content_h = max(28, len(wrapped) * line_h)
        box_h = 20 + 20 + 28 + 16 + content_h + 24 + 40 + 20
        r = pygame.Rect(0, 0, box_w, box_h)
        r.center = (W // 2, H // 2)
        return r

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_ESCAPE):
                self.on_done()
                return
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)

    def update(self, dt):
        if self.resume_to is not None and hasattr(self.resume_to, "update"):
            try:
                self.resume_to.update(dt)
            except Exception:
                pass

    def draw(self, screen):
        F = self._F
        W, H = screen.get_size()
        self.buttons.clear()
        self._hot = False

        # Draw underlying frozen scene if available
        if self.resume_to is not None:
            try:
                self.resume_to.mouse = (-1, -1)
                self.resume_to.draw(screen)
            except Exception:
                screen.fill(T.TABLE)
        else:
            screen.fill(T.TABLE)

        # Wrap body lines
        box_w = min(500, W - 48)
        inner_w = box_w - 48
        wrapped = []
        for m in self.messages:
            for ln in wrap(F["body"], m, inner_w):
                wrapped.append(ln)

        line_h = 24
        content_h = max(28, len(wrapped) * line_h)
        box_h = 20 + 20 + 28 + 16 + content_h + 24 + 40 + 20

        card = modal_card(screen, (box_w, box_h), veil=True)
        border_col = T.BLOOD if self.is_danger else T.BRASS
        pygame.draw.rect(screen, border_col, card, 2 if self.is_danger else 1, border_radius=4)

        # Header
        cx = card.x + 24
        cy = card.y + 20
        tag = "CRITICAL ALERT" if self.is_danger else "NOTICE"
        caps(screen, F["microb"], tag, (cx, cy), border_col)
        cy += 18
        text(screen, F["head"], self.title, (cx, cy), T.TX)
        cy += 30
        hline(screen, card.x + 20, card.right - 20, cy)
        cy += 16

        # Messages
        for ln in wrapped:
            text(screen, F["body"], ln, (cx, cy), T.TX)
            cy += line_h

        # Right-aligned confirm button
        bw, bh = 130, 38
        btn_r = pygame.Rect(card.right - 24 - bw, card.bottom - 20 - bh, bw, bh)
        draw_button(screen, F, btn_r, "OK", primary=True, danger=self.is_danger, mpos=self.mouse)
        self.buttons.append(("ok", btn_r))

        if btn_r.collidepoint(self.mouse):
            self._hot = True

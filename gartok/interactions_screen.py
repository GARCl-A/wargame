"""A consolidated menu for on-node interactions (Tanner, Forge, Bankers).

Instead of cluttering the map screen's side panel with multiple buttons, this
screen lists all available interactions for the group's current node. Choosing
one issues the corresponding `orders.interactive` order and returns to the map
(which then auto-advances if no groups are left idle).
"""

import pygame

from . import world
from .screen import Screen
from .theme import (INK, INK_DIM, INK_FAINT, LINE_SOFT, MARGIN, RADIUS,
                    SURFACE_2, SURFACE_3, panel, text)
from .widgets import ButtonsMixin, footer_bar

class InteractionsScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, group, on_back, on_action):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.on_back = on_back
        self.on_action = on_action
        self.buttons = []

    def tutorial_key(self):
        return None

    def handle_escape(self):
        self.on_back()
        return True

    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "back":
                self.on_back()
            else:
                self.on_action(key)
            return

    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self._reset_buttons()

        here = world.node(self.group.node)

        text(screen, "AVAILABLE INTERACTIONS", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, f"at {here.name}", f.body, INK_DIM, (MARGIN, MARGIN + 30))

        top = MARGIN + 90
        w = min(560, screen.get_width() - 2 * MARGIN)
        cx = MARGIN

        interactions = []
        if here.tanner:
            interactions.append(("tanner", "TALK TO THE TANNER", "a paid job, on the clock -- see what's on offer"))
        if here.trust:
            interactions.append(("trust", "TALK TO THE BANKERS", "a test of trust -- see what they're offering"))

        y = top
        for key, label, note in interactions:
            r = pygame.Rect(cx, y, w, 56)
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if hov else SURFACE_2, border=LINE_SOFT,
                  width=2 if hov else 1, radius=RADIUS)
            text(screen, label, f.body_bd, INK_DIM, (r.x + 20, r.y + 10))
            text(screen, note, f.body_sm, INK_FAINT, (r.x + 20, r.y + 32))
            self.buttons.append((key, r))
            y += 72

        self._draw_footer(screen)

    def _draw_footer(self, screen):
        footer_bar(self, screen, primary=("back", "BACK"))

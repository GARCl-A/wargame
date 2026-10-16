"""The group hand-over card: a beat that says whose turn it is.

With more than one group, the clock can hand the screen from one group to another by
itself: group A's Tavern opens right after group B was ordered away, or the map lands on a
band other than the one in view. This card names the group, where it stands and what is
about to happen, over a frozen view of the screen behind it; one click (or Enter / Space /
Esc) goes on.
"""

import pygame

from . import world
from .screen import Screen
from .ui.banner import player_color
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .ui.turn_card import draw_turn_card


def needed(guild):
    """A hand-over card only means something with two or more groups."""
    return sum(1 for g in guild.groups if not g.empty) > 1


class GroupTurnScreen(Screen):
    native = True

    def tutorial_key(self):
        return "group_turn"

    def __init__(self, fonts, guild, group, action, on_go, resume_to=None, danger=False):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.group = group
        self.action = action
        self.on_go = on_go
        self.resume_to = resume_to
        self.danger = danger
        self._button = None
        self._hot = False

    def card(self):
        live = [g for g in self.guild.groups if not g.empty]
        i = live.index(self.group) + 1 if self.group in live else 1
        return {"band": f"BAND {i} OF {len(live)}  ·  ITS TURN",
                "name": self.group.display_name,
                "node": world.node(self.group.node).name,
                "action": self.action,
                "members": [u.name for u in self.group.members],
                "color": player_color(),
                "danger": self.danger,
                "button": "GO ON"}

    def handle_escape(self):
        self.on_go()
        return True

    def handle_event(self, event):
        key = event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
        click = (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                 and self._button is not None and self._button.collidepoint(event.pos))
        if key or click:
            self.on_go()

    def draw(self, screen):
        if self.resume_to is not None:
            self.resume_to.mouse = (-1, -1)
            self.resume_to.draw(screen)
        else:
            screen.fill(T.TABLE)
        _, self._button = draw_turn_card(screen, self._F, self.card(), self.mouse)
        self._hot = self._button.collidepoint(self.mouse)

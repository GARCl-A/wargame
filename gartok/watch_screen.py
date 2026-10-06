"""The squad selector for a dangerous place the wagon cannot enter.

Everyone starts out going in; click a member to leave them outside minding the wagon. Any
one guard keeps it safe (`wagon_watch.py`); with nobody outside it may be lost for good.
The guards stay in the group, only the ones who go in take part in the activity.
"""

import pygame

from . import wagon_watch
from .screen import Screen
from .ui.primitives import draw_button, footer_bar, panel, section, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class WatchScreen(Screen):
    native = True

    def tutorial_key(self):
        return "watch"

    def __init__(self, fonts, group, node, go_label, on_confirm, on_back):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.group = group
        self.node = node
        self.go_label = go_label
        self.on_confirm = on_confirm
        self.on_back = on_back
        self.goes = set(group.members)
        self.buttons = []
        self._hot = False

    def handle_escape(self):
        self.on_back()
        return True

    @property
    def party(self):
        return [u for u in self.group.members if u in self.goes]

    @property
    def guards(self):
        return [u for u in self.group.members if u not in self.goes]

    def handle_event(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        for key, rect in self.buttons:
            if rect.collidepoint(event.pos):
                self._click(key)
                return

    def _click(self, key):
        kind, _, arg = key.partition(":")
        if kind == "toggle":
            unit = self.group.members[int(arg)]
            if unit in self.goes:
                if len(self.goes) > 1:
                    self.goes.discard(unit)
            else:
                self.goes.add(unit)
        elif kind == "go":
            self.on_confirm(self.party, bool(self.guards))
        elif kind == "back":
            self.on_back()

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False, danger=False, sub=None):
        draw_button(surf, self._F, rect, label, sub=sub, primary=primary, danger=danger,
                    enabled=enabled, mpos=self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or rect.collidepoint(self.mouse)

    def draw(self, screen):
        F = self._F
        m = T.S * 3
        screen.fill(T.TABLE)
        self.buttons = []
        self._hot = False

        text(screen, F["titleb"], "WHO MINDS THE WAGON?", (m, m - 2), T.TX)
        text(screen, F["body"], f"{self.node.name}  ·  the wagon cannot go in. Someone has to stay with it.",
             (m, m + 30), T.TX_MUTED)

        top = m + 62
        area = pygame.Rect(m, top, min(760, screen.get_width() - 2 * m), screen.get_height() - top - 80)
        panel(screen, area)
        x, w = area.x + 12, area.w - 24
        y = section(screen, F, f"THE PARTY  ({len(self.goes)} in, {len(self.guards)} outside)", x, area.y + 12, w)
        for i, unit in enumerate(self.group.members):
            going = unit in self.goes
            text(screen, F["bodyb"], unit.name, (x, y + 4), T.TX if going else T.TX_MUTED)
            self.add_button(screen, pygame.Rect(x + w - 190, y, 190, 28), f"toggle:{i}",
                            "GOES IN" if going else "MINDS THE WAGON",
                            enabled=not going or len(self.goes) > 1)
            y += 36
        self._draw_risk(screen, x, y + T.S, w)
        footer_bar(self, screen, F, primary=("go", self.go_label), back=("back", "BACK"))

    def _draw_risk(self, screen, x, y, w):
        F = self._F
        y = section(screen, F, "THE WAGON", x, y, w)
        if self.guards:
            text(screen, F["body"], "Guarded: it is safe while the party is away.", (x, y), T.TX)
            return
        chance = wagon_watch.risk(self.group, self.node)
        text(screen, F["bodyb"], f"Left alone: {chance:.0%} chance of losing it, cargo and animals with it.",
             (x, y), T.BLOOD if chance else T.TX)
        flight = wagon_watch.flight_chance(self.group)
        text(screen, F["body_sm"], f"{self.node.wagon_risk:.0%} the place  ·  {flight:.0%} the animals bolt",
             (x, y + 24), T.TX_MUTED)

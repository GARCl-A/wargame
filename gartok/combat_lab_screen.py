"""Combat lab screen: set up one of the benchmark fights and say who plays each side.

`on_start(setup)` gets `{"fight", "level", "squad", "controllers", "name"}`; the app builds the
battle (`combat_lab.build`), attaches its combat log and runs it.
"""

import pygame

from . import combat_lab
from .screen import Screen
from .ui.lab_panel import draw_lab_form
from .ui.primitives import draw_button, text
from .ui.tokens import T

_MAX_NAME = 40


class CombatLabScreen(Screen):
    native = True

    def __init__(self, fonts, on_start, on_back):
        super().__init__()
        self.F = fonts
        self.on_start = on_start
        self.on_back = on_back
        self.fight = "scrapper"
        self.level = 0
        self.squad = combat_lab.FIGHTS[self.fight].squad
        self.controllers = {"player": "human", "enemy": "ai"}
        self.name = ""
        self.editing = False
        self.hits = {}
        self.back_rect = None

    def _placeholder(self):
        return combat_lab.default_name(self.fight, self.controllers)

    def setup(self):
        return {"fight": self.fight, "level": self.level, "squad": self.squad,
                "controllers": dict(self.controllers), "name": self.name or self._placeholder()}

    def _pick(self, fight_id):
        self.fight = fight_id
        self.squad = combat_lab.FIGHTS[fight_id].squad

    def _click(self, px):
        if self.editing:
            self.editing = False
        if self.back_rect and self.back_rect.collidepoint(px):
            self.on_back()
            return
        for rect, fight_id in self.hits.get("fights", []):
            if rect.collidepoint(px):
                self._pick(fight_id)
                return
        for key, attr, lo, hi in (("level", "level", 0, combat_lab.MAX_LEVEL),
                                  ("squad", "squad", 1, combat_lab.MAX_SQUAD)):
            dec, inc = self.hits.get(key, (None, None))
            if dec and dec.collidepoint(px):
                setattr(self, attr, max(lo, getattr(self, attr) - 1))
                return
            if inc and inc.collidepoint(px):
                setattr(self, attr, min(hi, getattr(self, attr) + 1))
                return
        for key, team in (("p1", "player"), ("p2", "enemy")):
            if self.hits.get(key) and self.hits[key].collidepoint(px):
                self.controllers[team] = "ai" if self.controllers[team] == "human" else "human"
                return
        if self.hits.get("name") and self.hits["name"].collidepoint(px):
            self.editing = True
            return
        if self.hits.get("start") and self.hits["start"].collidepoint(px):
            self.on_start(self.setup())

    def handle_event(self, event):
        if self.editing and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.editing = False
            elif event.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
            elif event.unicode and len(self.name) < _MAX_NAME and event.unicode.isprintable():
                self.name += event.unicode
            return
        super().handle_event(event)

    def handle_escape(self):
        if self.editing:
            self.editing = False
            return True
        self.on_back()
        return True

    def tutorial_key(self):
        return "combat_lab"

    def draw(self, screen):
        F = self.F
        W, H = screen.get_size()
        pad = T.S * 4
        screen.fill(T.TABLE)
        text(screen, F["titleb"], "COMBAT LAB", (pad, pad - 2), T.TX)
        text(screen, F["body"], "play the benchmark fights by hand and record every decision",
             (pad, pad + 30), T.TX_MUTED)

        cw = min(720, W - 2 * pad)
        form = {"fights": [{"id": f.id, "name": f.name, "note": f.note} for f in combat_lab.FIGHTS.values()],
                "selected": self.fight, "level": self.level, "squad": self.squad,
                "p1": self.controllers["player"], "p2": self.controllers["enemy"],
                "name": self.name, "editing": self.editing, "placeholder": self._placeholder(),
                "ready": True}
        self.hits = draw_lab_form(screen, F, pygame.Rect((W - cw) // 2, pad + 70, cw, H - 2 * pad - 70),
                                  form, self.mouse)
        self.back_rect = pygame.Rect(pad, H - pad - 30, 120, 30)
        draw_button(screen, F, self.back_rect, "BACK", ghost=True, mpos=self.mouse)

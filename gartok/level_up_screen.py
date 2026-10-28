"""A character's new level: the portrait large, the level stamped, the numbers climbing
from before to after, and a way straight to the talent picks."""

import pygame

from . import sound
from .screen import Screen
from .ui.aftermath_panel import draw_level_up
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

CLIMB_MS = 900


class LevelUpScreen(Screen):
    native = True

    def __init__(self, fonts, level_up, on_done, on_talents=None, *, index=0, total=1):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.level_up = level_up
        self.on_done = on_done
        self.on_talents = on_talents
        self.tag = "LEVEL UP" if total <= 1 else f"LEVEL UP · {index + 1} OF {total}"
        self.elapsed = 0
        self._buttons = []
        self._hot = False
        sound.play("level_up")

    def tutorial_key(self):
        return "level_up"

    @property
    def progress(self):
        return min(1.0, self.elapsed / CLIMB_MS)

    def data(self):
        lu, t = self.level_up, self.progress
        track, level = lu.headline
        unit = lu.unit
        picks = self.on_talents is not None and bool(unit.pending_picks)
        return {"name": unit.name, "race": unit.race["name"], "portrait_id": unit.portrait_id,
                "stamp": f"LEVEL {level}", "track": track, "tag": self.tag,
                "gains": [(label, a, a + round((b - a) * t), b) for label, a, b in lu.gains],
                "talents": "PICK TALENTS" if picks else None, "button": "CONTINUE"}

    def update(self, dt):
        self.elapsed += dt

    def handle_escape(self):
        self.on_done()
        return True

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.on_done()
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        for key, rect in self._buttons:
            if rect is not None and rect.collidepoint(event.pos):
                (self.on_talents if key == "talents" else self.on_done)()
                return

    def draw(self, screen):
        screen.fill(T.TABLE)
        talents, button = draw_level_up(screen, self._F, self.data(), self.mouse)
        self._buttons = [("talents", talents), ("done", button)]
        self._hot = any(r is not None and r.collidepoint(self.mouse) for _, r in self._buttons)

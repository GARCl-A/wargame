"""The after-action report, the first screen after a fight: who stood, who fell, who downed
whom, the XP bars filling, the deeds earned. `on_done` goes on to the level-ups, then the
loot, the purse or the map."""

import pygame

from . import factions, progression
from .screen import Screen
from .ui.aftermath_panel import draw_report
from .ui.tokens import fonts as ui_fonts

FILL_MS = 1200


class ReportScreen(Screen):
    native = True

    def __init__(self, fonts, outcome, on_done, *, place=None, rounds=None, deeds=True, notes=()):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.outcome = outcome
        self.on_done = on_done
        self.place = place
        self.rounds = rounds
        self.deeds = deeds
        self.notes = list(notes)
        self.elapsed = 0
        self._button = None
        self._hot = False

    def tutorial_key(self):
        return "report"

    @property
    def progress(self):
        return min(1.0, self.elapsed / FILL_MS)

    def _row(self, r):
        curve = progression.COMBAT_XP_THRESHOLDS
        xp = r.xp_before + round(r.xp_gain * self.progress)
        into, span = progression.to_next(curve, xp)
        notes = [f"+{r.xp_gain} XP" if r.xp_gain else "", f"+{r.magic_gain} magic" if r.magic_gain else ""]
        return {"name": r.name, "race": r.race, "portrait_id": r.portrait_id, "status": r.status,
                "downed": r.downed, "level": curve.level(xp), "bar": into / span if span else 1.0,
                "xp_note": "  ".join(n for n in notes if n)}

    def data(self):
        o = self.outcome
        sub = " · ".join(s for s in (self.place, f"{self.rounds} rounds" if self.rounds else None) if s)
        deeds = [(f"DEED · {d.name}", f"{d.blurb}  +{d.rep} with {factions.faction(d.faction).name}")
                 for d in o.deeds_earned] if self.deeds else []
        notes = list(self.notes)
        if o.loot_pool and o.survivors:
            n = len(o.loot_pool)
            notes.append(f"{n} item{'s' if n != 1 else ''} left on the field to gather.")
        return {"result": o.result or ("VICTORY" if o.won else "DEFEAT"), "sub": sub.upper(),
                "rows": [self._row(r) for r in o.report], "takedowns": o.takedowns,
                "deeds": deeds, "notes": notes, "button": "CONTINUE"}

    def update(self, dt):
        self.elapsed += dt

    def handle_escape(self):
        self.on_done()
        return True

    def handle_event(self, event):
        key = event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
        click = (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                 and self._button is not None and self._button.collidepoint(event.pos))
        if key or click:
            self.on_done()

    def draw(self, screen):
        self._button = draw_report(screen, self._F, self.data(), self.mouse)
        self._hot = self._button.collidepoint(self.mouse)

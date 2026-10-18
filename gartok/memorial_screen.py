"""A lost character's memorial card: portrait, name, race, days with the guild, who downed
them and the line of the fall. One per death, in battle or off it."""

import pygame

from .screen import Screen
from .ui.aftermath_panel import draw_memorial
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


def card(m, tag="IN MEMORIAM", button="CONTINUE"):
    days = m.days_lived
    return {"name": m.name, "race": m.race, "occupation": m.occupation, "portrait_id": m.portrait_id,
            "cause": m.cause, "days": f"{days} day{'s' if days != 1 else ''} with the guild",
            "span": f"DAY {m.joined_day} TO DAY {m.day}", "place": m.place, "killer": m.killer,
            "line": m.line, "tag": tag, "button": button}


class MemorialScreen(Screen):
    native = True

    def __init__(self, fonts, memorial, on_done, *, resume_to=None, index=0, total=1):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.memorial = memorial
        self.on_done = on_done
        self.resume_to = resume_to
        self.tag = "IN MEMORIAM" if total <= 1 else f"IN MEMORIAM · {index + 1} OF {total}"
        self._button = None
        self._hot = False

    def tutorial_key(self):
        return "memorial"

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
        if self.resume_to is not None:
            self.resume_to.mouse = (-1, -1)
            self.resume_to.draw(screen)
        else:
            screen.fill(T.TABLE)
        self._button = draw_memorial(screen, self._F, card(self.memorial, self.tag), self.mouse)
        self._hot = self._button.collidepoint(self.mouse)


def chain(app, memorials, nxt, resume_to=None):
    """Show `memorials` one after another on `app.scene`, then call `nxt`."""
    memorials = list(memorials)

    def show(i):
        if i >= len(memorials):
            nxt()
            return
        app.scene = MemorialScreen(app.ui_fonts, memorials[i], lambda: show(i + 1),
                                   resume_to=resume_to, index=i, total=len(memorials))
    show(0)

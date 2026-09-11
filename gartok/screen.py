"""Common plumbing for the menu / campaign screens.

Every screen owns its own layout and drawing. This base only folds the three
things they all repeated verbatim: the canvas-space cursor `self.mouse` (the app
loop writes it each frame), the left-click -> `self._click(pos)` dispatch, and a
no-op `update`. Screens that need more (the battle screen also reads the
keyboard) override `handle_event` / `update` and still get `self.mouse` and the
contract.

The app loop calls `handle_event(event)`, `update(dt)` and `draw(surface)` on
whatever `self.scene` is, and sets `scene.mouse` before each frame.
"""

import pygame


class Screen:
    def __init__(self):
        self.mouse = (0, 0)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)

    def update(self, dt):
        pass

    def handle_escape(self):
        """Esc was pressed. Return True to consume it (e.g. cancel an aimed
        action or back out of a sub-mode) so the app does not also open the
        pause menu; False (the default) lets Esc fall through to pause."""
        return False

    def _click(self, pos):
        """Left click at canvas-space `pos`. Screens rebuild their hit lists in
        `draw` and test them here."""

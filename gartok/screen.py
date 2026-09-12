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

from .theme import MARGIN, SP2


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

    def tutorial_key(self):
        """The id (`tutorial.TUTORIALS`) of the soft tutorial card that applies
        to this screen right now, or None for no card. A screen with more than
        one teachable moment (a tab, a phase) reads its own state here -- see
        `GuildScreen.tutorial_key` switching on `self.tab`. The default is None:
        most screens (the menu, the editors, ...) never get one."""
        return None

    def tutorial_anchor(self, size):
        """Where that card (and its reopen `?` badge) sits: `(x, y, max_w, grow)`
        -- `grow` is `"down"` (the card's body extends below `(x, y)`) or `"up"`
        (it extends above). Only screens that override `tutorial_key` need to
        override this; the default is a generic top-left placement."""
        return (24, 24, 340, "down")

    def footer_anchor(self, size, *, offset=52, w=340, margin=None):
        """The shape most footer-only screens share: bottom-left, growing
        upward, clear of a footer row `offset` px tall (each screen's own
        `_draw_footer` already fixes that number -- pass it here instead of
        re-deriving the rect by hand). `margin` defaults to the theme's own
        `MARGIN`; screens with a width-dependent pad (`guild_screen.py`'s
        `pad = MARGIN if w < 1500 else SP5` pattern) pass their own."""
        W, H = size
        m = margin if margin is not None else MARGIN
        return (m, H - offset - SP2, min(w, W - 2 * m), "up")

    def _click(self, pos):
        """Left click at canvas-space `pos`. Screens rebuild their hit lists in
        `draw` and test them here."""

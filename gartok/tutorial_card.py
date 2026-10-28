"""Draws the current screen's tutorial card: a centred, veiled welcome card
(`ui/intro_card.py`) with that screen's copy (`locales/en.json` under
`tutorial.<id>`, via `i18n.t`), and a `?` badge that reopens it once dismissed.

The card is modal: `app.run` swallows every click and key while it is up (see
`App._tutorial_swallow`), so reading it never presses what lies beneath.

`app.run()` is the single place this gets called (every scene there is
`native` and drawn from one spot), so a screen opts in with nothing more than
a `tutorial_key()` override -- see `screen.py`.
"""

from . import tutorial
from .ui.intro_card import draw_intro_card
from .ui.primitives import panel, set_pointer, text
from .ui.tokens import T


def draw(surface, F, scene, state):
    """Called once a frame, right after `scene.draw(surface)`. Returns
    `(card_rect, badge_rect)` -- either may be None -- for `app.run` to
    hit-test a click against before forwarding it to the scene."""
    key = scene.tutorial_key()
    if key is None:
        return None, None
    if state.should_show(key):
        return _draw_card(surface, F, key, scene.mouse), None
    return None, _draw_badge(surface, F, scene, scene.mouse)


def _draw_card(surface, F, key, mouse):
    c = tutorial.card(key)
    rect, _ = draw_intro_card(surface, F, c["title"], c["body"], c["button"], mouse, note=c["suggestion"])
    set_pointer(True)
    return rect


def _draw_badge(surface, F, scene, mouse):
    r = scene.tutorial_badge_rect(surface.get_size())
    hot = r.collidepoint(mouse)
    panel(surface, r, hover=hot, width=2 if hot else 1)
    text(surface, F["bodyb"], "?", r.center, T.BRASS if hot else T.TX_MUTED, center=True)
    if hot:
        set_pointer(True)
    return r

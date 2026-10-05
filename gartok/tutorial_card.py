"""Draws the current screen's tutorial card: a centred, veiled welcome card
(`ui/intro_card.py`) with that screen's copy (`locales/en.json` under
`tutorial.<id>`, via `i18n.t`), and a `?` badge that reopens it once dismissed.

The card is modal: `app.run` swallows every click and key while it is up (see
`App._tutorial_swallow`), so reading it never presses what lies beneath.

`app.run()` is the single place this gets called (every scene there is
`native` and drawn from one spot), so a screen opts in with nothing more than
a `tutorial_key()` override -- see `screen.py`.
"""

import pygame

from . import i18n
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


def _resolve(key):
    title = i18n.t(f"tutorial.{key}.title")
    body = i18n.t(f"tutorial.{key}.body")
    if isinstance(body, str):
        body = [body]
    suggestion_key = f"tutorial.{key}.suggestion"
    suggestion = i18n.t(suggestion_key) if i18n.has(suggestion_key) else None
    button_key = f"tutorial.{key}.button"
    button = i18n.t(button_key if i18n.has(button_key) else "tutorial.default_button")
    return title, body, suggestion, button


def _draw_card(surface, F, key, mouse):
    title, body, suggestion, button = _resolve(key)
    rect, _ = draw_intro_card(surface, F, title, body, button, mouse, note=suggestion)
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

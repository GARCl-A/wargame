"""Draws the current screen's tutorial card: a small, non-blocking panel with
that screen's copy (`locales/en.json` under `tutorial.<id>`, via `i18n.t`) and
a `?` badge that reopens it once dismissed.

Modelled on `sheet_panel.SheetModalMixin` (drawing over a live screen), but
deliberately weaker: no veil, and only a click landing
inside the card or the badge is ever swallowed. Everything else falls through
to the screen underneath, which is what makes it "soft": it explains, it never
blocks.

`app.run()` is the single place this gets called (every scene there is
`native` and drawn from one spot), so a screen opts in with nothing more than
a `tutorial_key()` override -- see `screen.py`.
"""

import pygame

from . import i18n
from .ui.primitives import panel, set_pointer, text, wrap
from .ui.tokens import T

CARD_W = 340
BADGE_R = 10
_LH = 15


def draw(surface, F, scene, state):
    """Called once a frame, right after `scene.draw(surface)`. Returns
    `(card_rect, badge_rect)` -- either may be None -- for `app.run` to
    hit-test a click against before forwarding it to the scene."""
    key = scene.tutorial_key()
    if key is None:
        return None, None
    anchor = scene.tutorial_anchor(surface.get_size())
    if state.should_show(key):
        return _draw_card(surface, F, key, anchor, scene.mouse), None
    return None, _draw_badge(surface, F, scene, scene.mouse)


def _resolve(key):
    title = i18n.t(f"tutorial.{key}.title")
    body = i18n.t(f"tutorial.{key}.body")
    if isinstance(body, str):
        body = [body]
    suggestion_key = f"tutorial.{key}.suggestion"
    suggestion = i18n.t(suggestion_key) if i18n.has(suggestion_key) else None
    return title, body, suggestion


def _draw_card(surface, F, key, anchor, mouse):
    x, y, w, grow = anchor
    w = min(w, CARD_W)
    title, body, suggestion = _resolve(key)
    pad = T.S * 2
    inner_w = w - 2 * pad
    body_lines = [ln for para in body for ln in wrap(F["body_sm"], para, inner_w)]
    sugg_lines = wrap(F["body_sm"], suggestion, inner_w) if suggestion else []

    title_h = 20
    sugg_h = (T.S + len(sugg_lines) * _LH) if sugg_lines else 0
    h = pad + title_h + len(body_lines) * _LH + sugg_h + T.S + 14 + T.S

    rect = pygame.Rect(x, y if grow == "down" else y - h, w, h)
    panel(surface, rect, hover=True)

    ty = rect.y + T.S
    text(surface, F["bodyb"], title, (rect.x + pad, ty), T.BRASS)
    ty += title_h
    for ln in body_lines:
        text(surface, F["body_sm"], ln, (rect.x + pad, ty), T.TX_MUTED)
        ty += _LH
    if sugg_lines:
        ty += T.S
        for ln in sugg_lines:
            text(surface, F["body_sm"], ln, (rect.x + pad, ty), T.BRASS)
            ty += _LH

    text(surface, F["micro"], "click to dismiss",
         (rect.right - T.S, rect.bottom - T.S - 12), T.TX_FAINT, right=True)
    if rect.collidepoint(mouse):        # only ever raise the hand cursor here --
        set_pointer(True)               # never lower it, that's the scene's own call
    return rect


def _draw_badge(surface, F, scene, mouse):
    if hasattr(scene, "tutorial_badge_rect"):
        r = scene.tutorial_badge_rect(surface.get_size())
    else:
        W, _ = surface.get_size()
        size = 28
        r = pygame.Rect(W - size - T.S * 2, T.S * 2 - 4, size, size)
    hot = r.collidepoint(mouse)
    panel(surface, r, hover=hot, width=2 if hot else 1)
    text(surface, F["bodyb"], "?", r.center, T.BRASS if hot else T.TX_MUTED, center=True)
    if hot:
        set_pointer(True)
    return r

"""Draws the current screen's tutorial card: a small, non-blocking panel with
that screen's copy (`locales/en.json` under `tutorial.<id>`, via `i18n.t`) and
a `?` badge that reopens it once dismissed.

Modelled on `sheet_panel.SheetModalMixin` -- the repo's idiom for drawing over
a live screen -- but deliberately weaker: no veil, and only a click landing
inside the card or the badge is ever swallowed. Everything else falls through
to the screen underneath, which is what makes it "soft": it explains, it never
blocks.

`app.run()` is the single place this gets called (every scene there is
`native` and drawn from one spot), so a screen opts in with nothing more than
a `tutorial_key()` override -- see `screen.py`.
"""

import pygame

from . import i18n
from .theme import (
    ACCENT,
    INK_DIM,
    INK_FAINT,
    LINE,
    MARGIN,
    RADIUS,
    SP1,
    SP2,
    SP3,
    SURFACE_2,
    SURFACE_3,
    blit_block,
    panel,
    set_pointer,
    text,
    wrap_lines,
)

CARD_W = 340
BADGE_R = 10
_LH = 15


def draw(surface, fonts, scene, state):
    """Called once a frame, right after `scene.draw(surface)`. Returns
    `(card_rect, badge_rect)` -- either may be None -- for `app.run` to
    hit-test a click against before forwarding it to the scene."""
    key = scene.tutorial_key()
    if key is None:
        return None, None
    anchor = scene.tutorial_anchor(surface.get_size())
    if state.should_show(key):
        return _draw_card(surface, fonts, key, anchor, scene.mouse), None
    return None, _draw_badge(surface, fonts, anchor, scene.mouse)


def _resolve(key):
    title = i18n.t(f"tutorial.{key}.title")
    body = i18n.t(f"tutorial.{key}.body")
    if isinstance(body, str):
        body = [body]
    suggestion_key = f"tutorial.{key}.suggestion"
    suggestion = i18n.t(suggestion_key) if i18n.has(suggestion_key) else None
    return title, body, suggestion


def _draw_card(surface, fonts, key, anchor, mouse):
    x, y, w, grow = anchor
    w = min(w, CARD_W)
    title, body, suggestion = _resolve(key)
    inner_w = w - 2 * SP3
    body_lines = wrap_lines(body, fonts.body_sm, inner_w)
    sugg_lines = wrap_lines([suggestion], fonts.body_sm, inner_w) if suggestion else []

    title_h = 20
    body_h = len(body_lines) * _LH
    sugg_h = (SP2 + len(sugg_lines) * _LH) if sugg_lines else 0
    hint_h = SP2 + 14
    h = SP3 + title_h + body_h + sugg_h + hint_h + SP2

    rect = pygame.Rect(x, y if grow == "down" else y - h, w, h)
    panel(surface, rect, fill=SURFACE_2, border=ACCENT, width=1, radius=RADIUS)

    ty = rect.y + SP2
    text(surface, title, fonts.body_bd, ACCENT, (rect.x + SP3, ty))
    ty += title_h
    ty = blit_block(surface, body_lines, rect.x + SP3, ty, fonts.body_sm, INK_DIM, lh=_LH)
    if sugg_lines:
        ty += SP2
        blit_block(surface, sugg_lines, rect.x + SP3, ty, fonts.body_sm, ACCENT, lh=_LH)

    text(surface, "click to dismiss", fonts.label, INK_FAINT,
         (rect.right - SP2, rect.bottom - SP1), right=True, bottom=True)
    if rect.collidepoint(mouse):        # only ever raise the hand cursor here --
        set_pointer(True)               # never lower it, that's the scene's own call
    return rect


def _draw_badge(surface, fonts, anchor, mouse):
    W, H = surface.get_size()
    size = 26
    r = pygame.Rect(W - size - MARGIN, MARGIN, size, size)
    hot = r.collidepoint(mouse)
    panel(surface, r, fill=SURFACE_3 if hot else SURFACE_2, border=ACCENT if hot else LINE, radius=4, width=1)
    text(surface, "?", fonts.label, ACCENT if hot else INK_DIM, r.center, center=True)
    if hot:
        set_pointer(True)
    return r

"""The reputations view: one card per faction -- standing, its deeds, what its
standing unlocks -- laid out in as many columns as the width allows.

`factions` items: `{"name", "blurb", "rep", "deeds": [(name, blurb, rep, done)],
"unlocks": [(title, description, unlocked, rep_required)]}`.
"""

import pygame

from .primitives import (
    caps,
    contained,
    ellipsize,
    scrollbar,
    section,
    smooth_circle,
    text,
    tracked,
    wrap,
)
from .tokens import T

COL_MIN_W = T.S * 52
DEED_H = T.S * 5
UNLOCK_H = T.S * 5
HEAD_H = T.S * 9


def _card_h(f):
    h = HEAD_H + T.S * 3
    h += max(1, len(f["deeds"])) * DEED_H
    if f["unlocks"]:
        h += T.S * 3 + len(f["unlocks"]) * UNLOCK_H
    return h + T.S * 2


def _draw_card(surf, F, rect, f, mpos):
    pygame.draw.rect(surf, T.STEEL, rect)
    pygame.draw.rect(surf, T.STEEL_LINE, rect, 1)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4
    y = rect.y + T.S * 2

    tracked(surf, F["microb"], f["name"].upper(), (x, y), T.BRASS)
    text(surf, F["big"], str(f["rep"]), (x + w, y - 4), T.BRASS if f["rep"] else T.TX_FAINT, right=True)
    caps(surf, F["micro"], "standing", (x + w, y + 26), T.TX_FAINT, right=True)
    for i, ln in enumerate(_wrap_two(F["body_sm"], f["blurb"], w - T.S * 10)):
        text(surf, F["body_sm"], ln, (x, y + T.S * 2 + i * 16), T.TX_MUTED)
    y = rect.y + HEAD_H

    y = section(surf, F, "Deeds", x, y, w)
    if not f["deeds"]:
        text(surf, F["body_sm"], "None yet -- this faction's standing does not move.", (x, y), T.TX_FAINT)
        y += DEED_H
    for name, blurb, rep, done in f["deeds"]:
        smooth_circle(surf, T.GREEN if done else T.TX_FAINT, (x + 5, y + 9), 5, 0 if done else 1)
        text(surf, F["bodyb"], name, (x + T.S * 2, y), T.GREEN if done else T.TX)
        text(surf, F["body_sm"], ellipsize(blurb, F["body_sm"], w - T.S * 2 - T.S * 10),
             (x + T.S * 2, y + 18), T.TX_MUTED)
        caps(surf, F["microb"], "DONE" if done else f"+{rep} REP", (x + w, y + 2),
             T.GREEN if done else T.BRASS, right=True)
        y += DEED_H

    if f["unlocks"]:
        y = section(surf, F, "Unlocks", x, y + T.S, w)
        for title, desc, unlocked, req in f["unlocks"]:
            text(surf, F["bodyb"], title, (x, y), T.TX if unlocked else T.TX_MUTED)
            caps(surf, F["microb"], "UNLOCKED" if unlocked else f"NEEDS {req} REP", (x + w, y + 2),
                 T.GREEN if unlocked else T.TX_FAINT, right=True)
            text(surf, F["body_sm"], ellipsize(desc, F["body_sm"], w), (x, y + 18), T.TX_MUTED)
            y += UNLOCK_H


def _wrap_two(font, s, w):
    lines = wrap(font, s, w)
    if len(lines) > 2:
        lines = [lines[0], ellipsize(" ".join(lines[1:]), font, w)]
    return lines


def draw_reputation(surf, F, rect, factions, scroll, mpos):
    """Returns `{"content_h", "view_h"}` so the caller can clamp its scroll."""
    gap = T.S * 2
    cols = max(1, min(len(factions), (rect.w + gap) // (COL_MIN_W + gap)))
    cw = (rect.w - T.S * 2 - gap * (cols - 1)) // cols
    heights = [0] * cols
    with contained(surf, rect):
        for f in factions:
            c = heights.index(min(heights))
            r = pygame.Rect(rect.x + c * (cw + gap), rect.y - scroll + heights[c], cw, _card_h(f))
            _draw_card(surf, F, r, f, mpos)
            heights[c] += r.h + gap
    content_h = max(heights) if heights else 0
    if content_h > rect.h:
        scrollbar(surf, pygame.Rect(rect.right - T.S, rect.y, T.S, rect.h), scroll,
                  max(1, content_h - rect.h), content_h)
    return {"content_h": content_h, "view_h": rect.h}


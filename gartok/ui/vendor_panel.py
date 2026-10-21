"""A shop's keeper in the screen header: the portrait medallion and a name line.

    draw_vendor(surf, F, topleft, card, size=VENDOR_SIZE)   -> x offset the title text takes
    draw_vendor_name(surf, F, pos, card)                    -> x where the line ends
    draw_vendor_header(surf, F, rect, card, deal=None)      -> the shop screen's big header

A `card` is {"name": str, "caption": "Gnoll tanner", "portrait": "tanner.png"}. A
screen with no keeper passes None and both calls draw nothing and return 0.

The big header takes a fuller card: {"place": "The Smithy", "name", "caption", "portrait",
"line": what they say, "tongues": ["Dwarvish"], "bent": ["Lawful", "Neutral"]}, and the
party's `deal`: {"headline": "8% off", "tone": "good" | "bad" | "none", "why": [str]}, drawn
at the right edge (None: no deal block).
"""

import pygame

from .. import artwork
from .primitives import caps, text, wrap
from .tokens import T

VENDOR_SIZE = T.S * 6
_GAP = T.S * 2


def draw_vendor(surf, F, topleft, card, size=VENDOR_SIZE):
    if not card:
        return 0
    port = artwork.portrait(None, card["portrait"], size)
    if port is None:
        return 0
    surf.blit(port, topleft)
    return size + _GAP


def draw_vendor_name(surf, F, pos, card):
    if not card:
        return pos[0]
    name = text(surf, F["body_sm"], card["name"], pos, T.TX_MUTED)
    return caps(surf, F["micro"], card["caption"], (name.right + T.S, pos[1] + 2), T.TX_FAINT).right


_TONE = {"good": T.GREEN, "bad": T.BLOOD, "none": T.TX_MUTED}


def _chip(surf, F, x, y, label, color):
    w = F["micro"].size(label.upper())[0] + T.S * 2
    r = pygame.Rect(x, y, w, T.S * 2 + 4)
    pygame.draw.rect(surf, color, r, 1, border_radius=r.h // 2)
    caps(surf, F["micro"], label, (x + T.S, y + 4), color)
    return r.right + T.S - 2


def _bubble(surf, F, x, top, bottom, max_w, line):
    """The keeper's line, sitting on `bottom` unless that would climb above `top`."""
    font = F["body"]
    pad = T.S * 2
    rows = wrap(font, line, max_w - 2 * pad)[:2]
    lh = font.get_linesize()
    w = max(font.size(r)[0] for r in rows) + 2 * pad
    h = len(rows) * lh + T.S * 2
    r = pygame.Rect(x, max(top, bottom - h), w, h)
    pygame.draw.rect(surf, T.STEEL_HI, r, border_radius=T.S)
    pygame.draw.rect(surf, T.BRASS_DIM, r, 1, border_radius=T.S)
    tail = [(r.x + 1, r.y + 12), (r.x - 14, r.y + 22), (r.x + 1, r.y + 28)]
    pygame.draw.polygon(surf, T.STEEL_HI, tail)
    pygame.draw.lines(surf, T.BRASS_DIM, False, tail, 1)
    for i, row in enumerate(rows):
        text(surf, font, row, (r.x + pad, r.y + T.S + i * lh), T.TX)
    return r.bottom


def _deal(surf, F, right, y, deal):
    """The deal block, right-aligned at `right`; returns its left edge."""
    lab = caps(surf, F["micro"], "your deal", (right, y), T.TX_FAINT, right=True)
    big = text(surf, F["head"], deal["headline"], (right, lab.bottom + 4), _TONE[deal["tone"]], right=True)
    left = min(lab.x, big.x)
    y = big.bottom + T.S // 2
    for row in deal["why"]:
        r = text(surf, F["body_sm"], row, (right, y), T.TX_MUTED, right=True)
        left, y = min(left, r.x), r.bottom + 2
    return left


def draw_vendor_header(surf, F, rect, card, deal=None):
    """The keeper of a shop, big: portrait, name, tongues and bent, their line in a speech
    bubble, and the party's deal at the right. The portrait is the rect's height, so the
    screen sizes the header by the rect it hands over; a line that wraps may run below it.
    Returns the y where the header ends."""
    size = rect.h
    port = artwork.portrait(None, card["portrait"], size)
    x = rect.x
    if port is not None:
        surf.blit(port, (x, rect.y))
        x += size + T.S * 3
    right = _deal(surf, F, rect.right, rect.y, deal) - T.S * 4 if deal else rect.right
    caps(surf, F["micro"], card["place"], (x, rect.y), T.BRASS)
    name = text(surf, F["head"], card["name"], (x, rect.y + T.S * 2), T.TX)
    caps(surf, F["micro"], card["caption"], (name.right + T.S + 4, name.y + 6), T.TX_MUTED)
    cx, cy = x, name.bottom + T.S
    chips = card.get("tongues", ()) or card.get("bent", ())
    for tongue in card.get("tongues", ()):
        cx = _chip(surf, F, cx, cy, tongue, T.TX_MUTED)
    for part in card.get("bent", ()):
        cx = _chip(surf, F, cx, cy, part, T.TX_FAINT)
    top = cy + (T.S * 3 + 4 if chips else 0)
    if not card.get("line"):
        return rect.bottom
    return max(rect.bottom, _bubble(surf, F, x, top, rect.bottom, max(T.S * 20, right - x), card["line"]))

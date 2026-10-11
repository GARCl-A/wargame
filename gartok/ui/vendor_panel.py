"""A shop's keeper in the screen header: the portrait medallion and a name line.

    draw_vendor(surf, F, topleft, card, size=VENDOR_SIZE)   -> x offset the title text takes
    draw_vendor_name(surf, F, pos, card)                    -> x where the line ends

A `card` is {"name": str, "caption": "Gnoll tanner", "portrait": "tanner.png"}. A
screen with no keeper passes None and both calls draw nothing and return 0.
"""

import pygame

from .. import artwork
from .primitives import caps, text
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
    pygame.draw.circle(surf, T.STEEL_LINE, (topleft[0] + size // 2, topleft[1] + size // 2), size // 2, 1)
    return size + _GAP


def draw_vendor_name(surf, F, pos, card):
    if not card:
        return pos[0]
    name = text(surf, F["body_sm"], card["name"], pos, T.TX_MUTED)
    return caps(surf, F["micro"], card["caption"], (name.right + T.S, pos[1] + 2), T.TX_FAINT).right

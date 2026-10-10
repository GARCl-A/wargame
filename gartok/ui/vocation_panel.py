"""The vocation picker: one card per trade, with its six races and its perk.

    draw_vocation_cards(surf, F, rect, cards, selected, mpos) -> [(rect, id)]

Data is plain dicts. A `card` is
    {"id", "name", "races": [race name], "perk": str, "dormant": bool}
(`dormant`: the perk waits on a system that is not built yet). `selected` is the
chosen card's id or None. The cards lay out in as many columns as fit `rect`.
"""

import pygame

from .primitives import caps, contained, panel, text, wrap
from .tokens import T

MIN_CARD_W = T.S * 30
CARD_H = T.S * 17


def draw_vocation_cards(surf, F, rect, cards, selected, mpos):
    cols = max(1, min(3, (rect.w + T.S * 2) // (MIN_CARD_W + T.S * 2)))
    gap = T.S * 2
    card_w = (rect.w - (cols - 1) * gap) // cols
    hits = []
    for i, card in enumerate(cards):
        r = pygame.Rect(rect.x + (i % cols) * (card_w + gap),
                        rect.y + (i // cols) * (CARD_H + gap), card_w, CARD_H)
        chosen = card["id"] == selected
        hover = r.collidepoint(mpos)
        panel(surf, r, hover=hover or chosen, width=2 if (hover or chosen) else 1)
        if chosen:
            pygame.draw.rect(surf, T.GREEN, r, 2)
        _draw_card(surf, F, r, card)
        hits.append((r, card["id"]))
    return hits


def _draw_card(surf, F, r, card):
    pad = T.S * 2
    inner = r.w - 2 * pad
    with contained(surf, r):
        y = r.y + pad
        text(surf, F["head"], card["name"], (r.x + pad, y), T.TX)
        y += F["head"].get_height() + T.S
        caps(surf, F["micro"], "RACES", (r.x + pad, y), T.TX_FAINT)
        y += F["micro"].get_height() + 2
        for line in wrap(F["body_sm"], ", ".join(card["races"]), inner):
            text(surf, F["body_sm"], line, (r.x + pad, y), T.TX_MUTED)
            y += F["body_sm"].get_height()
        y += T.S
        caps(surf, F["micro"], "GUILD PERK", (r.x + pad, y), T.BRASS)
        y += F["micro"].get_height() + 2
        for line in wrap(F["body_sm"], card["perk"], inner):
            text(surf, F["body_sm"], line, (r.x + pad, y), T.TX)
            y += F["body_sm"].get_height()
        if card["dormant"]:
            caps(surf, F["microb"], "NO EFFECT YET", (r.right - pad, r.y + pad + 4), T.BLOOD, right=True)

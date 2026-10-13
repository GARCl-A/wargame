"""What a side knows of a foe: its visible traits, then the fields Intelligence has opened.

    card_height(card)                       -> px the card needs
    draw_foe_card(surf, F, rect, card, mpos) -> tooltip or None

Data is plain dicts. A `card` is
    {"name", "race", "size", "alignment", "conditions": [str], "steps": int, "steps_max": int,
     "equipment": [(label, name)], "read": str,
     "bands": [{"label": "EASY", "open": bool, "rows": [{"label", "value": str | None,
                "tip": (title, text) | None}]}]}
A row whose `value` is None is a field not learned yet and shows "?". A band with nothing open
folds into one line of its field names with their "?".
"""

import pygame

from .board_render import hp_bar
from .primitives import caps, contained, ellipsize, format_tooltip, hline, scrollbar, text, tracked
from .tokens import T

LINE = 16
HEAD_H = T.S * 4 + 4
BAR_H = T.S * 2


def _lines(card):
    n = 1 + (1 if card["conditions"] else 0) + len(card["equipment"]) + 1
    for band in card["bands"]:
        n += 1 + (len(band["rows"]) if band["open"] else 1)
    return n


def card_height(card):
    return HEAD_H + BAR_H + _lines(card) * LINE + T.S * 2


def draw_foe_card(surf, F, rect, card, mpos, scroll=0):
    tip = None
    full_h = card_height(card)
    max_scroll = max(0, full_h - rect.h)
    scroll = max(0, min(scroll, max_scroll))
    bw = rect.w - (6 if max_scroll else 0)

    with contained(surf, rect):
        y = rect.y - scroll
        text(surf, F["bodyb"], card["name"], (rect.x, y), T.TX)
        caps(surf, F["micro"], f"{card['race']} · {card['size']} · {card['alignment']}",
             (rect.x, y + T.S * 2 + 4), T.TX_FAINT)
        bar = pygame.Rect(rect.x, y + HEAD_H, bw, 6)
        hp_bar(surf, bar, card["steps"] / card["steps_max"], card["steps_max"])
        y += HEAD_H + BAR_H

        if card["conditions"]:
            caps(surf, F["micro"], "  ·  ".join(card["conditions"]), (rect.x, y), T.BLOOD)
            y += LINE
        for label, name in card["equipment"]:
            tracked(surf, F["micro"], label.upper(), (rect.x, y + 1), T.TX_FAINT)
            text(surf, F["body_sm"], ellipsize(name, F["body_sm"], bw - T.S * 9), (rect.x + T.S * 9, y), T.TX_MUTED)
            y += LINE
        caps(surf, F["micro"], card["read"], (rect.x, y + 1), T.TX_FAINT)
        y += LINE

        for band in card["bands"]:
            tracked(surf, F["micro"], band["label"], (rect.x, y + 1), T.BRASS if band["open"] else T.TX_FAINT)
            hline(surf, rect.x + T.S * 8, rect.x + bw, y + 7)
            y += LINE
            if not band["open"]:
                names = "   ".join(f"{r['label']} ?" for r in band["rows"])
                text(surf, F["body_sm"], ellipsize(names, F["body_sm"], bw), (rect.x, y), T.TX_FAINT)
                y += LINE
                continue
            for row in band["rows"]:
                row_r = pygame.Rect(rect.x, y, bw, LINE)
                text(surf, F["body_sm"], row["label"], (rect.x, y), T.TX_FAINT)
                shown = "?" if row["value"] is None else row["value"]
                text(surf, F["body_sm"], ellipsize(shown, F["body_sm"], bw - T.S * 11), (rect.x + bw, y),
                     T.TX_FAINT if row["value"] is None else T.TX, right=True)
                if row["tip"] and row_r.collidepoint(mpos):
                    tip = format_tooltip(*row["tip"], F)
                y += LINE
    if max_scroll:
        scrollbar(surf, rect, scroll, max_scroll, full_h)
    return tip

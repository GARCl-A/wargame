"""The figures on the right of a party row (the Wilds screen's roster).

    draw_party_stats(surf, F, rect, row)
    party_load(rows) -> (kg, normal, max), summed

A `row` is {"hp": (cur, max), "ac": int, "load": (kg, carry_normal, carry_max), "rations": int,
"work": (level, into, span)}; `span` 0 means the work track is maxed.
"""

import pygame

from . import load_meter
from .primitives import caps
from .tokens import T

_BAR_W = T.S * 12
_BAR_H = 6


def party_load(rows):
    return tuple(round(sum(r["load"][i] for r in rows), 1) for i in range(3))


def _hp_color(cur, mx):
    ratio = cur / mx if mx > 0 else 0
    return T.BLOOD if ratio <= 0.25 else T.BRASS if ratio <= 0.5 else T.GREEN


def draw_party_stats(surf, F, rect, row):
    right = rect.right - T.S * 2
    cur, mx = row["hp"]
    top = rect.y + T.S
    line = T.S * 2 + 2

    load = f"load {load_meter.figure(*row['load'])}".upper()
    caps(surf, F["micro"], load, (right, top), load_meter.color(*row["load"]), right=True)
    caps(surf, F["micro"], f"hp {cur}/{mx}   ac {row['ac']}",
         (right - F["micro"].size(load)[0] - T.S * 3, top), _hp_color(cur, mx), right=True)
    caps(surf, F["micro"], f"{row['rations']} rations", (right, top + line), T.GREEN, right=True)

    level, into, span = row["work"]
    by = top + line * 2
    if span:
        bar = pygame.Rect(right - _BAR_W, by + 3, _BAR_W, _BAR_H)
        pygame.draw.rect(surf, T.TABLE, bar)
        pygame.draw.rect(surf, T.STEEL_LINE, bar, 1)
        pygame.draw.rect(surf, T.BRASS, pygame.Rect(bar.x + 1, bar.y + 1,
                                                    int((bar.w - 2) * min(into / span, 1.0)), bar.h - 2))
        caps(surf, F["micro"], f"work {level}  {into}/{span} xp", (bar.x - T.S, by), T.BRASS, right=True)
    else:
        caps(surf, F["micro"], f"work {level}  maxed", (right, by), T.BRASS, right=True)

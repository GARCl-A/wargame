"""What a body carries, drawn one way on every screen.

The bar is as long as the most it can take (`carry_max`: past it nothing more is handed to
it), with a tick where the load starts to slow it (`carry_normal`: -1 speed, -2 STR/DEX).
Green up to the tick, amber past it, blood once full. The figure is always `kg / most`.
Every reading is `(kg, normal, most)`; a pack animal, a wagon or a strongbox has one limit
and passes it twice (no tick, no amber).

    state(kg, normal, most) -> FREE | SLOWED | FULL
    color(kg, normal, most), figure(kg, normal, most), note(kg, normal, most)
    status(kg, normal, most) -> (long label, color)
    draw_bar(surf, rect, kg, normal, most)
    draw(surf, F, rect, kg, normal, most) -> bottom y
"""

import pygame

from .primitives import caps
from .tokens import T

AMBER = (224, 149, 75)
FREE, SLOWED, FULL = "free", "slowed", "full"
_COLOR = {FREE: T.GREEN, SLOWED: AMBER, FULL: T.BLOOD}


def state(kg, normal, most):
    if most and kg >= most - 1e-9:
        return FULL
    return SLOWED if kg > normal + 1e-9 else FREE


def color(kg, normal, most):
    return _COLOR[state(kg, normal, most)]


def figure(kg, normal, most):
    return f"{round(kg, 1):g} / {round(most, 1):g} kg"


def note(kg, normal, most):
    s = state(kg, normal, most)
    if s == FULL:
        return "full"
    if s == SLOWED:
        return f"slowed past {round(normal, 1):g}"
    return f"slows past {round(normal, 1):g}" if normal < most else ""


def status(kg, normal, most):
    s = state(kg, normal, most)
    label = {FREE: "free", SLOWED: "slowed  -1 spd  -2 str/dex", FULL: "full: takes nothing more"}[s]
    return label, _COLOR[s]


def draw_bar(surf, rect, kg, normal, most):
    pygame.draw.rect(surf, T.TABLE, rect)
    pygame.draw.rect(surf, T.STEEL_LINE, rect, 1)
    if not most:
        return
    inner = rect.inflate(-2, -2)
    s = state(kg, normal, most)

    def x_at(w):
        return inner.x + int(inner.w * min(1.0, max(0.0, w / most)))

    if s == FULL:
        pygame.draw.rect(surf, T.BLOOD, inner)
    else:
        pygame.draw.rect(surf, T.GREEN, pygame.Rect(inner.x, inner.y, x_at(min(kg, normal)) - inner.x, inner.h))
        if s == SLOWED:
            pygame.draw.rect(surf, AMBER, pygame.Rect(x_at(normal), inner.y, x_at(kg) - x_at(normal), inner.h))
    if normal < most:
        tick = x_at(normal)
        pygame.draw.line(surf, T.TX, (tick, rect.y - 2), (tick, rect.bottom + 1), 2)


def draw(surf, F, rect, kg, normal, most, font="micro"):
    """The bar across `rect`, the figure under its left end and the note under its right."""
    draw_bar(surf, rect, kg, normal, most)
    y = rect.bottom + 4
    caps(surf, F[font], figure(kg, normal, most), (rect.x, y), color(kg, normal, most))
    caps(surf, F[font], note(kg, normal, most), (rect.right, y), T.TX_FAINT, right=True)
    return y + F[font].get_linesize()

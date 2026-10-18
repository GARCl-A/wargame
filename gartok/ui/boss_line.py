"""What a boss says before the fight: a veiled card with the speaker's portrait, name and line.

    draw_boss_line(surf, F, d, mpos) -> button rect

`d` is {"name", "race", "portrait", "caption", "line", "button" (its label), "step" ("1 / 3" or "")}.
The card sizes itself from the surface (proportional with a clamp).
"""

import pygame

from .. import artwork
from .primitives import caps, draw_button, ellipsize, panel, text, wrap
from .tokens import T

_MIN_W, _MAX_W = 460, 720
_BUTTON = (T.S * 20, T.S * 5)
_LINE_H = T.S * 3


def draw_boss_line(surf, F, d, mpos=(-1, -1)):
    W, H = surf.get_size()
    veil = pygame.Surface((W, H), pygame.SRCALPHA)
    veil.fill((6, 7, 12, 210))
    surf.blit(veil, (0, 0))

    w = int(min(max(W * 0.55, _MIN_W), _MAX_W, W - T.S * 4))
    pad = T.S * 4
    size = max(T.S * 10, min(T.S * 16, w // 4))
    tx = pad + size + T.S * 3
    inner = w - tx - pad
    lines = wrap(F["name"], f"“{d.get('line', '')}”", inner)
    text_h = T.S * 7 + len(lines) * _LINE_H
    h = min(pad + max(size, text_h) + T.S * 4 + _BUTTON[1] + pad, H - T.S * 2)

    rect = pygame.Rect(0, 0, w, h)
    rect.center = (W // 2, H // 2)
    panel(surf, rect, hover=True)
    pygame.draw.rect(surf, T.BRASS_DIM, rect.inflate(-T.S * 2, -T.S * 2), 1)

    px, py = rect.x + pad, rect.y + pad
    port = artwork.portrait(d.get("race"), d.get("portrait"), size)
    if port is not None:
        surf.blit(port, (px, py))
    else:
        icon = artwork.race_icon(d.get("race"), size // 2, T.TX_MUTED)
        if icon is not None:
            surf.blit(icon, (px + size // 4, py + size // 4))
    pygame.draw.circle(surf, T.BRASS_DIM, (px + size // 2, py + size // 2), size // 2, 1)

    x = rect.x + tx
    text(surf, F["titleb"], ellipsize(d.get("name", ""), F["titleb"], inner), (x, py), T.BRASS)
    caps(surf, F["micro"], d.get("caption", ""), (x, py + T.S * 4), T.TX_FAINT)
    if d.get("step"):
        caps(surf, F["micro"], d["step"], (rect.right - pad, py), T.TX_FAINT, right=True)
    y = py + T.S * 7
    for ln in lines:
        text(surf, F["name"], ln, (x, y), T.TX)
        y += _LINE_H

    button = pygame.Rect(0, 0, *_BUTTON)
    button.bottomright = (rect.right - pad, rect.bottom - pad)
    draw_button(surf, F, button, d.get("button", "FIGHT"), primary=True, mpos=mpos)
    return button

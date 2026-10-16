"""The group hand-over card: whose turn it is when the clock moves the player from one
group to another.

`draw_turn_card(surf, F, d, mpos)` takes a plain dict:

- `band`: the small tag on top ("BAND 2 OF 3");
- `name`: the group's name; `node`: where it stands;
- `action`: what is about to happen ("ENTER THE TAVERN", "AWAITS ORDERS");
- `members`: the names in the group;
- `color`: the banner colour of the stripe; `danger`: a forced fight (blood instead of brass);
- `button`: the label of the one button.

It veils what is behind it, sizes itself from the surface (proportional with a clamp) and
returns `(card_rect, button_rect)`.
"""

import pygame

from .primitives import caps, draw_button, ellipsize, hline, modal_card, text, wrap
from .tokens import T

_MIN_W, _MAX_W = 420, 620
_BUTTON = (T.S * 20, T.S * 5)


def draw_turn_card(surf, F, d, mpos=(-1, -1)):
    W, _ = surf.get_size()
    w = int(min(max(W * 0.42, _MIN_W), _MAX_W, W - T.S * 4))
    pad = T.S * 4
    inner = w - 2 * pad
    crew = wrap(F["body"], ", ".join(d.get("members", ())), inner)[:3]
    h = pad + T.S * 3 + T.S * 5 + T.S * 3 + T.S * 4 + T.S * 2 + len(crew) * T.S * 3 + T.S * 4 + _BUTTON[1] + pad
    accent = T.BLOOD if d.get("danger") else T.BRASS

    rect = modal_card(surf, (w, h), veil=True)
    pygame.draw.rect(surf, accent, rect, 2 if d.get("danger") else 1, border_radius=4)
    stripe = pygame.Rect(rect.x, rect.y, T.S, rect.h)
    pygame.draw.rect(surf, d.get("color", accent), stripe, border_top_left_radius=4, border_bottom_left_radius=4)

    x, y = rect.x + pad, rect.y + pad
    caps(surf, F["microb"], d.get("band", ""), (x, y), accent)
    y += T.S * 3
    text(surf, F["titleb"], ellipsize(d["name"], F["titleb"], inner), (x, y), T.TX)
    y += T.S * 5
    text(surf, F["body"], f"at {d['node']}", (x, y), T.TX_MUTED)
    y += T.S * 3
    hline(surf, x, rect.right - pad, y + T.S)
    y += T.S * 2
    caps(surf, F["bodyb"], d.get("action", ""), (x, y), accent)
    y += T.S * 4
    for ln in crew:
        text(surf, F["body"], ln, (x, y), T.TX_MUTED)
        y += T.S * 3

    button = pygame.Rect(0, 0, *_BUTTON)
    button.bottomright = (rect.right - pad, rect.bottom - pad)
    draw_button(surf, F, button, d.get("button", "GO ON"), primary=True,
                danger=bool(d.get("danger")), mpos=mpos)
    return rect, button

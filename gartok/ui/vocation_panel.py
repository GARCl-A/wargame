"""The vocation picker: one card per trade, with its six races and its perk.

    draw_vocation_cards(surf, F, rect, cards, selected, mpos) -> [(rect, id)]
    draw_steps(surf, F, topright, steps, current)             -> None

Data is plain dicts. A `card` is
    {"id", "name", "motto": str, "races": [race name], "perk": str, "dormant": bool,
     "icon": (kind, tone, shape)}
(`dormant`: the perk waits on a system that is not built yet; `icon` is what
`item_icons.draw_item_icon` takes). `selected` is the chosen card's id or None. The
cards lay out in as many columns as fit `rect` (up to 3), as tall as the room allows
past their content, and the grid is centred in `rect`. `steps` are the founding's
step names, `current` the index of this one.
"""

import pygame

from .item_icons import draw_item_icon
from .primitives import (
    contained,
    ellipsize,
    medallion,
    small_caps,
    spaced,
    spaced_width,
    text,
    wrap,
)
from .tokens import T, mix

MIN_CARD_W = T.S * 36
PAD = T.S * 3
GAP = T.S * 3
# the first that fits the room: faces with names, small faces, the races as one line of text
LAYOUTS = ({"icon": T.S * 7, "gap": T.S * 3, "face": T.S * 10, "named": True},
           {"icon": T.S * 5, "gap": T.S, "face": T.S * 4, "named": False},
           {"icon": T.S * 5, "gap": T.S, "face": 0, "named": False})


def _face_px(inner, lay):
    return max(T.S * 4, min(lay["face"], (inner - 5 * T.S) // 6)) if lay["face"] else 0


def _head_h(F, lay):
    return max(lay["icon"], F["hub_title"].get_height() + 2 + F["hub_quote_sm"].get_height())


def _content_height(F, inner, card, lay):
    perk_lines = len(wrap(F["hub_body"], card["perk"], inner))
    names = T.S + F["hub_sub"].get_height() if lay["named"] else 0
    faces = _face_px(inner, lay) + T.S if lay["face"] else 0
    return (2 * PAD + _head_h(F, lay) + lay["gap"] + F["hub_label"].get_height() + faces
            + names + lay["gap"] + F["hub_label"].get_height() + T.S
            + perk_lines * (F["hub_body"].get_height() + 4))


def draw_vocation_cards(surf, F, rect, cards, selected, mpos):
    cols = max(1, min(3, (rect.w + GAP) // (MIN_CARD_W + GAP)))
    rows = (len(cards) + cols - 1) // cols
    card_w = (rect.w - (cols - 1) * GAP) // cols
    room = (rect.h - (rows - 1) * GAP) // rows
    for lay in LAYOUTS:
        need = max(_content_height(F, card_w - 2 * PAD, c, lay) for c in cards)
        if need <= room:
            break
    card_h = max(need, min(need + T.S * 3, room))
    top = rect.y + max(0, (rect.h - rows * card_h - (rows - 1) * GAP) // 2)
    hits = []
    for i, card in enumerate(cards):
        r = pygame.Rect(rect.x + (i % cols) * (card_w + GAP), top + (i // cols) * (card_h + GAP),
                        card_w, card_h)
        _draw_card(surf, F, r, card, card["id"] == selected, r.collidepoint(mpos), lay)
        hits.append((r, card["id"]))
    return hits


def _draw_card(surf, F, r, card, chosen, hover, lay):
    fill = mix(T.STEEL, T.BRASS, 0.07) if chosen else (mix(T.STEEL, T.BRASS, 0.03) if hover else T.STEEL)
    pygame.draw.rect(surf, fill, r, border_radius=8)
    pygame.draw.rect(surf, T.BRASS if (chosen or hover) else T.STEEL_LINE, r, 2 if chosen else 1,
                     border_radius=8)
    inner = r.w - 2 * PAD
    x = r.x + PAD
    with contained(surf, r):
        y = r.y + PAD
        box = pygame.Rect(x, y, lay["icon"], lay["icon"])
        pygame.draw.rect(surf, T.TABLE, box, border_radius=6)
        pygame.draw.rect(surf, T.BRASS_DIM if chosen else T.STEEL_LINE, box, 1, border_radius=6)
        kind, tone, shape = card["icon"]
        draw_item_icon(surf, box.inflate(-T.S, -T.S), kind, tone, **shape)
        tx = box.right + T.S * 2
        name = small_caps(surf, F["hub_title"], F["hub_title_sc"], card["name"], (tx, y),
                          T.BRASS if chosen else T.TX)
        if card.get("motto"):
            text(surf, F["hub_quote_sm"], ellipsize(card["motto"], F["hub_quote_sm"], r.right - PAD - tx),
                 (tx, name.bottom + 2), T.TX_MUTED)
        if chosen:
            spaced(surf, F["hub_label"], "Chosen", (r.right - PAD, y + 4), T.BRASS, anchor="topright")
        elif card["dormant"]:
            spaced(surf, F["hub_label"], "No effect yet", (r.right - PAD, y + 4), T.BLOOD, anchor="topright")
        y += _head_h(F, lay) + lay["gap"]

        spaced(surf, F["hub_label"], "Its races", (x, y), T.TX_FAINT)
        if not lay["named"]:
            text(surf, F["hub_sub"], ellipsize(", ".join(card["races"]), F["hub_sub"], inner - T.S * 12),
                 (r.right - PAD, y - 1), T.TX_MUTED, right=True)
        y += F["hub_label"].get_height()
        px = _face_px(inner, lay)
        if px:
            y += T.S
        step = (inner - px) / 5
        for i, race in enumerate(card["races"]):
            cx = round(x + px / 2 + i * step)
            medallion(surf, (cx, y + px // 2), race, 0, px)
            if lay["named"]:
                label = ellipsize(race, F["hub_sub"], round(step) - 2)
                img = F["hub_sub"].render(label, True, T.TX_MUTED)
                surf.blit(img, img.get_rect(midtop=(cx, y + px + T.S)))
        y += px + (T.S + F["hub_sub"].get_height() if lay["named"] else 0) + lay["gap"]

        spaced(surf, F["hub_label"], "Guild perk", (x, y), T.BRASS)
        y += F["hub_label"].get_height() + T.S
        for line in wrap(F["hub_body"], card["perk"], inner):
            text(surf, F["hub_body"], line, (x, y), T.TX)
            y += F["hub_body"].get_height() + 4


def draw_steps(surf, F, topright, steps, current):
    font = F["hub_label"]
    sep = "  ·  "
    widths = [spaced_width(font, f"{i + 1}  {s}") for i, s in enumerate(steps)]
    x = topright[0] - sum(widths) - font.size(sep)[0] * (len(steps) - 1)
    for i, s in enumerate(steps):
        color = T.BRASS if i == current else (T.TX_MUTED if i < current else T.TX_FAINT)
        r = spaced(surf, font, f"{i + 1}  {s}", (x, topright[1]), color)
        x = r.right
        if i < len(steps) - 1:
            x = text(surf, font, sep, (x, topright[1]), T.TX_FAINT).right

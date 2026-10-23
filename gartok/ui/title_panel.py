"""The title screen: the game's name, the main menu and the last guild played.

    draw_title(surf, F, rect, title, subtitle, tagline, quote) -> y under the block
    draw_menu(surf, F, rect, items, mpos, row_h)           -> [(key, rect, enabled)]
    title_height(F, w, quote) / menu_height(items, row_h)  -> the heights, to centre the block
    draw_campaign(surf, F, rect, card, mpos)               -> the rect it took (click = continue)
    draw_invite(surf, F, rect, faces)                      -> None

Data is plain dicts. A menu `item` is {"key", "label", "hint": str|None, "primary": bool,
"enabled": bool}, or None for a gap between groups. A campaign `card` is
    {"name", "vocation": str|None, "day", "members", "wins", "saved": str,
     "color": (r, g, b), "icon": banner slug, "faces": [{"name", "race", "portrait"}]}
`faces` for the invite are the same face dicts, shown as a row with no names.
"""

import pygame

from .draft_panel import draw_shield
from .primitives import contained, ellipsize, medallion, small_caps, spaced, text, wrap
from .tokens import T, mix

ROW_H = T.S * 6
GROUP_GAP = T.S * 3
FACE = T.S * 10


def title_height(F, w, quote):
    return (F["hub_label"].get_height() + T.S + F["display"].get_height() - T.S + F["hub_head"].get_height()
            + T.S * 5 + len(wrap(F["hub_quote"], quote, w)) * (F["hub_quote"].get_height() + 2))


def menu_height(items, row_h=ROW_H):
    return sum(GROUP_GAP if i is None else row_h + 2 for i in items) - 2


def draw_title(surf, F, rect, title, subtitle, tagline, quote):
    big, small = F["display"], F["display_sc"]
    spaced(surf, F["hub_label"], tagline, (rect.x + 2, rect.y), T.BRASS, spacing=3)
    y = rect.y + F["hub_label"].get_height() + T.S
    r = small_caps(surf, big, small, title, (rect.x - 2, y), T.TX)
    y = r.bottom - T.S
    sub = spaced(surf, F["hub_head"], subtitle, (rect.x + 2, y), T.TX_MUTED, spacing=10)
    y = sub.bottom + T.S * 3
    pygame.draw.line(surf, T.BRASS_DIM, (rect.x, y), (rect.right, y), 2)
    y += T.S * 2
    for line in wrap(F["hub_quote"], quote, rect.w):
        text(surf, F["hub_quote"], line, (rect.x, y), T.TX_MUTED)
        y += F["hub_quote"].get_height() + 2
    return y


def draw_menu(surf, F, rect, items, mpos, row_h=ROW_H):
    hits = []
    y = rect.y
    for item in items:
        if item is None:
            y += GROUP_GAP
            continue
        r = pygame.Rect(rect.x, y, rect.w, row_h)
        on = item["enabled"]
        hot = on and r.collidepoint(mpos)
        if item.get("primary") and on:
            pygame.draw.rect(surf, mix(T.BRASS, T.TX, 0.15) if hot else T.BRASS, r, border_radius=6)
            spaced(surf, F["hub_bodyb"], item["label"], (r.x + T.S * 3, r.centery), T.TABLE, anchor="midleft")
            if item.get("hint"):
                text(surf, F["hub_sub"], ellipsize(item["hint"], F["hub_sub"], r.w // 2),
                     (r.right - T.S * 3, r.centery - F["hub_sub"].get_height() // 2), T.STEEL, right=True)
        else:
            if hot:
                pygame.draw.rect(surf, mix(T.TABLE, T.BRASS, 0.08), r, border_radius=6)
                pygame.draw.rect(surf, T.BRASS, (r.x, r.y + T.S, 3, r.h - T.S * 2))
            color = (T.BRASS if hot else T.TX) if on else T.TX_FAINT
            spaced(surf, F["hub_bodyb"], item["label"], (r.x + T.S * 3, r.centery), color, anchor="midleft")
            if item.get("hint"):
                text(surf, F["hub_sub"], ellipsize(item["hint"], F["hub_sub"], r.w // 2),
                     (r.right - T.S * 2, r.centery - F["hub_sub"].get_height() // 2), T.TX_FAINT, right=True)
        hits.append((item["key"], r, on))
        y += row_h + 2
    return hits


def _faces_height(F, w, n, px, named):
    gap = T.S * 2
    per_row = max(1, (w + gap) // (px + gap))
    rows = (n + per_row - 1) // per_row
    label_h = F["hub_sub"].get_height() + T.S if named else 0
    return rows * (px + label_h + gap) - gap


def _faces(surf, F, x, y, w, faces, px, named):
    gap = T.S * 2
    per_row = max(1, (w + gap) // (px + gap))
    label_h = F["hub_sub"].get_height() + T.S if named else 0
    for i, face in enumerate(faces):
        cx = x + (i % per_row) * (px + gap) + px // 2
        cy = y + (i // per_row) * (px + label_h + gap) + px // 2
        medallion(surf, (cx, cy), face["race"], face["portrait"], px)
        if named:
            name = ellipsize(face["name"], F["hub_sub"], px + gap - 2)
            img = F["hub_sub"].render(name, True, T.TX_MUTED)
            surf.blit(img, img.get_rect(midtop=(cx, cy + px // 2 + T.S // 2)))


def _frame(surf, rect, hot):
    pygame.draw.rect(surf, mix(T.STEEL, T.BRASS, 0.05) if hot else T.STEEL, rect, border_radius=8)
    pygame.draw.rect(surf, T.BRASS if hot else T.STEEL_LINE, rect, 1, border_radius=8)


def draw_campaign(surf, F, rect, card, mpos):
    """Sized to its content: `rect` is the room it may take, the returned rect what it took."""
    pad = T.S * 4
    w = rect.w - 2 * pad
    shield_h = T.S * 20
    head_h = F["hub_label"].get_height() + T.S * 3
    roster_h = (T.S * 7 + F["hub_label"].get_height() + _faces_height(F, w, len(card["faces"]), FACE, True)
                if card["faces"] else 0)
    rect = pygame.Rect(rect.x, rect.y, rect.w, min(rect.h, 2 * pad + head_h + shield_h + roster_h))
    hot = rect.collidepoint(mpos)
    _frame(surf, rect, hot)
    with contained(surf, rect):
        x, y = rect.x + pad, rect.y + pad
        spaced(surf, F["hub_label"], "Last campaign", (x, y), T.BRASS, spacing=3)
        if card["saved"]:
            text(surf, F["hub_sub"], f"saved {card['saved']}", (rect.right - pad, y), T.TX_FAINT, right=True)
        y += head_h

        shield_w = int(shield_h * 0.82)
        draw_shield(surf, x + shield_w // 2, y, shield_h, card["color"], card["icon"])
        tx, tw = x + shield_w + T.S * 5, w - shield_w - T.S * 5
        ty = y + T.S
        name = ellipsize(card["name"], F["hub_title"], tw)
        r = small_caps(surf, F["hub_title"], F["hub_title_sc"], name, (tx, ty), T.TX)
        ty = r.bottom + T.S
        if card.get("vocation"):
            spaced(surf, F["hub_label"], f"{card['vocation']} guild", (tx, ty), T.TX_MUTED, spacing=2)
            ty += F["hub_label"].get_height() + T.S * 2
        for label, value in (("Day", card["day"]), ("Members", card["members"]), ("Wins", card["wins"])):
            spaced(surf, F["hub_label"], label, (tx, ty + 6), T.TX_FAINT)
            text(surf, F["hub_value"], str(value), (tx + T.S * 14, ty), T.TX)
            ty += F["hub_value"].get_height() + 2
        y += shield_h

        if card["faces"]:
            y += T.S * 3
            pygame.draw.line(surf, T.STEEL_LINE, (x, y), (x + w, y))
            y += T.S * 2
            spaced(surf, F["hub_label"], "The roster", (x, y), T.TX_FAINT, spacing=3)
            y += F["hub_label"].get_height() + T.S * 2
            _faces(surf, F, x, y, w, card["faces"], FACE, named=True)
    if hot:
        spaced(surf, F["hub_label"], "click to continue", (rect.centerx, rect.bottom + T.S * 2), T.BRASS,
               spacing=3, anchor="midtop")
    return rect


INVITE_TEXT = ("Pick the trade it is founded on, name it, raise its banner, then draft three of nine "
               "strangers. Most of them will not last; the guild will.")


def draw_invite(surf, F, rect, faces):
    pad = T.S * 4
    x, w = rect.x + pad, rect.w - 2 * pad
    px = max(T.S * 6, min(T.S * 9, (w - T.S * 2 * (len(faces) - 1)) // max(1, len(faces))))
    lines = wrap(F["hub_body"], INVITE_TEXT, w)
    h = (2 * pad + F["hub_label"].get_height() + T.S * 3 + F["hub_title"].get_height() + T.S * 2
         + len(lines) * (F["hub_body"].get_height() + 4) + T.S * 3 + _faces_height(F, w, len(faces), px, False))
    rect = pygame.Rect(rect.x, rect.y, rect.w, min(rect.h, h))
    _frame(surf, rect, False)
    with contained(surf, rect):
        y = rect.y + pad
        spaced(surf, F["hub_label"], "No guild yet", (x, y), T.BRASS, spacing=3)
        y += F["hub_label"].get_height() + T.S * 3
        r = small_caps(surf, F["hub_title"], F["hub_title_sc"], "Found a guild", (x, y), T.TX)
        y = r.bottom + T.S * 2
        for line in lines:
            text(surf, F["hub_body"], line, (x, y), T.TX_MUTED)
            y += F["hub_body"].get_height() + 4
        y += T.S * 3
        _faces(surf, F, x, y, w, faces, px, named=False)

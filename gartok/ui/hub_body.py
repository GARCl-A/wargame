"""The pieces a hub tab's body is built from, in the shop's type (the `hub_*` fonts): what the
shop's FOR SALE and PARTY panels look like, for the tabs that are not a shop.

    draw_panel(surf, F, rect, title, aside=None, hot=False) -> the inner rect under the head rule
                                                              (`aside` follows the title, muted)
    draw_person(surf, F, rect, p, mpos)                    -> [(rect, label)] of its chips
    draw_offer(surf, F, rect, o, mpos)                     -> [(rect, key)] of its enabled buttons
    draw_items(surf, F, pos, names, color, max_x)          -> the x where the line ends
    draw_chip(surf, F, pos, label, tone, anchor)           -> rect
    draw_toggle(surf, F, rect, label, on, mpos)            -> None: a pill that is picked or not
    draw_bar(surf, rect, frac, tone)                       -> None: a thin progress bar
    draw_facts(surf, F, pos, w, rows)                      -> the y under the last row
    draw_section(surf, F, pos, label)                      -> rect: a tracked caps label

A person `p` is {"face": {"race", "portrait_id", "token"}, "name", "sub", "note" (optional second
line), "chips": [(label, tone)], "status": (text, tone) | None, "state": None | "on" | "good"
| "hot", "reserve": px kept free at the right for the caller's buttons}. An offer `o` is
{"icon": icon, "name", "sub", "note": (text, tone) | None, "price": str | None, "price_tone",
"buttons": [(key, label, primary, enabled)], "dim": bool}; an icon is {"item": name}, {"face":
face} or {"glyph": kind, "tone": material, **shape} (`item_icons.KINDS`). A fact row is
(label, value, tone). A tone is "money" | "good" | "bad" | "muted" | "faint" | None (plain ink).
"""

import pygame

from ..item_icon import draw_icon
from .board_render import draw_face
from .hub_frame import button_width, hub_button
from .item_icons import TONES, draw_item_icon
from .primitives import ellipsize, small_caps, spaced, spaced_width, text, wrap
from .tokens import T, mix

TONE = {"money": T.BRASS, "good": T.GREEN, "bad": T.BLOOD, "muted": T.TX_MUTED, "faint": T.TX_FAINT,
        None: T.TX}
PAD = T.S * 3
HEAD_H = T.S * 8
PERSON_H = T.S * 9 + 2           # a person row with a name and one line under it
PERSON_TALL_H = T.S * 14         # with a note and chips too
OFFER_H = T.S * 9 + 2            # the shop shelf's row


def draw_panel(surf, F, rect, title, aside=None, hot=False):
    pygame.draw.rect(surf, T.STEEL, rect, border_radius=8)
    pygame.draw.rect(surf, T.BRASS if hot else T.STEEL_LINE, rect, 2 if hot else 1, border_radius=8)
    t = small_caps(surf, F["hub_head"], F["hub_head_sc"], title, (rect.x + PAD, rect.y + T.S * 3), T.TX)
    if aside:
        x = t.right + T.S * 2
        text(surf, F["hub_body"], ellipsize(aside, F["hub_body"], rect.right - PAD - x),
             (x, t.bottom - F["hub_body"].get_height() - 1), T.TX_MUTED)
    head = rect.y + HEAD_H
    pygame.draw.line(surf, T.STEEL_LINE, (rect.x, head), (rect.right - 1, head))
    return pygame.Rect(rect.x + PAD, head + T.S * 2, rect.w - 2 * PAD, rect.bottom - head - T.S * 4)


def draw_section(surf, F, pos, label):
    return spaced(surf, F["hub_label"], label, pos, T.TX_MUTED)


def draw_chip(surf, F, pos, label, tone=None, anchor="topleft"):
    font = F["hub_subb"]
    r = pygame.Rect(0, 0, font.size(label)[0] + T.S * 2, T.S * 3)
    setattr(r, anchor, pos)
    color = TONE[tone]
    pygame.draw.rect(surf, mix(T.STEEL, color, 0.12), r, border_radius=r.h // 2)
    pygame.draw.rect(surf, color, r, 1, border_radius=r.h // 2)
    text(surf, font, label, r.center, color, center=True)
    return r


def draw_toggle(surf, F, rect, label, on, mpos):
    hot = not on and rect.collidepoint(mpos)
    pygame.draw.rect(surf, mix(T.STEEL, T.BRASS, 0.15) if on else T.STEEL, rect, border_radius=rect.h // 2)
    pygame.draw.rect(surf, T.BRASS if on else (T.TX_MUTED if hot else T.STEEL_LINE), rect, 1,
                     border_radius=rect.h // 2)
    text(surf, F["hub_bodyb" if on else "hub_body"], label, rect.center, T.TX if on else T.TX_MUTED,
         center=True)


def draw_bar(surf, rect, frac, tone="money"):
    pygame.draw.rect(surf, T.TABLE, rect, border_radius=rect.h // 2)
    fill = round(rect.w * max(0.0, min(1.0, frac)))
    if fill:
        pygame.draw.rect(surf, TONE[tone], pygame.Rect(rect.x, rect.y, fill, rect.h), border_radius=rect.h // 2)


def draw_facts(surf, F, pos, w, rows):
    """`rows` as a two-column table: the label tracked and muted, the value wrapped beside it."""
    x, y = pos
    label_w = max((spaced_width(F["hub_label"], label) for label, _v, _t in rows), default=0) + T.S * 3
    lh = F["hub_body"].get_linesize()
    for label, value, tone in rows:
        spaced(surf, F["hub_label"], label, (x, y + 3), T.TX_MUTED)
        for line in wrap(F["hub_body"], value, max(T.S * 10, w - label_w)) or [""]:
            text(surf, F["hub_body"], line, (x + label_w, y), TONE[tone])
            y += lh
        y += T.S
    return y


def draw_person(surf, F, rect, p, mpos):
    state = p.get("state")
    edge = {"on": T.BRASS, "good": T.GREEN}.get(state)
    if edge:
        pygame.draw.rect(surf, mix(T.STEEL, edge, 0.08), rect, border_radius=6)
        pygame.draw.rect(surf, mix(edge, T.STEEL, 0.3), rect, 1, border_radius=6)
    elif state == "hot" or rect.collidepoint(mpos):
        pygame.draw.rect(surf, T.STEEL_HI, rect, border_radius=6)
    else:
        pygame.draw.rect(surf, mix(T.STEEL, T.TABLE, 0.35), rect, border_radius=6)

    r = min(T.S * 3, rect.h // 2 - T.S)
    face_c = (rect.x + T.S * 2 + r, rect.y + T.S + 4 + r if p.get("note") or p.get("chips") else rect.centery)
    draw_face(surf, F, face_c, r, p["face"], fallback_color=T.STEEL_HI)

    x = face_c[0] + r + T.S * 2
    right = rect.right - T.S * 2 - p.get("reserve", 0)
    status = p.get("status")
    if status:
        s = text(surf, F["hub_bodyb"], status[0], (right, rect.y + T.S + 6), TONE[status[1]], right=True)
        right_name = s.x - T.S * 2
    else:
        right_name = right
    y = rect.y + T.S + 2
    small_caps(surf, F["hub_card"], F["hub_card_sc"], ellipsize(p["name"], F["hub_card"], right_name - x),
               (x, y), T.TX)
    y += T.S * 3 + 4
    if p.get("sub"):
        text(surf, F["hub_sub"], ellipsize(p["sub"], F["hub_sub"], right - x), (x, y), T.TX_MUTED)
        y += T.S * 2 + 4
    if p.get("note"):
        text(surf, F["hub_body"], ellipsize(p["note"], F["hub_body"], right - x), (x, y), T.TX)
        y += T.S * 3
    hits = []
    cx = x
    for label, tone in p.get("chips", []):
        c = draw_chip(surf, F, (cx, y + 2), label, tone)
        hits.append((c, label))
        cx = c.right + T.S
    return hits


def _icon(surf, F, rect, icon):
    if "face" in icon:
        draw_face(surf, F, rect.center, rect.w // 2, icon["face"], fallback_color=T.STEEL_HI)
    elif "item" in icon:
        draw_icon(surf, rect, icon["item"])
    else:
        shape = {k: v for k, v in icon.items() if k not in ("glyph", "tone")}
        draw_item_icon(surf, rect, icon["glyph"], TONES[icon.get("tone", "wood")], **shape)


def draw_offer(surf, F, rect, o, mpos):
    hits = []
    pygame.draw.rect(surf, T.STEEL_HI if rect.collidepoint(mpos) and not o.get("dim") else
                     mix(T.STEEL, T.TABLE, 0.35), rect, border_radius=6)
    icon = pygame.Rect(rect.x + T.S + 4, rect.y + (rect.h - T.S * 6) // 2, T.S * 6, T.S * 6)
    _icon(surf, F, icon, o["icon"])
    bx = rect.right - T.S * 2
    bh = T.S * 5
    for key, label, primary, enabled in reversed(o.get("buttons", [])):
        b = pygame.Rect(0, rect.y + (rect.h - bh) // 2, button_width(F, label) - T.S * 2, bh)
        b.right = bx
        hub_button(surf, F, b, label, primary=primary, enabled=enabled, mpos=mpos)
        if enabled:
            hits.append((b, key))
        bx = b.x - T.S
    if o.get("price"):
        p = text(surf, F["hub_price"], o["price"], (bx - T.S, rect.y + T.S + 2), TONE[o.get("price_tone", "money")],
                 right=True)
        bx = p.x - T.S
    x = icon.right + T.S * 2
    ink = T.TX_FAINT if o.get("dim") else T.TX
    text(surf, F["hub_row"], ellipsize(o["name"], F["hub_row"], bx - T.S - x), (x, rect.y + T.S + 4), ink)
    sub = text(surf, F["hub_sub"], ellipsize(o.get("sub", ""), F["hub_sub"], bx - T.S - x), (x, rect.y + T.S * 5),
               T.TX_MUTED)
    if o.get("note"):
        note, tone = o["note"]
        text(surf, F["hub_subb"], ellipsize(note, F["hub_subb"], bx - T.S * 2 - sub.right),
             (sub.right + T.S if o.get("sub") else x, sub.y), TONE[tone])
    return hits


def draw_items(surf, F, pos, names, color=T.TX, max_x=None):
    """`names` on one line, equal names counted ("2 × Iron Bar"), each behind its small icon;
    what does not fit before `max_x` becomes "...". """
    counts = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    font, size = F["hub_body"], T.S * 3
    x, y = pos
    items = list(counts.items())
    for i, (name, qty) in enumerate(items):
        label = (f"{qty} × " if qty > 1 else "") + name + (",  " if i < len(items) - 1 else "")
        w = size + T.S + font.size(label)[0]
        if max_x is not None and x + w > max_x:
            return text(surf, font, "...", (x, y), color).right
        draw_icon(surf, pygame.Rect(x, y + (font.get_height() - size) // 2, size, size), name)
        x = text(surf, font, label, (x + size + T.S, y), color).right
    return x

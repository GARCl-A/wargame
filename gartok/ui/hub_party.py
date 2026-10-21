"""A party member as a card on a hub screen (the shop's PARTY columns).

    member_card(surf, F, rect, member, scroll, mouse) -> hit dict

Same contract as `loadout_panel.column`: `member` is the dict `market_screen._member_dict` /
`store_column.store_dict` build (name, kg, cap, the slots as {"name", "note", "accepts", "sel"} or
None for a blocked off-hand, `pack: [(name, tag, weight, qty, locked, sel)]`, optional `status`,
`action`, `no_sheet`, `pending_picks`), and the result carries the same keys: sheet_rect,
head_rect, slot_rects, pack_zone, pack_area, pack_hits, lock_hits, dots_hits, scroll, action_rect.
Drawn at the hub size: name in serif small caps, the slots two by two, a dashed drop area under
the pack.
"""

import pygame

from .. import icons
from ..item_icon import draw_icon
from .hub_frame import hub_button
from .primitives import (
    dashed_rect,
    ellipsize,
    scrollbar,
    small_caps,
    spaced,
    text,
    wrap,
)
from .tokens import T, mix

SLOT_LABELS = {"hand": "main hand", "offhand": "off hand", "tongue": "tongue", "artifact": "artifact",
               "armor": "armor", "tack": "tack"}
SLOT_ORDER = ("hand", "offhand", "armor", "artifact", "tongue", "tack")
SLOT_H = T.S * 8 - 2
ROW_H = T.S * 7 - 4


def _load(surf, F, x, y, w, kg, cap):
    frac = kg / cap if cap else 0
    color = T.BLOOD if frac > 1 else T.BRASS if frac >= 0.75 else T.GREEN
    text(surf, F["hub_sub"], "Load", (x, y), T.TX_MUTED)
    note = "  ·  over" if frac > 1 else "  ·  near limit" if frac >= 0.75 else ""
    text(surf, F["hub_subb"], f"{kg:.1f} / {cap:.0f} kg{note}", (x + w, y), color if note else T.TX, right=True)
    bar = pygame.Rect(x, y + T.S * 3 - 2, w, 7)
    pygame.draw.rect(surf, T.TABLE, bar, border_radius=3)
    pygame.draw.rect(surf, color, pygame.Rect(bar.x, bar.y, int(bar.w * min(1.0, frac)), bar.h), border_radius=3)


def _slot(surf, F, r, kind, held, mouse):
    if held is None:
        pygame.draw.rect(surf, T.STEEL, r, border_radius=4)
        pygame.draw.rect(surf, T.STEEL_LINE, r, 1, border_radius=4)
        spaced(surf, F["hub_label"], SLOT_LABELS[kind], (r.x + T.S + 4, r.y + T.S + 2), T.TX_FAINT, spacing=1)
        text(surf, F["hub_sub"], "2-handed weapon", (r.x + T.S + 4, r.y + T.S * 4), T.TX_FAINT)
        return
    name, sel = held["name"], held["sel"]
    drop = held["accepts"] and not sel and r.collidepoint(mouse)
    fill = mix(T.STEEL, T.BRASS, 0.12) if sel else T.STEEL_HI if drop else mix(T.STEEL, T.TABLE, 0.2)
    pygame.draw.rect(surf, fill, r, border_radius=4)
    pygame.draw.rect(surf, T.BRASS if (sel or drop) else T.STEEL_LINE, r, 1, border_radius=4)
    x = r.x + T.S
    room_with_icon = r.right - (x + T.S * 5) - T.S
    if name and F["hub_body"].size(name)[0] <= room_with_icon:
        icon = pygame.Rect(x, r.centery - T.S * 2, T.S * 4, T.S * 4)
        pygame.draw.rect(surf, mix(T.STEEL, T.TABLE, 0.5), icon, border_radius=4)
        draw_icon(surf, icon.inflate(-4, -4), name)
        x = icon.right + T.S
    label = spaced(surf, F["hub_label"], SLOT_LABELS[kind], (x, r.y + T.S), T.TX_MUTED, spacing=1)
    room = r.right - x - T.S
    note = held.get("note")
    font = F["hub_bodyb"] if name and F["hub_bodyb"].size(name)[0] <= room else F["hub_body"]
    if not name or font.size(name)[0] <= room:
        text(surf, font, ellipsize(name or "—", font, room), (x, r.y + T.S * 3 - 2), T.TX if name else T.TX_FAINT)
        if note:
            text(surf, F["hub_sub"], ellipsize(note, F["hub_sub"], room), (x, r.y + T.S * 5 + 2), T.TX_MUTED)
        return
    # a long name takes two lines; the note moves up beside the label
    for i, line in enumerate(wrap(font, name, room)[:2]):
        text(surf, font, ellipsize(line, font, room), (x, r.y + T.S * 3 - 2 + i * (T.S * 2 + 2)), T.TX)
    if note:
        text(surf, F["hub_sub"], ellipsize(note, F["hub_sub"], r.right - T.S - label.right - T.S),
             (r.right - T.S, label.y - 1), T.TX_MUTED, right=True)


def _pack_row(surf, F, r, item, mouse):
    name, tag, weight, qty, locked, sel = item
    fill = mix(T.STEEL, T.BRASS, 0.1) if sel else mix(T.STEEL, T.TABLE, 0.2)
    pygame.draw.rect(surf, fill, r, border_radius=4)
    pygame.draw.rect(surf, T.BRASS if sel else T.STEEL_LINE, r, 2 if sel else 1, border_radius=4)
    lock = pygame.Rect(r.x + T.S, r.centery - 9, 18, 18)
    icons.icon(surf, "lock" if locked else "unlock", lock, T.BRASS if locked else T.TX_FAINT)
    disc = (lock.right + T.S * 2 + 4, r.centery)
    pygame.draw.circle(surf, mix(T.STEEL, T.TABLE, 0.6), disc, 17)
    draw_icon(surf, pygame.Rect(disc[0] - 14, disc[1] - 14, 28, 28), name)
    dots = pygame.Rect(r.right - T.S * 3 - 4, r.centery - 11, 22, 22)
    if dots.collidepoint(mouse):
        pygame.draw.rect(surf, T.STEEL_HI, dots, border_radius=4)
    text(surf, F["hub_bodyb"], "⋮", dots.center, T.TX_MUTED, center=True)
    kg = text(surf, F["hub_sub"], f"{weight * qty:.1f} kg", (dots.x - T.S, r.centery - 8),
              T.BLOOD if weight * qty >= 10 else T.TX_MUTED, right=True)
    x = disc[0] + T.S * 3
    room = kg.x - T.S - x
    label = name if qty == 1 else f"{name}  ×{qty}"
    text(surf, F["hub_body"], ellipsize(label, F["hub_body"], room), (x, r.y + T.S - 1),
         T.TX_FAINT if locked else T.TX)
    tag_color = T.BRASS if "AUTO-SELL" in (tag or "") else T.TX_MUTED
    text(surf, F["hub_sub"], ellipsize((tag or "").title(), F["hub_sub"], room), (x, r.y + T.S * 3 + 4), tag_color)
    return lock, dots


def member_card(surf, F, rect, member, scroll, mouse):
    pygame.draw.rect(surf, T.STEEL, rect, border_radius=8)
    pygame.draw.rect(surf, T.STEEL_LINE, rect, 1, border_radius=8)
    pad = T.S * 2 + 4
    x, w = rect.x + pad, rect.w - 2 * pad
    head = pygame.Rect(rect.x, rect.y, rect.w, T.S * 13 + 4)

    sheet_rect = pygame.Rect(rect.right - pad - 30, rect.y + T.S * 2 + 2, 30, 30)
    edge = sheet_rect.x - T.S
    if not member.get("no_sheet"):
        hot = sheet_rect.collidepoint(mouse)
        pygame.draw.circle(surf, T.TX_MUTED if hot else T.STEEL_LINE, sheet_rect.center, 15, 1)
        text(surf, F["hub_sub"], "?", sheet_rect.center, T.TX if hot else T.TX_MUTED, center=True)
    if member.get("pending_picks"):
        edge = spaced(surf, F["hub_label"], "● level up", (edge, sheet_rect.centery), T.BRASS,
                      spacing=1, anchor="midright").x - T.S
    clip = surf.get_clip()
    surf.set_clip(pygame.Rect(x, rect.y, edge - x, head.h).clip(clip))
    small_caps(surf, F["hub_card"], F["hub_card_sc"], member["name"], (x, rect.y + T.S * 2 + 4), T.TX)
    surf.set_clip(clip)
    _load(surf, F, x, rect.y + T.S * 7 + 2, w, member["kg"], member["cap"])
    pygame.draw.line(surf, T.STEEL_LINE, (rect.x, head.bottom), (rect.right - 1, head.bottom))

    y = head.bottom + T.S * 2
    status = member.get("status")
    if status:
        text(surf, F["hub_subb"], ellipsize(status["text"], F["hub_subb"], w), (x, y),
             T.BLOOD if status.get("danger") else T.TX_MUTED)
        y += T.S * 3
    action_rect = None
    if member.get("action"):
        act = member["action"]
        action_rect = pygame.Rect(x, y, w, T.S * 5)
        hub_button(surf, F, action_rect, act["label"], enabled=act.get("enabled", True), mpos=mouse)
        y = action_rect.bottom + T.S * 2

    slot_rects = {}
    kinds = [k for k in SLOT_ORDER if member.get(k, "skip") != "skip"]
    sw = (w - T.S - 2) // 2
    for i, kind in enumerate(kinds):
        r = pygame.Rect(x + (i % 2) * (sw + T.S + 2), y + (i // 2) * (SLOT_H + T.S), sw, SLOT_H)
        _slot(surf, F, r, kind, member[kind], mouse)
        slot_rects[kind] = r if member[kind] is not None else None
    if kinds:
        y += ((len(kinds) + 1) // 2) * (SLOT_H + T.S) + T.S * 2

    items = member["pack"]
    kg = sum(wt * q for _, _, wt, q, *_ in items)
    spaced(surf, F["hub_label"], "pack", (x, y), T.TX_MUTED)
    spaced(surf, F["hub_label"], f"{len(items)} stack{'' if len(items) == 1 else 's'} · {kg:.1f} kg",
           (x + w, y), T.TX_MUTED, spacing=1, anchor="topright")
    y += T.S * 3 + 2
    list_rect = pygame.Rect(x, y, w, rect.bottom - pad - y)
    pack_hits, lock_hits, dots_hits = [], [], []
    fit = max(1, list_rect.h // (ROW_H + T.S))
    max_scroll = max(0, len(items) - fit)
    scroll = max(0, min(scroll, max_scroll))
    iy = list_rect.y
    surf.set_clip(list_rect.clip(clip))
    for idx in range(scroll, min(len(items), scroll + fit)):
        r = pygame.Rect(x, iy, w - (T.S if max_scroll else 0), ROW_H)
        lock, dots = _pack_row(surf, F, r, items[idx], mouse)
        pack_hits.append((r, idx))
        lock_hits.append((lock, idx))
        dots_hits.append((dots, idx))
        iy = r.bottom + T.S
    surf.set_clip(clip)
    if max_scroll:
        scrollbar(surf, list_rect, scroll, max_scroll, len(items) * (ROW_H + T.S))
    drop = pygame.Rect(x, iy, w, list_rect.bottom - iy)
    if drop.h >= T.S * 6:
        dashed_rect(surf, drop, T.STEEL_LINE)
        text(surf, F["hub_sub"], "Drop items here" if items else "Carrying nothing  ·  drop items here",
             drop.center, T.TX_FAINT, center=True)
    return {"sheet_rect": sheet_rect, "head_rect": head, "slot_rects": slot_rects, "pack_zone": rect,
            "pack_area": list_rect, "pack_hits": pack_hits, "lock_hits": lock_hits, "dots_hits": dots_hits,
            "scroll": scroll, "action_rect": action_rect}

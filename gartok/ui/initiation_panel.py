"""A sanctuary's initiation: what the school asks, one row per member with where they stand,
and the footer that starts (or resumes) the rite for the one picked.

`terms` is a list of `(label, value, ok)` lines (`ok` False paints the value red). `rows` is a
list of dicts: `{key, name, status, note, enabled, picked}` (`note` replaces `status` on a row
that cannot start). `action` is the button's label for the picked row, or None when nothing
can start. Returns `(row_rects, begin_rect, leave_rect)`; `row_rects` is `[(key, rect)]`.
"""

import pygame

from .primitives import box, caps, draw_button, ellipsize, hline, text
from .tokens import T, mix

ROW_H = T.S * 8
TERM_H = 22


def draw_initiation(surf, F, rect, terms, rows, action, leave_label, mpos):
    y = rect.y
    label_w = min(rect.w // 3, T.S * 26)
    for label, value, ok in terms:
        caps(surf, F["micro"], label, (rect.x, y + 3), T.TX_FAINT)
        text(surf, F["body_sm"], ellipsize(value, F["body_sm"], rect.w - label_w), (rect.x + label_w, y),
             T.TX if ok else T.BLOOD)
        y += TERM_H
    y += T.S
    hline(surf, rect.x, rect.right, y)
    y += T.S * 2

    row_rects = []
    footer_h = T.S * 6
    list_bottom = rect.bottom - footer_h
    for r in rows:
        rr = pygame.Rect(rect.x, y, rect.w, ROW_H - T.S)
        if rr.bottom > list_bottom:
            break
        hover = r["enabled"] and rr.collidepoint(mpos)
        fill = mix(T.BRASS, T.STEEL, 0.85) if r["picked"] else (T.STEEL_HI if hover else T.STEEL)
        box(surf, rr, fill, T.BRASS if r["picked"] else T.STEEL_LINE)
        pad = T.S * 2
        caps(surf, F["head"], r["name"], (rr.x + pad, rr.y + T.S), T.TX if r["enabled"] else T.TX_FAINT)
        detail = r["status"] if r["enabled"] else r["note"]
        text(surf, F["body_sm"], ellipsize(detail, F["body_sm"], rr.w - 2 * pad),
             (rr.x + pad, rr.y + T.S * 4), T.TX_MUTED if r["enabled"] else T.BLOOD)
        row_rects.append((r["key"], rr))
        y += ROW_H

    hline(surf, rect.x, rect.right, list_bottom)
    fy = list_bottom + T.S * 2
    btn_w = min(T.S * 26, rect.w // 2 - T.S * 2)
    begin = pygame.Rect(rect.right - btn_w, fy, btn_w, T.S * 4)
    draw_button(surf, F, begin, action or "PICK WHO STAYS", primary=bool(action), enabled=bool(action), mpos=mpos)
    if leave_label is None:                       # a hub's frame has its own back
        return row_rects, begin, pygame.Rect(0, 0, 0, 0)
    leave = pygame.Rect(begin.x - T.S * 3 - btn_w, fy, btn_w, T.S * 4)
    draw_button(surf, F, leave, leave_label, mpos=mpos)
    return row_rects, begin, leave

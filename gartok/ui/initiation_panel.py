"""A sanctuary's initiation in the hub kit's type: what the school asks, one row per member with
where they stand, and the footer that starts (or resumes) the rite for the one picked.

`terms` is a list of `(label, value, ok)` lines (`ok` False paints the value red). `rows` is a
list of dicts: `{key, face, name, sub, status, note, enabled, picked}` (`note` replaces `status`
on a row that cannot start; `face` as `hub_body.draw_person` takes it). `action` is the button's
label for the picked row, or None when nothing can start. Returns `(row_rects, begin_rect,
leave_rect)`; `row_rects` is `[(key, rect)]`.
"""

import pygame

from . import hub_body as hb
from .hub_frame import button_width, hub_button
from .tokens import T

FOOT_H = T.S * 11


def draw_initiation(surf, F, rect, terms, rows, action, leave_label, mpos):
    left_w = max(T.S * 56, min(T.S * 80, round(rect.w * 0.45)))
    terms_r = pygame.Rect(rect.x, rect.y, left_w, rect.h)
    inner = hb.draw_panel(surf, F, terms_r, "The Terms", "what the school asks")
    hb.draw_facts(surf, F, (inner.x, inner.y), inner.w,
                  [(label, value, None if ok else "bad") for label, value, ok in terms])

    who = pygame.Rect(terms_r.right + T.S * 3, rect.y, rect.right - terms_r.right - T.S * 3, rect.h)
    inner = hb.draw_panel(surf, F, who, "Who Stays", "one member boards here until the school takes them in")
    foot_y = who.bottom - FOOT_H
    row_rects = []
    y = inner.y
    row_h = hb.PERSON_H + T.S * 3
    for r in rows:
        rr = pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, row_h)
        if rr.bottom > foot_y - T.S:
            break
        hb.draw_person(surf, F, rr, {
            "face": r["face"], "name": r["name"], "sub": r.get("sub", ""),
            "note": r["status"] if r["enabled"] else (r["note"], "bad"),
            "state": "on" if r["picked"] else None}, mpos if r["enabled"] else (-1, -1))
        row_rects.append((r["key"], rr))
        y += row_h + T.S

    pygame.draw.line(surf, T.STEEL_LINE, (who.x, foot_y), (who.right - 1, foot_y))
    by = foot_y + T.S * 3
    left = who.x + hb.PAD
    leave = pygame.Rect(0, 0, 0, 0)
    if leave_label is not None:                   # a hub's frame has its own back
        leave = pygame.Rect(left, by, button_width(F, leave_label), T.S * 6 + 4)
        hub_button(surf, F, leave, leave_label, mpos=mpos)
        left = leave.right + T.S * 2
    begin = pygame.Rect(left, by, who.right - hb.PAD - left, T.S * 6 + 4)
    hub_button(surf, F, begin, action or "Pick who stays", primary=True, enabled=bool(action), mpos=mpos)
    return row_rects, begin, leave

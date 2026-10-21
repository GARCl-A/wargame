"""The Medic's ward: one row per patient with what ails them and the price, and the
footer that totals the picked ones, in the hub kit's type.

`rows` is a list of dicts: `{key, face, name, sub, lines: [str], cost, hours, picked}` (`lines`
the ailments, `face` as `hub_body.draw_person` takes it). `stay` is the hospital stay picked, if
any: its footer line and button replace the quick treatment's. Returns
`(row_rects, treat_rect, leave_rect)`; `row_rects` is `[(key, rect)]`. `leave_label=None` draws no
leave button (a hub's frame has its own back) and returns an empty `leave_rect`.
"""

import pygame

from . import hub_body as hb
from .hub_frame import button_width, hub_button
from .primitives import text
from .tokens import T

FOOT_H = T.S * 15


def draw_medic(surf, F, rect, rows, total_cost, total_hours, can_pay, mpos, stay=None,
               leave_label="LEAVE THE MEDIC", aside=None):
    inner = hb.draw_panel(surf, F, rect, "The Ward", aside)
    foot_y = rect.bottom - FOOT_H
    row_rects = []
    y = inner.y
    if not rows:
        text(surf, F["hub_body"], "Nobody here needs treating.", (inner.x, y), T.TX_MUTED)
    row_h = hb.PERSON_H + T.S * 3
    for r in rows:
        rr = pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, row_h)
        if rr.bottom > foot_y - T.S:
            break
        hb.draw_person(surf, F, rr, {
            "face": r["face"], "name": r["name"], "sub": r.get("sub", ""),
            "chips": [(line, "bad" if line == "hospital stay" else "muted") for line in r["lines"]],
            "status": (f"${r['cost']}  ·  {r['hours']} h", "money"),
            "state": "on" if r["picked"] else None}, mpos)
        row_rects.append((r["key"], rr))
        y += row_h + T.S

    pygame.draw.line(surf, T.STEEL_LINE, (rect.x, foot_y), (rect.right - 1, foot_y))
    pad = hb.PAD
    ty = foot_y + T.S * 3 - F["hub_body"].get_height() // 2
    if total_cost:
        v = text(surf, F["hub_bodyb"], f"${total_cost}  ·  {total_hours} h", (rect.right - pad, ty),
                 T.TX if can_pay else T.BLOOD, right=True)
        text(surf, F["hub_body"], "Total ", (v.x, ty), T.TX_MUTED, right=True)
    who = stay or "the whole group waits while they are treated"
    text(surf, F["hub_body"], who if total_cost else "Pick who to treat", (rect.x + pad, ty), T.TX_MUTED)

    by = foot_y + T.S * 6
    leave = pygame.Rect(0, 0, 0, 0)
    left = rect.x + pad
    if leave_label is not None:
        leave = pygame.Rect(left, by, button_width(F, leave_label), T.S * 6 + 4)
        hub_button(surf, F, leave, leave_label, mpos=mpos)
        left = leave.right + T.S * 2
    treat = pygame.Rect(left, by, rect.right - pad - left, T.S * 6 + 4)
    label = ("Admit" if stay else "Treat") if can_pay or not total_cost else "Cannot pay"
    hub_button(surf, F, treat, label, primary=True, enabled=bool(total_cost and can_pay), mpos=mpos)
    return row_rects, treat, leave

"""The Medic's ward: one row per patient with what ails them and the price, and the
footer that totals the picked ones.

`rows` is a list of dicts: `{key, name, lines: [str], cost, hours, picked, enabled,
note}` (`lines` the ailments, `note` why a row cannot be picked). Returns
`(row_rects, treat_rect)`; `row_rects` is `[(key, rect)]`.
"""

import pygame

from .primitives import box, caps, draw_button, ellipsize, hline, text
from .tokens import T, mix

ROW_H = T.S * 8


def draw_medic(surf, F, rect, rows, total_cost, total_hours, can_pay, mpos):
    row_rects = []
    y = rect.y
    footer_h = T.S * 6
    list_bottom = rect.bottom - footer_h
    if not rows:
        text(surf, F["body"], "Nobody here needs treating.", (rect.x, y + T.S), T.TX_MUTED)
    for r in rows:
        rr = pygame.Rect(rect.x, y, rect.w, ROW_H - T.S)
        if rr.bottom > list_bottom:
            break
        hover = r["enabled"] and rr.collidepoint(mpos)
        fill = mix(T.BRASS, T.STEEL, 0.85) if r["picked"] else (T.STEEL_HI if hover else T.STEEL)
        box(surf, rr, fill, T.BRASS if r["picked"] else T.STEEL_LINE)
        pad = T.S * 2
        caps(surf, F["head"], r["name"], (rr.x + pad, rr.y + T.S), T.TX if r["enabled"] else T.TX_FAINT)
        price = f"${r['cost']}  ·  {r['hours']} h"
        text(surf, F["bodyb"], price, (rr.right - pad, rr.y + T.S), T.BRASS if r["enabled"] else T.TX_FAINT, right=True)
        detail = r["note"] if not r["enabled"] else "  ·  ".join(r["lines"])
        text(surf, F["body_sm"], ellipsize(detail, F["body_sm"], rr.w - 2 * pad),
             (rr.x + pad, rr.y + T.S * 4), T.BLOOD if not r["enabled"] else T.TX_MUTED)
        row_rects.append((r["key"], rr))
        y += ROW_H

    hline(surf, rect.x, rect.right, list_bottom)
    fy = list_bottom + T.S * 2
    summary = f"${total_cost}  ·  {total_hours} h for the whole group" if total_cost else "pick who to treat"
    text(surf, F["bodyb"], summary, (rect.x, fy + T.S), T.BLOOD if total_cost and not can_pay else T.TX)
    treat = pygame.Rect(rect.right - T.S * 22, fy, T.S * 22, T.S * 4)
    draw_button(surf, F, treat, "TREAT" if can_pay or not total_cost else "CANNOT PAY",
                primary=bool(total_cost and can_pay), enabled=bool(total_cost and can_pay), mpos=mpos)
    return row_rects, treat

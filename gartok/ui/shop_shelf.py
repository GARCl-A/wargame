"""The shop tab's FOR SALE panel on a hub screen: the shelf, the cart and the till footer.

    draw_shelf(surf, F, rect, data, mpos) -> hit dict

`data`:
    {"cats": [(label, key)], "cat": key, "kind": "weapons" | "armor" | "kit", "all_size": str | None,
     "rows": [row], "scroll": int, "drop": bool (pack items picked: the panel is the sell drop zone),
     "foot": {"left", "right" (optional: "Purse after: $4"), "right_bad", "button", "primary", "enabled"}}
    a row is `market_draw._stock_data`'s: {"name", "base_name", "spec", "price", "base_price", "weight",
    "stock", "afford", "fits", "sel" (in the cart), "tag", "qty", "size"}

Returns {"panel", "list", "rows": [(rect, name)], "qty_hits": [(rect, name, delta)],
"size_hits": [(rect, base_name, size)], "header_size_hits": [(rect, size)], "cat_hits": [(rect, key)],
"button": rect | None, "hovered": name | None, "max_scroll": int}. Fonts: the `hub_*` set.
"""

import pygame

from ..constants import fmt_money
from ..item_icon import draw_icon
from .hub_frame import hub_button
from .primitives import dashed_rect, ellipsize, scrollbar, small_caps, text
from .tokens import T, mix

ROW_H = T.S * 7 + 2
FOOT_H = T.S * 11


def _chip(surf, F, x, y, label, on, mpos):
    font = F["hub_subb"] if on else F["hub_sub"]
    w = font.size(label)[0] + T.S * 2 + 4
    r = pygame.Rect(x - w, y, w, T.S * 3)
    hot = not on and r.collidepoint(mpos)
    pygame.draw.rect(surf, mix(T.STEEL, T.BRASS, 0.15) if on else T.STEEL, r, border_radius=r.h // 2)
    pygame.draw.rect(surf, T.BRASS if on else (T.TX_MUTED if hot else T.STEEL_LINE), r, 1, border_radius=r.h // 2)
    text(surf, font, label, r.center, T.TX if on else T.TX_MUTED, center=True)
    return r


def _stepper(surf, F, r, name, qty, mpos):
    box = pygame.Rect(r.right - T.S * 12 - 6, r.y + (r.h - T.S * 4) // 2, T.S * 12, T.S * 4)
    pygame.draw.rect(surf, T.TABLE, box, border_radius=4)
    pygame.draw.rect(surf, T.STEEL_LINE, box, 1, border_radius=4)
    third = box.w // 3
    hits = []
    for i, (glyph, delta) in enumerate((("−", -1), (str(qty), 0), ("+", 1))):
        cell = pygame.Rect(box.x + i * third, box.y, third, box.h)
        if delta and cell.collidepoint(mpos):
            pygame.draw.rect(surf, T.STEEL_HI, cell.inflate(-2, -2))
        text(surf, F["hub_bodyb" if not delta else "hub_body"], glyph, cell.center, T.TX, center=True)
        if delta:
            hits.append((cell, name, delta))
    for i in (1, 2):
        pygame.draw.line(surf, T.STEEL_LINE, (box.x + i * third, box.y), (box.x + i * third, box.bottom - 1))
    return box, hits


def _row(surf, F, r, row, weapons, hover, mpos, out):
    sel = row["sel"]
    sold_out = row["stock"] is not None and row["stock"] <= 0
    if sel:
        pygame.draw.rect(surf, mix(T.STEEL, T.BRASS, 0.07), r, border_radius=6)
        pygame.draw.rect(surf, T.BRASS_DIM, r, 1, border_radius=6)
    elif hover:
        pygame.draw.rect(surf, T.STEEL_HI, r, border_radius=6)
    icon = pygame.Rect(r.x + T.S, r.y + (r.h - T.S * 5) // 2, T.S * 5, T.S * 5)
    pygame.draw.rect(surf, mix(T.STEEL, T.TABLE, 0.5), icon, border_radius=4)
    draw_icon(surf, icon.inflate(-6, -6), row["name"])

    box, hits = _stepper(surf, F, r, row["name"], row["qty"], mpos)
    out["qty_hits"] += hits
    price, base = row["price"], row["base_price"]
    color = (T.TX_FAINT if not row["afford"] else T.GREEN if price < base
             else T.BLOOD if price > base else T.BRASS)
    pr = text(surf, F["hub_price"], fmt_money(price), (box.x - T.S * 2, r.y + T.S - 1), color, right=True)
    if base != price:
        was = text(surf, F["hub_sub"], fmt_money(base), (pr.x - T.S, r.y + T.S + 2), T.TX_FAINT, right=True)
        pygame.draw.line(surf, T.TX_FAINT, (was.x, was.centery), (was.right, was.centery))
        pr = was

    x = icon.right + T.S * 2
    room = pr.x - T.S * 2 - x
    if weapons:
        is_l = row.get("size") == "Large"
        for i, (label, size) in enumerate((("M", "Medium"), ("L", "Large"))):
            b = pygame.Rect(pr.x - T.S * 2 - (2 - i) * (T.S * 2 + 4), r.y + T.S - 1, T.S * 2 + 2, T.S * 2 + 2)
            on = (size == "Large") == is_l
            pygame.draw.rect(surf, T.BRASS if on else T.STEEL, b, border_radius=3)
            pygame.draw.rect(surf, T.STEEL_LINE, b, 1, border_radius=3)
            text(surf, F["hub_subb"], label, b.center, T.TABLE if on else T.TX_MUTED, center=True)
            out["size_hits"].append((b, row["base_name"], size))
        room -= T.S * 6
    ink = T.TX if (row["afford"] and not sold_out) or sel else T.TX_FAINT
    text(surf, F["hub_row"], ellipsize(row["name"], F["hub_row"], room), (x, r.y + T.S - 1), ink)
    left = "sold out" if sold_out else f"{row['stock']} left" if row["stock"] is not None else ""
    bits = [b for b in (row.get("tag", "").title(), row.get("spec", ""),
                        f"{row['weight']:.1f} kg", left) if b]
    sub = text(surf, F["hub_sub"], ellipsize("  ·  ".join(bits), F["hub_sub"], box.x - T.S * 2 - x),
               (x, r.y + T.S * 3 + 4), T.TX_MUTED)
    if not row["fits"]:
        text(surf, F["hub_subb"], "too heavy for anyone", (sub.right + T.S, sub.y), T.BLOOD)


def draw_shelf(surf, F, rect, data, mpos):
    out = {"panel": rect, "list": None, "rows": [], "qty_hits": [], "size_hits": [],
           "header_size_hits": [], "cat_hits": [], "button": None, "hovered": None, "max_scroll": 0}
    drop = data.get("drop")
    pygame.draw.rect(surf, T.STEEL, rect, border_radius=8)
    pygame.draw.rect(surf, T.BRASS if drop else T.STEEL_LINE, rect, 2 if drop else 1, border_radius=8)
    pad = T.S * 2 + 4
    small_caps(surf, F["hub_head"], F["hub_head_sc"], "For Sale", (rect.x + pad, rect.y + T.S * 2 + 2), T.TX)
    x = rect.right - pad
    cats = data.get("cats", [])
    if len(cats) > 1:
        for label, key in reversed(cats):
            r = _chip(surf, F, x, rect.y + T.S * 2, label, key == data.get("cat"), mpos)
            out["cat_hits"].append((r, key))
            x = r.x - T.S
    elif cats:
        text(surf, F["hub_sub"], cats[0][0], (x, rect.y + T.S * 3 - 2), T.TX_MUTED, right=True)
    head = rect.y + T.S * 6 + 4
    pygame.draw.line(surf, T.STEEL_LINE, (rect.x, head), (rect.right - 1, head))

    weapons = data.get("kind") == "weapons"
    top = head + T.S
    if weapons:
        all_size = data.get("all_size")
        bx = rect.right - pad
        for label, size in (("LRG", "Large"), ("MED", "Medium")):
            r = _chip(surf, F, bx, top, label, all_size == size, mpos)
            out["header_size_hits"].append((r, size))
            bx = r.x - T.S
        text(surf, F["hub_sub"], "all sizes", (bx - T.S, top + 5), T.TX_FAINT, right=True)
        top += T.S * 4

    foot_y = rect.bottom - FOOT_H
    lst = pygame.Rect(rect.x + T.S, top, rect.w - T.S * 2, foot_y - T.S - top)
    out["list"] = lst
    rows = data["rows"]
    fit = max(1, lst.h // ROW_H)
    out["max_scroll"] = max_scroll = max(0, len(rows) - fit)
    scroll = max(0, min(data.get("scroll", 0), max_scroll))
    clip = surf.get_clip()
    surf.set_clip(lst.clip(clip))
    y = lst.y
    for row in rows[scroll:scroll + fit]:
        r = pygame.Rect(lst.x, y, lst.w - (T.S if max_scroll else 0), ROW_H - T.S)
        hover = data.get("hover", True) and r.collidepoint(mpos)
        _row(surf, F, r, row, weapons, hover, mpos, out)
        if hover:
            out["hovered"] = row["name"]
        out["rows"].append((r, row["name"]))
        y += ROW_H
    surf.set_clip(clip)
    if max_scroll:
        scrollbar(surf, pygame.Rect(lst.right - 4, lst.y, 4, fit * ROW_H - T.S), scroll, max_scroll,
                  len(rows) * ROW_H)
    if drop:
        hint = pygame.Rect(lst.x, y + T.S, lst.w, lst.bottom - y - T.S)
        if hint.h > T.S * 6:
            dashed_rect(surf, hint, T.BRASS)
            text(surf, F["hub_body"], "Drop here to sell", hint.center, T.BRASS, center=True)

    pygame.draw.line(surf, T.STEEL_LINE, (rect.x, foot_y), (rect.right - 1, foot_y))
    foot = data["foot"]
    ty = foot_y + T.S * 2 + 4 - F["hub_body"].get_height() // 2
    right_x = rect.right - pad
    if foot.get("right"):
        label, value = foot["right"]
        v = text(surf, F["hub_bodyb"], value, (right_x, ty), T.BLOOD if foot.get("right_bad") else T.TX, right=True)
        right_x = text(surf, F["hub_body"], label + " ", (v.x, ty), T.TX_MUTED, right=True).x
    text(surf, F["hub_body"], ellipsize(foot["left"], F["hub_body"], right_x - T.S * 2 - (rect.x + pad)),
         (rect.x + pad, ty), T.TX_MUTED)
    if foot.get("button"):
        b = pygame.Rect(rect.x + pad, foot_y + T.S * 5, rect.w - 2 * pad, T.S * 5)
        hub_button(surf, F, b, foot["button"], primary=foot.get("primary", False),
                   enabled=foot.get("enabled", True), mpos=mpos)
        if foot.get("enabled", True):
            out["button"] = b
    return out

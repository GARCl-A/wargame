"""The market's shelf: category tabs, the stock list and the drag ghost.

The shopper columns beside it are `loadout_panel.column`; this module only
draws the vendor's side.

`stock_list` data::

    {
        "kind": "weapons" | "armor" | "kit",   # picks the column layout
        "all_size": "Medium" | "Large" | None, # weapons: which header toggle is lit
        "hover": bool,                         # rows react to the mouse (nothing picked up)
        "rows": [{
            "name": str,            # what a buy delivers (may be "Large X")
            "base_name": str,       # the shelf entry (size toggles key on this)
            "spec": str,            # one-line stat blurb, "" for none
            "price": int, "base_price": int,   # base differs -> struck-through "was"
            "weight": float,        # kg per unit
            "stock": int | None,    # units left, None = unlimited
            "afford": bool,         # purse covers it and it isn't sold out
            "fits": bool,           # someone can carry it
            "sel": bool,            # it is the current pick
            "tag": str,             # kit: the item tag shown beside the stepper
            "qty": int,             # kit: the stepper's quantity
            "size": "Medium" | "Large" | None,   # weapons: this row's toggle
        }, ...],
    }
"""

import pygame

from .loadout_panel import TAG_COLOR
from .primitives import caps, draw_button, ellipsize, hline, text
from .tokens import T, mix

_NAME_W = 138
_NAME_W_ARMOR = 148
_STEPPER_DX = 138
_SIZE_DX = 164
_TAG_DX = 204
_PRICE_DX = 52


def category_tabs(surf, F, rect, cats, active, mpos):
    """`cats` is `[(label, key), ...]`, spread evenly across `rect`.
    Returns `[(rect, key)]`."""
    gap = T.S
    n = max(1, len(cats))
    w = (rect.w - (n - 1) * gap) // n
    hits = []
    for i, (label, key) in enumerate(cats):
        r = pygame.Rect(rect.x + i * (w + gap), rect.y, w, rect.h)
        draw_button(surf, F, r, label.upper(), ghost=key != active, mpos=mpos)
        hits.append((r, key))
    return hits


def stock_list(surf, F, rect, data, mpos):
    """The FOR SALE panel. Returns `{"rows": [(rect, name)], "qty_hits":
    [(rect, name, delta)], "size_hits": [(rect, base_name, size)],
    "header_size_hits": [(rect, size)], "hovered": name | None}`."""
    out = {"rows": [], "qty_hits": [], "size_hits": [], "header_size_hits": [], "hovered": None}
    kind = data["kind"]
    kit = kind == "kit"
    weapons = kind == "weapons"

    pygame.draw.rect(surf, T.STEEL, rect)
    pygame.draw.rect(surf, T.STEEL_LINE, rect, 1)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4
    wt_x = rect.right - T.S * 2
    price_x = wt_x - _PRICE_DX

    caps(surf, F["micro"], "FOR SALE", (x, rect.y + T.S * 2), T.TX_FAINT)
    if weapons:
        tw, th = 46, 18
        med = pygame.Rect(rect.right - T.S * 2 - tw * 2 - 2, rect.y + T.S, tw, th)
        lrg = pygame.Rect(rect.right - T.S * 2 - tw, rect.y + T.S, tw, th)
        all_med = data.get("all_size") == "Medium"
        all_lrg = data.get("all_size") == "Large"
        draw_button(surf, F, med, "MED", primary=all_med, ghost=not all_med, mpos=mpos)
        draw_button(surf, F, lrg, "LRG", primary=all_lrg, ghost=not all_lrg, mpos=mpos)
        out["header_size_hits"] += [(med, "Medium"), (lrg, "Large")]

    hline(surf, x, rect.right - T.S * 2, rect.y + T.S * 4)

    y = rect.y + T.S * 5
    caps(surf, F["micro"], "ITEM", (x, y), T.TX_FAINT)
    if kit:
        caps(surf, F["micro"], "QTY", (x + 152, y), T.TX_FAINT)
    elif weapons:
        caps(surf, F["micro"], "SIZE", (x + 168, y), T.TX_FAINT)
    caps(surf, F["micro"], "PRICE", (price_x, y), T.TX_FAINT, right=True)
    caps(surf, F["micro"], "WT", (wt_x, y), T.TX_FAINT, right=True)
    y += 17

    row_h = 30 if kit else 34
    name_w = _NAME_W if (kit or weapons) else _NAME_W_ARMOR
    for row in data["rows"]:
        r = pygame.Rect(x, y, w, row_h)
        hov = data.get("hover", True) and r.collidepoint(mpos)
        _stock_row(surf, F, r, row, kit, weapons, name_w, price_x, wt_x, hov, mpos, out)
        if hov:
            out["hovered"] = row["name"]
        out["rows"].append((r, row["name"]))
        y += row_h + T.S
    return out


def _stock_row(surf, F, r, row, kit, weapons, name_w, price_x, wt_x, hov, mpos, out):
    sel = row["sel"]
    price, base = row["price"], row["base_price"]
    stock = row["stock"]
    sold_out = stock is not None and stock <= 0

    fill = mix(T.BRASS, T.STEEL, .85) if sel else T.STEEL_HI if hov else T.TABLE
    pygame.draw.rect(surf, fill, r)
    pygame.draw.rect(surf, T.BRASS if sel else T.STEEL_LINE, r, 1)

    ink = T.TX if sel or row["afford"] else T.TX_FAINT
    faint = T.TX_MUTED if sel else T.TX_FAINT
    if sel:
        price_col = T.TX
    elif not row["afford"]:
        price_col = T.TX_FAINT
    elif price < base:
        price_col = T.GREEN
    elif price > base:
        price_col = T.BLOOD
    else:
        price_col = T.TX

    spec = "" if kit else row.get("spec", "")
    name_y = r.y + 4 if spec else r.centery - 8
    text(surf, F["body"], ellipsize(row["name"], F["body"], name_w), (r.x + T.S, name_y), ink)
    if spec:
        text(surf, F["micro"], spec, (r.x + T.S, r.y + 17), faint)

    if weapons:
        bw, bh = 20, 18
        by = r.centery - bh // 2
        btn_m = pygame.Rect(r.x + _SIZE_DX, by, bw, bh)
        btn_l = pygame.Rect(btn_m.right, by, bw, bh)
        is_l = row.get("size") == "Large"
        draw_button(surf, F, btn_m, "M", primary=not is_l, ghost=is_l, mpos=mpos)
        draw_button(surf, F, btn_l, "L", primary=is_l, ghost=not is_l, mpos=mpos)
        out["size_hits"] += [(btn_m, row["base_name"], "Medium"), (btn_l, row["base_name"], "Large")]

    tag_x = r.x + _TAG_DX
    if kit:
        out["qty_hits"] += _stepper(surf, F, r, row["name"], row["qty"], sel, mpos)
        tag = row.get("tag")
        if tag:
            caps(surf, F["micro"], tag, (tag_x, r.centery - 5), TAG_COLOR.get(tag, T.TX_FAINT))
    if stock is not None:
        caps(surf, F["micro"], "SOLD OUT" if sold_out else f"{stock} left",
             (tag_x, r.centery + 3), T.BLOOD if sold_out else T.TX_MUTED)

    caps(surf, F["micro"], f"{row['weight']:.1f} kg", (wt_x, r.centery - 5),
         T.TX_FAINT if row["fits"] else T.BLOOD, right=True)
    price_w = F["body"].size(f"{price}c")[0]
    text(surf, F["body"], f"{price}c", (price_x, r.centery - 8), price_col, right=True)
    if base != price:
        was_x = price_x - price_w - T.S
        was_w = F["micro"].size(f"{base}c")[0]
        caps(surf, F["micro"], f"{base}c", (was_x, r.centery - 5), faint, right=True)
        pygame.draw.line(surf, faint, (was_x - was_w, r.centery - 1), (was_x, r.centery - 1), 1)


def _stepper(surf, F, row, key, qty, sel, mpos):
    bw, bh = 16, 18
    cy = row.centery
    minus = pygame.Rect(row.x + _STEPPER_DX, cy - bh // 2, bw, bh)
    plus = pygame.Rect(minus.right + 26, cy - bh // 2, bw, bh)
    hits = []
    for r, glyph, delta in ((minus, "-", -1), (plus, "+", +1)):
        draw_button(surf, F, r, glyph, ghost=True, mpos=mpos)
        hits.append((r, key, delta))
    caps(surf, F["microb"], str(qty), ((minus.right + plus.x) // 2, cy - 6),
         T.BRASS if sel else T.TX, center=True)
    return hits


def drag_ghost(surf, F, label, mpos):
    """The brass chip that follows the cursor while something is dragged."""
    gx, gy = mpos
    r = pygame.Rect(gx + 12, gy + 6, F["body"].size(label)[0] + 2 * T.S, 20)
    pygame.draw.rect(surf, mix(T.BRASS, T.STEEL, .85), r)
    pygame.draw.rect(surf, T.BRASS, r, 1)
    text(surf, F["body"], label, r.center, T.TX, center=True)

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

from ..constants import fmt_money
from .loadout_panel import ICON, TAG_COLOR, item_icon
from .primitives import caps, draw_button, ellipsize, hline, text
from .tokens import T, mix

_STEPPER_W = 58         # minus, qty, plus
_SIZE_W = 40            # the M / L pair
_WT_W = 56              # "10.0 kg" plus a gap


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

    cols = _columns(F, x, wt_x, data["rows"], kit, weapons)
    price_x = cols["price_x"]

    y = rect.y + T.S * 5
    caps(surf, F["micro"], "ITEM", (x, y), T.TX_FAINT)
    if kit:
        caps(surf, F["micro"], "QTY", (cols["ctl_x"], y), T.TX_FAINT)
    elif weapons:
        caps(surf, F["micro"], "SIZE", (cols["ctl_x"], y), T.TX_FAINT)
    caps(surf, F["micro"], "PRICE", (price_x, y), T.TX_FAINT, right=True)
    caps(surf, F["micro"], "WT", (wt_x, y), T.TX_FAINT, right=True)
    y += 17

    row_h = 30 if kit else 34
    for row in data["rows"]:
        r = pygame.Rect(x, y, w, row_h)
        hov = data.get("hover", True) and r.collidepoint(mpos)
        _stock_row(surf, F, r, row, kit, weapons, cols, wt_x, hov, mpos, out)
        if hov:
            out["hovered"] = row["name"]
        out["rows"].append((r, row["name"]))
        y += row_h + T.S
    return out


def _columns(F, x, wt_x, rows, kit, weapons):
    """Where each column of the shelf starts, laid out right to left from the
    texts the rows really hold, so a long price or tag pushes the name's room
    in instead of landing on top of its neighbour."""
    micro, body = F["micro"], F["body"]
    price_w = 0
    tag_w = 0
    for row in rows:
        w = body.size(fmt_money(row["price"]))[0]
        if row["base_price"] != row["price"]:
            w += T.S + micro.size(fmt_money(row["base_price"]))[0]
        price_w = max(price_w, w)
        stock = row["stock"]
        if stock is not None:
            tag_w = max(tag_w, micro.size("SOLD OUT" if stock <= 0 else f"{stock} LEFT")[0])
        if kit and row.get("tag"):
            tag_w = max(tag_w, micro.size(row["tag"].upper())[0])
    price_x = wt_x - _WT_W
    tag_x = price_x - price_w - T.S * 2 - tag_w
    ctl_w = _STEPPER_W if kit else _SIZE_W if weapons else 0
    ctl_x = tag_x - T.S - ctl_w if ctl_w else tag_x
    return {"price_x": price_x, "tag_x": tag_x, "ctl_x": ctl_x, "name_right": ctl_x - T.S}


def _stock_row(surf, F, r, row, kit, weapons, cols, wt_x, hov, mpos, out):
    price_x = cols["price_x"]
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
    name_x = item_icon(surf, row["name"], r.x + 4, r.centery, min(ICON, r.h - 6))
    name_w = cols["name_right"] - name_x
    text(surf, F["body"], ellipsize(row["name"], F["body"], name_w), (name_x, name_y), ink)
    if spec:
        text(surf, F["micro"], ellipsize(spec, F["micro"], name_w), (name_x, r.y + 17), faint)

    if weapons:
        bw, bh = 20, 18
        by = r.centery - bh // 2
        btn_m = pygame.Rect(cols["ctl_x"], by, bw, bh)
        btn_l = pygame.Rect(btn_m.right, by, bw, bh)
        is_l = row.get("size") == "Large"
        draw_button(surf, F, btn_m, "M", primary=not is_l, ghost=is_l, mpos=mpos)
        draw_button(surf, F, btn_l, "L", primary=is_l, ghost=not is_l, mpos=mpos)
        out["size_hits"] += [(btn_m, row["base_name"], "Medium"), (btn_l, row["base_name"], "Large")]

    tag_x = cols["tag_x"]
    if kit:
        out["qty_hits"] += _stepper(surf, F, r, cols["ctl_x"], row["name"], row["qty"], sel, mpos)
    lines = []
    tag = row.get("tag") if kit else None
    if tag:
        lines.append((tag, TAG_COLOR.get(tag, T.TX_FAINT)))
    if stock is not None:
        lines.append(("SOLD OUT" if sold_out else f"{stock} left", T.BLOOD if sold_out else T.TX_MUTED))
    line_h = F["micro"].get_height()
    ty = r.centery - line_h * len(lines) // 2
    for label, color in lines:
        caps(surf, F["micro"], label, (tag_x, ty), color)
        ty += line_h

    caps(surf, F["micro"], f"{row['weight']:.1f} kg", (wt_x, r.centery - 5),
         T.TX_FAINT if row["fits"] else T.BLOOD, right=True)
    price_w = F["body"].size(fmt_money(price))[0]
    text(surf, F["body"], fmt_money(price), (price_x, r.centery - 8), price_col, right=True)
    if base != price:
        was_x = price_x - price_w - T.S
        was_w = F["micro"].size(fmt_money(base))[0]
        caps(surf, F["micro"], fmt_money(base), (was_x, r.centery - 5), faint, right=True)
        pygame.draw.line(surf, faint, (was_x - was_w, r.centery - 1), (was_x, r.centery - 1), 1)


def _stepper(surf, F, row, x, key, qty, sel, mpos):
    bw, bh = 16, 18
    cy = row.centery
    minus = pygame.Rect(x, cy - bh // 2, bw, bh)
    plus = pygame.Rect(x + _STEPPER_W - bw, cy - bh // 2, bw, bh)
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

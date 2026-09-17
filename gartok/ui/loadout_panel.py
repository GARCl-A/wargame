"""The RAIL / column / CARGO pieces `group_screen.py`'s BAGS and CARGO
views are built from -- factored out so a future screen that needs the
same "member as a bag of gear" view (`gear_screen.py`, one day) reuses
these instead of forking `group_screen.py`'s copy.

Purely presentational, same contract as the rest of `gartok.ui`: every
function takes plain dicts/tuples the caller adapts a `Unit`/`Group` into
(see `group_screen.py`'s own `_member_dict`/`_cargo_rows`) and never calls
a `Unit` method itself -- game-rules questions like "does this fit that
slot" or "what's the hit bonus" are answered by the caller and handed in
as an already-computed bool/string (`accepts`, `note`, ...). Hit rects
come back keyed by whatever the caller's data used as `key` (a slot name,
a pack index, a `(uid, idx)` pair, ...) -- never a `Unit` -- so the caller
(which already knows which real object each key maps to) does the last
translation step itself.
"""

import pygame

from .. import icons
from .inspector_panel import ROLE_MARK, draw_role
from .primitives import caps, contained, draw_button, hline, scrollbar, text
from .tokens import T, mix

TAG_COLOR = {"": T.TX_FAINT, "WEAPON": T.TX_MUTED, "ARMOR": T.TX_MUTED,
             "AMMO": T.TX_FAINT, "HEAL": T.GREEN, "LIGHT": T.BRASS_DIM,
             "FOOD": T.TX_FAINT, "CHEST": T.BRASS, "SEALED": T.BRASS}

SLOT_LABELS = {"hand": "main hand", "offhand": "off hand", "tongue": "tongue", "armor": "armor"}


def load_bar(surf, rect, ratio, over):
    """The bar the loadout tracks all use: fill marks current/cap, the
    thin tick at 72% marks the normal-carry threshold (past it the bar
    turning brass, then blood past 100%, is the actual warning -- the
    tick is just a fixed reference line, not itself a threshold check)."""
    pygame.draw.rect(surf, T.TABLE, rect)
    pygame.draw.rect(surf, T.STEEL_LINE, rect, 1)
    w = int((rect.w - 2) * min(max(ratio, 0), 1.0))
    col = T.BLOOD if over else T.GREEN if ratio < .7 else T.BRASS
    pygame.draw.rect(surf, col, pygame.Rect(rect.x + 1, rect.y + 1, w, rect.h - 2))
    mark = rect.x + int((rect.w - 2) * .72)
    pygame.draw.line(surf, T.TX_FAINT, (mark, rect.y - 2), (mark, rect.bottom + 2), 1)


def slot(surf, F, rect, kind, held, mouse):
    """One HAND/OFF/TONGUE/BODY box. `held` is `{"name","note","accepts"}`
    or `None` to draw the box as a placeholder text with nothing to pick
    up or drop into (the two-handed "off hand" line). `rect` is the
    caller's own -- there is nothing to report back, it already has it
    for hit-testing."""
    caps(surf, F["micro"], SLOT_LABELS[kind], (rect.x, rect.y - 13), T.TX_FAINT)
    if held is None:
        pygame.draw.rect(surf, T.TABLE, rect)
        pygame.draw.rect(surf, T.STEEL_LINE, rect, 1)
        text(surf, F["body_sm"], "2-handed weapon", (rect.x + T.S, rect.centery - 6), T.TX_FAINT)
        return

    name, note, accepts, sel = held["name"], held["note"], held["accepts"], held["sel"]
    drop = accepts and not sel and rect.collidepoint(mouse)
    fill = mix(T.BRASS, T.STEEL, .82) if sel else T.STEEL_HI if drop else T.TABLE
    border = T.BRASS if (sel or drop) else T.STEEL_LINE
    pygame.draw.rect(surf, fill, rect)
    pygame.draw.rect(surf, border, rect, 1)
    with contained(surf, rect.inflate(-16, 0)):
        text(surf, F["body"], name or "empty", (rect.x + T.S, rect.centery - 8),
             T.TX_FAINT if not name else T.TX)
    if note:
        caps(surf, F["micro"], note, (rect.right - T.S, rect.centery - 5), T.TX_FAINT, right=True)


def pack_row(surf, F, rect, item, *, selected, mouse):
    """One pack-stack row. `item` is `(name, tag, weight_each, qty,
    locked)`. Returns `(lock_rect, dots_rect)` -- the padlock toggle and
    the "⋮" menu button, both hit zones the caller registers separately
    from the row itself (clicking either must not also pick the row up)."""
    name, tag, weight, qty, locked = item
    pygame.draw.rect(surf, mix(T.BRASS, T.STEEL, .85) if selected else T.TABLE, rect)
    pygame.draw.rect(surf, T.BRASS if selected else T.STEEL_LINE, rect, 1)

    name_x = rect.x + T.S
    lock_r = pygame.Rect(name_x, rect.centery - 9, 18, 18)
    icons.icon(surf, "lock" if locked else "unlock", lock_r, T.BRASS if locked else T.TX_FAINT)
    name_x += 22

    dots_r = pygame.Rect(rect.right - T.S * 3, rect.centery - 10, 20, 20)
    draw_button(surf, F, dots_r, "⋮", ghost=True, mpos=mouse)

    label = name if qty == 1 else f"{name}  ×{qty}"
    text(surf, F["body"], label, (name_x, rect.centery - 13), T.TX_FAINT if locked else T.TX)
    caps(surf, F["micro"], tag, (name_x, rect.centery + 3), TAG_COLOR.get(tag, T.TX_FAINT))

    total = weight * qty
    caps(surf, F["micro"], f"{total:.1f} kg", (rect.right - T.S * 7, rect.centery + 2),
         T.BLOOD if total >= 10 else T.TX_FAINT, right=True)
    return lock_r, dots_r


def rail(surf, F, rect, members, pinned_keys, carrying, scroll, mouse):
    """Every member as a compact row, always -- a rail row is both a pin
    toggle and, from the caller's own `zones`, a drop target whether or
    not that member's column is pinned open. `members` is `[{"key","name",
    "role","kg","cap"}]`; `carrying` highlights the hovered row as a valid
    drop target while the caller is carrying something. Returns `(hits,
    max_scroll)` -- `hits` is `[(rect, key)]`, scrolled rows included
    (off-screen ones just won't be under the mouse)."""
    pygame.draw.rect(surf, T.STEEL, rect)
    pygame.draw.line(surf, T.STEEL_LINE, (rect.right - 1, rect.y), (rect.right - 1, rect.bottom), 1)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4

    row_h = T.S * 7
    content_h = len(members) * (row_h + 4)
    header_h = T.S * 5
    max_scroll = max(0, content_h - (rect.h - header_h - T.S))
    scroll = max(0, min(scroll, max_scroll))

    hits = []
    area = pygame.Rect(rect.x, rect.y + header_h, rect.w, rect.h - header_h - T.S)
    with contained(surf, area):
        y = area.y - scroll
        for m in members:
            r = pygame.Rect(x, y, w, row_h)
            hits.append((r, m["key"]))
            if r.bottom >= area.y and r.y <= area.bottom:
                pinned = m["key"] in pinned_keys
                drop_hot = carrying and r.collidepoint(mouse)
                pygame.draw.rect(surf, T.STEEL_HI if (pinned or drop_hot) else T.TABLE, r)
                pygame.draw.rect(surf, T.BRASS if drop_hot else T.STEEL_LINE, r, 1)
                if pinned:
                    pygame.draw.rect(surf, T.BRASS, pygame.Rect(r.x, r.y, 3, r.h))
                draw_role(surf, (r.x + T.S * 2, r.y + T.S * 2), ROLE_MARK.get(m["role"], "sword"), T.TX_MUTED)
                text(surf, F["body"], m["name"], (r.x + T.S * 4, r.y + T.S - 2), T.TX if pinned else T.TX_MUTED)
                free = m["cap"] - m["kg"]
                caps(surf, F["micro"], f"{free:+.1f}", (r.right - T.S, r.y + T.S),
                     T.BLOOD if free < 0 else T.GREEN if free > 4 else T.TX_MUTED, right=True)
                ratio = (m["kg"] / m["cap"]) if m["cap"] else 0
                load_bar(surf, pygame.Rect(r.x + T.S, r.y + T.S * 4, r.w - T.S * 2, 6), ratio, m["kg"] > m["cap"])
            y = r.bottom + 4
        if max_scroll > 0:
            scrollbar(surf, area, scroll, max_scroll, content_h)
    return hits, max_scroll


def column(surf, F, rect, member, scroll, mouse):
    """One full member column: header (name, role, load), HAND/OFF/
    (TONGUE)/BODY slots, scrollable PACK. `member` is a dict the caller
    builds (see `group_screen._member_dict`) carrying every slot's
    already-resolved `{"name","note","accepts","sel"}` (or `None` for a
    slot the caller doesn't want drawn as interactive, e.g. a blocked
    off-hand) and `pack: [(name, tag, weight, qty, locked, sel)]`.

    Returns a dict of hit info; the caller already knows which real `Unit`
    this column belongs to (it built `member` from one), so it zips these
    straight onto its own `sources`/`zones`/`sheet_hits` without any key
    lookup:
      {"sheet_rect", "slot_rects": {kind: rect_or_None}, "pack_zone",
       "pack_area", "pack_hits": [(rect, idx)], "lock_hits": [(rect, idx)],
       "dots_hits": [(rect, idx)], "scroll"}
    """
    pygame.draw.rect(surf, T.STEEL, rect)
    pygame.draw.rect(surf, T.STEEL_LINE, rect, 1)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4
    over = member["kg"] > member["cap"]

    head = pygame.Rect(rect.x, rect.y, rect.w, T.S * 11)
    pygame.draw.rect(surf, T.STEEL_HI, head)
    hline(surf, head.x, head.right, head.bottom)
    draw_role(surf, (x + 8, head.y + T.S * 2 + 2), ROLE_MARK.get(member["role"], "sword"), T.TX_MUTED)

    edge = head.right - T.S * 2 - 24
    if member["pending_picks"]:
        lbl = "● LEVEL UP"
        caps(surf, F["micro"], lbl, (edge, head.y + 6), T.BRASS, right=True)
        edge -= F["micro"].size(lbl)[0] + T.S
    text(surf, F["nameb"], member["name"], (x + T.S * 3, head.y + T.S), T.TX)

    sheet_rect = pygame.Rect(head.right - T.S * 2 - 20, head.y + T.S + 2, 20, 20)
    draw_button(surf, F, sheet_rect, "?", ghost=True, mpos=mouse)

    load_bar(surf, pygame.Rect(x, head.y + T.S * 5, w, 8),
             (member["kg"] / member["cap"]) if member["cap"] else 0, over)
    caps(surf, F["micro"], f"{member['kg']:.1f} / {member['cap']:.0f} kg",
         (x, head.y + T.S * 7 + 2), T.BLOOD if over else T.TX_MUTED)
    if over:
        caps(surf, F["micro"], f"+{member['kg'] - member['cap']:.1f} kg",
             (head.right - T.S * 2, head.y + T.S * 7 + 2), T.BLOOD, right=True)

    y = head.bottom + T.S * 4
    slot_rects = {}
    for kind in ("hand", "offhand", "tongue", "armor"):
        held = member.get(kind, "skip")
        if held == "skip":
            continue
        r = pygame.Rect(x, y, w, T.S * 5)
        slot(surf, F, r, kind, held, mouse)
        slot_rects[kind] = r if held is not None else None
        y = r.bottom + T.S * 3

    items = member["pack"]
    carried_kg = sum(w_ * q for _, _, w_, q, *_ in items)
    caps(surf, F["micro"], f"pack  ·  {len(items)} stacks", (x, y), T.TX_FAINT)
    caps(surf, F["micro"], f"{carried_kg:.1f} kg", (x + w, y), T.TX_FAINT, right=True)
    y += T.S * 3

    list_rect = pygame.Rect(x, y, w, rect.bottom - T.S * 2 - y)
    pack_zone = rect
    pack_area = list_rect

    pack_hits, lock_hits, dots_hits = [], [], []
    if not items:
        text(surf, F["body_sm"], "carrying nothing", (x, y + 4), T.TX_FAINT)
        return {"sheet_rect": sheet_rect, "slot_rects": slot_rects, "pack_zone": pack_zone,
                "pack_area": pack_area, "pack_hits": pack_hits, "lock_hits": lock_hits,
                "dots_hits": dots_hits, "scroll": 0}

    # `scroll` is an item-index offset (rows scrolled past), not pixels --
    # it's `PackColumnMixin`'s own wheel handler that owns this value
    # (`gartok/packbox.py`, shared with `GearScreen`), one row per wheel
    # tick, clamped only to `len(items)-1`; re-clamp here to what actually
    # fits so a stale value from a shorter previous list can't skip rows
    row_h = T.S * 6 + T.S
    visible_n = max(1, list_rect.h // row_h)
    max_pack_scroll = max(0, len(items) - visible_n)
    scroll = max(0, min(scroll, max_pack_scroll))
    content_h = len(items) * row_h

    with contained(surf, list_rect):
        iy = list_rect.y
        for idx in range(scroll, min(len(items), scroll + visible_n)):
            name, tag, weight, qty, locked, sel = items[idx]
            r = pygame.Rect(x, iy, w - (8 if max_pack_scroll > 0 else 0), T.S * 6)
            lock_r, dots_r = pack_row(surf, F, r, (name, tag, weight, qty, locked),
                                      selected=sel, mouse=mouse)
            pack_hits.append((r, idx))
            lock_hits.append((lock_r, idx))
            dots_hits.append((dots_r, idx))
            iy = r.bottom + T.S
        if max_pack_scroll > 0:
            scrollbar(surf, list_rect, scroll, max_pack_scroll, content_h)

    return {"sheet_rect": sheet_rect, "slot_rects": slot_rects, "pack_zone": pack_zone,
            "pack_area": pack_area, "pack_hits": pack_hits, "lock_hits": lock_hits,
            "dots_hits": dots_hits, "scroll": scroll}


def cargo_table(surf, F, rect, rows, scroll, mouse):
    """Every stack across the whole band, one sortable table. `rows` is
    `[(key, name, tag, weight, qty, locked, sel, carrier_label)]` -- `key`
    is whatever the caller marks selection with (a `(uid, idx)` pair, most
    likely). Returns `{"list_rect", "scroll", "max_scroll", "hits":
    [(rect, key)], "lock_hits": [(rect, key)], "dots_hits": [(rect, key)]}`."""
    hd = pygame.Rect(rect.x, rect.y, rect.w, T.S * 3)
    pygame.draw.rect(surf, T.TABLE, hd)
    for lab, dx in (("item", T.S * 4), ("weight", rect.w - T.S * 30), ("carried by", rect.w - T.S * 16)):
        caps(surf, F["micro"], lab, (rect.x + dx, hd.centery - 5), T.TX_FAINT)
    caps(surf, F["micro"], "↓", (rect.x + rect.w - T.S * 32, hd.centery - 5), T.BRASS)
    hline(surf, rect.x, rect.right, hd.bottom)

    list_rect = pygame.Rect(rect.x, hd.bottom, rect.w, rect.h - hd.h)
    row_h = T.S * 5
    content_h = len(rows) * row_h
    max_scroll = max(0, content_h - list_rect.h)
    scroll = max(0, min(scroll, max_scroll))

    hits, lock_hits, dots_hits = [], [], []
    with contained(surf, list_rect):
        y = list_rect.y - scroll
        for key, name, tag, weight, qty, locked, sel, carrier in rows:
            r = pygame.Rect(rect.x, y, rect.w, row_h)
            if r.bottom > list_rect.y and r.y < list_rect.bottom:
                lock_r, menu_rects = _cargo_row(surf, F, r, name, tag, weight, qty, locked, sel, carrier, mouse)
                lock_hits.append((lock_r, key))
                dots_hits.extend((mr, key) for mr in menu_rects)
                hits.append((r, key))
            y = r.bottom
        if max_scroll > 0:
            scrollbar(surf, list_rect, scroll, max_scroll, content_h)

    return {"list_rect": list_rect, "scroll": scroll, "max_scroll": max_scroll,
            "hits": hits, "lock_hits": lock_hits, "dots_hits": dots_hits}


def _cargo_row(surf, F, r, name, tag, weight, qty, locked, sel, carrier, mouse):
    pygame.draw.rect(surf, mix(T.BRASS, T.STEEL, .88) if sel else T.STEEL, r)
    hline(surf, r.x, r.right, r.bottom - 1)

    cb = pygame.Rect(r.x + T.S * 2, r.centery - 6, 12, 12)
    pygame.draw.rect(surf, T.BRASS if sel else T.STEEL_LINE, cb, 1)
    if sel:
        pygame.draw.lines(surf, T.BRASS, False, [(cb.x + 3, cb.centery),
                          (cb.centerx, cb.bottom - 4), (cb.right - 3, cb.y + 3)], 2)

    lock_r = pygame.Rect(cb.right + T.S, r.centery - 9, 18, 18)
    icons.icon(surf, "lock" if locked else "unlock", lock_r, T.BRASS if locked else T.TX_FAINT)

    dots_r = pygame.Rect(r.right - T.S * 4, r.centery - 10, 20, 20)
    draw_button(surf, F, dots_r, "⋮", ghost=True, mpos=mouse)

    # "carried by" doubles as a dropdown -- a second way into the same
    # send-to menu the "⋮" opens, right where the eye already is when
    # scanning who's holding what
    carrier_r = pygame.Rect(dots_r.x - T.S - T.S * 13, r.centery - 12, T.S * 13, T.S * 3)
    hov = carrier_r.collidepoint(mouse)
    pygame.draw.rect(surf, T.STEEL_HI if hov else T.TABLE, carrier_r)
    pygame.draw.rect(surf, T.STEEL_LINE, carrier_r, 1)
    caps(surf, F["micro"], carrier, (carrier_r.x + T.S, carrier_r.centery - 5), T.TX_MUTED)
    caps(surf, F["micro"], "▾", (carrier_r.right - T.S, carrier_r.centery - 5), T.TX_FAINT, right=True)

    name_x = lock_r.right + T.S
    label = name if qty == 1 else f"{name}  ×{qty}"
    text(surf, F["body"], label, (name_x, r.centery - 8), T.TX)
    caps(surf, F["micro"], tag, (name_x + F["body"].size(label)[0] + T.S,
         r.centery - 5), TAG_COLOR.get(tag, T.TX_FAINT))

    total = weight * qty
    text(surf, F["bodyb"] if total >= 10 else F["body"], f"{total:.1f} kg",
         (carrier_r.x - T.S, r.centery - 8), T.BLOOD if total >= 10 else T.TX_MUTED, right=True)
    return lock_r, [dots_r, carrier_r]


def cargo_bulk_bar(surf, F, rect, sel_count, sel_kg, actions, mouse):
    """The bulk-action footer that appears once something is selected in
    CARGO. `actions` is `[(key, label, enabled, primary)]`, right-to-left.
    Returns `hits: [(rect, key)]` for the enabled ones."""
    pygame.draw.rect(surf, T.TABLE, rect)
    hline(surf, rect.x, rect.right, rect.y, T.BRASS)
    caps(surf, F["microb"], f"{sel_count} selected  ·  {sel_kg:.1f} kg",
         (rect.x + T.S * 3, rect.centery - 6), T.BRASS)

    hits = []
    bx = rect.right - T.S * 3
    for key, lab, enabled, primary in actions:
        w = T.S * 16
        r = pygame.Rect(bx - w, rect.y + T.S * 2, w, rect.h - T.S * 4)
        draw_button(surf, F, r, lab, primary=primary, enabled=enabled, mpos=mouse)
        if enabled:
            hits.append((r, key))
        bx -= w + T.S
    return hits


def send_menu(surf, F, anchor, rows, mouse):
    """The right-click "send to.../split/drop" popup. `rows` is
    `[(kind, label, arg)]` -- `arg` is opaque, echoed back untouched in
    the hit (a destination's `uid` for a "member" row, `None` otherwise).
    Returns `{"rect", "hits": [(rect, kind, arg)]}`."""
    W, H = surf.get_size()
    row_h = 24
    w = max(180, max(F["body"].size(lbl)[0] for _, lbl, _ in rows) + T.S * 4)
    h = 22 + len(rows) * row_h + T.S
    x, y = anchor
    rect = pygame.Rect(min(x, W - w - T.S * 2), min(y, H - h - T.S * 2), w, h)
    pygame.draw.rect(surf, T.STEEL_HI, rect)
    pygame.draw.rect(surf, T.BRASS, rect, 1)

    hits = []
    iy = rect.y + 22
    for kind, label, arg in rows:
        r = pygame.Rect(rect.x + T.S, iy, rect.w - T.S * 2, row_h)
        hov = r.collidepoint(mouse)
        if hov:
            pygame.draw.rect(surf, T.STEEL, r)
        col = T.BLOOD if kind == "drop" else T.BRASS if hov else T.TX
        text(surf, F["body"], label, (r.x + T.S, r.centery - 7), col)
        hits.append((r, kind, arg))
        iy += row_h
    return {"rect": rect, "hits": hits}


def split_prompt(surf, F, center, name, amount, held, mouse):
    """The split-stack quantity picker. Returns `{"rect", "hits":
    [(rect, "minus"|"plus"|"confirm")]}`."""
    w, h = 260, 110
    rect = pygame.Rect(0, 0, w, h)
    rect.center = center
    pygame.draw.rect(surf, (8, 9, 11), rect.move(4, 5))
    pygame.draw.rect(surf, T.STEEL_HI, rect)
    pygame.draw.rect(surf, T.BRASS, rect, 1)

    caps(surf, F["microb"], f"split {name}", (rect.centerx, rect.y + T.S * 2), T.TX, center=True)

    minus_r = pygame.Rect(rect.x + T.S * 3, rect.y + T.S * 5, 28, 28)
    plus_r = pygame.Rect(rect.right - T.S * 3 - 28, rect.y + T.S * 5, 28, 28)
    draw_button(surf, F, minus_r, "-", ghost=True, mpos=mouse)
    draw_button(surf, F, plus_r, "+", ghost=True, mpos=mouse)
    text(surf, F["bodyb"], f"{amount} / {held}", rect.center, T.TX, center=True)

    confirm_r = pygame.Rect(rect.x + T.S * 2, rect.bottom - T.S * 5, rect.w - T.S * 4, T.S * 4)
    draw_button(surf, F, confirm_r, "SPLIT INTO TWO STACKS", primary=True, mpos=mouse)

    return {"rect": rect, "hits": [(minus_r, "minus"), (plus_r, "plus"), (confirm_r, "confirm")]}

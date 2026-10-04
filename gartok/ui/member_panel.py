"""The member detail panel of the guild screen, one block per function.

Every `draw_*` takes `(surf, F, x, y, w, data, mpos)` and returns
`(y_below, tip)`; `tip` is a tooltip string when the mouse is over something
that explains itself, else None. Data is plain dicts / tuples:

- `identity`: `{"name", "sub", "where", "task", "token"}`; a stat `tip` is a string or tooltip lines
- `vitals`: `{"hp": (cur, max), "hp_tip", "stats": [(label, value, tip)], "attrs": [(label, value, mod, penalised)]}`
- `weapon`: `{"name", "tags", "chips": [(label, value, tip)]}`
- `gear`: `{"hands", "armor", "armor_note", "coins", "rations": (n, ok), "load": (cur, normal, max), "load_state": (text, color)}`
- `ability`: `(name, description)`
- `tracks`: `[{"label", "value", "frac" (0-1 or None), "text", "tip"}]`
- `talents`: `[(name, tip)]`
- `record`: `[(text, color, font_key)]`
- `rows` (roles): `[{"key", "title", "sub", "badge": (text, color)|None, "action": (label, enabled, primary)|None, "tip", "lit"}]`
"""

import pygame

from .primitives import (
    caps,
    draw_button,
    ellipsize,
    section,
    text,
    token_badge,
    tracked,
    wrap,
)
from .tokens import T

AMBER = (224, 149, 75)
ROW_H = T.S * 6
CHIP_GAP = T.S


def _box(surf, rect, mpos, lit=False):
    pygame.draw.rect(surf, T.TABLE, rect)
    pygame.draw.rect(surf, T.BRASS if (lit or rect.collidepoint(mpos)) else T.STEEL_LINE, rect, 1)


PORTRAIT_R = T.S * 8


def draw_identity(surf, F, x, y, w, d, mpos):
    token_badge(surf, F, (x + PORTRAIT_R, y + PORTRAIT_R), d["token"], r=PORTRAIT_R)
    tx = x + PORTRAIT_R * 2 + T.S * 2
    tw = w - (tx - x)
    text(surf, F["titleb"], ellipsize(d["name"], F["titleb"], tw), (tx, y + T.S), T.TX)
    text(surf, F["body"], ellipsize(d["sub"], F["body"], tw), (tx, y + T.S * 5), T.TX_MUTED)
    loc = pygame.Rect(tx, y + PORTRAIT_R * 2 - T.S * 5, min(tw, T.S * 26), T.S * 5)
    pygame.draw.rect(surf, T.STEEL, loc)
    pygame.draw.rect(surf, T.STEEL_LINE, loc, 1)
    caps(surf, F["micro"], "LOCATION", (loc.x + T.S, loc.y + T.S - 2), T.TX_FAINT)
    caps(surf, F["microb"], ellipsize(f"{d['where']} · {d['task']}".upper(), F["microb"], loc.w - T.S * 2),
         (loc.x + T.S, loc.y + T.S * 3 - 2), T.TX)
    return y + PORTRAIT_R * 2 + T.S * 2, None


def format_breakdown(F, title, terms, total):
    """Tooltip lines for a stat's calculation: `terms` is `[(label, value)]`
    (the first is the base), `total` the resulting number, already formatted."""
    lines = [(title, F["microb"], T.BRASS)]
    for i, (label, v) in enumerate(terms):
        col = T.TX_MUTED if i == 0 else T.GREEN if v > 0 else T.BLOOD
        lines.append((f"{label}: {v}" if i == 0 else f"{label}: {v:+}", F["body_sm"], col))
    lines.append((f"= {total}", F["bodyb"], T.BRASS))
    return lines


def _stat_chip(surf, F, rect, label, value, color, mpos, tip, big=True):
    _box(surf, rect, mpos)
    caps(surf, F["micro"], label, (rect.centerx, rect.y + T.S - 2), T.TX_FAINT, center=True)
    text(surf, F["head"] if big else F["bodyb"], value, (rect.centerx, rect.y + T.S * 3), color, center=True)
    return tip if rect.collidepoint(mpos) else None


def draw_vitals(surf, F, x, y, w, d, mpos):
    tip = None
    cur, mx = d["hp"]
    hp_col = T.GREEN if cur >= mx else (T.BLOOD if cur <= mx // 2 else T.BRASS)
    cells = [("HP", f"{cur}/{mx}", hp_col, d["hp_tip"])]
    cells += [(label, str(v), T.TX, t) for label, v, t in d["stats"]]
    cw = (w - (len(cells) - 1) * CHIP_GAP) // len(cells)
    for i, (label, val, col, t) in enumerate(cells):
        tip = _stat_chip(surf, F, pygame.Rect(x + i * (cw + CHIP_GAP), y, cw, T.S * 6), label, val, col, mpos, t) or tip
    y += T.S * 6 + CHIP_GAP

    attrs = d["attrs"]
    aw = (w - (len(attrs) - 1) * CHIP_GAP) // len(attrs)
    for i, (label, val, mod, pen) in enumerate(attrs):
        r = pygame.Rect(x + i * (aw + CHIP_GAP), y, aw, T.S * 8)
        _box(surf, r, mpos)
        caps(surf, F["microb"], label, (r.centerx, r.y + T.S - 2), T.TX_FAINT, center=True)
        text(surf, F["head"], str(val), (r.centerx, r.y + T.S * 3 - 2), T.BLOOD if pen else T.TX, center=True)
        mcol = T.GREEN if mod > 0 else T.BLOOD if mod < 0 else T.TX_FAINT
        text(surf, F["micro"], f"{mod:+}", (r.centerx, r.y + T.S * 5 + 4), mcol, center=True)
        if r.collidepoint(mpos):
            tip = f"{label}: {val} (modifier {mod:+})" + (" -- lowered by hunger or load" if pen else "")
    return y + T.S * 8 + T.S, tip


def draw_weapon(surf, F, x, y, w, d, mpos):
    y = section(surf, F, "Weapon", x, y, w)
    box = pygame.Rect(x, y, w, T.S * 12)
    _box(surf, box, mpos)
    text(surf, F["bodyb"], ellipsize(d["name"], F["bodyb"], w // 2), (box.x + T.S * 1.5, box.y + T.S), T.TX)
    caps(surf, F["micro"], ellipsize(d["tags"], F["micro"], w // 2 - T.S * 2),
         (box.right - T.S * 1.5, box.y + T.S + 2), T.TX_MUTED, right=True)
    tip = None
    n = len(d["chips"])
    pad = T.S * 1.5
    cw = int((box.w - 2 * pad - (n - 1) * CHIP_GAP) // n)
    for i, (label, value, t) in enumerate(d["chips"]):
        r = pygame.Rect(int(box.x + pad + i * (cw + CHIP_GAP)), box.y + T.S * 4, cw, T.S * 6)
        pygame.draw.rect(surf, T.STEEL, r)
        pygame.draw.rect(surf, T.BRASS if r.collidepoint(mpos) else T.STEEL_LINE, r, 1)
        caps(surf, F["micro"], label, (r.x + T.S, r.y + 5), T.TX_FAINT)
        text(surf, F["bodyb"], value, (r.x + T.S, r.y + T.S * 3 - 1), T.TX)
        if r.collidepoint(mpos):
            tip = t
    return box.bottom + T.S * 2, tip


def draw_gear(surf, F, x, y, w, d, mpos):
    y = section(surf, F, "Equipment & load", x, y, w)
    box = pygame.Rect(x, y, w, T.S * 11)
    _box(surf, box, mpos)
    half = w // 2
    pad = T.S * 1.5
    for col, (label, val, note) in enumerate([("HANDS", d["hands"], ""), ("ARMOR", d["armor"], d["armor_note"])]):
        cx = int(box.x + pad + col * half)
        caps(surf, F["micro"], label, (cx, box.y + T.S - 2), T.TX_FAINT)
        vr = text(surf, F["body"], ellipsize(val, F["body"], half - T.S * 3), (cx, box.y + T.S + 12), T.TX)
        if note:
            text(surf, F["body_sm"], ellipsize(note, F["body_sm"], cx + half - T.S * 2 - vr.right - T.S),
                 (vr.right + T.S, box.y + T.S + 13), T.TX_MUTED)
    n, ok = d["rations"]
    caps(surf, F["micro"], "COINS", (box.x + pad, box.y + T.S * 6 - 2), T.TX_FAINT)
    text(surf, F["body"], f"{d['coins']} copper", (box.x + pad, box.y + T.S * 6 + 12), T.BRASS)
    caps(surf, F["micro"], "RATIONS", (box.x + pad + half, box.y + T.S * 6 - 2), T.TX_FAINT)
    text(surf, F["body"], f"{n} in pack", (box.x + pad + half, box.y + T.S * 6 + 12),
         T.GREEN if n > 0 else (T.TX_MUTED if ok else T.BLOOD))
    y = box.bottom + T.S

    cur, norm, mx = d["load"]
    state, scol = d["load_state"]
    caps(surf, F["micro"], f"Cargo {cur:g} / {norm:g} kg", (x, y), T.TX)
    caps(surf, F["microb"], state, (x + w, y), scol, right=True)
    y += T.S * 2
    bar = pygame.Rect(x, y, w, T.S + 2)
    pygame.draw.rect(surf, T.TABLE, bar)
    pygame.draw.rect(surf, T.STEEL_LINE, bar, 1)
    fill = int((bar.w - 2) * min(1.0, cur / mx)) if mx else 0
    if fill:
        pygame.draw.rect(surf, scol, (bar.x + 1, bar.y + 1, fill, bar.h - 2))
    tick = bar.x + int((bar.w - 2) * min(1.0, norm / mx)) if mx else bar.x
    pygame.draw.line(surf, T.TX, (tick, bar.y - 2), (tick, bar.bottom + 1), 2)
    y = bar.bottom + 4
    left = caps(surf, F["micro"], "0", (x, y), T.TX_FAINT)
    right = caps(surf, F["micro"], f"Max {mx:g} kg", (x + w, y), T.TX_FAINT, right=True)
    lab = f"Normal limit {norm:g} kg"
    lw = F["micro"].size(lab.upper())[0]
    lx = max(left.right + T.S, min(tick - lw // 2, right.x - T.S - lw))
    caps(surf, F["micro"], lab, (lx, y), T.TX_MUTED)
    return y + T.S * 3, None


def draw_ability(surf, F, x, y, w, d, mpos):
    y = section(surf, F, "Racial trait", x, y, w)
    name, desc = d["ability"]
    lines = wrap(F["body_sm"], desc, w - T.S * 3)
    box = pygame.Rect(x, y, w, T.S * 4 + len(lines) * 16)
    _box(surf, box, mpos)
    text(surf, F["bodyb"], name, (box.x + T.S * 1.5, box.y + T.S), T.TX)
    ty = box.y + T.S * 3
    for ln in lines:
        text(surf, F["body_sm"], ln, (box.x + T.S * 1.5, ty), T.TX_MUTED)
        ty += 16
    y = box.bottom + T.S
    caps(surf, F["micro"], "Languages", (x, y + 1), T.TX_FAINT)
    text(surf, F["body_sm"], ", ".join(d["langs"]) or "none", (x + T.S * 10, y), T.TX_MUTED)
    return y + T.S * 3, None


def draw_tracks(surf, F, x, y, w, tracks, mpos):
    y = section(surf, F, "Progression", x, y, w)
    tip = None
    for t in tracks:
        top = y
        tracked(surf, F["microb"], t["label"].upper(), (x, y), T.BRASS)
        text(surf, F["micro"], t["value"], (x + w, y), T.TX, right=True)
        y += T.S * 2
        bar = pygame.Rect(x, y, w, 6)
        pygame.draw.rect(surf, T.TABLE, bar)
        pygame.draw.rect(surf, T.STEEL_LINE, bar, 1)
        if t["frac"]:
            pygame.draw.rect(surf, T.BRASS, (bar.x + 1, bar.y + 1, int((bar.w - 2) * min(1.0, t["frac"])), bar.h - 2))
        y += T.S + 6
        for ln in wrap(F["body_sm"], t["text"], w):
            text(surf, F["body_sm"], ln, (x, y), T.TX_MUTED)
            y += 16
        if pygame.Rect(x, top, w, y - top).collidepoint(mpos):
            tip = t["tip"]
        y += T.S * 2
    return y, tip


def draw_talents(surf, F, x, y, w, talents, mpos):
    y = section(surf, F, "Talents & traits", x, y, w)
    if not talents:
        text(surf, F["body_sm"], "No talents yet -- level up to unlock picks.", (x, y), T.TX_FAINT)
        return y + T.S * 3, None
    tip, tx = None, x
    for name, t in talents:
        tw = F["microb"].size(name.upper())[0] + T.S * 2
        if tx + tw > x + w:
            tx, y = x, y + T.S * 3
        r = pygame.Rect(tx, y, tw, T.S * 2 + 4)
        hov = r.collidepoint(mpos)
        _box(surf, r, mpos)
        caps(surf, F["microb"], name, r.center, T.BRASS if hov else T.TX, center=True)
        if hov:
            tip = t
        tx += tw + 6
    return y + T.S * 4, tip


def draw_role_rows(surf, F, x, y, w, rows, mpos):
    """Returns `(y, tip, hits)`; `hits` is `[(key, rect)]` for each enabled action."""
    y = section(surf, F, "Roles & logistics", x, y, w)
    tip, hits = None, []
    for row in rows:
        r = pygame.Rect(x, y, w, ROW_H)
        pygame.draw.rect(surf, T.STEEL, r)
        pygame.draw.rect(surf, T.BRASS if row.get("lit") else T.STEEL_LINE, r, 1)
        text(surf, F["bodyb"], row["title"], (r.x + T.S * 1.5, r.y + T.S), T.BRASS if row.get("lit") else T.TX)
        act_w = T.S * 20 if row["action"] else 0
        text(surf, F["body_sm"], ellipsize(row["sub"], F["body_sm"], w - T.S * 3 - act_w - (T.S * 2 if act_w else 0)),
             (r.x + T.S * 1.5, r.y + T.S * 3 + 2), T.TX_MUTED)
        if row["badge"]:
            caps(surf, F["microb"], row["badge"][0], (r.right - T.S * 1.5, r.centery - 6), row["badge"][1], right=True)
        if row["action"]:
            label, enabled, primary = row["action"]
            btn = pygame.Rect(r.right - T.S - act_w, r.y + T.S, act_w, ROW_H - T.S * 2)
            draw_button(surf, F, btn, label, primary=primary, enabled=enabled, mpos=mpos)
            if enabled:
                hits.append((row["key"], btn))
        if r.collidepoint(mpos):
            tip = row["tip"]
        y += ROW_H + 4
    return y + 4, tip, hits


def draw_record(surf, F, x, y, w, lines, mpos):
    y = section(surf, F, "Personal record", x, y, w)
    for s, col, font in lines:
        for ln in wrap(F[font], s, w):
            text(surf, F[font], ln, (x, y), col)
            y += 16
    return y + T.S, None

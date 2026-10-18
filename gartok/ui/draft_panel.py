"""The founding draft's pieces: a pool of candidates to pick from, the squad rail
and the commission modal.

    pool_card_height()
    draw_pool_card(surf, F, rect, card, mpos)            -> tooltip or None
    draw_squad_rail(surf, F, rect, slots, mpos)          -> tooltip or None
    draw_commission_modal(surf, F, items, picked, tokens, mpos)
        -> {"modal", "items": [(rect, key, can_toggle)], "cancel", "confirm", "tooltip"}
    draw_identity_form(surf, F, rect, form, mpos)
        -> {"name", "colors": [(rect, color)], "icons": [(rect, slug)], "leaders": [(rect, index)],
            "unit_names": [(rect, index)], "continue", "tooltip"}
    draw_shield(surf, center_x, top, h, color, icon)

Data is plain dicts. A `card` is
    {"ch": the `sheet_card.unit_to_ch` dict, "tags": [(label, style, desc, starred)],
     "selected": bool, "order": 1-based pick number or None, "targeting": bool}
(`targeting`: a commission is waiting for a card to replace). A rail `slot` is None
for an empty seat or {"ch": ..., "attrs": [(abbr, value)]}. Modal `items` are
{"key", "label", "desc", "style", "can_toggle", "note"}. The identity `form` is
    {"name": str, "name_set": bool, "editing": bool, "color": rgb, "icon": slug, "colors": [rgb],
     "icons": [slug], "leaders": [{"ch": ..., "selected": bool, "recruits": (n, "base 1 · CHA +2")}],
     "can_continue": bool, "editing_unit_idx": int | None, "unit_name_buf": str}.
"""

import pygame

from .. import artwork, data
from .primitives import (
    caps,
    contained,
    draw_button,
    ellipsize,
    format_tooltip,
    hline,
    modal_card,
    panel,
    smooth_circle,
    text,
    token_badge,
    tracked,
)
from .sheet_card import draw_sheet, sheet_height
from .tokens import ARCHETYPE_COLORS, T, mix

SHEET_BLOCKS = ("vitals", "attributes", "weapon")
PORTRAIT_R = T.S * 4
_TAG_H = 16
_FOOT_H = T.S * 2
_RAIL_LABEL_H = 16


def pool_card_height():
    return (T.S * 2 + PORTRAIT_R * 2 + T.S + sheet_height("compact", SHEET_BLOCKS)
            + T.S + _FOOT_H + T.S)


def draw_pool_card(surf, F, rect, card, mpos):
    tip = None
    pad = T.S * 2
    selected, targeting = card["selected"], card["targeting"]
    hover = rect.collidepoint(mpos)
    panel(surf, rect, hover=hover or selected, width=2 if (hover or selected) else 1)
    if selected:
        pygame.draw.rect(surf, T.GREEN, rect, 2)
    elif targeting and hover:
        pygame.draw.rect(surf, T.BLOOD, rect, 2)

    with contained(surf, rect):
        ch = card["ch"]
        token_badge(surf, F, (rect.x + pad + PORTRAIT_R, rect.y + pad + PORTRAIT_R), ch["unit"],
                    r=PORTRAIT_R)
        left = rect.x + pad + PORTRAIT_R * 2 + T.S * 2
        tx, ty = left, rect.y + pad
        for label, style, desc, starred in card["tags"][:3]:
            tcol = ARCHETYPE_COLORS.get(style, T.TX_MUTED)
            shown = f"★ {label}" if starred else label
            w = F["microb"].size(shown)[0] + 12
            if tx + w > rect.right - pad - T.S * 5:
                break
            pill = pygame.Rect(tx, ty, w, _TAG_H)
            pygame.draw.rect(surf, mix(T.STEEL_HI, T.BRASS, 0.25) if starred else T.STEEL_HI,
                             pill, border_radius=4)
            pygame.draw.rect(surf, T.BRASS if starred else tcol, pill, 2 if starred else 1,
                             border_radius=4)
            text(surf, F["microb"], shown, pill.center, T.BRASS if starred else tcol, center=True)
            if pill.collidepoint(mpos):
                tip = format_tooltip(label + (" (COMMISSIONED)" if starred else ""), desc, F)
            tx += w + T.S

        if card["order"]:
            token_pos = (rect.right - pad - T.S * 2, ty + _TAG_H // 2)
            pygame.draw.circle(surf, T.GREEN, token_pos, T.S * 2 - 2)
            text(surf, F["bodyb"], str(card["order"]), token_pos, T.TABLE, center=True)

        ty += _TAG_H + T.S
        draw_sheet(surf, F, pygame.Rect(left, ty, rect.right - pad - left, T.S * 5), ch,
                   density="compact", only=("identity",), mouse=mpos)

        ty = rect.y + pad + PORTRAIT_R * 2 + T.S
        sh = sheet_height("compact", SHEET_BLOCKS)
        _used, sheet_tip = draw_sheet(surf, F, pygame.Rect(rect.x + pad, ty, rect.w - 2 * pad, sh),
                                      card["ch"], density="compact", only=SHEET_BLOCKS, mouse=mpos)
        tip = sheet_tip or tip

        ty += sh + T.S
        line = f"{ch['ability'][0]}  ·  {', '.join(ch['langs']) or 'no languages'}"
        text(surf, F["body_sm"], ellipsize(line, F["body_sm"], rect.w - 2 * pad),
             (rect.x + pad, ty), T.TX_MUTED)
        if pygame.Rect(rect.x + pad, ty, rect.w - 2 * pad, 16).collidepoint(mpos):
            tip = format_tooltip(ch["ability"][0], ch["ability"][1], F)
    return tip


def draw_squad_rail(surf, F, rect, slots, mpos):
    tip = None
    tracked(surf, F["microb"], "YOUR SQUAD", (rect.x, rect.y), T.TX_FAINT)
    gap = T.S * 2
    y = rect.y + _RAIL_LABEL_H
    h = rect.h - _RAIL_LABEL_H
    w = (rect.w - gap * (len(slots) - 1)) // len(slots)
    for i, slot in enumerate(slots):
        r = pygame.Rect(rect.x + i * (w + gap), y, w, h)
        if slot is None:
            pygame.draw.rect(surf, T.STEEL_LINE, r, 1)
            text(surf, F["body_sm"], f"slot {i + 1}", r.center, T.TX_FAINT, center=True)
            continue
        ch = slot["ch"]
        panel(surf, r)
        pygame.draw.rect(surf, T.GREEN, r, 1)
        dot = (r.x + T.S * 3 + 9, r.centery)
        token_badge(surf, F, dot, ch["unit"], r=12)
        nx = dot[0] + 20
        text(surf, F["bodyb"], ellipsize(ch["name"], F["bodyb"], r.right - nx - T.S),
             (nx, r.y + T.S), T.TX)
        text(surf, F["body_sm"],
             ellipsize(f"{ch['race']}  ·  {ch['occ']}", F["body_sm"], r.right - nx - T.S),
             (nx, r.y + T.S + 18), T.TX_MUTED)
        ax = nx
        for abbr, value in slot["attrs"]:
            txt = f"{abbr} {value}"
            tw = F["body_sm"].size(txt)[0]
            if ax + tw > r.right - T.S:
                break
            text(surf, F["body_sm"], txt, (ax, r.y + T.S + 36), T.TX_MUTED)
            if pygame.Rect(ax, r.y + T.S + 36, tw, 16).collidepoint(mpos) \
                    and abbr in data.ATTRIBUTE_HELP:
                t, d = data.ATTRIBUTE_HELP[abbr]
                tip = format_tooltip(t, d, F)
            ax += tw + 8
    return tip


def draw_commission_modal(surf, F, items, picked, tokens, mpos):
    cols = 3
    rows = (len(items) + cols - 1) // cols
    gap = T.S
    cw = max(T.S * 20, min(T.S * 30, (surf.get_width() - T.S * 12) // cols - gap))
    ch = T.S * 7
    pw = cols * cw + (cols - 1) * gap + T.S * 6
    ph = rows * ch + (rows - 1) * gap + T.S * 18
    panel_r = modal_card(surf, (pw, ph), veil=True)

    text(surf, F["titleb"], "COMMISSION RECRUITS", (panel_r.x + T.S * 3, panel_r.y + T.S * 2), T.TX)
    noun = "token" if tokens == 1 else "tokens"
    text(surf, F["body_sm"],
         f"Call the archetypes the pool is missing, then pick the candidate to replace. "
         f"{tokens} {noun} left.",
         (panel_r.x + T.S * 3, panel_r.y + T.S * 5 + 4), T.TX_MUTED)

    tip = None
    item_rects = []
    for i, it in enumerate(items):
        r = pygame.Rect(panel_r.x + T.S * 3 + (i % cols) * (cw + gap),
                        panel_r.y + T.S * 9 + (i // cols) * (ch + gap), cw, ch)
        on, can = it["key"] in picked, it["can_toggle"]
        hover = r.collidepoint(mpos) and can
        if on:
            pygame.draw.rect(surf, T.STEEL_HI, r)
            pygame.draw.rect(surf, T.BRASS, r, 2)
        elif can:
            pygame.draw.rect(surf, T.STEEL_HI if hover else T.STEEL, r)
            pygame.draw.rect(surf, T.BRASS if hover else T.STEEL_LINE, r, 1)
        else:
            pygame.draw.rect(surf, T.TABLE, r)
            pygame.draw.rect(surf, T.STEEL_LINE, r, 1)
        col = ARCHETYPE_COLORS.get(it["style"], T.TX_MUTED)
        caps(surf, F["microb"], ("[✓] " if on else "[ ] ") + it["label"],
             (r.x + T.S, r.y + T.S), T.BRASS if on else (col if can else T.TX_FAINT))
        text(surf, F["body_sm"], ellipsize(it["note"] or it["desc"], F["body_sm"], cw - T.S * 2),
             (r.x + T.S, r.y + T.S * 3 + 2), T.TX_MUTED if can else T.TX_FAINT)
        if r.collidepoint(mpos):
            tip = format_tooltip(it["label"] + (" [SELECTED]" if on else ""), it["desc"], F)
        item_rects.append((r, it["key"], can))

    fy = panel_r.bottom - T.S * 6
    cost = len(picked)
    text(surf, F["body"], f"Cost: {cost} of {tokens} tokens",
         (panel_r.x + T.S * 3, fy + T.S), T.BRASS if cost else T.TX_MUTED)
    confirm = pygame.Rect(panel_r.right - T.S * 3 - T.S * 18, fy, T.S * 18, T.S * 4)
    cancel = pygame.Rect(confirm.x - T.S - T.S * 12, fy, T.S * 12, T.S * 4)
    draw_button(surf, F, cancel, "CANCEL", ghost=True, mpos=mpos)
    draw_button(surf, F, confirm, f"CONFIRM ({cost})" if cost else "CONFIRM", primary=True,
                enabled=1 <= cost <= tokens, mpos=mpos)
    return {"modal": panel_r, "items": item_rects, "cancel": cancel, "confirm": confirm,
            "tooltip": tip}


_SWATCH_MAX = 40
_EMBLEM_MAX = 48
_FOOT = T.S * 10
_PORTRAIT_R_MAX = T.S * 20


def _shield_points(cx, top, w, h):
    """A heater shield: flat top, straight sides for half its height, curving to a point."""
    x0, x1 = cx - w / 2, cx + w / 2
    mid = top + h * 0.5
    pts = [(x0, top), (x1, top), (x1, mid)]
    for k in range(1, 9):
        t = k / 8
        pts.append((x1 - (w / 2) * t ** 1.6, mid + (h * 0.5) * t))
    for k in range(7, 0, -1):
        t = k / 8
        pts.append((x0 + (w / 2) * t ** 1.6, mid + (h * 0.5) * t))
    pts.append((x0, mid))
    return pts


def draw_shield(surf, center_x, top, h, color, icon):
    """The guild's banner on a shield: the colour quartered with dark, the emblem on an inner shield."""
    w = int(h * 0.82)
    outer = _shield_points(center_x, top, w, h)
    pygame.draw.polygon(surf, color, outer)
    dark = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    pygame.draw.polygon(dark, mix(color, T.TABLE, 0.78), [(px - center_x + w / 2, py - top) for px, py in outer])
    half_w, half_h = w // 2 + 1, h // 2 + 1
    surf.blit(dark, (center_x, top), area=pygame.Rect(w // 2, 0, half_w, half_h))
    surf.blit(dark, (center_x - w // 2, top + h // 2), area=pygame.Rect(0, h // 2, half_w, half_h + 1))
    inner_h = int(h * 0.62)
    inner_top = top + (h - inner_h) // 3
    inner = _shield_points(center_x, inner_top, int(inner_h * 0.82), inner_h)
    pygame.draw.polygon(surf, T.TABLE, inner)
    pygame.draw.polygon(surf, mix(color, T.TABLE, 0.4), inner, 2)
    pygame.draw.polygon(surf, T.STEEL_LINE, outer, 3)
    art = artwork.banner_icon(icon, int(inner_h * 0.55), color)
    if art is not None:
        surf.blit(art, art.get_rect(center=(center_x, inner_top + inner_h * 0.44)))


def _identity_column(surf, F, rect, form, mpos, out):
    pad = T.S * 3
    x, w = rect.x + pad, rect.w - 2 * pad
    panel(surf, rect)
    shield_h = max(T.S * 8, min(T.S * 24, rect.h - 2 * pad - T.S * 40))
    draw_shield(surf, rect.centerx, rect.y + pad, shield_h, form["color"], form["icon"])
    y = rect.y + pad + shield_h + T.S * 3

    tracked(surf, F["microb"], "GUILD NAME", (x, y), T.TX_FAINT)
    name_r = pygame.Rect(x, y + 18, w, 40)
    out["name"] = name_r
    lit = name_r.collidepoint(mpos) or form["editing"]
    panel(surf, name_r, hover=lit, width=2 if lit else 1)
    shown = form["name"] + "|" if form["editing"] else form["name"] or "click to name your guild"
    text(surf, F["name"], ellipsize(shown, F["name"], w - T.S * 4),
         (name_r.x + T.S * 2, name_r.centery - F["name"].get_height() // 2),
         T.TX if (form["editing"] or form["name"]) else T.TX_FAINT)
    y = name_r.bottom + T.S * 3

    tracked(surf, F["microb"], "BANNER COLOUR", (x, y), T.TX_FAINT)
    y += 20
    n = len(form["colors"])
    gap = T.S
    sw = max(T.S * 3, min(_SWATCH_MAX, (w - (n - 1) * gap) // n))
    step = (w - sw) / max(1, n - 1)
    for i, color in enumerate(form["colors"]):
        r = pygame.Rect(round(x + i * step), y, sw, sw)
        sel = color == form["color"]
        smooth_circle(surf, color, r.center, sw // 2)
        smooth_circle(surf, T.BRASS if sel else (T.STEEL_LINE if r.collidepoint(mpos) else T.STEEL),
                      r.center, sw // 2, 3 if sel else 1)
        out["colors"].append((r, color))
    y += sw + T.S * 3

    tracked(surf, F["microb"], "EMBLEM", (x, y), T.TX_FAINT)
    y += 20
    icons = form["icons"]
    per_row = max(1, min(len(icons), (w + gap) // (T.S * 5 + gap)))
    rows = (len(icons) + per_row - 1) // per_row
    em = max(T.S * 3, min(_EMBLEM_MAX, (w - (per_row - 1) * gap) // per_row,
                          (rect.bottom - pad - y - (rows - 1) * gap) // rows))
    for i, slug in enumerate(icons):
        r = pygame.Rect(x + (i % per_row) * (em + gap), y + (i // per_row) * (em + gap), em, em)
        sel = slug == form["icon"]
        hover = r.collidepoint(mpos)
        panel(surf, r, hover=sel or hover, width=2 if sel else 1)
        if sel:
            pygame.draw.rect(surf, T.BRASS, r, 2)
        art = artwork.banner_icon(slug, em - T.S * 2, form["color"] if (sel or hover) else T.TX_MUTED)
        if art is not None:
            surf.blit(art, art.get_rect(center=r.center))
        out["icons"].append((r, slug))


_CARD_FIXED = 336         # everything on a leader card but its portrait: band, name, line, recruits, grid, languages


def _leader_card(surf, F, r, i, leader, form, mpos, out):
    ch, sel = leader["ch"], leader["selected"]
    panel(surf, r, hover=r.collidepoint(mpos) or sel, width=2 if sel else 1)
    band = pygame.Rect(r.x + 1, r.y + 1, r.w - 2, T.S * 3)
    pygame.draw.rect(surf, mix(T.BRASS, T.TABLE, 0.7) if sel else T.STEEL_HI, band)
    if sel:
        pygame.draw.rect(surf, T.BRASS, r, 2)
        caps(surf, F["microb"], "leader", (band.centerx, band.y + 5), T.BRASS, center=True)
    pad = T.S * 2
    x, w = r.x + pad, r.w - 2 * pad

    pr = max(T.S * 3, min(w // 2 - T.S, (r.h - _CARD_FIXED) // 2, _PORTRAIT_R_MAX))
    py = band.bottom + T.S * 2 + pr
    token_badge(surf, F, (r.centerx, py), ch["unit"], r=pr)
    pygame.draw.circle(surf, T.BRASS_DIM if sel else T.STEEL_LINE, (r.centerx, py), pr, 1)
    y = py + pr + T.S * 2

    if form.get("editing_unit_idx") == i:
        box = pygame.Rect(x, y, w - 40, 28)
        panel(surf, box, hover=True, width=2)
        text(surf, F["body"], ellipsize(form.get("unit_name_buf", "") + "|", F["body"], box.w - 8),
             (box.x + 4, box.centery - F["body"].get_height() // 2), T.BRASS)
        btn = pygame.Rect(box.right + 4, y + 2, 34, 24)
        draw_button(surf, F, btn, "OK", primary=True, fnt=F["microb"], mpos=mpos)
    else:
        ren_w = 56
        name = ellipsize(ch["name"], F["nameb"], w - ren_w - T.S)
        nw = F["nameb"].size(name)[0]
        nx = r.centerx - (nw + T.S + ren_w) // 2
        text(surf, F["nameb"], name, (nx, y + 4), T.TX)
        btn = pygame.Rect(nx + nw + T.S, y + 6, ren_w, 18)
        draw_button(surf, F, btn, "RENAME", ghost=True, fnt=F["micro"], mpos=mpos)
    out["unit_names"].append((btn, i))
    y += 30
    sub = ellipsize(f"{ch['align']} · {ch['race']} {ch['occ']}", F["body_sm"], w)
    text(surf, F["body_sm"], sub, (r.centerx, y), T.TX_MUTED, center=True)
    y += 20 + T.S

    rec, parts = leader["recruits"]
    box = pygame.Rect(x, y, w, 48)
    pygame.draw.rect(surf, mix(T.BRASS, T.TABLE, 0.15) if sel else mix(T.BRASS, T.TABLE, 0.82), box)
    pygame.draw.rect(surf, T.BRASS if sel else T.BRASS_DIM, box, 1)
    ink = T.TABLE if sel else T.BRASS
    caps(surf, F["microb"], ellipsize(f"can recruit: {rec}", F["microb"], w - T.S * 2),
         (box.centerx, box.y + 8), ink, center=True)
    text(surf, F["body_sm"], ellipsize(parts, F["body_sm"], w - T.S * 2), (box.centerx, box.y + 28),
         ink, center=True)
    y = box.bottom + T.S * 2

    cell_w, cell_h = (w - 2 * T.S) // 3, T.S * 6
    big = F["big"] if cell_w >= T.S * 8 else F["head"]
    for k, (abbr, value, mod, penalized) in enumerate(ch["attrs"]):
        c = pygame.Rect(x + (k % 3) * (cell_w + T.S), y + (k // 3) * (cell_h + T.S), cell_w, cell_h)
        pygame.draw.rect(surf, T.TABLE, c)
        pygame.draw.rect(surf, T.STEEL_LINE, c, 1)
        caps(surf, F["micro"], f"{abbr} {value}", (c.centerx, c.y + 4), T.TX_FAINT, center=True)
        col = T.BLOOD if mod < 0 or penalized else T.GREEN if mod > 0 else T.TX_MUTED
        text(surf, big, f"{mod:+d}", (c.centerx, c.bottom - big.get_height() // 2 - 4), col, center=True)
        if c.collidepoint(mpos) and abbr in data.ATTRIBUTE_HELP:
            out["tooltip"] = format_tooltip(*data.ATTRIBUTE_HELP[abbr], F)

    hline(surf, r.x + 1, r.right - 1, r.bottom - T.S * 4 - 2)
    langs = ", ".join(ch["langs"]) or "none"
    text(surf, F["body_sm"], ellipsize(f"Languages: {langs}", F["body_sm"], w),
         (r.centerx, r.bottom - T.S * 2 - 2), T.TX_MUTED, center=True)


def draw_identity_form(surf, F, rect, form, mpos):
    """The guild's identity (shield, name, colour, emblem) on the left, the leader cards on the
    right, FOUND THE GUILD at the foot. Every size comes from `rect`."""
    out = {"colors": [], "icons": [], "leaders": [], "unit_names": [], "tooltip": None}
    m = T.S * 4 if rect.w >= 1200 else T.S * 2
    text(surf, F["titleb"], "FOUND THE GUILD", (rect.x + m, rect.y + T.S * 3), T.TX)
    text(surf, F["body"], "Name your guild, pick a banner, and choose your leader.",
         (rect.x + m, rect.y + T.S * 3 + 32), T.TX_MUTED)
    top = rect.y + T.S * 3 + 64
    avail = pygame.Rect(rect.x + m, top + 22, rect.w - 2 * m, rect.bottom - _FOOT - top - 22)
    left_w = max(T.S * 32, min(T.S * 56, int(avail.w * 0.34)))
    right_w = avail.w - left_w - T.S * 3
    leaders = form["leaders"]
    n = max(1, len(leaders))
    gap = T.S * 2
    cw = (right_w - (n - 1) * gap) // n
    natural = _CARD_FIXED + 2 * min(cw // 2 - T.S * 3, _PORTRAIT_R_MAX)
    body_h = min(avail.h, max(natural, T.S * 66))
    body = pygame.Rect(avail.x, avail.y + (avail.h - body_h) // 2, avail.w, body_h)

    left = pygame.Rect(body.x, body.y, left_w, body.h)
    right = pygame.Rect(left.right + T.S * 3, body.y, right_w, body.h)
    tracked(surf, F["microb"], "GUILD IDENTITY", (left.x, body.y - 22), T.TX_FAINT)
    tracked(surf, F["microb"], "CHOOSE YOUR GUILD LEADER", (right.x, body.y - 22), T.TX_FAINT)
    _identity_column(surf, F, left, form, mpos, out)

    for i, leader in enumerate(leaders):
        r = pygame.Rect(right.x + i * (cw + gap), right.y, cw, right.h)
        _leader_card(surf, F, r, i, leader, form, mpos, out)
        out["leaders"].append((r, i))

    foot_y = rect.bottom - _FOOT + T.S
    hline(surf, rect.x + m, rect.right - m, foot_y)
    out["continue"] = pygame.Rect(rect.right - m - T.S * 28, foot_y + T.S * 2, T.S * 28, T.S * 5)
    draw_button(surf, F, out["continue"], "FOUND THE GUILD", primary=True,
                enabled=form["can_continue"], mpos=mpos)
    return out

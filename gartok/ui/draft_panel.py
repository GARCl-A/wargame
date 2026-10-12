"""The founding draft's pieces: a pool of candidates to pick from, the squad rail
and the commission modal.

    pool_card_height()
    draw_pool_card(surf, F, rect, card, mpos)            -> tooltip or None
    draw_squad_rail(surf, F, rect, slots, mpos)          -> tooltip or None
    draw_commission_modal(surf, F, items, picked, tokens, mpos)
        -> {"modal", "items": [(rect, key, can_toggle)], "cancel", "confirm", "tooltip"}
    draw_identity_form(surf, F, rect, form, mpos)
        -> {"name", "colors": [(rect, color)], "icons": [(rect, slug)], "leaders": [(rect, index)],
            "continue", "tooltip"}

Data is plain dicts. A `card` is
    {"ch": the `sheet_card.unit_to_ch` dict, "tags": [(label, style, desc, starred)],
     "selected": bool, "order": 1-based pick number or None, "targeting": bool}
(`targeting`: a commission is waiting for a card to replace). A rail `slot` is None
for an empty seat or {"ch": ..., "attrs": [(abbr, value)]}. Modal `items` are
{"key", "label", "desc", "style", "can_toggle", "note"}. The identity `form` is
    {"name": str, "name_set": bool, "editing": bool, "color": rgb, "icon": slug, "colors": [rgb],
     "icons": [slug], "leaders": [{"ch": ..., "selected": bool}], "can_continue": bool}.
"""

import pygame

from .. import artwork, data
from .primitives import (
    TOKEN_INK,
    caps,
    contained,
    draw_button,
    ellipsize,
    format_tooltip,
    modal_card,
    panel,
    smooth_circle,
    text,
    token_badge,
    tracked,
)
from .sheet_card import draw_row, draw_sheet, sheet_height
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


_NAME_W_MAX = 560
_SWATCH = 40
_EMBLEM = 44
_LEADER_H = 74


def draw_identity_form(surf, F, rect, form, mpos):
    """The guild's name, banner colour and emblem, then who leads it. Centred in `rect`."""
    cw = min(_NAME_W_MAX, rect.w - 2 * T.S * 4)
    cx = rect.x + (rect.w - cw) // 2
    out = {"colors": [], "icons": [], "leaders": [], "tooltip": None}

    text(surf, F["titleb"], "FOUND THE GUILD", (cx, rect.y + T.S * 4 - 2), T.TX)
    text(surf, F["body"], "Name your guild, pick a banner, and choose your leader.",
         (cx, rect.y + T.S * 4 + 30), T.TX_MUTED)
    y = rect.y + T.S * 4 + 74

    pv = (cx + 24, y + 28)
    smooth_circle(surf, form["color"], pv, 24)
    art = artwork.banner_icon(form["icon"], 32, TOKEN_INK)
    if art is not None:
        surf.blit(art, art.get_rect(center=pv))

    nx, nw = cx + 64, cw - 64
    tracked(surf, F["microb"], "GUILD NAME", (nx, y), T.TX_FAINT)
    name_r = pygame.Rect(nx, y + 16, nw, 40)
    out["name"] = name_r
    lit = name_r.collidepoint(mpos) or form["editing"]
    panel(surf, name_r, hover=lit, width=2 if lit else 1)
    shown = form["name"] + "|" if form["editing"] else form["name"] or "click to name your guild"
    text(surf, F["body"], shown, (name_r.x + T.S * 2, name_r.centery - F["body"].get_height() // 2),
         T.TX if (form["editing"] or form["name"]) else T.TX_FAINT)
    y += 56 + T.S * 3

    tracked(surf, F["microb"], "BANNER COLOUR", (cx, y), T.TX_FAINT)
    y += 18
    for i, color in enumerate(form["colors"]):
        r = pygame.Rect(cx + i * (_SWATCH + T.S * 2), y, _SWATCH, _SWATCH)
        sel = color == form["color"]
        smooth_circle(surf, color, r.center, _SWATCH // 2)
        smooth_circle(surf, T.BRASS if sel else (T.STEEL_LINE if r.collidepoint(mpos) else T.STEEL),
                      r.center, _SWATCH // 2, 3 if sel else 1)
        out["colors"].append((r, color))
    y += _SWATCH + T.S * 3

    tracked(surf, F["microb"], "EMBLEM", (cx, y), T.TX_FAINT)
    y += 18
    per_row = max(1, (cw + T.S * 2) // (_EMBLEM + T.S * 2))
    for i, slug in enumerate(form["icons"]):
        r = pygame.Rect(cx + (i % per_row) * (_EMBLEM + T.S * 2),
                        y + (i // per_row) * (_EMBLEM + T.S * 2), _EMBLEM, _EMBLEM)
        sel = slug == form["icon"]
        panel(surf, r, hover=sel or r.collidepoint(mpos), width=2 if sel else 1)
        smooth_circle(surf, form["color"], r.center, 14)
        art = artwork.banner_icon(slug, _EMBLEM - 16, TOKEN_INK)
        if art is not None:
            surf.blit(art, art.get_rect(center=r.center))
        out["icons"].append((r, slug))
    rows = (len(form["icons"]) + per_row - 1) // per_row
    y += rows * (_EMBLEM + T.S * 2) + T.S * 3

    tracked(surf, F["microb"], "WHO LEADS THE GUILD?", (cx, y), T.TX_FAINT)
    y += 18

    def attrs(surf, r, ch):
        x = r.right - 380
        for abbr, value, _mod, _penalized in ch["attrs"]:
            label = f"{abbr} {value}"
            w = F["body_sm"].size(label)[0]
            top = r.centery - F["body_sm"].get_height() // 2
            text(surf, F["body_sm"], label, (x, top), T.TX_MUTED)
            if pygame.Rect(x, top, w, F["body_sm"].get_height()).collidepoint(mpos) and abbr in data.ATTRIBUTE_HELP:
                out["tooltip"] = format_tooltip(*data.ATTRIBUTE_HELP[abbr], F)
            x += w + 20

    out["unit_names"] = []
    editing_idx = form.get("editing_unit_idx")
    unit_buf = form.get("unit_name_buf", "")

    for i, leader in enumerate(form["leaders"]):
        r = pygame.Rect(cx, y + i * (_LEADER_H + T.S * 2), cw, _LEADER_H)
        draw_row(surf, F, r, leader["ch"], selected=leader["selected"], draw_trailing=attrs)
        out["leaders"].append((r, i))

        if editing_idx == i:
            name_box = pygame.Rect(r.x + T.S * 6 - 2, r.centery - 16, 150, 24)
            panel(surf, name_box, hover=True, width=2)
            text(surf, F["body"], unit_buf + "|", (name_box.x + 4, name_box.centery - F["body"].get_height() // 2), T.BRASS)
            ok_btn = pygame.Rect(name_box.right + 4, r.centery - 12, 34, 20)
            draw_button(surf, F, ok_btn, "OK", primary=True, fnt=F["microb"], mpos=mpos)
            out["unit_names"].append((ok_btn, i))
        else:
            name_w = F["name"].size(leader["ch"]["name"])[0]
            ren_btn = pygame.Rect(r.x + T.S * 6 + name_w + 8, r.centery - 16, 52, 18)
            draw_button(surf, F, ren_btn, "RENAME", ghost=True, fnt=F["micro"], mpos=mpos)
            out["unit_names"].append((ren_btn, i))

    y += len(form["leaders"]) * (_LEADER_H + T.S * 2) + T.S * 4

    out["continue"] = pygame.Rect(cx + cw - 200, y, 200, 44)
    draw_button(surf, F, out["continue"], "FOUND THE GUILD", primary=True,
                enabled=form["can_continue"], mpos=mpos)
    return out

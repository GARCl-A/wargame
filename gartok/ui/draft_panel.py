"""The founding draft's pieces: a pool of candidates to pick from, the squad rail
and the commission modal.

    pool_card_height()
    draw_pool_card(surf, F, rect, card, mpos)            -> tooltip or None
    draw_squad_rail(surf, F, rect, slots, mpos)          -> tooltip or None
    draw_commission_modal(surf, F, items, picked, tokens, mpos)
        -> {"modal", "items": [(rect, key, can_toggle)], "cancel", "confirm", "tooltip"}

Data is plain dicts. A `card` is
    {"ch": the `sheet_card.unit_to_ch` dict, "tags": [(label, style, desc, starred)],
     "selected": bool, "order": 1-based pick number or None, "targeting": bool}
(`targeting`: a commission is waiting for a card to replace). A rail `slot` is None
for an empty seat or {"ch": ..., "attrs": [(abbr, value)]}. Modal `items` are
{"key", "label", "desc", "style", "can_toggle", "note"}.
"""

import pygame

from .. import data
from .primitives import (
    caps,
    contained,
    draw_button,
    ellipsize,
    format_tooltip,
    modal_card,
    panel,
    text,
    token_badge,
    tracked,
)
from .sheet_card import draw_sheet, sheet_height
from .tokens import ARCHETYPE_COLORS, T, mix

SHEET_BLOCKS = ("identity", "vitals", "attributes", "weapon")
_TAG_H = 16
_FOOT_H = T.S * 3
_RAIL_LABEL_H = 16


def pool_card_height():
    return (T.S * 2 + _TAG_H + T.S + sheet_height("compact", SHEET_BLOCKS)
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
        tx, ty = rect.x + pad, rect.y + pad
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
        sh = sheet_height("compact", SHEET_BLOCKS)
        _used, sheet_tip = draw_sheet(surf, F, pygame.Rect(rect.x + pad, ty, rect.w - 2 * pad, sh),
                                      card["ch"], density="compact", only=SHEET_BLOCKS, mouse=mpos)
        tip = sheet_tip or tip

        ty += sh + T.S
        ch = card["ch"]
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

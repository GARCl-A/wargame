"""The battle screen's chrome around the board: the INITIATIVE strip, the
side PANEL (title, turn / victory card, hint, action list, inspect header)
and the LOG well.

Every function takes the rect it owns and plain data; the ones with click
targets return `[(key, rect)]` where `key` is whatever opaque value the
caller put in the item (the screen uses its `Action` objects) or one of the
fixed string keys documented on the function.

Data shapes::

    init_entry = {"name": str, "team": "player" | "enemy", "known": bool,
                  "active": bool, "race": str, "portrait_id": str | None,
                  "token": str, "hp_frac": float, "dying": str | None}

    turn_card = {"name": str, "token": str, "mine": bool, "stats": str,
                 "ap": int, "ap_max": int,
                 "walk": (moved, speed) | None, "note": str | None}

    victory_card = {"won": bool, "stabilized": [str], "fallen": [str]}

    action_item = {"key": any, "label": str, "enabled": bool, "armed": bool,
                   "icon": str | None,          # icons.icon id
                   "cost": int, "cost_style": "pips" | "count",
                   "aim": "demo" | "throw" | "attack" | "spell" | None,
                   "center": bool}              # a plain centred menu entry
"""

import pygame

from .. import icons
from .board_render import draw_face, hp_bar, team_color
from .board_style import (
    DANGER,
    INK_FAINT,
    LOG_HURT,
    MOVE_HL,
    OK,
    WARN,
    aim_color,
)
from .primitives import TOKEN_INK, box, pips, scrollbar, text, tracked, wrap
from .tokens import T

TITLE_H = 30
TURN_CARD_H = 74
VICTORY_CARD_H = 84
HINT_H = 16
INSPECT_HEAD_H = 24
INSPECT_ARMED_H = 20
ACTION_H = 34
ACTION_GAP = T.S // 2
TAB_H = 26
BACK_H = 30
LOG_LINE_H = 17


# ---------------------------------------------------------------------- #
# initiative strip                                                       #
# ---------------------------------------------------------------------- #
def draw_initiative(surf, F, rect, entries):
    box(surf, rect, fill=T.STEEL)
    tracked(surf, F["micro"], "INITIATIVE", (rect.x + T.S, rect.y + T.S // 2), INK_FAINT)
    label_w = T.S * 11
    n = max(1, len(entries))
    cw = max(T.S * 3, min(T.S * 14, max(1, rect.w - label_w - T.S * 1.5) // n))
    cw = int(cw)
    x, y = rect.x + label_w, rect.y + 6
    for e in entries:
        _init_chip(surf, F, pygame.Rect(x, y, cw - T.S // 2, rect.h - 12), e)
        x += cw


def _init_chip(surf, F, r, e):
    active, known = e["active"], e["known"]
    box(surf, r, fill=T.STEEL_HI if active else T.TABLE,
        border=T.BRASS if active else T.STEEL_LINE, width=2 if active else 1)
    draw_face(surf, F, (r.x + 12, r.centery - 3), 8, e,
              fallback_color=team_color(e["team"]), known=known)
    clip = surf.get_clip()
    surf.set_clip(r.inflate(-6, -6))
    text(surf, F["body_sm"], e["name"], (r.x + 26, r.y + 4), T.TX if active else T.TX_MUTED)
    surf.set_clip(clip)
    if e["dying"]:
        text(surf, F["micro"], f"dying {e['dying']}", (r.x + 8, r.bottom - 14), DANGER)
    elif known:
        hp_bar(surf, pygame.Rect(r.x + 8, r.bottom - 9, r.w - 16, 4), e["hp_frac"])


# ---------------------------------------------------------------------- #
# panel header and cards                                                 #
# ---------------------------------------------------------------------- #
def draw_title(surf, F, rect, title, state, vision_on):
    """`state` is "victory", "mopping" or None and only picks the colour."""
    col = T.BRASS if state == "victory" else WARN if state == "mopping" else T.TX
    text(surf, F["titleb"], title, (rect.x, rect.y - 4), col)
    label = "ACTIVE" if vision_on else "SQUAD"
    text(surf, F["body_sm"], f"vision {label}  [L]", (rect.right, rect.y + 4),
         T.BRASS if vision_on else T.TX_MUTED, right=True)


def draw_turn_card(surf, F, card, data):
    mine = data["mine"]
    tcol = team_color("player" if mine else "enemy")
    box(surf, card, fill=T.TABLE, border=tcol, width=1)

    dot = (card.x + T.S * 2 + 11, card.y + 21)
    pygame.draw.circle(surf, tcol, dot, 13)
    text(surf, F["bodyb"], data["token"], dot, TOKEN_INK, center=True)
    text(surf, F["head"], data["name"], (dot[0] + 24, card.y + 7), T.TX)
    text(surf, F["micro"], data["stats"], (dot[0] + 24, card.y + 28), T.TX_MUTED)

    px = card.right - T.S * 2 - 19
    text(surf, F["micro"], "ACTION", (px + 4, card.y + 8), INK_FAINT, center=True)
    pips(surf, (px, card.y + 30), data["ap"], data["ap_max"], r=7, gap=8)

    base = card.y + 50
    if data["walk"] is not None:
        moved, speed = data["walk"]
        text(surf, F["micro"], f"walk {moved}/{speed}", (card.x + T.S * 2, base), T.TX_MUTED)
        track = pygame.Rect(card.x + T.S * 2 + 116, base + 4, card.w - T.S * 2 - 128, 5)
        pygame.draw.rect(surf, T.STEEL_HI, track, border_radius=2)
        frac = min(1.0, moved / max(1, speed))
        pygame.draw.rect(surf, MOVE_HL, pygame.Rect(track.x, track.y, int(track.w * frac), track.h),
                         border_radius=2)
    elif data["note"]:
        text(surf, F["micro"], data["note"], (card.x + T.S * 2, base), INK_FAINT)


def draw_victory_card(surf, F, card, data):
    won = data["won"]
    box(surf, card, fill=T.TABLE, border=T.BRASS if won else DANGER, width=1)
    x = card.x + T.S * 2
    text(surf, F["head"], "VICTORY" if won else "DEFEAT", (x, card.y + 6), T.BRASS if won else DANGER)

    stabilized, fallen = data["stabilized"], data["fallen"]
    if stabilized and fallen:
        text(surf, F["body_sm"], f"Stabilized: {', '.join(stabilized)}", (x, card.y + 26), OK)
        text(surf, F["body_sm"], f"Fallen: {', '.join(fallen)}", (x, card.y + 44), DANGER)
    elif stabilized:
        text(surf, F["body_sm"], f"Stabilized: {', '.join(stabilized)} (unconscious)",
             (x, card.y + 30), OK)
    elif fallen:
        text(surf, F["body_sm"], f"Fallen: {', '.join(fallen)}", (x, card.y + 30), DANGER)
    else:
        text(surf, F["body_sm"], "All squad members survived standing.", (x, card.y + 30), T.TX_MUTED)
    text(surf, F["micro"], "Click anywhere to continue", (x, card.y + 64), INK_FAINT)


def draw_hint(surf, F, rect, msg, color):
    if msg is not None:
        text(surf, F["body_sm"], msg, rect.topleft, color)


# ---------------------------------------------------------------------- #
# actions                                                                #
# ---------------------------------------------------------------------- #
def draw_height_prompt(surf, F, rect, options):
    """A pick-one list of `[(z, label)]` plus Cancel. Keys:
    `("prompt_height", z)` and `"prompt_cancel"`."""
    hits = []
    y = rect.y
    text(surf, F["bodyb"], "DISK ALTITUDE:", (rect.x, y), T.BRASS)
    y += 26 + T.S // 2
    for z, label in options:
        r = pygame.Rect(rect.x, y, rect.w, 32)
        box(surf, r, fill=T.TABLE, border=T.BRASS, width=1)
        text(surf, F["bodyb"], label, r.center, T.TX, center=True)
        hits.append((("prompt_height", z), r))
        y = r.bottom + T.S // 2
    r = pygame.Rect(rect.x, y, rect.w, 28)
    box(surf, r, fill=T.STEEL, border=T.STEEL_LINE, width=1)
    text(surf, F["body_sm"], "Cancel", r.center, T.TX_MUTED, center=True)
    hits.append(("prompt_cancel", r))
    return hits


def draw_action_tabs(surf, F, rect, active, show_blocked, mpos):
    """COMBAT / UTILITY tabs and the show-blocked toggle. Keys:
    `"tab_combat"`, `"tab_utility"`, `"toggle_blocked"`."""
    toggle_w = T.S * 4 - 2
    w = (rect.w - toggle_w - T.S) // 2
    combat = pygame.Rect(rect.x, rect.y, w, rect.h)
    utility = pygame.Rect(combat.right + 4, rect.y, w, rect.h)
    toggle = pygame.Rect(rect.right - toggle_w, rect.y, toggle_w, rect.h)
    hits = []
    for key, label, r in (("combat", "COMBAT", combat), ("utility", "UTILITY", utility)):
        on, hov = active == key, r.collidepoint(mpos)
        box(surf, r, fill=T.STEEL_HI if on else T.TABLE if hov else T.STEEL,
            border=T.BRASS if on else T.STEEL_LINE, width=1)
        text(surf, F["bodyb"], label, r.center,
             T.BRASS if on else T.TX if hov else T.TX_MUTED, center=True)
        hits.append((f"tab_{key}", r))
    box(surf, toggle, fill=T.TABLE if show_blocked else T.STEEL, border=T.STEEL_LINE, width=1)
    text(surf, F["micro"], "(o)" if show_blocked else "(-)", toggle.center, T.TX, center=True)
    hits.append(("toggle_blocked", toggle))
    return hits


def draw_back_bar(surf, F, rect, label):
    box(surf, rect, fill=T.STEEL, border=T.STEEL_LINE, width=1)
    text(surf, F["bodyb"], label, rect.center, T.TX, center=True)
    return rect


def draw_action_list(surf, F, rect, items, scroll):
    """A clipped, scrollable column of action buttons. Returns
    `{"buttons": [(key, rect)], "scroll": clamped, "max_scroll": int}` --
    only rows actually on screen get a button."""
    content_h = len(items) * (ACTION_H + ACTION_GAP)
    max_scroll = max(0, content_h - rect.h)
    scroll = max(0, min(scroll, max_scroll))
    bw = rect.w - (6 if max_scroll else 0)
    buttons = []
    clip = surf.get_clip()
    surf.set_clip(rect)
    y = rect.y - scroll
    for it in items:
        r = pygame.Rect(rect.x, y, bw, ACTION_H)
        y += ACTION_H + ACTION_GAP
        if r.bottom <= rect.top or r.top >= rect.bottom:
            continue
        _action_button(surf, F, r, it)
        buttons.append((it["key"], r))
    surf.set_clip(clip)
    if max_scroll:
        scrollbar(surf, rect, scroll, max_scroll, content_h)
    return {"buttons": buttons, "scroll": scroll, "max_scroll": max_scroll}


def _action_button(surf, F, r, it):
    enabled, armed = it["enabled"], it["armed"]
    if it.get("center"):
        box(surf, r, fill=T.TABLE if enabled else T.STEEL, border=T.STEEL_LINE, width=1)
        text(surf, F["bodyb"], it["label"], r.center, T.TX if enabled else INK_FAINT, center=True)
        return
    arm_c = aim_color(it.get("aim"))
    box(surf, r, fill=arm_c if armed else T.TABLE if enabled else T.STEEL,
        border=arm_c if armed else T.STEEL_LINE, width=1)
    ink = T.TABLE if armed else T.TX if enabled else INK_FAINT
    ibox = pygame.Rect(r.x + T.S, r.y + 5, 24, 24)
    if it.get("icon"):
        icons.icon(surf, it["icon"], ibox, ink)
    text(surf, F["bodyb"], it["label"], (ibox.right + T.S, r.y + 9), ink)
    cost = it.get("cost", 0)
    if not cost:
        return
    cx = r.right - T.S * 2
    if it.get("cost_style") == "count":
        text(surf, F["micro"], str(cost), (cx, r.centery - 6), ink, right=True)
        pygame.draw.circle(surf, ink, (cx - 16, r.centery), 3)
    else:
        for i in range(cost):
            pygame.draw.circle(surf, T.BRASS, (cx - i * 14, r.centery), 4)


def draw_action_tip(surf, F, anchor, desc):
    """The description bubble above (or below, near the top) a button."""
    w = T.S * 25
    lines = wrap(F["body_sm"], desc, w - T.S * 2)
    tip = pygame.Rect(0, 0, w, T.S + len(lines) * 16)
    tip.bottomleft = (anchor.left, anchor.top - 4)
    if tip.top < 0:
        tip.topleft = (anchor.left, anchor.bottom + 4)
    box(surf, tip, fill=T.STEEL_HI, border=T.STEEL_LINE)
    y = tip.y + T.S // 2
    for ln in lines:
        text(surf, F["body_sm"], ln, (tip.x + T.S, y), T.TX)
        y += 16


def inspect_height(open_, armed, sheet_h):
    return INSPECT_HEAD_H + (INSPECT_ARMED_H if armed else 0) + (sheet_h + T.S if open_ else 0)


def draw_inspect_header(surf, F, rect, label, open_, armed):
    """The collapsible INSPECT / ACTIVE UNIT bar. Returns `(toggle_rect,
    y)` -- `y` is where the sheet below it starts."""
    head = pygame.Rect(rect.x, rect.y, rect.w, 20)
    caret = "v" if open_ else ">"
    tracked(surf, F["micro"], f"{caret}  {label}", (head.x, head.y + 3), T.TX_MUTED)
    text(surf, F["body_sm"], "click a unit", (head.right, head.y + 3), INK_FAINT, right=True)
    pygame.draw.line(surf, T.STEEL_LINE, (head.x, head.bottom + 2), (head.right, head.bottom + 2))
    y = head.bottom + 4
    if armed:
        text(surf, F["body_sm"], "click again to attack", (rect.x, y), DANGER)
        y += INSPECT_ARMED_H
    return head, y


# ---------------------------------------------------------------------- #
# log                                                                    #
# ---------------------------------------------------------------------- #
LOG_RULES = (
    (("---", "***", "Round"), INK_FAINT),
    (("CRITICAL HIT",), WARN),
    (("DEAD", "dies.", "goes down, dying", "coup de grace", "Victory:",
      "*** Victory", "doesn't survive"), DANGER),
    (("is dying", "BROKEN", "ferocity runs out"), WARN),
    (("takes", "damage"), LOG_HURT),
    (("-> misses", "no effect", "critical miss", "misses again", "-> fail"), INK_FAINT),
    (("-> hit", "-> lands", "regenerates", "recovers", "recompo", "stabiliz",
      "survives", "-> success", "repaired", "back online"), OK),
)


def log_color(line):
    for needles, col in LOG_RULES:
        if any(nd in line for nd in needles):
            return col
    return T.TX_MUTED


def log_rows(rect):
    """How many log lines fit in the well."""
    return max(1, (rect.h - 24) // LOG_LINE_H)


def draw_log(surf, F, rect, lines, scrolled):
    """The log well. `lines` are the ones to show (oldest first); `scrolled`
    is how many newer lines sit below them (0 = following live, which lights
    the newest line). Returns the export button rect."""
    box(surf, rect, fill=T.TABLE, border=T.STEEL_LINE)
    tracked(surf, F["micro"], "LOG", (rect.x + T.S, rect.y + T.S // 2), INK_FAINT)
    export = pygame.Rect(0, rect.y + 1, 62, 16)
    export.right = rect.right - T.S
    box(surf, export, fill=T.STEEL, border=T.STEEL_LINE, width=1)
    text(surf, F["micro"], "export", export.center, INK_FAINT, center=True)

    y = rect.y + 22
    for i, ln in enumerate(lines):
        last = scrolled == 0 and i == len(lines) - 1
        text(surf, F["micro"], ln[:180], (rect.x + T.S * 2, y), T.TX if last else log_color(ln))
        y += LOG_LINE_H
    if scrolled:
        text(surf, F["micro"], f"v {scrolled} more below (scroll to follow)",
             (rect.right - T.S, rect.bottom - T.S // 2 - 14), INK_FAINT, right=True)
    return export


def draw_winner(surf, F, center, title):
    card = pygame.Rect(0, 0, T.S * 45, T.S * 11 + 4)
    card.center = center
    box(surf, card, fill=T.TABLE, border=T.BRASS, width=2)
    text(surf, F["titleb"], title, (card.centerx, card.y + 30), T.TX, center=True)
    text(surf, F["body"], "click to continue", (card.centerx, card.y + 62), T.TX_MUTED, center=True)

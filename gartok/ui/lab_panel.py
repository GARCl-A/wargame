"""The combat lab's setup form: which fight, how strong, who plays each side.

    draw_lab_form(surf, F, rect, form, mpos) -> {"fights": [(rect, id)], "level": (dec, inc),
        "squad": (dec, inc), "p1": rect, "p2": rect, "name": rect, "start": rect}

`form` is plain data:
    {"fights": [{"id", "name", "note"}], "selected": id, "level": int, "squad": int,
     "p1": "human" | "ai", "p2": "human" | "ai", "name": str, "editing": bool,
     "placeholder": str, "ready": bool}
`p1` is the guild's side (the player team, on the left of the board), `p2` the opposing one.
"""

import pygame

from .primitives import caps, draw_button, ellipsize, panel, section, text, tracked
from .tokens import T

ROW_H = T.S * 5
STEP_W = T.S * 4


def _stepper(surf, F, x, y, label, value, mpos):
    tracked(surf, F["microb"], label, (x, y), T.TX_FAINT)
    dec = pygame.Rect(x, y + 16, STEP_W, STEP_W)
    inc = pygame.Rect(x + STEP_W * 2 + T.S * 2, y + 16, STEP_W, STEP_W)
    draw_button(surf, F, dec, "-", mpos=mpos)
    draw_button(surf, F, inc, "+", mpos=mpos)
    text(surf, F["bodyb"], str(value), (dec.right + T.S + STEP_W // 2 + 2, dec.centery), T.TX, center=True)
    return dec, inc


def draw_lab_form(surf, F, rect, form, mpos):
    hits = {"fights": []}
    y = section(surf, F, "Fight", rect.x, rect.y, rect.w)
    col_w = (rect.w - T.S) // 2
    for i, fight in enumerate(form["fights"]):
        r = pygame.Rect(rect.x + (i % 2) * (col_w + T.S), y + (i // 2) * (ROW_H + T.S), col_w, ROW_H)
        chosen = fight["id"] == form["selected"]
        hover = r.collidepoint(mpos)
        panel(surf, r, hover=hover or chosen, width=2 if (hover or chosen) else 1)
        if chosen:
            pygame.draw.rect(surf, T.GREEN, r, 2)
        text(surf, F["bodyb"], ellipsize(fight["name"], F["bodyb"], r.w - T.S * 3), (r.x + T.S * 1.5, r.y + 4), T.TX)
        text(surf, F["body_sm"], ellipsize(fight["note"], F["body_sm"], r.w - T.S * 3),
             (r.x + T.S * 1.5, r.y + 4 + F["bodyb"].get_height()), T.TX_MUTED)
        hits["fights"].append((r, fight["id"]))
    y += ((len(form["fights"]) + 1) // 2) * (ROW_H + T.S) + T.S

    y = section(surf, F, "Setup", rect.x, y, rect.w)
    hits["level"] = _stepper(surf, F, rect.x, y, "LEVEL", form["level"], mpos)
    hits["squad"] = _stepper(surf, F, rect.x + T.S * 20, y, "SQUAD", form["squad"], mpos)
    y += STEP_W + T.S * 4

    half = (rect.w - T.S * 2) // 2
    for i, key in enumerate(("p1", "p2")):
        x = rect.x + i * (half + T.S * 2)
        who = "PLAYER 1  ·  the guild" if key == "p1" else "PLAYER 2  ·  the opposing side"
        tracked(surf, F["microb"], who, (x, y), T.TX_FAINT)
        r = pygame.Rect(x, y + 16, half, T.S * 5)
        human = form[key] == "human"
        draw_button(surf, F, r, "HUMAN" if human else "AI", primary=human, mpos=mpos)
        hits[key] = r
    y += T.S * 5 + 16 + T.S * 3

    tracked(surf, F["microb"], "SIMULATION NAME", (rect.x, y), T.TX_FAINT)
    nr = pygame.Rect(rect.x, y + 16, rect.w, T.S * 5)
    hot = nr.collidepoint(mpos) or form["editing"]
    panel(surf, nr, hover=hot, width=2 if hot else 1)
    shown = form["name"] + "|" if form["editing"] else form["name"] or form["placeholder"]
    text(surf, F["body"], shown, (nr.x + T.S * 2, nr.centery - F["body"].get_height() // 2),
         T.TX if (form["editing"] or form["name"]) else T.TX_FAINT)
    hits["name"] = nr
    y += T.S * 5 + 16 + T.S * 3

    start = pygame.Rect(rect.right - T.S * 25, y, T.S * 25, T.S * 5)
    draw_button(surf, F, start, "START", primary=True, enabled=form["ready"], mpos=mpos)
    hits["start"] = start
    caps(surf, F["micro"], "the log is saved under combat_lab/<date>/", (rect.x, start.centery - 6), T.TX_FAINT)
    return hits

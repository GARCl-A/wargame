"""The guild overview: how known the guild is, how many groups that lets it run,
what each group is doing with its slot, and what it holds.

`data` is one dict:
`{"fame": int, "fame_next": int (rep still needed for one more slot),
  "slots": (used, total), "factions": [(name, rep)],
  "notices": [(text, tone)],              # tone: "warn" | "bad"
  "groups": [{"name", "where", "task", "size", "capacity", "over", "note"}],
  "bases": [{"name", "status", "tone": "good" | "warn" | "bad" | "muted", "detail"}],
  "vocation": {"name", "perk", "dormant"} or None}`.
`note` is a short warning line or "". Fame is the sum of the factions' rep; the
rule it feeds lives in `RULES.md` ("Fame and group slots").
"""

import pygame

from .primitives import (
    caps,
    contained,
    ellipsize,
    scrollbar,
    section,
    text,
    tracked,
    wrap,
)
from .tokens import T

SIDE_MIN, SIDE_MAX = T.S * 34, T.S * 46
ROW_H = T.S * 8
PIP = T.S * 3
TONES = {"good": T.GREEN, "warn": T.BRASS, "bad": T.BLOOD, "muted": T.TX_MUTED}


def _card(surf, rect):
    pygame.draw.rect(surf, T.STEEL, rect)
    pygame.draw.rect(surf, T.STEEL_LINE, rect, 1)


def _draw_fame(surf, F, rect, d):
    _card(surf, rect)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4
    y = rect.y + T.S * 2
    used, total = d["slots"]
    tracked(surf, F["microb"], "GROUP SLOTS", (x, y), T.BRASS)
    text(surf, F["big"], f"{used}/{total}", (x + w, y - 4), T.BRASS, right=True)
    y += T.S * 4
    per_row = max(1, w // (PIP + T.S))
    for i in range(total):
        px = x + (i % per_row) * (PIP + T.S)
        py = y + (i // per_row) * (PIP + T.S)
        pr = pygame.Rect(px, py, PIP, PIP)
        if i < used:
            pygame.draw.rect(surf, T.BRASS, pr)
        else:
            pygame.draw.rect(surf, T.TX_FAINT, pr, 1)
    y += ((total - 1) // per_row + 1) * (PIP + T.S) + T.S

    y = section(surf, F, "Fame", x, y, w)
    text(surf, F["big"], str(d["fame"]), (x, y - 4), T.TX)
    caps(surf, F["micro"], "total reputation", (x + w, y + 8), T.TX_FAINT, right=True)
    y += T.S * 5
    text(surf, F["body_sm"], f"{d['fame_next']} more reputation for another group slot",
         (x, y), T.TX_MUTED)
    y += T.S * 3
    for name, rep in d["factions"]:
        text(surf, F["body_sm"], name, (x, y), T.TX_MUTED)
        text(surf, F["bodyb"], str(rep), (x + w, y), T.TX if rep else T.TX_FAINT, right=True)
        y += T.S * 3
    y += T.S
    for ln in wrap(F["micro"], "Every group takes a slot: a garrison, a work crew, people studying. "
                   "Fame is how widely the guild is known -- deeds raise it, nothing lowers it.",
                   w):
        text(surf, F["micro"], ln, (x, y), T.TX_FAINT)
        y += 14
    return y


def _draw_group(surf, F, rect, g):
    pygame.draw.line(surf, T.STEEL_LINE, rect.bottomleft, rect.bottomright)
    x, w = rect.x, rect.w
    y = rect.y + T.S
    badge = f"{g['size']}/{g['capacity']}"
    over = g["over"]
    text(surf, F["bodyb"], ellipsize(g["name"], F["bodyb"], w - T.S * 12), (x, y), T.TX)
    text(surf, F["bodyb"], badge, (x + w, y), T.BLOOD if over else T.TX_MUTED, right=True)
    sub = f"{g['where']}  ·  {g['task']}"
    text(surf, F["body_sm"], ellipsize(sub, F["body_sm"], w), (x, y + T.S * 3), T.TX_MUTED)
    warn = "  ·  ".join(p for p in (f"OVEREXTENDED +{over}" if over else "", g["note"]) if p)
    if warn:
        text(surf, F["microb"], ellipsize(warn, F["microb"], w), (x, y + T.S * 5), T.BLOOD)


def _draw_base(surf, F, rect, b):
    pygame.draw.line(surf, T.STEEL_LINE, rect.bottomleft, rect.bottomright)
    x, w = rect.x, rect.w
    y = rect.y + T.S
    tone = TONES[b["tone"]]
    text(surf, F["bodyb"], b["name"], (x, y), T.TX)
    caps(surf, F["microb"], b["status"], (x + w, y + 2), tone, right=True)
    text(surf, F["body_sm"], ellipsize(b["detail"], F["body_sm"], w), (x, y + T.S * 3), T.TX_MUTED)


def _draw_vocation(surf, F, x, y, w, voc):
    """The founding trade and its perk; returns the y below it."""
    text(surf, F["bodyb"], voc["name"], (x, y), T.TX)
    if voc["dormant"]:
        caps(surf, F["microb"], "NO EFFECT YET", (x + w, y + 2), T.BLOOD, right=True)
    y += T.S * 3
    for line in wrap(F["body_sm"], voc["perk"], w):
        text(surf, F["body_sm"], line, (x, y), T.TX_MUTED)
        y += F["body_sm"].get_height()
    return y


def draw_guild(surf, F, rect, data, scroll, mpos):
    """Returns `{"content_h", "view_h"}` so the caller can clamp its scroll."""
    gap = T.S * 2
    side_w = int(min(max(rect.w * 0.3, SIDE_MIN), SIDE_MAX))
    side_w = min(side_w, rect.w)
    main = pygame.Rect(rect.x + side_w + gap, rect.y, max(0, rect.w - side_w - gap), rect.h)
    with contained(surf, pygame.Rect(rect.x, rect.y, side_w, rect.h)):
        _draw_fame(surf, F, pygame.Rect(rect.x, rect.y, side_w, rect.h), data)

    y = main.y - scroll
    with contained(surf, main):
        for ln, tone in data["notices"]:
            nr = pygame.Rect(main.x, y, main.w - T.S, T.S * 5)
            pygame.draw.rect(surf, T.STEEL, nr)
            pygame.draw.rect(surf, TONES[tone], nr, 1)
            text(surf, F["bodyb"], ellipsize(ln, F["bodyb"], nr.w - T.S * 3),
                 (nr.x + T.S * 2, nr.y + T.S + 2), TONES[tone])
            y += nr.h + T.S
        if data["notices"]:
            y += T.S
        voc = data.get("vocation")
        if voc:
            y = section(surf, F, "Vocation", main.x, y, main.w - T.S)
            y = _draw_vocation(surf, F, main.x, y, main.w - T.S, voc) + T.S * 2
        y = section(surf, F, "Groups", main.x, y, main.w - T.S)
        for g in data["groups"]:
            _draw_group(surf, F, pygame.Rect(main.x, y, main.w - T.S, ROW_H), g)
            y += ROW_H
        y = section(surf, F, "Holdings", main.x, y + T.S * 2, main.w - T.S)
        for b in data["bases"]:
            _draw_base(surf, F, pygame.Rect(main.x, y, main.w - T.S, T.S * 6), b)
            y += T.S * 6
    content_h = y + scroll - main.y
    if content_h > main.h:
        scrollbar(surf, pygame.Rect(main.right - T.S, main.y, T.S, main.h), scroll,
                  max(1, content_h - main.h), content_h)
    return {"content_h": content_h, "view_h": main.h}

"""The guild roster column: filter pills, then every band as a collapsible
accordion of member cards.

Data in, rects out. `bands` items: `{"key", "name", "where" (node label),
"task" (order label), "collapsed", "members": [...]}`; each member is
`{"key", "name", "sub" (race / level line), "badges": [(label, color)],
"hp": (cur, max), "load": (cur, normal), "selected", "token"}` where `token`
is anything `primitives.token_badge` can read (race / portrait_id / token).
`filters` is `[(key, label, tip)]`.
"""

import pygame

from .primitives import caps, contained, ellipsize, scrollbar, text, token_badge
from .tokens import T

FILTER_H = T.S * 3
HEAD_H = T.S * 4
CARD_H = T.S * 8
GAP = 4
FOOT_H = T.S * 4


def _hp_col(cur, mx):
    if cur >= mx:
        return T.GREEN
    return T.BLOOD if cur <= mx // 2 else T.BRASS


def _arrow(surf, rect, collapsed, color):
    cx, cy = rect.x + T.S * 2, rect.centery
    if collapsed:
        pts = [(cx - 3, cy - 5), (cx - 3, cy + 5), (cx + 4, cy)]
    else:
        pts = [(cx - 5, cy - 3), (cx + 5, cy - 3), (cx, cy + 4)]
    pygame.draw.polygon(surf, color, pts)


def _badges(surf, F, rect, x, badges):
    """Pills laid left-to-right from `x`; stops before running off the card."""
    limit = rect.right - T.S * 11
    for label, color in badges:
        w = F["microb"].size(label)[0] + T.S * 2
        if x + w > limit:
            break
        pill = pygame.Rect(x, rect.y + T.S, w, T.S * 2 + 2)
        pygame.draw.rect(surf, T.TABLE, pill)
        pygame.draw.rect(surf, color, pill, 1)
        caps(surf, F["microb"], label, pill.center, color, center=True)
        x += w + 4


def draw_member_card(surf, F, rect, m, mpos):
    sel = m["selected"]
    hov = rect.collidepoint(mpos)
    pygame.draw.rect(surf, T.STEEL_HI if (sel or hov) else T.STEEL, rect)
    pygame.draw.rect(surf, T.BRASS if sel else T.STEEL_LINE, rect, 1)
    token_badge(surf, F, (rect.x + T.S * 3, rect.centery), m["token"], r=T.S * 2)

    tx = rect.x + T.S * 6
    right_w = T.S * 11
    name = ellipsize(m["name"], F["bodyb"], rect.w - (tx - rect.x) - right_w)
    nr = text(surf, F["bodyb"], name, (tx, rect.y + T.S), T.TX)
    _badges(surf, F, rect, nr.right + T.S, m["badges"])
    caps(surf, F["micro"], ellipsize(m["sub"], F["micro"], rect.w - (tx - rect.x) - right_w),
         (tx, rect.y + T.S * 4), T.TX_MUTED)

    hp, mx = m["hp"]
    text(surf, F["bodyb"], f"HP {hp}/{mx}", (rect.right - T.S, rect.y + T.S), _hp_col(hp, mx), right=True)
    load, norm = m["load"]
    text(surf, F["body_sm"], f"{load:g}/{norm:g} kg", (rect.right - T.S, rect.y + T.S * 4),
         T.BLOOD if load > norm else T.TX_MUTED, right=True)


def draw_guild_roster(surf, F, rect, bands, filters, active_filter, scroll, footer, mpos):
    """Returns `{"filters": [(rect, key)], "bands": [(rect, key)],
    "members": [(rect, key)], "tip": str|None, "content_h", "view_h"}`."""
    hits = {"filters": [], "bands": [], "members": [], "tip": None}

    fw = (rect.w - GAP * (len(filters) - 1)) // len(filters)
    for i, (key, label, tip) in enumerate(filters):
        fr = pygame.Rect(rect.x + i * (fw + GAP), rect.y, fw, FILTER_H)
        on, hov = key == active_filter, fr.collidepoint(mpos)
        pygame.draw.rect(surf, T.STEEL_HI if (on or hov) else T.STEEL, fr)
        pygame.draw.rect(surf, T.BRASS if on else T.STEEL_LINE, fr, 1)
        caps(surf, F["microb"], label, fr.center, T.BRASS if on else (T.TX if hov else T.TX_MUTED),
             center=True)
        hits["filters"].append((fr, key))
        if hov:
            hits["tip"] = tip

    top = rect.y + FILTER_H + T.S
    view = pygame.Rect(rect.x, top, rect.w, rect.bottom - top - FOOT_H - T.S)
    y = view.y - scroll
    with contained(surf, view):
        for band in bands:
            hr = pygame.Rect(rect.x, y, rect.w, HEAD_H)
            hov = hr.collidepoint(mpos) and view.collidepoint(mpos)
            pygame.draw.rect(surf, T.STEEL_HI if hov else T.STEEL, hr)
            pygame.draw.rect(surf, T.BRASS if hov else T.STEEL_LINE, hr, 1)
            _arrow(surf, hr, band["collapsed"], T.TX_MUTED)
            where = f"{band['where']} · {band['task']}".upper()
            wr = caps(surf, F["micro"], where, (hr.right - T.S, hr.centery - 6), T.TX_FAINT, right=True)
            title = f"{band['name']} ({len(band['members'])})"
            text(surf, F["bodyb"], ellipsize(title, F["bodyb"], wr.x - hr.x - T.S * 5 - T.S),
                 (hr.x + T.S * 4, hr.y + T.S - 2), T.TX)
            hits["bands"].append((hr.clip(view), band["key"]))
            if hov:
                hits["tip"] = f"{band['name']}: click to {'expand' if band['collapsed'] else 'collapse'}"
            y += HEAD_H + GAP
            if not band["collapsed"]:
                for m in band["members"]:
                    cr = pygame.Rect(rect.x, y, rect.w, CARD_H)
                    draw_member_card(surf, F, cr, m, mpos if view.collidepoint(mpos) else (-1, -1))
                    hits["members"].append((cr.clip(view), m["key"]))
                    y += CARD_H + GAP
            y += GAP * 2
        if not bands:
            text(surf, F["body_sm"], "Nobody matches this filter.", (rect.x + T.S, y + T.S), T.TX_FAINT)

    content_h = y + scroll - view.y
    hits["content_h"], hits["view_h"] = content_h, view.h
    if content_h > view.h:
        scrollbar(surf, pygame.Rect(rect.right + T.S, view.y, T.S, view.h), scroll,
                  max(1, content_h - view.h), content_h)

    fr = pygame.Rect(rect.x, rect.bottom - FOOT_H, rect.w, FOOT_H)
    pygame.draw.rect(surf, T.STEEL, fr)
    pygame.draw.rect(surf, T.STEEL_LINE, fr, 1)
    caps(surf, F["micro"], footer, fr.center, T.TX_MUTED, center=True)
    return hits


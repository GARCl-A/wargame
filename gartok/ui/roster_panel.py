"""The ROSTER zone: left-hand queue of bands -- one card per group, a
left-edge stripe in the group's own status colour -- plus the
upcoming-events timeline pinned to its bottom.

Status is whatever the caller says it is: each group dict carries a
ready-to-draw `state_label`/`state_color` instead of an enum key this
component would have to know the vocabulary of. A war-table mock has four
states; a real screen's orders have a couple dozen (travel/work/garrison/
market/bank/forge/...) -- this component doesn't need to know either list,
just what to print and in what colour.
"""

import pygame

from .primitives import caps, contained, draw_button, hline, text
from .tokens import T

CARD_H = 80                        # fixed top block: name/status/detail/rations
SPLIT_ROW_H = 20                   # one member checkbox row
SPLIT_FOOTER_H = 12 + 8 + 4 + 24 + 8   # divider gap + gap + button gap + button + bottom margin
MERGE_HEADER_H = 8 + 8 + 16        # gap + divider gap + "merge with" label
MERGE_ROW_H = 24 + 6               # one MERGE button + the gap after it
MERGE_MARGIN = 8                   # trailing gap below the last MERGE button


def hp_color(v):
    if v >= .85:
        return T.GREEN
    if v >= .45:
        return T.BRASS
    return T.BLOOD


def draw_party_pips(surf, party, pos, size=6, gap=4):
    x, y = pos
    for _, _, hp in party:
        pygame.draw.rect(surf, hp_color(hp), pygame.Rect(x, y, size, size))
        x += size + gap
    return x


def draw_roster(surf, F, rect, groups, events, selected, split_target=None,
                split_picks=frozenset(), mpos=(-1, -1)):
    """`groups` items: `{"key", "name", "lead", "state_label", "state_color",
    "needs_orders" (bool), "detail" (one-line status text), "rations_label",
    "party": [(name, role, hp_frac)],
    "roster_members": [(member_id, name, tag)],
    "mates": [(other_key, other_name)]}` (`tag` is an optional short label
    next to the name, e.g. race/level -- pass "" for none; `mates` is who
    that band could MERGE with, shown alongside SPLIT once its own card is
    expanded -- empty for none). `events` items: `(group_key, start, end,
    label, color)`. `split_picks` is the set of `member_id`s currently
    toggled to leave, for whichever group's card is expanded (`split_target`).

    Draws every group's card plus the upcoming-events timeline. Returns
    `(roster_rects, split_member_rects, split_confirm_rect, merge_rects)`:
    `roster_rects` is `[(card_rect, group_key, gear_rect)]`;
    `split_member_rects` is `[(member_id, rect)]` for the expanded card's
    checkboxes, empty unless `split_target` is set; `split_confirm_rect`
    is that card's SPLIT button rect, or None; `merge_rects` is
    `[(other_key, rect)]` for its MERGE buttons, one per `mates` entry."""
    pygame.draw.rect(surf, T.STEEL, rect)
    pygame.draw.line(surf, T.STEEL_LINE, (rect.right - 1, rect.y),
                     (rect.right - 1, rect.bottom), 1)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4
    y = rect.y + T.S * 2
    caps(surf, F["microb"], "bands", (x, y), T.TX_FAINT)
    awaiting = sum(1 for g in groups if g["needs_orders"])
    caps(surf, F["micro"], f"{awaiting} await orders", (rect.right - T.S * 2, y), T.BRASS, right=True)
    y += T.S * 3

    roster_rects = []
    split_member_rects = []
    split_confirm_rect = None
    merge_rects = []
    for g in groups:
        is_split = g["key"] == split_target
        mates = g.get("mates", []) if is_split else []
        h = CARD_H
        if is_split:
            h += len(g["roster_members"]) * SPLIT_ROW_H + SPLIT_FOOTER_H
            if mates:
                h += MERGE_HEADER_H + len(mates) * MERGE_ROW_H + MERGE_MARGIN

        card = pygame.Rect(x, y, w, h)
        with contained(surf, card):
            on = g["key"] == selected
            pygame.draw.rect(surf, T.STEEL_HI if on else T.TABLE, card)
            pygame.draw.rect(surf, T.STEEL_LINE, card, 1)
            # status stripe on the left edge: the eye only has to scan that column
            pygame.draw.rect(surf, g["state_color"], pygame.Rect(card.x, card.y, 3, card.h))

            cx = card.x + T.S + 2
            cy = card.y + T.S - 2

            r1 = text(surf, F["nameb"] if on else F["name"], g["name"],
                 (cx, cy), T.TX if on else T.TX_MUTED)

            cy = r1.bottom + 4
            r2 = caps(surf, F["micro"], g["state_label"], (cx, cy), g["state_color"])

            cy = r2.bottom + 2
            r3 = text(surf, F["body"], g["detail"], (cx, cy), T.TX_FAINT)

            cy = r3.bottom + 4
            r4 = caps(surf, F["micro"], g["rations_label"], (cx, cy), T.TX_FAINT)

            # gear button (split/merge)
            gear_rect = pygame.Rect(card.right - 24, r4.bottom - 16, 20, 20)
            pygame.draw.rect(surf, T.STEEL_LINE, gear_rect, 1)
            pygame.draw.circle(surf, T.TX_FAINT, gear_rect.center, 3, 1)
            for dx, dy in ((-4, 0), (4, 0), (0, -4), (0, 4)):
                pygame.draw.line(surf, T.TX_FAINT, gear_rect.center,
                                 (gear_rect.centerx + dx, gear_rect.centery + dy), 1)

            if is_split:
                sy = r4.bottom + 12
                pygame.draw.line(surf, T.STEEL_LINE, (card.x + T.S, sy), (card.right - T.S, sy), 1)
                sy += 8
                for member_id, name, tag in g["roster_members"]:
                    picked = member_id in split_picks
                    box = pygame.Rect(cx, sy, 12, 12)
                    if picked:
                        pygame.draw.rect(surf, T.BRASS, box)
                    else:
                        pygame.draw.rect(surf, T.STEEL_LINE, box, 1)
                    name_col = T.BRASS if picked else T.TX
                    name_r = text(surf, F["body"], name, (cx + 20, sy - 2), name_col)
                    if tag:
                        text(surf, F["micro"], tag, (name_r.right + T.S, sy),
                            T.BRASS if picked else T.TX_FAINT)
                    split_member_rects.append((member_id, box))
                    sy += SPLIT_ROW_H

                split_confirm_rect = pygame.Rect(cx, sy + 4, card.w - 2 * T.S, 24)
                draw_button(surf, F, split_confirm_rect, "confirm split", ghost=True, mpos=mpos)
                sy = split_confirm_rect.bottom

                if mates:
                    sy += 8
                    pygame.draw.line(surf, T.STEEL_LINE, (card.x + T.S, sy), (card.right - T.S, sy), 1)
                    sy += 8
                    caps(surf, F["micro"], "merge with", (cx, sy), T.TX_FAINT)
                    sy += 16
                    for other_key, other_name in mates:
                        mrect = pygame.Rect(cx, sy, card.w - 2 * T.S, 24)
                        draw_button(surf, F, mrect, f"merge with {other_name}", ghost=True, mpos=mpos)
                        merge_rects.append((other_key, mrect))
                        sy += MERGE_ROW_H

        roster_rects.append((card, g["key"], gear_rect))
        y = card.bottom + T.S

    # upcoming events, anchored to the bottom of the roster
    evs = sorted(events, key=lambda e: e[2])
    hud_h = len(evs) * 24 + 40
    y = rect.bottom - hud_h

    bg_rect = pygame.Rect(rect.x, y, rect.w, rect.bottom - y)
    pygame.draw.rect(surf, T.STEEL, bg_rect)
    hline(surf, rect.x, rect.right, y)

    y += T.S * 2
    caps(surf, F["microb"], "upcoming events", (x, y), T.TX_FAINT)
    y += T.S * 2

    for key, a, b, label, col in evs:
        is_sel = key == selected
        h_str = f"{int(b) % 24:02d}:00"
        lead = next((g["lead"] for g in groups if g["key"] == key), "")

        cx, cy = x, y + 8
        pygame.draw.circle(surf, col, (cx + 6, cy + 8), 4)
        if is_sel:
            pygame.draw.circle(surf, T.BRASS, (cx + 6, cy + 8), 6, 1)

        text(surf, F["microb"], h_str, (cx + 18, cy + 1), T.TX_MUTED)
        t_col = T.TX if is_sel else T.TX_FAINT
        text(surf, F["body"], f"{lead} · {label}", (cx + 56, cy - 1), t_col)

        y += 24

    return roster_rects, split_member_rects, split_confirm_rect, merge_rects

"""Active-quest cards for a group/roster view -- one card per accepted
mission: who took it, the deadline, and (when the mission tracks a
delivery quantity) progress toward the goal. Same contract as the rest of
`gartok.ui`: plain dicts in, the caller resolves `Mission`/`MissionTemplate`
questions (`missions.template_of`/`missions.progress`) before handing them
over."""

import pygame

from .loadout_panel import ICON_GAP, item_icon
from .primitives import draw_button, text
from .tokens import T

TAG_COLOR = {
    "economic": T.BRASS,
    "trust": T.BRASS,
    "bankers": T.BRASS_DIM,
    "apothecary": T.GREEN,
    "library": T.TX_MUTED,
    "tanner": T.TX_MUTED,
    "scholarly": T.TX_MUTED,
    "ruins": T.BLOOD,
}


def quest_list(surf, F, area, quests, empty_label="No active quests."):
    """`quests` is `[{"name","accepted_by","days_left","progress","tags"}]` --
    `progress` is `(have, goal, item)`, or `None` for a flat delivery quest
    with no tracked quantity ("Delivery"). Purely presentational: returns the y
    below the last card, where the caller may draw on."""
    if not quests:
        text(surf, F["body"], empty_label, (area.x, area.y), T.TX_FAINT)
        return area.y + T.S * 5

    y = area.y
    for q in quests:
        r = pygame.Rect(area.x, y, min(600, area.w), 80)
        pygame.draw.rect(surf, T.STEEL, r)
        pygame.draw.rect(surf, T.STEEL_LINE, r, 1)

        text(surf, F["nameb"], q["name"], (r.x + T.S * 3, r.y + T.S * 2), T.TX)

        tags = q.get("tags") or ()
        if tags:
            tx = r.x + T.S * 3 + F["nameb"].size(q["name"])[0] + T.S * 2
            for tag in tags:
                label = tag.upper()
                col = TAG_COLOR.get(tag.lower(), T.TX_MUTED)
                pw = F["microb"].size(label)[0] + 10
                if tx + pw > r.right - 140:
                    break
                pill = pygame.Rect(tx, r.y + T.S * 2 + 1, pw, 15)
                pygame.draw.rect(surf, T.STEEL_HI, pill, border_radius=4)
                pygame.draw.rect(surf, col, pill, 1, border_radius=4)
                text(surf, F["microb"], label, pill.center, col, center=True)
                tx += pw + 4

        text(surf, F["body_sm"], f"Accepted by {q['accepted_by']}", (r.x + T.S * 3, r.y + 40), T.TX_FAINT)

        days_left = q["days_left"]
        if days_left is None:
            dcol, due = T.TX_MUTED, "no deadline"
        else:
            dcol = T.BLOOD if days_left <= 1 else T.BRASS if days_left <= 3 else T.GREEN
            due = f"{max(0, days_left)} day(s) left"
        text(surf, F["body"], due, (r.right - T.S * 3, r.y + T.S * 2), dcol, right=True)

        progress = q["progress"]
        if progress is not None:
            have, goal, item = progress
            label = f"{have} / {goal} {item}"
            text(surf, F["body"], label, (r.right - T.S * 3, r.y + 40), T.GREEN if have >= goal else T.TX, right=True)
            item_icon(surf, item, r.right - T.S * 3 - F["body"].size(label)[0] - ICON_GAP - T.S * 3,
                      r.y + 48, T.S * 3)
        else:
            text(surf, F["body"], "Delivery", (r.right - T.S * 3, r.y + 40), T.TX, right=True)

        y += r.h + T.S * 3
    return y


def captive_list(surf, F, area, captives, mpos=None):
    """`captives` is `[{"key","name","race","days_left"}]`: one row per bound foe the group
    keeps, with a RELEASE button. Returns `[(rect, key)]` for the buttons."""
    text(surf, F["microb"], "CAPTIVES", (area.x, area.y), T.BRASS)
    y = area.y + T.S * 3
    if not captives:
        text(surf, F["body_sm"], "No one in bonds.", (area.x, y), T.TX_FAINT)
        return []
    hits = []
    for c in captives:
        r = pygame.Rect(area.x, y, min(600, area.w), T.S * 6)
        pygame.draw.rect(surf, T.STEEL, r)
        pygame.draw.rect(surf, T.STEEL_LINE, r, 1)
        text(surf, F["nameb"], c["name"], (r.x + T.S * 3, r.y + T.S + 2), T.TX)
        text(surf, F["body_sm"], c["race"], (r.x + T.S * 3, r.y + T.S * 3 + 4), T.TX_FAINT)
        left = c["days_left"]
        col = T.BLOOD if left <= 1 else T.BRASS if left <= 3 else T.TX_MUTED
        btn = pygame.Rect(r.right - T.S * 14, r.y + T.S + 2, T.S * 12, r.h - T.S * 2 - 4)
        text(surf, F["body"], f"{left} day(s) to live", (btn.x - T.S * 2, r.y + T.S * 2), col, right=True)
        draw_button(surf, F, btn, "release", ghost=True, mpos=mpos)
        hits.append((btn, c["key"]))
        y += r.h + T.S
    return hits

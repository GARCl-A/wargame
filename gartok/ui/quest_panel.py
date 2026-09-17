"""Active-quest cards for a group/roster view -- one card per accepted
mission: who took it, the deadline, and (when the mission tracks a
delivery quantity) progress toward the goal. Same contract as the rest of
`gartok.ui`: plain dicts in, the caller resolves `Mission`/`MissionTemplate`
questions (`missions.template_of`/`missions.progress`) before handing them
over."""

import pygame

from .primitives import text
from .tokens import T


def quest_list(surf, F, area, quests, empty_label="No active quests."):
    """`quests` is `[{"name","accepted_by","days_left","progress"}]` --
    `progress` is `(have, goal, item)`, or `None` for a flat delivery quest
    with no tracked quantity ("Delivery"). Purely presentational; no hits
    to return since a quest card isn't clickable yet."""
    if not quests:
        text(surf, F["body"], empty_label, area.center, T.TX_FAINT, center=True)
        return

    y = area.y
    for q in quests:
        r = pygame.Rect(area.x, y, min(600, area.w), 80)
        pygame.draw.rect(surf, T.STEEL, r)
        pygame.draw.rect(surf, T.STEEL_LINE, r, 1)

        text(surf, F["nameb"], q["name"], (r.x + T.S * 3, r.y + T.S * 2), T.TX)
        text(surf, F["body_sm"], f"Accepted by {q['accepted_by']}", (r.x + T.S * 3, r.y + 40), T.TX_FAINT)

        days_left = q["days_left"]
        dcol = T.BLOOD if days_left <= 1 else T.BRASS if days_left <= 3 else T.GREEN
        text(surf, F["body"], f"{max(0, days_left)} day(s) left",
             (r.right - T.S * 3, r.y + T.S * 2), dcol, right=True)

        progress = q["progress"]
        if progress is not None:
            have, goal, item = progress
            text(surf, F["body"], f"{have} / {goal} {item}",
                 (r.right - T.S * 3, r.y + 40), T.GREEN if have >= goal else T.TX, right=True)
        else:
            text(surf, F["body"], "Delivery", (r.right - T.S * 3, r.y + 40), T.TX, right=True)

        y += r.h + T.S * 3

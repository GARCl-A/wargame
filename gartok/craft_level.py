"""A recipe's level, worked out from how hard the recipe really is.

The level never blocks anyone: it is the recipe's difficulty label and, through
`progression.work_xp_hours`, the work-XP multiplier for a crafter below it. Points come from
three things, `LEVEL_PER_POINTS` of them per level above the first:

- the barrier to start: anyone (0), a talent any race can take (1), a racial talent or a quest's teaching only (2);
- scarce reagents, those the shops do not sell without limit (0, 1, 2 or more);
- the time a batch takes at an average roll (`HOURS_STEPS` hours add a point each).
"""

from . import economy, items

ENTRY_POINTS = {"open": 0, "talent": 1, "race": 2}
HOURS_STEPS = (3, 6)
LEVEL_PER_POINTS = 2
AVG_ROLL = 10.5                       # a d20 at INT mod 0: crafting progress per hour


def entry_of(name):
    """Who may start the recipe: `open` (everyone, or anyone who speaks the dictionary's
    language), `talent` (a talent any race can take) or `race` (only a racial talent, or a job's reward like the tanner's)."""
    if name in items.COMMON_RECIPES or name.startswith("Dictionary of "):
        return "open"
    if name in items.APOTHECARY_RECIPES or name in items.BLACKSMITH_RECIPES:
        return "talent"
    return "race"


def scarce_inputs(recipe):
    return sorted({m for m in recipe.materials if not economy.freely_buyable(m)})


def batch_hours(recipe):
    return items.recipe_goal(recipe) / AVG_ROLL


def breakdown(recipe):
    """The parts of a recipe's difficulty and the level they add up to."""
    entry, scarce, hours = entry_of(recipe.target), scarce_inputs(recipe), batch_hours(recipe)
    points = (ENTRY_POINTS[entry] + min(2, len(scarce))
              + sum(hours >= step for step in HOURS_STEPS))
    return {"entry": entry, "scarce": scarce, "hours": hours, "points": points,
            "level": 1 + points // LEVEL_PER_POINTS}


def level_of(recipe):
    return breakdown(recipe)["level"]

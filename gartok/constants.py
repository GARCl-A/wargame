"""
Centralized tuning constants for GARTOK.
These values govern economy, justice, progression, and campaign generation.
Tune these after playtesting to balance the game.
"""

# Economy
BANK_CHEST_PRICE = 90
BANK_CHEST_CAPACITY = 30
LUMBER_WAGE = 1
WILDS_CLAIM_SCOUT_HOURS = 2
WILDS_CLAIM_FENCE_HOURS = 8

# Justice
PRISON_DAYS_PER_CRIME = 2
PATROL_LEVEL_CAP = 6
PATROL_SIZE = 3

# Campaign & World events
FORTRESS_AMBUSH_LEVEL = 3
FORTRESS_AMBUSH_SIZE = 3
CITY_RAID_CHANCE = 0.25
CITY_RAID_LEVEL = 4

# Highest combat / work level an enemy pack is pitched at (encounters.py, arena.py):
# the XP curves (progression.py) have no top, so authored NPCs go past it
ENEMY_COMBAT_CAP = 7
ENEMY_WORK_CAP = 6
# Natural armor: a flat AC bonus a creature is born with (no Dex cap, no drag)
NATURAL_ARMOR_MAX = 5


def fmt_money(amount):
    """An amount of $ for display: `$1,250`."""
    return f"${amount:,}"

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

# Progression (XP Thresholds)
# Combat level thresholds (Level 1, 2, 3...)
COMBAT_XP_THRESHOLDS = (3, 10, 21, 36, 55, 78, 105, 136, 171, 210)
# Work marks thresholds (Level 1, 2, 3...)
WORK_XP_THRESHOLDS = (2, 6, 12, 20, 30, 42, 56, 72, 90, 110)
# Racial level thresholds (combat + work level)
RACIAL_XP_THRESHOLDS = (2, 4, 6, 8, 10, 12, 14, 16, 18, 20)
# Highest combat / work level an enemy pack is pitched at (encounters.py, arena.py):
# the XP tables above run past it so the creator can pin NPCs higher
ENEMY_COMBAT_CAP = 7
ENEMY_WORK_CAP = 6
# Natural armor: a flat AC bonus a creature is born with (no Dex cap, no drag)
NATURAL_ARMOR_MAX = 5

"""
Centralized tuning constants for GARTOK.
These values govern economy, justice, progression, and campaign generation.
Tune these after playtesting to balance the game.
"""

# Economy
BANK_CHEST_PRICE = 50
BANK_CHEST_CAPACITY = 10
CITY_HOSPITAL_PRICE = 15
CITY_TAVERN_PRICE = 10
CITY_TRAINING_PRICE = 20
LUMBER_WAGE = 3
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
COMBAT_XP_THRESHOLDS = (3, 10, 21, 36, 55, 78, 105)
# Work marks thresholds (Level 1, 2, 3...)
WORK_XP_THRESHOLDS = (2, 6, 12, 20, 30, 42)
# Racial level thresholds (combat + work level)
RACIAL_XP_THRESHOLDS = (2, 4, 6, 8, 10, 12, 14)

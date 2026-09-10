"""GARTOK tables, ported from the original character generator's .xlsx sheets.

Combat did not exist in the generator; the WEAPONS table and the mechanical
effect of the RACIAL ABILITIES were designed here for the wargame, keeping the
d20 style.

Naming: everything is English -- identifiers and the domain *content* (race,
occupation, alignment, size, language, weapon and item names). `RULES.md` is the
design-prose doc; `python -m gartok.reference` turns these tables into
`REFERENCE.md`, the authoritative catalog.
"""

import random

# --------------------------------------------------------------------------- #
# Dice                                                                         #
# --------------------------------------------------------------------------- #

def roll(n, sides):
    return sum(random.randint(1, sides) for _ in range(n))


def d20():
    return random.randint(1, 20)


def mod(score):
    return (score - 10) // 2


def squares(meters):
    """Meters -> board squares (1 square = 1.5 m, d20 standard). Minimum 1.

    Used both for movement (`speed`) and for ranges; every constant below rounds
    to the same value whether you floor or round, so one function covers both.
    """
    return max(1, round(meters / 1.5))


# --------------------------------------------------------------------------- #
# Typed bonuses                                                                #
#   Rule: bonuses of the SAME TYPE do not stack -> the largest one applies.    #
#   Untyped bonuses (type None) and ALL penalties stack normally.              #
# --------------------------------------------------------------------------- #

def resolve_bonus(mods):
    """mods: list of (value, type, label). Returns (total, [(value, label)])."""
    total = 0
    applied = []
    best_by_type = {}
    for value, kind, label in mods:
        if value == 0:
            continue
        if kind is None or value < 0:
            total += value
            applied.append((value, label))
        else:
            current = best_by_type.get(kind)
            if current is None or value > current[0]:
                best_by_type[kind] = (value, label)
    for kind, (value, label) in best_by_type.items():
        total += value
        applied.append((value, f"{label} [{kind}]"))
    return total, applied


# --------------------------------------------------------------------------- #
# Sizes  (speed in meters, carry multiplier, footprint side in squares)        #
#   `footprint` = squares per side of the board footprint. Large is 2x2 = 4.   #
#   Base speed does NOT change with size: Large moves like Medium (9 m); the    #
#   Centaur only exceeds 9 m because of the Gallop ability.                    #
# --------------------------------------------------------------------------- #

SIZES = {
    "Tiny": {"speed": 4.5, "carry": 0.5, "footprint": 1},
    "Small":  {"speed": 6.0, "carry": 1.0, "footprint": 1},
    "Medium":    {"speed": 9.0, "carry": 1.0, "footprint": 1},
    "Large":   {"speed": 9.0, "carry": 2.0, "footprint": 2},
}


# --------------------------------------------------------------------------- #
# Unarmed attack  (everyone has one; the die comes from the size)              #
# --------------------------------------------------------------------------- #

UNARMED_ATTACK = {
    "Tiny": (1, 2),
    "Small":  (1, 2),
    "Medium":    (1, 3),
    "Large":   (1, 4),
}


# --------------------------------------------------------------------------- #
# Falling, stabilizing and death  (designed for the wargame)                   #
# --------------------------------------------------------------------------- #

DYING_TURNS = 3              # dying unit rolls its death save on its 3rd own turn
DEATH_SAVE_MIN = 11         # d20 >= this survives (11-20 = 50%)
FIRST_AID_DC = 10          # first-aid kit: d20 + mod Wisdom vs this
AUTOMATON_REPAIR_DC = 15   # repairing a "broken" automaton: d20 + mod Intelligence vs this
FIRST_AID_CHARGES = 10     # a kit starts with this many charges (rechargeable)
QUIVER_AMMO = 20          # a quiver starts with this many bolts
BREATH_BASE = 4            # rounds a unit can stay underwater = this + its Constitution mod;
                          # every round past it: escalating drowning damage (1d6, 2d6, ...)


# --------------------------------------------------------------------------- #
# Ammo and improvised weapon                                                   #
# --------------------------------------------------------------------------- #

AMMO_ITEM = "Quiver"                     # inventory item that feeds a ranged weapon
FIRST_AID_ITEM = "First Aid Kit"


# --------------------------------------------------------------------------- #
# Vision and light  (designed for the wargame)                                 #
# --------------------------------------------------------------------------- #

SIGHT_MAX = squares(200)          # "infinite" along the line of sight (200 m)
DARKVISION = squares(18)          # ability "darkvision": sees 18 m in the dark
DEMORALIZE_RANGE = squares(18)    # Demoralize action: 18 m, needs mutual sight + shared language
TORCH_RADIUS = squares(6)         # torch: lights a 6 m radius (held or dropped)

# Inventory items that emit light -> lit radius in squares.
LIGHT_SOURCES = {
    "Lantern": squares(9),       # 9 m radius
}


# --------------------------------------------------------------------------- #
# Races   (threshold = upper bound on a d100 roll)                             #
# mods: Str Dex Con Int Wis Cha ; token = board letter (one per race)          #
# The mechanical effect of each ability lives in abilities.py.                 #
# --------------------------------------------------------------------------- #

RACES = [
    # threshold, name,          token,  Str Dex Con Int Wis Cha  ability         language     age     hd  size
    (15,  "Dwarf",           "A", ( 1,  0,  2,  0, -1, -2), "darkvision",     "Dwarvish",   5.000, 10, "Medium"),
    (17,  "Automaton",       "T", ( 1,  1,  0,  0, -1, -1), "inorganic_body", "Ankarin",   1.000,  8, "Medium"),
    (19,  "Centaur",       "C", ( 1, -2,  0,  0,  2, -1), "gallop",         "Elvish",    2.500, 10, "Large"),
    (34,  "Elf",           "E", (-2,  2, -1,  1,  0,  0), "sleep_immunity", "Elvish",    8.750,  8, "Medium"),
    (35,  "Gnoll",          "N", ( 0,  0,  2, -1,  0, -1), "strong_stomach", "Orcish",   0.625,  8, "Medium"),
    (36,  "Gnome",          "G", (-2,  1, -1,  0,  1,  1), "primal_blood",   "Gnomish",   6.250,  8, "Small"),
    (51,  "Goblin",         "O", (-1,  2,  1, -1,  0, -1), "pack_tactics",   "Goblin", 0.625,  6, "Small"),
    (54,  "Goliath",         "L", ( 2,  1,  0, -1, -1, -1), "strong_body",    "Jotun",     1.000, 10, "Medium"),
    (57,  "Grippli",        "P", (-1,  1,  0,  0,  1, -1), "amphibious",     "Sylvan", 1.500,  8, "Small"),
    (60,  "Halfling",       "H", (-2,  2, -2,  0,  1,  1), "keen_hearing",   "Halfling",   1.500,  6, "Small"),
    (64,  "Hobgoblin",      "B", ( 1,  1,  1, -1, -2,  0), "darkvision",     "Goblin", 0.625,  8, "Medium"),
    (74,  "Lizardfolk",  "Z", ( 1,  1,  0, -1,  0, -1), "climber",        "Draconic", 0.875, 10, "Medium"),
    (89,  "Human",         "M", ( 0,  0,  0,  0,  0,  0), "extra_language", "Ankarin",   1.000,  8, "Medium"),
    (92,  "Kenku",          "K", (-3,  1, -1,  0,  1,  2), "mimic_sounds",   "Sylvan", 1.000,  6, "Medium"),
    (95,  "Kobold",         "D", (-2,  1,  0,  1, -1,  1), "ancestral_blood","Draconic", 2.500,  6, "Small"),
    (96,  "Leshy",          "Y", (-1,  0,  1, -1,  1,  0), "autotroph",      "Verdant",    1.000,  6, "Small"),
    (99,  "Orc",            "R", ( 2,  1,  1, -1,  0, -3), "ferocity",       "Orcish",   0.625, 10, "Medium"),
    (100, "Sprite",         "S", (-2,  0, -2,  0,  2,  2), "flight",         "Gnomish",   1.500,  6, "Tiny"),
]

def _race_dict(threshold, name, token, mods, ability, language, age, hd, size):
    return {
        "name": name, "token": token, "mods": mods, "ability": ability,
        "language": language, "age_mult": age, "hd": hd, "size": size,
    }


_RACES = [_race_dict(*row) for row in RACES]

# Every language in the world = the racial languages (no description in the generator).
LANGUAGES = sorted({r["language"] for r in _RACES})


_RACE_THRESHOLDS = [row[0] for row in RACES]
RACE_NAMES = [r["name"] for r in _RACES]


def roll_race():
    r = random.randint(1, 100)
    for threshold, race in zip(_RACE_THRESHOLDS, _RACES):
        if r <= threshold:
            return dict(race)
    return None  # unreachable


def race_by_name(name):
    for race in _RACES:
        if race["name"] == name:
            return dict(race)
    return None


# --------------------------------------------------------------------------- #
# Weapons   (designed for the wargame)                                         #
#   damage (n, faces) ; range in squares (0 = melee) ; finesse uses Dexterity  #
#   thrown = throwing range in squares (0 = not a thrown weapon).              #
#   Only the Dagger is thrown for now (9 m = 6 squares).                       #
#   hands = how many hands the weapon takes (1 or 2); the torch takes 1 apart. #
#   weight in kg (invented values, base of the carry rule).                    #
# --------------------------------------------------------------------------- #

WEAPONS = {
    "Dagger":         {"damage": (1, 4), "range": 0,  "finesse": True,  "thrown": 6, "hands": 1, "weight": 0.5},
    "Hatchet":    {"damage": (1, 6), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 1.0},
    "Axe":       {"damage": (1, 8), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 3.0},
    "Light Hammer":  {"damage": (1, 4), "range": 0,  "finesse": True,  "thrown": 0, "hands": 1, "weight": 1.0},
    "Hammer":       {"damage": (1, 8), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 4.0},
    "Club":         {"damage": (1, 6), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 1.5},
    "Quarterstaff":        {"damage": (1, 6), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 2.0},
    "Shortspear":   {"damage": (1, 6), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 1.5},
    "Light Pick": {"damage": (1, 4), "range": 0,  "finesse": True,  "thrown": 0, "hands": 1, "weight": 1.0},
    "Pick":      {"damage": (1, 8), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 3.0},
    "Broadsword":    {"damage": (1, 12), "range": 0, "finesse": False, "thrown": 0, "hands": 2, "weight": 4.0},
    "Light Crossbow":    {"damage": (1, 8), "range": 11, "finesse": False, "thrown": 0, "hands": 2, "weight": 2.5},
}


# --------------------------------------------------------------------------- #
# Armor   (designed for the wargame)                                           #
#   ac      = flat bonus to Armor Class                                        #
#   max_dex = cap on the Dexterity mod that still counts to AC (None = no cap) #
#   speed   = board squares shaved off movement (heavy armor is slow)          #
#   weight  = kg, feeds the carry rule                                         #
#   More AC costs more copper (see economy.py), caps Dexterity harder and      #
#   weighs more; from +4 it also eats into movement.                           #
# --------------------------------------------------------------------------- #

ARMOR = {
    "Leather Jerkin":     {"ac": 1, "max_dex": None, "speed": 0, "weight": 4.0},
    "Studded Leather":       {"ac": 2, "max_dex": 3,    "speed": 0, "weight": 6.0},
    "Chainmail":      {"ac": 3, "max_dex": 2,    "speed": 0, "weight": 10.0},
    "Brigandine":             {"ac": 4, "max_dex": 1,    "speed": 1, "weight": 18.0},
    "Plate Armor": {"ac": 5, "max_dex": 0,    "speed": 2, "weight": 28.0},
}


# --------------------------------------------------------------------------- #
# Carry: weight of the inventory-slot items (kg, invented).                    #
# The Shepherd's sheep does NOT count here: it is a creature (see CREATURE_ITEMS). #
# --------------------------------------------------------------------------- #

TORCH_WEIGHT = 0.5
TORCH_ITEM = "Torch"                     # a torch carried in the pack / between battles

# Pack items that count as a day's meal (see the hunger rule in unit.py / guild.py).
FOOD_ITEMS = {"Meat", "Potato"}
STARVATION_DEATH_DAYS = 4                # missed meals in a row before a character dies

# Items used up in play, not hauled cargo -- the Carrier talent's carry relief
# skips these. Editable; grows as more consumables land.
CONSUMABLE_ITEMS = FOOD_ITEMS | {"First Aid Kit"}

ITEM_WEIGHTS = {
    TORCH_ITEM: TORCH_WEIGHT,
    "Meat": 1.0, "Potato": 1.0, "1kg Firewood": 1.0, "1kg Coal": 1.0, "1L Beer": 1.0,
    "Chisel": 0.3, "Scissors": 0.2, "Quiver": 1.5, "Rope": 2.0, "Iron Shackles": 1.0,
    "Map": 0.1, "Sack": 0.3, "Stone Brick": 3.0, "1sqm Hide": 2.0, "Shovel": 2.0,
    "Chains": 5.0, "Scroll": 0.1, "Iron Bar": 5.0, "Lantern": 1.0, "Compass": 0.2,
    "Deck of Cards": 0.2, "Cloak": 1.0, "Dictionary": 2.0, "First Aid Kit": 0.8, "Musical Instrument": 2.0,
    "Scales": 1.0, "Holy Symbol": 0.5, "Bucket": 1.0,
}


def item_weight(name):
    """Weight of an item in the pack. Weapons and armor weigh the same stowed as worn."""
    if name in WEAPONS:
        return WEAPONS[name]["weight"]
    if name in ARMOR:
        return ARMOR[name]["weight"]
    return ITEM_WEIGHTS.get(name, 0.5)


# Prices, market stock and haggling live in `economy.py` (behaviour, not a
# ported table). This module keeps only the raw generator data + game constants.

# --------------------------------------------------------------------------- #
# Alignment  (two axes: order Lawful/Neutral/Chaotic, morality Good/Neutral/Evil)     #
#   Feeds both the enemy AI (tendency) and market haggling (price sympathy).    #
# --------------------------------------------------------------------------- #
_ORDER_AXIS = {"Lawful": 1, "Neutral": 0, "Chaotic": -1}
_MORAL_AXIS = {"Good": 1, "Neutral": 0, "Evil": -1}


def alignment_axes(alignment):
    """'Lawful and Evil' -> (order, morality), each in {-1, 0, 1}."""
    order, morality = alignment.split(" and ")
    return _ORDER_AXIS[order], _MORAL_AXIS[morality]


def alignment_distance(a, b):
    """Distance on the two alignment axes: 0 (identical) .. 4 (diametrically opposed)."""
    ax, ay = alignment_axes(a)
    bx, by = alignment_axes(b)
    return abs(ax - bx) + abs(ay - by)


# Items from the occupation table that are actually creatures on the battlefield
# (not controllable, standing still for now). They stay out of the inventory / carry.
CREATURE_ITEMS = {
    "Sheep": {"name": "Sheep", "token": "o", "footprint": 1},
}


# --------------------------------------------------------------------------- #
# Occupations   (threshold = upper bound on a d100 roll)                       #
# --------------------------------------------------------------------------- #

OCCUPATIONS = [
    (5,   "Butcher",  "Hatchet",    "Meat"),
    (11,  "Farmer",  "Hatchet",    "Potato"),
    (14,  "Craftsman",     "Light Hammer",  "Chisel"),
    (19,  "Barber",    "Dagger",         "Scissors"),
    (21,  "Crossbowman",    "Light Crossbow",    "Quiver"),
    (25,  "Hunter",     "Shortspear",   "Rope"),
    (27,  "Jailer",  "Club",         "Iron Shackles"),
    (28,  "Cartographer",  "Dagger",         "Map"),
    (29,  "Brewer",  "Dagger",         "1L Beer"),
    (32,  "Merchant", "Dagger",         "Sack"),
    (35,  "Builder",  "Hammer",       "Stone Brick"),
    (38,  "Tanner",    "Dagger",         "1sqm Hide"),
    (40,  "Gravedigger",     "Light Pick", "Shovel"),
    (42,  "Slave",     "Club",         "Chains"),
    (43,  "Scribe",     "Dagger",         "Scroll"),
    (46,  "Blacksmith",    "Hammer",       "Iron Bar"),
    (48,  "Guard",      "Club",         "Lantern"),
    (51,  "Guide",        "Quarterstaff",        "Compass"),
    (55,  "Gambler",     "Dagger",         "Deck of Cards"),
    (61,  "Thief",      "Dagger",         "Cloak"),
    (67,  "Woodcutter",    "Axe",       "1kg Firewood"),
    (68,  "Linguist",   "Dagger",         "Dictionary"),
    (69,  "Physician",      "Dagger",         "First Aid Kit"),
    (72,  "Messenger",  "Quarterstaff",        "Sack"),
    (77,  "Mercenary",  "Axe",       "Rope"),
    (81,  "Miner",   "Pick",      "1kg Coal"),
    (85,  "Musician",      "Dagger",         "Musical Instrument"),
    (88,  "Goldsmith",     "Dagger",         "Scales"),
    (91,  "Priest",       "Quarterstaff",        "Holy Symbol"),
    (96,  "Shepherd",      "Quarterstaff",        "Sheep"),
    (100, "Innkeeper",  "Dagger",         "Bucket"),
]


def _occupation_dict(threshold, name, weapon, item):
    return {"name": name, "weapon": weapon, "item": item}


_OCCUPATIONS = [_occupation_dict(*row) for row in OCCUPATIONS]
_OCCUPATION_THRESHOLDS = [row[0] for row in OCCUPATIONS]
OCCUPATION_NAMES = [o["name"] for o in _OCCUPATIONS]


def roll_occupation():
    r = random.randint(1, 100)
    for threshold, occupation in zip(_OCCUPATION_THRESHOLDS, _OCCUPATIONS):
        if r <= threshold:
            return dict(occupation)
    return None


def occupation_by_name(name):
    for occupation in _OCCUPATIONS:
        if occupation["name"] == name:
            return dict(occupation)
    return None


# --------------------------------------------------------------------------- #
# Alignments   (threshold = upper bound on a d100 roll)                        #
# --------------------------------------------------------------------------- #

ALIGNMENTS = [
    (10,  "Lawful and Good"),
    (34,  "Lawful and Neutral"),
    (39,  "Lawful and Evil"),
    (63,  "Neutral and Good"),
    (72,  "Neutral and Neutral"),
    (82,  "Neutral and Evil"),
    (92,  "Chaotic and Good"),
    (97,  "Chaotic and Neutral"),
    (100, "Chaotic and Evil"),
]


def roll_alignment():
    r = random.randint(1, 100)
    for threshold, name in ALIGNMENTS:
        if r <= threshold:
            return name
    return None

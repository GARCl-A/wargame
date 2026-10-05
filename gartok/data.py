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

from . import items

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

SIZE_ORDER = ("Tiny", "Small", "Medium", "Large", "Huge")

SIZES = {
    "Tiny": {"speed": 4.5, "carry": 0.5, "footprint": 1},
    "Small":  {"speed": 6.0, "carry": 1.0, "footprint": 1},
    "Medium":    {"speed": 9.0, "carry": 1.0, "footprint": 1},
    "Large":   {"speed": 9.0, "carry": 2.0, "footprint": 2},
    "Huge":    {"speed": 9.0, "carry": 4.0, "footprint": 3},
}


# --------------------------------------------------------------------------- #
# Unarmed attack  (everyone has one; the die comes from the size)              #
# --------------------------------------------------------------------------- #

UNARMED_ATTACK = {
    "Tiny": (1, 2),
    "Small":  (1, 2),
    "Medium":    (1, 3),
    "Large":   (1, 4),
    "Huge":    (1, 6),
}


# --------------------------------------------------------------------------- #
# Falling, stabilizing and death  (designed for the wargame)                   #
# --------------------------------------------------------------------------- #

DYING_TURNS = 4              # dying unit rolls its death save on its 4th own turn (each hit on it adds one)
DEATH_SAVE_MIN = 11         # d20 >= this survives (11-20 = 50%)
FIRST_AID_DC = 10          # first-aid kit: d20 + mod Wisdom vs this
AUTOMATON_REPAIR_DC = 15   # repairing a "broken" automaton: d20 + mod Intelligence vs this
CHEST_DC = 15              # picking a locked chest: d20 + mod Dexterity vs this (see chest.py)
FIRST_AID_CHARGES = 10     # a kit starts with this many charges (rechargeable)
QUIVER_AMMO = 20          # a quiver starts with this many bolts
BREATH_BASE = 4            # rounds a unit can stay underwater = this + its Constitution mod;
                          # every round past it: escalating drowning damage (1d6, 2d6, ...)


# --------------------------------------------------------------------------- #
# Ammo and improvised weapon                                                   #
# --------------------------------------------------------------------------- #

AMMO_ITEM = items.AMMO_ITEM                     # inventory item that feeds a ranged weapon
FIRST_AID_ITEM = items.FIRST_AID_ITEM

# A locked chest: pick the lock (chest.py) for the gems inside, or hand it in
# whole. Failure costs nothing -- try again -- so it is never removed on a miss.
CHEST_ITEM = items.CHEST_ITEM
GEM_ITEM = items.GEM_ITEM                   # what a chest holds; sellable, not stocked to buy back

# The Bankers' trust mission (missions.py): a sealed chest that is NOT
# data.CHEST_ITEM on purpose -- opening this one early (chest.py's same roll)
# fails the mission and marks the opener a criminal instead of quietly paying
# out. LETTER_ITEM is what Ledger Hold hands back once it's exchanged intact.
MISSION_CHEST_ITEM = items.MISSION_CHEST_ITEM
LETTER_ITEM = items.LETTER_ITEM
CODEX_ITEM = items.CODEX_ITEM


# --------------------------------------------------------------------------- #
# Vision and light  (designed for the wargame)                                 #
# --------------------------------------------------------------------------- #

SIGHT_MAX = squares(200)          # "infinite" along the line of sight (200 m)
DARKVISION = squares(18)          # ability "darkvision": sees 18 m in the dark
DEMORALIZE_RANGE = squares(18)    # Demoralize action: 18 m, needs mutual sight + shared language
TORCH_RADIUS = squares(6)         # torch: lights a 6 m radius (held or dropped)

LANTERN_ITEM = items.LANTERN_ITEM          # an off-hand light source, like a torch but bigger and heavier


# Off-hand light sources beyond the torch -> lit radius in squares. Only lights
# while equipped in the off hand (see combatant.light_radius), same as a torch.
LIGHT_SOURCES = {
    LANTERN_ITEM: squares(9),    # 9 m radius
}


# --------------------------------------------------------------------------- #
# Races   (threshold = upper bound on a d100 roll)                             #
# mods: Str Dex Con Int Wis Cha ; token = board letter (one per race)          #
# The mechanical effect of each ability lives in abilities.py. A race's        #
# `ability` is one id, or a tuple of ids when it has several (Skeleton).       #
# --------------------------------------------------------------------------- #

RACES = [
    # threshold, name,          token,  Str Dex Con Int Wis Cha  ability         language     age     hd  size
    (15,  "Dwarf",           "A", ( 1,  0,  2,  0, -1, -2), "darkvision",     "Dwarvish",   5.000, 10, "Medium"),
    (17,  "Automaton",       "T", ( 1,  1,  0,  0, -1, -1), "inorganic_body", "Ankarin",   1.000,  8, "Medium"),
    (19,  "Centaur",       "C", ( 1, -2,  0,  0,  2, -1), "gallop",         "Elvish",    2.500, 10, "Large"),
    (34,  "Elf",           "E", (-2,  2, -1,  1,  0,  0), "sleep_immunity", "Elvish",    8.750,  8, "Medium"),
    (35,  "Gnoll",          "N", ( 0,  0,  2, -1,  0, -1), "strong_stomach", "Orcish",   0.625,  8, "Medium"),
    (36,  "Gnome",          "G", (-2,  1, -1,  0,  1,  1), "nature_magic",    "Gnomish",   6.250,  8, "Small"),
    (51,  "Goblin",         "O", (-1,  2,  1, -1,  0, -1), "pack_tactics",   "Goblin", 0.625,  6, "Small"),
    (54,  "Goliath",         "L", ( 2,  1,  0, -1, -1, -1), "strong_body",    "Jotun",     1.000, 10, "Medium"),
    (57,  "Grippli",        "P", (-1,  1,  0,  0,  1, -1), "amphibious",     "Sylvan", 1.500,  8, "Small"),
    (60,  "Halfling",       "H", (-2,  2, -2,  0,  1,  1), "innocent_face",  "Halfling",   1.500,  6, "Small"),
    (64,  "Hobgoblin",      "B", ( 1,  1,  1, -1, -2,  0), "darkvision",     "Goblin", 0.625,  8, "Medium"),
    (74,  "Lizardfolk",  "Z", ( 1,  1,  0, -1,  0, -1), "climber",        "Draconic", 0.875, 10, "Medium"),
    (89,  "Human",         "M", ( 0,  0,  0,  0,  0,  0), "extra_language", "Ankarin",   1.000,  8, "Medium"),
    (92,  "Kenku",          "K", (-3,  1, -1,  0,  1,  2), "mimic_sounds",   "Sylvan", 1.000,  6, "Medium"),
    (95,  "Kobold",         "D", (-2,  1,  0,  1, -1,  1), "blood_magic",    "Draconic", 2.500,  6, "Small"),
    (96,  "Treefolk",        "Y", (-1,  0,  1, -1,  1,  0), "autotroph",      "Verdant",    1.000,  6, "Medium"),
    (99,  "Orc",            "R", ( 2,  1,  1, -1,  0, -3), "ferocity",       "Orcish",   0.625, 10, "Medium"),
    (100, "Sprite",         "S", (-2,  0, -2,  0,  2,  2), "flight",         "Gnomish",   1.500,  6, "Tiny"),
]

def _race_dict(threshold, name, token, mods, ability, language, age, hd, size,
               kind="humanoid", drop_item=None, drop_chance=0.0, speed=None, also_drops=()):
    return {
        "name": name, "token": token, "mods": mods, "ability": ability,
        "language": language, "age_mult": age, "hd": hd, "size": size, "kind": kind,
        "drop_item": drop_item, "drop_chance": drop_chance,
        "also_drops": also_drops,                      # [(item, chance, qty)] beyond the trophy
        "speed": SIZES[size]["speed"] if speed is None else speed,   # meters; the size's unless the race sets its own
    }


_RACES = [_race_dict(*row) for row in RACES]

# Every language in the world = the racial languages (no description in the generator).
ATTRIBUTES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
LANGUAGES = sorted({r["language"] for r in _RACES})

# --------------------------------------------------------------------------- #
# Beasts: the first non-humanoid `kind` -- enemy-only (never rolled as a       #
# player's race), scaled through `encounters.build_enemy` exactly like a      #
# humanoid, but with no occupation (see `Unit._apply_beast`): a beast never   #
# carries a job's weapon/item, it fights with its own body (unarmed damage +  #
# its racial ability's `melee_damage`) and drops its own `drop_item` instead  #
# of gear (`loot.field_loot` reads it straight off the race dict -- a new     #
# beast's material is just two more columns here, not a change to loot.py).  #
# --------------------------------------------------------------------------- #

BEASTS = [
    # threshold, name, token, Str Dex Con Int Wis Cha  ability             language  age    hd  size      drop_item     drop_chance  speed (m)  also_drops
    (100, "Wolf", "w", ( 2,  2,  1, -4, -1, -3), "wolf_pack_tactics", "",       0.400,  8, "Medium", "1sqm Hide",  1.000,      10.5, (("Meat", 1.0, 2),)),
    (100, "Giant Spider", "x", ( 1,  2,  1, -4,  1, -4), ("climber", "spider_venom"), "", 0.200,  8, "Medium", "Venom Gland", 0.5, None),
]

def _beast_dict(threshold, name, token, mods, ability, language, age, hd, size,
                drop_item, drop_chance, speed=None, also_drops=()):
    return _race_dict(threshold, name, token, mods, ability, language, age, hd, size,
                      kind="beast", drop_item=drop_item, drop_chance=drop_chance, speed=speed,
                      also_drops=also_drops)


_BEASTS = [_beast_dict(*row) for row in BEASTS]

# Undead are not animals: they keep a job (an occupation, its weapon and item),
# but like a beast they are never rolled as a player race -- authored in the
# creator or placed by hand (the ruins).
UNDEAD = [
    # threshold, name, token, Str Dex Con Int Wis Cha  ability                                language  age    hd  size
    (100, "Skeleton", "s", ( 0,  2,  4, -4, -2, -4), ("darkvision", "sleep_immunity"), "", 5.000,  8, "Medium"),
]
_UNDEAD = [_race_dict(*row, kind="undead") for row in UNDEAD]

# Public pools for anything that needs to draw an arbitrary body from one
# (`encounters.EncounterEntry.race_pool`) -- `roll_race` stays the one path
# that rolls a fresh *player* race (humanoid, weighted by `RACES`' thresholds).
RACE_POOL = _RACES
BEAST_POOL = _BEASTS

# What the Wilds and the Old Road actually roll. The Giant Spider and the
# Skeleton are placed by hand, not drawn from a locality's table.
WILD_BEASTS = ("Wolf",)
WILD_POOL = [r for r in _BEASTS if r["name"] in WILD_BEASTS]

BEAST_OCCUPATION = {"name": "Wild Beast", "weapon": None, "item": None}


_RACE_THRESHOLDS = [row[0] for row in RACES]
RACE_NAMES = [r["name"] for r in _RACES]
BEAST_NAMES = [r["name"] for r in _BEASTS]
UNDEAD_NAMES = [r["name"] for r in _UNDEAD]
ALL_RACE_NAMES = RACE_NAMES + BEAST_NAMES + UNDEAD_NAMES        # what the creator offers; RACE_NAMES stays the playable set


def roll_race():
    r = random.randint(1, 100)
    for threshold, race in zip(_RACE_THRESHOLDS, _RACES):
        if r <= threshold:
            return dict(race)
    return None  # unreachable


def race_by_name(name):
    if name == "Leshy":
        name = "Treefolk"
    for race in _RACES + _BEASTS + _UNDEAD:
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
#   reload = True if firing the weapon requires the Reload action to chamber.  #
# --------------------------------------------------------------------------- #

from . import items

DAMAGE_STEPS = items.DAMAGE_STEPS
step_damage_die = items.step_damage_die

WEAPONS = items.weapons()
weapon_size = items.weapon_size

# --------------------------------------------------------------------------- #
# Armor & Shields                                                             #
# --------------------------------------------------------------------------- #

ARMOR = items.armor()
SHIELDS = items.shields()

# --------------------------------------------------------------------------- #
# Carry & Food                                                                #
# --------------------------------------------------------------------------- #

TORCH_WEIGHT = 0.5
TORCH_ITEM = "Torch"

FOOD_ITEMS = {item.name for item in items.food_items().values()}
STARVATION_DEATH_DAYS = 4

FOOD_LIFESPAN = {item.name: item.lifespan for item in items.food_items().values() if item.lifespan is not None}
CONSUMABLE_ITEMS = FOOD_ITEMS | {"First Aid Kit", "Minor Healing Potion"}

ITEM_WEIGHTS = {item.name: item.weight for item in items.all_items().values()}
item_weight = items.item_weight

# --------------------------------------------------------------------------- #
# Crafting Recipes                                                             #
# --------------------------------------------------------------------------- #

CRAFTING_RECIPES = items.CRAFTING_RECIPES
APOTHECARY_RECIPES = items.APOTHECARY_RECIPES
BLACKSMITH_RECIPES = items.BLACKSMITH_RECIPES



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
    (67,  "Woodcutter",    "Axe",       "Lumber"),
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
    if name == BEAST_OCCUPATION["name"]:
        return dict(BEAST_OCCUPATION)
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


# --------------------------------------------------------------------------- #
# Attribute & Stat Help                                                        #
# --------------------------------------------------------------------------- #

ATTRIBUTE_HELP = {
    "STR": (
        "STRENGTH (STR)",
        "Melee attack & damage rolls, carry weight capacity, athletics (jump, swim, climb, and push DC)."
    ),
    "DEX": (
        "DEXTERITY (DEX)",
        "Armor Class (AC), ranged & finesse weapon attack rolls, lockpicking, and disarming traps."
    ),
    "CON": (
        "CONSTITUTION (CON)",
        "Max Hit Points (HP), natural healing during rest, breath underwater, and push resistance."
    ),
    "INT": (
        "INTELLIGENCE (INT)",
        "Research and crafting progress, spell/psionic attack rolls, and repairing broken automatons."
    ),
    "WIS": (
        "WISDOM (WIS)",
        "Mental Defense (MD vs Demoralize), combat initiative bonus, and First Aid stabilization."
    ),
    "CHA": (
        "CHARISMA (CHA)",
        "Demoralize attack rolls, tavern recruitment contests, squad leadership limit, and shop bargaining."
    ),
}

DERIVED_HELP = {
    "HP": (
        "HIT POINTS (HP)",
        "Current / maximum health. Dropping to 0 HP makes a unit dying."
    ),
    "AC": (
        "ARMOR CLASS (AC)",
        "Physical defense target. Attacks meeting or beating AC inflict damage."
    ),
    "MD": (
        "MENTAL DEFENSE (MD)",
        "Resistance against Demoralize and psychological effects (10 + WIS mod)."
    ),
    "SPD": (
        "SPEED (SPD)",
        "Movement allowance per turn in cells (1 cell = 1.5 meters)."
    ),
    "INIT": (
        "INITIATIVE (INIT)",
        "Bonus added to turn order roll at start of combat (based on WIS)."
    ),
}

item_tooltip = items.item_tooltip


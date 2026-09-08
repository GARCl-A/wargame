"""GARTOK tables, ported from the original character generator's .xlsx sheets.

Combat did not exist in the generator; the WEAPONS table and the mechanical
effect of the RACIAL ABILITIES were designed here for the wargame, keeping the
d20 style.

Naming: identifiers are English; the domain *content* (race, occupation,
alignment, size, language, weapon and item names) stays in Portuguese because it
is shared, verbatim, with GARTOK-regras.md and shown in the UI.
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
    "Diminuto": {"speed": 4.5, "carry": 0.5, "footprint": 1},
    "Pequeno":  {"speed": 6.0, "carry": 1.0, "footprint": 1},
    "Medio":    {"speed": 9.0, "carry": 1.0, "footprint": 1},
    "Grande":   {"speed": 9.0, "carry": 2.0, "footprint": 2},
}


# --------------------------------------------------------------------------- #
# Unarmed attack  (everyone has one; the die comes from the size)              #
# --------------------------------------------------------------------------- #

UNARMED_ATTACK = {
    "Diminuto": (1, 2),
    "Pequeno":  (1, 2),
    "Medio":    (1, 3),
    "Grande":   (1, 4),
}


# --------------------------------------------------------------------------- #
# Falling, stabilizing and death  (designed for the wargame)                   #
# --------------------------------------------------------------------------- #

DYING_TURNS = 3              # dying unit rolls its death save on its 3rd own turn
DEATH_SAVE_MIN = 11         # d20 >= this survives (11-20 = 50%)
FIRST_AID_DC = 10          # first-aid kit: d20 + mod Wisdom vs this
AUTOMATON_REPAIR_DC = 15   # repairing a "broken" automaton: d20 + mod Intelligence vs this
FIRST_AID_CHARGES = 10     # a kit starts with this many charges (rechargeable)
QUIVER_AMMO = 20          # a quiver (Aljava) starts with this many bolts


# --------------------------------------------------------------------------- #
# Ammo and improvised weapon                                                   #
# --------------------------------------------------------------------------- #

AMMO_ITEM = "Aljava"                     # inventory item that feeds a ranged weapon
FIRST_AID_ITEM = "Kit de primeiros socorros"


# --------------------------------------------------------------------------- #
# Vision and light  (designed for the wargame)                                 #
# --------------------------------------------------------------------------- #

SIGHT_MAX = squares(200)          # "infinite" along the line of sight (200 m)
DARKVISION = squares(18)          # ability "darkvision": sees 18 m in the dark
DEMORALIZE_RANGE = squares(18)    # Demoralize action: 18 m, needs mutual sight + shared language
TORCH_RADIUS = squares(6)         # torch: lights a 6 m radius (held or dropped)

# Inventory items that emit light -> lit radius in squares.
LIGHT_SOURCES = {
    "Lanterna": squares(9),       # 9 m radius
}


# --------------------------------------------------------------------------- #
# Races   (threshold = upper bound on a d100 roll)                             #
# mods: Str Dex Con Int Wis Cha ; token = board letter (one per race)          #
# The mechanical effect of each ability lives in abilities.py.                 #
# --------------------------------------------------------------------------- #

RACES = [
    # threshold, name,          token,  Str Dex Con Int Wis Cha  ability         language     age     hd  size
    (15,  "Anao",           "A", ( 1,  0,  2,  0, -1, -2), "darkvision",     "Enanico",   5.000, 10, "Medio"),
    (17,  "Automato",       "T", ( 1,  1,  0,  0, -1, -1), "inorganic_body", "Ankarin",   1.000,  8, "Medio"),
    (19,  "Centauro",       "C", ( 1, -2,  0,  0,  2, -1), "gallop",         "Elfico",    2.500, 10, "Grande"),
    (34,  "Elfo",           "E", (-2,  2, -1,  1,  0,  0), "sleep_immunity", "Elfico",    8.750,  8, "Medio"),
    (35,  "Gnoll",          "N", ( 0,  0,  2, -1,  0, -1), "strong_stomach", "Orquico",   0.625,  8, "Medio"),
    (36,  "Gnomo",          "G", (-2,  1, -1,  0,  1,  1), "primal_blood",   "Gnomico",   6.250,  8, "Pequeno"),
    (51,  "Goblin",         "O", (-1,  2,  1, -1,  0, -1), "pack_tactics",   "Goblinico", 0.625,  6, "Pequeno"),
    (54,  "Golias",         "L", ( 2,  1,  0, -1, -1, -1), "strong_body",    "Jotun",     1.000, 10, "Medio"),
    (57,  "Grippli",        "P", (-1,  1,  0,  0,  1, -1), "amphibious",     "Silvestre", 1.500,  8, "Pequeno"),
    (60,  "Halfling",       "H", (-2,  2, -2,  0,  1,  1), "keen_hearing",   "Pequine",   1.500,  6, "Pequeno"),
    (64,  "Hobgoblin",      "B", ( 1,  1,  1, -1, -2,  0), "darkvision",     "Goblinico", 0.625,  8, "Medio"),
    (74,  "Homem Lagarto",  "Z", ( 1,  1,  0, -1,  0, -1), "climber",        "Draconico", 0.875, 10, "Medio"),
    (89,  "Humano",         "M", ( 0,  0,  0,  0,  0,  0), "extra_language", "Ankarin",   1.000,  8, "Medio"),
    (92,  "Kenku",          "K", (-3,  1, -1,  0,  1,  2), "mimic_sounds",   "Silvestre", 1.000,  6, "Medio"),
    (95,  "Kobold",         "D", (-2,  1,  0,  1, -1,  1), "ancestral_blood","Draconico", 2.500,  6, "Pequeno"),
    (96,  "Leshy",          "Y", (-1,  0,  1, -1,  1,  0), "autotroph",      "Planti",    1.000,  6, "Pequeno"),
    (99,  "Orc",            "R", ( 2,  1,  1, -1,  0, -3), "ferocity",       "Orquico",   0.625, 10, "Medio"),
    (100, "Sprite",         "S", (-2,  0, -2,  0,  2,  2), "flight",         "Gnomico",   1.500,  6, "Diminuto"),
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
    "Adaga":         {"damage": (1, 4), "range": 0,  "finesse": True,  "thrown": 6, "hands": 1, "weight": 0.5},
    "Machadinha":    {"damage": (1, 6), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 1.0},
    "Machado":       {"damage": (1, 8), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 3.0},
    "Martelo Leve":  {"damage": (1, 4), "range": 0,  "finesse": True,  "thrown": 0, "hands": 1, "weight": 1.0},
    "Martelo":       {"damage": (1, 8), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 4.0},
    "Clava":         {"damage": (1, 6), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 1.5},
    "Bordao":        {"damage": (1, 6), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 2.0},
    "Lanca Curta":   {"damage": (1, 6), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 1.5},
    "Picareta Leve": {"damage": (1, 4), "range": 0,  "finesse": True,  "thrown": 0, "hands": 1, "weight": 1.0},
    "Picareta":      {"damage": (1, 8), "range": 0,  "finesse": False, "thrown": 0, "hands": 1, "weight": 3.0},
    "Besta Leve":    {"damage": (1, 8), "range": 11, "finesse": False, "thrown": 0, "hands": 2, "weight": 2.5},
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
    "Gibao de couro":     {"ac": 1, "max_dex": None, "speed": 0, "weight": 4.0},
    "Couro batido":       {"ac": 2, "max_dex": 3,    "speed": 0, "weight": 6.0},
    "Cota de malha":      {"ac": 3, "max_dex": 2,    "speed": 0, "weight": 10.0},
    "Brunea":             {"ac": 4, "max_dex": 1,    "speed": 1, "weight": 18.0},
    "Armadura de placas": {"ac": 5, "max_dex": 0,    "speed": 2, "weight": 28.0},
}


# --------------------------------------------------------------------------- #
# Carry: weight of the inventory-slot items (kg, invented).                    #
# The Shepherd's sheep does NOT count here: it is a creature (see CREATURE_ITEMS). #
# --------------------------------------------------------------------------- #

TORCH_WEIGHT = 0.5
TORCH_ITEM = "Tocha"                     # a torch carried in the pack / between battles

# Pack items that count as a day's meal (see the hunger rule in unit.py / guild.py).
FOOD_ITEMS = {"1kg Carne", "1kg Batata"}
STARVATION_DEATH_DAYS = 4                # missed meals in a row before a character dies

ITEM_WEIGHTS = {
    TORCH_ITEM: TORCH_WEIGHT,
    "1kg Carne": 1.0, "1kg Batata": 1.0, "1kg Lenha": 1.0, "1kg Carvao": 1.0, "1L Cerveja": 1.0,
    "Cinzel": 0.3, "Tesoura": 0.2, "Aljava": 1.5, "Corda": 2.0, "Algemas de ferro": 1.0,
    "Mapa": 0.1, "Saco": 0.3, "Tijolo de pedra": 3.0, "1 m2 Couro": 2.0, "Pa": 2.0,
    "Correntes": 5.0, "Pergaminho": 0.1, "Barra de ferro": 5.0, "Lanterna": 1.0, "Bussola": 0.2,
    "Baralho": 0.2, "Capa": 1.0, "Dicionario": 2.0, "Kit de primeiros socorros": 0.8, "Instrumento musical": 2.0,
    "Balanca": 1.0, "Simbolo Religioso": 0.5, "Balde": 1.0,
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
# Alignment  (two axes: order Leal/Neutro/Caotico, morality Bom/Neutro/Mal)     #
#   Feeds both the enemy AI (tendency) and market haggling (price sympathy).    #
# --------------------------------------------------------------------------- #
_ORDER_AXIS = {"Leal": 1, "Neutro": 0, "Caotico": -1}
_MORAL_AXIS = {"Bom": 1, "Neutro": 0, "Mal": -1}


def alignment_axes(alignment):
    """'Leal e Mal' -> (order, morality), each in {-1, 0, 1}."""
    order, morality = alignment.split(" e ")
    return _ORDER_AXIS[order], _MORAL_AXIS[morality]


def alignment_distance(a, b):
    """Distance on the two alignment axes: 0 (identical) .. 4 (diametrically opposed)."""
    ax, ay = alignment_axes(a)
    bx, by = alignment_axes(b)
    return abs(ax - bx) + abs(ay - by)


# Items from the occupation table that are actually creatures on the battlefield
# (not controllable, standing still for now). They stay out of the inventory / carry.
CREATURE_ITEMS = {
    "Ovelha": {"name": "Ovelha", "token": "o", "footprint": 1},
}


# --------------------------------------------------------------------------- #
# Occupations   (threshold = upper bound on a d100 roll)                       #
# --------------------------------------------------------------------------- #

OCCUPATIONS = [
    (5,   "Acougueiro",  "Machadinha",    "1kg Carne"),
    (11,  "Agricultor",  "Machadinha",    "1kg Batata"),
    (14,  "Artesao",     "Martelo Leve",  "Cinzel"),
    (19,  "Barbeiro",    "Adaga",         "Tesoura"),
    (21,  "Besteiro",    "Besta Leve",    "Aljava"),
    (25,  "Cacador",     "Lanca Curta",   "Corda"),
    (27,  "Carcereiro",  "Clava",         "Algemas de ferro"),
    (28,  "Cartografo",  "Adaga",         "Mapa"),
    (29,  "Cervejeiro",  "Adaga",         "1L Cerveja"),
    (32,  "Comerciante", "Adaga",         "Saco"),
    (35,  "Construtor",  "Martelo",       "Tijolo de pedra"),
    (38,  "Coureiro",    "Adaga",         "1 m2 Couro"),
    (40,  "Coveiro",     "Picareta Leve", "Pa"),
    (42,  "Escravo",     "Clava",         "Correntes"),
    (43,  "Escriba",     "Adaga",         "Pergaminho"),
    (46,  "Ferreiro",    "Martelo",       "Barra de ferro"),
    (48,  "Guarda",      "Clava",         "Lanterna"),
    (51,  "Guia",        "Bordao",        "Bussola"),
    (55,  "Jogador",     "Adaga",         "Baralho"),
    (61,  "Ladrao",      "Adaga",         "Capa"),
    (67,  "Lenhador",    "Machado",       "1kg Lenha"),
    (68,  "Linguista",   "Adaga",         "Dicionario"),
    (69,  "Medico",      "Adaga",         "Kit de primeiros socorros"),
    (72,  "Mensageiro",  "Bordao",        "Saco"),
    (77,  "Mercenario",  "Machado",       "Corda"),
    (81,  "Minerador",   "Picareta",      "1kg Carvao"),
    (85,  "Musico",      "Adaga",         "Instrumento musical"),
    (88,  "Ourives",     "Adaga",         "Balanca"),
    (91,  "Padre",       "Bordao",        "Simbolo Religioso"),
    (96,  "Pastor",      "Bordao",        "Ovelha"),
    (100, "Taverneiro",  "Adaga",         "Balde"),
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
    (10,  "Leal e Bom"),
    (34,  "Leal e Neutro"),
    (39,  "Leal e Mal"),
    (63,  "Neutro e Bom"),
    (72,  "Neutro e Neutro"),
    (82,  "Neutro e Mal"),
    (92,  "Caotico e Bom"),
    (97,  "Caotico e Neutro"),
    (100, "Caotico e Mal"),
]


def roll_alignment():
    r = random.randint(1, 100)
    for threshold, name in ALIGNMENTS:
        if r <= threshold:
            return name
    return None

"""Where the art files are, with no pygame: the portrait of a unit, the glyph of each race and
occupation, the banner emblems. `artwork.py` loads and tints them for pygame; the web serves the
files as they are."""

import functools
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PORTRAITS = os.path.join(_HERE, "assets", "portraits")


# Race -> head silhouette in assets/icons/head/. A few races have no exact glyph
# (Centaur, Treefolk, Sprite) and borrow the nearest read. Keep every value pointing
# at a file that exists -- `icon()` falls back to None (caller draws the letter)
# if one goes missing, but a typo here would silently blank every token.
RACE_ICON = {
    "Dwarf":      "dwarf-face",
    "Automaton":  "robot-helmet",
    "Centaur":    "barbarian",
    "Elf":        "elf-ear",
    "Gnoll":      "fox-head",
    "Gnome":      "wizard-face",
    "Goblin":     "goblin-head",
    "Goliath":    "ogre",
    "Grippli":    "triton-head",
    "Halfling":   "baby-face",
    "Hobgoblin":  "orc-head",
    "Lizardfolk": "lizardman",
    "Human":      "caesar",
    "Kenku":      "kenku-head",
    "Kobold":     "horned-reptile",
    "Leshy":      "sprout",
    "Treefolk":   "sprout",
    "Orc":        "orc-head",
    "Sprite":     "air-man",
    "Wolf":       "wolf-head",
    "Snake":      "medusa-head",
    "Ogre":       "ogre",
    "Dragon":     "dragon-head",
    "Skeleton":   "dead-head",
    "Zombie":     "mummy-head",
}


# Occupation name -> (category, file under assets/icons/). Every occupation in
# `data.OCCUPATIONS` needs a line (a test fails for one with none).
OCCUPATION_ICON = {
    "Butcher": ("map", "cleaver"), "Farmer": ("body", "farmer"), "Craftsman": ("action", "crafting"),
    "Barber": ("map", "scissors"), "Crossbowman": ("body", "bowman"), "Hunter": ("hat", "robin-hood-hat"),
    "Jailer": ("body", "guards"), "Cartographer": ("body", "atlas"), "Brewer": ("action", "pouring-chalice"),
    "Merchant": ("action", "trade"), "Builder": ("action", "stone-crafting"), "Tanner": ("map", "hide"),
    "Gravedigger": ("map", "shovel"), "Slave": ("body", "slavery-whip"), "Scribe": ("action", "read"),
    "Blacksmith": ("body", "blacksmith"), "Guard": ("body", "static-guard"), "Guide": ("action", "hiking"),
    "Gambler": ("body", "tabletop-players"), "Thief": ("body", "rogue"), "Woodcutter": ("action", "stick-splitting"),
    "Linguist": ("action", "conversation"), "Physician": ("hat", "plague-doctor-profile"),
    "Messenger": ("action", "run"), "Mercenary": ("body", "swordman"), "Miner": ("body", "miner"),
    "Musician": ("action", "sing"), "Goldsmith": ("hat", "crown-coin"), "Priest": ("body", "sun-priest"),
    "Shepherd": ("map", "crook"), "Innkeeper": ("action", "drinking"), "Wild Beast": ("action", "wolf-howl"),
}


@functools.lru_cache(maxsize=1024)
def portrait_path(race_name, portrait_id):
    """The file of a unit's portrait, or None if the race has none.

    If `portrait_id` is a string (e.g. 'ribit.png', 'adelio', 'npc/bufo.png'),
    it pins to that specific image file so the generic race pool does not pick it.
    Otherwise, an integer selects deterministically from the numbered portraits in the pool."""
    if not race_name and not portrait_id:
        return None

    if isinstance(portrait_id, str) and not portrait_id.isdigit():
        p_str = portrait_id.strip()
        candidates = [p_str] if p_str.lower().endswith(".png") else [p_str, f"{p_str}.png"]
        search_dirs = []
        if race_name:
            r_clean = str(race_name).lower().strip()
            if r_clean == "leshy":
                r_clean = "treefolk"
            folder = os.path.join(_PORTRAITS, r_clean)
            if not os.path.isdir(folder):
                alt = r_clean.replace(", ", "_").replace(" ", "_") if " " in r_clean else r_clean.replace("_", " ")
                folder = os.path.join(_PORTRAITS, alt)
            if os.path.isdir(folder):
                search_dirs.append(folder)
        search_dirs.extend([
            os.path.join(_PORTRAITS, "npc"),
            _PORTRAITS,
        ])
        for sdir in search_dirs:
            if not os.path.isdir(sdir):
                continue
            for cand in candidates:
                p_cand = os.path.join(sdir, cand)
                if os.path.isfile(p_cand):
                    return p_cand

    if not race_name:
        return None
    r_clean = str(race_name).lower().strip()
    if r_clean == "leshy":
        r_clean = "treefolk"
    folder = os.path.join(_PORTRAITS, r_clean)
    if not os.path.isdir(folder):
        alt = r_clean.replace(", ", "_").replace(" ", "_") if " " in r_clean else r_clean.replace("_", " ")
        alt_folder = os.path.join(_PORTRAITS, alt)
        if os.path.isdir(alt_folder):
            folder = alt_folder
        else:
            return None

    def _sort_key(f):
        stem, _ = os.path.splitext(f)
        return (0, int(stem)) if stem.isdigit() else (1, stem)

    try:
        files = [f for f in sorted(os.listdir(folder), key=_sort_key) if f.lower().endswith(".png")]
    except OSError:
        return None
    if not files:
        return None

    numeric_pool = [f for f in files if os.path.splitext(f)[0].isdigit()]
    pool = numeric_pool if numeric_pool else files

    if isinstance(portrait_id, int) or (isinstance(portrait_id, str) and portrait_id.isdigit()):
        idx = abs(int(portrait_id)) % len(pool)
    else:
        idx = 0
    return os.path.join(folder, pool[idx])


# A small curated gallery for the guild's banner emblem (picked at the draft's
# charter) -- (category, slug, label). Not every icon under assets/
# reads well tinted at emblem size on a flat disc; this is a hand-picked
# subset, same spirit as RACE_ICON above. `Guild.banner_icon` stores the slug.
BANNER_ICONS = [
    ("action", "shield-bash", "Shield"),
    ("body", "surrounded-shield", "Bulwark"),
    ("body", "bell-shield", "Vigil"),
    ("body", "sword-tie", "Blade"),
    ("action", "wolf-howl", "Wolf Cry"),
    ("head", "wolf-head", "Wolf"),
    ("head", "snake-bite", "Serpent"),
    ("body", "fire-silhouette", "Flame"),
    ("gui", "stars-stack", "Stars"),
    ("body", "psychic-waves", "Storm"),
]

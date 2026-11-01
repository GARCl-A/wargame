"""Procedural personal names for GARTOK's nobodies.

The recruits drifting through the taverna, the bodies hired to pad out an enemy
squad, the one-off arena challengers -- none of them are authored, so none of
them come with a name. This hands each one a throwaway: 2-4 syllables strung
together and capitalised (mostly 2, never past `MAX_LETTERS`, never two heavy ones side by
side). Not culture-aware, not gendered -- just enough to tell one nameless
mercenary from the next.

Wild beasts are not named here: they go by their species, a pack tells its members
apart with an `EPITHETS` adjective (`Unit`, `Battle._tell_beasts_apart`).
Authored NPCs (the library, hand-built champions) carry their own names and
never pass through here.
"""

import random

# A private stream so handing out names never disturbs the global `random`
# sequence the rest of the game (and the tests) seed for reproducible rolls.
_rng = random.Random()

SYLLABLES = [
    "ka", "dor", "ven", "mir", "thal", "grok", "un", "el", "bran", "sur",
    "tik", "mor", "za", "hel", "dun", "ash", "kor", "vel", "nim", "gar",
    "oth", "ru", "sen", "kael", "drix", "ma", "tor", "yl", "bex", "orn",
    "vok", "ther", "rax", "im", "dral", "sho", "keth", "uln", "brae", "tas",
    "gorm", "nyx", "vash", "ek", "mun", "throg", "ald", "ir", "skel", "wen",
    "dro", "caz", "fel", "hrom", "lys", "ob", "pyr", "quen", "rig", "vyr",
]


def seed(value):
    """Pin the name stream, so a seeded fight (`combat_lab.build`) names its units the same."""
    _rng.seed(value)


MAX_LETTERS = 9
SYLLABLE_COUNTS = (2, 3, 4)
SYLLABLE_WEIGHTS = (6, 3, 1)
HEAVY = {s for s in SYLLABLES if len(s) >= 4 or s[:2] in {"th", "dr", "br", "gr", "sk", "hr"}}


def random_name(rng=_rng):
    while True:
        parts = rng.choices(SYLLABLES, k=rng.choices(SYLLABLE_COUNTS, SYLLABLE_WEIGHTS)[0])
        if sum(p in HEAVY for p in parts) > 1 or len("".join(parts)) > MAX_LETTERS:
            continue
        return "".join(parts).capitalize()


# Fit a wolf, a spider and a snake alike.
EPITHETS = [
    "Scarred", "Pale", "Gaunt", "Old", "Young", "Black", "Grey", "Sleek", "Lean", "Hulking",
    "Wary", "Restless", "Sullen", "Twitchy", "Hungry", "Starved", "Feral", "Battered", "Bold", "Cunning",
]


def epithets(count, rng=_rng):
    """`count` distinct adjectives; past the list's length they start over."""
    pool = []
    while len(pool) < count:
        pool += rng.sample(EPITHETS, len(EPITHETS))
    return pool[:count]

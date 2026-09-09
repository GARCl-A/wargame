"""Procedural personal names for GARTOK's nobodies.

The recruits drifting through the taverna, the bodies hired to pad out an enemy
squad, the one-off arena challengers -- none of them are authored, so none of
them come with a name. This hands each one a throwaway: 2-4 syllables strung
together and capitalised. Not culture-aware, not gendered -- just enough to tell
one nameless mercenary from the next.

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


def random_name(rng=_rng):
    return "".join(rng.choice(SYLLABLES)
                   for _ in range(rng.randint(2, 4))).capitalize()

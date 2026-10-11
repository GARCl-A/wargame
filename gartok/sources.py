"""Where each base material comes from.

A base material is a raw good no recipe makes: an item of a `RAW_TYPES` type that is
not the target of any `CRAFTING_RECIPES` entry (derived, like `craft_level.py`, never
set by hand). Every one must have a source. Gathered goods (`gather.TABLES`) and beast
drops (`data.BEASTS`) are read off those tables; the rest are declared in `DECLARED`.
Weapons, armour and the other end products are not base materials until recipes cover
them.
"""

from collections import namedtuple

from . import data, gather, items

Source = namedtuple("Source", "kind where")

GATHERED, DROPPED, HUNTED, FORAGED, QUEST, TRADED, SPOILED = (
    "gathered", "dropped", "hunted", "foraged", "quest", "traded", "spoiled")

RAW_TYPES = (items.ItemType.MATERIAL, items.ItemType.FOOD, items.ItemType.GEM)

DECLARED = {
    "Meat": (Source(HUNTED, "the Wilds"),),
    "Red Mushroom": (Source(FORAGED, "the Wilds"),),
    "Legendary Horn": (Source(QUEST, "the tanner's last job"),),
    "Rotten Food": (Source(SPOILED, "food left to rot"),),
    # the shops supply these; no node produces them until the production chain exists.
    # Farm and Smith are the shops they will move to; the Market sells them until then
    "Potato": (Source(TRADED, "Farm"),),
    "Salt": (Source(TRADED, "Market"),),
    "1L Beer": (Source(TRADED, "Market"),),
    "Iron Bar": (Source(TRADED, "Smith"),),
    "Vial": (Source(TRADED, "Market"),),
    "Paper": (Source(TRADED, "Library"),),
    "Ink": (Source(TRADED, "Library"),),
}


def base_materials():
    made = {r.target for r in items.CRAFTING_RECIPES.values()}
    return sorted(i.name for i in items.all_items().values()
                  if i.type in RAW_TYPES and i.name not in made)


def _beast_drops():
    drops = {}
    for row in data.BEASTS:
        name, main, also = row[1], row[9], (row[12] if len(row) > 12 else ())
        for item in [main, *(d[0] for d in also)]:
            if item:
                drops.setdefault(item, []).append(Source(DROPPED, name))
    return drops


def sources_of(name):
    found = [Source(GATHERED, node_id) for node_id, table in gather.TABLES.items()
             if any(n == name for n, _ in table)]
    found += _beast_drops().get(name, [])
    return found + list(DECLARED.get(name, ()))

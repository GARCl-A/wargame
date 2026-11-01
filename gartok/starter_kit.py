"""What a fresh recruit starts with: one random weapon and one random item, by price.

The pools are read off `items.py`, so a new cheap item joins the draw on its own. Large and Huge
weapons belong to the Ogre's shelf, quest items are never carried at the start, and money is the
purse (`economy.STARTING_WEALTH_DICE`), not an item.
"""

import random

from . import items

WEAPON_PRICE_CAP = 35
ITEM_PRICE_CAP = 20


def weapon_pool():
    return [d.name for d in items._REGISTRY.values()
            if d.type == items.ItemType.WEAPON and 0 < d.price <= WEAPON_PRICE_CAP
            and d.size not in (items.WeaponSize.LARGE, items.WeaponSize.HUGE)]


def item_pool():
    skipped = (items.ItemType.WEAPON, items.ItemType.QUEST, items.ItemType.CURRENCY)
    return [d.name for d in items._REGISTRY.values() if d.type not in skipped and 0 < d.price <= ITEM_PRICE_CAP]


def roll():
    """`(weapon, item)` names, each drawn evenly from its pool."""
    return random.choice(weapon_pool()), random.choice(item_pool())

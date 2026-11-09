"""What a fresh recruit starts with: one random weapon and one random item, by price.

The pools are read off `items.py`, so a new cheap item joins the draw on its own. They hold the plain
(Medium) items and the price cap is the plain price; the pick is then made for the body: a weapon at the
body's size but never above Medium (a Centaur gets no free Large weapon), armor at exactly its size.
Quest items are never carried at the start, and money is the purse (`economy.STARTING_WEALTH_DICE`), not an item.
"""

import random

from . import data, items

WEAPON_PRICE_CAP = 35
ITEM_PRICE_CAP = 20


def weapon_pool():
    return [d.name for d in items._REGISTRY.values()
            if d.type == items.ItemType.WEAPON and 0 < d.price <= WEAPON_PRICE_CAP and d.base is None]


def item_pool():
    skipped = (items.ItemType.WEAPON, items.ItemType.QUEST, items.ItemType.CURRENCY)
    return [d.name for d in items._REGISTRY.values()
            if d.type not in skipped and 0 < d.price <= ITEM_PRICE_CAP and d.base is None]


def for_body(name, size):
    """`name` as a body of `size` starts with it (the plain item when it has no size of its own)."""
    if name is None:
        return None
    item = items.get(name)
    if item is None or item.size is None:
        return name
    if item.type == items.ItemType.WEAPON and data.SIZE_ORDER.index(size) > data.SIZE_ORDER.index("Medium"):
        size = "Medium"
    variant = items.sized(name, size)
    return variant.name if variant else name


def roll(size="Medium"):
    """`(weapon, item)` names fitted to a body of `size`, each drawn evenly from its pool."""
    return for_body(random.choice(weapon_pool()), size), for_body(random.choice(item_pool()), size)

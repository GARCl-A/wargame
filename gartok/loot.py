"""What the party can carry off after a won fight.

The loot pool is everything left on the battlefield once the enemies are down:
the gear each defeated enemy still had on them, the gear of any of the party's
own dead (their body is right there), and loose objects on the ground -- weapons
that were dropped or thrown, torches. `LootScreen` lets the survivors take what
fits under `carry_max`; the rest is left behind.

Read off the *battle* combatants, never the roster: a weapon a unit threw is on
`battle.ground`, not on the combatant, so nothing is counted twice.

A beast (`Unit.race["kind"] == "beast"`, see `data.BEAST_POOL`) never carries
gear -- it drops its own trophy material instead, straight off the race dict
(`drop_item`/`drop_chance`, e.g. the Wolf's `data.BEASTS` row): a new species'
material is a data change in `data.py`, not a new branch here.
"""

import random

from . import data


def _carried_by(u):
    """Item names a downed/defeated combatant still has: the weapon in hand, a
    lit torch or lantern, and everything in the pack."""
    items = []
    if getattr(u, "weapon_hand", False) and getattr(u, "weapon_name", None):
        items.append(u.weapon_name)
    if getattr(u, "torch_hand", False):
        items.append(data.TORCH_ITEM)
    if getattr(u, "lantern_hand", False):
        items.append(data.LANTERN_ITEM)
    items += list(getattr(u, "inventory", []))
    return items


def field_loot(battle, fallen_combatants, rng=random):
    """-> sorted list[str] of item names on the field after a player win.

    `fallen_combatants` are the player's own dead (from `battle.player_units`).
    """
    pool = []
    for u in list(battle.enemy_units) + list(fallen_combatants):
        if getattr(u, "fled", False):
            continue                      # ran off the map with their kit
        pool += _carried_by(u)
        char = getattr(u, "char", None)
        drop = char.race.get("drop_item") if char is not None else None
        if drop and rng.random() < char.race.get("drop_chance", 0.0):
            pool.append(drop)
    for obj in battle.ground:
        if obj.is_weapon and obj.weapon_name:
            pool.append(obj.weapon_name)
        elif obj.is_torch:
            pool.append(data.TORCH_ITEM)
    return sorted(pool)

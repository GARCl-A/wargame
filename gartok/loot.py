"""What the party can carry off after a won fight.

The loot pool is everything left on the battlefield once the enemies are down:
the gear each defeated enemy still had on them, the gear of any of the party's
own dead (their body is right there), and loose objects on the ground -- weapons
that were dropped or thrown, torches. `LootScreen` lets the survivors take what
fits under `carry_max`; the rest is left behind.

Read off the *battle* combatants (deep copies), never the roster: a weapon a
unit threw is on `battle.ground`, not on the unit, so nothing is counted twice.
"""

from . import data


def _carried_by(u):
    """Item names a downed/defeated combatant still has: the weapon in hand, a
    lit torch, and everything in the pack."""
    items = []
    if getattr(u, "weapon_hand", False) and getattr(u, "weapon_name", None):
        items.append(u.weapon_name)
    if getattr(u, "torch_hand", False):
        items.append(data.TORCH_ITEM)
    items += list(getattr(u, "inventory", []))
    return items


def field_loot(battle, fallen_combatants):
    """-> sorted list[str] of item names on the field after a player win.

    `fallen_combatants` are the player's own dead (from `battle.player_units`).
    """
    pool = []
    for u in list(battle.enemy_units) + list(fallen_combatants):
        if getattr(u, "fled", False):
            continue                      # ran off the map with their kit
        pool += _carried_by(u)
    for obj in battle.ground:
        if obj.is_weapon and obj.weapon_name:
            pool.append(obj.weapon_name)
        elif obj.is_torch:
            pool.append(data.TORCH_ITEM)
    return sorted(pool)

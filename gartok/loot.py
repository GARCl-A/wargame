"""What the party can carry off after a won fight.

The loot pool is everything left on the battlefield once the enemies are down:
the gear each defeated enemy still had on them, everything the party's own dead
carried -- purse included, the coins being items too (their body is right there;
an enemy's purse is not looted) -- and loose objects on the ground -- weapons
that were dropped or thrown, torches. `spoils.Spoils` lets the survivors take what
fits under `carry_max`; the rest is left behind.

Read off the *battle* combatants, never the roster: a weapon a unit threw is on
`battle.ground`, not on the combatant, so nothing is counted twice.

A rolled beast (`Unit.race["kind"] == "beast"`, see `data.BEAST_POOL`) never
carries gear -- it drops its own trophy material instead, straight off the race dict
(`drop_item`/`drop_chance`, e.g. the Wolf's `data.BEASTS` row): a new species'
material is a data change in `data.py`, not a new branch here. An authored NPC
(`npc_lib`) can instead carry guaranteed unique drops, keyed by its slug in
`UNIQUE_DROPS` (the Biwolf's leather, the Aurochs' hide and horn), and a body worth keeping
(`captives.CORPSES`) from a foe left fallen and unbound -- a won lethal fight finishes it.
"""

import random

from . import captives, items

UNIQUE_DROPS = {"biwolf": (items.BIWOLF_LEATHER_ITEM,),
               "aurochs": (items.THUNDERHIDE_ITEM, items.LEGENDARY_HORN_ITEM)}
BATTLEFIELD_SPARE_THE_DYING_CHANCE = 0.001
SPARE_THE_DYING_SCROLL = "Scroll of Spare the Dying"


def parse_currency(it):
    """If `it` represents a currency award, returns the copper amount (int), else None."""
    if isinstance(it, tuple) and len(it) == 2:
        if isinstance(it[0], (int, float)) and str(it[1]).lower() in ("copper", "gold", "coin", "coins"):
            return int(it[0])
        if str(it[0]).lower() in ("copper", "gold", "coin", "coins"):
            try:
                return int(it[1])
            except (ValueError, TypeError):
                pass
    elif isinstance(it, str):
        parts = it.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].lower() in ("copper", "gold", "coin", "coins"):
            return int(parts[0])
    return None


def carried_by(u):
    """Item names a downed/defeated combatant still has: the weapon in hand, a
    lit torch or lantern, and everything in the pack."""
    carried = []
    if getattr(u, "weapon_hand", False) and getattr(u, "weapon_name", None):
        carried.append(u.weapon_name)
    if getattr(u, "torch_hand", False):
        carried.append(items.TORCH_ITEM)
    if getattr(u, "lantern_hand", False):
        carried.append(items.LANTERN_ITEM)
    for it in getattr(u, "inventory", []):
        if isinstance(it, str):
            carried.append(it)
        else:
            carried += [it.name] * it.qty
    return carried


def worn_by(unit):
    """What a roster `Unit` has on their body: hands, tongue, armor, artifact.
    A fight's loot reads the combatant instead, so this is for deaths outside one."""
    slots = (unit.equipped_weapon, unit.equipped_offhand, unit.equipped_tongue,
             unit.equipped_armor, unit.equipped_artifact)
    return [name for name in slots if name]


def field_loot(battle, fallen_combatants, rng=random):
    """-> sorted list[str] of item names on the field after a player win.

    `fallen_combatants` are the player's own dead (from `battle.player_units`). The bodies of
    every other side and of the allied NPCs who fell lie there too (a raised member of the
    guild is counted once, as one of the guild's own). A scenario with `strips_the_dead` gives
    up what every body wore too (armour, off hand, artifact), not only what it carried.
    """
    pool = []
    strip = getattr(getattr(battle, "scenario", None), "strips_the_dead", False)
    fallen = list(fallen_combatants)
    bodies = [u for u in battle.foe_units if u not in fallen]
    bodies += [u for u in battle.player_units if u.ai_ally and u.dead and u not in fallen]
    for u in bodies + fallen:
        if getattr(u, "fled", False):
            continue                      # ran off the map with their kit
        pool += carried_by(u)
        char = getattr(u, "char", None)
        if char is not None and u in fallen_combatants:
            for coin in items.COIN_VALUE:
                pool += [coin] * char.count_of(coin)
        if char is not None and (u in fallen_combatants or strip):
            if char.equipped_armor:
                pool.append(char.equipped_armor)
            if char.equipped_offhand:
                if char.equipped_offhand == items.TORCH_ITEM and getattr(u, "torch_hand", False):
                    pass
                elif char.equipped_offhand == items.LANTERN_ITEM and getattr(u, "lantern_hand", False):
                    pass
                else:
                    pool.append(char.equipped_offhand)
            if char.equipped_artifact:
                pool.append(char.equipped_artifact)
            if getattr(char, "equipped_tongue", None):
                pool.append(char.equipped_tongue)
        if char is not None and not getattr(u, "captured", False):
            slug = getattr(char, "npc_slug", None)
            pool += UNIQUE_DROPS.get(slug, ())
            if slug in captives.CORPSES and u in battle.foe_units and not u.alive:
                pool.append(captives.CORPSES[slug])
            drop = char.race.get("drop_item")
            if drop and rng.random() < char.race.get("drop_chance", 0.0):
                pool.append(drop)
            for name, chance, qty in char.race.get("also_drops", ()):
                if rng.random() < chance:
                    pool += [name] * qty
            if (getattr(getattr(battle, "scenario", None), "is_battlefield", False)
                    and u in battle.foe_units and not u.alive):
                if rng.random() < BATTLEFIELD_SPARE_THE_DYING_CHANCE:
                    pool.append(SPARE_THE_DYING_SCROLL)
    for obj in battle.ground:
        if obj.fixture:
            continue
        if obj.is_weapon and obj.weapon_name:
            pool.append(obj.weapon_name)
        elif obj.is_torch:
            pool.append(items.TORCH_ITEM)
        elif obj.is_trap:
            if obj.trap_type == "bear trap":
                pool.append("Bear Trap")
            elif obj.trap_type == "alarm trap":
                pool.append("Alarm Trap")
        elif getattr(obj, "is_chest", False):
            for it in getattr(obj, "contents", []):
                if parse_currency(it) is None:
                    pool.append(it)
    relics_left = getattr(getattr(battle, "scenario", None), "relics_left", None)
    if relics_left is not None:
        pool += relics_left(battle)
    return sorted(pool)


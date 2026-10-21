"""What a generated body of a given level carries: its kit, bought with the level's budget.

`KIT_BUDGET` is the copper a character of that racial level has had to spend by the time they
get there (`scripts/wealth_by_level.py`, a player who wins 95% of fights and takes any risk).
`outfit` spends it on a humanoid from `encounters.build_enemy`, in this order:

  - armour, up to `ARMOR_SHARE` of the budget: the one that gives the most AC once its Dex cap
    is taken (`ac + min(Dex mod, max_dex)`), the cheapest of those, worn without being
    overloaded; a nimble body stops at the armour its Dex already fills;
  - weapon, up to `WEAPON_SHARE`, by the body's archetype, whatever its occupation: Strength
    over Dexterity fights in melee, `TWO_HANDED_SHARE` of them with a two-handed blade (a
    Broadsword), the rest with a one-handed weapon that is not finesse; otherwise
    `RANGED_SHARE` of them shoot (a bow or a crossbow, and a Quiver) and the rest fight with a
    one-handed finesse weapon. A one-handed fighter holds a light in the off hand (the Lantern
    from the pack, else a Torch). Whoever cannot pay for the two-handed blade or the bow falls
    back to one hand (an archer keeps a bow already in hand). A Strength or ranged weapon is
    drawn among those that cost at least `WEAPON_SPREAD` of the dearest that fits (price is
    their power there); a finesse one among all that fit, since none of them beats the others
    outright (the Dagger throws, the Rapier hits harder). The old weapon is gone, not packed;
  - potions: Minor Healing Potions with what is left, at most `POTION_CAP` and never past the
    overload (the catalogue has no kit to soak up the budgets past level 5, the rest buys
    nothing).

Only what some shelf sells is bought (`economy.SHELVES`). Level 0 keeps the occupation's kit;
a beast is never outfitted.

`light_the_band` makes sure a band brings a light to a dark field: `Battle` calls it on every
side the player does not play.
"""

import random

from . import economy, items

KIT_BUDGET = {0: 56, 1: 67, 2: 120, 3: 216, 4: 344, 5: 1054, 6: 1995, 7: 2960, 8: 5741}
ARMOR_SHARE = 0.5
WEAPON_SHARE = 0.35
WEAPON_SPREAD = 0.5
RANGED_SHARE = 0.5
TWO_HANDED_SHARE = 0.5
POTION = "Minor Healing Potion"
POTION_CAP = 3
STRENGTH, FINESSE, RANGED = "strength", "finesse", "ranged"
_HEAVY = "heavy"                       # Strength with a two-handed blade
_LIGHTS = (items.TORCH_ITEM, items.LANTERN_ITEM)

_SOLD = sorted({name for shelf in economy.SHELVES.values() for name in shelf},
               key=lambda name: -economy.buy_price(name))


def budget(level):
    """Copper of kit a body of racial `level` carries; past the table, its last row."""
    return KIT_BUDGET[max(0, min(level, max(KIT_BUDGET)))]


def _price(name):
    return economy.buy_price(name) if name else 0


def _armor_ac(unit, name):
    """The AC `name` (None: none worn) adds over a bare body, Dex counted under its cap."""
    dex = unit.mod_dexterity
    if name is None:
        return dex
    armor = items.get(name)
    return armor.ac + (dex if armor.max_dex is None else min(dex, armor.max_dex))


def _armor(unit, cap):
    """Put on the armour within `cap` that adds the most AC, the cheapest of those, if `unit`
    wears it unencumbered and it beats what it has on."""
    worn = unit.equipped_armor
    best = (_armor_ac(unit, worn), -_price(worn))
    choice = worn
    for name in _SOLD:
        if not items.is_armor(name) or _price(name) > cap:
            continue
        key = (_armor_ac(unit, name), -_price(name))
        if key <= best:
            continue
        unit.equipped_armor = name
        unit._derive_combat()
        if not unit.encumbered:
            best, choice = key, name
        unit.equipped_armor = worn
        unit._derive_combat()
    unit.equipped_armor = choice
    unit._derive_combat()


def archetype(unit, rng=random):
    """How `unit` fights: `STRENGTH`, `FINESSE` or `RANGED` (see the module)."""
    if unit.mod_strength > unit.mod_dexterity:
        return STRENGTH
    return RANGED if rng.random() < RANGED_SHARE else FINESSE


def _fits(name, style):
    it = items.get(name)
    if style == RANGED:
        return bool(it.range)
    if it.range:
        return False
    if style == FINESSE:
        return it.hands == 1 and it.finesse
    return not it.finesse and it.hands == (2 if style == _HEAVY else 1)


def _snapshot(unit):
    return unit.equipped_weapon, unit.equipped_offhand, [inst.copy() for inst in unit._base_inventory]


def _restore(unit, snap):
    unit.equipped_weapon, unit.equipped_offhand = snap[0], snap[1]
    unit._base_inventory = [inst.copy() for inst in snap[2]]
    unit._derive_combat()


def _arm(unit, name, style):
    """Wield `name` with what its style carries beside it: a Quiver for a bow, a light in a free
    off hand for a one-handed blade (the Lantern from the pack, else a Torch). -> copper the
    extras cost."""
    unit.equipped_weapon = None
    unit.give_to_hand(name)
    cost = 0
    if style == RANGED:
        if not unit.has_item(items.AMMO_ITEM):
            unit.give_to_pack(items.AMMO_ITEM)
            cost = _price(items.AMMO_ITEM)
    elif not unit.equipped_offhand and items.get(name).hands == 1:
        cost = _light(unit)
    unit._derive_combat()
    return cost


def _light(unit):
    """Put a light in `unit`'s off hand: the Lantern from the pack, else a Torch. -> its cost."""
    if unit.has_item(items.LANTERN_ITEM):
        unit.remove_named(items.LANTERN_ITEM)
        unit.equipped_offhand = items.LANTERN_ITEM
        return 0
    unit.equipped_offhand = items.TORCH_ITEM
    return _price(items.TORCH_ITEM)


def _candidates(unit, style, cap):
    """Weapons of `style` within `cap` (the one in hand costs nothing more) that `unit` carries
    with their extras unencumbered, dearest first."""
    held = unit.equipped_weapon
    snap = _snapshot(unit)
    out = []
    for name in _SOLD:
        if not items.is_weapon(name) or not _fits(name, style):
            continue
        if name != held and (_price(name) > cap or not unit.can_wield(name)):
            continue
        _arm(unit, name, style)
        if not unit.encumbered:
            out.append(name)
        _restore(unit, snap)
    return out


def _weapon(unit, cap, rng):
    """Arm `unit` by its archetype within `cap`. -> copper spent besides the weapon (light, quiver)."""
    style = archetype(unit, rng)
    if style == STRENGTH and rng.random() < TWO_HANDED_SHARE:
        style = _HEAVY
    fits = _candidates(unit, style, cap)
    if not fits and style in (RANGED, _HEAVY):
        style = FINESSE if style == RANGED else STRENGTH
        fits = _candidates(unit, style, cap)
    if not fits:
        return 0
    if style != FINESSE:
        floor = _price(fits[0]) * WEAPON_SPREAD
        fits = [n for n in fits if _price(n) >= floor]
    return _arm(unit, rng.choice(fits), style)


def _free_hand(unit):
    held = items.get(unit.equipped_weapon) if unit.equipped_weapon else None
    return not unit.equipped_offhand and (held is None or held.hands == 1)


def light_the_band(units):
    """If no outfitted humanoid of the band (racial level 1 and up, as `outfit` arms them) holds
    a light, hand one a Torch (its Lantern if it packs one): the first with a free off hand,
    else the first generated two-handed fighter, who swaps its blade for the dearest one-handed
    weapon it wields within the blade's price."""
    band = [u for u in units if u.race.get("kind") != "beast" and u.racial_level > 0]
    if not band or any(u.equipped_offhand in _LIGHTS for u in band):
        return
    for u in band:
        if _free_hand(u):
            _light(u)
            u._derive_combat()
            return
    for u in band:
        held = items.get(u.equipped_weapon) if u.equipped_weapon else None
        if getattr(u, "npc_slug", None) or held is None or held.range or held.hands < 2:
            continue
        fits = _candidates(u, STRENGTH, _price(u.equipped_weapon))
        if fits:
            _arm(u, fits[0], STRENGTH)
            return


def _potions(unit, n):
    """Pack up to `n` potions, one at a time, stopping before the overload."""
    packed = 0
    while packed < n:
        unit.give_to_pack(POTION)
        unit._derive_combat()
        if unit.encumbered:
            unit.remove_named(POTION)
            unit._derive_combat()
            break
        packed += 1
    return packed


def outfit(unit, level, rng=random):
    """Spend `budget(level)` on `unit`'s kit (see the module). Returns the copper it carries in kit."""
    if unit.race.get("kind") == "beast" or level <= 0:
        return _price(unit.equipped_weapon) + _price(unit.equipped_armor)
    total = budget(level)
    _armor(unit, total * ARMOR_SHARE)
    extra = _weapon(unit, total * WEAPON_SHARE, rng)
    spent = _price(unit.equipped_weapon) + _price(unit.equipped_armor) + extra
    potions = _potions(unit, min(POTION_CAP, int((total - spent) // _price(POTION))))
    return spent + potions * _price(POTION)

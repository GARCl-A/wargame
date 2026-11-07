"""Draw and stow: what the two hands hold in a fight, and the pack they swap with.

The hands are the weapon hand and the off hand (a shield, a torch or a lantern). `Draw` takes one item
from the combatant's own pack into the hand it fits and the item that hand held goes back to the pack, never
to the ground. A two-handed weapon takes both hands, so what they held is stowed in the same action; the other
way round, drawing a one-handed item over a two-handed weapon stows it and leaves the other hand empty for the
next action. `stow:weapon` and `stow:offhand` empty one hand.
"""

from dataclasses import dataclass

from . import data, i18n, items

STOW = "stow:"
LIGHTS = (data.TORCH_ITEM, data.LANTERN_ITEM)


@dataclass(frozen=True)
class Option:
    target: str          # the item's name to draw, or STOW + "weapon" / STOW + "offhand"
    qty: int = 1         # how many of it the pack holds
    reason: str = ""     # why it cannot be drawn now ("" when it can)

    @property
    def stow(self):
        return self.target.startswith(STOW)

    @property
    def ok(self):
        return not self.reason


def _drawable(name):
    return items.is_weapon(name) or items.is_shield(name) or name in LIGHTS


def hands(actor):
    """(weapon, off hand) the actor holds now: item names, None for an empty hand."""
    weapon = actor.weapon_name if actor.weapon_hand else None
    if actor.torch_hand:
        return weapon, data.TORCH_ITEM
    if actor.lantern_hand:
        return weapon, data.LANTERN_ITEM
    shield = actor.equipped_offhand
    two_handed = weapon is not None and items.get(weapon).hands >= 2
    return weapon, shield if shield and items.is_shield(shield) and not two_handed else None


def options(actor):
    """Every way to change the hands: each kind of drawable item in the actor's own pack, then a stow per
    occupied hand. A weapon its body is too small to wield is listed with the reason."""
    counts = {}
    for name in actor.inventory:
        if _drawable(name):
            counts[name] = counts.get(name, 0) + 1
    out = []
    for name, qty in counts.items():
        too_big = items.is_weapon(name) and not actor.char.can_wield(name)
        out.append(Option(name, qty, i18n.t("action.draw.too_big") if too_big else ""))
    weapon, off = hands(actor)
    if weapon:
        out.append(Option(STOW + "weapon"))
    if off:
        out.append(Option(STOW + "offhand"))
    return out


def drawable(actor):
    """The items the actor could draw now (no stow)."""
    return [o for o in options(actor) if not o.stow and o.ok]


def result(actor, target):
    """(weapon, off hand) the hands hold once `target` is done."""
    weapon, off = hands(actor)
    if target == STOW + "weapon":
        return None, off
    if target == STOW + "offhand":
        return weapon, None
    if items.is_weapon(target):
        return target, None if items.get(target).hands >= 2 else off
    if weapon and items.get(weapon).hands >= 2:
        weapon = None
    return weapon, target


def stowed(actor, target):
    """The items the hands hand back to the pack for `target`."""
    weapon, off = hands(actor)
    new_weapon, new_off = result(actor, target)
    drew_weapon = not target.startswith(STOW) and items.is_weapon(target)
    drew_off = not target.startswith(STOW) and not drew_weapon
    out = []
    if weapon and (new_weapon != weapon or drew_weapon):
        out.append(weapon)
    if off and (new_off != off or drew_off):
        out.append(off)
    return out


def _shield_ac(name):
    return items.get(name).ac if name and items.is_shield(name) else 0


def carry_back(member, combatant):
    """After the fight: `member` keeps the hands and the weapons, shields and lights in the pack as the
    combatant left them."""
    member.equipped_weapon, member.equipped_offhand = hands(combatant)
    member._base_inventory = [it for it in member._base_inventory if not _drawable(it[0])]
    for name in dict.fromkeys(n for n in combatant.inventory if _drawable(n)):
        member.give_to_pack(name, combatant.inventory.count(name))


def apply(actor, target):
    """Put `target` in its hand (see the module). -> the items stowed. The caller spends the action."""
    weapon, off = hands(actor)
    new_weapon, new_off = result(actor, target)
    back = stowed(actor, target)
    if not target.startswith(STOW):
        actor.inventory.remove(target)
    actor.inventory.extend(back)
    actor.drew = True
    if weapon in back:
        if actor.crossbow_loaded:
            actor.ammo += 1
        actor.crossbow_loaded = False
        actor.weapon_hand = False
        actor.weapon_name, actor._held = None, None
    if new_weapon and (new_weapon != weapon or weapon in back):
        actor.weapon_name, actor._held = new_weapon, items.get(new_weapon)
        actor.weapon_hand = True
        actor.let_go = None
    if off in back or new_off != off:
        actor.equipped_offhand = new_off
        actor.torch_hand = new_off == data.TORCH_ITEM
        actor.lantern_hand = new_off == data.LANTERN_ITEM
        actor.shield_ac_delta = _shield_ac(new_off) - _shield_ac(actor.char.equipped_offhand)
    return back

"""The persistent loadout: the two hands, the tongue, the armor slot and the pack.

A weapon is an item; the weapon hand holds one (1-2 hands), the off hand a
torch. `equipped_weapon` / `equipped_offhand` are what every battle re-seeds a
Combatant from. The pack is `list[ItemInstance]` stacks, one row per distinct
name, so an `idx` addresses a stack, not a physical item.
"""

from . import data, items
from .data import roll


COIN_HANDFUL = 10          # coins moved per step when spreading a purse (0.05 kg)


def pack_from_raw(raw):
    """Build a stacked list of ItemInstance from a save field that may be
    an old flat list[str], a list[[name, qty]], a list[dict], or list[ItemInstance]."""
    if not raw:
        return []
    if isinstance(raw[0], str):
        order, counts = [], {}
        for name in raw:
            if name not in counts:
                order.append(name)
                counts[name] = 0
            counts[name] += 1
        return [items.create_instance(name, qty=counts[name]) for name in order]
    return [items.ItemInstance.from_raw(entry) for entry in raw]


def stack_add(pack, name, qty=1, charges=None, days_old=0):
    """Add `qty` of `name` (str or ItemInstance) to a stacked pack in place,
    merging into an existing stack of the same name and state."""
    if isinstance(name, items.ItemInstance):
        inst = name
    else:
        if charges is None:
            charges = getattr(name, "charges", None)
        inst = items.create_instance(name, qty=qty, charges=charges, days_old=days_old)
    for i, it in enumerate(pack):
        if isinstance(it, items.ItemInstance):
            if it.id == inst.id and it.days_old == inst.days_old and it.charges == inst.charges:
                it.qty += inst.qty
                return
        elif isinstance(it, tuple):
            if it[0] == inst.name:
                pack[i] = (it[0], it[1] + inst.qty)
                return
    pack.append(inst)


def stack_take(pack, idx, qty=1):
    """Remove up to `qty` from the stack at `idx` in place, dropping the row
    once it empties. Returns `(name, removed, remaining)`."""
    entry = pack[idx]
    if isinstance(entry, items.ItemInstance):
        name = items.stack_name(entry)
        removed = min(qty, entry.qty)
        entry.qty -= removed
        if entry.qty <= 0:
            pack.pop(idx)
            remaining = 0
        else:
            remaining = entry.qty
        return name, removed, remaining
    name, held = entry
    removed = min(qty, held)
    remaining = held - removed
    if remaining <= 0:
        pack.pop(idx)
    else:
        pack[idx] = (name, remaining)
    return name, removed, remaining


def split_stack(pack, idx, qty):
    """Peel `qty` off the stack at `idx` into its own stack right after it.
    False (and nothing changes) unless `0 < qty < held`."""
    entry = pack[idx]
    if isinstance(entry, items.ItemInstance):
        if not (0 < qty < entry.qty):
            return False
        entry.qty -= qty
        split_inst = entry.copy()
        split_inst.qty = qty
        pack.insert(idx + 1, split_inst)
        return True
    name, held = entry
    if not (0 < qty < held):
        return False
    pack[idx] = (name, held - qty)
    pack.insert(idx + 1, (name, qty))
    return True


class LoadoutMixin:
    # ------------------------------------------------------------------ #
    # roster management: shuffling items between the two hands and the   #
    # pack. A weapon is an item; the weapon hand holds one (1-2 hands),  #
    # the off hand a torch. `equipped_weapon` / `equipped_offhand` are   #
    # the persistent loadout every battle re-seeds a Combatant from.     #
    # ------------------------------------------------------------------ #
    @staticmethod
    def is_weapon(name):
        return items.is_weapon(name)

    @staticmethod
    def fits_offhand(name):
        return items.is_shield(name) or items.is_light_source(name)


    @staticmethod
    def fits_armor(name):
        return items.is_armor(name)

    def can_wield(self, name):
        """Checks if this unit can wield `name`. Large weapons require Large size
        (e.g. Centaur) or the Giant's Grip talent (Goliath)."""
        if not self.is_weapon(name):
            return False
        w = items.get(name)
        if not w:
            return False
        if w.size == "Large":
            return self.size in ("Large", "Huge") or self.has_talent("giant_grip")
        return True

    def fits_tongue(self, name):
        """The Tongue slot takes one 1-handed weapon (it is a single extra limb),
        and only if this character has the `tongue` talent and can wield it."""
        w = items.get(name)
        return (self.has_tongue and self.can_wield(name)
                and w is not None and w.hands == 1)

    def give_to_hand(self, name):
        """Wield `name`; the weapon already held goes to the pack. A 2-handed
        weapon also bumps whatever was in the off hand. No-op if not a weapon
        or cannot be wielded due to size."""
        if not self.can_wield(name):
            return False
        if self.equipped_weapon:
            self._pack_add(self.equipped_weapon)
        self.equipped_weapon = name
        w = items.get(name)
        if w and w.hands >= 2 and self.equipped_offhand:
            self._pack_add(self.equipped_offhand)
            self.equipped_offhand = None
        return True

    def give_to_offhand(self, name):
        if not self.fits_offhand(name):
            return False
        if self.equipped_offhand:
            self._pack_add(self.equipped_offhand)
        self.equipped_offhand = name
        return True

    def give_to_tongue(self, name):
        """Hold `name` in the Tongue; the weapon already there goes to the pack.
        No-op if it does not fit (not a 1-handed weapon, or no Tongue talent)."""
        if not self.fits_tongue(name):
            return False
        if self.equipped_tongue:
            self._pack_add(self.equipped_tongue)
        self.equipped_tongue = name
        return True

    # ------------------------------------------------------------------ #
    # the pack itself: `list[(name, qty)]` stacks, one row per distinct   #
    # name (`_pack_add` merges into an existing row rather than ever      #
    # appending a duplicate) -- so `idx` below addresses a stack, not a   #
    # physical item.                                                     #
    # ------------------------------------------------------------------ #
    def _pack_add(self, name, qty=1, charges=None, days_old=0):
        stack_add(self._base_inventory, name, qty, charges=charges, days_old=days_old)

    def give_to_pack(self, name, qty=1, charges=None, days_old=0):
        self._pack_add(name, qty, charges=charges, days_old=days_old)

    def _charges_of(self, item_name):
        inst = next((it for it in self._base_inventory
                     if isinstance(it, items.ItemInstance) and it.name == item_name), None)
        if inst is None:
            return 0
        return items.get(item_name).max_charges if inst.charges is None else inst.charges

    def _set_charges_of(self, item_name, value):
        """Write `value` to one copy of `item_name`, peeling it off its stack first so
        its siblings keep their own charges. No-op with none carried."""
        idx = next((i for i, it in enumerate(self._base_inventory)
                    if isinstance(it, items.ItemInstance) and it.name == item_name), None)
        if idx is None:
            return
        inst = self._base_inventory[idx]
        if inst.qty > 1:
            inst.qty -= 1
            inst = inst.copy()
            inst.qty = 1
            self._base_inventory.insert(idx, inst)
        inst.charges = max(0, int(value))

    @property
    def quiver_charges(self):
        return self._charges_of(data.AMMO_ITEM)

    @quiver_charges.setter
    def quiver_charges(self, value):
        self._set_charges_of(data.AMMO_ITEM, value)

    @property
    def first_aid_charges(self):
        return self._charges_of(data.FIRST_AID_ITEM)

    @first_aid_charges.setter
    def first_aid_charges(self, value):
        self._set_charges_of(data.FIRST_AID_ITEM, value)

    def pack_tag(self, name):
        """The pill under a pack row's name; a quiver or kit also shows what is left in it."""
        tag = items.item_tag(name)
        if name == data.AMMO_ITEM:
            return f"{tag} · {self.quiver_charges}/{data.QUIVER_AMMO}"
        if name == data.FIRST_AID_ITEM:
            return f"{tag} · {self.first_aid_charges}/{data.FIRST_AID_CHARGES}"
        return tag

    def take_from_hand(self):
        name, self.equipped_weapon = self.equipped_weapon, None
        return name

    def take_from_offhand(self):
        name, self.equipped_offhand = self.equipped_offhand, None
        return name

    def take_from_tongue(self):
        name, self.equipped_tongue = self.equipped_tongue, None
        return name

    def give_to_armor(self, name):
        """Don `name`; whatever was worn goes back to the pack. Armor changes the
        derived AC and speed, so re-derive. No-op if `name` is not armor."""
        if not self.fits_armor(name):
            return False
        if self.equipped_armor:
            self._pack_add(self.equipped_armor)
        self.equipped_armor = name
        self._derive_combat()
        return True

    def take_from_armor(self):
        name, self.equipped_armor = self.equipped_armor, None
        self._derive_combat()
        return name

    def _pack_take(self, idx, qty=1):
        """Remove up to `qty` from the stack at `idx`, deleting the row once
        it empties, and reconcile `locked_items` against what's left. Returns
        `(name, removed)`; shared by `take_from_pack` (index) and
        `remove_named` (name)."""
        name, removed, held_after = stack_take(self._base_inventory, idx, qty)
        if self.locked_items.get(name, 0) > held_after:
            self.locked_items[name] = held_after
            if not held_after:
                del self.locked_items[name]
        return name, removed

    def take_from_pack(self, idx, qty=1):
        name, _ = self._pack_take(idx, qty)
        self._derive_combat()
        return name

    def split_pack(self, idx, qty):
        """Peel `qty` off the stack at `idx` into its own new stack right
        after it -- lets a partial quantity be moved/locked on its own
        without touching the rest. `locked_items` stays keyed by name (a
        lock counts against the total across every stack of that name, see
        `locked_of`), so splitting never changes how much is locked, only
        how it's grouped. No-op (`False`) unless `0 < qty < held` -- moving
        the whole stack isn't a split, and `_pack_add` would just merge a
        same-named stack of qty 0 straight back in."""
        return split_stack(self._base_inventory, idx, qty)

    def remove_named(self, name, qty=1):
        """Remove up to `qty` of `name` by name rather than index -- for
        callers (missions, chests, the ledger, ...) that know what they want
        gone but not where it sits. Returns how many were actually removed."""
        idx = next((i for i, (n, _) in enumerate(self._base_inventory) if n == name), None)
        if idx is None:
            return 0
        _, removed = self._pack_take(idx, qty)
        return removed

    def count_of(self, name):
        """Total quantity of `name` held in the pack (0 if none)."""
        return sum(q for n, q in self._base_inventory if n == name)

    def has_item(self, name):
        return self.count_of(name) > 0

    def locked_of(self, name):
        """How many of `name` in this pack are locked against distribute_load --
        clamped to what's actually held, so a lock never outlives its items."""
        return min(self.locked_items.get(name, 0), self.count_of(name))

    @property
    def gold(self):
        """Copper coins carried: the size of the "Copper Coin" stacks in the pack,
        so money is an ordinary item -- it weighs, splits and moves like one."""
        return self.count_of(items.COIN_ITEM)

    @gold.setter
    def gold(self, amount):
        amount = max(0, int(amount))
        held = self.gold
        if amount > held:
            self.give_to_pack(items.COIN_ITEM, amount - held)
        while held > amount:                      # a split purse spans several stacks
            held -= self.remove_named(items.COIN_ITEM, held - amount)

    @property
    def inventory(self):
        """Flat / active view of the character's pack items as ItemInstances."""
        return self._base_inventory

    @inventory.setter
    def inventory(self, val):
        self._base_inventory = pack_from_raw(val)

    def toggle_lock(self, name):
        """Lock the whole stack of `name`, or unlock it if already fully locked."""
        held = self.count_of(name)
        if held == 0:
            return
        if self.locked_of(name) >= held:
            del self.locked_items[name]
        else:
            self.locked_items[name] = held

    @property
    def known_recipes(self):
        return self.recipes + [r for r in items.COMMON_RECIPES if r not in self.recipes]

    @staticmethod
    def crafting_goal(recipe):
        """The progress one batch of `recipe` takes."""
        recipe_data = items.CRAFTING_RECIPES[recipe]
        total = recipe_data.complexity
        for mat in recipe_data.materials:
            mat_item = items.get(mat)
            total += mat_item.price if mat_item else 10
        return total

    def progress_crafting(self):
        """Roll 1d20 + INT to advance crafting. Returns (progress_made, is_done)."""
        if not self.crafting_target:
            return 0, False
        target_val = self.crafting_goal(self.crafting_target)
        recipe_data = items.CRAFTING_RECIPES[self.crafting_target]
        station = recipe_data.station
        bonus = self.talent_bonus("craft_bonus") + self.craft_bonuses.get(station, 0)
        prog = roll(1, 20) + self.mod_intelligence + bonus
        prog = max(1, prog)
        self.crafting_progress += prog
        
        is_done = self.crafting_progress >= target_val
        if is_done:
            self.give_to_pack(self.crafting_target, recipe_data.yield_qty)
            self.crafting_target = None
            self.crafting_progress = 0
        return prog, is_done


def flatten_pack(unit):
    """`unit`'s pack as a flat `list[str]`, one entry per physical item --
    only for the battle boundary (`Combatant.inventory` stays flat; nothing
    in a fight needs stacked display, just per-charge checks)."""
    return [name for name, qty in unit._base_inventory
            if name != items.COIN_ITEM for _ in range(qty)]


def distribute_load(units, share_coins=True, creatures=()):
    """Rebalance pack items across `units` by free carrying capacity, heaviest
    first -- locked items (see `Unit.locked_items`/`toggle_lock`) stay put on
    their current owner instead of joining the pool. Item granularity, not
    whole-stack: a locked portion of a stack stays put, the rest still moves.
    With `share_coins`, unlocked coins are poured out in small handfuls onto
    whoever is lightest, since they weigh too; without it every purse stays
    with its owner. `creatures` (a group's animals and wagons) share the load
    too, the ones with room to carry; coins stay on people."""
    bearers = [*units, *(c for c in creatures if c.capacity > 0)]
    pool = []
    coins = 0
    for u in bearers:
        keep, move = [], []
        for it in u._base_inventory:
            name, qty = it[0], it[1]
            locked = u.locked_of(name)
            if name == items.COIN_ITEM and share_coins:
                coins += qty - locked
            elif name == items.COIN_ITEM:
                locked = qty
            if locked:
                if isinstance(it, items.ItemInstance):
                    locked_inst = it.copy()
                    locked_inst.qty = locked
                    keep.append(locked_inst)
                else:
                    keep.append((name, locked))
            if qty > locked and not (name == items.COIN_ITEM and share_coins):
                if isinstance(it, items.ItemInstance):
                    for _ in range(qty - locked):
                        c = it.copy()
                        c.qty = 1
                        move.append(c)
                else:
                    move.extend([name] * (qty - locked))
        u._base_inventory[:] = keep
        pool.extend(move)
        u._derive_combat()

    pool.sort(key=items.item_weight, reverse=True)
    for item in pool:
        best = min(bearers, key=lambda m: m.load / max(1.0, m.carry_normal))
        best.give_to_pack(item)
        best._derive_combat()

    while coins:
        handful = min(coins, COIN_HANDFUL)
        best = min(units, key=lambda m: m.load / max(1.0, m.carry_normal))
        best.give_to_pack(items.COIN_ITEM, handful)
        best._derive_combat()
        coins -= handful

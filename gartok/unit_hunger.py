"""Hunger and eating: one meal a day, or the body starts giving out.

Mixed into `unit.Unit`; see RULES.md (the Leshy "Autotroph" is exempt).
"""

from . import data, items


def take_ration(pack):
    """Eat one ration out of `pack` (a stacked pack list, in place). Oldest fresh
    food first (highest days_old), tie-broken by cheapest, then pack order; Rotten
    Food only when nothing fresh is left. Returns the food's name, or None."""
    fresh_candidates = []
    rotten_candidates = []
    for i, entry in enumerate(pack):
        if isinstance(entry, items.ItemInstance):
            is_food = entry.defn.food or items.is_food(entry.defn.id)
            is_rotten = entry.is_rotten() or entry.name.startswith("Rotten Food")
            days_old = entry.days_old
            price = entry.defn.price
        elif isinstance(entry, (tuple, list)):
            raw_name = entry[0]
            base = raw_name.split(" (")[0]
            it = items.get(base)
            is_food = (it.food if it else False) or items.is_food(base)
            is_rotten = raw_name.startswith("Rotten Food")
            days_old = 0
            if " (" in raw_name and raw_name.endswith("d)"):
                try:
                    days_old = int(raw_name.split(" (")[1][:-2])
                except ValueError:
                    days_old = 0
            price = it.price if it else 0
        else:
            raw_name = str(entry)
            base = raw_name.split(" (")[0]
            it = items.get(base)
            is_food = (it.food if it else False) or items.is_food(base)
            is_rotten = raw_name.startswith("Rotten Food")
            days_old = 0
            if " (" in raw_name and raw_name.endswith("d)"):
                try:
                    days_old = int(raw_name.split(" (")[1][:-2])
                except ValueError:
                    days_old = 0
            price = it.price if it else 0

        if is_food and not is_rotten:
            # Sort key: (-days_old: oldest first, price: cheapest first, i: pack order)
            fresh_candidates.append((-days_old, price, i))
        elif is_rotten:
            rotten_candidates.append(i)

    if fresh_candidates:
        fresh_candidates.sort()
        idx = fresh_candidates[0][2]
    elif rotten_candidates:
        idx = rotten_candidates[0]
    else:
        idx = None

    if idx is not None:
        entry = pack[idx]
        if isinstance(entry, items.ItemInstance):
            name = entry.name
            if entry.qty > 1:
                entry.qty -= 1
            else:
                pack.pop(idx)
        else:
            name, qty = entry
            if qty > 1:
                pack[idx] = (name, qty - 1)
            else:
                pack.pop(idx)
        return "Rotten Food" if name.startswith("Rotten Food") else name
    return None


class HungerMixin:
    # ------------------------------------------------------------------ #
    # hunger: one meal a day, or the body starts giving out               #
    #   (see RULES.md; the Leshy "Autotroph" is exempt)                   #
    # ------------------------------------------------------------------ #
    @property
    def hunger_level(self):
        """0 fed · 1 hungry · 2 starving · 3 starving to death."""
        if self._ability.id == "autotroph":
            return 0
        return min(self.unfed_days, 3)

    @property
    def hunger_attribute_penalty(self):
        return (0, -2, -4, -4)[self.hunger_level]

    @property
    def hunger_label(self):
        return ("", "hungry", "starving", "starving to death")[self.hunger_level]

    @property
    def incapacitated(self):
        """Collapsed from hunger -- cannot be sent into a fight."""
        return self.hunger_level >= 3

    def _take_ration(self, larder=None):
        """Eat one ration: this character's own pack first, then each pack in
        `larder` (guild-mates sharing food, the group's wagon)."""
        for pack in (self._base_inventory, *(larder or ())):
            name = take_ration(pack)
            if name is not None:
                return name
        return None

    def consume_daily_food(self, larder=None):
        """Resolve one day's meal: eat a ration (own pack, then `larder`) if one
        is to be had, else go hungrier. Returns 'ate' | 'hungry' | 'dead'. The
        caller re-derives combat stats and clears the dead from the roster."""
        if self._ability.id == "autotroph":
            return "ate"
        food = self._take_ration(larder)
        if food:
            self.unfed_days = 0
            if food == "Rotten Food" and self._ability.id != "strong_stomach":
                self.sick = True
            return "ate"
        self.unfed_days += 1
        return "dead" if self.unfed_days >= data.STARVATION_DEATH_DAYS else "hungry"

    def eat_now(self, larder=None):
        """Eat a ration this instant -- the guild stopping to have a meal rather
        than waiting for the day to turn. Only bites if the character is actually
        hungry and a ration is to be had (own pack, then `larder`); never advances
        hunger. Returns True if a meal was eaten. The caller re-derives combat."""
        if self.hunger_level == 0:
            return False
        food = self._take_ration(larder)
        if not food:
            return False
        self.unfed_days = 0
        if food == "Rotten Food" and self._ability.id != "strong_stomach":
            self.sick = True
        return True

    @property
    def rations(self):
        """Meals sitting in this character's pack."""
        return sum(qty for name, qty in self._base_inventory
                   if items.is_food(name.split(" (")[0]))

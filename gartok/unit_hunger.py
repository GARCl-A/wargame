"""Hunger and eating: one meal a day, or the body starts giving out.

Mixed into `unit.Unit`; see RULES.md (the Leshy "Autotroph" is exempt).
"""

from . import data, items


def take_ration(pack, allow_rotten=True):
    """Eat one ration out of `pack` (a stacked pack list, in place). Fresh food nearing
    spoilage first (lowest remaining shelf life: lifespan - days_old), tie-broken by cheapest,
    then pack order; Rotten Food only when nothing fresh is left (and `allow_rotten` is True).
    Returns the food's name, or None."""
    fresh_candidates = []
    rotten_candidates = []
    for i, entry in enumerate(pack):
        is_food = entry.defn.food or items.is_food(entry.defn.id)
        is_rotten = entry.is_rotten() or entry.name.startswith("Rotten Food")
        days_old = entry.days_old
        price = entry.defn.price
        lifespan = entry.defn.lifespan

        if is_food and not is_rotten:
            rem_life = (lifespan - days_old) if lifespan is not None else 999999
            fresh_candidates.append((rem_life, price, i))
        elif is_rotten:
            rotten_candidates.append(i)

    if fresh_candidates:
        fresh_candidates.sort()
        idx = fresh_candidates[0][2]
    elif allow_rotten and rotten_candidates:
        idx = rotten_candidates[0]
    else:
        idx = None

    if idx is not None:
        entry = pack[idx]
        name = entry.name
        if entry.qty > 1:
            entry.qty -= 1
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

    def _take_ration(self, larder=None, allow_rotten=True):
        """Eat one ration across the shared larder (eater's pack and `larder` evaluated together):
        fresh food nearing spoilage first (lowest remaining shelf life: lifespan - days_old),
        tie-broken by cheapest, preference for eater's own pack, then pack order.
        Only when nothing fresh is left in any pack does it fall back to Rotten Food (if allow_rotten)."""
        packs = (self._base_inventory, *(larder or ()))
        fresh_candidates = []
        rotten_candidates = []
        for p_idx, pack in enumerate(packs):
            for i, entry in enumerate(pack):
                is_food = entry.defn.food or items.is_food(entry.defn.id)
                is_rotten = entry.is_rotten() or entry.name.startswith("Rotten Food")
                days_old = entry.days_old
                price = entry.defn.price
                lifespan = entry.defn.lifespan

                if is_food and not is_rotten:
                    rem_life = (lifespan - days_old) if lifespan is not None else 999999
                    fresh_candidates.append((rem_life, price, p_idx, i))
                elif is_rotten:
                    rotten_candidates.append((p_idx, i))

        target = None
        if fresh_candidates:
            fresh_candidates.sort()
            target = fresh_candidates[0][2:]
        elif allow_rotten and rotten_candidates:
            target = rotten_candidates[0]

        if target is not None:
            p_idx, i = target
            pack = packs[p_idx]
            entry = pack[i]
            name = entry.name
            if entry.qty > 1:
                entry.qty -= 1
            else:
                pack.pop(i)
            return "Rotten Food" if name.startswith("Rotten Food") else name
        return None

    def consume_daily_food(self, larder=None):
        """Resolve one day's meal: eat a ration (own pack and `larder` evaluated together)
        if one is to be had, else go hungrier. Rotten Food is eaten automatically only as
        a last resort against starvation death (on the day before dying).
        Returns 'ate' | 'hungry' | 'dead'. The caller re-derives combat stats and clears
        the dead from the roster."""
        if self._ability.id == "autotroph":
            return "ate"
        allow_rotten = self.unfed_days >= data.STARVATION_DEATH_DAYS - 1
        food = self._take_ration(larder, allow_rotten=allow_rotten)
        if food:
            self.unfed_days = 0
            if food == "Rotten Food" and self._ability.id != "strong_stomach":
                self.sick = True
                self._apply_attributes()
            return "ate"
        self.unfed_days += 1
        return "dead" if self.unfed_days >= data.STARVATION_DEATH_DAYS else "hungry"

    def eat_now(self, larder=None, allow_rotten=True):
        """Eat a ration this instant -- the guild stopping to have a meal rather
        than waiting for the day to turn. Only bites if the character is actually
        hungry and a ration is to be had (own pack, then `larder`); never advances
        hunger. Returns True if a meal was eaten. The caller re-derives combat."""
        if self.hunger_level == 0:
            return False
        food = self._take_ration(larder, allow_rotten=allow_rotten)
        if not food:
            return False
        self.unfed_days = 0
        if food == "Rotten Food" and self._ability.id != "strong_stomach":
            self.sick = True
            self._apply_attributes()
        return True

    @property
    def rations(self):
        """Meals sitting in this character's pack."""
        return sum(qty for name, qty in self._base_inventory
                   if items.is_food(name.split(" (")[0]))

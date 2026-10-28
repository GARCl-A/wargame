"""A workbench with no window (the Forge, the Carpenter, the Apothecary's craft, the Library's writing, a
kitchen): who in the band works at this station, their recipes, what the band's packs lack, and a stint put
in with the group waiting or the crafter gone off alone.

Materials come from the whole group's packs, wagons and animals (padlocked items excepted) and are consumed
immediately; progress is 1d20+INT an hour. pygame's `CraftingScreen` is the window over `Bench` and
`web/craft_tab.py` the browser's.
"""

from collections import Counter

from . import items, solo
from .unit_loadout import pooled_unlocked

WAIT_HOURS = (1, 4, 8)          # a stint the whole group waits out, here and now
ALONE_HOURS = (4, 8, 16)        # a solo task: the crafter splits off and the map runs the clock


class Bench:
    def __init__(self, guild, group, station="forge"):
        self.guild, self.group, self.station = guild, group, station
        self.selected_crafter = None
        self.refresh()

    def refresh(self):
        """Re-read who can work here after the band changed (a crafter gone off alone, a recipe learnt)."""
        self.crafters = [u for u in self.group.members if any(self._for_station(r) for r in u.known_recipes)]
        if self.selected_crafter not in self.crafters:
            self.selected_crafter = self.crafters[0] if self.crafters else None

    def hub_cards(self):
        known = {r for u in self.crafters for r in u.known_recipes if self._for_station(r)}
        return [{"label": "crafters", "value": f"{len(self.crafters)} of {len(self.group.members)}"},
                {"label": "recipes known", "value": str(len(known))}]

    def _for_station(self, recipe):
        """Is `recipe` worked at this bench's station (any station when it has none)?"""
        found = items.CRAFTING_RECIPES.get(recipe)
        variants = found if isinstance(found, list) else [found] if found else []
        return not self.station or any(rc.station == self.station for rc in variants)

    @property
    def _packs(self):
        return [*self.group.members, *self.group.stores]

    def _get_missing_materials(self, recipe):
        recipe_data = items.get_recipe(recipe)
        if not recipe_data:
            return []
        need = Counter(recipe_data.materials)
        missing = []
        for mat, qty in need.items():
            have = pooled_unlocked(self._packs, mat)
            if have < qty:
                missing.append(f"{qty - have}x {mat}")
        return missing

    def _get_missing_tools(self, recipe):
        recipe_data = items.get_recipe(recipe)
        return items.missing_tools(recipe_data, self._packs) if recipe_data else []

    def _has_materials(self, recipe):
        return not self._get_missing_materials(recipe) and not self._get_missing_tools(recipe)

    def alone_blocker(self, m, recipe_id):
        """Why `m` cannot go off alone to craft `recipe_id`, or None when they can."""
        if len(self.group.members) > 1 and not self.guild.free_slots:
            return "no free group slot"
        if self.guild.craft_blocker(m, recipe_id, [m]) is not None:
            return "not in their own pack"
        return None

    def _recipes(self, m):
        """`(recipe_id, data, active)` for each recipe `m` works at this station."""
        out = []
        for r_name in m.known_recipes:
            found = items.CRAFTING_RECIPES.get(r_name, [])
            variants = found if isinstance(found, (list, tuple)) else [found] if found else []
            for i, r_data in enumerate(variants):
                if not r_data or (self.station and r_data.station != self.station):
                    continue
                recipe_id = f"{r_name}:{i}" if len(variants) > 1 else r_name
                active = m.crafting_target == recipe_id or (len(variants) == 1 and m.crafting_target == r_name)
                out.append((recipe_id, r_data, active))
        return out

    def _work(self, recipe, hours):
        """The picked crafter puts `hours` into `recipe` while the group waits: -> the lines it said."""
        if hours not in WAIT_HOURS:
            raise ValueError(f"no {hours} h stint")
        result = self.guild.crafting_shift(self.selected_crafter, recipe, hours, pool=self._packs)
        return result[0] if isinstance(result, tuple) else result

    def _alone(self, recipe, hours):
        """The picked crafter splits off on a solo task for `hours`: -> `(ok, lines)`."""
        if hours not in ALONE_HOURS:
            raise ValueError(f"no {hours} h stint alone")
        return solo.craft(self.guild, self.group, self.selected_crafter, recipe, hours)

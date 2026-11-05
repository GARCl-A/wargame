"""A workbench with no window (the Forge, the Carpenter, the Apothecary's craft, the Library's writing, a
kitchen): who in the band works at this station, their recipes, what the band's packs lack, and a stint put
in with the group waiting or the crafter gone off alone.

Materials come from the whole group's packs, wagons and animals (padlocked items excepted) and are consumed
immediately; progress is 1d20+INT an hour. `web/craft_tab.py` draws `Bench`.
"""

from collections import Counter

from . import i18n, items, solo, world
from .unit_loadout import pooled_unlocked

WAIT_HOURS = (1, 4, 8)          # a solo task the whole group waits out
ALONE_HOURS = (4, 8, 16)        # a solo task: the crafter splits off and the map runs the clock


NODE_STATION = {"forge": "forge", "carpenter": "carpenter", "apothecary": "apothecary", "library": "scriptorium"}


def stations_at(guild, group):
    """The stations a band can work where it stands: the node's own bench, the house's kitchen once it has
    an oven, the claim's once its hearth can cook, a field campfire while it burns."""
    node = world.node(group.node)
    found = {station for function, station in NODE_STATION.items() if node.has(function)}
    kitchen = ((node.has("property") and guild.house.owned and guild.house.oven)
               or (node.has("claim") and guild.wilds_claim_can_cook)
               or group.has_campfire(guild.clock.seconds))
    return found | {items.CraftingStation.COOKING} if kitchen else found


def blocker(guild, group, recipe):
    """Why `group` cannot work `recipe` where it stands -- the recipe is unknown, nobody in it knows it,
    or the node has no station for it -- or None. The tab's own rules, for a routine's `Craft`."""
    data = items.get_recipe(recipe)
    if data is None:
        return i18n.t("workbench.unknown_recipe", recipe=recipe)
    if not any(recipe.split(":")[0] in u.known_recipes for u in group.members):
        return i18n.t("workbench.nobody_in_group_knows", target=data.target)
    if data.station not in stations_at(guild, group):
        return i18n.t("workbench.no_station_here", station=data.station)
    return None


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
        return [{"label": i18n.lab("crafters"), "value": i18n.t("workbench.of", crafters=len(self.crafters), members=len(self.group.members))},
                {"label": i18n.t("workbench.recipes_known"), "value": str(len(known))}]

    def _for_station(self, recipe):
        """Is `recipe` worked at this bench's station (any station when it has none)?"""
        found = items.CRAFTING_RECIPES.get(recipe)
        variants = found if isinstance(found, list) else [found] if found else []
        return not self.station or any(rc.station == self.station for rc in variants)

    @property
    def _packs(self):
        return self.group.carriers

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
            return i18n.t("workbench.no_free_group_slot")
        if self.guild.craft_blocker(m, recipe_id, self._packs) is not None:
            return i18n.t("workbench.not_in_group_s_stock")
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

    def _wait(self, recipe, hours):
        """The picked crafter puts `hours` into `recipe` while the group waits on a `solo` order,
        every pack feeding the craft: -> `(ok, lines)`."""
        if hours not in WAIT_HOURS:
            raise ValueError(i18n.t("workbench.no_h_stint", hours=hours))
        return solo.craft(self.guild, self.group, self.selected_crafter, recipe, hours, alone=False)

    def _alone(self, recipe, hours):
        """The picked crafter splits off on a solo task for `hours`: -> `(ok, lines)`."""
        if hours not in ALONE_HOURS:
            raise ValueError(i18n.t("workbench.no_h_stint_alone", hours=hours))
        return solo.craft(self.guild, self.group, self.selected_crafter, recipe, hours)

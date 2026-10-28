"""A hub's workbench in the browser (the Smithy's FORGE, the Carpenter's CARPENTRY, the Apothecary's CRAFT,
the Library's WRITE, the house's KITCHEN): on leather who in the band can work here and what the last stint
made, on paper the picked crafter's recipes (what each uses, what the band lacks, the progress) and the hours
to put in, with the group waiting or the crafter gone off alone.

The reads and rules are `workbench.Bench`'s. The verb that runs the
clock lives on `HubSession`, which holds the map.
"""

from collections import Counter

from .. import item_icon, progression
from ..unit_loadout import pooled_unlocked
from ..workbench import ALONE_HOURS, WAIT_HOURS, Bench
from .shop_tab import _portrait

# a node's function -> the station it works at and what is made there
STATIONS = {"forge": ("forge", "forge weapons and armour"),
            "carpenter": ("carpenter", "craft wooden bows, crossbows and tools"),
            "apothecary": ("apothecary", "brew potions and draughts"),
            "library": ("scriptorium", "write dictionaries and translate texts"),
            "kitchen": ("cooking", "cook what the pack carries")}
CRAFT_TABS = {"craft", "forge", "carpenter", "kitchen"}


def _function(key, node):
    return key if key != "craft" else next(f for f in ("forge", "apothecary", "library") if node.has(f))


class CraftTab:
    def __init__(self, guild, group, node, key="craft"):
        self.key = key
        self.station, self.what = STATIONS[_function(key, node)]
        self.s = Bench(guild, group, self.station)
        self.guild, self.group, self.node = guild, group, node
        self.report = []                # what the last stint said
        self.notice = None

    @property
    def crafter(self):
        return self.s.selected_crafter

    def pick(self, uid):
        self.s.refresh()
        u = next((u for u in self.s.crafters if u.uid == uid), None)
        if u is None:
            raise ValueError("nobody by that id works here")
        self.s.selected_crafter = u

    def recipe(self, recipe_id):
        self.s.refresh()
        if self.crafter is None or all(r != recipe_id for r, _, _ in self.s._recipes(self.crafter)):
            raise ValueError(f"no recipe {recipe_id!r} for this crafter here")
        return recipe_id

    def _recipe(self, m, recipe_id, r, active):
        s = self.s
        packs = s._packs
        tools = set(s._get_missing_tools(recipe_id))
        mod = m.mod_intelligence + m.craft_bonus(r.station)
        can = active or s._has_materials(recipe_id)
        return {"id": recipe_id, "target": r.target, "glyph": item_icon.glyph(r.target), "level": r.level,
                "xp": progression.work_xp_hours(1, r.level, m.work_level), "makes": r.yield_qty,
                "uses": [{"name": n, "need": q, "have": pooled_unlocked(packs, n)} for n, q in Counter(r.materials).items()],
                "tools": [{"name": t, "have": t not in tools} for t in r.tools],
                "goal": m.crafting_goal(r), "roll": mod, "active": active,
                "progress": m.crafting_progress if active else 0, "can": can,
                "alone": s.alone_blocker(m, recipe_id) if can else None}

    def state(self):
        self.s.refresh()
        s, m = self.s, self.crafter
        crafters = []
        for u in s.crafters:
            n = len(s._recipes(u))
            mod = u.mod_intelligence + u.craft_bonus(self.station)
            crafters.append({"uid": u.uid, "name": u.name, "portrait": _portrait(u), "picked": u is m,
                             "sub": f"{u.occupation['name']} · d20{mod:+d} · {n} recipe{'s' if n != 1 else ''}",
                             "note": f"working on {u.crafting_target.split(':')[0]}" if u.crafting_target else None})
        notice, self.notice = self.notice, None
        return {"cards": s.hub_cards(), "what": self.what, "crafters": crafters,
                "who": m.name if m else None,
                "recipes": [self._recipe(m, rid, r, a) for rid, r, a in s._recipes(m)] if m else [],
                "wait_hours": list(WAIT_HOURS), "alone_hours": list(ALONE_HOURS),
                "report": self.report, "notice": notice}

"""Vision and light.

Pure functions over the battle state:
- `unit_light` / `ground_light` centralize "this emits light and how far";
- `cell_lit` / `can_see` answer what a unit sees;
- `observers` / `visible_cells` / `enemy_visible` build the on-screen vision
  (what the PLAYER sees now), which is the character's vision, not the player's.
"""

from . import data
from .board import COLS, ROWS, cells, chebyshev


def unit_light(unit):
    """Light radius (squares) the unit emits; 0 if none."""
    if not unit.alive:
        return 0
    if unit.has_torch:
        return data.TORCH_RADIUS
    return max((data.LIGHT_SOURCES.get(it, 0) for it in unit.inventory), default=0)


def ground_light(obj):
    """Light radius of a ground object; 0 if it does not emit."""
    return data.TORCH_RADIUS if obj.is_torch else 0


def _light_sources(battle):
    for u in battle.units:
        radius = unit_light(u)
        if radius:
            for c in cells(u.pos, u.footprint):   # a large creature lights from its whole footprint
                yield c, radius
    for obj in battle.ground:
        radius = ground_light(obj)
        if radius:
            yield obj.pos, radius


def light_sources(battle):
    """[(cell, radius)] of everything emitting light now (units + ground objects)."""
    return list(_light_sources(battle))


def cell_lit(battle, pos):
    """Cell lit? (within a light source's radius, with LOS to it)."""
    return any(chebyshev(fp, pos) <= radius and battle.board.los_clear(fp, pos)
               for fp, radius in _light_sources(battle))


def can_see(battle, observer, target_pos):
    """Does `observer` see the cell `target_pos`?

    A dungeon map is dark: with no light and no darkvision you only see your own
    cell. `darkvision` sees up to its range as if lit. A scenario with
    `ambient_light` (daylight) drops the light requirement -- LOS and range still
    apply, so walls and distance matter, torches don't.
    """
    ocells = cells(observer.pos, observer.footprint)
    dist = min(chebyshev(oc, target_pos) for oc in ocells)
    if dist == 0:
        return True                              # you always see your own cell
    if dist > data.SIGHT_MAX \
            or not any(battle.board.los_clear(oc, target_pos) for oc in ocells):
        return False
    if getattr(battle, "ambient_light", False):
        return True
    dark = observer.ability.darkvision
    if dark and dist <= dark:
        return True
    return cell_lit(battle, target_pos)


def can_see_unit(battle, observer, target):
    # a downed body (dying/stable) can still be seen -- e.g. to be finished off
    return (observer.alive and not target.dead
            and any(can_see(battle, observer, c)
                    for c in cells(target.pos, target.footprint)))


# --------------------------------------------------------------------------- #
# On-screen vision (what the player sees now)                                  #
# --------------------------------------------------------------------------- #

def observers(battle, view_squad):
    """Whose vision is shown now.

    On your turn the vision is the ACTIVE character's; `view_squad` (key L) toggles
    to the union of your living team. On the enemy turn it is always the whole squad.
    """
    if battle.winner is None and battle.active.team == "player" and not view_squad:
        return [battle.active]
    return [u for u in battle.units if u.alive and u.team == "player"]


def enemy_visible(battle, obs, u):
    return any(can_see_unit(battle, o, u) for o in obs)


def visible_cells(battle, obs):
    """Set of cells the observers see.

    A wall shows if the observer sees a cell right next to it (otherwise light
    leaks past the wall at the LOS cutoff).
    """
    b = battle
    vis = set()
    for o in obs:
        vis.update(cells(o.pos, o.footprint))
    for cx in range(COLS):
        for cy in range(ROWS):
            p = (cx, cy)
            if p in vis or p in b.board.walls:
                continue
            if any(can_see(b, o, p) for o in obs):
                vis.add(p)
    for wx, wy in b.board.walls:
        if any((wx + dx, wy + dy) in vis
               for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            vis.add((wx, wy))
    return vis


def vision_desc(unit):
    """Short phrase for the panel: how this unit sees in the dark."""
    if unit.ability.darkvision:
        return f"darkvision, {unit.ability.darkvision} squares"
    if unit.has_torch:
        return f"torch in hand, {data.TORCH_RADIUS} squares"
    for it in unit.inventory:
        radius = data.LIGHT_SOURCES.get(it, 0)
        if radius:
            return f"{it.lower()}, {radius} squares"
    return "no light of their own (only sees light along the line of sight)"

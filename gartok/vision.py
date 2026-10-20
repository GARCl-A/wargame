"""Vision and light.

Pure functions over the battle state:
- `unit_light` / `ground_light` centralize "this emits light and how far";
- `cell_lit` / `can_see` answer what a unit sees;
- `observers` / `visible_cells` / `enemy_visible` build the on-screen vision
  (what the PLAYER sees now), which is the character's vision, not the player's.
"""

from . import data
from .board import cells, grid_distance


def unit_light(unit):
    """Light radius (squares) the unit emits; 0 if none. Only an equipped
    light source counts -- one riding in the pack stays dark."""
    if not unit.alive:
        return 0
    return unit.light_radius


def ground_light(obj):
    """Light radius of a ground object; 0 if it does not emit."""
    return data.TORCH_RADIUS if obj.is_torch else 0


def _light_sources(battle):
    aftermath = getattr(battle, "winner", None) is not None and not any(
        u.alive and u.team == "player" for u in battle.units
    )
    for u in battle.units:
        radius = u.light_radius if aftermath else unit_light(u)
        if radius:
            for c in cells(u.pos, u.footprint):   # a large creature lights from its whole footprint
                yield c, radius
    for obj in battle.ground:
        radius = ground_light(obj)
        if radius:
            yield obj.pos, radius
    for c in getattr(battle, "fire", ()):
        yield c, data.FIRE_LIGHT


def light_sources(battle):
    """[(cell, radius)] of everything emitting light now (units + ground objects)."""
    return list(_light_sources(battle))


def cell_lit(battle, pos):
    """Cell lit? (within a light source's radius, with LOS to it)."""
    return any(grid_distance(fp, pos) <= radius and battle.board.los_clear(fp, pos)
               for fp, radius in _light_sources(battle))


def dark_range(unit):
    """How far `unit` sees in the dark with no light: darkvision, or the Elf's Twilight Sight."""
    twilight = unit.char.talent_bonus("twilight_sight") if hasattr(unit, "char") else 0
    return max(unit.ability.darkvision, int(twilight))


def can_see(battle, observer, target_pos):
    """Does `observer` see the cell `target_pos`?

    A dungeon map is dark: with no light and no darkvision you only see your own
    cell. `darkvision` sees up to its range as if lit. A scenario with
    `ambient_light` (daylight) drops the light requirement -- LOS and range still
    apply, so walls and distance matter, torches don't.
    """
    ocells = cells(observer.pos, observer.footprint)
    dist = min(grid_distance(oc, target_pos) for oc in ocells)
    if dist == 0:
        return True                              # you always see your own cell
    if dist > data.SIGHT_MAX \
            or not any(battle.board.los_clear(oc, target_pos) for oc in ocells):
        return False
    if getattr(battle, "ambient_light", False):
        return True
    dark = dark_range(observer)
    if dark and dist <= dark:
        return True
    return cell_lit(battle, target_pos)


def can_see_unit(battle, observer, target):
    # a downed body (dying/stable) can still be seen -- e.g. to be finished off
    if not (observer.alive and not target.dead and not target.hidden_from(observer.team)):
        return False
    if any(can_see(battle, observer, c) for c in cells(target.pos, target.footprint)):
        return True
    # Heard / adjacent in the dark: a body within 1 cell is sensed by sound/presence unless blocked by wall
    if battle.units_distance(observer, target) <= 1 and battle.los_between(observer, target):
        return True
    return smells_blood(battle, observer, target)


def smells_blood(battle, observer, target):
    """Gnoll Bloodscent: a foe below half its HP is known within range, through walls and dark."""
    scent = observer.char.talent_bonus("bloodscent") if hasattr(observer, "char") else 0
    return bool(scent and target.team != observer.team and target.hp < target.hp_max / 2
                and battle.units_distance(observer, target) <= scent)


def is_obscured(battle, observer, target):
    """True if `target` is not visually in light for `observer` (e.g. only heard in the dark)."""
    return not any(can_see(battle, observer, c) for c in cells(target.pos, target.footprint))


# --------------------------------------------------------------------------- #
# On-screen vision (what the player sees now)                                  #
# --------------------------------------------------------------------------- #

def observers(battle, view_squad, team="player"):
    """Whose vision is shown now, through `team`'s eyes.

    On your turn the vision is the ACTIVE character's; `view_squad` (key L) toggles
    to the union of your living team. On the enemy turn it is always the whole squad.
    Once the fight is over and nobody on `team` is left standing, the fallen squad's
    last view stays lit so the defeat screen is not an empty black board.
    """
    if battle.winner is None and battle.active.team == team and not view_squad:
        return [battle.active]
    living = [u for u in battle.units if u.alive and u.team == team]
    if living or battle.winner is None:
        return living
    return [u for u in battle.units if u.team == team]


def enemy_visible(battle, obs, u):
    if battle.winner is not None and obs and not any(o.alive for o in obs):
        return (not u.dead and not u.hidden_from(obs[0].team)
                and any(can_see(battle, o, c) for o in obs for c in cells(u.pos, u.footprint)))
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
    for cx in range(b.board.cols):
        for cy in range(b.board.rows):
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
    if dark_range(unit):
        return f"twilight sight, {dark_range(unit)} squares"
    if unit.has_torch:
        return f"torch in hand, {data.TORCH_RADIUS} squares"
    if unit.has_lantern:
        return f"lantern in hand, {data.LIGHT_SOURCES[data.LANTERN_ITEM]} squares"
    return "no light of their own (only sees light along the line of sight)"

"""Darkness and light on the battle grid, one level per cell.

Each cell the character sees (`vision.visible_cells`) gets one light level: how close it
sits to a light that reaches it along the line of sight -- the rule `vision.cell_lit` uses --
or to the character's own eyes (darkvision, the own cell). A cell out of sight is dark
outright: dimmed if the side has seen it before (`fog.FogMemory`), black if never. The
drawing never shows what the rules hide, and each cell is one flat tone, like Brogue's.
"""

import math

from . import vision

_SEEN_NOW = 0.42      # the least light a cell in sight gets, so it never reads as remembered
_OWN_CELL = 0.6       # the light of a character's own cell with nothing lit around them
_TORCH_CORE = 0.30    # share of a torch's reach in full light
_DARK_CORE = 0.55     # same for darkvision


def _falloff(dist, radius, core):
    """Light 0..1 at `dist` cells from a source reaching `radius` cells."""
    t = dist / (radius + 0.5)
    fade = min(1.0, max(0.0, (t - core) / (1 - core)))
    return 1 - (6 + 249 * fade ** 1.5) / 255


def cell_levels(battle, visible, observers, sources=None):
    """{cell: light 0..1} for every cell in `visible`, from `sources` ([(cell, radius)], every
    light on the board when None)."""
    board = battle.board
    if getattr(battle, "ambient_light", False):
        return dict.fromkeys(visible, 1.0)
    levels = {cell: 0.0 for cell in visible if cell not in board.walls}
    for (sx, sy), radius in vision.light_sources(battle) if sources is None else sources:
        r = int(radius + 0.5)
        for x in range(sx - r, sx + r + 1):
            for y in range(sy - r, sy + r + 1):
                cell = (x, y)
                if cell not in levels:
                    continue
                d = math.dist((sx, sy), cell)
                if d <= radius + 0.5 and board.los_clear((sx, sy), cell):
                    levels[cell] = max(levels[cell], _falloff(d, radius, _TORCH_CORE))
    eyes = [(o.pos, vision.dark_range(o)) for o in observers]
    for cell, light in levels.items():
        for pos, dark in eyes:
            d = math.dist(pos, cell)
            if d == 0:
                light = max(light, _OWN_CELL)
            elif dark and d <= dark + 0.5:
                light = max(light, _falloff(d, dark, _DARK_CORE))
        levels[cell] = max(_SEEN_NOW, light)
    for wx, wy in set(visible) & board.walls:      # a wall face takes the light of the floor before it
        near = [levels[n] for n in ((wx + 1, wy), (wx - 1, wy), (wx, wy + 1), (wx, wy - 1)) if n in levels]
        levels[(wx, wy)] = max(near) if near else _SEEN_NOW
    return levels

"""Darkness and light on the battle grid, one level per cell.

Each cell the character sees (`vision.visible_cells`) gets one light level: how close it
sits to a light that reaches it along the line of sight -- the rule `vision.cell_lit` uses --
or to the character's own eyes (darkvision, the own cell). A cell out of sight is dark
outright: dimmed if the side has seen it before (`fog.FogMemory`), black if never. The
drawing never shows what the rules hide, and each cell is one flat tone, like Brogue's.
One instance per battle screen.
"""

import math

import pygame

from . import vision
from .ui.board_style import NIGHT

_NIGHT_SEEN = 200     # a remembered cell at night: the terrain just shows through
_DAY_SEEN = 110       # a remembered cell by day: a haze over it
_SEEN_NOW = 0.42      # the least light a cell in sight gets, so it never reads as remembered
_OWN_CELL = 0.6       # the light of a character's own cell with nothing lit around them
_TORCH_CORE = 0.30    # share of a torch's reach in full light
_DARK_CORE = 0.55     # same for darkvision


def _falloff(dist, radius, core):
    """Light 0..1 at `dist` cells from a source reaching `radius` cells."""
    t = dist / (radius + 0.5)
    fade = min(1.0, max(0.0, (t - core) / (1 - core)))
    return 1 - (6 + 249 * fade ** 1.5) / 255


def cell_levels(battle, visible, observers):
    """{cell: light 0..1} for every cell in `visible`."""
    board = battle.board
    if getattr(battle, "ambient_light", False):
        return dict.fromkeys(visible, 1.0)
    levels = {cell: 0.0 for cell in visible if cell not in board.walls}
    for (sx, sy), radius in vision.light_sources(battle):      # each source over its own reach
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


class LightRenderer:
    def __init__(self):
        self.view = None               # BoardView, set each frame by `draw`
        self._tiles = {}               # (size, alpha) -> a NIGHT tile

    def _tile(self, size, alpha):
        key = (size, alpha)
        tile = self._tiles.get(key)
        if tile is None:
            if len(self._tiles) > 512:
                self._tiles.clear()
            tile = pygame.Surface(size, pygame.SRCALPHA)
            tile.fill((*NIGHT, alpha))
            self._tiles[key] = tile
        return tile

    def draw(self, screen, battle, visible, observers, view, seen=None):
        """Darken each cell for what `observers` see now. `seen` is the side's fog memory
        (`fog.FogMemory.seen`): a cell out of sight is dimmed if seen before and black if
        never; None treats every cell as seen."""
        self.view = view
        vr = view.rect
        if vr.w < 4 or vr.h < 4:
            return
        ambient = getattr(battle, "ambient_light", False)
        remembered = _DAY_SEEN if ambient else _NIGHT_SEEN
        levels = cell_levels(battle, visible, observers)
        board = battle.board
        if not ambient:                       # off the board is night too
            area = pygame.Rect(view.cell_rect(0, 0).topleft, (board.cols * view.tile, board.rows * view.tile))
            for strip in _outside(vr, area):
                screen.fill(NIGHT, strip)
        for cx in range(board.cols):
            for cy in range(board.rows):
                r = view.cell_rect(cx, cy)
                if not r.colliderect(vr):
                    continue
                light = levels.get((cx, cy))
                if light is not None:
                    alpha = int(255 * (1 - light))
                else:
                    alpha = remembered if (seen is None or (cx, cy) in seen) else 255
                if alpha:
                    screen.blit(self._tile(r.size, alpha), r)


def _outside(area, board):
    """The strips of `area` off the `board` rect."""
    inner = board.clip(area)
    if not inner.w or not inner.h:
        return [area]
    strips = (pygame.Rect(area.x, area.y, inner.x - area.x, area.h),
              pygame.Rect(inner.right, area.y, area.right - inner.right, area.h),
              pygame.Rect(inner.x, area.y, inner.w, inner.y - area.y),
              pygame.Rect(inner.x, inner.bottom, inner.w, area.bottom - inner.bottom))
    return [r for r in strips if r.w > 0 and r.h > 0]

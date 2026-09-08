"""Darkness + light-radius rendering for the battle grid.

Was ~100 lines buried in the old `app.py` god class. Holds its own mask cache;
one instance per battle screen.
"""

import math
import random

import pygame

from . import vision
from .battle import COLS, ROWS
from .theme import GRID_H, GRID_W, GRID_X, GRID_Y, NIGHT, TILE


class LightRenderer:
    def __init__(self):
        self._mask_cache = {}          # (radius_px, core) -> darkness mask

    # ------------------------------------------------------------------ #
    def _cell_center_px(self, pos):
        cx, cy = pos
        return (GRID_X + cx * TILE + TILE // 2, GRID_Y + cy * TILE + TILE // 2)

    def _flicker_px(self, pos):
        """A small per-frame wobble on a torch's reach -- a sine sway plus light
        noise, so static darkness breathes. Snapped to 2px steps to keep the
        mask cache down to a handful of keys per radius."""
        t = pygame.time.get_ticks() / 1000.0
        phase = pos[0] * 12.9898 + pos[1] * 78.233      # per-torch offset
        wobble = math.sin(t * 8 + phase) * 2 + random.uniform(-1, 1)
        return int(round(wobble / 2)) * 2

    def _source_visible(self, pos, visible):
        """Is the source at `pos` inside (or hugging) the area the character sees?"""
        return pos in visible or any(
            (pos[0] + dx, pos[1] + dy) in visible
            for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    def _sources(self, battle, visible, observers):
        """[(center_px, radius_px, core)] of the lights affecting the scene now."""
        result = []
        for pos, radius in vision.light_sources(battle):
            if self._source_visible(pos, visible):
                reach = radius * TILE + TILE // 2 + self._flicker_px(pos)
                result.append((self._cell_center_px(pos), reach, 0.30))
        for o in observers:                        # darkvision / own cell
            dark = o.ability.darkvision
            result.append((self._cell_center_px(o.pos),
                           (dark if dark else 0) * TILE + TILE // 2, 0.55))
        return result

    def _mask(self, radius_px, core):
        """Darkness mask for a light of `radius_px`: transparent at the centre,
        opaque at the edge. `core` = fraction of the radius in full light."""
        key = (radius_px, core)
        m = self._mask_cache.get(key)
        if m is None:
            m = pygame.Surface((radius_px * 2, radius_px * 2), pygame.SRCALPHA)
            m.fill((*NIGHT, 255))
            for i in range(64, 0, -1):
                t = i / 64                         # 1 at the edge -> 0 at the centre
                falloff = min(1.0, max(0.0, (t - core) / (1 - core)))
                pygame.draw.circle(m, (*NIGHT, int(6 + 249 * falloff ** 1.5)),
                                   (radius_px, radius_px), max(1, int(radius_px * t)))
            self._mask_cache[key] = m
        return m

    def draw(self, screen, battle, visible, observers):
        if getattr(battle, "ambient_light", False):
            return                       # daylight scene: no darkness layer at all
        ceiling = max(GRID_W, GRID_H)
        darkness = pygame.Surface((GRID_W, GRID_H), pygame.SRCALPHA)
        darkness.fill((*NIGHT, 255))
        for (cxpx, cypx), radius_px, core in self._sources(battle, visible, observers):
            radius_px = max(TILE // 2, min(radius_px, ceiling))
            mask = self._mask(radius_px, core)
            darkness.blit(mask, (cxpx - GRID_X - radius_px, cypx - GRID_Y - radius_px),
                          special_flags=pygame.BLEND_RGBA_MIN)
        occl = pygame.Surface((TILE, TILE), pygame.SRCALPHA)   # re-occlude what the character can't see
        occl.fill((*NIGHT, 244))
        for cx in range(COLS):
            for cy in range(ROWS):
                if (cx, cy) not in visible:
                    darkness.blit(occl, (cx * TILE, cy * TILE))
        # blur the edges to kill the square aliasing of the cells
        f = 4
        darkness = pygame.transform.smoothscale(darkness, (GRID_W // f, GRID_H // f))
        darkness = pygame.transform.smoothscale(darkness, (GRID_W, GRID_H))
        screen.blit(darkness, (GRID_X, GRID_Y))

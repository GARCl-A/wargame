"""Darkness + light-radius rendering for the battle grid.

Was ~100 lines buried in the old `app.py` god class. Holds its own mask cache;
one instance per battle screen.
"""

import math
import random

import pygame

from . import vision
from .theme import NIGHT


class LightRenderer:
    def __init__(self):
        self._mask_cache = {}          # (radius_px, core) -> darkness mask
        self.view = None               # BoardView, set each frame by `draw`

    # ------------------------------------------------------------------ #
    def _cell_center_px(self, pos):
        r = self.view.cell_rect(*pos)
        return r.center

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
        tile = self.view.tile
        result = []
        for pos, radius in vision.light_sources(battle):
            if self._source_visible(pos, visible):
                reach = radius * tile + tile // 2 + self._flicker_px(pos)
                result.append((self._cell_center_px(pos), reach, 0.30))
        for o in observers:                        # darkvision / own cell
            dark = o.ability.darkvision
            result.append((self._cell_center_px(o.pos),
                           (dark if dark else 0) * tile + tile // 2, 0.55))
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

    def draw(self, screen, battle, visible, observers, view):
        self.view = view
        if getattr(battle, "ambient_light", False):
            return                       # daylight scene: no darkness layer at all
        vr = view.rect
        if vr.w < 4 or vr.h < 4:
            return
        tile = view.tile
        ox, oy = vr.topleft
        ceiling = max(vr.w, vr.h)
        darkness = pygame.Surface(vr.size, pygame.SRCALPHA)
        darkness.fill((*NIGHT, 255))
        for (cxpx, cypx), radius_px, core in self._sources(battle, visible, observers):
            radius_px = int(max(tile // 2, min(radius_px, ceiling)))
            mask = self._mask(radius_px, core)
            darkness.blit(mask, (cxpx - ox - radius_px, cypx - oy - radius_px),
                          special_flags=pygame.BLEND_RGBA_MIN)
        occl = pygame.Surface((tile, tile), pygame.SRCALPHA)   # re-occlude what the character can't see
        occl.fill((*NIGHT, 244))
        board = battle.board
        for cx in range(board.cols):
            for cy in range(board.rows):
                if (cx, cy) not in visible:
                    r = view.cell_rect(cx, cy)
                    if r.colliderect(vr):
                        darkness.blit(occl, (r.x - ox, r.y - oy))
        # blur the edges to kill the square aliasing of the cells
        f = 4
        small = (max(1, vr.w // f), max(1, vr.h // f))
        darkness = pygame.transform.smoothscale(darkness, small)
        darkness = pygame.transform.smoothscale(darkness, vr.size)
        screen.blit(darkness, vr.topleft)

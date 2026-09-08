"""Loads the dungeon tileset (assets/dungeon_tileset.png + .json).

Typical use:

    from gartok.tileset import Tileset
    ts = Tileset.load(scale=44 // 16)      # or Tileset.load(target=44)
    screen.blit(ts["floor"], (x, y))
    screen.blit(ts["slime_green"], (x, y))

Tiles come from the "16x16 Dungeon" promo sheet, sliced by assets/build_tileset.py.
Some tall objects (table, torch, archway, wall_door_top, weapon_rack) are 16x32
or 32x32 - the blit aligns by the top-left corner, so draw them anchoring the
feet to the cell (y - (h - TILE)).
"""
import json
import os

import pygame

_HERE = os.path.dirname(os.path.abspath(__file__))
_ASSETS = os.path.join(_HERE, "assets", "dungeon")


class Tileset:
    def __init__(self, surfaces, meta):
        self._surf = surfaces          # nome -> pygame.Surface
        self.tile_size = meta["tile_size"]
        self.names = sorted(surfaces)

    @classmethod
    def load(cls, scale=1, target=None):
        """scale: fator inteiro de ampliacao (nearest). target: tamanho final
        desejado da celula em pixels (sobrepoe scale)."""
        with open(os.path.join(_ASSETS, "dungeon_tileset.json")) as f:
            meta = json.load(f)
        sheet = pygame.image.load(
            os.path.join(_ASSETS, meta["image"])
        ).convert_alpha()

        ts = meta["tile_size"]
        if target is not None:
            scale = max(1, round(target / ts))

        surfaces = {}
        for name, r in meta["tiles"].items():
            tile = sheet.subsurface(pygame.Rect(r["x"], r["y"], r["w"], r["h"])).copy()
            if scale != 1:
                tile = pygame.transform.scale(
                    tile, (r["w"] * scale, r["h"] * scale)
                )
            surfaces[name] = tile
        return cls(surfaces, meta)

    def __getitem__(self, name):
        return self._surf[name]

    def get(self, name, default=None):
        return self._surf.get(name, default)

    def __contains__(self, name):
        return name in self._surf


# nomes uteis agrupados (pra montar salas / autotiling manual)
WALLS = [
    "wall_top", "wall_bottom", "wall_left", "wall_right",
    "wall_corner_tl", "wall_corner_tr", "wall_corner_bl", "wall_corner_br",
    "wall_door_top", "wall_left_chain", "wall_brick",
]
FLOORS = ["floor", "floor_alt", "floor_studs", "floor_bars", "floor_medallion"]
PROPS = [
    "barrel", "ladder", "table", "chair", "chest_open", "gravestone",
    "weapon_rack", "torch", "fence", "bar", "rubble", "anvil", "archway",
]
ENEMIES = ["slime_green", "slime_blue", "slime_pink"]

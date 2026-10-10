"""Render a contact sheet of the item silhouettes (prototype): python scripts/item_icon_preview.py out.png"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame

from gartok.ui.item_icons import draw_item_icon
from gartok.ui.tokens import T, fonts

IRON, STEEL_TONE, WOOD, LEATHER, BRASS = (150, 158, 170), (186, 194, 206), (150, 108, 66), (160, 120, 76), T.BRASS
RIM = {"common": None, "uncommon": T.GREEN, "rare": T.BRASS, "unique": T.BLOOD}

SAMPLES = [
    ("Dagger", "blade", IRON, "common", {"length": 34, "width": 8, "guard": 16, "taper": .3}),
    ("Rapier", "blade", STEEL_TONE, "uncommon", {"length": 62, "width": 5, "guard": 26, "taper": .2}),
    ("Broadsword", "blade", IRON, "common", {"length": 58, "width": 14, "guard": 30, "taper": .3}),
    ("Dwarf Axe", "blade", BRASS, "uncommon", {"length": 44, "width": 12, "guard": 20, "taper": .5}),
    ("Shortbow", "bow", WOOD, "common", {}),
    ("Leather Jerkin", "armor", LEATHER, "common", {"heavy": 0}),
    ("Chainmail", "armor", IRON, "uncommon", {"heavy": .5}),
    ("Plate Armor", "armor", STEEL_TONE, "rare", {"heavy": 1}),
    ("Healing Potion", "flask", (190, 205, 215), "common", {"liquid": (176, 66, 58)}),
    ("Antidote", "flask", (190, 205, 215), "uncommon", {"liquid": (106, 160, 98)}),
]

if __name__ == "__main__":
    pygame.init()
    pygame.display.set_mode((1, 1))
    F = fonts()
    cell, pad = 128, 24
    cols = 5
    rows = -(-len(SAMPLES) // cols)
    sheet = pygame.Surface((cols * (cell + pad) + pad, rows * (cell + pad + 28) + pad))
    sheet.fill(T.TABLE)
    for i, (name, kind, tone, rarity, shape) in enumerate(SAMPLES):
        x = pad + (i % cols) * (cell + pad)
        y = pad + (i // cols) * (cell + pad + 28)
        draw_item_icon(sheet, pygame.Rect(x, y, cell, cell), kind, tone, RIM[rarity], **shape)
        label = F["body_sm"].render(name, True, T.TX_MUTED)
        sheet.blit(label, label.get_rect(midtop=(x + cell // 2, y + cell + 6)))
    pygame.image.save(sheet, sys.argv[1] if len(sys.argv) > 1 else "item_icons.png")

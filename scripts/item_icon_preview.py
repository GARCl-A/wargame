"""Render a contact sheet of every item's icon: python scripts/item_icon_preview.py out.png"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame

from gartok import item_icon, items
from gartok.ui.tokens import T, fonts

if __name__ == "__main__":
    pygame.init()
    pygame.display.set_mode((1, 1))
    F = fonts()
    names = [n for n in items.all_items() if item_icon._base(n) == n]
    cell, pad, label_h, cols = 96, 20, 22, 10
    rows = -(-len(names) // cols)
    sheet = pygame.Surface((cols * (cell + pad) + pad, rows * (cell + label_h + pad) + pad))
    sheet.fill(T.TABLE)
    for i, name in enumerate(names):
        x = pad + (i % cols) * (cell + pad)
        y = pad + (i // cols) * (cell + label_h + pad)
        item_icon.draw_icon(sheet, pygame.Rect(x, y, cell, cell), name)
        label = F["micro"].render(name[:16], True, T.TX_MUTED)
        sheet.blit(label, label.get_rect(midtop=(x + cell // 2, y + cell + 4)))
    pygame.image.save(sheet, sys.argv[1] if len(sys.argv) > 1 else "item_icons.png")

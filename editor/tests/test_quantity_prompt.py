"""The quantity box keeps its amount clear of its buttons."""

import pygame
from editor.ui.loadout_panel import quantity_prompt
from editor.ui.tokens import fonts as ui_fonts

def test_the_quantity_box_keeps_the_amount_clear_of_its_buttons():
    pygame.init()
    surf = pygame.Surface((640, 480))
    res = quantity_prompt(surf, ui_fonts(), (320, 240), "mint gold coins", 12, 40, "PAY $1,212", (0, 0))
    (minus, _), (plus, _), (confirm, _) = res["hits"]
    amount = ui_fonts()["bodyb"].size("12 / 40")
    assert minus.right < 320 - amount[0] // 2 and plus.left > 320 + amount[0] // 2
    assert confirm.top > minus.bottom and res["rect"].contains(confirm)

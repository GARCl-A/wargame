"""Tests for the founding draft: a pool of nine, pick three, and the commission tokens."""

import pygame
from editor.ui.tokens import fonts as ui_fonts
from gartok.unit import Unit

def test_compact_weapon_block_is_two_lines():
    from gartok.combatant import Combatant
    from gartok.sheet import unit_to_ch
    from editor.ui import sheet_card
    assert sheet_card.H["compact"]["weapon"] == 32
    ch = unit_to_ch(Combatant(Unit("player")))
    pygame.init()
    surf = pygame.Surface((600, 80))
    sheet_card.draw_sheet(surf, ui_fonts(), pygame.Rect(0, 0, 400, 80), ch, density="compact", only=("weapon",))

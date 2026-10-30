"""Test trap mechanics in battle: trigger on movement, trigger on push, shield AC."""

from gartok.ground import GroundObject
from tests.helpers import _melee_battle

def test_battle_screen_draws_traps():
    import pygame
    pygame.font.init()
    from editor.battle_screen import BattleScreen
    from editor.ui.tokens import fonts as ui_fonts
    batt, actor, defender = _melee_battle()
    batt.ground.append(GroundObject.trap((1, 1), "bear trap", "enemy"))
    batt.ground.append(GroundObject.trap((2, 2), "alarm trap", "player"))
    batt.ground.append(GroundObject.trap((3, 3), "unknown trap", "enemy"))
    bs = BattleScreen(ui_fonts(), batt, lambda w: None)
    bs._visible = {(1, 1), (2, 2), (3, 3)}
    surf = pygame.Surface((1024, 768))
    bs._draw_ground(surf)

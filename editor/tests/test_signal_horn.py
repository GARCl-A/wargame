"""The artifact slot and the Signal Horn it carries: once per battle, 2 points,
+2 initiative to every ally within 10 squares (which can reorder the turns)."""

from tests.helpers import Unit

def test_editor_draws_the_artifact_row():
    import pygame

    from editor.char_editor_screen import CharEditorScreen
    from editor.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    scr = CharEditorScreen(ui_fonts(), lambda: None)
    u = Unit("player")
    u.give_to_artifact("Signal Horn")
    scr._load_unit(u)
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1600, 1000)))

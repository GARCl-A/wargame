"""The tutorial: TutorialState's dismiss/reopen/reset rules, the i18n
catalog backing every id a screen can hand back, and save/load round-tripping
the seen/enabled state by slot."""


def test_header_reserves_space_when_has_tutorial_is_true():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from editor.ui.primitives import header
    from editor.ui.tokens import T
    from editor.ui.tokens import fonts as ui_fonts

    pygame.init()
    F = ui_fonts()
    surf = pygame.Surface((1000, 600))
    head_rect = pygame.Rect(0, 0, 1000, 72)

    tabs_normal = header(surf, F, head_rect, "Title", "Sub", ("gear", "quests"), "gear", has_tutorial=False)
    tabs_tut = header(surf, F, head_rect, "Title", "Sub", ("gear", "quests"), "gear", has_tutorial=True)

    # The rightmost tab with tutorial should be shifted left by 28 + T.S
    assert tabs_tut["quests"].right == tabs_normal["quests"].right - (28 + T.S)

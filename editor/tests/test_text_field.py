import pygame
from editor.text_field import TextField

def _press(field, *keys):
    for k in keys:
        if isinstance(k, str):
            field.key(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=k))
        else:
            field.key(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=""))


def test_the_arrows_move_the_caret_and_typing_lands_there():
    f = TextField(24, text="Brok")
    _press(f, pygame.K_LEFT, pygame.K_LEFT, "a")
    assert f.text == "Braok" and f.caret == 3
    assert f.shown() == "Bra|ok"
    _press(f, pygame.K_HOME, "X", pygame.K_END, "!")
    assert f.text == "XBraok!"


def test_backspace_and_delete_work_around_the_caret():
    f = TextField(24, text="abcd")
    _press(f, pygame.K_LEFT, pygame.K_LEFT, pygame.K_BACKSPACE)
    assert f.text == "acd" and f.caret == 1
    _press(f, pygame.K_DELETE)
    assert f.text == "ad" and f.caret == 1
    _press(f, pygame.K_HOME, pygame.K_BACKSPACE, pygame.K_LEFT)
    assert f.text == "ad" and f.caret == 0
    _press(f, pygame.K_END, pygame.K_RIGHT, pygame.K_DELETE)
    assert f.text == "ad" and f.caret == 2


def test_the_cap_and_the_filter_hold():
    f = TextField(3, allow=str.isdigit, text="12")
    _press(f, "x", "3", "4")
    assert f.text == "123"
    f.set("98765")
    assert f.text == "987" and f.caret == 3


def test_enter_is_left_to_the_screen():
    f = TextField(8)
    assert not f.key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r"))

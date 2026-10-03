import sys
try:
    import pygame
except ImportError:
    from unittest.mock import MagicMock
    mock_pg = MagicMock()
    mock_pg.Surface.side_effect = lambda size, *a, **kw: MagicMock(get_size=lambda: size)
    sys.modules["pygame"] = mock_pg
    sys.modules["pygame.base"] = MagicMock()

from gartok import actions
from gartok.battle_screen import BattleScreen


class DummyScreen:
    def __init__(self, aim_action=None, player_turn=True):
        self.aim_action = aim_action
        self._player_turn = player_turn
        self.battle = MagicMock()
        self.battle.mopping_up = False
        self.battle.is_ctf = False

    def _is_player_turn(self):
        return self._player_turn

    _hint_message = BattleScreen._hint_message


def test_hint_messages_for_utility_and_spells():
    s = DummyScreen(actions.DRINK_POTION)
    msg, _ = s._hint_message()
    assert msg == "click self or damaged ally to drink potion"

    s.aim_action = actions.MOUNT
    msg, _ = s._hint_message()
    assert msg == "click an adjacent allied Centaur to mount"

    s.aim_action = actions.DISMOUNT
    msg, _ = s._hint_message()
    assert msg == "click an adjacent free cell to dismount"

    s.aim_action = actions.WAKE_UP
    msg, _ = s._hint_message()
    assert msg == "click an adjacent sleeping ally to wake them"

    s.aim_action = actions.EAT_CORPSE
    msg, _ = s._hint_message()
    assert msg == "click an adjacent dead enemy corpse to devour"

    s.aim_action = actions.PUSH
    msg, _ = s._hint_message()
    assert msg == "click an adjacent unit to push"

    s.aim_action = actions.CLIMB
    msg, _ = s._hint_message()
    assert msg == "click an adjacent ledge cell to climb"

    s.aim_action = actions.DROP
    msg, _ = s._hint_message()
    assert msg == "click a cell below to drop down"

    s.aim_action = actions.JUMP
    msg, _ = s._hint_message()
    assert msg == "click a cell to jump over a pit"

    s.aim_action = actions.SWIM
    msg, _ = s._hint_message()
    assert msg == "click an adjacent water cell to swim"

    s.aim_action = actions.CastSpellAction("sleep")
    msg, _ = s._hint_message()
    assert msg == "click enemy within 6 cells to cast Sleep"

    s.aim_action = actions.CastSpellAction("magic_missile")
    msg, _ = s._hint_message()
    assert msg == "click enemy within 6 cells to cast Magic Missile"

    s.aim_action = actions.CastSpellAction("light_globe")
    msg, _ = s._hint_message()
    assert msg == "click empty cell within 6 cells to conjure Light Globe"

    s.aim_action = actions.CastSpellAction("floating_disk")
    msg, _ = s._hint_message()
    assert msg == "click empty cell within 6 cells to summon Floating Disk"

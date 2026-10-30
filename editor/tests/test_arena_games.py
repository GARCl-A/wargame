"""The arena's second stage -- the Games: the scaled brawl, capture the flag,
the flag-seeking AI and the three second-stage deeds."""

import random
from gartok.battle import Battle
from gartok.scenario import FlagScenario
from gartok.unit import Unit

def _ctf_battle(n_enemy=1):
    random.seed(0)
    b = Battle([Unit("player")], [Unit("enemy") for _ in range(n_enemy)],
               scenario=FlagScenario(), lethal=False, arena=True)
    return b


def test_the_enemy_flag_stays_hidden_until_you_can_see_its_cell():
    from editor.battle_screen import BattleScreen
    b = _ctf_battle(n_enemy=1)
    b.flags["player"] = (2, 2)
    scr = BattleScreen(None, b, on_battle_end=lambda *a: None)

    drawn = []
    scr._draw_pennant = lambda screen, pos, color: drawn.append(pos)

    scr._visible = {b.flags["player"]}                      # own flag in sight, enemy's not
    scr._draw_flags(None)
    assert drawn == [b.flags["player"]]                     # enemy flag withheld

    drawn.clear()
    scr._visible = {b.flags["player"], b.flags["enemy"]}    # now its cell is lit
    scr._draw_flags(None)
    assert set(drawn) == {b.flags["player"], b.flags["enemy"]}

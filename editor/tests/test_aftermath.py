"""The screens after a fight: the memorial, the after-action report, the level-up card, and the
VICTORY / FLED / DEFEAT word the battle screen and the report share."""

from gartok.guild import Guild
from tests.helpers import Battle, _unit

NODE = "wilds"

def _fight(n=2, foes=1, seed=0):
    squad = [_unit(seed=seed + i) for i in range(n)]
    enemies = [_unit(team="enemy", seed=100 + seed + i) for i in range(foes)]
    guild = Guild(squad, node=NODE)
    battle = Battle(squad, enemies, lethal=True)
    return guild, squad, battle


def test_the_battle_screen_says_the_squad_fled():
    from editor.battle_screen import BattleScreen
    _, _, battle = _fight(n=1)
    battle.player_units[0].status = "fled"
    battle.winner = "enemy"
    scr = BattleScreen(None, battle, on_battle_end=lambda *a: None)
    assert scr._winner_text() == "You fled"

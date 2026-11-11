"""The Demon's lair (`docs/plans/holy_symbol_quest.md`): `cult_site.LAIR_DAYS` after a failed rite the Demon
comes back to the Cult Site and makes it its lair. One fight, lethal: the Demon alone, the strongest mob in
the game. Its death reopens the Farm (`missions.shop_closed`); the Holy Symbol is the girl's, never the Demon's.
"""

from . import i18n, npc_lib
from .board import Board
from .scenario import Scenario

COLS, ROWS = 28, 18


class DemonLairScenario(Scenario):
    floor = "earth"
    outdoor = True
    torch_count = 0

    def __init__(self, squad=None):
        self.allies = []
        self.enemies = [npc_lib.load_npc("the-demon")]

    def _make_board(self):
        return Board(walls=set(), cols=COLS, rows=ROWS)


def settle_fight(guild, battle):
    """A win ends the Demon: the site goes cold for good. -> the notice lines."""
    if battle.winner != "player":
        return []
    from . import cult_site
    cult_site.demon_slain(guild)
    return [i18n.t("demon_lair.slain")]

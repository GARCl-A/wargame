"""The Ogre's fortress (`wildfire.py`): the fight at the Great Focus, and at the fortress itself
once it stands.

A ring of walls in a clearing, under the sky. Going up it is half-raised -- wide gaps on every
side and two stubs of the keep inside; finished it is whole but for its gate. A bonfire burns in
the yard and spreads one or two cells a round (`Battle.spread_fire`): a body on a burning cell
takes `data.FIRE_DICE` a cell at the top of its turn and on walking in. The fight is won the
moment the Ogre is down, whatever is still standing.
"""

import random

from . import wildfire
from .board import Board
from .scenario import Scenario

COLS, ROWS = 24, 16
RING = (7, 2, 20, 13)                          # x0, y0, x1, y1 of the wall line
GAPS = (                                       # where the walls are not up yet
    ((7, 6), (7, 7), (7, 8), (7, 9)),          # the way in
    ((11, 2), (12, 2), (13, 2)),
    ((14, 13), (15, 13), (16, 13), (17, 13)),
    ((20, 4), (20, 5)),
)
GATE = ((7, 7), (7, 8))                        # all that is open once it stands
KEEP = ((16, 4), (16, 5), (16, 6), (16, 9), (16, 10), (16, 11))
BONFIRE = ((11, 7), (12, 7), (11, 8), (12, 8))
OGRE_CELL = (17, 7)
SPREAD = (1, 2)                                # cells the fire takes each round


def _ring():
    x0, y0, x1, y1 = RING
    return ({(x, y0) for x in range(x0, x1 + 1)} | {(x, y1) for x in range(x0, x1 + 1)}
            | {(x0, y) for y in range(y0, y1 + 1)} | {(x1, y) for y in range(y0, y1 + 1)})


def walls(finished=False):
    open_cells = set(GATE) if finished else {c for gap in GAPS for c in gap}
    return (_ring() - open_cells) | (set(KEEP) if not finished else set())


def yard():
    x0, y0, x1, y1 = RING
    return {(x, y) for x in range(x0 + 1, x1) for y in range(y0 + 1, y1)}


class FortressScenario(Scenario):
    outdoor = True
    torch_count = 0

    def __init__(self, enemies, finished=False, rng=random):
        self.enemies = enemies
        self.finished = finished
        self.rng = rng

    def _make_board(self):
        return Board(walls=walls(self.finished), cols=COLS, rows=ROWS)

    def _deploy_cells(self, u):
        if u.team == "player":
            return super()._deploy_cells(u)
        free = sorted(yard() - set(BONFIRE) - set(KEEP))
        self.rng.shuffle(free)
        if getattr(u.char, "npc_slug", None) == wildfire.OGRE_SLUG:
            return [OGRE_CELL] + free
        return free

    def build(self, battle):
        super().build(battle)
        battle.fire = set(BONFIRE)

    def on_round(self, battle):
        battle.spread_fire(self.rng.randint(*SPREAD), self.rng)

    def win_check(self, battle):
        ogre = wildfire.ogre_of(battle)
        if ogre is not None and not ogre.alive:
            return "player"
        return None

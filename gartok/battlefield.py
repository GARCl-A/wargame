"""The Battlefield: the border war past Ledger Hold's frontier outpost.

A known node from the start, but for now its only fight is the Faith Order's errand
(`missions.FAITH_BATTLEFIELD`): the group joins a skirmish beside a squad of Ledger
Hold soldiers that `ai.py` plays (`Battle(allies=...)`, `Combatant.ai_ally`), against a
frontier warband. The errand is the soldiers: it fails if any of them dies, whatever
happens to the guild's own people.

The field is two trenches, one per side, and open ground between them. A trench is a
parapet (a wall line with gaps to climb out through) with its side's deployment
behind it; the soldiers start in the guild's trench, beside the group.

Levels follow the squad: the warband one over its mean level, the soldiers two under,
so there is someone to protect.
"""

import random

from . import encounters
from .board import Board
from .ground import GroundObject
from .scenario import Scenario

NODE = "battlefield"
SOLDIERS = 4
WARBAND = 6
SOLDIER_GAP = 2                        # soldiers are this many levels under the squad
WARBAND_EDGE = 1                       # the warband this many over
SOLDIER_ALIGNMENT = "Lawful and Good"   # ai.py: a good unit stabilizes a downed ally first
SOLDIER_ARMOR = "Leather Jerkin"

COLS, ROWS = 32, 18
PARAPET_X = (5, COLS - 6)              # the guild's trench, the warband's trench
GAP_EVERY = 6                          # a two-cell gap in the parapet every this many rows
_MAX_MEAN = (encounters._COMBAT_CAP + encounters._WORK_CAP) // 2


def squad_level(squad):
    """The squad's mean level, the yardstick for both sides."""
    return round(sum(u.mean_level for u in squad) / len(squad)) if squad else 0


def _clamp(level):
    return max(0, min(_MAX_MEAN, level))


def build_soldiers(level, rng=random):
    """Ledger Hold's line: `SOLDIERS` humanoids `SOLDIER_GAP` levels under `level`, lawful
    and good, in a leather jerkin where it fits."""
    out = []
    for _ in range(SOLDIERS):
        u = encounters.build_enemy(_clamp(level - SOLDIER_GAP), rng)
        u.team = "player"
        u.alignment = SOLDIER_ALIGNMENT
        if u.fits_armor(SOLDIER_ARMOR) and not u.equipped_armor:
            u.give_to_armor(SOLDIER_ARMOR)
        out.append(u)
    return out


def build_warband(level, rng=random):
    """The frontier warband: `WARBAND` mixed humanoids `WARBAND_EDGE` over `level`."""
    return [encounters.build_enemy(_clamp(level + WARBAND_EDGE), rng) for _ in range(WARBAND)]


def parapet(x):
    """A trench's wall line at column `x`, with a two-cell gap every `GAP_EVERY` rows."""
    return {(x, y) for y in range(ROWS) if y % GAP_EVERY not in (2, 3)}


def soldiers_lost(battle):
    """The allied soldiers who did not come through."""
    return [c for c in battle.player_units if c.ai_ally and not c.survived]


class BattlefieldScenario(Scenario):
    outdoor = True
    torch_count = 0

    def __init__(self, squad, rng=random):
        level = squad_level(squad)
        self.allies = build_soldiers(level, rng)
        self.enemies = build_warband(level, rng)

    def _make_board(self):
        return Board(walls=parapet(PARAPET_X[0]) | parapet(PARAPET_X[1]), cols=COLS, rows=ROWS)

    def _spawn_cells(self, team):
        xs = range(PARAPET_X[0]) if team == "player" else range(PARAPET_X[1] + 1, COLS)
        return [(x, y) for x in xs for y in range(ROWS)]

    def build(self, battle):
        super().build(battle)
        if not battle.daylight:            # the watch fires burn in both trenches
            for x in (PARAPET_X[0] - 1, PARAPET_X[1] + 1):
                for y in (ROWS // 4, 3 * ROWS // 4):
                    battle.ground.append(GroundObject.torch((x, y)))


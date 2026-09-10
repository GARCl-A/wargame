"""Shared test fixtures: deterministic Unit/Combatant builders, the battle
scaffolds used across more than one domain file, and `fixed_d20`.

The domain files import the game modules from here too
(`from tests.helpers import world, Battle, ...`), so the imports below are
deliberate re-exports.
"""

import contextlib
import random

from gartok import abilities, actions, data, economy, persist, recruit, talents, world
from gartok import battle as _battle_mod
from gartok.board import COLS, ROWS, Board, grid_distance
from gartok.battle import Battle
from gartok.scenario import CustomScenario, ErmosScenario
from gartok.conditions import Defending, Demoralized
from gartok.data import SIZES, resolve_bonus, squares
from gartok.ground import GroundObject
from gartok.unit import Unit
from gartok.combatant import Combatant


def _unit(**over):
    """A deterministic Unit for tests: seeded roll with overridden fields."""
    random.seed(over.pop("seed", 0))
    u = Unit(over.pop("team", "player"))
    for k, v in over.items():
        setattr(u, k, v)
    return u


def _combatant(**over):
    """A Combatant wrapping a deterministic Unit -- for battle-behaviour tests."""
    return Combatant(_unit(**over))


def _recruit(batt, team="player"):
    """Drop a fresh combatant into an already-built battle (not in the initiative
    order -- tests that use it drive turns by hand)."""
    c = Combatant(Unit(team), team)
    batt.units.append(c)
    (batt.player_units if team == "player" else batt.enemy_units).append(c)
    return c


def _melee_battle():
    random.seed(3)
    batt = Battle([Unit("player")], [Unit("enemy")])
    a, d = batt.units
    a.pos, d.pos = (5, 5), (6, 5)
    a.weapon_hand, a.torch_hand = True, False
    return batt, a, d


class _FixedRNG:
    """A stand-in for `random`: hands back the given d20 values in order."""
    def __init__(self, *vals):
        self.vals = list(vals)

    def randint(self, a, b):
        return self.vals.pop(0)


@contextlib.contextmanager
def fixed_d20(value):
    """Pin every `d20()` roll to `value` for the block -- death saves, attack
    rolls, checks, initiative. Patches the name in each module that bound it
    (`actions`, `battle`) plus the source (`data`), so a test asserts on the
    check outcome instead of a magic seed. Use nested blocks for a sequence
    (fail then succeed)."""
    mods = (actions, _battle_mod, data)
    saved = [m.d20 for m in mods]
    for m in mods:
        m.d20 = lambda: value
    try:
        yield
    finally:
        for m, fn in zip(mods, saved):
            m.d20 = fn


def _person(seed, *, lang="Comum", align="Neutral and Neutral", cha=0):
    u = _unit(seed=seed, languages=[lang], alignment=align)
    u.mod_charisma = cha
    return u

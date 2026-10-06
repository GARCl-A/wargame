# ruff: noqa: F401
"""Shared test fixtures: deterministic Unit/Combatant builders, the battle
scaffolds used across more than one domain file, and `fixed_d20`.

The domain files import the game modules from here too
(`from tests.helpers import world, Battle, ...`), so the imports below are
deliberate re-exports.
"""

import contextlib
import random
from unittest.mock import MagicMock, patch

from gartok import abilities, actions, data, economy, persist, recruit, talents, world
from gartok import battle as _battle_mod
from gartok.battle import Battle
from gartok.board import COLS, ROWS, Board, grid_distance
from gartok.combatant import Combatant
from gartok.conditions import Defending, Demoralized
from gartok.data import SIZES, resolve_bonus, squares
from gartok.ground import GroundObject
from gartok.scenario import CustomScenario, ErmosScenario
from gartok.unit import Unit


def packed(names):
    """Group a flat, possibly-repeated item-name list into `[(name, qty)]`
    stacks, first-seen order -- the shape `Unit._base_inventory` now uses.
    Lets old-style test fixtures (`["Rope"]*3`) become `packed(["Rope"]*3)`
    with a mechanical wrap instead of hand-authoring the pairs."""
    order, counts = [], {}
    for name in names:
        if name not in counts:
            order.append(name)
            counts[name] = 0
        counts[name] += 1
    return [(name, counts[name]) for name in order]


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


def _action_mods():
    return [m for m in vars(actions).values()
            if getattr(m, "__package__", None) == "gartok.actions" and hasattr(m, "d20")]


@contextlib.contextmanager
def patch_action_d20(**kwargs):
    """`patch(..., d20)` for every `gartok.actions` submodule that rolls it, all
    sharing one mock so a `side_effect` sequence spans actions."""
    mock = MagicMock(**kwargs)
    with contextlib.ExitStack() as stack:
        for m in _action_mods():
            stack.enter_context(patch.object(m, "d20", mock))
        yield mock


@contextlib.contextmanager
def fixed_d20(value):
    """Pin every `d20()` roll to `value` for the block -- death saves, attack
    rolls, checks, initiative. Patches the name in each module that bound it
    (each `actions` submodule that rolls it, `battle`) plus the source
    (`data`), so a test asserts on the check outcome instead of a magic seed. Use nested blocks for a sequence
    (fail then succeed)."""
    mods = (*_action_mods(), _battle_mod, data)
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


def walker(team="player"):
    """A unit pinned to the 9 m walk one travel distance unit is measured by."""
    u = Unit(team)
    u.speed = 6
    return u

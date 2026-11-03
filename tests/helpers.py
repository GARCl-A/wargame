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

from gartok import (
    abilities,
    actions,
    data,
    economy,
    items,
    persist,
    recruit,
    talents,
    world,
)
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
    """Group a flat, possibly-repeated item-name list into `ItemInstance`
    stacks, first-seen order -- the shape `Unit._base_inventory` uses."""
    order, counts = [], {}
    for name in names:
        if name not in counts:
            order.append(name)
            counts[name] = 0
        counts[name] += 1
    return [items.create_instance(name, qty=counts[name]) for name in order]


def _unit(**over):
    """A deterministic Unit for tests: seeded roll (race and attributes) with a fixed kit and overridden fields."""
    random.seed(over.pop("seed", 0))
    u = Unit(over.pop("team", "player"))
    u._stock("Quarterstaff", None)
    for k, v in over.items():
        setattr(u, k, v)
    return u


def standard_unit(team="player"):
    """The one test body, rolled by nothing: a Human Guide, every attribute 10, the hit die at its
    top (8 HP), a Quarterstaff in hand, an empty pack, no coin, one language. A test that is not
    about a roll starts here and sets what it is about on top; each call is a fresh copy."""
    u = Unit(team, name="Standard")
    u.set_race("Human")
    u.set_kit("Quarterstaff", None)
    for a in data.ATTRIBUTES:
        u.base_attributes[a] = 10
    u.languages = ["Ankarin"]
    u.recipes = []
    u._sync_dictionary_recipes()
    u.alignment = "Neutral and Neutral"
    u._age_base = u.age = 30
    u._hp_roll = u.race["hd"]
    u._base_inventory = []
    u.magic_sources, u.spells_known = [], []
    u.magic_blood = False
    u._apply_attributes()
    u._derive_combat()
    u.hp = u.hp_max
    return u


def _body(team, race, attributes, hp_roll, language, age, weapon):
    u = standard_unit(team)
    u.set_race(race)
    u.base_attributes.update(attributes)
    u.languages = [language]
    u._hp_roll = hp_roll
    u._age_base = u.age = age
    u.alignment = "Neutral and Good"
    u._stock(weapon, None)
    u._apply_attributes()
    u._derive_combat()
    u.hp = u.hp_max
    return u


def duelists():
    """The two bodies the duel boards were tuned on: a Lizardfolk (player) and a Grippli (enemy),
    two peoples with no tongue in common."""
    return (_body("player", "Lizardfolk", dict(strength=12, dexterity=10, constitution=15, intelligence=7,
                                               wisdom=12, charisma=10), 7, "Draconic", 53, "Quarterstaff"),
            _body("enemy", "Grippli", dict(strength=13, dexterity=8, constitution=5, intelligence=12,
                                           wisdom=16, charisma=14), 5, "Sylvan", 111, "Dagger"))


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
    side_a, side_d = duelists()
    random.seed(3)                                  # the board does not depend on how the bodies rolled
    batt = Battle([side_a], [side_d])
    batt.board.walls = set()
    batt.ambient_light = True
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


def said(state):
    """The lines of the guild's log a map state carries, oldest first."""
    return [row["text"] for row in state["log"]["rows"]]

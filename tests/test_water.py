"""Water terrain: shallow (difficult terrain), deep water (Swim + drowning),
and the Amphibious rework."""

import random

from tests.helpers import abilities, actions, Battle, fixed_d20, Unit


def _set_stats(combatant, **scores):
    for k, v in scores.items():
        setattr(combatant.char, k, v)
    combatant.char._derive_combat()
    combatant.hp = combatant.hp_max          # re-deriving HP shifts hp_max; top up


def _water_battle(deep=None, shallow=None, depth=2):
    """A clear board with the given cells flooded: `deep` cells become a pit
    `depth` levels down full of water, `shallow` cells a ground-level puddle."""
    random.seed(3)
    batt = Battle([Unit("player")], [Unit("enemy")])
    a, d = batt.units
    a._ability = d._ability = abilities.get("none")
    a.pos, d.pos = (5, 5), (0, 0)
    a.weapon_hand, a.torch_hand = True, False
    batt.board.walls = set()
    elev, water = {}, set()
    for c in (deep or []):
        elev[tuple(c)] = -depth
        water.add(tuple(c))
    for c in (shallow or []):
        water.add(tuple(c))
    batt.board.elevation, batt.board.water = elev, water
    batt.board.refresh_terrain()
    a.ap = d.ap = 2
    return batt, a, d


# --- shallow water = difficult terrain ------------------------------------- #

def test_shallow_water_costs_one_extra_square():
    batt, a, _ = _water_battle(shallow=[(6, 5)])
    reach = batt.reachable(a)
    assert reach[(6, 4)] == 1          # plain diagonal step: first diagonal is free
    assert reach[(6, 5)] == 2          # straight step into the puddle: 1 + 1


def test_shallow_water_is_walkable_just_slower():
    batt, a, _ = _water_battle(shallow=[(6, 5)])
    assert (6, 5) in batt.reachable(a)
    hp = a.hp
    actions.MOVE.execute(batt, a, (6, 5))
    assert a.pos == (6, 5) and a.hp == hp        # no swim, no drown


# --- deep water blocks a walk -------------------------------------------- #

def test_deep_water_cannot_be_walked_into():
    batt, a, _ = _water_battle(deep=[(6, 5), (7, 5)])
    a.pos = (6, 5)                                # standing in the flooded pit
    assert (7, 5) not in batt.reachable(a)        # same depth, but you must Swim


def test_flier_crosses_deep_water():
    batt, a, _ = _water_battle(deep=[(6, 5)])
    a._ability = abilities.get("flight")
    assert (6, 5) in batt.reachable(a)


# --- Swim ---------------------------------------------------------------- #

def test_swim_crosses_deep_water_on_a_strength_roll():
    batt, a, d = _water_battle(deep=[(6, 5), (7, 5), (8, 5)])
    a.pos = (6, 5)
    _set_stats(a, strength=10)                    # +0
    assert actions.SWIM.can(batt, a, (7, 5))
    with fixed_d20(15):                                # 15 // 5 = 3 squares available
        actions.SWIM.execute(batt, a, (8, 5))
    assert a.pos in ((7, 5), (8, 5)) and a.ap == 1


def test_swim_stops_at_the_water_edge():
    batt, a, d = _water_battle(deep=[(6, 5), (7, 5)])
    a.pos = (6, 5)
    _set_stats(a, strength=18)                    # +4, plenty of reach
    with fixed_d20(20):
        actions.SWIM.execute(batt, a, (8, 5))     # aims onto the dry cell past the water
    assert a.pos == (7, 5)                        # ends on the last water cell


def test_swim_hidden_unless_at_water():
    batt, a, _ = _water_battle(deep=[(6, 5)])
    a.pos = (2, 2)
    assert not actions.SWIM.available(batt, a)
    a.pos = (5, 5)                                # next to the water
    assert actions.SWIM.available(batt, a)


# --- breath / drowning -------------------------------------------------- #

def test_breath_runs_out_then_escalating_drowning_damage():
    batt, a, _ = _water_battle(deep=[(6, 5)])
    a.pos = (6, 5)
    _set_stats(a, constitution=10)                # CON mod 0 -> holds 4 rounds
    for _ in range(4):
        batt._apply_submersion(a)
    assert a.hp == a.hp_max and a.rounds_submerged == 4
    batt._apply_submersion(a)                     # 5th round under: 1d6
    first = a.hp_max - a.hp
    assert 1 <= first <= 6
    batt._apply_submersion(a)                     # 6th: 2d6, strictly worse on average
    assert a.hp_max - a.hp >= first


def test_surfacing_resets_the_breath_counter():
    batt, a, _ = _water_battle(deep=[(6, 5)])
    a.pos = (6, 5)
    _set_stats(a, constitution=10)
    for _ in range(3):
        batt._apply_submersion(a)
    a.pos = (5, 5)                                # climbed out
    batt._apply_submersion(a)
    assert a.rounds_submerged == 0


def test_amphibious_never_drowns():
    batt, a, _ = _water_battle(deep=[(6, 5)])
    a.pos = (6, 5)
    a._ability = abilities.get("amphibious")
    _set_stats(a, constitution=6)                 # would run out fast
    for _ in range(12):
        batt._apply_submersion(a)
    assert a.hp == a.hp_max and a.rounds_submerged == 0


def test_amphibious_no_longer_grants_speed():
    random.seed(0)
    u = Unit("player")
    u._ability = abilities.get("none")
    u._derive_combat()
    base = u.speed
    u._ability = abilities.get("amphibious")
    u._derive_combat()
    assert u.speed == base


# --- falling into water ------------------------------------------------- #

def test_a_plunge_into_deep_water_is_cushioned():
    batt, a, _ = _water_battle(deep=[(6, 5)], depth=5)
    a.pos = (6, 5)
    hp = a.hp
    batt.apply_fall(a, 5, batt.log)
    assert a.hp == hp                             # the water broke the fall

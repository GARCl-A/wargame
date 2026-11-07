"""Water terrain: shallow (difficult terrain), deep water (Swim + drowning),
and the Amphibious rework."""

import random

from tests.helpers import Battle, Unit, abilities, actions, fixed_d20


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


def test_swim_refuses_a_first_step_that_is_not_free_deep_water():
    batt, a, _ = _water_battle(deep=[(6, 5), (8, 5)])
    a.pos = (6, 5)
    assert not actions.SWIM.can(batt, a, (8, 5))   # (7, 5) is dry land: the swim would move nothing


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


# --- Webbed Feet (Grippli racial talent) -------------------------------- #

def _swimmer(talent):
    batt, a, d = _water_battle(deep=[(6, 5), (7, 5), (8, 5), (9, 5), (10, 5)])
    a.pos = (6, 5)
    a.speed = 4
    a.char.talents["racial"] = [talent] if talent else []
    _set_stats(a, strength=10)
    return batt, a


def test_webbed_feet_add_one_square_to_the_swim_and_its_cap():
    batt, a = _swimmer(None)
    assert actions.SWIM._max_reach(batt, a) == 2          # half of speed 4
    assert not actions.SWIM.can(batt, a, (9, 5))
    with fixed_d20(20):
        actions.SWIM.execute(batt, a, (8, 5))
    assert a.pos == (8, 5)

    batt, a = _swimmer("webbed_feet")
    assert actions.SWIM._max_reach(batt, a) == 3
    with fixed_d20(20):
        actions.SWIM.execute(batt, a, (9, 5))
    assert a.pos == (9, 5)


def test_webbed_feet_add_to_a_poor_roll_but_never_pass_full_speed():
    batt, a = _swimmer("webbed_feet")
    with fixed_d20(5):                                   # 5 // 5 = 1, +1 from the talent
        actions.SWIM.execute(batt, a, (9, 5))
    assert a.pos == (8, 5)

    batt, a = _swimmer("webbed_feet")
    a.speed = 1                                          # cap is min(speed, 1 + 1)
    assert actions.SWIM._max_reach(batt, a) == 1


def test_ai_swims_farther_with_webbed_feet():
    from gartok import ai
    batt, a = _swimmer("webbed_feet")
    d = batt.enemy_units[0]
    d.pos = (10, 5)
    a.ap = 2
    with fixed_d20(20):
        assert ai._step_over_terrain(batt, a, d)
    assert a.pos == (9, 5)


# --- a Large body --------------------------------------------------------- #

def _river_battle(cols=range(8, 11)):
    """A Centaur on the west bank, a foe on the east one and a river of deep water between them from edge to edge:
    nobody walks across."""
    random.seed(3)
    centaur = Unit("player")
    centaur.set_race("Centaur")
    batt = Battle([centaur], [Unit("enemy")])
    a, d = batt.units
    a._ability = d._ability = abilities.get("none")
    batt.board.walls = set()
    deep = [(x, y) for x in cols for y in range(batt.board.rows)]
    batt.board.elevation, batt.board.water = {c: -2 for c in deep}, set(deep)
    batt.board.refresh_terrain()
    a.pos, d.pos = (2, 5), (15, 5)
    a.ap = d.ap = 2
    return batt, a, d


def test_a_large_body_swims_in_from_the_bank():
    batt, a, _ = _river_battle()
    assert a.footprint == 2
    a.pos = (6, 5)                                # its far column stands on (7, 5), one short of the water
    _set_stats(a, strength=18)
    assert actions.SWIM.available(batt, a)
    assert actions.SWIM.can(batt, a, (9, 5))
    with fixed_d20(20):
        actions.SWIM.execute(batt, a, (9, 5))
    assert a.pos[0] > 6 and all(batt.board.is_deep_water(c) for c in batt.cells_of(a))


def test_a_large_body_is_never_left_half_in_the_water():
    batt, a, _ = _river_battle()
    a.pos = (6, 5)
    _set_stats(a, strength=10)
    with fixed_d20(1):                            # a poor roll: one square, which is only the bank cell touching the river
        actions.SWIM.execute(batt, a, (9, 5))
    assert a.pos == (6, 5)


def _centaur_and_foe(start, foe):
    from gartok import map_lib
    from gartok.scenario import CustomScenario
    random.seed(3)
    centaur = Unit("player")
    centaur.set_race("Centaur")
    batt = Battle([centaur], [Unit("enemy")], scenario=CustomScenario(map_lib.load_map("capture-the-flag-the-gamers")))
    a, d = batt.units
    a._ability = d._ability = abilities.get("none")
    a.pos, d.pos = start, foe
    return batt, a, d


def test_the_ai_takes_a_large_body_across_the_river_when_no_dry_road_leads_to_the_foe():
    from gartok import ai
    batt, a, d = _centaur_and_foe((5, 0), (14, 0))     # a 2x2 body cannot pass the map's one-wide gaps: the river is its road
    assert batt.path_step_toward(a, d.pos, a.speed) == a.pos
    for _ in range(14):
        a.ap, a.walking = 2, False
        with fixed_d20(20):
            if not ai._step_over_terrain(batt, a, d):
                break
    assert a.pos[0] >= 13


def _walk_turns(batt, a, turns):
    from gartok import ai
    for _ in range(turns):
        a.ap, a.walking = 2, False
        with fixed_d20(20):
            ai.take_turn(batt, a)


def test_a_large_body_cut_off_by_the_river_does_not_pace_back_and_forth_on_the_bank():
    batt, a, _ = _centaur_and_foe((1, 8), (19, 8))
    _walk_turns(batt, a, 8)
    assert a.pos[0] >= 13


def test_a_large_body_crosses_by_the_channel_nearer_its_foe():
    batt, a, _ = _centaur_and_foe((1, 13), (19, 13))
    _walk_turns(batt, a, 8)
    assert a.pos[0] >= 13 and a.pos[1] >= 9

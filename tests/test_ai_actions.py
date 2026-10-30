"""The AI's use of the actions it used to skip or take blindly: the 2-point weapon actions
scored against two plain attacks, Throw, Jump, Push into a pit, traps, secret walls, riding."""

import random

from gartok import ai
from gartok.ground import GroundObject
from tests.helpers import Battle, Unit, abilities, actions, fixed_d20, _recruit
from tests.test_ai_racial import _centaur, _rider_unit


def _duel(weapon="Axe"):
    random.seed(3)
    batt = Battle([Unit("player")], [Unit("enemy")])
    p, e = batt.player_units[0], batt.enemy_units[0]
    for u in batt.units:
        u._ability = abilities.get("none")
    batt.board.walls = set()
    batt.board.elevation = {}
    batt.ambient_light = True
    e.equip_weapon(weapon)
    e.pos, p.pos = (5, 5), (6, 5)
    p.hp = p.hp_max = 30
    e.ap = 2
    return batt, e, p


def _ac(plain, pierced=None):
    """A `_reckoned_ac` stand-in: `plain` AC, `pierced` once worn armour is ignored."""
    return lambda battle, unit, target, armor_pierce=False: (
        pierced if armor_pierce and pierced is not None else plain)


# --------------------------------------------------------------------------- #
# Weapon actions against two plain attacks                                    #
# --------------------------------------------------------------------------- #

def test_two_swings_beat_a_lone_parry_and_strike():
    batt, e, p = _duel("Broadsword")
    assert ai._pick_attack(batt, e, p) is actions.ATTACK


def test_parry_and_strike_when_the_swing_barely_lands_and_foes_crowd_in(monkeypatch):
    batt, e, p = _duel("Broadsword")
    for pos in ((4, 5), (5, 4)):
        _recruit(batt, team="player").pos = pos
    monkeypatch.setattr(ai.reckon, "_reckoned_ac", _ac(40))
    assert ai._pick_attack(batt, e, p) is actions.PARRY_STRIKE


def test_cleave_when_a_second_foe_stands_beside_both():
    batt, e, p = _duel("Axe")
    _recruit(batt, team="player").pos = (6, 6)
    assert ai._pick_attack(batt, e, p) is actions.CLEAVE


def test_a_lone_foe_takes_two_axe_swings_not_a_cleave():
    batt, e, p = _duel("Axe")
    assert ai._pick_attack(batt, e, p) is actions.ATTACK


def test_armor_pierce_when_the_armour_is_most_of_the_ac(monkeypatch):
    batt, e, p = _duel("Pick")
    monkeypatch.setattr(ai.reckon, "_reckoned_ac", _ac(26, pierced=10))
    assert ai._pick_attack(batt, e, p) is actions.ARMOR_PIERCE
    monkeypatch.setattr(ai.reckon, "_reckoned_ac", _ac(14, pierced=12))
    assert ai._pick_attack(batt, e, p) is actions.ATTACK


def test_extreme_shot_only_past_the_crossbow_s_range():
    batt, e, p = _duel("Light Crossbow")
    e.ammo, e.crossbow_loaded = 5, True
    p.pos = (15, 5)
    assert ai._pick_attack(batt, e, p) is actions.ATTACK
    batt.board.cols = max(batt.board.cols, 40)
    p.pos = (35, 5)
    assert ai._pick_attack(batt, e, p) is actions.EXTREME_SHOT


def test_power_shot_on_a_long_shot_or_the_last_arrow():
    batt, e, p = _duel("Shortbow")
    e.char.strength = 16
    e.ammo = 6
    p.pos = (9, 5)
    assert ai._pick_attack(batt, e, p) is actions.ATTACK
    p.pos = (13, 5)
    assert ai._pick_attack(batt, e, p) is actions.POWER_SHOT
    p.pos, e.ammo = (9, 5), 1
    assert ai._pick_attack(batt, e, p) is actions.POWER_SHOT


def test_a_longbow_power_shots_the_foe_past_half_its_range():
    batt, e, p = _duel("Longbow")
    batt.board.cols = max(batt.board.cols, 30)
    e.char.strength = 16
    e.ammo = 6
    p.pos = (13, 5)
    assert ai._pick_attack(batt, e, p) is actions.ATTACK
    p.pos = (20, 5)
    assert ai._pick_attack(batt, e, p) is actions.POWER_SHOT


def test_parry_and_strike_with_a_sword_when_foes_crowd_in(monkeypatch):
    batt, e, p = _duel("Sword")
    assert ai._pick_attack(batt, e, p) is actions.ATTACK
    for pos in ((4, 5), (5, 4)):
        _recruit(batt, team="player").pos = pos
    monkeypatch.setattr(ai.reckon, "_reckoned_ac", _ac(40))
    assert ai._pick_attack(batt, e, p) is actions.PARRY_STRIKE


def test_a_glaive_swings_twice_in_reach_and_long_thrusts_one_square_past_it():
    batt, e, p = _duel("Glaive")
    p.pos = (7, 5)
    assert ai._pick_attack(batt, e, p) is actions.ATTACK
    p.pos = (8, 5)
    assert ai._pick_attack(batt, e, p) is actions.LONG_THRUST
    p.pos = (9, 5)
    assert ai._pick_attack(batt, e, p) is None


def test_a_glaive_bearer_stops_at_its_reach_and_strikes():
    batt, e, p = _duel("Glaive")
    assert ai._approach_reach(e) == 2
    p.pos = (11, 5)
    ai.take_turn(batt, e)
    assert batt.units_distance(e, p) == 2
    assert any(line.startswith(f"{e.name} -> {p.name}") for line in batt.log_lines)


def test_maiming_strike_on_a_foe_that_cannot_dodge():
    from gartok.conditions import Entangled
    batt, e, p = _duel("Club")
    assert ai._pick_attack(batt, e, p) is actions.ATTACK
    p.add_condition(Entangled())
    assert ai._pick_attack(batt, e, p) is actions.MAIMING_STRIKE


def test_maiming_strike_on_the_flag_runner(monkeypatch):
    batt, e, p = _duel("Club")
    monkeypatch.setattr(type(batt), "is_ctf", property(lambda self: True))
    batt.flag_carrier = {"player": None, "enemy": p}
    assert ai._pick_attack(batt, e, p) is actions.MAIMING_STRIKE
    batt.flag_carrier = {"player": None, "enemy": None}
    assert ai._pick_attack(batt, e, p) is actions.ATTACK


# --------------------------------------------------------------------------- #
# Throw                                                                        #
# --------------------------------------------------------------------------- #

def test_throw_with_the_last_point_at_a_foe_it_may_drop():
    batt, e, p = _duel("Dagger")
    p.pos, e.ap = (9, 5), 1
    p.hp = 1
    with fixed_d20(15):
        assert ai._try_throw(batt, e, p, stalled=False)
    assert e.unarmed


def test_no_throw_at_a_healthy_foe_it_can_still_walk_to():
    batt, e, p = _duel("Dagger")
    p.pos, e.ap = (9, 5), 1
    assert not ai._try_throw(batt, e, p, stalled=False)
    e.ap = 2
    assert not ai._try_throw(batt, e, p, stalled=True)      # two points: walk and swing instead


def test_throw_when_it_cannot_get_any_nearer():
    batt, e, p = _duel("Dagger")
    p.pos, e.ap = (9, 5), 1
    with fixed_d20(15):
        assert ai._try_throw(batt, e, p, stalled=True)


# --------------------------------------------------------------------------- #
# Jump, Push                                                                   #
# --------------------------------------------------------------------------- #

def test_ai_jumps_a_trench_it_cannot_walk_round():
    batt, e, p = _duel("Axe")
    batt.board.elevation = {(5, y): -3 for y in range(batt.board.rows)}
    e.pos, p.pos = (4, 5), (9, 5)
    batt.turn_idx = batt.order.index(e)
    with fixed_d20(15):
        ai.take_turn(batt, e)
    assert e.pos[0] > 5 and batt.elevation(e) == 0


def test_ai_shoves_a_foe_into_a_deep_pit(monkeypatch):
    batt, e, p = _duel("Club")
    batt.board.elevation = {(7, 5): -4}
    monkeypatch.setattr(ai.reckon, "_shove_odds", lambda unit, foe: 0.9)
    assert ai._try_shove(batt, e)
    assert batt.elevation(p) < 0 or p.pos == (6, 5)


def test_shoving_a_flanker_counts_the_flank_it_breaks():
    batt, e, p = _duel("Club")
    mate = _recruit(batt, team="player")
    mate.pos = (4, 5)
    assert ai._unflank_worth(batt, e, p) > 0
    mate.pos = (5, 4)
    assert ai._unflank_worth(batt, e, p) == 0


# --------------------------------------------------------------------------- #
# Traps and secret walls                                                       #
# --------------------------------------------------------------------------- #

def test_ai_walks_round_a_trap_it_can_see():
    batt, e, p = _duel("Axe")
    e.pos, p.pos = (3, 5), (10, 5)
    trap = GroundObject.trap((5, 5), "bear trap", "player")
    batt.ground.append(trap)
    batt.turn_idx = batt.order.index(e)
    ai.take_turn(batt, e)
    assert trap in batt.ground and e.pos != (3, 5)


def test_ai_disarms_a_trap_that_blocks_the_only_corridor():
    batt, e, p = _duel("Axe")
    batt.board.walls = {(x, y) for x in range(batt.board.cols) for y in (4, 6)}
    e.pos, p.pos = (3, 5), (10, 5)
    trap = GroundObject.trap((5, 5), "bear trap", "player")
    batt.ground.append(trap)
    batt.turn_idx = batt.order.index(e)
    with fixed_d20(18):
        ai.take_turn(batt, e)
    assert trap not in batt.ground
    assert e.hp == e.hp_max


def test_ai_opens_a_secret_wall_it_is_stalled_beside():
    batt, e, p = _duel("Axe")
    batt.board.walls = {(x, y) for x in range(batt.board.cols) for y in (4, 6)} | {(6, 5)}
    batt.secret_walls = {(6, 5)}
    e.pos, p.pos = (5, 5), (10, 5)
    batt.turn_idx = batt.order.index(e)
    ai.take_turn(batt, e)
    assert (6, 5) not in batt.board.walls


# --------------------------------------------------------------------------- #
# Riding                                                                       #
# --------------------------------------------------------------------------- #

def _riding(rider_pos=(5, 5), foe_pos=(5, 12)):
    random.seed(3)
    c, r = _centaur(), _rider_unit()
    batt = Battle([Unit("player")], [c, r])
    cc, rc = batt.enemy_units
    p = batt.player_units[0]
    batt.board.walls = set()
    batt.ambient_light = True
    cc.pos = rc.pos = rider_pos
    rc.mounted_on, cc.rider = cc, rc
    p.pos = foe_pos
    rc.equip_weapon("Hammer")
    return batt, cc, rc, p


def test_a_rider_never_walks_off_its_mount():
    batt, cc, rc, p = _riding()
    batt.order = [rc, p, cc] + [u for u in batt.order if u not in (rc, p, cc)]
    batt.turn_idx = 0
    rc.ap = 2
    ai.take_turn(batt, rc)
    assert rc.mounted_on is cc and rc.pos == cc.pos


def test_a_rider_waits_for_its_mount_to_carry_it():
    batt, cc, rc, p = _riding()
    batt.order = [rc, cc, p]
    batt.turn_idx = 0
    rc.ap = 2
    ai.take_turn(batt, rc)
    assert rc.delayed and batt.order.index(rc) > batt.order.index(cc)


def test_a_rider_gets_off_beside_the_foe_and_strikes():
    batt, cc, rc, p = _riding(rider_pos=(5, 5), foe_pos=(5, 7))
    batt.order = [rc, cc, p]
    batt.turn_idx = 0
    rc.ap = 2
    with fixed_d20(18):
        ai.take_turn(batt, rc)
    assert rc.mounted_on is None and cc.rider is None
    assert batt.units_distance(rc, p) <= 1


def test_moving_while_mounted_does_nothing():
    batt, cc, rc, p = _riding()
    rc.ap = 2
    actions.MOVE.execute(batt, rc, (5, 8))
    assert rc.pos == (5, 5) and rc.ap == 2


def test_dismount_never_lands_under_a_large_mount():
    batt, cc, rc, p = _riding()
    body = set(batt.cells_of(cc))
    spots = actions.DISMOUNT.highlight_cells(batt, rc)
    assert spots and not body & set(spots)


# --------------------------------------------------------------------------- #
# The premise: two plain attacks win out of the action's case, the action in it #
# --------------------------------------------------------------------------- #

def _case(aid, favoured):
    """A duel set up for `aid`: plain, or in the action's favoured case."""
    from gartok.conditions import Entangled
    weapon = {"sneak_attack": "Dagger", "precise_thrust": "Rapier", "cleave": "Axe",
              "repel_strike": "Quarterstaff", "maiming_strike": "Club", "armor_pierce": "Pick",
              "power_shot": "Shortbow", "hook_shield": "Hatchet", "parry_strike": "Broadsword"}[aid]
    batt, e, p = _duel(weapon)
    e.ammo = 6
    if aid == "power_shot":
        p.pos = (13, 5) if favoured else (8, 5)
    if not favoured:
        return batt, e, p
    if aid in ("sneak_attack", "precise_thrust"):
        _recruit(batt, team="enemy").pos = (7, 5)
    elif aid == "cleave":
        _recruit(batt, team="player").pos = (6, 6)
    elif aid == "repel_strike":
        batt.board.walls = {(7, 5)}
    elif aid == "maiming_strike":
        p.add_condition(Entangled())
    elif aid == "hook_shield":
        p.equipped_offhand = "Dwarf Shield"
    elif aid == "parry_strike":
        _recruit(batt, team="player").pos = (4, 5)
    return batt, e, p


FLANK_ONLY = ("sneak_attack", "precise_thrust")     # no flank, no action at all
PREMISE = ("sneak_attack", "precise_thrust", "cleave", "repel_strike", "maiming_strike",
           "armor_pierce", "power_shot", "hook_shield", "parry_strike")


def test_every_weapon_action_loses_to_two_attacks_out_of_its_case_and_wins_in_it(monkeypatch):
    for aid in PREMISE:
        act = next(a for a in actions.WEAPON_ACTIONS if a.id == aid)
        for strength in (10, 14, 18):
            for ac in (10, 13, 16, 19):
                monkeypatch.setattr(ai.reckon, "_reckoned_ac", _ac(ac, pierced=ac - 3))
                for favoured in (False, True):
                    batt, e, p = _case(aid, favoured)
                    e.char.strength = strength
                    if aid == "armor_pierce" and favoured:
                        monkeypatch.setattr(type(act), "favoured", lambda self, b, a, t: True)
                    elif aid == "armor_pierce":
                        monkeypatch.setattr(type(act), "favoured", lambda self, b, a, t: False)
                    if aid in FLANK_ONLY and not favoured:
                        assert not act.can(batt, e, p), aid
                        continue
                    assert act.can(batt, e, p), aid
                    assert act.favoured(batt, e, p) is favoured, (aid, favoured)
                    worth = ai._weapon_action_worth(batt, e, act, p)
                    two = ai._two_points(batt, e, p)
                    case = f"{aid} STR {strength} AC {ac} {'favoured' if favoured else 'plain'}"
                    assert (worth > two) is favoured, f"{case}: action {worth:.2f} vs two attacks {two:.2f}"


def test_a_favoured_strike_lands_twice_over():
    batt, e, p = _case("maiming_strike", True)
    rolls = []
    real = type(e).damage_roll

    def spy(self, *a, **kw):
        out = real(self, *a, **kw)
        rolls.append(out)
        return out
    import gartok.combatant as combatant
    orig = combatant.Combatant.damage_roll
    combatant.Combatant.damage_roll = spy
    try:
        with fixed_d20(15):
            actions.MAIMING_STRIKE.execute(batt, e, p)
    finally:
        combatant.Combatant.damage_roll = orig
    assert len(rolls) == 2 and any("twice over" in ln for ln in batt.log_lines)

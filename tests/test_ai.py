"""The tendency-driven enemy AI."""

import random

from tests.helpers import (
    abilities, Battle, CustomScenario, fixed_d20, Unit, _melee_battle, _recruit,
)


def test_unarmed_ai_goes_for_a_dropped_weapon_before_fighting():
    from gartok import ai
    from gartok.ground import GroundObject
    batt, a, d = _melee_battle()
    batt.board.walls = set()
    d.disarm()
    batt.ground.append(GroundObject.weapon((10, 5), "Axe"))
    d.pos, d.ap = (8, 5), 2
    assert ai._recover_weapon(batt, d)                 # spent the action on the weapon
    assert d.pos != (8, 5) or not d.unarmed            # closed on it, or already grabbed it


def test_ai_reloads_an_empty_crossbow_rather_than_only_walking():
    from gartok import ai
    batt, a, d = _melee_battle()
    batt.board.walls = set()
    for u in batt.units:
        u._ability = abilities.get("none")
    d.equip_weapon("Light Crossbow")
    d.ammo, d.crossbow_loaded = 5, False
    d.pos, a.pos = (2, 5), (12, 5)
    batt.turn_idx = batt.order.index(d)
    d.ap = 2
    ai.take_turn(batt, d)
    assert d.ammo == 4                                 # a bolt left the quiver -> it reloaded


def test_chaotic_ai_breaks_early_but_lawful_holds_the_line():
    from gartok import ai
    random.seed(0)
    batt = Battle([Unit("player"), Unit("player")],
                  [Unit("enemy"), Unit("enemy")], lethal=True)
    a, b = batt.player_units
    e, mate = batt.enemy_units
    a.pos, b.pos = (13, 2), (13, 9)                    # the players are far off
    e.pos, mate.pos = (0, 5), (14, 5)                  # e on the edge, a clean run home
    e.hp = 1                                           # badly hurt, outnumbered
    e.alignment = "Chaotic and Neutral"
    assert ai._should_flee(batt, e)
    e.alignment = "Lawful and Neutral"                 # a lawful unit stays while its mate stands
    assert not ai._should_flee(batt, e)


def test_evil_ai_gives_a_downed_enemy_the_coup_de_grace():
    from gartok import ai
    batt, a, d = _melee_battle()
    d.alignment = "Chaotic and Evil"
    a.go_down(batt.log)                              # the player is dying, adjacent to d
    assert a.dying
    d.ap = 2
    batt.turn_idx = batt.order.index(d)
    with fixed_d20(20):                              # the finishing blow connects
        ai.take_turn(batt, d)
    assert a.dead


def test_neutral_ai_ignores_a_downed_enemy():
    from gartok import ai
    batt, a, d = _melee_battle()
    d.alignment = "Neutral and Neutral"
    a.go_down(batt.log)
    assert ai._finish_off(batt, d) is None


def test_good_ai_stabilizes_a_downed_ally_first():
    from gartok import ai
    batt, a, d = _melee_battle()
    mate = _recruit(batt, "enemy")
    d.alignment = "Lawful and Good"
    d.pos, mate.pos = (6, 5), (7, 5)
    mate.go_down(batt.log)
    d.ap = 2
    batt.turn_idx = batt.order.index(d)
    with fixed_d20(20):                              # the stabilize lands
        ai.take_turn(batt, d)
    assert mate.stable


def test_ai_never_flees_a_non_lethal_bout():
    from gartok import ai
    random.seed(0)
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")], lethal=False)
    e = batt.enemy_units[0]
    e.pos, e.hp, e.alignment = (0, 5), 1, "Chaotic and Evil"
    assert ai._should_flee(batt, e) is False


def test_ai_crosses_a_pit_trench_instead_of_stalling():
    """A pit that splits the whole board used to lock the melee AI into an
    endless defend loop. Now both sides climb through and the fight ends."""
    from gartok import ai
    m = {"deploy_player": [[2, 5]], "deploy_enemy": [[13, 5]], "ambient_light": True,
         "elevation": [[x, y, -2] for x in (7, 8) for y in range(12)]}
    for seed in range(8):
        random.seed(seed)
        batt = Battle([Unit("player"), Unit("player")],
                      [Unit("enemy"), Unit("enemy")], scenario=CustomScenario(m))
        guard = 0
        while batt.winner is None and guard < 1500:
            guard += 1
            ai.take_turn(batt, batt.active)
        assert batt.winner is not None, f"seed {seed} never resolved ({guard} turns)"

import json
from unittest.mock import patch

from gartok import actions, ai, data, npc_lib
from gartok.battle import Battle
from gartok.combatant import Combatant
from gartok.conditions import Grappled
from gartok.unit import Unit


def _make_unit(team="player", race_name="Human", **attrs):
    race = data.race_by_name(race_name)
    u = Unit(team, race=race)
    for k, v in attrs.items():
        setattr(u, k, v)
    u._derive_combat()
    return u


def _make_battle(u1, u2, pos1=(1, 1), pos2=(1, 2)):
    b = Battle([u1], [u2])
    c1 = b.player_units[0]
    c2 = b.enemy_units[0]
    c1.pos = pos1
    c2.pos = pos2
    return b, c1, c2


# --------------------------------------------------------------------------- #
# Grab & Escape Grapple mechanics                                             #
# --------------------------------------------------------------------------- #

def test_grab_success_and_escape():
    u1 = _make_unit("player", "Human", strength=14)
    u2 = _make_unit("enemy", "Human", strength=10, dexterity=10)
    b, c1, c2 = _make_battle(u1, u2)

    base_ac = c2.ac
    # Grab attempt: DC is 10 + max(10, 10) mod (0) = 10.
    # Attacker STR mod is +2. With d20 = 10, total = 12 >= 10 -> success!
    with patch("gartok.actions.combat.d20", return_value=10):
        actions.GRAB.execute(b, c1, c2)

    assert c2.has_condition("grappled")
    assert c2.speed == 0
    assert b.reachable(c2) == {}
    assert c2.ac == base_ac - 2

    # Cannot flee while grappled
    assert not actions.FLEE.available(b, c2)
    assert actions.FLEE.blocked_reason(b, c2) == "grappled"

    # Escape attempt: DC is 10 + c1 STR mod (2) = 12.
    # Target STR/DEX mod is 0. With d20 = 15, total = 15 >= 12 -> success!
    with patch("gartok.actions.combat.d20", return_value=15):
        actions.ESCAPE_GRAPPLE.execute(b, c2)

    assert not c2.has_condition("grappled")
    assert c2.speed > 0
    assert c2.ac == base_ac


def test_grapple_breaks_when_grappler_moves_or_dies():
    u1 = _make_unit("player", "Human", strength=14)
    u2 = _make_unit("enemy", "Human", strength=10)
    b, c1, c2 = _make_battle(u1, u2)

    with patch("gartok.actions.combat.d20", return_value=20):
        actions.GRAB.execute(b, c1, c2)
    assert c2.has_condition("grappled")

    # Grappler walks away -> grapple breaks
    b.move_unit(c1, (1, 0))
    assert not c2.has_condition("grappled")

    # Re-apply grapple (reset c1 AP and pos)
    c1.pos = (1, 1)
    c1.ap = 2
    with patch("gartok.actions.combat.d20", return_value=20):
        actions.GRAB.execute(b, c1, c2)
    assert c2.has_condition("grappled")

    # Grappler dies -> grapple breaks
    c1.hp = 0
    c1.status = "dead"
    b.check_grapples()
    assert not c2.has_condition("grappled")


# --------------------------------------------------------------------------- #
# Zombie racial talents: Death Grip & Zombie Bite                             #
# --------------------------------------------------------------------------- #

def test_zombie_talents_grab_bonus_and_bite():
    z = _make_unit("player", "Zombie")
    z.set_track_level("racial", 10)
    assert z.choose_talent("racial", "death_grip")
    assert z.has_talent("death_grip")
    assert z.talent_bonus("grab_bonus") == 2

    assert z.choose_talent("racial", "zombie_bite")
    assert z.has_talent("zombie_bite")

    target = _make_unit("enemy", "Human", strength=10, dexterity=10, hp=30)
    b, cz, ct = _make_battle(z, target)
    ct.hp_max = 30
    ct.hp = 30

    # Zombie Bite is NOT applicable when target is not grappled
    assert not actions.ZOMBIE_BITE.can(b, cz, ct)

    # Zombie grabs target: Death Grip gives +2 bonus
    with patch("gartok.actions.combat.d20", return_value=10):
        # 10 + STR (0) + grab_bonus (2) = 12 vs DC 10 -> success!
        actions.GRAB.execute(b, cz, ct)
    assert ct.has_condition("grappled")

    # Now Zombie Bite is available!
    assert actions.ZOMBIE_BITE.can(b, cz, ct)

    # Execute bite: 1d8 + STR damage, +2 circumstance to hit
    initial_hp = ct.hp
    with patch("gartok.actions.combat.d20", return_value=12), \
         patch("gartok.actions.combat.roll", return_value=6):
        actions.ZOMBIE_BITE.execute(b, cz, ct)

    # Damage dealt is 6 + STR (1) = 7
    assert ct.hp == initial_hp - (6 + cz.mod_strength)


# --------------------------------------------------------------------------- #
# Dragon racial talents: Sweeping Claws & Draconic Wings                       #
# --------------------------------------------------------------------------- #

def test_dragon_sweeping_claws_unarmed_cleave():
    dragon_race = data.race_by_name("Dragon")
    d = Unit("player", race=dragon_race)
    d.set_track_level("racial", 15)
    assert d.choose_talent("racial", "dragon")
    assert d.choose_talent("racial", "sweeping_claws")
    assert d.has_talent("sweeping_claws")
    assert d.talent_bonus("unarmed_cleave") == 1

    t1 = _make_unit("enemy", "Human", strength=10, hp=30)
    t2 = _make_unit("enemy", "Human", strength=10, hp=30)
    b = Battle([d], [t1, t2])
    c_d = b.player_units[0]
    c_t1 = b.enemy_units[0]
    c_t2 = b.enemy_units[1]

    # Dragon is unarmed in battle
    assert c_d.unarmed

    c_d.pos = (1, 1)
    c_t1.pos = (1, 2)
    c_t2.pos = (2, 2)

    app, _ = actions.CLEAVE.applicable(b, c_d)
    assert app
    assert "Sweeping Claws" in actions.CLEAVE.label(b, c_d)
    assert actions.CLEAVE.can(b, c_d, c_t1)
    assert actions.CLEAVE.second(b, c_d, c_t1) is c_t2

    # Cleave deals unarmed damage (2d6 for huge dragon)
    hp1_before = c_t1.hp
    hp2_before = c_t2.hp
    with patch("gartok.actions.weapon_actions.d20", return_value=15), \
         patch("gartok.combatant.roll", return_value=8):
        actions.CLEAVE.execute(b, c_d, c_t1)

    assert c_t1.hp < hp1_before
    assert c_t2.hp < hp2_before


def test_dragon_draconic_wings_speed_and_flight():
    dragon_race = data.race_by_name("Dragon")
    d = Unit("player", race=dragon_race)
    d.set_track_level("racial", 15)
    assert d.choose_talent("racial", "dragon")
    assert d.choose_talent("racial", "draconic_wings")
    assert d.has_talent("draconic_wings")
    assert d.speed == 12

    c = Combatant(d, "player")
    assert c.speed == 12
    assert c.flies is True
    assert c.can_move_vertically is True


def test_dragon_kharzuul_json():
    with open("npcs/dragon.json", "r", encoding="utf-8") as f:
        data_json = json.load(f)
    racial = data_json.get("talents", {}).get("racial", [])
    assert "dragon" in racial
    assert "dragon_breath" in racial
    assert "sweeping_claws" in racial
    assert "draconic_wings" in racial

    d = npc_lib.load_npc("dragon")
    assert d.speed == 12
    c = Combatant(d, "enemy")
    assert c.speed == 12
    assert c.flies is True


# --------------------------------------------------------------------------- #
# AI tests: Grab, Bite, and Escape                                            #
# --------------------------------------------------------------------------- #

def test_ai_zombie_combos_grab_and_bite():
    z = _make_unit("enemy", "Zombie", strength=14)
    z.set_track_level("racial", 10)
    z.choose_talent("racial", "death_grip")
    z.choose_talent("racial", "zombie_bite")

    target = _make_unit("player", "Human", strength=10, dexterity=10, hp=30)
    b = Battle([target], [z])
    ct = b.player_units[0]
    cz = b.enemy_units[0]
    ct.hp_max = 30
    ct.hp = 30
    cz.pos = (1, 1)
    ct.pos = (1, 2)
    cz.ap = 2
    b.order = [cz, ct]
    b.turn_idx = 0

    # With d20=15, first action will Grab, second action will Bite!
    with patch("gartok.actions.combat.d20", return_value=15), \
         patch("gartok.actions.combat.roll", return_value=6):
        ai.take_turn(b, cz)

    assert ct.has_condition("grappled")
    # Both 2 AP were spent: 1 on Grab, 1 on Zombie Bite!
    assert cz.ap == 0
    assert ct.hp < 30


def test_ai_grappled_ranged_unit_escapes():
    archer = _make_unit("enemy", "Human", dexterity=16, strength=10)
    archer.give_to_hand("Light Crossbow")
    archer.give_to_pack("Quiver")

    grappler = _make_unit("player", "Human", strength=10)
    b = Battle([grappler], [archer])
    cg = b.player_units[0]
    ca = b.enemy_units[0]
    ca.pos = (1, 1)
    cg.pos = (1, 2)

    ca.add_condition(Grappled(grappler=cg))
    assert ca.has_condition("grappled")
    ca.ap = 2
    b.order = [ca, cg]
    b.turn_idx = 0

    with patch("gartok.actions.combat.d20", return_value=18):
        ai.take_turn(b, ca)

    # Archer broke free!
    assert not ca.has_condition("grappled")

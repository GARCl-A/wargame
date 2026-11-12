"""The body as a weapon: Unarmed and the beasts' natural weapons, one variant per body size."""

from gartok import data, intel, items, natural_weapons
from gartok.ground import GroundObject
from tests.helpers import Battle, Unit, _melee_battle, actions, fitted, fixed_d20, standard_unit


def test_every_beast_names_its_weapon():
    for beast in data.BEASTS:
        assert beast[1] in natural_weapons.RACE_WEAPON, beast[1]


def test_every_named_weapon_exists_at_every_size():
    for name in natural_weapons.RACE_WEAPON.values():
        for size in data.SIZE_ORDER:
            assert natural_weapons.get(name, size) is not None


def test_dice_follow_the_size_ladder():
    ladder = {"Tiny": (1, 2), "Small": (1, 2), "Medium": (1, 3), "Large": (1, 4), "Huge": (1, 6)}
    for size, die in ladder.items():
        assert natural_weapons.get("Unarmed", size).damage == die
        assert natural_weapons.get("Bite", size).damage == die


def test_a_wolf_bites_and_a_large_wolf_has_a_large_bite():
    wolf = Unit("enemy", race=data.race_by_name("Wolf"))
    assert (wolf.natural_weapon.name, wolf.natural_weapon.damage) == ("Bite", (1, 3))
    wolf.talents["racial"].append("dire_growth")
    wolf._derive_combat()
    assert wolf.size == "Large"
    assert (wolf.natural_weapon.name, wolf.natural_weapon.damage) == ("Bite", (1, 4))


def test_natural_weapons_stay_out_of_the_item_registry():
    for name in natural_weapons.NAMES:
        assert items.get(name) is None
        assert name not in items.weapons()


def test_a_humanoid_fights_with_unarmed_at_its_size():
    u = standard_unit()
    assert u.natural_weapon.name == "Unarmed"
    assert u.natural_weapon.size == u.size


def test_a_humanoid_with_a_weapon_is_armed_and_without_one_unarmed():
    batt, _, fighter = _melee_battle()
    fighter.equip_weapon(fitted(fighter, "Broadsword"))
    assert fighter.armed and not fighter.unarmed and not fighter.natural
    fighter.disarm()
    assert fighter.unarmed and not fighter.armed and not fighter.natural
    assert fighter.weapon.name == "Unarmed"


def test_a_beast_is_natural_never_unarmed():
    wolf = Unit("enemy", race=data.race_by_name("Wolf"))
    batt = Battle([standard_unit()], [wolf])
    cw = batt.enemy_units[0]
    assert cw.natural and not cw.unarmed and not cw.armed
    assert cw.weapon.name == "Bite"
    assert actions.ATTACK.label(batt, cw) == "Bite"
    assert not cw.weapon.has_trait("cleave")


def test_only_bare_hands_pick_up_a_weapon():
    batt, _, fighter = _melee_battle()
    fighter.equip_weapon(fitted(fighter, "Broadsword"))
    obj = GroundObject.weapon((0, 0), fitted(fighter, "Dagger"))
    assert not actions.base._pickable(fighter, obj)
    fighter.disarm()
    assert actions.base._pickable(fighter, obj)
    wolf = Battle([standard_unit()], [Unit("enemy", race=data.race_by_name("Wolf"))]).enemy_units[0]
    assert not actions.base._pickable(wolf, obj)


def test_a_talent_grants_a_trait_to_the_body_weapon_only():
    dragon = Unit("player", race=data.race_by_name("Dragon"))
    assert not dragon.natural_weapon.has_trait("cleave")
    dragon.talents["racial"] += ["dragon", "sweeping_claws"]
    assert dragon.natural_weapon.has_trait("cleave")
    skeleton = standard_unit()
    skeleton.talents["racial"].append("deft_bones")
    assert skeleton.natural_weapon.is_finesse
    assert not items.get("Dagger").has_trait("cleave")


def test_a_crossbow_swung_empty_hits_with_the_body_die():
    batt, _, fighter = _melee_battle()
    fighter.equip_weapon(fitted(fighter, "Crossbow"))
    fighter.ammo = 0
    assert fighter.improvised
    assert fighter.hand_die == fighter.char.natural_weapon.damage


def test_a_foe_shows_the_name_of_its_natural_weapon_and_its_action():
    wolf = Unit("enemy", race=data.race_by_name("Wolf"))
    batt = Battle([standard_unit()], [wolf])
    known = intel.known_fields(batt, "player", batt.enemy_units[0])
    assert known.visible["weapon"] == "Bite" and known.visible["weapon_action"] == "Clamp"


# --------------------------------------------------------------------------- #
# Body actions: Trample (Hooves) and Clamp (Bite)
# --------------------------------------------------------------------------- #

def _beast_scene(race, foe_pos=None):
    """A beast of `race` (enemy side, two points) beside a standard player with room behind it
    (a Large body fills four cells, so its neighbour stands one cell further off)."""
    foe_pos = foe_pos or ((7, 5) if race == "Horse" else (6, 5))
    batt = Battle([standard_unit("player")], [Unit("enemy", race=data.race_by_name(race))])
    beast, foe = batt.enemy_units[0], batt.player_units[0]
    batt.board.walls, batt.board.elevation = set(), {}
    batt.ambient_light = True
    beast.turns_taken = foe.turns_taken = 1
    beast.pos, foe.pos = (5, 5), foe_pos
    beast.ap = 2
    foe.hp = foe.char.hp_max = 60
    return batt, beast, foe


def _log_text(batt):
    return "\n".join(str(line) for line in batt.log_lines) if hasattr(batt, "log_lines") else ""


def test_each_action_is_offered_only_to_its_own_body_with_nothing_in_hand():
    batt, horse, foe = _beast_scene("Horse")
    assert actions.TRAMPLE.applicable(batt, horse)[0] and not actions.CLAMP.applicable(batt, horse)[0]
    batt, wolf, foe = _beast_scene("Wolf")
    assert actions.CLAMP.applicable(batt, wolf)[0] and not actions.TRAMPLE.applicable(batt, wolf)[0]
    assert not actions.CLAMP.applicable(batt, foe)[0] and not actions.TRAMPLE.applicable(batt, foe)[0]


def test_neither_action_is_available_with_one_point():
    for race, act in (("Horse", actions.TRAMPLE), ("Wolf", actions.CLAMP)):
        batt, beast, foe = _beast_scene(race)
        assert act.can(batt, beast, foe)
        beast.ap = 1
        assert not act.can(batt, beast, foe)


def test_both_cost_two_points_once():
    for race, act in (("Horse", actions.TRAMPLE), ("Wolf", actions.CLAMP)):
        batt, beast, foe = _beast_scene(race)
        with fixed_d20(15):
            act.execute(batt, beast, foe)
        assert beast.ap == 0


def test_trample_strikes_then_shoves_then_takes_down_in_that_order(monkeypatch):
    batt, horse, foe = _beast_scene("Horse")
    order = []
    monkeypatch.setattr(actions.weapon_actions, "_strike", lambda *a, **k: order.append("strike") or "hit")
    monkeypatch.setattr(actions.combat.Push, "shove", classmethod(lambda cls, *a: order.append("shove")))
    monkeypatch.setattr(actions.combat.Takedown, "knock_down", staticmethod(lambda *a: order.append("takedown")))
    actions.TRAMPLE.execute(batt, horse, foe)
    assert order == ["strike", "shove", "takedown"]


def test_trample_stops_cleanly_when_the_foe_dies_on_the_first_step(monkeypatch):
    batt, horse, foe = _beast_scene("Horse")
    foe.hp = 1
    order = []
    monkeypatch.setattr(actions.combat.Push, "shove", classmethod(lambda cls, *a: order.append("shove")))
    monkeypatch.setattr(actions.combat.Takedown, "knock_down", staticmethod(lambda *a: order.append("takedown")))
    with fixed_d20(20):
        actions.TRAMPLE.execute(batt, horse, foe)
    assert not foe.alive and order == [] and horse.ap == 0


def test_trample_skips_the_takedown_when_the_shove_throws_the_foe_out_of_reach():
    batt, horse, foe = _beast_scene("Horse")
    with fixed_d20(20):
        actions.TRAMPLE.execute(batt, horse, foe)
    assert foe.pos == (8, 5) and not foe.has_condition("prone")


def test_trample_takes_the_foe_down_when_the_shove_has_nowhere_to_go():
    batt, horse, foe = _beast_scene("Horse")
    batt.board.walls = {(8, 5), (8, 4), (8, 6)}
    with fixed_d20(20):
        actions.TRAMPLE.execute(batt, horse, foe)
    assert foe.pos == (7, 5) and foe.has_condition("prone")


def test_clamp_grabs_on_a_hit_and_not_on_a_miss():
    batt, wolf, foe = _beast_scene("Wolf")
    with fixed_d20(1):
        actions.CLAMP.execute(batt, wolf, foe)
    assert not foe.has_condition("grappled")
    batt, wolf, foe = _beast_scene("Wolf")
    with fixed_d20(20):
        actions.CLAMP.execute(batt, wolf, foe)
    held = foe.condition("grappled")
    assert held is not None and held.grappler is wolf


def test_clamp_is_brutal_on_a_foe_already_grappled():
    from gartok.conditions import Grappled

    def brutal(held):
        batt, wolf, foe = _beast_scene("Wolf")
        if held:
            foe.add_condition(Grappled(grappler=wolf))
        seen = []
        real = wolf.damage_roll
        wolf.damage_roll = lambda **kw: seen.append(kw["brutal"]) or real(**kw)
        with fixed_d20(15):
            actions.CLAMP.execute(batt, wolf, foe)
        return seen[0]
    assert brutal(held=False) == 0 and brutal(held=True) == 1


def test_clamp_does_not_grab_a_foe_it_killed():
    batt, wolf, foe = _beast_scene("Wolf")
    foe.hp = 1
    with fixed_d20(20):
        actions.CLAMP.execute(batt, wolf, foe)
    assert not foe.alive and not foe.has_condition("grappled")


def test_a_fight_with_both_actions_is_recorded_as_one_row_each(tmp_path):
    from gartok import combat_log
    for race, act in (("Horse", actions.TRAMPLE), ("Wolf", actions.CLAMP)):
        batt, beast, foe = _beast_scene(race)
        log = combat_log.CombatLog(str(tmp_path / f"{race}.jsonl"), {}, {"player": "human", "enemy": "ai"})
        batt.record_to(log)
        with fixed_d20(15):
            act.execute(batt, beast, foe)
        log.end(batt)
        rows = [r for r in combat_log.load(log.path) if r["e"] == "act"]
        assert [r["action"] for r in rows] == [act.id]
        assert rows[0]["ap"] == 2 and act.id in rows[0]["options"], race


def test_a_fight_with_both_body_actions_replays_from_its_log(tmp_path):
    from gartok import combat_log
    for race, act in (("Horse", actions.TRAMPLE), ("Wolf", actions.CLAMP)):
        batt, beast, foe = _beast_scene(race)
        log = combat_log.CombatLog(str(tmp_path / f"{race}.jsonl"), {}, {})
        batt.record_to(log)
        with fixed_d20(20):
            act.execute(batt, beast, foe)
        rows = combat_log.load(log.path)
        assert [r["action"] for r in rows[1:]] == [act.id]
        seen = combat_log.frames(rows)[-1]["units"]
        for unit, state in zip(batt.units, seen):
            assert (state["hp"], (state["x"], state["y"])) == (unit.hp, tuple(unit.pos))

"""The Snake: a Small beast of the Lumber Yard -- Fangs, every attack a finesse attack, a gland it
drops, and three racial talents (two growths and Snake Venom)."""

import random

from gartok import actions, ai, data, encounters, gather, loot, poisons, sources, talents
from gartok.battle import Battle
from gartok.ground import GroundObject
from gartok.unit import Unit

VENOM = "snake_venom"


def _human(con=10):
    u = Unit("player", race=data.race_by_name("Human"))
    u.set_base_attribute("constitution", con)
    return u


def _snake(*picks, racial=0):
    random.seed(41)
    sn = Unit("enemy", race=data.race_by_name("Snake"))
    if racial or picks:
        sn.set_track_level("racial", max(racial, 10 if picks else 0))
    for p in picks:
        assert sn.choose_talent("racial", p)
    return sn


def _fight(snake):
    batt = Battle([_human()], [snake])
    sn, victim = batt.enemy_units[0], batt.player_units[0]
    sn.pos, victim.pos = (5, 5), (6, 5)
    batt.board.walls.clear()
    batt.ground[:] = [GroundObject.torch((5, 4))]
    sn.ap = 2
    return batt, sn, victim


def _force(monkeypatch, attack=20, save=1):
    monkeypatch.setattr("gartok.actions.combat.d20", lambda: attack)
    monkeypatch.setattr(data, "d20", lambda: save)


def test_the_snake_is_a_small_beast_with_its_attributes_and_a_gland():
    race = data.race_by_name("Snake")
    assert race["kind"] == "beast" and race["size"] == "Small"
    assert race["mods"] == (-2, 4, 1, -1, 2, -1)
    assert race["drop_item"] == "Snake Venom Gland" and race["ability"] == "serpentine"
    assert race in data.BEAST_POOL and race not in data.WILD_POOL and data.SNAKE_POOL == [race]


def test_the_snake_gland_has_a_source_in_the_snake():
    assert sources.sources_of("Snake Venom Gland") == [sources.Source(sources.DROPPED, "Snake")]


def test_every_attack_of_a_snake_is_a_finesse_attack():
    sn = _snake()
    assert sn.strength < sn.dexterity
    assert sn.attack_bonus == (sn.mod_dexterity, "STR/DEX")
    batt, snake, victim = _fight(sn)
    mods = snake.attack_mods(victim)
    assert (sn.mod_dexterity, None, "STR/DEX") in mods


def test_an_unarmed_beast_without_the_ability_still_hits_with_strength():
    ox = Unit("enemy", race=data.race_by_name("Ox"))
    assert ox.attack_bonus == (ox.mod_strength, "STR")


def test_the_snake_attacks_with_fangs():
    batt, snake, victim = _fight(_snake())
    assert actions.Attack().label(batt, snake) == "Fangs"
    assert actions.Attack().label(batt, victim) == "Attack"


def test_a_fang_bite_is_logged_as_one(monkeypatch):
    _force(monkeypatch)
    batt, snake, victim = _fight(_snake())
    actions.Attack().execute(batt, snake, victim)
    assert any("(fangs)" in line for line in batt.log_lines)


def test_the_two_growths_take_a_snake_from_small_to_large_and_need_each_other():
    sn = _snake()
    assert sn.size == "Small"
    assert not sn.choose_talent("racial", "great_serpent")
    sn = _snake("serpent_growth")
    assert sn.size == "Medium"
    sn = _snake("serpent_growth", "great_serpent")
    assert sn.size == "Large"


def test_the_snake_talents_are_the_snakes_alone():
    human = Unit("player", race=data.race_by_name("Human"))
    human.set_track_level("racial", 10)
    for tid in ("serpent_growth", "great_serpent", "snake_venom"):
        assert not human.choose_talent("racial", tid)
    assert {t.id for t in talents.racial_tree("Snake")} == {
        "serpent_growth", "great_serpent", "snake_venom"}


def test_a_snake_has_no_venom_until_it_takes_the_talent():
    assert _snake().venom is None
    assert _snake("snake_venom").venom == VENOM
    spider = Unit("enemy", race=data.race_by_name("Giant Spider"))
    assert spider.venom == "giant_spider_venom"


def test_the_venom_eats_constitution_and_the_dc_follows_the_racial_level():
    victim = _human(con=12)
    victim.add_poison(VENOM, 11)
    victim.add_poison(VENOM, 11)
    assert victim.constitution == 10 and victim.dexterity == victim.base_attributes["dexterity"]
    assert "Snake Venom 2" in victim.poison_label
    assert poisons.save_dc(poisons.get(VENOM), _snake(racial=4)) == 15


def test_a_venomous_bite_poisons_a_victim_who_fails_the_save(monkeypatch):
    _force(monkeypatch, attack=20, save=1)
    batt, snake, victim = _fight(_snake("snake_venom"))
    actions.Attack().execute(batt, snake, victim)
    assert victim.char.poisons.get(VENOM, {}).get("level") == 1


def test_a_plain_snake_bite_poisons_nobody(monkeypatch):
    _force(monkeypatch, attack=20, save=1)
    batt, snake, victim = _fight(_snake())
    actions.Attack().execute(batt, snake, victim)
    assert not victim.char.poisoned


def test_a_victim_who_makes_the_save_shakes_it_off(monkeypatch):
    _force(monkeypatch, attack=20, save=20)
    batt = Battle([_human(con=30)], [_snake("snake_venom")])
    snake, victim = batt.enemy_units[0], batt.player_units[0]
    snake.pos, victim.pos = (5, 5), (6, 5)
    snake.ap = 2
    actions.Attack().execute(batt, snake, victim)
    assert not victim.char.poisoned


def test_the_yard_rolls_snakes_and_a_dead_one_drops_its_gland():
    entry_races = {r["name"] for e in encounters.LUMBER_YARD_TABLE for r in (e.race_pool or ())}
    assert "Snake" in entry_races and "Snake" not in {
        r["name"] for e in encounters.MINE_TABLE for r in (e.race_pool or ())}

    class AlwaysDrop:
        def random(self):
            return 0.0

    batt = Battle([Unit("player")], [_snake(), _snake()])
    pool = loot.field_loot(batt, [], rng=AlwaysDrop())
    assert pool.count("Snake Venom Gland") == 2


def test_the_ai_plays_a_snake_fight_to_the_end():
    random.seed(9)
    pack = [_snake("snake_venom"), _snake()]
    battle = Battle([_human(), _human()], pack, lethal=True, aggressor="enemy")
    for _ in range(600):
        if battle.winner is not None:
            break
        ai.take_turn(battle, battle.active)
    assert battle.winner is not None


def test_a_gather_ambush_at_the_yard_can_be_snakes():
    rng = random.Random(5)
    seen = {u.race["name"] for _ in range(200) for u in gather.ambush_pack("lumber_yard", rng)}
    assert {"Wolf", "Snake", "Giant Spider"} <= seen

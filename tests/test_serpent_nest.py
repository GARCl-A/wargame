"""The Snake Dragon's job (serpent_nest.py, the two exclusive missions in missions.py)."""

import random
from types import SimpleNamespace
from unittest.mock import patch

from gartok import captives, factions, loot, missions, npc_lib, serpent_nest, world
from gartok.board import grid_distance
from gartok.guild import Guild
from tests.helpers import Battle, Unit, items


def _sanctuaries_open():
    u = Unit("player")
    guild = Guild([u], node="lumber_yard")
    guild.missions.append(missions.Mission(missions.LIBRARY_ANCIENT_CODEX.id, u.uid, 0, None, state="done"))
    return guild, u


def test_the_snake_dragon_is_a_snake_with_dragon_blood():
    d = npc_lib.load_npc(serpent_nest.DRAGON_SLUG)
    assert d.race["name"] == "Snake" and d.combat_level == 8
    assert d.size == "Medium" and d.has_talent("serpent_growth")
    assert d.has_talent("dragon_breath") and "blood" in d.magic_sources
    assert d.picks_available("racial") == 0 and d.picks_available("magic") == 0


def test_both_schools_offer_the_snake_once_the_sanctuaries_are_open():
    guild, _ = _sanctuaries_open()
    assert missions.BLOOD_SNAKE in missions.offers_at(guild, "blood_sanctuary")
    assert missions.NATURE_SNAKE in missions.offers_at(guild, "nature_grove")
    assert missions.BLOOD_SNAKE not in missions.offers_at(Guild([Unit("player")]), "blood_sanctuary")


def test_the_nest_is_hidden_off_the_lumber_yard():
    node = world.node(serpent_nest.NODE)
    assert node.hidden and node.has("serpents_nest")
    assert serpent_nest.NODE in [v for v, _ in world.neighbors("lumber_yard")]


def test_searching_finds_the_nest_only_with_a_snake_job_out():
    guild, u = _sanctuaries_open()
    group = guild.groups[0]
    with patch("gartok.serpent_nest.data.d20", return_value=20):
        assert not serpent_nest.search(guild, group)[0]
        missions.accept(guild, u, missions.BLOOD_SNAKE)
        assert serpent_nest.search(guild, group)[0]
    assert guild.is_node_revealed(serpent_nest.NODE)


def _nest_battle(dragon=True):
    sc = serpent_nest.NestScenario(2, random.Random(1), dragon=dragon)
    return Battle([Unit("player")], sc.enemies, scenario=sc, lethal=True)


def test_five_chambers_all_reachable_from_the_entrance():
    batt = _nest_battle()
    board = batt.board
    for room in serpent_nest.ROOMS:
        cell = (room[0], room[1])
        assert board.path_to((2, 8), cell), room
    assert board.deep_water and board.difficult


def test_the_packs_sleep_in_their_chambers_and_the_dragon_in_its_lair():
    batt = _nest_battle()
    dragon = serpent_nest.dragon_of(batt)
    assert dragon is not None and dragon.pos == serpent_nest.DRAGON_CELL
    assert all(u.dormant for u in batt.enemy_units)
    assert all(grid_distance(u.pos, batt.player_units[0].pos) > serpent_nest.AWARENESS
               for u in batt.enemy_units)


def test_the_fight_is_won_when_the_dragon_is_dead_or_bound():
    batt = _nest_battle()
    dragon = serpent_nest.dragon_of(batt)
    assert batt.scenario.win_check(batt) is None
    dragon.captured = True
    assert batt.scenario.win_check(batt) == "player"
    dragon.captured, dragon.status = False, "dead"
    assert batt.scenario.win_check(batt) == "player"


def test_a_fallen_dragon_left_unbound_leaves_its_body_and_a_bound_one_does_not():
    batt = _nest_battle()
    dragon = serpent_nest.dragon_of(batt)
    dragon.status = "stable"
    assert items.SNAKE_DRAGON_CORPSE_ITEM in loot.field_loot(batt, [])
    dragon.captured = True
    assert items.SNAKE_DRAGON_CORPSE_ITEM not in loot.field_loot(batt, [])


def test_the_body_goes_to_the_blood_cult_and_the_grove_is_failed():
    guild, u = _sanctuaries_open()
    m = missions.accept(guild, u, missions.BLOOD_SNAKE)
    other = missions.accept(guild, u, missions.NATURE_SNAKE)
    u.give_to_pack(items.SNAKE_DRAGON_CORPSE_ITEM)
    earned = missions.turn_in(guild, m)
    assert [d.id for d in earned] == ["blood_snake"]
    assert other.state == "failed" and missions.closed(guild, missions.NATURE_SNAKE)
    assert factions.failed(guild, factions.DEEDS["nature_snake"])
    assert not serpent_nest.dragon_home(guild)


def test_the_captive_goes_alive_to_the_grove():
    guild, u = _sanctuaries_open()
    m = missions.accept(guild, u, missions.NATURE_SNAKE)
    assert missions.snake_wanted_alive(guild)
    group = guild.groups[0]
    assert not missions.can_turn_in(guild, m)
    group.captives.append(captives.Captive(Unit("enemy"), 0, missions.SNAKE_SLUG))
    assert missions.progress(guild, m) == 1
    earned = missions.turn_in(guild, m)
    assert [d.id for d in earned] == ["nature_snake"] and not group.captives
    assert factions.failed(guild, factions.DEEDS["blood_snake"])


def test_a_closed_codex_delivery_shows_as_failed():
    guild, _u = _sanctuaries_open()
    guild.deeds_done.append("faith_codex")
    assert factions.failed(guild, factions.DEEDS["blood_codex"])
    assert not factions.failed(guild, factions.DEEDS["faith_codex"])
    assert factions.DEEDS["blood_codex"] not in factions.open_deeds(guild)


def test_an_emptied_lair_has_no_dragon():
    batt = _nest_battle(dragon=False)
    assert serpent_nest.dragon_of(batt) is None


def test_entering_the_nest_wants_the_dragon_alive_for_the_grove():
    guild, u = _sanctuaries_open()
    missions.accept(guild, u, missions.NATURE_SNAKE)
    entered = SimpleNamespace(battle=None)

    from gartok.app import App
    app = App.__new__(App)
    app.guild, app._map_notices = guild, []
    app._leave_outside = lambda *a: None
    app._enter_battle = lambda battle, node: setattr(entered, "battle", battle)
    app._delve_nest(guild.groups[0], world.node(serpent_nest.NODE), [u], True)
    dragon = serpent_nest.dragon_of(entered.battle)
    assert dragon in entered.battle.wanted_alive

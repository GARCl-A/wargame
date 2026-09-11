"""matchup.build: turning a world node + arena Bout into (enemies, scenario)."""

import random

from gartok import arena, matchup, world
from gartok.guild import Guild
from gartok.scenario import (ArenaScenario, CustomFlagScenario, CustomScenario,
                             FlagScenario)
from tests.helpers import Unit


def _guild(**over):
    g = Guild([Unit("player")])
    for k, v in over.items():
        setattr(g, k, v)
    return g


def test_a_plain_node_fight_is_generic_enemies_on_the_node_scenario():
    enemies, scenario = matchup.build(world.node("arena"), None,
                                      squad_size=3, guild=_guild())
    assert len(enemies) == 3 and all(e.team == "enemy" for e in enemies)
    assert isinstance(scenario, ArenaScenario)


def test_a_staked_tier_scales_its_opponents_to_the_bout_level():
    random.seed(1)
    iron = next(b for b in world.ARENA_TIERS if b.name == "Iron cage")   # level 2, 3 enemies
    enemies, scenario = matchup.build(world.node("arena"), iron,
                                      squad_size=1, guild=_guild())
    assert len(enemies) == iron.enemies
    assert all(e.mean_level == iron.level for e in enemies)   # scaled, not bare level 0
    assert isinstance(scenario, ArenaScenario) and not isinstance(scenario, FlagScenario)


def test_the_champion_bout_fields_adelio_on_the_authored_map():
    enemies, scenario = matchup.build(world.node("arena"), arena.champion_bout(),
                                      squad_size=2, guild=_guild())
    assert getattr(enemies[0], "arena_role", None) == "champion"
    assert len(enemies) == 3                              # champion + 2 goons
    assert isinstance(scenario, CustomScenario)


def test_a_games_ctf_bout_is_stage2_pack_on_a_flag_scenario():
    random.seed(2)
    enemies, scenario = matchup.build(world.node("arena"), arena.ctf_bout(),
                                      squad_size=3, guild=_guild(deeds_done=["arena_dethrone"]))
    assert len(enemies) == 3 and all(e.mean_level >= 1 for e in enemies)
    assert isinstance(scenario, FlagScenario)


def test_the_boss_bout_fields_the_ribbit_brothers_plus_goons_on_the_authored_ctf_map():
    random.seed(3)
    enemies, scenario = matchup.build(
        world.node("arena"), arena.boss_bout(),
        squad_size=6, guild=_guild(deeds_done=["arena_dethrone"]))
    brothers = [e for e in enemies if not e._auto_name]
    goons = [e for e in enemies if e._auto_name]
    assert {e.name for e in brothers} == {"Ribit", "Bufo", "Peep"}
    assert all(e.race["name"] == "Grippli" and e.mean_level == 4 for e in brothers)
    assert len(goons) == arena.BOSS_GOONS
    assert all(e.mean_level == arena.BOSS_GOON_LEVEL for e in goons)
    assert isinstance(scenario, CustomFlagScenario) and scenario.is_ctf


def test_a_title_defense_is_one_challenger_scaled_to_the_champion():
    champ = Unit("player")
    champ.arena_title = True
    champ.set_track_level("combat", 4)                    # mean level 2
    guild = Guild([champ])
    enemies, _ = matchup.build(world.node("arena"), arena.defense_bout(),
                               squad_size=1, guild=guild)
    assert len(enemies) == 1 and enemies[0].mean_level == champ.mean_level + 1


def test_the_dethroned_adelio_can_cameo_in_an_ordinary_pit_bout():
    rookie = next(b for b in world.ARENA_TIERS if b.rep == 0)
    guild = _guild(deeds_done=["arena_dethrone"])
    adelio = arena.load_champion().name
    names = set()
    for seed in range(80):
        random.seed(seed)
        enemies, _ = matchup.build(world.node("arena"), rookie, squad_size=1, guild=guild)
        names.update(e.name for e in enemies)
    assert adelio in names                                # the 5% cameo lands within 80 rolls

    # ...but only once the champion has been dethroned
    fresh = _guild()
    random.seed(0)
    calm = {e.name for _ in range(80)
            for e in matchup.build(world.node("arena"), rookie, squad_size=1, guild=fresh)[0]}
    assert adelio not in calm

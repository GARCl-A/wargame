"""Scenarios, the world-map graph, the clock and enemy scaling."""

import random

from tests.helpers import (
    abilities, Battle, Board, COLS, CustomScenario, ErmosScenario, ROWS, Unit,
)


# --------------------------------------------------------------------------- #
# scenarios and the world map                                                  #
# --------------------------------------------------------------------------- #

def _right_edge_goals():
    return [(COLS - 1, y) for y in range(ROWS)]


def test_board_seg_params_keep_sides_connected():
    random.seed(1)
    b = Board(min_seg=1, max_seg=2)
    assert Board._sides_connected(b.walls, (0, 0), _right_edge_goals())


def test_ermos_scenario_builds_lit_connected_board():
    random.seed(0)
    batt = Battle([Unit("player")], [Unit("enemy")], scenario=ErmosScenario())
    assert batt.ambient_light is True
    assert len(batt.units) == 2
    assert Board._sides_connected(batt.board.walls, (0, 0), _right_edge_goals())


def test_ambient_light_sees_without_a_torch():
    random.seed(1)
    batt = Battle([Unit("player")], [Unit("enemy")], scenario=ErmosScenario())
    batt.board.walls = set()
    batt.ground = []                                  # nothing emitting light
    for u in batt.units:                              # no light source, no darkvision
        u.weapon_hand = u.torch_hand = False
        u.inventory, u._ability = ["Sack"], abilities.get("none")
    p, e = batt.units
    p.pos, e.pos = (2, 2), (12, 9)
    assert batt.can_see(p, (8, 2)) is True            # daylight: a torch would be needed in the arena


def test_battle_runs_with_a_partial_squad():
    random.seed(0)
    squad = [Unit("player"), Unit("player")]          # two of a larger guild
    batt = Battle(squad, [Unit("enemy") for _ in range(2)])
    assert len(batt.player_units) == 2 and len(batt.units) == 4


def test_world_route_takes_the_cheapest_path():
    from gartok import world
    assert world.route("city", "city") == (["city"], 0)
    path, hours = world.route("city", "arena")
    assert path == ["city", "arena"] and hours == 2
    # cidade->estrada is 4 direct, but cidade->arena->estrada is 2+3=5, so direct wins
    path, hours = world.route("city", "road")
    assert hours == 4 and path == ["city", "road"]
    # multi-hop: cidade -> ... -> ermos
    path, hours = world.route("city", "wilds")
    assert path[0] == "city" and path[-1] == "wilds"
    assert hours == sum(w for a, b, w in world.EDGES
                        if {a, b} in [set(p) for p in zip(path, path[1:])])


# --------------------------------------------------------------------------- #
# encounters: enemies scaled to a place                                        #
# --------------------------------------------------------------------------- #
def test_weighted_choice_follows_the_weights():
    from gartok import encounters
    rng = random.Random(1)
    counts = {}
    for _ in range(4000):
        k = encounters.weighted_choice({"a": 1, "b": 3}, rng)
        counts[k] = counts.get(k, 0) + 1
    assert counts["a"] < counts["b"]                       # 1:3 -- b clearly more often
    assert 2.0 < counts["b"] / counts["a"] < 4.5           # roughly the ratio


def test_build_enemy_hits_the_mean_level_with_valid_talents():
    from gartok import encounters, talents
    rng = random.Random(7)
    for M in range(5):
        u = encounters.build_enemy(M, rng)
        assert u.mean_level == M
        for track, picked in u.talents.items():
            for tid in picked:
                t = talents.get(tid)
                assert t.requires is None or t.requires in picked   # tree respected


def test_build_enemy_is_reproducible_under_a_seed():
    """`build_enemy` still rolls HD/attributes off the global stream (like any
    Unit), but with a fixed global seed + an explicit choice rng the whole enemy
    -- levels, talents and all -- comes out identical every time."""
    from gartok import encounters

    def one():
        random.seed(123)
        u = encounters.build_enemy(3, random.Random(0))
        return (u.combat_level, u.work_level, u.hp_max,
                tuple(u.talents["combat"]), tuple(u.talents["work"]))

    assert one() == one()


def test_roll_pack_size_is_in_range():
    from gartok import encounters
    rng = random.Random(3)
    for _ in range(200):
        pack = encounters.roll_pack(rng=rng)
        assert 1 <= len(pack) <= 6
        assert all(0 <= u.mean_level <= 4 for u in pack)


def test_build_challenger_still_scales():
    from gartok import arena
    random.seed(0)
    u = arena.build_challenger(2)
    assert u.mean_level == 2


# --------------------------------------------------------------------------- #
# the scenario win-condition seam                                              #
# --------------------------------------------------------------------------- #
def test_scenario_win_check_forces_the_winner():
    from gartok.scenario import ArenaScenario

    class PlayerWins(ArenaScenario):
        def win_check(self, battle):
            return "player"

    class EnemyWins(ArenaScenario):
        def win_check(self, battle):
            return "enemy"

    random.seed(0)
    b = Battle([Unit("player")], [Unit("enemy")], scenario=PlayerWins())
    assert b._check_winner() == "player"                   # nobody down, still a win
    assert not b.enemy_units[0].dead                        # the seam doesn't kill anyone itself

    b = Battle([Unit("player"), Unit("player")], [Unit("enemy")],
               scenario=EnemyWins(), lethal=True)
    b.player_units[0].take_damage(999, b.log)               # one already bleeding out
    assert b._check_winner() == "enemy"
    assert b.player_units[0].dead                           # a lethal loss finishes the downed
    assert b.player_units[1].survived                       # ...but the one still standing lives


def test_field_loot_gathers_the_dead_and_the_ground():
    from gartok import loot
    from gartok.ground import GroundObject
    random.seed(4)
    squad = [Unit("player")]
    enemies = [Unit("enemy"), Unit("enemy")]
    batt = Battle(squad, enemies)
    for e in batt.enemy_units:                        # freeze known kit
        e.weapon_hand, e.weapon_name = True, "Axe"
        e.torch_hand = False
        e.inventory = ["Rope"]
    dead_ally = batt.player_units[0]
    dead_ally.weapon_hand, dead_ally.weapon_name = True, "Dagger"
    dead_ally.inventory = []
    batt.ground = [GroundObject.weapon((3, 3), "Club"), GroundObject.torch((4, 4))]

    pool = loot.field_loot(batt, [dead_ally])
    assert sorted(pool) == ["Axe", "Axe", "Club", "Dagger", "Rope", "Rope", "Torch"]


def test_field_loot_includes_a_fallen_enemys_equipped_lantern():
    from gartok import data, loot
    random.seed(4)
    enemy = Unit("enemy")
    batt = Battle([Unit("player")], [enemy])
    e = batt.enemy_units[0]
    e.weapon_hand, e.weapon_name = False, None
    e.torch_hand, e.lantern_hand = False, True
    e.inventory = []
    batt.ground = []

    pool = loot.field_loot(batt, [])
    assert pool == [data.LANTERN_ITEM]


def test_non_lethal_battle_knocks_out_and_keeps_everyone():
    random.seed(0)
    squad = [Unit("player"), Unit("player")]
    batt = Battle(squad, [Unit("enemy") for _ in range(2)], lethal=False)
    for u in batt.units:
        assert u.nonlethal
    for u in batt.player_units:                       # squad wiped
        u.take_damage(999, batt.log)
        assert u.status == "stable" and not u.dying
    batt._check_winner()
    assert batt.winner == "enemy"
    for u in batt.player_units:                       # a lost bout kills nobody
        assert u.survived and not u.dead


def test_guild_gold_is_the_sum_of_the_roster():
    from gartok.guild import Guild
    roster = [Unit("player") for _ in range(3)]
    for m, g in zip(roster, (5, 12, 3)):
        m.gold = g
    assert Guild(roster).gold == 20


def test_clock_tracks_day_and_daylight():
    from gartok.clock import Clock
    c = Clock()
    assert c.day == 1 and c.hour_of_day == 0 and not c.is_daylight   # midnight
    c.advance_hours(9)
    assert c.hour_of_day == 9 and c.is_daylight and c.phase == "day"
    c.advance_hours(10)                               # 19:00
    assert c.hour_of_day == 19 and not c.is_daylight
    c.advance_hours(6)                                # 01:00 next day
    assert c.day == 2 and c.hour_of_day == 1
    c.advance_rounds(10)                              # 60s -> 01:01
    assert c.minute_of_hour == 1


def test_ermos_daylight_follows_the_clock():
    random.seed(0)
    night = Battle([Unit("player")], [Unit("enemy")],
                   scenario=ErmosScenario(), daylight=False)
    assert night.ambient_light is False
    assert not night.ground                           # open country: bring your own torch
    random.seed(0)
    day = Battle([Unit("player")], [Unit("enemy")],
                 scenario=ErmosScenario(), daylight=True)
    assert day.ambient_light is True and not day.ground


def test_custom_scenario_builds_the_authored_map():
    random.seed(0)
    data_map = {"walls": [[8, 4], [8, 5], [8, 6]], "torches": [[3, 3], [12, 8]],
                "deploy_player": [[1, 1]], "deploy_enemy": [[14, 10]],
                "ambient_light": False, "outdoor": False}
    batt = Battle([Unit("player")], [Unit("enemy")],
                  scenario=CustomScenario(data_map))
    assert batt.board.walls == {(8, 4), (8, 5), (8, 6)}
    assert {o.pos for o in batt.ground if o.is_torch} == {(3, 3), (12, 8)}
    p, e = batt.player_units[0], batt.enemy_units[0]
    assert p.pos == (1, 1) and e.pos == (14, 10)
    assert batt.ambient_light is False


def test_custom_scenario_falls_back_to_edge_columns_for_a_blank_side():
    random.seed(0)
    batt = Battle([Unit("player")], [Unit("enemy")],
                  scenario=CustomScenario({"deploy_player": [[0, 0]]}))
    assert batt.player_units[0].pos == (0, 0)
    assert batt.enemy_units[0].pos[0] >= COLS - 3       # blank enemy side: edge columns


def test_custom_scenario_deploys_a_named_npc_on_the_npc_zone():
    random.seed(0)
    goon = Unit("enemy")
    boss = Unit("enemy")
    boss.set_name("Adelio Small-Knife")                 # a named library character
    batt = Battle([Unit("player")], [goon, boss],
                  scenario=CustomScenario({"deploy_enemy": [[14, 2]],
                                           "deploy_npc": [[8, 6, "whoever"]]}))
    named = next(c for c in batt.enemy_units if not c._auto_name)
    generic = next(c for c in batt.enemy_units if c._auto_name)
    assert named.pos == (8, 6) and generic.pos == (14, 2)


def test_custom_scenario_lit_map_scatters_no_torches():
    random.seed(0)
    batt = Battle([Unit("player")], [Unit("enemy")],
                  scenario=CustomScenario({"ambient_light": True}))
    assert batt.ambient_light is True and not batt.ground


def test_arena_torches_scatter_across_the_whole_floor():
    from gartok.scenario import ArenaScenario
    xs = set()
    for s in range(12):
        random.seed(s)
        b = Battle([Unit("player")], [Unit("enemy")], scenario=ArenaScenario())
        xs.update(o.pos[0] for o in b.ground if o.is_torch)
    assert any(x < 5 for x in xs) and any(x > 10 for x in xs)   # not just a centre band

"""The arena's second stage -- the Games: the scaled brawl, capture the flag,
the flag-seeking AI and the three second-stage deeds."""

import random
from gartok import actions, ai, arena, campaign, encounters, factions, world
from gartok.battle import COLS, Battle
from gartok.guild import Guild
from gartok.scenario import FlagScenario, own_half
from gartok.unit import Unit

def _ctf_battle(n_enemy=1):
    random.seed(0)
    b = Battle([Unit("player")], [Unit("enemy") for _ in range(n_enemy)],
               scenario=FlagScenario(), lethal=False, arena=True)
    return b

def _games_win(tier, *, kos=0, won=True):
    """Resolve a Games bout for a guild that has already dethroned the champion."""
    random.seed(1)
    guild = Guild([Unit("player")], node="arena")
    guild.deeds_done = ["arena_first_blood", "arena_lone_wolf", "arena_dethrone"]
    guild.reputation = {"arena": 3}
    squad = [Unit("player")]
    guild.groups[0].members = list(squad)
    battle = Battle(squad, [Unit("enemy")], lethal=False, arena=True)
    battle.winner = "player" if won else "enemy"
    for u in battle.player_units:
        u.status = "up"
    battle.player_units[0].kills = kos
    out = campaign.absorb_battle(guild, squad, battle, node=world.node("arena"),
                                 arena_offer=tier)
    return guild, out


def test_stage2_pack_rolls_every_fighter_level_one_to_six():
    rng = random.Random(4)
    seen = set()
    for _ in range(60):
        pack = arena.stage2_pack(3, rng)
        assert len(pack) == 3
        for u in pack:
            assert 1 <= u.mean_level <= 6
            seen.add(u.mean_level)
    assert seen == {1, 2, 3, 4, 5, 6}                      # the whole curve shows up
    assert set(encounters.ARENA_LEVEL_WEIGHTS) == {1, 2, 3, 4, 5, 6}


def test_games_bouts_carry_the_stage2_tags():
    brawl, ctf = arena.brawl_bout(), arena.ctf_bout()
    assert brawl.stage2 and not brawl.ctf
    assert ctf.stage2 and ctf.ctf
    assert brawl.entry == ctf.entry == arena.STAGE2_ENTRY
    assert brawl.purse == ctf.purse == arena.STAGE2_PURSE
    assert brawl.player_cap == ctf.player_cap == arena.STAGE2_ENEMIES


def test_the_boss_bout_is_a_six_a_side_ctf_on_the_authored_map():
    boss = arena.boss_bout()
    assert boss.stage2 and boss.ctf and boss.boss
    assert boss.map_slug == arena.BOSS_MAP
    assert boss.enemies == arena.BOSS_LACKEYS and boss.level == arena.BOSS_LACKEY_LEVEL
    assert boss.player_cap == arena.BOSS_SQUAD == 6         # brothers + lackeys, matched
    assert boss.purse == arena.BOSS_PURSE
    assert "Lackeys" in arena.bout_level_range(boss, [])


def test_flag_scenario_drops_the_enemy_flag_in_the_right_half():
    b = _ctf_battle()
    fx, fy = b.flags["enemy"]
    assert fx in own_half("enemy") and (fx, fy) not in b.board.walls
    assert b.flags["player"] is None and b.awaiting_flag and b.is_ctf


def test_the_boss_ctf_runs_on_the_authored_map_with_the_brothers_placed():
    from gartok import matchup
    from gartok.guild import Guild
    from gartok.scenario import CustomFlagScenario
    guild = Guild([Unit("player")], node="arena")
    guild.deeds_done = ["arena_dethrone"]
    enemies, scen = matchup.build(world.node("arena"), arena.boss_bout(),
                                  squad_size=6, guild=guild)
    assert isinstance(scen, CustomFlagScenario)
    b = Battle([Unit("player") for _ in range(6)], enemies, scenario=scen,
               lethal=False, arena=True)
    assert b.is_ctf and b.board.cols == 21 and b.board.rows == 17
    fx, fy = b.flags["enemy"]
    assert fx in own_half("enemy", b.board.cols) and (fx, fy) not in b.board.walls
    brothers = {u.name: u.pos for u in b.enemy_units if not u._auto_name}
    assert brothers == {"Peep": (17, 8), "Ribit": (18, 14), "Bufo": (20, 8)}


def test_stepping_on_the_enemy_flag_picks_it_up_not_an_instant_win():
    b = _ctf_battle()
    b.flags["player"] = (1, 1)
    assert b.scenario.win_check(b) is None                 # nobody on a flag yet
    b.player_units[0].pos = b.flags["enemy"]
    assert b._check_winner() is None                       # scooped up, not home yet
    assert b.flag_carrier["enemy"] is b.player_units[0]
    assert b.flag_pos("enemy") == b.flags["enemy"]          # rides along at the carrier


def test_carrying_the_enemy_flag_home_wins_it_without_a_wipe():
    b = _ctf_battle()
    b.flags["player"] = (1, 1)
    b.flag_carrier["enemy"] = b.player_units[0]             # already holding it
    b.player_units[0].pos = b.flags["player"]               # brings it home
    assert b._check_winner() == "player"
    assert b.player_units[0].survived and not b.enemy_units[0].dead   # non-lethal


def test_enemy_carrying_the_player_flag_home_wins_for_the_enemy():
    b = _ctf_battle()
    b.flags["player"] = (2, 3)
    b.enemy_units[0].pos = (2, 3)
    assert b._check_winner() is None                       # scooped up, not home yet
    assert b.flag_carrier["player"] is b.enemy_units[0]
    b.enemy_units[0].pos = b.flags["enemy"]                 # brings it home
    assert b._check_winner() == "enemy"
    assert b.player_units[0].survived                      # a lost bout kills nobody


def test_a_downed_carrier_drops_the_flag_where_they_fell():
    b = _ctf_battle()
    b.flags["player"] = (1, 1)
    carrier = b.player_units[0]
    carrier.pos = (5, 5)
    b.flag_carrier["enemy"] = carrier                       # already holding it
    carrier.take_damage(999, b.log)
    assert b.scenario.win_check(b) is None
    assert b.flag_carrier["enemy"] is None and b.flags["enemy"] == (5, 5)


def test_standing_on_your_own_flag_does_nothing():
    b = _ctf_battle()
    b.flags["player"] = (2, 2)
    b.player_units[0].pos = (2, 2)                          # own flag
    assert b._check_winner() is None


def test_each_side_s_fastest_is_its_one_flag_runner():
    b = _ctf_battle(n_enemy=3)
    b.enemy_units[0].char.speed = 3
    b.enemy_units[1].char.speed = 9
    b.enemy_units[2].char.speed = 6
    b._assign_flag_runners()                                # re-tag after tweaking speed
    assert [c for c in b.enemy_units if c.ctf_runner] == [b.enemy_units[1]]
    assert sum(c.ctf_runner for c in b.player_units) == 1   # the AI runs the player's side too


def test_fallen_flag_runner_is_replaced_by_fastest_living_survivor():
    b = _ctf_battle(n_enemy=3)
    b.enemy_units[0].char.speed = 3
    b.enemy_units[1].char.speed = 9
    b.enemy_units[2].char.speed = 6
    b._assign_flag_runners()
    runner = b.enemy_units[1]
    assert runner.ctf_runner is True
    runner.status = "dead"
    runner.hp = 0
    b._promote_fallen_runners()
    assert b.enemy_units[2].ctf_runner is True
    assert b.enemy_units[0].ctf_runner is False


def test_a_disarmed_runner_keeps_on_the_flag_instead_of_a_dropped_weapon():
    from gartok.ground import GroundObject
    b = _ctf_battle()
    b.board.walls = set()
    runner = b.enemy_units[0]
    runner.ctf_runner = True
    runner.pos, runner.ap = (COLS - 2, 5), 2
    runner.disarm()
    b.ground.append(GroundObject.weapon((COLS - 6, 8), "Axe"))
    assert not ai._recover_weapon(b, runner)
    assert runner.pos == (COLS - 2, 5)
    runner.ctf_runner = False
    assert ai._recover_weapon(b, runner)                   # a holder still goes for it


def test_a_player_side_runner_goes_for_the_enemy_flag_and_brings_it_home():
    b = _ctf_battle()
    b.board.walls = set()
    b.flags["player"] = (1, 5)
    runner = b.player_units[0]
    runner.ctf_runner = True
    runner.pos = (5, 5)
    assert ai._ctf_goal(b, runner) == b.flags["enemy"]
    b.flag_carrier["enemy"] = runner
    assert ai._ctf_goal(b, runner) == (1, 5)


def test_a_runner_closes_on_the_player_flag():
    b = _ctf_battle()
    b.board.walls = set()
    b.flags["player"] = (1, 5)
    runner = b.enemy_units[0]
    runner.ctf_runner = True
    runner.pos = (COLS - 1, 5)
    b.player_units[0].pos = (8, 0)                          # out of the way
    before = abs(runner.pos[0] - 1)
    b.order = [runner]                                      # make it the active unit
    b.turn_idx = 0
    ai.take_turn(b, runner)
    assert abs(runner.pos[0] - 1) < before                  # moved toward the flag


def test_a_runner_scoops_up_the_flag_over_a_downed_body_on_it():
    random.seed(0)
    # a second, untouched player unit keeps the fight from ending by plain
    # elimination once `body` goes down -- this test is about the flag alone.
    b = Battle([Unit("player"), Unit("player")], [Unit("enemy")],
              scenario=FlagScenario(), lethal=False, arena=True)
    b.board.walls = set()
    b.flags["player"] = (2, 5)
    runner = b.enemy_units[0]
    runner.ctf_runner = True
    runner.pos = (6, 5)
    runner.char.speed = 3
    body, safe = b.player_units                             # a KO'd fighter lying on the flag
    body.pos = (2, 5)
    body.take_damage(999, b.log)
    safe.pos = (0, 0)
    assert not body.alive and (2, 5) not in b.occupied()   # a body does not hold the cell
    b.order = [runner]
    b.turn_idx = 0
    for _ in range(6):
        if b.flag_carrier["player"] is runner:
            break
        ai.take_turn(b, runner)
    assert b.flag_carrier["player"] is runner               # walked onto the flag over the body
    assert b.winner is None                                 # picked up, not home yet


def test_a_runner_carrying_the_flag_heads_home_next():
    b = _ctf_battle()
    b.board.walls = set()
    b.flags["player"] = (1, 1)
    runner = b.enemy_units[0]
    runner.ctf_runner = True
    runner.pos = (1, 5)
    b.flag_carrier["player"] = runner                        # already holding it
    home_x = b.flags["enemy"][0]
    before = abs(runner.pos[0] - home_x)
    b.order = [runner]
    b.turn_idx = 0
    ai.take_turn(b, runner)
    assert abs(runner.pos[0] - home_x) < before


def test_a_non_runner_ignores_the_flag():
    b = _ctf_battle()
    b.board.walls = set()
    b.flags["player"] = (1, 5)
    plain = b.enemy_units[0]
    plain.ctf_runner = False                                # a holder, not a runner
    plain.pos = (10, 5)
    b.player_units[0].pos = (14, 5)                         # a target the opposite way from the flag
    b.order = [plain]
    b.turn_idx = 0
    ai.take_turn(b, plain)
    assert plain.pos[0] >= 10                               # never chased the far-left flag


def test_a_defender_chases_whoever_is_carrying_the_enemys_flag():
    """A non-runner would normally go for the nearest/weakest foe -- but once
    someone is running off with its own side's flag, stopping them takes
    priority over any other fight, even one that is closer or an easier kill."""
    random.seed(0)
    b = Battle([Unit("player"), Unit("player")], [Unit("enemy")],
              scenario=FlagScenario(), lethal=False, arena=True)
    b.board.walls = set()
    d = b.enemy_units[0]
    d.ctf_runner = False
    d.pos = (10, 5)
    near_weak, carrier = b.player_units
    near_weak.pos, carrier.pos = (11, 5), (15, 5)           # near_weak is closer *and* weaker
    near_weak.hp, carrier.hp = 1, near_weak.hp_max
    b.flag_carrier["enemy"] = carrier                        # carrying OUR flag away
    assert ai._target(b, d) is carrier


def test_a_brawl_win_banks_bloodsport_only():
    guild, out = _games_win(arena.brawl_bout())
    assert {d.id for d in out.deeds_earned} == {"arena_bloodsport"}
    assert guild.reputation["arena"] == 4


def test_a_clean_flag_capture_banks_all_three():
    guild, out = _games_win(arena.ctf_bout(), kos=0)
    assert {d.id for d in out.deeds_earned} == {
        "arena_bloodsport", "arena_flag_runner", "arena_untouchable"}
    assert guild.reputation["arena"] == 6


def test_a_flag_capture_with_a_knockout_misses_untouchable():
    guild, out = _games_win(arena.ctf_bout(), kos=1)
    assert {d.id for d in out.deeds_earned} == {"arena_bloodsport", "arena_flag_runner"}
    assert "arena_untouchable" not in guild.deeds_done


def test_beating_the_ribbit_brothers_banks_their_deed():
    guild, out = _games_win(arena.boss_bout(), kos=0)
    earned = {d.id for d in out.deeds_earned}
    assert "arena_ribbit_brothers" in earned                # the capstone deed
    assert earned == {"arena_bloodsport", "arena_flag_runner",
                      "arena_untouchable", "arena_ribbit_brothers"}


def test_games_deeds_are_locked_until_the_champion_is_beaten():
    open_ids = {d.id for d in factions.open_deeds(Guild([Unit("player")]))}
    assert "arena_bloodsport" not in open_ids               # requires arena_dethrone
    assert "arena_flag_runner" not in open_ids


def test_a_lost_games_bout_banks_nothing():
    guild, out = _games_win(arena.ctf_bout(), won=False)
    assert out.deeds_earned == [] and guild.reputation["arena"] == 3


def test_bout_max_combat_level():
    assert arena.bout_max_combat_level(arena.scrapper_bout()) == 0
    assert arena.bout_max_combat_level(arena.champion_bout()) == 1
    assert arena.bout_max_combat_level(arena.boss_bout()) == 6
    assert arena.bout_max_combat_level(arena.brawl_bout()) == 7
    assert arena.bout_max_combat_level(arena.ctf_bout()) == 7
    assert arena.bout_max_combat_level(world.Bout("Custom", entry=0, purse=0, enemies=2, level=2)) == 4
    assert arena.bout_max_combat_level(None) == 0


def test_the_champion_title_demoralizes_in_a_ctf_bout_without_a_shared_language():
    from unittest.mock import patch
    b = _ctf_battle()
    b.ambient_light = True
    champ, foe = b.player_units[0], b.enemy_units[0]
    champ.char.arena_title = True
    champ.char.languages = ["Common"]
    foe.char.languages = ["Orc"]
    champ.pos, foe.pos = (5, 5), (6, 5)
    champ.ap = 2
    assert actions.DEMORALIZE.can(b, champ, foe)
    with patch("gartok.actions.combat.d20", return_value=20):
        actions.DEMORALIZE.execute(b, champ, foe)
    assert foe.demoralized


def test_a_defender_holds_position_on_own_flag_square():
    b = _ctf_battle()
    b.board.walls = set()
    b.flags["player"] = (2, 5)
    b.flags["enemy"] = (12, 5)
    d = b.enemy_units[0]
    d.ctf_runner = False
    d.pos = (14, 5)
    b.player_units[0].pos = (2, 8)
    b.order = [d]
    b.turn_idx = 0

    # Turn 1: defender moves directly onto (12, 5)
    ai.take_turn(b, d)
    assert d.pos == (12, 5)

    # Turn 2: defender holds on (12, 5) without moving away towards player
    d.ap = 2
    d.walking = False
    ai.take_turn(b, d)
    assert d.pos == (12, 5)

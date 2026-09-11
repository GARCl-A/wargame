"""The arena's second stage -- the Games: the scaled brawl, capture the flag,
the flag-seeking AI and the three second-stage deeds."""

import random

from gartok import ai, arena, campaign, encounters, factions, world
from gartok.battle import COLS, Battle
from gartok.guild import Guild
from gartok.scenario import FlagScenario, own_half
from gartok.unit import Unit


# --------------------------------------------------------------------------- #
# scaled opponents                                                             #
# --------------------------------------------------------------------------- #
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
    assert boss.enemies == arena.BOSS_GOONS and boss.level == arena.BOSS_GOON_LEVEL
    assert boss.player_cap == arena.BOSS_SQUAD == 6         # brothers + goons, matched
    assert boss.purse == arena.BOSS_PURSE


# --------------------------------------------------------------------------- #
# the capture-the-flag scenario                                                #
# --------------------------------------------------------------------------- #
def _ctf_battle(n_enemy=1):
    random.seed(0)
    b = Battle([Unit("player")], [Unit("enemy") for _ in range(n_enemy)],
               scenario=FlagScenario(), lethal=False, arena=True)
    return b


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


# --------------------------------------------------------------------------- #
# the flag-seeking AI                                                          #
# --------------------------------------------------------------------------- #
def test_fastest_enemies_are_tagged_as_flag_runners():
    b = _ctf_battle(n_enemy=3)
    b.enemy_units[0].char.speed = 3
    b.enemy_units[1].char.speed = 9
    b.enemy_units[2].char.speed = 6
    b._assign_flag_runners()                                # re-tag after tweaking speed
    runners = [c for c in b.enemy_units if c.ctf_runner]
    assert len(runners) == 2                                # ceil(half) of a 3v3
    assert b.enemy_units[1] in runners and b.enemy_units[0] not in runners  # the slow one holds


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


def test_the_enemy_flag_stays_hidden_until_you_can_see_its_cell():
    from gartok.battle_screen import BattleScreen
    b = _ctf_battle(n_enemy=1)
    b.flags["player"] = (2, 2)
    scr = BattleScreen(None, b, on_battle_end=lambda *a: None)

    drawn = []
    scr._draw_pennant = lambda screen, pos, color: drawn.append(pos)

    scr._visible = {b.flags["player"]}                      # own flag in sight, enemy's not
    scr._draw_flags(None)
    assert drawn == [b.flags["player"]]                     # enemy flag withheld

    drawn.clear()
    scr._visible = {b.flags["player"], b.flags["enemy"]}    # now its cell is lit
    scr._draw_flags(None)
    assert set(drawn) == {b.flags["player"], b.flags["enemy"]}


# --------------------------------------------------------------------------- #
# the three second-stage deeds                                                 #
# --------------------------------------------------------------------------- #
def _games_win(tier, *, kos=0, won=True):
    """Resolve a Games bout for a guild that has already dethroned the champion."""
    random.seed(1)
    guild = Guild([Unit("player")], node="arena")
    guild.deeds_done = ["arena_first_blood", "arena_lone_wolf", "arena_dethrone"]
    guild.reputation = {"arena": 3}
    squad = [Unit("player")]
    guild.roster = list(squad)
    battle = Battle(squad, [Unit("enemy")], lethal=False, arena=True)
    battle.winner = "player" if won else "enemy"
    for u in battle.player_units:
        u.status = "up"
    battle.player_units[0].kills = kos
    out = campaign.absorb_battle(guild, squad, battle, node=world.node("arena"),
                                 arena_offer=tier)
    return guild, out


def test_a_brawl_win_banks_bloodsport_only():
    guild, out = _games_win(arena.brawl_bout())
    assert {d.id for d in out.deeds_earned} == {"arena_bloodsport"}
    assert guild.reputation["arena"] == 4


def test_a_clean_flag_capture_banks_all_three():
    guild, out = _games_win(arena.ctf_bout(), kos=0)
    assert {d.id for d in out.deeds_earned} == {
        "arena_bloodsport", "arena_flag_runner", "arena_untouchable"}
    assert guild.reputation["arena"] == 6                   # opens the Iron cage (rep 5)
    assert len(world.arena_offers(guild.reputation["arena"])) == 3


def test_a_flag_capture_with_a_knockout_misses_untouchable():
    guild, out = _games_win(arena.ctf_bout(), kos=1)
    assert {d.id for d in out.deeds_earned} == {"arena_bloodsport", "arena_flag_runner"}
    assert "arena_untouchable" not in guild.deeds_done


def test_arena_squad_cap_follows_the_selected_bout():
    from gartok.squad_screen import SquadScreen
    roster = [Unit("player") for _ in range(6)]
    scr = SquadScreen(None, roster, world.node("arena"), on_confirm=lambda *a: None,
                      on_back=lambda: None,
                      arena_offers=[arena.brawl_bout(), arena.boss_bout()])
    assert scr.max_pick == 3                              # brawl: 3 opponents, squad of 3
    for u in roster:
        scr._toggle(u)
    assert len(scr.picked) == 3                           # capped at the tier

    scr.offer_idx = 1                                     # the boss bout: 6 a side
    assert scr.max_pick == 6
    for u in roster:
        if u not in scr.picked:
            scr._toggle(u)
    assert len(scr.picked) == 6


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


# --------------------------------------------------------------------------- #
# the arena node offers the Games once the champion is down                     #
# --------------------------------------------------------------------------- #
def test_arena_node_swaps_the_champion_bout_for_the_games_after_dethroning():
    from gartok.app import App

    app = App.__new__(App)
    app.fonts = None
    app.guild = Guild([Unit("player")], node="arena")
    app.guild.reputation = {"arena": 3}

    captured = {}
    def fake_screen(fonts, roster, node, **kw):
        captured["offers"] = kw["arena_offers"]
        return object()
    import gartok.app as app_mod
    orig = app_mod.SquadScreen
    app_mod.SquadScreen = fake_screen
    try:
        group = app.guild.groups[0]
        app.guild.deeds_done = []
        app._open_arena(group, world.node("arena"))
        assert any(o.champion for o in captured["offers"])
        assert not any(o.stage2 for o in captured["offers"])

        app.guild.deeds_done = ["arena_dethrone"]
        app._open_arena(group, world.node("arena"))
        assert not any(o.champion for o in captured["offers"])
        names = {o.name for o in captured["offers"] if o.stage2}
        assert names == {"Games: Brawl", "Games: Capture the Flag",
                         "Games: The Ribbit Brothers"}
    finally:
        app_mod.SquadScreen = orig

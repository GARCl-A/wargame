"""GARTOK Tactical rules tests (no external dependency: `python test_gartok.py`).

They cover the pieces that break most often when the system is touched: typed
bonuses, conditions, abilities, board/vision and the actions. They do not test the UI.
"""

import os
import random

from gartok import abilities, actions, data, economy, persist, recruit
from gartok.board import COLS, ROWS, Board
from gartok.battle import Battle
from gartok.scenario import ErmosScenario
from gartok.conditions import Defending, Demoralized
from gartok.data import SIZES, resolve_bonus, squares
from gartok.ground import GroundObject
from gartok.unit import Unit
from gartok.combatant import Combatant


def _unit(**over):
    """A deterministic Unit for tests: seeded roll with overridden fields."""
    random.seed(over.pop("seed", 0))
    u = Unit(over.pop("team", "player"))
    for k, v in over.items():
        setattr(u, k, v)
    return u


def _combatant(**over):
    """A Combatant wrapping a deterministic Unit -- for battle-behaviour tests."""
    return Combatant(_unit(**over))


def _recruit(batt, team="player"):
    """Drop a fresh combatant into an already-built battle (not in the initiative
    order -- tests that use it drive turns by hand)."""
    c = Combatant(Unit(team), team)
    batt.units.append(c)
    (batt.player_units if team == "player" else batt.enemy_units).append(c)
    return c


# --------------------------------------------------------------------------- #
# resolve_bonus                                                                #
# --------------------------------------------------------------------------- #

def test_typed_bonus_does_not_stack():
    total, _ = resolve_bonus([(2, "circumstance", "A"), (4, "circumstance", "B")])
    assert total == 4, total


def test_untyped_bonus_stacks():
    total, _ = resolve_bonus([(2, None, "A"), (3, None, "B")])
    assert total == 5, total


def test_penalties_always_stack():
    total, _ = resolve_bonus([(-1, "status", "A"), (-1, "status", "B"), (2, "circumstance", "C")])
    assert total == 0, total


# --------------------------------------------------------------------------- #
# conditions                                                                   #
# --------------------------------------------------------------------------- #

def test_defend_gives_1_ac_and_expires_next_turn():
    u = _combatant()
    base = u.ac
    u.add_condition(Defending())
    assert u.ac == base + 1
    u.start_turn(lambda _: None)
    assert u.ac == base and not u.defending


def test_demoralized_penalizes_and_expires_at_turn_end():
    u = _combatant()
    ac, md = u.ac, u.mental_defense
    u.add_condition(Demoralized())
    assert u.ac == ac - 1 and u.mental_defense == md - 1
    u.end_turn(lambda _: None)
    assert not u.demoralized


def test_condition_does_not_duplicate():
    u = _combatant()
    u.add_condition(Demoralized())
    u.add_condition(Demoralized())
    assert len(u.conditions) == 1


# --------------------------------------------------------------------------- #
# abilities                                                                    #
# --------------------------------------------------------------------------- #

def test_passive_ability_adds_in_derivation():
    u = _unit()
    u._ability = abilities.get("none")
    u._derive_combat()
    hp0, spd0, dr0 = u.hp_max, u.speed, u.dr
    random.seed(0)                                    # same HP roll
    u2 = _unit()
    u2._ability = abilities.get("strong_stomach")
    u2._derive_combat()
    assert u2.hp_max == hp0 + 3
    u2._ability = abilities.get("gallop")
    u2._derive_combat()
    assert u2.speed == spd0 + 2
    u2._ability = abilities.get("inorganic_body")
    u2._derive_combat()
    assert u2.dr == dr0 + 1


def test_large_centaur_moves_12m_from_gallop_not_size():
    # a Large creature moves like a Medium by default (9 m); the Centaur only
    # exceeds that because of Gallop (+3 m) -> 12 m = 8 squares.
    assert SIZES["Large"]["speed"] == SIZES["Medium"]["speed"] == 9.0
    u = _unit(size="Large")
    u._ability = abilities.get("none")
    u._derive_combat()
    assert u.speed == squares(9.0) == 6
    u._ability = abilities.get("gallop")
    u._derive_combat()
    assert u.speed == 8


def test_large_creature_takes_2x2_blocks_and_touches():
    random.seed(2)
    batt = Battle([Unit("player")], [Unit("enemy")])
    batt.board.walls = set()
    big, foe = batt.units
    big.footprint, big.pos = 2, (4, 4)
    foe.footprint, foe.pos = 1, (6, 5)                  # right against the footprint edge
    for u in (big, foe):                                # unarmed -> pure melee
        u.weapon_hand = u.torch_hand = False

    assert set(batt.cells_of(big)) == {(4, 4), (5, 4), (4, 5), (5, 5)}
    assert batt.unit_at((5, 5)) is big and batt.unit_at((4, 4)) is big
    assert batt.units_distance(big, foe) == 1           # melee
    assert actions.ATTACK.can(batt, big, foe)           # reaches without needing to see

    reach = batt.reachable(big)
    assert (5, 5) not in reach                          # anchor whose footprint would step on the foe
    assert (2, 4) in reach                              # free space to the left


def test_ferocity_falls_at_end_of_turn_then_clock_runs():
    base = _unit()
    base.ability_id = "ferocity"
    base._ability = abilities.get("ferocity")
    u = Combatant(base)
    u.hp = 3
    u.take_damage(99, lambda _: None)
    assert u.alive and u.hp == 0 and u.ferocity_pending      # 0 PV but still standing
    assert u.death_clock == 0
    u.end_turn(lambda _: None)
    assert u.dying and not u.ferocity_pending and u.death_clock == 0
    # once per battle: a second fatal hit drops it straight into dying
    u.status, u.hp, u.death_clock = "up", 3, 0
    u.take_damage(99, lambda _: None)
    assert u.dying and not u.ferocity_pending


def test_goliath_carries_as_a_large_creature():
    small = _unit(size="Medium")
    small._ability = abilities.get("none")
    small._derive_combat()
    goliath = _unit(size="Medium")
    goliath._ability = abilities.get("strong_body")
    goliath._derive_combat()
    assert goliath.carry_normal == small.carry_normal * 2      # Large carry multiplier
    assert goliath.carry_max == small.carry_max * 2
    assert goliath.footprint == 1 and goliath.speed == small.speed   # only carry changes


def test_automaton_breaks_instead_of_dying():
    batt, a, d = _melee_battle()
    d._ability = abilities.get("inorganic_body")
    d.take_damage(999, batt.log)
    assert d.broken and d.downed and not d.dying and not d.alive
    assert d.survived and d.death_clock == 0
    batt._resolve_dangling_dying()                            # no death save ever runs
    assert d.broken


def test_ally_repairs_broken_automaton_with_intelligence():
    batt, a, d = _melee_battle()
    a._ability = abilities.get("inorganic_body")
    a.go_down(batt.log); a.pos = (5, 5)
    assert a.broken
    b = _recruit(batt)
    b.char.intelligence = 30; b.char._derive_combat()
    b.pos = (5, 6)
    for _ in range(50):                                       # keep trying (infinite time)
        if a.alive:
            break
        b.ap = 2
        actions.STABILIZE.execute(batt, b, a)
    assert a.alive and a.hp == 1


# --------------------------------------------------------------------------- #
# board and vision                                                             #
# --------------------------------------------------------------------------- #

def test_los_blocked_by_wall():
    b = Board()
    b.walls = {(5, 5)}
    assert b.los_clear((4, 5), (6, 5)) is False
    assert b.los_clear((4, 4), (4, 8)) is True


def test_two_walls_at_corner_block_diagonal_and_sight():
    b = Board()
    b.walls = {(4, 4), (5, 5)}
    reach = b.reachable((4, 5), 1)
    assert (5, 4) not in reach
    assert b.los_clear((4, 5), (5, 4)) is False
    assert b.los_clear((4, 5), (7, 2)) is False


def test_single_wall_at_corner_does_not_block_diagonal():
    b = Board()
    b.walls = {(5, 5)}
    reach = b.reachable((4, 5), 1)
    assert (5, 4) in reach
    assert b.los_clear((4, 5), (5, 4)) is True


def test_ally_lets_pass_but_not_stop_enemy_blocks():
    random.seed(0)
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")])
    # wall on column 6 with a single door at (6,5): only way through
    batt.board.walls = {(6, y) for y in range(12) if y != 5}
    a, ally, foe = batt.units
    for u in batt.units:
        u.footprint = 1
    a.pos, a.ap, a.walking = (5, 5), 2, False
    ally.pos, foe.pos = (6, 5), (12, 9)
    reach = batt.reachable(a)
    assert (6, 5) not in reach                 # does not end on top of the ally
    assert (7, 5) in reach                     # but crosses through to the other side

    ally.pos, foe.pos = (12, 9), (6, 5)        # enemy in the chokepoint
    reach = batt.reachable(a)
    assert (6, 5) not in reach and (7, 5) not in reach   # enemy blocks completely


def test_path_to_returns_full_route():
    b = Board()
    b.walls = set()
    path = b.path_to((2, 2), (5, 2))
    assert path[0] == (2, 2) and path[-1] == (5, 2)
    assert len(path) == 4                              # 3 steps, cost 1 each
    assert b.path_to((0, 0), (0, 0)) == [(0, 0)]


def test_move_records_walked_path():
    random.seed(0)
    batt = Battle([Unit("player")], [Unit("enemy")])
    batt.board.walls = set()
    u = batt.units[0]
    u.pos, u.ap, u.walking = (3, 3), 2, False
    u.path = [u.pos]
    batt.move_unit(u, (5, 3))
    assert u.path[0] == (3, 3) and u.path[-1] == (5, 3)
    batt.move_unit(u, (5, 5))                          # second step, same turn
    assert u.path[0] == (3, 3) and u.path[-1] == (5, 5)


def test_reachable_respects_budget():
    b = Board()
    b.walls = set()
    reach = b.reachable((8, 6), 2)
    assert all(v <= 2 for v in reach.values())
    assert (10, 6) in reach and (11, 6) not in reach


def test_dark_map_only_sees_own_cell():
    random.seed(1)
    batt = Battle([Unit("player")], [Unit("enemy")])
    batt.ground = []                                  # no torches on the ground
    for u in batt.units:                              # no light source, no darkvision
        u.weapon_hand = u.torch_hand = False
        u.inventory, u._ability = ["Sack"], abilities.get("none")
    p, e = batt.units
    p.pos, e.pos = (2, 2), (12, 9)
    assert batt.can_see(p, p.pos) is True
    assert batt.can_see(p, (5, 2)) is False


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


def test_arena_offers_scale_with_reputation():
    from gartok import world
    assert [o["name"] for o in world.arena_offers(0)] == ["Rookie pit"]
    assert len(world.arena_offers(2)) == 2
    assert len(world.arena_offers(99)) == len(world.ARENA_TIERS)
    # ordered cheapest first; one fighter's entry always below the purse
    for tier in world.ARENA_TIERS:
        assert tier["entry"] < tier["purse"]


def test_arena_entry_is_staked_per_fighter():
    from gartok.app import App
    from gartok.squad_screen import SquadScreen
    from gartok import world

    roster = [Unit("player") for _ in range(3)]
    for u in roster:
        u.gold = 10
    scr = SquadScreen(None, roster, world.node("arena"), on_confirm=lambda *a: None,
                      on_back=lambda: None, arena_offers=world.arena_offers(0))
    assert scr.picked == roster                       # roster fits, all auto-picked
    assert scr.entry_cost == world.ARENA_TIERS[0]["entry"] * 3
    assert scr.ok and scr.picked_gold >= scr.entry_cost

    scr.picked = roster[:1]                           # solo pays a third
    assert scr.entry_cost == world.ARENA_TIERS[0]["entry"]

    # the app bills that whole stake off the squad, richest first
    App._charge(roster, world.ARENA_TIERS[0]["entry"] * 3)
    assert sum(u.gold for u in roster) == 30 - world.ARENA_TIERS[0]["entry"] * 3


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


def test_lethal_flag_defaults_true_and_permadeath_still_bites():
    batt, a, d = _melee_battle()
    assert batt.lethal and not a.nonlethal
    d.take_damage(999, batt.log)
    assert d.dying                                    # not knocked out -- dying


def test_market_sell_is_a_loss_and_checkout_splits_the_purse():
    from gartok.market_screen import MarketScreen
    assert economy.sell_price("Axe") < economy.buy_price("Axe")
    random.seed(1)
    shoppers = [Unit("player") for _ in range(3)]
    for m in shoppers:
        m.gold = 10
    ms = MarketScreen.__new__(MarketScreen)           # no draw in this test
    ms.shoppers = shoppers
    ms.purse = sum(m.gold for m in shoppers)          # 30
    ms.on_done = lambda: None
    ms._checkout()
    assert sorted(m.gold for m in shoppers) == [10, 10, 10] and sum(m.gold for m in shoppers) == 30
    ms.purse = 31
    ms._checkout()
    assert sorted(m.gold for m in shoppers) == [10, 10, 11]


def test_dragselect_ignores_a_mouseup_with_no_matching_press():
    """Entering the market via the squad picker's GO SHOPPING button leaves the
    left button down; the release then lands on the scene that just replaced it.
    That stray MOUSEBUTTONUP must not count as a click (which would fire
    LEAVE THE MARKET and bounce the player straight back out)."""
    import pygame
    from gartok.dragselect import DragSelectMixin
    from gartok.screen import Screen

    class Probe(DragSelectMixin, Screen):
        def __init__(self):
            super().__init__()
            self.drops = 0

        def _source_at(self, px):
            return None

        def _drop(self, px, dragging, src):
            self.drops += 1

    p = Probe()
    up = pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (10, 10)})
    p.handle_event(up)
    assert p.drops == 0                               # stray release: no-op

    down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (5, 5)})
    p.handle_event(down)
    p.handle_event(up)
    assert p.drops == 1                               # a real press/release still lands


def test_every_race_has_a_token_icon_that_loads():
    """`theme.token_badge` draws `artwork.RACE_ICON[race]` -> a file under
    assets/icons/head/. A missing mapping or a typo'd filename silently blanks
    the token, so pin both here."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import artwork
    pygame.init()
    pygame.display.set_mode((1, 1))
    artwork.icon.cache_clear()

    for name in data.RACE_NAMES:
        assert name in artwork.RACE_ICON, f"race {name!r} has no token icon"
        surf = artwork.race_icon(name, 24, (15, 15, 20))
        assert surf is not None and surf.get_size() == (24, 24), name

    assert artwork.race_icon("Goblin", 24) is artwork.race_icon("Goblin", 24)  # cached
    assert artwork.icon("head", "no-such-glyph", 24) is None                   # graceful


def test_every_screen_draws_native_at_any_window_size():
    """Every screen is `native`: it draws straight to the real window and lays
    itself out from `screen.get_size()`. Render each at a few sizes -- catches a
    stray fixed constant, an out-of-scope `screen`, or a layout that divides by
    something that goes to zero on a small window."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import world
    from gartok.guild import Guild
    from gartok.battle import Battle
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    F = Fonts()

    random.seed(0)
    roster = [Unit("player") for _ in range(5)]
    guild = Guild(list(roster), node=world.START_NODE)
    noop = lambda *a, **k: None
    bnode = next(n for n in world.NODES if n.kind == "battle")
    mnode = next(n for n in world.NODES if n.kind == "market")
    tnode = next(n for n in world.NODES if n.kind == "tavern")
    batt = Battle(list(roster[:3]), [Unit("enemy") for _ in range(3)],
                  scenario=bnode.scenario(), daylight=True, lethal=True)

    from gartok.menu_screen import MenuScreen
    from gartok.draft_screen import DraftScreen
    from gartok.map_screen import MapScreen
    from gartok.squad_screen import SquadScreen
    from gartok.battle_screen import BattleScreen
    from gartok.loot_screen import LootScreen
    from gartok.reward_screen import RewardScreen
    from gartok.market_screen import MarketScreen
    from gartok.taverna_screen import TavernaScreen
    from gartok.work_screen import WorkScreen
    from gartok.guild_screen import GuildScreen
    from gartok.level_screen import LevelScreen
    from gartok.pause_screen import PauseScreen

    scenes = [
        MenuScreen(F, noop, noop, noop),
        DraftScreen(F, noop),
        MapScreen(F, guild, noop, noop, noop, noop, noop, noop),
        SquadScreen(F, roster, bnode, noop, noop),
        BattleScreen(F, batt, noop),
        LootScreen(F, guild, list(roster[:3]), ["Axe", "Rope"], noop),
        RewardScreen(F, guild, list(roster[:3]), 120, noop),
        MarketScreen(F, guild, list(roster[:3]), mnode, noop),
        TavernaScreen(F, guild, list(roster[:3]), tnode, noop),
        WorkScreen(F, guild, list(roster[:3]), noop, noop),
        GuildScreen(F, guild, noop, noop),
        LevelScreen(F, roster[0], noop, noop),
    ]
    scenes.append(PauseScreen(F, scenes[2], noop, noop, noop))

    for scene in scenes:
        assert getattr(scene, "native", False), type(scene).__name__
        for size in ((1280, 800), (1920, 1080), (1024, 640)):
            surf = pygame.Surface(size)
            scene.mouse = (size[0] // 2, size[1] // 2)
            scene.draw(surf)


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


# --------------------------------------------------------------------------- #
# actions                                                                      #
# --------------------------------------------------------------------------- #

def _melee_battle():
    random.seed(3)
    batt = Battle([Unit("player")], [Unit("enemy")])
    a, d = batt.units
    a.pos, d.pos = (5, 5), (6, 5)
    a.weapon_hand, a.torch_hand = True, False
    return batt, a, d


def test_attack_spends_point():
    batt, a, d = _melee_battle()
    a.ap = 2
    actions.ATTACK.execute(batt, a, d)
    assert a.ap == 1


def test_defend_adds_condition():
    batt, a, _ = _melee_battle()
    a.ap = 2
    actions.DEFEND.execute(batt, a)
    assert a.defending and a.ap == 1


def test_throw_disarms_and_drops_object():
    batt, a, d = _melee_battle()
    a.equip_weapon("Dagger")
    a.pos, d.pos = (5, 5), (8, 5)
    a.ap = 2
    n_obj = len(batt.ground)
    assert actions.THROW.can(batt, a, d)
    actions.THROW.execute(batt, a, d)
    assert a.unarmed and len(batt.ground) == n_obj + 1


def test_pickup_recovers_weapon_from_ground():
    batt, a, d = _melee_battle()
    a.disarm()
    batt.ground.append(GroundObject.weapon(a.pos, "Axe"))
    a.ap = 2
    assert actions.PICK_UP.available(batt, a)
    actions.PICK_UP.execute(batt, a)
    assert not a.unarmed and a.weapon_name == "Axe"


def test_demoralize_requires_shared_language():
    batt, a, d = _melee_battle()
    a.languages, d.languages = ["Elvish"], ["Orcish"]
    a._ability = abilities.get("none")
    a.ap = 2
    assert actions.DEMORALIZE.can(batt, a, d) is False
    d.languages = ["Elvish"]
    # can() still depends on mutual sight; force bright light with adjacency + torch
    a.torch_hand = True
    assert actions.DEMORALIZE.can(batt, a, d) is True


# --------------------------------------------------------------------------- #
# hands / inventory / carry                                                    #
# --------------------------------------------------------------------------- #

def test_crossbow_takes_two_hands():
    u = _combatant()
    u.equip_weapon("Light Crossbow")
    assert u.weapon["hands"] == 2 and u.free_hands == 0
    dropped = u.equip_torch()                         # only fits by dropping the crossbow
    assert dropped == [("weapon", "Light Crossbow")] and u.has_torch and u.unarmed


def test_one_handed_weapon_and_torch_coexist():
    u = _combatant()
    u.equip_weapon("Dagger")
    dropped = u.equip_torch()
    assert dropped == [] and not u.unarmed and u.has_torch and u.free_hands == 0


def test_stowed_weapon_weighs_the_same_as_wielded():
    from gartok.data import WEAPONS, item_weight
    assert item_weight("Axe") == WEAPONS["Axe"]["weight"]
    u = _unit()
    u.equipped_weapon = None
    u._base_inventory = ["Axe"]
    assert Combatant(u).load == round(WEAPONS["Axe"]["weight"], 1)


def test_load_sums_weapon_torch_and_items():
    from gartok.data import WEAPONS, TORCH_WEIGHT, item_weight
    u = _combatant()
    u.equip_weapon("Axe")
    u.torch_hand = True
    u.inventory = ["Rope", "Map"]
    expected = round(WEAPONS["Axe"]["weight"] + TORCH_WEIGHT
                     + item_weight("Rope") + item_weight("Map"), 1)
    assert u.load == expected


def test_pickup_torch_with_free_hand_does_not_drop_weapon():
    batt, a, d = _melee_battle()
    a.equip_weapon("Dagger")                           # one-handed weapon
    batt.ground.append(GroundObject.torch(a.pos))
    a.ap = 2
    n_obj = len(batt.ground)
    actions.PICK_UP.execute(batt, a)
    assert a.has_torch and not a.unarmed and len(batt.ground) == n_obj - 1


def test_shepherd_spawns_neutral_sheep_that_blocks():
    random.seed(0)
    shepherd = _unit()
    shepherd.set_occupation("Shepherd")
    assert shepherd.starting_creature == "Sheep" and shepherd._base_inventory == []
    batt = Battle([shepherd], [Unit("enemy")])
    assert len(batt.creatures) == 1 and batt.creatures[0] not in batt.units

    batt.board.walls = set()
    batt.creatures[0].pos = (8, 6)                    # pin the sheep for the test
    p = batt.units[0]
    p.pos, p.ap, p.walking = (7, 6), 2, False
    assert (8, 6) not in batt.reachable(p)            # the sheep's cell blocks
    assert (9, 6) in batt.reachable(p)                # but you can go around


# --------------------------------------------------------------------------- #
# falling, stabilizing and death                                               #
# --------------------------------------------------------------------------- #

def test_downed_enters_dying_not_dead():
    batt, a, d = _melee_battle()
    d.take_damage(999, batt.log)
    assert d.dying and not d.dead and not d.alive and d.downed
    assert d.hp == 0 and d.death_clock == 0


def test_death_save_survives_on_third_turn():
    batt, a, d = _melee_battle()
    d.go_down(batt.log)
    random.seed(0)                                    # first d20 = 13 -> survives
    batt._resolve_dying_turn(d); assert d.dying and d.death_clock == 1
    batt._resolve_dying_turn(d); assert d.dying and d.death_clock == 2
    batt._resolve_dying_turn(d); assert d.stable and d.survived


def test_death_save_can_kill():
    batt, a, d = _melee_battle()
    d.go_down(batt.log)
    random.seed(1)                                    # first d20 = 5 -> dies
    for _ in range(3):
        batt._resolve_dying_turn(d)
    assert d.dead and not d.survived


def test_ally_stabilize_success_and_failure():
    batt, a, d = _melee_battle()
    b = _recruit(batt)
    b.pos = (5, 6)
    a.go_down(batt.log); a.pos = (5, 5)
    b.ap = 2
    random.seed(1)                                    # d20 = 5 -> fail
    actions.STABILIZE.execute(batt, b, a)
    assert a.dying and b.ap == 1
    b.ap = 2
    random.seed(0)                                    # d20 = 13 -> success
    actions.STABILIZE.execute(batt, b, a)
    assert a.stable and b.ap == 1


def test_first_aid_consumes_charge_either_way():
    batt, a, d = _melee_battle()
    medic = _recruit(batt)
    medic.pos = (5, 6)
    medic.first_aid_charges = 10
    a.go_down(batt.log); a.pos = (5, 5)
    medic.ap = 2
    random.seed(1)                                    # low roll -> likely fail
    actions.FIRST_AID.execute(batt, medic, a)
    assert medic.first_aid_charges == 9 and medic.ap == 1
    assert not actions.FIRST_AID.available(batt, medic) or medic.first_aid_charges == 9


def test_medic_carries_first_aid_kit():
    u = _unit()
    u.set_occupation("Physician")
    c = Combatant(u)
    assert data.FIRST_AID_ITEM in c.inventory
    assert c.first_aid_charges == data.FIRST_AID_CHARGES


def test_finish_off_dying_enemy_kills():
    batt, a, d = _melee_battle()
    d.go_down(batt.log)
    a.ap = 2
    random.seed(2)                                    # any non-fumble hit finishes it
    for _ in range(20):
        if not d.dying:
            break
        a.ap = 2
        actions.ATTACK.execute(batt, a, d)
    assert d.dead


def test_hitting_stable_reverts_to_dying():
    batt, a, d = _melee_battle()
    d.status, d.hp = "stable", 0
    a.ap = 2
    for _ in range(20):
        a.ap = 2
        actions.ATTACK.execute(batt, a, d)
        if d.status != "stable":
            break
    assert d.dying and d.death_clock == 0


def test_victory_when_a_side_is_all_downed():
    batt, a, d = _melee_battle()
    d.status = "dying"
    batt._check_winner()
    assert batt.winner == "player"
    assert d.status in ("stable", "dead")             # dangling save resolved


def test_win_waits_for_dying_allies_to_resolve():
    """Enemy is down but an ally is still bleeding out and a teammate stands:
    the battle is not called until the dying ally is stable or dead."""
    batt, a, d = _melee_battle()
    mate = _recruit(batt)
    mate.pos = (5, 6)
    a.go_down(batt.log)                               # a is dying, mate stands
    d.status = "dead"                                 # enemy side wiped
    assert batt._check_winner() is None               # mop-up, not over yet
    assert batt._mopup_open
    random.seed(0)                                    # let the clock run out -> save
    for _ in range(data.DYING_TURNS):
        batt._resolve_dying_turn(a)
    assert a.status in ("stable", "dead")
    assert batt._check_winner() == "player"


def test_lost_lethal_battle_takes_the_whole_squad():
    batt, a, d = _melee_battle()
    a.status = "stable"                               # would have "survived"
    # enemy still stands, no player is up -> total defeat
    batt._check_winner()
    assert batt.winner == "enemy"
    assert a.status == "dead" and not a.survived


# --------------------------------------------------------------------------- #
# ammo and improvised weapon                                                   #
# --------------------------------------------------------------------------- #

def test_besteiro_starts_with_ammo():
    u = _unit()
    u.set_occupation("Crossbowman")
    assert Combatant(u).ammo == data.QUIVER_AMMO and u.weapon_name == "Light Crossbow"


def test_ranged_attack_consumes_one_bolt():
    batt, a, d = _melee_battle()
    batt.board.walls = set()                          # clear lane between shooter and target
    a.equip_weapon("Light Crossbow"); a.ammo = 3
    a.pos, d.pos = (2, 5), (9, 5)
    a.torch_hand = False
    for u in batt.units:                              # light the lane so LOS+sight hold
        u._ability = abilities.get("none")
    batt.ground = [GroundObject.torch((6, 5))]
    a.ap = 2
    assert actions.ATTACK.can(batt, a, d)
    actions.ATTACK.execute(batt, a, d)
    assert a.ammo == 2


def test_unit_attack_bonus_picks_the_right_attribute():
    """`Unit.attack_bonus` -- the base to-hit the guild screen shows on the
    weapon row (and `sheet_panel._to_hit` reuses)."""
    u = _unit()
    u.strength, u.dexterity = 16, 8               # +3 STR, -1 DEX
    u._derive_combat()
    u.take_from_hand()                            # start from empty hands
    assert u.attack_bonus == (3, "STR")           # unarmed hits with Strength
    u.give_to_hand("Axe")                         # plain melee -> STR
    assert u.attack_bonus == (3, "STR")
    u.give_to_hand("Dagger")                      # finesse -> better of STR/DEX
    assert u.attack_bonus == (3, "STR/DEX")
    u.give_to_hand("Light Crossbow")              # ranged -> DEX
    assert u.attack_bonus == (-1, "DEX")


def test_attack_bonus_folds_in_the_to_hit_talent():
    u = _unit(seed=1)
    u.combat_xp = 10
    u.choose_talent("combat", "strong")
    u.choose_talent("combat", "sure_strike")      # +1 to hit on STR attacks
    u.give_to_hand("Axe")
    assert u.attack_bonus[0] == u.mod_strength + 1
    u._base_inventory.append("Quiver")
    u.give_to_hand("Light Crossbow")              # DEX attack -> Sure Strike doesn't apply
    assert u.attack_bonus[0] == u.mod_dexterity


def test_crossbow_without_ammo_is_improvised():
    u = _combatant()
    u.equip_weapon("Light Crossbow"); u.ammo = 0
    assert u.improvised and not u.ranged and u.attack_range == 1
    # to-hit uses Strength (melee), not Dexterity
    labels = {lbl for _, _, lbl in u.attack_mods(None)}
    assert "STR" in labels and "DEX" not in labels
    # damage die is the size unarmed die, never 1d8
    faces = data.UNARMED_ATTACK[u.size][1]
    assert max(u.damage_roll() for _ in range(200)) <= faces + u.mod_strength + u._ability.melee_damage


# --------------------------------------------------------------------------- #
# flanking                                                                     #
# --------------------------------------------------------------------------- #

def _flank_battle():
    random.seed(3)
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")])
    a, b, e = batt.units
    for u in batt.units:
        u._ability = abilities.get("none")
    a.pos, e.pos = (4, 5), (5, 5)
    return batt, a, b, e


def test_strict_flank_needs_opposite_sides():
    batt, a, b, e = _flank_battle()
    b.pos = (6, 5)                                    # opposite side of a
    assert actions._flanked(batt, a, e)
    b.pos = (4, 4)                                    # adjacent but same side
    assert not actions._flanked(batt, a, e)
    assert actions._pack_flank(batt, a, e)           # loose flank still true


def test_pack_tactics_and_flank_do_not_stack():
    batt, a, b, e = _flank_battle()
    a._ability = abilities.get("pack_tactics")
    b.pos = (6, 5)
    mods = a.attack_mods(e, actions._pack_flank(batt, a, e))
    if actions._flanked(batt, a, e):
        mods.append((2, "circumstance", "Flanquear"))
    total, _ = resolve_bonus(mods)
    assert total == 2 + max(0, a.mod_strength)        # +2 circ once, not +4


# --------------------------------------------------------------------------- #
# persistence                                                                  #
# --------------------------------------------------------------------------- #

def test_unit_save_round_trip_keeps_rolled_values():
    from gartok import persist
    from gartok.unit import ATTRIBUTES
    random.seed(7)
    u = Unit("player")
    u._base_inventory = ["Rope", "Map"]
    v = Unit.from_save(persist.unit_to_dict(u))
    for f in ("name", "alignment", "age", "hp_max", "ac", "speed",
              "mental_defense", "languages", "_base_inventory", "gold"):
        assert getattr(v, f) == getattr(u, f), f
    assert v.race["name"] == u.race["name"]
    assert v.occupation["name"] == u.occupation["name"]
    assert [getattr(v, a) for a in ATTRIBUTES] == [getattr(u, a) for a in ATTRIBUTES]


def test_weapon_is_an_item_hand_and_pack():
    u = _unit()
    start = u.equipped_weapon
    assert start in data.WEAPONS and Combatant(u).weapon_hand
    u.give_to_pack(u.take_from_hand())               # stow it
    assert u.equipped_weapon is None and start in u._base_inventory
    c = Combatant(u)
    assert c.unarmed and not c.weapon_hand           # fights unarmed next battle
    u.give_to_hand("Axe")                        # draw a different weapon
    assert u.equipped_weapon == "Axe"
    c = Combatant(u)
    assert c.weapon_name == "Axe" and not c.unarmed


def test_offhand_torch_lights_unless_a_two_handed_weapon_blocks_it():
    u = _unit()
    u.equipped_weapon, u.equipped_offhand = "Dagger", data.TORCH_ITEM
    assert Combatant(u).torch_hand                    # one-handed weapon: off hand free
    u.equipped_weapon = "Light Crossbow"                  # two-handed: off hand occupied
    assert not Combatant(u).torch_hand
    assert u.equipped_offhand == data.TORCH_ITEM      # still assigned, just not lit


def test_equipping_two_handed_weapon_bumps_offhand_torch_to_pack():
    u = _unit()
    u.equipped_weapon, u.equipped_offhand = "Dagger", data.TORCH_ITEM
    u.give_to_hand("Light Crossbow")
    assert u.equipped_offhand is None and data.TORCH_ITEM in u._base_inventory


def test_equipped_weapon_survives_save():
    from gartok import persist
    random.seed(9)
    u = Unit("player")
    u.give_to_hand("Axe")
    u.give_to_offhand(data.TORCH_ITEM)
    u.give_to_pack("Dagger")
    v = Unit.from_save(persist.unit_to_dict(u))
    assert v.equipped_weapon == "Axe"
    assert v.equipped_offhand == data.TORCH_ITEM and Combatant(v).torch_hand
    assert "Dagger" in v._base_inventory


def test_save_slot_file_round_trip():
    from gartok import persist
    from gartok.guild import Guild
    from gartok.clock import Clock
    slot = persist.NUM_SLOTS - 1
    if os.path.exists(persist.slot_path(slot)):
        return                                        # never clobber a real save
    random.seed(8)
    guild = Guild([Unit("player") for _ in range(3)], battles_won=4,
                  arena_reputation=3, clock=Clock(30 * 3600), node="wilds")
    guild.roster[0].gold = 42
    pool = recruit.refresh_pool(guild)
    recruit.bar(guild, pool[0], guild.roster[0])
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.battles_won == 4 and back.arena_reputation == 3
        assert back.clock.seconds == 30 * 3600 and back.node == "wilds"
        assert [u.name for u in back.roster] == [u.name for u in guild.roster]
        assert [u.hp_max for u in back.roster] == [u.hp_max for u in guild.roster]
        assert back.roster[0].gold == 42
        assert back.taverna_week == guild.taverna_week
        assert [u.uid for u in back.taverna_pool] == [u.uid for u in pool]
        assert back.taverna_blocked == [[pool[0].uid, guild.roster[0].uid]]
    finally:
        persist.delete_slot(slot)


# --------------------------------------------------------------------------- #
# flee the battle                                                              #
# --------------------------------------------------------------------------- #

def test_flee_needs_the_map_edge():
    batt, a, d = _melee_battle()
    a.pos, d.pos = (5, 5), (12, 9)                    # a mid-board, foe far
    assert not actions.FLEE.available(batt, a)
    a.pos = (0, 5)                                    # left edge, foe still 12 away
    assert actions.FLEE.available(batt, a)


def test_flee_succeeds_when_faster_or_far_and_ends_the_fight_left_behind():
    batt, a, d = _melee_battle()
    mate = _recruit(batt)
    a.pos, mate.pos, d.pos = (0, 5), (5, 5), (2, 5)   # foe adjacent-ish to a
    a.speed, d.speed = 9, 4                           # a outruns the pursuer
    a.ap = 2
    mate.go_down(batt.log)                            # a downed ally left on the field
    actions.FLEE.execute(batt, a, None)
    assert a.fled and a.survived and not a.alive and a.ap == 0
    # still an enemy up and no player standing -> enemy "wins", the downed mate is lost
    assert batt.winner == "enemy" and mate.dead


def test_flee_blocked_when_pursuers_keep_pace():
    batt, a, d = _melee_battle()
    a.pos, d.pos = (0, 5), (2, 5)                     # edge, but the foe is 2 away
    a.speed, d.speed = 5, 8                           # slower than the pursuer
    assert not actions.FLEE.available(batt, a)        # not faster, not far enough
    actions.FLEE.execute(batt, a, None)
    assert not a.fled and a.status == "up"


def test_all_enemies_fleeing_hands_the_player_the_win():
    batt, a, d = _melee_battle()
    d.pos, d.speed = (COLS - 1, 5), 9
    a.speed = 4
    actions.FLEE.execute(batt, d, None)
    assert d.fled and batt.winner == "player"


def test_flee_drags_an_adjacent_downed_ally_and_leaves_the_far_one():
    batt, a, d = _melee_battle()
    near, far = _recruit(batt), _recruit(batt)
    a.pos, near.pos, far.pos, d.pos = (0, 5), (0, 6), (8, 8), (11, 9)
    a.speed = 9
    near.go_down(batt.log); far.go_down(batt.log)
    a.ap = 2
    actions.FLEE.execute(batt, a, None)
    assert a.fled and near.fled and near.survived
    assert batt.winner == "enemy" and far.dead      # too far to drag -> lost with the defeat


# --------------------------------------------------------------------------- #
# tendency-driven AI (audio 4)                                                 #
# --------------------------------------------------------------------------- #

def test_evil_ai_gives_a_downed_enemy_the_coup_de_grace():
    from gartok import ai
    batt, a, d = _melee_battle()
    d.alignment = "Chaotic and Evil"
    a.go_down(batt.log)                              # the player is dying, adjacent to d
    assert a.dying
    d.ap = 2
    batt.turn_idx = batt.order.index(d)
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
    random.seed(0)                                   # d20 13 -> the stabilize lands
    ai.take_turn(batt, d)
    assert mate.stable


def test_ai_never_flees_a_non_lethal_bout():
    from gartok import ai
    random.seed(0)
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")], lethal=False)
    e = batt.enemy_units[0]
    e.pos, e.hp, e.alignment = (0, 5), 1, "Chaotic and Evil"
    assert ai._should_flee(batt, e) is False


# --------------------------------------------------------------------------- #
# hunger                                                                       #
# --------------------------------------------------------------------------- #

def test_hunger_ramps_penalties_and_caps_hp():
    u = _unit(seed=5)
    fed_str, fed_hp = u.mod_strength, u.hp_max
    u.unfed_days = 1
    u._derive_combat()
    assert u.mod_strength == fed_str - 1                  # -2 to the score = -1 to the mod
    assert u.hunger_label == "hungry" and not u.incapacitated
    u.unfed_days = 2
    u._derive_combat()
    assert u.mod_strength == fed_str - 2 and u.hp_max == 1
    u.unfed_days = 3
    u._derive_combat()
    assert u.incapacitated and u.hunger_label == "starving to death"
    u.unfed_days = 0
    u._derive_combat()
    assert u.mod_strength == fed_str and u.hp_max == fed_hp   # re-derive never re-rolls HP


def test_encumbrance_penalises_str_dex_and_speed():
    from gartok.data import mod
    u = _unit(seed=5)
    u.equipped_weapon = None
    u._base_inventory = []
    u._derive_combat()
    assert not u.encumbered
    unloaded_speed = u.speed
    exp_str, exp_dex = mod(u.strength - 2), mod(u.dexterity - 2)
    u._base_inventory = ["Iron Bar"] * 20          # ~100 kg, well over carry_normal
    u._derive_combat()
    assert u.encumbered
    assert u.mod_strength == exp_str and u.mod_dexterity == exp_dex
    assert u.speed == max(1, unloaded_speed - 1)


def test_encumbrance_does_not_shrink_carry_capacity():
    u = _unit(seed=5)
    u.equipped_weapon = None
    u._base_inventory = []
    u._derive_combat()
    cap_n, cap_m = u.carry_normal, u.carry_max
    u._base_inventory = ["Iron Bar"] * 20
    u._derive_combat()
    assert u.encumbered and u.carry_normal == cap_n and u.carry_max == cap_m


def test_dropping_weight_lifts_encumbrance():
    u = _unit(seed=5)
    u.equipped_weapon = None
    u._base_inventory = ["Iron Bar"] * 20
    u._derive_combat()
    assert u.encumbered
    u._base_inventory = []
    u._derive_combat()
    assert not u.encumbered


def test_encumbrance_survives_a_save_round_trip():
    from gartok import persist
    u = _unit(seed=5)
    u._base_inventory = ["Iron Bar"] * 20
    u._derive_combat()
    assert u.encumbered
    u2 = Unit.from_save(persist.unit_to_dict(u))
    assert u2.encumbered and u2.mod_strength == u.mod_strength


def test_eating_a_ration_resets_hunger():
    u = _unit(seed=1)
    u._base_inventory = ["1kg Potato", "Rope"]
    u.unfed_days = 2
    assert u.consume_daily_food() == "ate"
    assert u.unfed_days == 0 and "1kg Potato" not in u._base_inventory
    assert "Rope" in u._base_inventory


def test_autotroph_never_eats_or_starves():
    u = _unit(seed=1)
    u._ability = abilities.get("autotroph")
    u._base_inventory = []
    for _ in range(6):
        assert u.consume_daily_food() == "ate"
    assert u.unfed_days == 0 and u.hunger_level == 0


def test_starving_without_food_eventually_kills():
    u = _unit(seed=2)
    u._base_inventory = []
    outcomes = [u.consume_daily_food() for _ in range(data.STARVATION_DEATH_DAYS)]
    assert outcomes[:-1] == ["hungry"] * (data.STARVATION_DEATH_DAYS - 1)
    assert outcomes[-1] == "dead"


def test_guild_pass_time_feeds_starves_and_buries():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(3)
    fed = Unit("player"); fed._base_inventory = ["1kg Meat", "1kg Meat"]
    doomed = Unit("player"); doomed._base_inventory = []
    guild = Guild([fed, doomed], clock=Clock(6 * 3600))    # 06:00 day 1
    guild.pass_time(24)                                     # -> day 2
    assert fed.unfed_days == 0 and "1kg Meat" in fed._base_inventory
    assert doomed.unfed_days == 1 and doomed in guild.roster
    for _ in range(data.STARVATION_DEATH_DAYS):
        guild.pass_time(24)
    assert doomed not in guild.roster and fed in guild.roster


def test_eat_now_only_bites_when_hungry_and_carrying_food():
    u = _unit(seed=1)
    u._base_inventory = ["1kg Meat"]
    assert u.eat_now() is False                       # saciado: no meal, food kept
    assert u._base_inventory == ["1kg Meat"]
    u.unfed_days = 2
    assert u.eat_now() is True
    assert u.unfed_days == 0 and u._base_inventory == []
    u.unfed_days = 2
    assert u.eat_now() is False                       # hungry but nothing to eat


def test_do_maintenance_feeds_the_hungry_without_waiting_for_the_day():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(3)
    u = Unit("player")
    u.unfed_days = 1
    u._base_inventory = ["1kg Meat"]
    u._derive_combat()
    guild = Guild([u], clock=Clock(10 * 3600))        # 10:00 day 1
    events = guild.do_maintenance()                   # 1 h stop, no day crossed
    assert guild.clock.day == 1 and guild.clock.hour_of_day == 11
    assert u.unfed_days == 0 and u.rations == 0
    assert any("eat" in e for e in events)


def test_guild_screen_multidrop_moves_every_picked_pack_item():
    from gartok.guild import Guild
    from gartok.guild_screen import GuildScreen
    random.seed(4)
    a, b = Unit("player"), Unit("player")
    a._base_inventory = ["Rope", "1kg Meat", "Map"]
    b._base_inventory = []
    g = Guild([a, b])
    scr = GuildScreen(None, g, on_back=lambda: None)
    scr.selected = [(a, 0), (a, 2)]                       # Corda + Mapa, indices bracket a keeper
    scr._give_many(b, "pack")
    assert a._base_inventory == ["1kg Meat"]             # the un-picked row is untouched
    assert sorted(b._base_inventory) == ["Map", "Rope"]
    assert scr.selected == []


def test_guild_screen_multidrop_on_a_hand_takes_the_first_that_fits():
    from gartok.guild import Guild
    from gartok.guild_screen import GuildScreen
    random.seed(4)
    a = Unit("player")
    a.equipped_weapon = None
    a._base_inventory = ["Rope", "Dagger"]
    g = Guild([a])
    scr = GuildScreen(None, g, on_back=lambda: None)
    scr.selected = [(a, 0), (a, 1)]
    scr._give_many(a, "hand")
    assert a.equipped_weapon == "Dagger" and a._base_inventory == ["Rope"]


def test_hunger_survives_a_save_round_trip():
    from gartok import persist
    random.seed(7)
    u = Unit("player")
    u.unfed_days = 2
    u._derive_combat()
    v = Unit.from_save(persist.unit_to_dict(u))
    assert v.unfed_days == 2 and v.hp_max == 1
    assert v.mod_strength == u.mod_strength
    v.unfed_days = 0
    v._derive_combat()
    assert v.hp_max == v._hp_roll + v.mod_constitution + v._ability.hp_max


# --------------------------------------------------------------------------- #
# Campaign: folding a battle back into the guild                                #
# --------------------------------------------------------------------------- #

def test_absorb_battle_permadeath_and_clock():
    from gartok import campaign
    from gartok.guild import Guild
    random.seed(2)
    squad = [Unit("player") for _ in range(3)]
    guild = Guild(list(squad))
    battle = Battle(squad, [Unit("enemy")])
    battle.winner = "player"
    battle.round_no = 4
    battle.player_units[1].status = "dead"          # the middle member falls
    battle.player_units[0].status = battle.player_units[2].status = "up"

    out = campaign.absorb_battle(guild, squad, battle)

    assert out.won and not out.campaign_over
    assert squad[1] not in guild.roster and len(guild.roster) == 2
    assert out.fallen == [squad[1]] and set(out.survivors) == {squad[0], squad[2]}
    assert guild.battles_won == 1
    assert guild.clock.seconds == 4 * 6                # ~6 s per round fought


def test_absorb_battle_arena_win_pays_the_purse_not_loot():
    from gartok import campaign
    from gartok.guild import Guild
    random.seed(5)
    squad = [Unit("player")]
    guild = Guild(list(squad))
    battle = Battle(squad, [Unit("enemy")], lethal=False)
    battle.winner = "player"
    for u in battle.player_units:
        u.status = "up"

    out = campaign.absorb_battle(guild, squad, battle,
                                 arena_offer={"purse": 55, "enemies": 1, "entry": 15})
    assert out.arena_reward == 55 and out.loot_pool == []
    assert guild.arena_reputation == 1


# --------------------------------------------------------------------------- #
# market haggling                                                              #
# --------------------------------------------------------------------------- #

def test_alignment_distance_axes():
    assert data.alignment_distance("Lawful and Good", "Lawful and Good") == 0
    assert data.alignment_distance("Lawful and Good", "Chaotic and Evil") == 4
    assert data.alignment_distance("Lawful and Neutral", "Neutral and Neutral") == 1


def test_no_shared_language_means_no_deal():
    m = _unit(seed=1)
    m.languages = ["Orcish"]
    assert economy.market_deal([m], "Ankarin", "Lawful and Neutral") == 0.0
    assert economy.buy_price("Dagger", 0.0) == economy.PRICES["Dagger"]


def test_charisma_and_alignment_bend_the_price_but_resale_stays_a_loss():
    good = _unit(seed=1)
    good.languages = ["Ankarin"]
    good.charisma = 18
    good.alignment = "Lawful and Neutral"                        # same as the vendor
    good._derive_combat()
    deal = economy.market_deal([good], "Ankarin", "Lawful and Neutral")
    assert deal > 0
    assert economy.buy_price("Axe", deal) < economy.buy_price("Axe", 0.0)
    assert economy.sell_price("Axe", deal) > economy.sell_price("Axe", 0.0)
    assert economy.sell_price("Axe", deal) < economy.buy_price("Axe", deal)

    hostile = _unit(seed=1)
    hostile.languages = ["Ankarin"]
    hostile.charisma = 6
    hostile.alignment = "Chaotic and Evil"                     # opposed -> premium
    hostile._derive_combat()
    bad = economy.market_deal([hostile], "Ankarin", "Lawful and Neutral")
    assert bad < 0 and economy.buy_price("Axe", bad) > economy.buy_price("Axe", 0.0)


def test_market_deal_picks_the_best_speaker():
    from gartok.market_screen import MarketScreen
    from gartok import world
    random.seed(1)
    loud = Unit("player"); loud.languages = ["Ankarin"]; loud.charisma = 17
    loud.alignment = "Lawful and Neutral"; loud._derive_combat()
    mute = Unit("player"); mute.languages = ["Orcish"]; mute.charisma = 20
    ms = MarketScreen.__new__(MarketScreen)
    ms.shoppers = [loud, mute]
    ms.node = world.node("market")
    ms.deal = economy.market_deal(ms.shoppers, ms.node.language, ms.node.alignment)
    assert ms.deal > 0                                      # the Orc's 20 CHA is wasted


# --------------------------------------------------------------------------- #
# armor                                                                        #
# --------------------------------------------------------------------------- #

def _bare_human(strength=20, **over):
    """An unloaded Humano (Medio, cm 1.0, no natural armor). Strength 20 by
    default -> carry_normal 35 kg, room for a mid-weight armor before encumbrance."""
    u = _unit(**over)
    u.set_race("Human")
    u.base_attributes["strength"] = strength
    u._configure_race()                                # Humano mods are all 0
    u.equipped_weapon = u.equipped_offhand = None
    u._base_inventory = []
    u._derive_combat()
    return u


def test_armor_raises_ac_and_caps_dexterity():
    u = _bare_human(seed=1)
    u.dexterity = 18                                    # +4 Dexterity mod
    u._derive_combat()
    bare_ac = u.ac
    u.give_to_armor("Chainmail")                    # +3 AC, Dex to AC capped at +2, 10 kg
    assert not u.encumbered
    assert u.ac == bare_ac - 4 + 2 + 3
    assert u.equipped_armor == "Chainmail"


def test_leather_armor_keeps_full_dexterity():
    u = _bare_human(seed=1)
    u.dexterity = 18
    u._derive_combat()
    base = u.ac
    u.give_to_armor("Leather Jerkin")                   # +1 AC, no Dex cap
    assert not u.encumbered and u.ac == base + 1


def test_plate_slows_you_and_its_weight_encumbers_on_top():
    u = _bare_human(strength=10, seed=1)                # carry_normal 15 kg
    base_speed = u.speed
    u.give_to_armor("Plate Armor")               # -2 squares, and 28 kg overloads
    assert u.encumbered
    assert u.speed == max(1, base_speed - 2 - 1)        # armor -2, encumbrance -1


def test_equipping_armor_stows_the_old_piece():
    u = _bare_human(seed=1)
    u.give_to_armor("Leather Jerkin")
    u.give_to_armor("Chainmail")
    assert u.equipped_armor == "Chainmail"
    assert "Leather Jerkin" in u._base_inventory


def test_armor_weighs_the_same_worn_or_stowed():
    u = _bare_human(seed=1)
    base = u.load
    u.give_to_pack("Chainmail")
    stowed = u.load
    assert stowed == base + data.ARMOR["Chainmail"]["weight"]
    u.give_to_armor(u.take_from_pack(u._base_inventory.index("Chainmail")))
    assert u.load == stowed


def test_worn_armor_reaches_the_combatant():
    u = _bare_human(seed=1)
    u.give_to_armor("Chainmail")
    c = Combatant(u)
    assert c.ac == u.ac and c.speed == u.speed


def test_armor_is_stocked_and_priced_by_the_ac_it_grants():
    for name in data.ARMOR:
        assert name in economy.MARKET_STOCK and name in economy.PRICES
    assert (economy.PRICES["Leather Jerkin"] < economy.PRICES["Chainmail"]
            < economy.PRICES["Plate Armor"])


def test_armor_survives_a_save_round_trip():
    from gartok import persist
    u = _bare_human(seed=7)
    u.give_to_armor("Brigandine")
    ac, speed, enc = u.ac, u.speed, u.encumbered
    u2 = Unit.from_save(persist.unit_to_dict(u))
    assert u2.equipped_armor == "Brigandine"
    assert u2.ac == ac and u2.speed == speed and u2.encumbered == enc


# --------------------------------------------------------------------------- #
# combat XP                                                                    #
# --------------------------------------------------------------------------- #

def test_downing_a_standing_enemy_credits_the_killer():
    batt, a, d = _melee_battle()
    a.equip_weapon("Axe")
    d.dr = 0
    random.seed(2)
    for _ in range(30):
        if not d.alive:
            break
        d.hp = 1
        a.ap = 2
        actions.ATTACK.execute(batt, a, d)
    assert not d.alive and a.kills == 1


def test_finishing_a_downed_enemy_does_not_double_count():
    batt, a, d = _melee_battle()
    a.equip_weapon("Axe")
    d.go_down(batt.log)                                 # already dying: someone else's kill
    random.seed(2)
    for _ in range(30):
        if d.dead:
            break
        a.ap = 2
        actions.ATTACK.execute(batt, a, d)
    assert d.dead and a.kills == 0


def test_ferocity_credits_the_hit_that_brought_the_orc_to_zero():
    batt, a, d = _melee_battle()
    d.char._ability = abilities.get("ferocity")
    d.char.ability_id = "ferocity"
    d.dr = 0
    a.equip_weapon("Axe")
    random.seed(2)
    for _ in range(30):
        if d.ferocity_pending or not d.alive:
            break
        d.hp = 3
        a.ap = 2
        actions.ATTACK.execute(batt, a, d)
    assert d.ferocity_pending and a.kills == 0        # still on its feet: no credit yet
    d.end_turn(batt.log)
    assert not d.alive and a.kills == 1               # falls at end of turn -> attacker credited


def test_absorb_battle_folds_kills_into_combat_xp():
    from gartok import campaign
    from gartok.guild import Guild
    random.seed(2)
    squad = [Unit("player") for _ in range(2)]
    guild = Guild(list(squad))
    battle = Battle(squad, [Unit("enemy")])
    battle.winner = "player"
    battle.player_units[0].status = battle.player_units[1].status = "up"
    battle.player_units[0].combat_xp_earned = 2
    out = campaign.absorb_battle(guild, squad, battle)
    assert squad[0].combat_xp == 2 and squad[1].combat_xp == 0
    assert out.xp_awards == {squad[0].name: 2}


def test_combat_xp_survives_a_save_round_trip():
    u = _unit(seed=1)
    u.combat_xp = 5
    assert Unit.from_save(persist.unit_to_dict(u)).combat_xp == 5


# --------------------------------------------------------------------------- #
# leveling: progression curves, talents, mean-level hit dice                    #
# --------------------------------------------------------------------------- #

def test_combat_level_thresholds():
    from gartok import progression
    assert progression.combat_level(2) == 0
    assert progression.combat_level(3) == 1
    assert progression.combat_level(9) == 1
    assert progression.combat_level(10) == 2


def test_xp_award_scales_by_level_gap():
    from gartok import progression
    assert progression.xp_award(0, 0) == 1
    assert progression.xp_award(0, 10) == 11
    assert progression.xp_award(1, 1) == 1
    assert progression.xp_award(3, 0) == 0        # veteran mopping up: nothing


def test_credit_kill_uses_the_attacker_and_victim_levels():
    atk = _combatant(seed=1, combat_xp=10)        # combat level 2
    vic = _combatant(seed=2, combat_xp=0)         # combat level 0
    atk.credit_kill(vic)
    assert atk.kills == 1 and atk.combat_xp_earned == 0
    vic2 = _combatant(seed=3, combat_xp=10)
    atk.credit_kill(vic2)
    assert atk.combat_xp_earned == 1              # equal level -> +1


def test_choosing_a_combat_root_raises_the_real_attribute():
    u = _unit(seed=1)
    u.combat_xp = 3
    before = u.strength
    hp_before = u.hp_max
    assert u.pending_picks == ["combat"]
    assert u.choose_talent("combat", "strong")
    assert u.strength == before + 1               # the score itself, shown on the sheet
    assert u.pending_picks == []
    assert not u.choose_talent("combat", "agile")  # pick already spent
    assert not u.choose_talent("combat", "strong")  # not twice
    _ = hp_before  # derived stats were rebuilt (hp_max may or may not move by parity)


def test_negotiator_lifts_only_the_haggle_charisma():
    u = _unit(seed=4)
    u.work_hours = economy.LUMBER_XP_HOURS * 2    # work level 1
    cha_mod = u.mod_charisma
    assert u.choose_talent("work", "negotiator")
    assert u.mod_charisma == cha_mod              # the real Charisma is untouched
    assert u.haggle_charisma_mod == data.mod(
        u.charisma + u.hunger_attribute_penalty + 1)


def test_carrier_relieves_only_cargo_weight():
    u = _unit(seed=5)
    u.work_hours = economy.LUMBER_XP_HOURS * 2
    u._base_inventory = ["Rope", "1kg Meat"]     # cargo + a consumable
    u._derive_combat()
    load = u.load
    assert u.choose_talent("work", "carrier")
    assert u.load == load                         # displayed weight unchanged
    assert u.carry_load == round(load - 1.0, 1)   # 1 kg off the Rope, not the Meat


def test_mean_level_grants_a_hit_die():
    u = _unit(seed=1)
    hp0 = u.hp_max
    u.combat_xp = 3                               # combat 1 / work 0 -> mean 0
    assert not u.collect_levels()
    assert u.hp_max == hp0
    u.combat_xp = 10                              # combat 2 / work 0 -> mean 1
    assert u.collect_levels()
    assert len(u._level_hp_rolls) == 1
    assert u.hp_max > hp0
    assert not u.collect_levels()                 # idempotent


def test_talents_and_hit_dice_survive_a_save_without_rerolling():
    u = _unit(seed=1)
    u.combat_xp = 10
    u.collect_levels()
    u.choose_talent("combat", "tough")
    d = persist.unit_to_dict(u)
    back = Unit.from_save(d)
    assert back.talents == u.talents
    assert back._level_hp_rolls == u._level_hp_rolls
    assert back.hp_max == u.hp_max
    assert back.constitution == u.constitution


# --------------------------------------------------------------------------- #
# talents: tier 2 (specialise the tier-1 identity)                             #
# --------------------------------------------------------------------------- #

def test_tier2_talent_needs_its_root_first():
    u = _unit(seed=1)
    u.combat_xp = 10                              # combat level 2 -> 2 picks
    assert not u.choose_talent("combat", "sure_strike")   # no Strong yet
    assert u.choose_talent("combat", "strong")
    assert u.choose_talent("combat", "sure_strike")
    assert u.talents["combat"] == ["strong", "sure_strike"]


def test_sure_strike_and_deadeye_key_off_the_attack_attribute():
    tgt = _combatant(seed=7)

    def to_hit(weapon, *picks, ammo=False):
        u = _unit(seed=1)
        u.combat_xp = 10
        for p in picks:
            assert u.choose_talent("combat", p)
        if ammo:
            u._base_inventory.append("Quiver")
        u.give_to_hand(weapon)
        return sum(v for v, *_ in Combatant(u).attack_mods(tgt))

    # Sure Strike (under Strong): +1 on a Strength swing, nothing on a bolt
    assert to_hit("Axe", "strong", "sure_strike") == to_hit("Axe", "strong") + 1
    assert to_hit("Light Crossbow", "strong", "sure_strike", ammo=True) \
        == to_hit("Light Crossbow", "strong", ammo=True)
    # Deadeye (under Agile): the mirror image
    assert to_hit("Light Crossbow", "agile", "deadeye", ammo=True) \
        == to_hit("Light Crossbow", "agile", ammo=True) + 1
    assert to_hit("Axe", "agile", "deadeye") == to_hit("Axe", "agile")


def test_heavy_hand_adds_one_melee_damage():
    def dmg(*picks):
        u = _unit(seed=1)
        u.combat_xp = 10
        for p in picks:
            assert u.choose_talent("combat", p)
        u.give_to_hand("Axe")
        c = Combatant(u)
        random.seed(99)
        return c.damage_roll()

    assert dmg("strong", "heavy_hand") == dmg("strong") + 1


def test_long_reach_extends_ranged_and_thrown_not_melee():
    u = _unit(seed=1)
    u.combat_xp = 10
    assert u.choose_talent("combat", "agile")
    assert u.choose_talent("combat", "long_reach")
    u._base_inventory.append("Quiver")

    u.give_to_hand("Light Crossbow")
    assert Combatant(u).attack_range == data.WEAPONS["Light Crossbow"]["range"] + 1
    u.give_to_hand("Dagger")
    assert Combatant(u).throw_range == data.WEAPONS["Dagger"]["thrown"] + 1
    u.give_to_hand("Axe")
    assert Combatant(u).attack_range == 1         # melee reach is untouched


def test_hardy_adds_hp_per_hit_die_and_bulwark_adds_ac():
    u = _unit(seed=1)
    u.combat_xp = 21                              # combat level 3 -> 3 picks
    u.collect_levels()                            # mean level 1 -> one extra hit die
    hit_dice = 1 + len(u._level_hp_rolls)
    assert u.choose_talent("combat", "tough")
    hp_after_tough, ac_after_tough = u.hp_max, u.ac
    assert u.choose_talent("combat", "hardy")
    assert u.hp_max == hp_after_tough + hit_dice
    assert u.choose_talent("combat", "bulwark")
    assert u.ac == ac_after_tough + 1


def test_tier2_talent_effect_survives_a_save():
    u = _unit(seed=1)
    u.combat_xp = 10
    u.choose_talent("combat", "tough")
    u.choose_talent("combat", "bulwark")
    ac = u.ac
    back = Unit.from_save(persist.unit_to_dict(u))
    assert back.talents["combat"] == ["tough", "bulwark"]
    assert back.ac == ac


def _work_ready(*picks):
    """A fresh Unit at work level 2 with the given work talents spent."""
    u = Unit("player")
    u.gold = 0
    u._base_inventory = []
    u.work_hours = economy.LUMBER_XP_HOURS * 6    # work_xp 6 -> work level 2 -> 2 picks
    u._derive_combat()
    for p in picks:
        assert u.choose_talent("work", p)
    return u


def test_piecework_lifts_pay_and_brisk_hands_is_individual():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(3)
    plain = _work_ready()
    rich = _work_ready("carrier", "piecework")
    quick = _work_ready("carrier", "brisk_hands")

    # mixed crew: pay is per-worker; the guild leaves when the SLOWEST is done
    guild = Guild([plain, rich, quick], clock=Clock(6 * 3600))
    base = economy.lumber_pay(16)                 # 12 copper
    guild.work_shift([plain, rich, quick], 16)
    assert plain.gold == base
    assert rich.gold == round(base * 1.20)        # Piecework: +20%
    assert quick.gold == base                     # speed does not touch the pay
    assert all(u.work_hours == economy.LUMBER_XP_HOURS * 6 + 16
               for u in (plain, rich, quick))     # full hours banked for XP
    assert guild.clock.seconds == 6 * 3600 + 16 * 3600    # plain drags: full 16 h

    # a Brisk worker on their own: 16 h of work banked in 14.4 h of the clock
    solo = Guild([_work_ready("carrier", "brisk_hands")], clock=Clock(6 * 3600))
    solo.work_shift(solo.roster, 16)
    assert solo.roster[0].work_hours == economy.LUMBER_XP_HOURS * 6 + 16
    assert solo.clock.seconds == 6 * 3600 + round(16 * 0.9 * 3600)


def test_provisioner_discounts_food_with_no_shared_language():
    u = _work_ready("negotiator", "provisioner")
    u.languages = ["Orcish"]                      # not the market's Ankarin
    mods = economy.deal_mods([u], "Ankarin", "Lawful and Neutral")
    assert economy.deal_value(mods, "Axe", "buy") == 0.0          # no general haggle
    assert economy.deal_value(mods, "1kg Meat", "buy") == economy.CHA_DEAL_STEP
    assert economy.deal_value(mods, "1kg Meat", "sell") == 0.0    # buy side only


def test_provisioner_stacks_on_the_base_haggle_for_food_only():
    u = _work_ready("negotiator", "provisioner")
    u.languages = ["Ankarin"]
    u.charisma = 12
    u.alignment = "Lawful and Neutral"           # same as the vendor -> +0.10
    u._derive_combat()
    mods = economy.deal_mods([u], "Ankarin", "Lawful and Neutral")
    general = economy.deal_value(mods, "Axe", "buy")
    assert 0 < general < economy.DEAL_MAX
    assert economy.deal_value(mods, "1kg Meat", "buy") == round(
        general + economy.CHA_DEAL_STEP, 3)
    assert economy.deal_value(mods, "1kg Meat", "sell") == general   # not on sells


def test_fixer_lifts_the_recruiters_pitch():
    r = _work_ready("negotiator", "fixer")
    r.languages = ["Ankarin"]
    r.alignment = "Neutral and Neutral"
    r.mod_charisma = 0                            # pin after the talent re-derive
    c = _unit(seed=2, languages=["Ankarin"], alignment="Neutral and Neutral")
    c.mod_charisma = 0

    p = recruit.convince(r, c, 2, rng=_FixedRNG(10, 10))   # 10 +1 Fixer = 11 vs 10
    assert p.ok and (1, "Fixer") in p.modifiers
    # same rolls, no talent: 10 vs 10 -> tie -> the stranger stays put
    bare = _unit(seed=1, languages=["Ankarin"], alignment="Neutral and Neutral")
    bare.mod_charisma = 0
    assert not recruit.convince(bare, c, 2, rng=_FixedRNG(10, 10)).ok


# --------------------------------------------------------------------------- #
# recruitment                                                                  #
# --------------------------------------------------------------------------- #

class _FixedRNG:
    """A stand-in for `random`: hands back the given d20 values in order."""
    def __init__(self, *vals):
        self.vals = list(vals)

    def randint(self, a, b):
        return self.vals.pop(0)


def _person(seed, *, lang="Comum", align="Neutral and Neutral", cha=0):
    u = _unit(seed=seed, languages=[lang], alignment=align)
    u.mod_charisma = cha
    return u


def test_recruit_needs_a_shared_language():
    r = _person(1, lang="Ankarin")
    c = _person(2, lang="Orcish")
    assert not recruit.can_pitch(r, c)
    p = recruit.convince(r, c, 3)
    assert not p.ok and p.reason == "no shared language"


def test_recruit_is_a_charisma_contest_and_ties_go_to_the_stranger():
    r = _person(1, cha=2)
    c = _person(2, cha=0)
    tie = recruit.convince(r, c, 2, rng=_FixedRNG(10, 12))   # 12 vs 12 -> stranger stays put
    win = recruit.convince(r, c, 2, rng=_FixedRNG(11, 12))   # 13 vs 12 -> signs on
    assert not tie.ok and win.ok
    assert tie.modifiers == []                               # guild of 2 -> no size penalty


def test_taverna_pool_is_stable_within_the_week_then_refreshes():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(1)
    g = Guild([_person(1)], clock=Clock())
    first = list(recruit.refresh_pool(g))
    assert recruit.refresh_pool(g) is g.taverna_pool and g.taverna_pool == first
    g.clock.advance_hours(24 * recruit.REFRESH_DAYS)         # a week goes by
    recruit.refresh_pool(g)
    assert [u.uid for u in g.taverna_pool] != [u.uid for u in first]
    assert g.taverna_blocked == []                           # bars cleared with the new crop


def test_failed_pitch_bars_that_recruiter_only():
    from gartok.guild import Guild
    from gartok.clock import Clock
    g = Guild([], clock=Clock())
    r1, r2, cand = _person(1), _person(3), _person(2)
    recruit.bar(g, cand, r1)
    recruit.bar(g, cand, r1)                                 # idempotent
    assert recruit.barred(g, cand, r1) and not recruit.barred(g, cand, r2)
    assert g.taverna_blocked == [[cand.uid, r1.uid]]


def test_enlist_pulls_the_recruit_out_of_the_pool():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(2)
    g = Guild([_person(1)], clock=Clock())
    pool = recruit.refresh_pool(g)
    cand = pool[1]
    recruit.enlist(g, cand, g.roster[0])
    assert cand in g.roster and cand not in g.taverna_pool and len(g.taverna_pool) == 2


def test_recruit_alignment_distance_docks_the_pitch():
    r = _person(1, align="Lawful and Good")
    c = _person(2, align="Chaotic and Evil")                  # distance 4
    p = recruit.convince(r, c, 0, rng=_FixedRNG(15, 12))   # 15 - 4 = 11  vs  12 -> fail
    assert not p.ok
    assert any(v == -4 for v, _ in p.modifiers)


def test_recruit_bigger_guild_is_a_harder_sell():
    assert (recruit.size_penalty(2), recruit.size_penalty(3), recruit.size_penalty(7)) == (0, 1, 5)
    r, c = _person(1), _person(2)
    small = recruit.convince(r, c, 2, rng=_FixedRNG(11, 10))
    big = recruit.convince(r, c, 6, rng=_FixedRNG(11, 10))   # same rolls, -4 for the crowd
    assert small.ok and not big.ok


def test_enlist_binds_the_recruit_to_the_recruiter():
    from gartok.guild import Guild
    r, c = _person(1), _person(2)
    g = Guild([r])
    recruit.enlist(g, c, r)
    assert c in g.roster and c.recruited_by == r.uid


def test_uid_is_stable_across_a_save_round_trip():
    u = _unit(seed=3)
    assert Unit.from_save(persist.unit_to_dict(u)).uid == u.uid


def test_from_save_backfills_a_uid_for_pre_uid_saves():
    d = persist.unit_to_dict(_unit(seed=3))
    d.pop("uid")
    assert Unit.from_save(d).uid                            # got a fresh one, no crash


def test_recruited_by_survives_a_save_round_trip():
    u = _unit(seed=3)
    u.recruited_by = "deadbeef"
    assert Unit.from_save(persist.unit_to_dict(u)).recruited_by == "deadbeef"


# --------------------------------------------------------------------------- #
# arena torch scatter                                                          #
# --------------------------------------------------------------------------- #

def test_arena_torches_scatter_across_the_whole_floor():
    from gartok.scenario import ArenaScenario
    xs = set()
    for s in range(12):
        random.seed(s)
        b = Battle([Unit("player")], [Unit("enemy")], scenario=ArenaScenario())
        xs.update(o.pos[0] for o in b.ground if o.is_torch)
    assert any(x < 5 for x in xs) and any(x > 10 for x in xs)   # not just the old centre band


# --------------------------------------------------------------------------- #
# lumber yard: day-labour for copper                                           #
# --------------------------------------------------------------------------- #

def test_lumber_pay_is_by_the_whole_block():
    assert economy.lumber_pay(0) == 0
    assert economy.lumber_pay(3) == 0                 # short of a block: nothing
    assert economy.lumber_pay(4) == 3
    assert economy.lumber_pay(15) == 9                # three blocks, 3 h unpaid
    assert economy.lumber_pay(16) == 12               # a full day


def test_work_shift_pays_every_worker_and_banks_the_hours():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(4)
    a, b = Unit("player"), Unit("player")
    a.gold = b.gold = 0
    a._base_inventory = b._base_inventory = []
    for u in (a, b):
        u._derive_combat()
    guild = Guild([a, b], clock=Clock(6 * 3600))      # 06:00 day 1
    events = guild.work_shift([a, b], 16)
    assert a.gold == 12 and b.gold == 12
    assert a.work_hours == 16 and b.work_hours == 16
    assert guild.clock.hour_of_day == 22 and guild.clock.day == 1
    assert any("Lumber yard" in e for e in events)


def test_work_shift_crossing_midnight_runs_the_daily_meal():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(5)
    u = Unit("player")
    u.gold = 0
    u._base_inventory = ["1kg Potato"]
    u._derive_combat()
    guild = Guild([u], clock=Clock(20 * 3600))        # 20:00 day 1
    guild.work_shift([u], 8)                          # -> 04:00 day 2, one meal
    assert guild.clock.day == 2
    assert u.gold == 6 and u.rations == 0 and u.unfed_days == 0


def test_work_xp_is_one_mark_per_16_hours_and_survives_a_save():
    u = _unit(seed=6, work_hours=0)
    assert u.work_xp == 0
    u.work_hours = 15
    assert u.work_xp == 0
    u.work_hours = 32
    assert u.work_xp == 2
    assert Unit.from_save(persist.unit_to_dict(u)).work_hours == 32


def test_madeireira_is_a_work_town_one_hour_from_the_city():
    from gartok import world
    n = world.node("lumber_yard")
    assert n.kind == "town" and n.work
    _, hours = world.route("city", "lumber_yard")
    assert hours == 1


# --------------------------------------------------------------------------- #
# runner                                                                       #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  ERR  {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)

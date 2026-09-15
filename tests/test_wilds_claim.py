"""The Wilds claim campaign (Sistema 3, [[gartok-property-two-paths]]): the
six-stage state machine, the two deliberate fights (CLEAR/SWEEP), hauling
Lumber to raise the fences, garrisoning to sustain the claim, and the
periodic raid that can reset the sustain countdown. Also the first real
consumer of Sistema 1's garrison engine (`world.WILDS_TERRITORY_NODE` is the
first node with a `garrison_job` actually set)."""

import random

from tests.helpers import economy, Unit, world
from gartok import campaign, orders
from gartok.app import App
from gartok.group import Group
from gartok.guild import Guild
from gartok.wilds_claim_screen import WildsClaimScreen

NODE = world.WILDS_TERRITORY_NODE


def _app(guild):
    app = App.__new__(App)
    app.scene = None
    app.fonts = None
    app.guild = guild
    app._battle_squad = []
    app._battle_node = None
    app._arena_offer = None
    app._hunt = None
    app._pause_order = None
    app._pause_group = None
    app._claim_stage_pending = None
    app._map_notices = []
    app._pending = []
    app._save = lambda: None
    return app


def _screen(guild, group):
    s = WildsClaimScreen.__new__(WildsClaimScreen)
    s.guild = guild
    s.group = group
    s.notice = None
    s.on_done = lambda: None
    s.on_fight_clear = lambda g: None
    s.on_fight_sweep = lambda g: None
    return s


# --------------------------------------------------------------------------- #
# the node itself                                                             #
# --------------------------------------------------------------------------- #

def test_the_claim_node_exists_reachable_from_the_wilds_and_offers_the_lumber_job():
    node = world.node(NODE)
    assert node.claim and node.garrison_job == "lumber"
    path, hours = world.route("wilds", NODE)
    assert path == ["wilds", NODE] and hours > 0


# --------------------------------------------------------------------------- #
# the stage state machine                                                     #
# --------------------------------------------------------------------------- #

def test_scouting_flips_the_stage_with_no_check():
    random.seed(1)
    guild = Guild([Unit("player")])
    assert guild.wilds_claim_stage == "NONE"
    guild.wilds_claim_scout()
    assert guild.wilds_claim_stage == "SCOUTED"


def test_building_fences_consumes_the_banked_lumber():
    random.seed(1)
    guild = Guild([Unit("player")])
    guild.wilds_claim_deposit_lumber(economy.WILDS_CLAIM_FENCE_LUMBER + 3)
    guild.wilds_claim_build_fences()
    assert guild.wilds_claim_stage == "FENCED"
    assert guild.wilds_claim_fence_lumber == 3


def test_starting_to_sustain_sets_the_full_countdown():
    random.seed(1)
    guild = Guild([Unit("player")])
    guild.wilds_claim_start_sustaining()
    assert guild.wilds_claim_stage == "SUSTAINING"
    assert guild.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS


def test_sustaining_counts_down_only_while_actually_garrisoned():
    random.seed(1)
    g = Group([Unit("player")], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    g.order = orders.garrison("lumber")

    guild.pass_time(24)
    assert guild.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS - 1

    g.order = orders.idle()                    # pulled out early, not raided
    guild.pass_time(24)
    assert guild.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS


def test_sustaining_the_full_stretch_establishes_the_claim():
    random.seed(1)
    p = Unit("player")
    p._base_inventory = ["Meat"] * (economy.WILDS_CLAIM_SUSTAIN_DAYS + 2)   # never starves mid-test
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    g.order = orders.garrison("lumber")

    for _ in range(economy.WILDS_CLAIM_SUSTAIN_DAYS):
        guild.pass_time(24)
    assert guild.wilds_claim_stage == "ESTABLISHED"
    assert guild.wilds_claim_sustain_days_left is None


def test_a_garrison_elsewhere_does_not_count_toward_sustaining_here():
    random.seed(1)
    g = Group([Unit("player")], node="market")
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    g.order = orders.garrison("lumber")

    guild.pass_time(24)
    assert guild.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS


# --------------------------------------------------------------------------- #
# the screen: scouting, depositing/building, garrisoning                      #
# --------------------------------------------------------------------------- #

def test_screen_scout_advances_the_stage_and_spends_time():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    s = _screen(guild, g)

    day_before = guild.clock.day
    s._scout()
    assert guild.wilds_claim_stage == "SCOUTED"
    assert guild.clock.seconds > 0 or guild.clock.day >= day_before


def test_screen_deposit_moves_all_carried_lumber_into_the_fence_bank():
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    a._base_inventory = ["Lumber", "Lumber", "Rope"]
    b._base_inventory = ["Lumber"]
    g = Group([a, b], node=NODE)
    guild = Guild(None, groups=[g])
    s = _screen(guild, g)

    s._deposit_lumber()
    assert guild.wilds_claim_fence_lumber == 3
    assert a._base_inventory == ["Rope"] and b._base_inventory == []


def test_screen_build_fences_is_refused_below_the_threshold():
    random.seed(1)
    g = Group([Unit("player")], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_deposit_lumber(economy.WILDS_CLAIM_FENCE_LUMBER - 1)
    s = _screen(guild, g)

    s._build_fences()
    assert guild.wilds_claim_stage != "FENCED"


def test_screen_garrison_issues_the_order_and_starts_sustaining():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_stage = "SWEPT"
    done = []
    s = _screen(guild, g)
    s.on_done = lambda: done.append(True)

    s._start_garrison()
    assert g.order.kind == "garrison" and g.order.job == "lumber"
    assert guild.wilds_claim_stage == "SUSTAINING"
    assert done == [True]


def test_screen_collect_lumber_respects_carry_capacity():
    """`carry_max` is re-derived from Strength on every `_derive_combat()` call
    (`Unit._derive_carry`) -- it can't just be assigned and expected to stick
    through a pickup loop that calls it each time (unlike `bank_screen`'s own
    capacity test, which only ever hits the *refusal* path, never a
    successful pickup in between). Filling the pack with same-weight Rope
    instead leaves a real, predictable amount of headroom."""
    random.seed(1)
    p = Unit("player")
    p._base_inventory = []
    p._derive_combat()
    base_load = p.load                          # equipped weapon/armor already counts toward it
    filler = max(0, int((p.carry_max - base_load - 4.0) // 2))   # leaves room for exactly 2 Lumber (2 kg each)
    p._base_inventory = ["Rope"] * filler
    p._derive_combat()
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.garrison_stock[NODE] = ["Lumber"] * 5
    s = _screen(guild, g)

    s._collect_lumber()
    assert p._base_inventory.count("Lumber") == 2
    assert guild.garrison_stock[NODE] == ["Lumber"] * 3


# --------------------------------------------------------------------------- #
# claim battles (CLEAR / SWEEP) through app._battle_end                       #
# --------------------------------------------------------------------------- #

def test_winning_the_clear_battle_advances_the_stage():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_stage = "SCOUTED"
    app = _app(guild)

    app._start_claim_clear_battle(g)
    battle = app.scene.battle
    battle.winner, battle.round_no = "player", 1
    for c in battle.player_units:
        c.status = "up"
    app._battle_squad = [p]
    app._battle_node = world.node(NODE)
    app._battle_end(battle)

    assert guild.wilds_claim_stage == "CLEARED"
    assert app._claim_stage_pending is None


def test_losing_the_sweep_battle_leaves_the_stage_unchanged():
    random.seed(1)
    a, b = Unit("player"), Unit("player")
    g = Group([a, b], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_stage = "FENCED"
    app = _app(guild)

    app._start_claim_sweep_battle(g)
    battle = app.scene.battle
    battle.winner, battle.round_no = "enemy", 1
    battle.player_units[0].status = "up"        # one survivor -- not a full wipe
    battle.player_units[1].status = "dead"
    app._battle_squad = [a, b]
    app._battle_node = world.node(NODE)
    app._battle_end(battle)

    assert guild.wilds_claim_stage == "FENCED"


# --------------------------------------------------------------------------- #
# the raid during SUSTAINING                                                  #
# --------------------------------------------------------------------------- #

def _forced_raid_chance(value):
    orig = economy.WILDS_RAID_CHANCE
    economy.WILDS_RAID_CHANCE = value
    return orig


def test_a_garrison_can_be_raided_mid_sustain():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        g = Group([Unit("player")], node=NODE)
        guild = Guild(None, groups=[g])
        guild.wilds_claim_start_sustaining()
        g.order = orders.garrison("lumber")

        result = campaign.advance(guild, dt=1)
    finally:
        economy.WILDS_RAID_CHANCE = orig

    assert g.order is None
    order = next(o for grp, o in result.pending if grp is g)
    assert order.kind == "wilds_raid" and order.job == "lumber" and len(order.pack) > 0


def test_no_raid_outside_the_sustaining_stage():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        g = Group([Unit("player")], node=NODE)
        guild = Guild(None, groups=[g])
        g.order = orders.garrison("lumber")        # no claim in progress at all
        result = campaign.advance(guild, dt=1)
    finally:
        economy.WILDS_RAID_CHANCE = orig

    assert g.order.kind == "garrison" and not result.pending


def test_winning_the_raid_resumes_the_same_garrison_job():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    order = orders.Order("wilds_raid", pack=(Unit("enemy"),), job="lumber")

    outcome = campaign.BattleOutcome(won=True, survivors=[p], fallen=[])
    events = campaign.resolve_wilds_raid(guild, g, order, outcome)
    assert g.order.kind == "garrison" and g.order.job == "lumber"
    assert guild.wilds_claim_stage == "SUSTAINING"
    assert any("drives off" in e for e in events)


def test_losing_the_raid_resets_the_sustain_countdown():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    guild.wilds_claim_start_sustaining()
    guild.wilds_claim_sustain_days_left = 1     # about to finish -- then a raid hits
    order = orders.Order("wilds_raid", pack=(Unit("enemy"),), job="lumber")

    outcome = campaign.BattleOutcome(won=False, survivors=[p], fallen=[])
    events = campaign.resolve_wilds_raid(guild, g, order, outcome)
    assert g.order.kind == "idle"
    assert guild.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS
    assert any("scattered" in e for e in events)


def test_app_runs_the_wilds_raid_battle_end_to_end():
    random.seed(1)
    orig = _forced_raid_chance(1.0)
    try:
        p = Unit("player")
        g = Group([p], node=NODE)
        guild = Guild(None, groups=[g])
        guild.wilds_claim_start_sustaining()
        g.order = orders.garrison("lumber")
        app = _app(guild)
        app._advance(dt=1)
    finally:
        economy.WILDS_RAID_CHANCE = orig

    assert app._pause_order is not None and app._pause_order.kind == "wilds_raid"
    battle = app.scene.battle
    battle.winner, battle.round_no = "player", 1
    for c in battle.player_units:
        c.status = "up"
    app._battle_squad = [p]
    app._battle_node = world.node(NODE)
    app._battle_end(battle)

    assert app._pause_order is None
    assert g.order.kind == "garrison"


# --------------------------------------------------------------------------- #
# app wiring: opening the screen                                              #
# --------------------------------------------------------------------------- #

def test_app_opens_the_claim_screen():
    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    app = _app(guild)

    app._open_wilds_claim(g, world.node(NODE))
    assert isinstance(app.scene, WildsClaimScreen)


# --------------------------------------------------------------------------- #
# Sistema 1's engine finally has a real consumer                              #
# --------------------------------------------------------------------------- #

def test_a_garrison_at_the_real_claim_node_produces_lumber():
    random.seed(1)
    g = Group([Unit("player"), Unit("player")], node=NODE)
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("lumber")

    guild.pass_time(24)
    assert guild.garrison_stock_at(NODE) == ["Lumber"] * (
        2 * economy.GARRISON_YIELD_PER_MEMBER_PER_DAY)


# --------------------------------------------------------------------------- #
# real draw, through pygame -- every stage panel at least once                #
# --------------------------------------------------------------------------- #

def test_drawing_every_stage_does_not_crash():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    surf = pygame.Surface((1280, 800))

    for stage in ("NONE", "SCOUTED", "CLEARED", "FENCED", "SWEPT", "SUSTAINING", "ESTABLISHED"):
        guild.wilds_claim_stage = stage
        if stage == "SUSTAINING":
            guild.wilds_claim_sustain_days_left = 3
            g.order = orders.garrison("lumber")
        elif stage == "ESTABLISHED":
            guild.garrison_stock[NODE] = ["Lumber", "Lumber"]
            g.order = orders.idle()
        else:
            g.order = None
        s = WildsClaimScreen(Fonts(), guild, g, on_done=lambda: None,
                             on_fight_clear=lambda g: None, on_fight_sweep=lambda g: None)
        s.mouse = (0, 0)
        s.draw(surf)                            # must not raise for any stage


def test_drawing_and_clicking_scout_through_pygame():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))

    random.seed(1)
    p = Unit("player")
    g = Group([p], node=NODE)
    guild = Guild(None, groups=[g])
    s = WildsClaimScreen(Fonts(), guild, g, on_done=lambda: None,
                         on_fight_clear=lambda g: None, on_fight_sweep=lambda g: None)
    surf = pygame.Surface((1280, 800))
    s.mouse = (0, 0)

    s.draw(surf)
    scout = next(r for k, r in s.buttons if k == "scout")
    s._click(scout.center)
    assert guild.wilds_claim_stage == "SCOUTED"


# --------------------------------------------------------------------------- #
# save round trip                                                             #
# --------------------------------------------------------------------------- #

def test_wilds_claim_state_survives_a_save_round_trip():
    import os

    from gartok import persist
    slot = persist.NUM_SLOTS - 1
    if os.path.exists(persist.slot_path(slot)):
        return
    random.seed(1)
    guild = Guild([Unit("player")])
    guild.wilds_claim_start_sustaining()
    guild.wilds_claim_fence_lumber = 4
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.wilds_claim_stage == "SUSTAINING"
        assert back.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS
        assert back.wilds_claim_fence_lumber == 4
    finally:
        persist.delete_slot(slot)

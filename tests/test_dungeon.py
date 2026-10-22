"""Tests for the Ruins of the Ancient Library dungeon, mechanics, and quest progression."""

from gartok import campaign, data, missions, world
from gartok.actions import Disarm, Flee, Investigate, PickUp
from gartok.battle import Battle
from gartok.guild import Guild
from gartok.scenario import AncientRuinsScenario
from gartok.unit import Unit
from tests.helpers import fixed_d20


def test_scout_ancient_ruins():
    u = Unit("player")
    u.base_attributes["wisdom"] = 14
    u._apply_attributes()
    u._derive_combat()
    g = Guild([u], node="road")
    assert not g.is_node_revealed("ancient_ruins")

    # Low roll fails
    with fixed_d20(2):
        ok, msg = campaign.scout_ancient_ruins(g, g.groups[0])
        assert not ok
        assert not g.is_node_revealed("ancient_ruins")

    # High roll succeeds
    with fixed_d20(18):
        ok, msg = campaign.scout_ancient_ruins(g, g.groups[0])
        assert ok
        assert g.is_node_revealed("ancient_ruins")
        assert "discovered" in msg.lower()


def test_ancient_ruins_world_routing():
    # Verify pathfinding route from road to ancient_ruins
    path, hours = world.route("road", "ancient_ruins")
    assert path == ["road", "ancient_ruins"]
    assert hours == 2


def test_dungeon_scenario_setup():
    scenario = AncientRuinsScenario()
    assert scenario._cols == 30
    assert scenario._rows == 18
    assert not scenario.ambient_light

    u1 = Unit("player")
    u2 = Unit("player")
    battle = Battle([u1, u2], scenario.enemies, scenario=scenario, daylight=False, lethal=True)

    # Check secret wall is present in board.walls and secret_walls set
    assert (12, 6) in battle.secret_walls
    assert (12, 6) in battle.board.walls

    # Check traps
    traps = [o for o in battle.ground if o.is_trap]
    assert len(traps) >= 2
    assert any(o.trap_type == "bear trap" for o in traps)
    assert any(o.trap_type == "alarm trap" for o in traps)

    # Check chest and codex relic
    assert any(o.is_chest and o.pos == (20, 3) for o in battle.ground)
    assert any(o.is_relic and o.pos == (27, 11) and o.item_name == data.CODEX_ITEM for o in battle.ground)

    # Check enemies: 2 sentries and 1 boss
    assert len(battle.enemy_units) == 5
    boss = next(e for e in battle.enemy_units if "Archivist" in e.name)
    assert boss.dormant

    # Verify path connectivity from entrance to boss and codex
    assert battle.board.path_to((1, 7), boss.pos, blocked=battle.board.walls)
    assert battle.board.path_to((1, 7), (27, 11), blocked=battle.board.walls)


def test_investigate_secret_wall():
    scenario = AncientRuinsScenario()
    u = Unit("player")
    battle = Battle([u], scenario.enemies, scenario=scenario, daylight=False, lethal=True)
    actor = battle.player_units[0]
    actor.ap = 2

    inv = Investigate()

    # Too far away (at (1, 7)) -> not available
    actor.pos = (1, 7)
    assert not inv.available(battle, actor)

    # Adjacent to secret wall (12, 6) -> e.g. at (13, 7)
    actor.pos = (13, 7)
    assert inv.available(battle, actor)

    # Execute
    inv.execute(battle, actor)
    assert (12, 6) not in battle.secret_walls
    assert (12, 6) not in battle.board.walls
    assert actor.ap == 1


def test_disarm_trap():
    scenario = AncientRuinsScenario()
    u = Unit("player")
    u.base_attributes["dexterity"] = 16
    u._apply_attributes()
    u._derive_combat()
    battle = Battle([u], scenario.enemies, scenario=scenario, daylight=False, lethal=True)
    actor = battle.player_units[0]
    actor.ap = 2

    disarm = Disarm()
    # Move adjacent to bear trap at (8, 8)
    actor.pos = (8, 7)
    assert disarm.available(battle, actor)

    # Disarm success
    with fixed_d20(15):
        disarm.execute(battle, actor)
        assert not any(o.pos == (8, 8) and o.is_trap for o in battle.ground)
        assert "Bear Trap" in actor.inventory
        assert "Bear Trap" in actor.picked_up_items


def test_disarm_fumble_triggers_trap():
    scenario = AncientRuinsScenario()
    u = Unit("player")
    battle = Battle([u], scenario.enemies, scenario=scenario, daylight=False, lethal=True)
    actor = battle.player_units[0]
    actor.ap = 2
    actor.pos = (8, 7)

    disarm = Disarm()
    hp_before = actor.hp
    with fixed_d20(1): # Critical fumble
        disarm.execute(battle, actor)
        assert actor.hp < hp_before


def test_pickup_chest_and_codex():
    scenario = AncientRuinsScenario()
    u = Unit("player")
    battle = Battle([u], scenario.enemies, scenario=scenario, daylight=False, lethal=True)
    actor = battle.player_units[0]
    actor.ap = 2

    # Open chest at (20, 3)
    actor.pos = (20, 3)
    pu = PickUp()
    assert pu.available(battle, actor)
    gold_before = actor.char.money
    pu.execute(battle, actor)
    assert "Scroll of Sleep" in actor.inventory
    assert "Semi-precious Gemstone" in actor.inventory
    assert actor.char.money == gold_before + 150
    assert not any(o.pos == (20, 3) and o.is_chest for o in battle.ground)

    # Pick up Codex at (27, 11)
    actor.ap = 2
    actor.pos = (27, 11)
    assert pu.available(battle, actor)
    pu.execute(battle, actor)
    assert data.CODEX_ITEM in actor.inventory
    assert data.CODEX_ITEM in actor.picked_up_items
    assert not any(o.pos == (27, 11) and o.is_relic for o in battle.ground)


def test_an_unopened_chest_is_not_field_loot():
    from gartok.campaign import absorb_battle
    scenario = AncientRuinsScenario()
    u = Unit("player")
    u.money = 10
    guild = Guild([u], node="ancient_ruins")
    battle = Battle([u], scenario.enemies, scenario=scenario, daylight=False, lethal=True)
    battle.winner = "player"
    outcome = absorb_battle(guild, [u], battle, node=world.node("ancient_ruins"))
    assert u.money == 10
    assert not {"Semi-precious Gemstone", "Bear Trap", data.CODEX_ITEM} & set(outcome.loot_pool)


def test_boss_dormancy_and_alarm_awakening():
    scenario = AncientRuinsScenario()
    u = Unit("player")
    battle = Battle([u], scenario.enemies, scenario=scenario, daylight=False, lethal=True)
    actor = battle.player_units[0]
    actor.pos = (1, 7)
    boss = next(e for e in battle.enemy_units if "Archivist" in e.name)

    assert boss.dormant

    # Boss turn while player is far away in darkness
    from gartok import ai
    ai.take_turn(battle, boss)
    assert boss.dormant
    assert boss.pos == (25, 11) # Did not move

    # Triggering the alarm trap at (12, 7) awakens everyone
    alarm_trap = next(o for o in battle.ground if o.pos == (12, 7))
    battle.trigger_trap(actor, alarm_trap)
    assert not boss.dormant
    assert boss.alerted


def test_flee_with_codex_victory_and_carry_forward():
    scenario = AncientRuinsScenario()
    u = Unit("player")
    guild = Guild([u], node="ancient_ruins")
    battle = Battle([u], scenario.enemies, scenario=scenario, daylight=False, lethal=True)
    actor = battle.player_units[0]

    # Sentries in Room 1 have already been downed by the party
    for e in battle.enemy_units:
        if "Sentry" in e.name:
            e.status = "dead"

    # Give actor the codex and place at entrance escape cell (1, 7)
    actor.inventory.append(data.CODEX_ITEM)
    actor.picked_up_items = [data.CODEX_ITEM]
    actor.pos = (1, 7)
    actor.ap = 2

    flee = Flee()
    assert flee.available(battle, actor)
    flee.execute(battle, actor)
    assert actor.status == "fled"

    # Win check triggers victory
    winner = scenario.win_check(battle)
    assert winner == "player"

    # Absorb battle into guild
    outcome = campaign.absorb_battle(guild, [u], battle, node=world.node("ancient_ruins"))
    assert outcome.won
    assert u.has_item(data.CODEX_ITEM)


def test_library_quest_two_turn_in_and_trusted_deed():
    u = Unit("player")
    guild = Guild([u], node="library")
    # First library deed is completed
    guild.deeds_done.append("library_initiate")
    m1 = missions.accept(guild, u, missions.LIBRARY_DICTIONARY)
    m1.state = "done"

    # Library offers quest 2
    offers = missions.offers_at(guild, "library")
    assert any(t.id == "library_ancient_codex" for t in offers)

    t2 = next(t for t in offers if t.id == "library_ancient_codex")
    m2 = missions.accept(guild, u, t2)
    assert m2.state == "active"

    # Give unit the Codex
    u.give_to_pack(data.CODEX_ITEM)
    assert missions.progress(guild, m2) == 1
    assert missions.can_turn_in(guild, m2)

    # Turn in
    copper_before = u.money
    earned = missions.turn_in(guild, m2)
    assert m2.state == "done"
    assert u.money == copper_before + t2.reward
    assert u.has_item(data.CODEX_ITEM)  # handed back, to be taken to a school

    # Verify library_trusted deed was banked
    assert "library_trusted" in guild.deeds_done
    assert guild.reputation.get("library", 0) >= 1


def test_parse_currency():
    from gartok.loot import parse_currency
    assert parse_currency("50 Copper") == 50
    assert parse_currency("100 Gold") == 100
    assert parse_currency(("copper", 25)) == 25
    assert parse_currency((30, "coins")) == 30
    assert parse_currency("Scroll of Sleep") is None
    assert parse_currency("Semi-precious Gemstone") is None
    assert parse_currency(None) is None


def test_sanctum_spiders_come_from_the_maps_npc_deploy():
    scenario = AncientRuinsScenario()
    spiders = [e for e in scenario.enemies if e.race["name"] == "Giant Spider"]
    assert [s.map_cell for s in spiders] == [(24, 6), (27, 6)]
    battle = Battle([Unit("player")], scenario.enemies, scenario=scenario, daylight=False, lethal=True)
    placed = [e for e in battle.enemy_units if e.race["name"] == "Giant Spider"]
    assert {s.pos for s in placed} == {(24, 6), (27, 6)}
    assert all(s.dormant and s.has_talent("spin_web") and s.footprint == 1 for s in placed)


def test_no_alarm_trap_sits_on_the_first_steps_of_the_deploy_zone():
    scenario = AncientRuinsScenario()
    battle = Battle([Unit("player")], scenario.enemies, scenario=scenario, daylight=False, lethal=True)
    alarms = [o.pos for o in battle.ground if o.is_trap and o.trap_type == "alarm trap"]
    assert alarms and all(x >= 9 for x, _ in alarms)


def _delve(guild, u):
    scenario = AncientRuinsScenario(guild.ruins_cleared)
    return Battle([u], scenario.enemies, scenario=scenario, daylight=False, lethal=True)


def test_the_slain_and_the_taken_stay_gone_after_a_retreat():
    from gartok import scenario as scenario_mod
    u = Unit("player")
    guild = Guild([u], node="ancient_ruins")
    battle = _delve(guild, u)
    for e in battle.enemy_units:
        if "Sentry" in e.name:
            e.status = "dead"
    chest = next(o for o in battle.ground if o.is_chest)
    battle.ground.remove(chest)
    actor = battle.player_units[0]
    actor.status = "fled"

    outcome = campaign.absorb_battle(guild, [u], battle, node=world.node("ancient_ruins"))
    assert not outcome.won
    assert not scenario_mod.ruins_empty(guild)

    battle = _delve(guild, u)
    assert not any("Sentry" in e.name for e in battle.enemy_units)
    assert any("Archivist" in e.name for e in battle.enemy_units)
    assert not any(o.is_chest for o in battle.ground)
    assert any(o.is_relic for o in battle.ground)


def _ruins_keys():
    from gartok import scenario as scenario_mod
    return scenario_mod._ruins_keys()


def _slay_all(battle):
    for e in battle.enemy_units:
        e.status = "dead"


def _walk_out(battle, actor):
    actor.pos, actor.ap = (0, 7), 2
    Flee().execute(battle, actor)
    battle.check_objective()


def test_the_ruins_stay_open_until_the_squad_walks_out():
    u = Unit("player")
    guild = Guild([u], node="ancient_ruins")
    battle = _delve(guild, u)
    _slay_all(battle)
    assert battle._check_winner() is None
    assert not battle.can_withdraw

    actor = battle.player_units[0]
    relic = next(o for o in battle.ground if o.is_relic)
    actor.pos, actor.ap = (relic.pos[0] - 1, relic.pos[1]), 2
    battle.ground = [o for o in battle.ground if o.pos != actor.pos]
    while any(o.is_relic for o in battle.ground):
        PickUp().execute(battle, actor)
    battle.ground = [o for o in battle.ground if not o.is_chest]
    battle.check_objective()
    assert battle.winner is None                  # everything taken, still inside

    _walk_out(battle, actor)
    assert battle.winner == "player"
    campaign.absorb_battle(guild, [u], battle, node=world.node("ancient_ruins"))
    assert u.has_item(data.CODEX_ITEM)


def test_a_codex_left_behind_waits_for_the_next_delve():
    from gartok import scenario as scenario_mod
    u = Unit("player")
    guild = Guild([u], node="ancient_ruins")
    battle = _delve(guild, u)
    _slay_all(battle)
    _walk_out(battle, battle.player_units[0])
    assert battle.winner == "player"

    outcome = campaign.absorb_battle(guild, [u], battle, node=world.node("ancient_ruins"))
    assert not u.has_item(data.CODEX_ITEM)
    assert not {data.CODEX_ITEM, "Semi-precious Gemstone"} & set(outcome.loot_pool)
    assert not scenario_mod.ruins_empty(guild)

    battle = _delve(guild, u)
    assert battle.scenario.enemies == []
    assert [o.item_name for o in battle.ground if o.is_relic] == [data.CODEX_ITEM]
    assert any(o.is_chest for o in battle.ground) and any(o.is_trap for o in battle.ground)
    assert battle._check_winner() is None


def test_an_open_chest_and_the_lifted_codex_leave_the_ruins_empty():
    from gartok import scenario as scenario_mod
    u = Unit("player")
    guild = Guild([u], node="ancient_ruins")
    battle = _delve(guild, u)
    _slay_all(battle)
    battle.ground = [o for o in battle.ground if not (o.is_relic or o.is_chest)]
    _walk_out(battle, battle.player_units[0])
    campaign.absorb_battle(guild, [u], battle, node=world.node("ancient_ruins"))
    assert scenario_mod.ruins_empty(guild)


def test_an_ai_squad_walks_to_the_codex_in_the_empty_ruins():
    from gartok import ai
    u = Unit("player")
    guild = Guild([u], node="ancient_ruins")
    guild.ruins_cleared.update(k for k in _ruins_keys() if k.startswith("npc:"))
    guild.ruins_cleared.update(f"trap:{i}" for i in range(len(AncientRuinsScenario()._traps)))
    battle = _delve(guild, u)
    actor = battle.player_units[0]
    for _ in range(60):
        if battle.winner:
            break
        ai.take_turn(battle, battle.active)
    assert battle.winner == "player"
    assert data.CODEX_ITEM in actor.picked_up_items and actor.fled


def test_a_squad_that_ran_off_loots_nothing():
    u = Unit("player")
    u.money = 10
    guild = Guild([u], node="ancient_ruins")
    battle = _delve(guild, u)
    actor = battle.player_units[0]
    actor.inventory.append(data.CODEX_ITEM)
    actor.picked_up_items = [data.CODEX_ITEM]
    battle.ground = [o for o in battle.ground if not o.is_relic]
    actor.status = "fled"
    assert battle.scenario.win_check(battle) == "player"
    battle.winner = "player"

    outcome = campaign.absorb_battle(guild, [u], battle, node=world.node("ancient_ruins"))
    assert outcome.won and outcome.loot_pool == []
    assert u.money == 10
    assert u.has_item(data.CODEX_ITEM)
    battle = _delve(guild, u)
    assert any(o.is_chest for o in battle.ground)


def test_the_ruins_remember_across_a_save():
    from gartok import persist
    guild = Guild([Unit("a")])
    guild.ruins_cleared.update({"npc:0", "chest:0"})
    world_id = persist.new_world_id()
    persist.save_game(world_id, guild)
    assert persist.load_game(world_id).ruins_cleared == {"npc:0", "chest:0"}


def _clear_the_ruins(guild):
    guild.ruins_cleared.update(_ruins_keys())


def test_the_map_offers_no_way_into_empty_ruins():
    from gartok.map_screen import MapScreen
    from gartok.ui.tokens import fonts as ui_fonts
    guild = Guild([Unit("player")], node="ancient_ruins")
    ms = MapScreen(ui_fonts(), guild, lambda: None, lambda: None, lambda: None, lambda grp: None)

    def blocks():
        return ms._inspector_content(guild.groups[0], world.node("ancient_ruins"))
    assert any(b.get("key") == "ancient_ruins" for b in blocks())
    _clear_the_ruins(guild)
    assert not any(b.get("key") == "ancient_ruins" for b in blocks())
    assert any("ruins lie silent" in b.get("text", "") for b in blocks())


def test_entering_empty_ruins_starts_no_fight():
    from tests.helpers import make_app
    guild = Guild([Unit("player")], node="ancient_ruins")
    _clear_the_ruins(guild)
    app = make_app(guild)
    app._map_notices = []
    done = []
    app._after_activity = lambda: done.append(True)
    app._enter_ancient_ruins(guild.groups[0], world.node("ancient_ruins"))
    assert done and app.scene is None
    assert any("silent" in n for n in app._map_notices)

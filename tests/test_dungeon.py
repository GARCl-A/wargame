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
    assert not g.ancient_ruins_discovered

    # Low roll fails
    with fixed_d20(2):
        ok, msg = campaign.scout_ancient_ruins(g, g.groups[0])
        assert not ok
        assert not g.ancient_ruins_discovered

    # High roll succeeds
    with fixed_d20(18):
        ok, msg = campaign.scout_ancient_ruins(g, g.groups[0])
        assert ok
        assert g.ancient_ruins_discovered
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
    assert len(battle.enemy_units) == 3
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
    gold_before = actor.char.gold
    pu.execute(battle, actor)
    assert "Scroll of Sleep" in actor.inventory
    assert "Amethyst" in actor.inventory
    assert actor.char.gold == gold_before + 150
    assert not any(o.pos == (20, 3) and o.is_chest for o in battle.ground)

    # Pick up Codex at (27, 11)
    actor.ap = 2
    actor.pos = (27, 11)
    assert pu.available(battle, actor)
    pu.execute(battle, actor)
    assert data.CODEX_ITEM in actor.inventory
    assert data.CODEX_ITEM in actor.picked_up_items
    assert not any(o.pos == (27, 11) and o.is_relic for o in battle.ground)


def test_unopened_chest_currency_absorbed_on_victory():
    from gartok.campaign import absorb_battle
    scenario = AncientRuinsScenario()
    u = Unit("player")
    u.gold = 10
    guild = Guild([u], node="ancient_ruins")
    battle = Battle([u], scenario.enemies, scenario=scenario, daylight=False, lethal=True)
    battle.winner = "player"
    absorb_battle(guild, [u], battle, node=world.node("ancient_ruins"))
    assert u.gold == 160


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
    copper_before = u.gold
    earned = missions.turn_in(guild, m2)
    assert m2.state == "done"
    assert u.gold == copper_before + t2.reward
    assert not u.has_item(data.CODEX_ITEM) # Turned in

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
    assert parse_currency("Amethyst") is None
    assert parse_currency(None) is None


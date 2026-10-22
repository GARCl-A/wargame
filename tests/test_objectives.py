"""Tests for the Guild Objectives checklist (onboarding checklist on Guild Screen)."""

from unittest.mock import MagicMock
from gartok import objectives
from gartok.guild import Guild
from gartok.unit import Unit


def test_objectives_initial_state():
    u = Unit("player")
    g = Guild([u])
    assert g.objectives_done == []

    card = objectives.card_data(g)
    assert card["name"] == "Guild Objectives"
    n = len(objectives.OBJECTIVES)
    assert card["rep"] == f"0/{n}"
    assert card["rep_label"] == "done"
    assert len(card["deeds"]) == n
    # All initially open
    assert all(state == "open" for _, _, _, state in card["deeds"])


def test_buy_food_objective():
    u = Unit("player")
    g = Guild([u])
    assert not objectives.is_done(g, "obj_buy_food")

    objectives.complete(g, "obj_buy_food")
    assert objectives.is_done(g, "obj_buy_food")
    assert "obj_buy_food" in g.objectives_done


def test_buy_torch_objective():
    u = Unit("player")
    g = Guild([u])
    assert not objectives.is_done(g, "obj_buy_torch")

    objectives.complete(g, "obj_buy_torch")
    assert objectives.is_done(g, "obj_buy_torch")
    assert "obj_buy_torch" in g.objectives_done


def test_combat_level_1_objective():
    u = Unit("player")
    g = Guild([u])
    assert not objectives.is_done(g, "obj_combat_lv1")

    u.combat_xp = 100
    assert objectives.is_done(g, "obj_combat_lv1")
    objectives.check_and_bank(g)
    assert "obj_combat_lv1" in g.objectives_done


def test_work_chain_progression_and_blurbs():
    from gartok import economy, progression
    u = Unit("player")
    g = Guild([u])

    # Step 0
    blurb0 = objectives._work_chain_blurb(g)
    assert "Step 0/3" in blurb0
    assert not objectives.is_done(g, "obj_work_chain")

    # Step 1: Work Lv 1 reached
    u.work_hours = progression.WORK_XP_THRESHOLDS[0] * economy.LUMBER_XP_HOURS
    blurb1 = objectives._work_chain_blurb(g)
    assert "Step 1/3" in blurb1
    assert not objectives.is_done(g, "obj_work_chain")

    # Step 2: Axe acquired
    u.give_to_pack(objectives.AXE)
    blurb2 = objectives._work_chain_blurb(g)
    assert "Step 2/3" in blurb2
    assert not objectives.is_done(g, "obj_work_chain")

    # Step 3: Work Lv 2 reached -> completed
    u.work_hours = progression.WORK_XP_THRESHOLDS[1] * economy.LUMBER_XP_HOURS
    assert objectives.is_done(g, "obj_work_chain")
    objectives.check_and_bank(g)
    assert "obj_work_chain" in g.objectives_done
    blurb3 = objectives._work_chain_blurb(g)
    assert "reached" in blurb3.lower()


def test_arena_bout_objective():
    u = Unit("player")
    g = Guild([u])
    assert not objectives.is_done(g, "obj_arena_bout")

    g.battles_won = 1                      # a road ambush won is not a bout
    assert not objectives.is_done(g, "obj_arena_bout")
    objectives.complete(g, "obj_arena_bout")
    assert objectives.is_done(g, "obj_arena_bout")


def test_recruitment_objectives():
    u = Unit("player")
    g = Guild([u])
    assert not objectives.is_done(g, "obj_recruit_tavern")
    assert not objectives.is_done(g, "obj_recruit_prison")

    objectives.complete(g, "obj_recruit_tavern")
    assert objectives.is_done(g, "obj_recruit_tavern")
    assert "obj_recruit_tavern" in g.objectives_done

    objectives.complete(g, "obj_recruit_prison")
    assert objectives.is_done(g, "obj_recruit_prison")
    assert "obj_recruit_prison" in g.objectives_done


def test_objectives_persistence():
    from gartok import persist
    u = Unit("player")
    g = Guild([u], objectives_done=["obj_buy_food", "obj_combat_lv1"])
    payload = persist._payload(g, "current", "")
    assert "objectives_done" in payload
    assert payload["objectives_done"] == ["obj_buy_food", "obj_combat_lv1"]

    world = persist.new_world_id()
    try:
        persist.save_game(world, g)
        loaded = persist.load_game(world)
        assert loaded.objectives_done == ["obj_buy_food", "obj_combat_lv1"]
    finally:
        persist.delete_world(world)


def test_guild_screen_reputations_shows_objectives_card_first():
    import pygame
    from gartok.guild_screen import GuildScreen
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.font.init()
    u = Unit("player")
    g = Guild([u])
    fonts = ui_fonts()
    gs = GuildScreen(fonts, g, on_back=lambda: None)
    gs.tab = "reputations"

    surf = pygame.Surface((1280, 720))
    gs.draw(surf)
    assert gs._rep_scroll == 0


def test_market_buy_completes_objectives():
    from gartok import world
    from gartok.market_screen import MarketScreen
    u = Unit("player")
    u.give_to_pack("Copper Coin", 500)
    g = Guild([u])
    node = world.node("market")
    ms = MarketScreen(None, g, [u], node, lambda: None)

    assert "obj_buy_food" not in g.objectives_done
    assert "obj_buy_torch" not in g.objectives_done

    ms._buy(u, ["Meat"])
    assert "obj_buy_food" in g.objectives_done

    ms._buy(u, ["Torch"])
    assert "obj_buy_torch" in g.objectives_done


def test_the_axe_the_chain_asks_for_is_sold_at_the_smithy():
    from gartok import economy
    assert economy.shop_of(objectives.AXE) == "smith"


def test_state_objectives_follow_the_guild():
    from gartok import economy
    from gartok.animals import Animal
    from gartok.wagon import Wagon
    u, v = Unit("a"), Unit("b")
    g = Guild([u, v])
    ids = ("obj_work_shift", "obj_licence", "obj_mission", "obj_two_groups",
           "obj_strongbox", "obj_pack_animal", "obj_wagon", "obj_deed", "obj_initiation")
    assert not any(objectives.is_done(g, i) for i in ids)

    u.work_hours = 4
    g.licences.add("lumber_yard")
    g.missions.append(MagicMock())
    g.bank.capacity = economy.BANK_CHEST_CAPACITY
    cart, ox = Wagon("Cart"), Animal("Ox", tack="Harness")
    g.groups[0].wagons.append(cart)
    g.groups[0].herd.append(ox)
    assert not objectives.is_done(g, "obj_wagon")          # a wagon nothing pulls
    assert not objectives.is_done(g, "obj_pack_animal")    # a Harness pulls, it carries nothing
    ox.hitch = cart.uid
    g.groups[0].herd.append(Animal("Donkey", tack="Pack Saddle"))
    g.deeds_done.append("arena_dethrone")
    u.rite_progress["nature"] = 270
    u.magic_sources = [*u.magic_sources, "nature"]
    assert all(objectives.is_done(g, i) for i in ids if i != "obj_two_groups")


def test_two_groups_stays_done_once_banked():
    from gartok.group import Group
    u, v = Unit("a"), Unit("b")
    g = Guild([u, v])
    g.groups.append(Group([v], g.groups[0].node))
    g.groups[0].members.remove(v)
    assert "obj_two_groups" in objectives.check_and_bank(g)
    g.groups[0].members.append(v)
    g.groups.pop()
    assert objectives.is_done(g, "obj_two_groups")


def test_a_racial_magic_source_is_not_an_initiation():
    u = Unit("a")
    u.magic_sources = ["nature"]
    assert not objectives.is_done(Guild([u]), "obj_initiation")


def test_the_medic_marks_its_objective():
    from gartok import medic
    u = Unit("a")
    u.give_to_pack("Copper Coin", 500)
    g = Guild([u])
    u.hp = max(1, u.hp_max - 2)
    ok, _ = medic.treat(g, g.groups[0], [u])
    assert ok and "obj_medic" in g.objectives_done

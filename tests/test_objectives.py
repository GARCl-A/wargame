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
    assert card["rep"] == "0/7"
    assert card["rep_label"] == "done"
    assert len(card["deeds"]) == 7
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
    u.give_to_pack("Woodcutter's Axe")
    blurb2 = objectives._work_chain_blurb(g)
    assert "Step 2/3" in blurb2
    assert not objectives.is_done(g, "obj_work_chain")

    # Step 3: Work Lv 2 reached -> completed
    u.work_hours = progression.WORK_XP_THRESHOLDS[1] * economy.LUMBER_XP_HOURS
    assert objectives.is_done(g, "obj_work_chain")
    objectives.check_and_bank(g)
    assert "obj_work_chain" in g.objectives_done
    blurb3 = objectives._work_chain_blurb(g)
    assert "completed" in blurb3.lower()


def test_arena_bout_objective():
    u = Unit("player")
    g = Guild([u])
    assert not objectives.is_done(g, "obj_arena_bout")

    g.battles_won = 1
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

"""Missions: paid, time-boxed jobs, scoped to the accepting *unit* (not the
group it happened to be standing in -- see missions.py's module docstring) --
and the market's finite stock on a few items (economy.STOCK)."""

import random

from gartok import missions
from gartok.guild import Guild
from tests.helpers import Unit, economy


def _guild_with_two_groups():
    random.seed(1)
    hunters = [Unit("player") for _ in range(2)]
    stay_home = [Unit("player")]
    guild = Guild(hunters + stay_home)
    hunting_group, home_group = guild.split_group(guild.groups[0], hunters), guild.groups[0]
    return guild, hunting_group, home_group


def test_only_the_signers_current_groups_hides_count_toward_turn_in():
    guild, hunters, home = _guild_with_two_groups()
    signer = hunters.members[0]
    m = missions.accept(guild, signer, missions.TANNER_HIDES)

    home.members[0].give_to_pack("1sqm Hide")
    assert missions.progress(guild, m) == 0
    assert not missions.can_turn_in(guild, m)

    for _ in range(15):
        signer.give_to_pack("1sqm Hide")
    assert missions.progress(guild, m) == 15
    assert missions.can_turn_in(guild, m)


def test_mission_follows_its_signer_into_a_new_group_after_a_split():
    """The whole point of scoping to a unit, not a Group object: a group is
    reshuffled constantly, so the mission must survive the signer moving to a
    different one."""
    guild, hunters, home = _guild_with_two_groups()
    signer, other_hunter = hunters.members
    m = missions.accept(guild, signer, missions.TANNER_HIDES)

    # the signer splits off alone into a brand new group -- the old `hunters`
    # Group object no longer holds them (and may not even still exist).
    guild.reputation["arena"] = 3                      # fame for a third group slot
    solo = guild.split_group(hunters, [signer])
    signer_gold_before = signer.money
    other_hunter_gold_before = other_hunter.money
    for _ in range(15):
        signer.give_to_pack("1sqm Hide")

    assert missions.progress(guild, m) == 15          # still resolves via the unit
    missions.turn_in(guild, m)
    assert m.state == "done"
    assert signer.money == signer_gold_before + missions.TANNER_HIDES.reward  # solo: whole reward
    assert other_hunter.money == other_hunter_gold_before  # left behind, untouched


def test_turn_in_consumes_the_hides_and_splits_the_reward():
    guild, hunters, _home = _guild_with_two_groups()
    signer = hunters.members[0]
    m = missions.accept(guild, signer, missions.TANNER_HIDES)
    for _ in range(15):
        signer.give_to_pack("1sqm Hide")
    for u in hunters.members:
        u.money = 0

    missions.turn_in(guild, m)

    assert m.state == "done"
    assert signer._base_inventory.count("1sqm Hide") == 0
    assert sum(u.money for u in hunters.members) == missions.TANNER_HIDES.reward


def test_missed_deadline_fails_the_mission_and_it_is_not_offered_again():
    guild, hunters, home = _guild_with_two_groups()
    m = missions.accept(guild, hunters.members[0], missions.TANNER_HIDES)
    assert missions.TANNER_HIDES.id not in {t.id for t in missions.offers_at(guild, "city")}

    for u in guild.roster:                       # keep everyone fed -- not what's under test
        for _ in range(10):
            u.give_to_pack("Meat")

    guild.pass_time(24 * (missions.TANNER_HIDES.deadline_days + 1))

    assert m.state == "failed"
    assert missions.TANNER_HIDES.id not in {t.id for t in missions.offers_at(guild, "city")}


def test_signers_death_leaves_the_mission_unreachable():
    guild, hunters, home = _guild_with_two_groups()
    signer = hunters.members[0]
    m = missions.accept(guild, signer, missions.TANNER_HIDES)
    guild.remove_members([signer])
    assert missions.progress(guild, m) == 0
    assert not missions.can_turn_in(guild, m)


def test_market_stock_is_finite_for_scarce_items_and_unlimited_otherwise():
    random.seed(2)
    guild = Guild([Unit("player")])
    assert guild.market_stock["1sqm Hide"] == 0
    assert economy.stock_of(guild.market_stock, "Meat") is None   # never scarce


def test_apothecary_and_tanner_both_satisfy_bankers_good_for_business():
    # Test Tanner turn-in earns the deed
    guild1, hunters1, _ = _guild_with_two_groups()
    signer1 = hunters1.members[0]
    m1 = missions.accept(guild1, signer1, missions.TANNER_HIDES)
    for _ in range(15):
        signer1.give_to_pack("1sqm Hide")
    earned1 = missions.turn_in(guild1, m1)
    assert any(d.id == "bankers_good_for_business" for d in earned1)
    assert "bankers_good_for_business" in guild1.deeds_done

    # Test Apothecary turn-in also earns the deed
    guild2, hunters2, _ = _guild_with_two_groups()
    signer2 = hunters2.members[0]
    m2 = missions.accept(guild2, signer2, missions.APOTHECARY_MUSHROOMS)
    for _ in range(15):
        signer2.give_to_pack("Red Mushroom")
    earned2 = missions.turn_in(guild2, m2)
    assert any(d.id == "bankers_good_for_business" for d in earned2)
    assert "bankers_good_for_business" in guild2.deeds_done


def test_mission_template_tags_and_tag_back_compat():
    # Passed tags tuple
    t1 = missions.MissionTemplate(
        "t1", "giver", "city", "Test", "Blurb", "Item", 1, 10, 5,
        tags=("economic", "tanner"),
    )
    assert t1.tags == ("economic", "tanner")
    assert t1.tag == "economic"

    # Passed single tag kwarg
    t2 = missions.MissionTemplate(
        "t2", "giver", "city", "Test", "Blurb", "Item", 1, 10, 5,
        tag="economic",
    )
    assert t2.tags == ("economic",)
    assert t2.tag == "economic"

    # Passed positional string for tag/tags
    t3 = missions.MissionTemplate(
        "t3", "giver", "city", "Test", "Blurb", "Item", 1, 10, 5,
        "economic",
    )
    assert t3.tags == ("economic",)
    assert t3.tag == "economic"


def test_quest_panel_draws_tags_pills():
    import pygame
    pygame.font.init()
    from gartok.ui import quest_panel
    from gartok.ui.tokens import fonts as ui_fonts
    UI_F = ui_fonts()
    surf = pygame.Surface((800, 600))
    area = pygame.Rect(10, 10, 500, 400)
    quests = [{
        "name": "Fifteen Hides",
        "tags": ("economic", "tanner"),
        "accepted_by": "Adelio",
        "days_left": 4,
        "progress": (5, 15, "1sqm Hide"),
    }, {
        "name": "A Test of Trust",
        "tags": ("trust", "bankers"),
        "accepted_by": "Valdo",
        "days_left": 2,
        "progress": None,
    }]
    quest_panel.quest_list(surf, UI_F, area, quests)


def test_completed_mission_shows_completed_label():
    import pygame

    from gartok.tanner_screen import TannerScreen
    from gartok.ui.tokens import fonts as ui_fonts
    guild, hunters, _home = _guild_with_two_groups()
    signer = hunters.members[0]
    m = missions.accept(guild, signer, missions.TANNER_HIDES)
    for _ in range(15):
        signer.give_to_pack("1sqm Hide")
    missions.turn_in(guild, m)
    assert m.state == "done"

    hunters.node = "city"
    screen = TannerScreen(ui_fonts(), guild, hunters, None)
    assert screen._completed
    assert not screen._offered
    surf = pygame.Surface((800, 600))
    screen.draw(surf)


def test_mission_offer_screen_containment_and_notice():
    import pygame

    from gartok.library_mission_screen import LibraryMissionScreen
    from gartok.ui.tokens import fonts as ui_fonts

    guild, scholars, _home = _guild_with_two_groups()
    scholars.node = "library"
    done_called = False

    def on_done():
        nonlocal done_called
        done_called = True

    screen = LibraryMissionScreen(ui_fonts(), guild, scholars, on_done)
    surf = pygame.Surface((1280, 720))

    # 1. Draw fresh offer and verify all button bounds
    screen.draw(surf)
    accept_btn = next((r for k, r in screen.buttons if k == "accept"), None)
    leave_btn = next((r for k, r in screen.buttons if k == "done"), None)
    assert accept_btn is not None
    assert leave_btn is not None
    assert accept_btn.bottom < leave_btn.top

    # 2. Set notice (reproducing user's screenshot where notice pushed footer out)
    screen.notice = "paid out 250 copper, split across the group. · DEED · Library Initiate +1 reputation with The Library"
    screen.draw(surf)

    leave_btn_after = next((r for k, r in screen.buttons if k == "done"), None)
    assert leave_btn_after is not None
    # All buttons must be well within the screen surface and leave button must have clearance from bottom
    for _k, r in screen.buttons:
        assert r.top >= 0 and r.bottom <= 720, f"Button {_k} rect {r} out of bounds"

    # 3. Test handle_escape
    assert screen.handle_escape() is True
    assert done_called is True


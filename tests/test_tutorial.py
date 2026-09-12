"""The soft tutorial: TutorialState's dismiss/reopen/reset rules, the i18n
catalog backing every id a screen can hand back, and save/load round-tripping
the seen/enabled state by slot."""

import random

from gartok import i18n, persist
from gartok.tutorial import TUTORIALS, TutorialState
from tests.helpers import Unit


def test_every_registered_id_resolves_real_copy_not_the_key_itself():
    for tid in TUTORIALS:
        title = i18n.t(f"tutorial.{tid}.title")
        body = i18n.t(f"tutorial.{tid}.body")
        assert title != f"tutorial.{tid}.title", tid
        assert body != f"tutorial.{tid}.body", tid
        assert isinstance(body, list) and body, tid


def test_missing_key_falls_back_to_the_key_itself_not_a_crash():
    assert i18n.t("tutorial.does_not_exist.title") == "tutorial.does_not_exist.title"


def test_has_tells_a_real_string_apart_from_one_that_only_looks_like_its_key():
    assert i18n.has("tutorial.map.suggestion")            # map's card really has one
    assert not i18n.has("tutorial.squad.suggestion")       # squad's doesn't
    assert not i18n.has("tutorial.does_not_exist.title")


def test_stale_tutorial_rect_never_swallows_a_click_after_a_scene_swap():
    """A card/badge rect is only trusted for the exact scene it was drawn for
    -- guards `app.run()`'s once-per-frame rect cache against two events in
    one batch where the first one already swapped `self.scene`."""
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from gartok import tutorial_card
    from gartok.app import App

    app = App()
    app._new_game(0)                              # DraftScreen, phase "pick"
    draft = app.scene
    draft.mouse = (-1, -1)
    app.window.fill((0, 0, 0))
    draft.draw(app.window)
    app._tutorial_card_rect, app._tutorial_badge_rect = tutorial_card.draw(
        app.window, app.fonts, draft, app.tutorial)
    app._tutorial_rect_scene = draft
    stale_rect = app._tutorial_card_rect
    assert stale_rect is not None

    app._start_menu()                             # scene swaps mid-"batch"
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=stale_rect.center)
    assert app._tutorial_click(ev) is False


def test_footer_anchor_clears_a_footer_of_the_given_height():
    from gartok.screen import Screen
    s = Screen()
    size = (1600, 950)
    x, y, w, grow = s.footer_anchor(size, offset=52)
    assert grow == "up" and w > 0
    assert y <= 950 - 52          # never dips into the footer band it was told to clear
    x2, y2, w2, grow2 = s.footer_anchor(size, offset=44, margin=24, w=300)
    assert (x2, w2) == (24, 300) and y2 > y      # a shorter footer sits lower


def test_draft_screen_reports_one_id_per_phase():
    from gartok.draft_screen import DraftScreen
    ds = DraftScreen.__new__(DraftScreen)
    for phase, expected in (("pick", "draft.pick"), ("identity", "draft.identity"),
                            ("leader", "draft.leader")):
        ds.phase = phase
        assert ds.tutorial_key() == expected and expected in TUTORIALS


def test_map_screen_key_is_registered():
    from gartok.map_screen import MapScreen
    assert MapScreen.tutorial_key(MapScreen.__new__(MapScreen)) in TUTORIALS


def test_guild_screen_key_follows_the_active_tab():
    from gartok.guild_screen import GuildScreen
    gs = GuildScreen.__new__(GuildScreen)
    gs.tab = "members"
    gs.selected = []
    assert gs.tutorial_key() == "guild.members" and gs.tutorial_key() in TUTORIALS
    gs.tab = "reputations"
    assert gs.tutorial_key() == "guild.reputations" and gs.tutorial_key() in TUTORIALS


def test_every_simple_screen_reports_its_registered_id():
    """Screens whose `tutorial_key` is a flat constant (no tab/phase to read),
    checked without running their real `__init__` (bare `__new__` -- these
    methods touch no instance state)."""
    import gartok.bank_screen as bank_screen
    import gartok.battle_screen as battle_screen
    import gartok.gear_screen as gear_screen
    import gartok.hunt_screen as hunt_screen
    import gartok.level_screen as level_screen
    import gartok.loot_screen as loot_screen
    import gartok.market_screen as market_screen
    import gartok.reward_screen as reward_screen
    import gartok.squad_screen as squad_screen
    import gartok.taverna_screen as taverna_screen

    cases = [
        (squad_screen.SquadScreen, "squad"),
        (battle_screen.BattleScreen, "battle"),
        (loot_screen.LootScreen, "loot"),
        (reward_screen.RewardScreen, "reward"),
        (market_screen.MarketScreen, "market"),
        (taverna_screen.TavernaScreen, "taverna"),
        (hunt_screen.HuntScreen, "hunt"),
        (bank_screen.BankScreen, "bank"),
        (gear_screen.GearScreen, "gear"),
        (level_screen.LevelScreen, "level"),
    ]
    for cls, expected in cases:
        assert cls.tutorial_key(cls.__new__(cls)) == expected, cls.__name__
        assert expected in TUTORIALS, cls.__name__


def test_every_anchor_returns_a_valid_grow_direction():
    """`tutorial_anchor` must hand back `(x, y, w, grow)` with grow in
    {"up", "down"} -- `app.py`'s `tutorial_card.draw` trusts this blindly."""
    from gartok.battle_screen import BattleScreen
    from gartok.draft_screen import DraftScreen
    from gartok.guild_screen import GuildScreen
    from gartok.map_screen import MapScreen

    size = (1600, 950)
    bs = BattleScreen.__new__(BattleScreen)
    gs = GuildScreen.__new__(GuildScreen)
    ms = MapScreen.__new__(MapScreen)
    ds = DraftScreen.__new__(DraftScreen)

    for scene in (bs, ms):
        x, y, w, grow = scene.tutorial_anchor(size)
        assert grow in ("up", "down") and w > 0

    for tab in ("members", "reputations"):
        gs.tab = tab
        x, y, w, grow = gs.tutorial_anchor(size)
        assert grow in ("up", "down") and w > 0

    for phase in ("pick", "identity", "leader"):
        ds.phase = phase
        x, y, w, grow = ds.tutorial_anchor(size)
        assert grow in ("up", "down") and w > 0


def test_should_show_tracks_seen_enabled_and_a_forced_reopen():
    st = TutorialState()
    assert st.should_show("map")             # never seen -> show
    st.dismiss("map")
    assert not st.should_show("map")         # seen -> stays hidden
    st.reopen("map")
    assert st.should_show("map")             # badge click forces it back...
    st.dismiss("map")
    assert not st.should_show("map")         # ...and dismissing un-forces it
    st.enabled = False
    st.seen.clear()
    assert not st.should_show("map")         # disabled wins even over "never seen"


def test_reset_clears_seen_and_any_forced_reopen():
    st = TutorialState(seen={"map", "guild.members"})
    st.reopen("guild.reputations")
    st.reset()
    assert st.seen == set() and st.showing is None
    assert st.should_show("map")


def test_save_round_trips_tutorial_state_by_slot():
    slot = 97
    random.seed(11)
    guild_before = persist.Guild([Unit("player")], node="city")
    guild_before.tutorial.dismiss("draft.pick")
    guild_before.tutorial.dismiss("map")
    guild_before.tutorial.enabled = False
    persist.save_game(slot, guild_before)
    try:
        loaded = persist.load_game(slot)
        assert loaded.tutorial.seen == {"draft.pick", "map"}
        assert loaded.tutorial.enabled is False
    finally:
        persist.delete_slot(slot)


def test_a_pre_tutorial_save_loads_as_unseen_and_enabled():
    slot = 98
    random.seed(12)
    guild = persist.Guild([Unit("player")], node="city")
    persist.save_game(slot, guild)
    path = persist.slot_path(slot)
    import json
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    del payload["tutorial_seen"]
    del payload["tutorial_enabled"]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    try:
        loaded = persist.load_game(slot)
        assert loaded.tutorial.seen == set() and loaded.tutorial.enabled is True
    finally:
        persist.delete_slot(slot)

"""The tutorial: TutorialState's dismiss/reopen/reset rules, the i18n
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
    app._new_game()                              # DraftScreen, phase "pick"
    draft = app.scene
    draft.mouse = (-1, -1)
    app.window.fill((0, 0, 0))
    draft.draw(app.window)
    app._tutorial_card_rect, app._tutorial_badge_rect = tutorial_card.draw(
        app.window, app.ui_fonts, draft, app.tutorial)
    app._tutorial_rect_scene = draft
    stale_rect = app._tutorial_card_rect
    assert stale_rect is not None

    app._start_menu()                             # scene swaps mid-"batch"
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=stale_rect.center)
    assert app._tutorial_click(ev) is False


def test_draft_screen_reports_one_id_per_phase():
    from gartok.draft_screen import DraftScreen
    ds = DraftScreen.__new__(DraftScreen)
    ds.picks = []
    ds.tutorial = TutorialState(seen={"draft.intro"})
    for phase, expected in (("pick", "draft.pick"), ("identity", "draft.identity")):
        ds.phase = phase
        assert ds.tutorial_key() == expected and expected in TUTORIALS


def test_map_screen_reports_its_card_and_reuses_the_command_bar_help_button():
    """The COMMAND bar already draws a "?" top-right, so the map's reopen badge
    sits exactly on it instead of in a second corner."""
    import pygame

    from gartok.map_screen import MapScreen
    ms = MapScreen.__new__(MapScreen)
    ms._help_rect = pygame.Rect(1100, 20, 32, 32)
    assert ms.tutorial_key() == "map" and "map" in TUTORIALS
    assert ms.tutorial_badge_rect((1212, 832)) == ms._help_rect


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
    from gartok import (
        bank_screen,
        battle_screen,
        hunt_screen,
        city_property_screen,
        crafting_screen,
        group_screen,
        justice_screen,
        ledger_screen,
        level_screen,
        loot_screen,
        market_screen,
        prison_screen,
        reward_screen,
        squad_screen,
        taverna_screen,
        tanner_screen,
        trust_screen,
        wilds_claim_screen,
    )

    cases = [
        (squad_screen.SquadScreen, "squad"),
        (battle_screen.BattleScreen, "battle"),
        (loot_screen.LootScreen, "loot"),
        (reward_screen.RewardScreen, "reward"),
        (market_screen.MarketScreen, "market"),
        (taverna_screen.TavernaScreen, "taverna"),
        (hunt_screen.HuntScreen, "hunt"),
        (bank_screen.BankScreen, "bank"),
        (level_screen.LevelScreen, "level"),
        (group_screen.GroupScreen, "group"),
        (tanner_screen.TannerScreen, "missions"),
        (trust_screen.TrustScreen, "trust"),
        (ledger_screen.LedgerScreen, "ledger"),
        (crafting_screen.CraftingScreen, "craft"),
        (city_property_screen.CityPropertyScreen, "property"),
        (wilds_claim_screen.WildsClaimScreen, "claim"),
        (justice_screen.GuardScreen, "guard"),
        (prison_screen.PrisonScreen, "prison"),
    ]
    for cls, expected in cases:
        assert cls.tutorial_key(cls.__new__(cls)) == expected, cls.__name__
        assert expected in TUTORIALS, cls.__name__


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
        persist.delete_world(slot)


def test_guild_screen_tabs_and_badge_are_on_same_line_without_overlap():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.guild import Guild
    from gartok.guild_screen import GuildScreen
    from gartok.ui.tokens import fonts as ui_fonts
    from gartok.ui.tokens import T

    pygame.init()
    g = Guild([Unit("Alice"), Unit("Bob")], node="city")
    gs = GuildScreen(ui_fonts(), g, on_back=lambda: None)
    W, H = 1280, 800
    surf = pygame.Surface((W, H))
    gs.draw(surf)

    badge_rect = gs.tutorial_badge_rect((W, H))
    assert badge_rect.width == 28 and badge_rect.height == 28

    # Ensure tabs do not collide with tutorial badge
    for rect, key in gs.tab_hits:
        assert not rect.colliderect(badge_rect), f"Tab {key} collided with tutorial badge"
        assert rect.top == badge_rect.top, f"Tab {key} top {rect.top} != badge top {badge_rect.top}"

    # REPUTATIONS should be immediately to the left of the badge, separated by T.S
    rep_rect = next(r for r, k in gs.tab_hits if k == "reputations")
    assert rep_rect.right + T.S == badge_rect.left


def test_tutorial_badge_rect_queried_by_tutorial_card():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok import tutorial_card
    from gartok.screen import Screen
    from gartok.ui.tokens import fonts as ui_fonts

    class CustomScreen(Screen):
        def tutorial_key(self):
            return "map"

        def tutorial_badge_rect(self, size):
            return pygame.Rect(100, 200, 28, 28)

    pygame.init()
    surf = pygame.Surface((800, 600))
    cs = CustomScreen()
    st = TutorialState()
    st.dismiss("map")

    _, badge_rect = tutorial_card.draw(surf, ui_fonts(), cs, st)
    assert badge_rect == pygame.Rect(100, 200, 28, 28)


def test_header_reserves_space_when_has_tutorial_is_true():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.ui.primitives import header
    from gartok.ui.tokens import T
    from gartok.ui.tokens import fonts as ui_fonts

    pygame.init()
    F = ui_fonts()
    surf = pygame.Surface((1000, 600))
    head_rect = pygame.Rect(0, 0, 1000, 72)

    tabs_normal = header(surf, F, head_rect, "Title", "Sub", ("gear", "quests"), "gear", has_tutorial=False)
    tabs_tut = header(surf, F, head_rect, "Title", "Sub", ("gear", "quests"), "gear", has_tutorial=True)

    # The rightmost tab with tutorial should be shifted left by 28 + T.S
    assert tabs_tut["quests"].right == tabs_normal["quests"].right - (28 + T.S)


def test_draft_screen_buttons_clear_tutorial_badge():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok.draft_screen import DraftScreen
    from gartok.ui.tokens import T
    from gartok.ui.tokens import fonts as ui_fonts

    pygame.init()
    F = ui_fonts()
    ds = DraftScreen(F, lambda *args: None)
    W, H = 1280, 800
    surf = pygame.Surface((W, H))
    ds.draw(surf)

    badge_rect = ds.tutorial_badge_rect((W, H))
    assert badge_rect.width == 28 and badge_rect.height == 28
    assert badge_rect.right == W - T.S * 4
    assert badge_rect.top == T.S * 4

    # Commission button should be aligned on the same top line and height as the tutorial badge
    assert ds.commission_btn_rect.top == badge_rect.top
    assert ds.commission_btn_rect.height == badge_rect.height

    # Commission button should be immediately to the left of the badge, separated by T.S
    assert ds.commission_btn_rect.right + T.S == badge_rect.left
    assert not ds.commission_btn_rect.colliderect(badge_rect)


def test_all_tutorial_screens_have_aligned_badge_rect():
    import pygame

    from gartok.hunt_screen import HuntScreen
    from gartok.loot_screen import LootScreen
    from gartok.reward_screen import RewardScreen
    from gartok.squad_screen import SquadScreen
    from gartok.taverna_screen import TavernaScreen
    from gartok.ui.tokens import T

    W, H = 1280, 800
    tav = TavernaScreen.__new__(TavernaScreen)
    rew = RewardScreen.__new__(RewardScreen)
    loot = LootScreen.__new__(LootScreen)
    hunt = HuntScreen.__new__(HuntScreen)
    squad = SquadScreen.__new__(SquadScreen)

    assert tav.tutorial_badge_rect((W, H)) == pygame.Rect(W - T.S * 3 - 28, T.S * 2, 28, 28)
    assert rew.tutorial_badge_rect((W, H)) == pygame.Rect(W - T.S * 3 - 28, T.S * 2, 28, 28)
    assert loot.tutorial_badge_rect((W, H)) == pygame.Rect(W - T.S * 4 - 28, T.S * 4, 28, 28)
    assert hunt.tutorial_badge_rect((W, H)) == pygame.Rect(W - T.S * 3 - 28, T.S * 3 - 4, 28, 28)
    assert squad.tutorial_badge_rect((W, H)) == pygame.Rect(W - 16 - 28, 16 - 4, 28, 28)
    assert squad.tutorial_badge_rect((1600, 900)) == pygame.Rect(1600 - 24 - 28, 24 - 4, 28, 28)


def test_draft_opens_on_the_intro_card_once():
    from gartok.draft_screen import DraftScreen
    ds = DraftScreen.__new__(DraftScreen)
    ds.phase, ds.picks, ds.tutorial = "pick", [], TutorialState()
    assert ds.tutorial_key() == "draft.intro"
    ds.tutorial.dismiss("draft.intro")
    assert ds.tutorial_key() == "draft.pick"
    ds.tutorial.reset()
    ds.picks = ["a"]                                  # mid-draft: a reset never re-pops the intro
    assert ds.tutorial_key() == "draft.pick"


def _hero_app():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok import tutorial_card
    from gartok.app import App

    app = App()
    app._new_game()
    app.scene.mouse = (-1, -1)
    app.window.fill((0, 0, 0))
    app.scene.draw(app.window)
    app._tutorial_card_rect, app._tutorial_badge_rect = tutorial_card.draw(
        app.window, app.ui_fonts, app.scene, app.tutorial)
    app._tutorial_rect_scene = app.scene
    return app, pygame


def test_intro_card_swallows_everything_and_a_click_dismisses_it():
    app, pygame = _hero_app()
    assert app.scene.tutorial_key() == "draft.intro"
    down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5))   # outside the card
    key = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)
    assert app._tutorial_swallow(key) is True
    assert "draft.intro" not in app.tutorial.seen
    assert app._tutorial_swallow(down) is True
    assert "draft.intro" in app.tutorial.seen


def test_closing_a_card_never_reaches_the_screen_underneath():
    app, pygame = _hero_app()
    down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5))
    up = pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(5, 5))
    app._tutorial_swallow(down)
    assert app._tutorial_swallow(up) is True                  # the dismissing press's release
    assert app._tutorial_swallow(down) is True                # a quick second click: debounced
    app._tutorial_block_until = 0
    assert app._tutorial_swallow(down) is True                # the next card (draft.pick) is up
    app.tutorial.seen.add("draft.pick")
    app._tutorial_block_until = 0
    assert app._tutorial_swallow(down) is False               # no card left: clicks flow again


def test_intro_card_dismisses_on_enter_and_lets_escape_through():
    app, pygame = _hero_app()
    esc = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    assert app._tutorial_swallow(esc) is True                 # swallowed here, but `run` handles Esc first
    enter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    assert app._tutorial_swallow(enter) is True
    assert "draft.intro" in app.tutorial.seen


def test_hubs_show_the_card_of_the_tab_they_are_on():
    from gartok.apothecary_hub_screen import ApothecaryHubScreen
    from gartok.bank_hub_screen import BankHubScreen
    from gartok.library_hub_screen import LibraryHubScreen

    class _Tab:
        def __init__(self, key):
            self.key = key

        def tutorial_key(self):
            return self.key

    for cls in (BankHubScreen, LibraryHubScreen, ApothecaryHubScreen):
        hub = cls.__new__(cls)
        hub.active_screen = lambda: _Tab("bank")
        assert hub.tutorial_key() == "bank"


def test_no_registered_card_is_orphaned():
    """Every id must be returned by some screen -- the map's card once sat
    registered and never showed. `guild.*` and `draft.*` ids are picked per tab/phase
    and covered by their own tests."""
    import pathlib
    files = [p for p in pathlib.Path("gartok").rglob("*.py") if p.name != "tutorial.py"]
    src = "".join(p.read_text(encoding="utf-8") for p in files)
    for tid in TUTORIALS:
        if not tid.startswith(("guild.", "draft.")):
            assert f'return "{tid}"' in src, tid

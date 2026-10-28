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
    assert i18n.has("tutorial.work.suggestion")           # work's card really has one
    assert not i18n.has("tutorial.squad.suggestion")       # squad's doesn't
    assert not i18n.has("tutorial.does_not_exist.title")




def test_guild_screen_key_follows_the_active_tab():
    from gartok.guild_screen import GuildScreen
    gs = GuildScreen.__new__(GuildScreen)
    gs.tab = "members"
    gs.selected = []
    assert gs.tutorial_key() == "guild.members" and gs.tutorial_key() in TUTORIALS
    gs.tab = "reputations"
    assert gs.tutorial_key() == "guild.reputations" and gs.tutorial_key() in TUTORIALS


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
    from gartok.ui.tokens import T
    from gartok.ui.tokens import fonts as ui_fonts

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






def test_no_registered_card_is_orphaned():
    """Every id must be named by some screen -- the map's card once sat registered and never showed.
    `guild.*` and `draft.*` ids are picked per tab/phase and covered by their own tests; `group_turn`
    waits for its browser screen."""
    import pathlib
    files = [p for p in pathlib.Path("gartok").rglob("*.py") if p.name != "tutorial.py"]
    src = "".join(p.read_text(encoding="utf-8") for p in files)
    for tid in TUTORIALS:
        if not tid.startswith(("guild.", "draft.")) and tid != "group_turn":
            assert f'"{tid}"' in src, tid

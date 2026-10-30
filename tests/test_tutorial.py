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


def test_no_registered_card_is_orphaned():
    """Every id must be named by some screen -- the map's card once sat registered and never showed.
    `guild.*` and `draft.*` ids are picked per tab/phase and covered by their own tests."""
    import pathlib
    files = [p for p in pathlib.Path("gartok").rglob("*.py") if p.name != "tutorial.py"]
    src = "".join(p.read_text(encoding="utf-8") for p in files)
    for tid in TUTORIALS:
        if not tid.startswith(("guild.", "draft.")):
            assert f'"{tid}"' in src, tid

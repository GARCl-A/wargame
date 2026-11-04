"""The map's side of a routine: a stopped one shows on its band's card and CONTINUE ROUTINE runs it again."""

import pytest

from gartok import gather
from gartok import routines as r
from gartok.web.map_session import MapSession
from tests.test_web_hub import _guild


def _stopped():
    """A band at the lumber yard whose routine stopped on a gather nobody carries the tool for."""
    guild = _guild("lumber_yard")
    g = guild.groups[0]
    r.assign(guild, g, r.Routine([r.Gather(8)]))
    return guild, g, MapSession(guild)


def _card(session, g):
    return next(b for b in session.state()["groups"] if b["gid"] == g.gid)


def test_a_stopped_routine_shows_on_the_band_card_with_a_continue_button():
    _, g, session = _stopped()
    card = _card(session, g)
    assert card["chip"] == "Routine stopped" and card["tone"] == "bad" and "carries" in card["detail"]
    keys = [b.get("key") for b in card["inspector"]["blocks"]]
    assert "continue_routine" in keys


def test_continue_runs_the_block_the_routine_stopped_on_again():
    _, g, session = _stopped()
    for u in g.members:
        u.give_to_pack(gather.tool("lumber_yard"))
    session.act(g.gid, "continue_routine")
    assert g.routine is None and g.members[0].count_of("Lumber") + g.members[1].count_of("Lumber") > 0


def test_continue_stops_again_when_the_cause_is_still_there():
    _, g, session = _stopped()
    session.act(g.gid, "continue_routine")
    assert g.routine.paused and g.order is None


def test_continue_needs_a_stopped_routine():
    guild = _guild("city")
    session = MapSession(guild)
    with pytest.raises(ValueError, match="no stopped routine"):
        session.act(guild.groups[0].gid, "continue_routine")

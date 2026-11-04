"""The Book of routines: automation seats come from fame, none to start with."""

import pytest

from gartok import routine_book as book
from gartok import routines as r
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import standard_unit


def _guild(*nodes):
    groups = [Group([standard_unit()], node=node, name=f"Band {i}") for i, node in enumerate(nodes)]
    return Guild(None, groups=groups, clock=Clock(6 * 3600))


def test_a_new_guild_has_no_automation_seat():
    guild = _guild("city")
    assert book.slots(guild) == 0 and book.used(guild) == 0
    with pytest.raises(ValueError, match="no free automation slot"):
        book.assign(guild, guild.groups[0], r.Routine([r.Rest(1)]))
    assert guild.groups[0].routine is None


def test_every_fame_step_opens_one_seat():
    guild = _guild("city")
    assert book.fame_to_next_slot(guild) == book.FAME_PER_SLOT
    guild.reputation["arena"] = book.FAME_PER_SLOT * 2 + 1
    assert book.slots(guild) == 2 and book.fame_to_next_slot(guild) == book.FAME_PER_SLOT - 1


def test_a_group_on_a_routine_takes_a_seat_and_the_seats_run_out():
    guild = _guild("city", "city", "city")
    guild.reputation["arena"] = book.FAME_PER_SLOT * 2
    a, b, c = guild.groups
    book.assign(guild, a, r.Routine([r.Rest(1)]))
    book.assign(guild, b, r.Routine([r.Rest(1)]))
    assert book.used(guild) == 2
    with pytest.raises(ValueError, match="no free automation slot"):
        book.assign(guild, c, r.Routine([r.Rest(1)]))


def test_a_stopped_routine_keeps_its_seat_and_a_finished_one_frees_it():
    guild = _guild("city")
    guild.reputation["arena"] = book.FAME_PER_SLOT
    g = guild.groups[0]
    book.assign(guild, g, r.Routine([r.Trade(sell=("Lumber",))]))
    assert g.routine.paused and book.used(guild) == 1
    g.routine = None
    book.assign(guild, g, r.Routine([r.Wait(r.coins(r.own()) >= 0)]))
    assert g.routine is None and book.used(guild) == 0


def test_replacing_the_routine_of_a_group_needs_no_second_seat():
    guild = _guild("city")
    guild.reputation["arena"] = book.FAME_PER_SLOT
    g = guild.groups[0]
    book.assign(guild, g, r.Routine([r.Trade(sell=("Lumber",))]))
    book.assign(guild, g, r.Routine([r.Rest(1)]))
    assert g.routine.blocks == (r.Rest(1),) and book.used(guild) == 1

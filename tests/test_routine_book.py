"""The Book of routines: automation seats come from fame, none to start with."""

import pytest

from gartok import persist
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


def _poc_blocks():
    mill = r.group("Gatherers")
    trader = (r.Repeat(r.coins(r.own()) < 500, [
        r.Wait(r.items(mill, "Lumber") >= 8),
        r.Take(mill, "Lumber"),
        r.Travel("farm"),
        r.Trade(sell=("Lumber",), buy=(("Potato", 3),), food_days=3),
        r.Travel("lumber_yard"),
        r.HandOver(mill, "Potato", 3),
    ]),)
    gatherer = (r.Repeat(r.coins(r.group("Trader")) >= 500, [r.Gather(16)], until=True),)
    return trader, gatherer


def test_the_proof_of_concept_routines_pass_the_check():
    guild = _guild("city")
    for blocks in _poc_blocks():
        book.check(guild, blocks)


@pytest.mark.parametrize("block, message", [
    (r.Travel("nowhere"), "unknown place"),
    (r.Gather(0), "hours"),
    (r.Craft("Nothing", 8), "unknown recipe"),
    (r.Wait(r.items(r.own(), "Moonbeam") >= 1), "unknown item"),
    (r.Wait(r.Cond("coins", r.own(), None, "==", 1)), "unknown condition"),
    (r.Take(r.own(), "Lumber"), "another group"),
    (r.HandOver(r.Ref("named", None), "Lumber"), "name the group"),
    (r.HandOver(r.group("B"), "Lumber", 0), "at least 1"),
    (r.Trade(sell=("Moonbeam",)), "unknown item"),
    (r.Trade(food_days=-1), "below zero"),
    (r.Repeat(r.coins(r.own()) < 1, [r.Travel("nowhere")]), "unknown place"),
])
def test_the_check_refuses_what_names_something_that_does_not_exist(block, message):
    with pytest.raises(ValueError, match=message):
        book.check(_guild("city"), (block,))


def test_a_page_is_written_saved_renamed_and_torn():
    guild = _guild("city")
    i = book.write(guild, "  Potato   trader ")
    assert guild.routine_pages[i].name == "Potato trader"
    trader, _ = _poc_blocks()
    book.save(guild, i, "Trader", "a note", r.dump(trader))
    assert guild.routine_pages[i].blocks == trader and guild.routine_pages[i].note == "a note"
    book.tear(guild, i)
    assert guild.routine_pages == []


def test_a_page_needs_its_own_name():
    guild = _guild("city")
    book.write(guild, "A")
    with pytest.raises(ValueError, match="needs a name"):
        book.write(guild, "   ")
    with pytest.raises(ValueError, match="already a routine called A"):
        book.write(guild, "A")


def test_a_refused_save_leaves_the_page_as_it_was():
    guild = _guild("city")
    i = book.write(guild, "A")
    with pytest.raises(ValueError, match="unknown place"):
        book.save(guild, i, "B", "", r.dump((r.Travel("nowhere"),)))
    with pytest.raises(ValueError, match="not well formed"):
        book.save(guild, i, "B", "", [{"_": "Nope"}])
    with pytest.raises(ValueError, match="not well formed"):
        book.save(guild, i, "B", "", [{"_": "Gather", "hours": "many"}])
    assert guild.routine_pages[0].name == "A" and guild.routine_pages[0].blocks == ()


def test_the_written_routines_survive_a_save():
    guild = _guild("city")
    trader, gatherer = _poc_blocks()
    book.save(guild, book.write(guild, "Trader"), "Trader", "carries", r.dump(trader))
    book.save(guild, book.write(guild, "Gatherer"), "Gatherer", "", r.dump(gatherer))
    world_id = persist.new_world_id()
    persist.save_game(world_id, guild)
    loaded = persist.load_game(world_id)
    assert [(p.name, p.note, p.blocks) for p in loaded.routine_pages] == [("Trader", "carries", trader), ("Gatherer", "", gatherer)]


def test_a_group_is_given_a_copy_that_its_own_edits_never_touch():
    guild = _guild("city")
    guild.reputation["arena"] = book.FAME_PER_SLOT
    guild.routine_pages.append(book.Page("Walker", (r.Rest(8), r.Travel("farm")), "a note"))
    group = guild.groups[0]
    book.equip(guild, group, 0)
    assert group.routine.name == "Walker" and group.routine.note == "a note" and group.order is not None
    book.adjust(guild, group, r.dump((r.Rest(2),)))
    assert group.routine.blocks == (r.Rest(2),) and guild.routine_pages[0].blocks == (r.Rest(8), r.Travel("farm"))


def test_equipping_needs_a_free_seat_and_a_group_without_a_routine():
    guild = _guild("city")
    guild.routine_pages.append(book.Page("Walker", (r.Rest(8),)))
    with pytest.raises(ValueError, match="no free automation slot"):
        book.equip(guild, guild.groups[0], 0)
    guild.reputation["arena"] = book.FAME_PER_SLOT
    book.equip(guild, guild.groups[0], 0)
    with pytest.raises(ValueError, match="already has a routine"):
        book.equip(guild, guild.groups[0], 0)


def test_adjusting_keeps_the_pointer_when_the_block_is_still_there_and_starts_over_when_not():
    guild = _guild("city")
    guild.reputation["arena"] = book.FAME_PER_SLOT
    group = guild.groups[0]
    book.assign(guild, group, r.Routine([r.Rest(1), r.Rest(2), r.Rest(3)], path=[2]))
    book.adjust(guild, group, r.dump((r.Rest(1), r.Rest(2), r.Rest(9))))
    assert group.routine.path == [2]
    book.adjust(guild, group, r.dump((r.Rest(1),)))
    assert group.routine.path == [0]
    with pytest.raises(ValueError, match="unknown place"):
        book.adjust(guild, group, r.dump((r.Travel("nowhere"),)))
    assert group.routine.blocks == (r.Rest(1),)


def test_taking_off_and_saving_back_to_the_book():
    guild = _guild("city")
    guild.reputation["arena"] = book.FAME_PER_SLOT
    guild.routine_pages.append(book.Page("Walker", (r.Rest(8),)))
    group = guild.groups[0]
    book.equip(guild, group, 0)
    book.adjust(guild, group, r.dump((r.Rest(3),)))
    assert book.save_back(guild, group) == 1
    assert [p.name for p in guild.routine_pages] == ["Walker", "Walker 2"]
    assert guild.routine_pages[1].blocks == (r.Rest(3),) and guild.routine_pages[0].blocks == (r.Rest(8),)
    book.take_off(group)
    assert group.routine is None and book.used(guild) == 0


def test_a_copy_travels_in_the_save_with_its_name():
    guild = _guild("city")
    guild.reputation["arena"] = book.FAME_PER_SLOT
    guild.routine_pages.append(book.Page("Walker", (r.Rest(8),), "n"))
    book.equip(guild, guild.groups[0], 0)
    d = r.dump(guild.groups[0].routine)
    back = r.load(d)
    assert (back.name, back.note) == ("Walker", "n")
    assert r.load({k: v for k, v in d.items() if k not in ("name", "note")}).name == ""

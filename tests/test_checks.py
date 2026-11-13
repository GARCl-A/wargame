"""The checks a player's order rolls outside a fight (`checks.py`): one per roll, drained once, never saved."""
from gartok import checks, chest, data, items, persist
from gartok.guild import Guild
from tests.helpers import fixed_d20, standard_unit


def _guild():
    return Guild([standard_unit()], node="market")


def test_a_lock_picked_puts_one_check():
    guild = _guild()
    unit = guild.roster[0]
    unit.give_to_pack(items.BOX_OF_GEMS_ITEM)
    with fixed_d20(17):
        chest.try_open(unit, guild=guild)
    assert len(guild.table) == 1
    c = guild.table[0]
    assert (c.nat, c.mod, c.dc) == (17, unit.mod_dexterity, data.CHEST_DC)
    assert c.ok == (17 + unit.mod_dexterity >= data.CHEST_DC)


def test_a_roll_without_a_guild_puts_nothing():
    unit = standard_unit()
    with fixed_d20(10):
        chest.roll_lock(unit)


def test_drain_hands_the_records_over_once():
    guild = _guild()
    checks.put(guild, checks.Check("Ann", 20, 2, 22, 12, True, "picks the lock"))
    checks.put(guild, checks.Check("Bo", 1, 2, 3, 12, False, "picks the lock", (9, 11)))
    out = checks.drain(guild)
    assert [r["outcome"] for r in out] == ["crit", "fumble"]
    assert out[1]["vs"] == "contest" and out[1]["theirs"] == {"nat": 9, "total": 11}
    assert out[0]["actor"] is None and out[0]["label"] == "Ann picks the lock"
    assert guild.table == [] and checks.drain(guild) == []


def test_the_table_is_capped_and_not_saved():
    guild = _guild()
    for i in range(checks.TABLE_CAP + 9):
        checks.put(guild, checks.Check("A", i, 0, i, 10, True, "x"))
    assert len(guild.table) == checks.TABLE_CAP
    assert "table" not in persist._payload(guild, "current", "")


def test_the_web_answer_drains_the_table_of_the_open_screen():
    from types import SimpleNamespace
    from gartok.web import server
    guild = _guild()
    checks.put(guild, checks.Check("Ann", 12, 1, 13, 10, True, "picks the lock"))
    over_the_map = SimpleNamespace(map=SimpleNamespace(guild=guild))
    assert len(server._table(over_the_map)) == 1
    assert server._table(over_the_map) == [] and server._table(SimpleNamespace()) == []


def test_an_ask_around_hour_puts_its_check():
    from gartok import investigation
    guild = _guild()
    group = guild.groups[0]
    job, node = next((j, n) for j, nodes in investigation.CLUES.items() for n in nodes)
    group.node = node
    with fixed_d20(15):
        investigation.ask(guild, group, job)
    (c,) = guild.table
    assert c.nat == 15 and c.dc == investigation.GATHER_DC


def test_the_ruins_search_puts_its_check():
    from gartok import campaign
    from gartok.group import Group
    guild = _guild()
    with fixed_d20(11):
        campaign.scout_ancient_ruins(guild, Group([guild.roster[0]], "market"))
    (c,) = guild.table
    assert c.nat == 11 and c.dc == 12 and c.label

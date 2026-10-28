"""The three hidden sanctuaries: revealed by the Library's Codex turn-in, each takes
the Codex for its school, and only one ever can."""


from gartok import data, factions, job_board, missions, world
from gartok.guild import Guild
from gartok.web.hub_session import tabs_for
from tests.helpers import Unit

SHRINES = ("blood_sanctuary", "nature_grove", "faith_cathedral")


def _library_done():
    u = Unit("player")
    guild = Guild([u], node="library")
    guild.deeds_done.append("library_initiate")
    missions.accept(guild, u, missions.LIBRARY_DICTIONARY).state = "done"
    m = missions.accept(guild, u, missions.LIBRARY_ANCIENT_CODEX)
    u.give_to_pack(data.CODEX_ITEM)
    missions.turn_in(guild, m)
    return guild, u


def _codex_offers(guild, node):
    return [t for t in missions.offers_at(guild, node) if "codex" in t.tags]


def test_shrines_are_hidden_until_the_codex_is_turned_in():
    guild = Guild([Unit("player")], node="city")
    known = {n.id for n in world.known(guild)}
    assert not known & set(SHRINES)
    assert not any(missions.offers_at(guild, s) for s in SHRINES)
    guild, _u = _library_done()
    assert set(SHRINES) <= {n.id for n in world.known(guild)}
    assert {t.node for t in missions.offers_at(guild, "library")} <= {"library"}


def test_every_shrine_is_wired_into_the_graph():
    for s in SHRINES:
        assert world.node(s).hidden and world.node(s).has("shrine")
        assert world.neighbors(s)


def test_each_shrine_offers_its_own_codex_delivery_once_the_library_is_done():
    guild, _u = _library_done()
    for s, t in zip(SHRINES, missions.CODEX_DELIVERIES, strict=True):
        assert _codex_offers(guild, s) == [t]


def test_delivering_to_one_school_closes_the_other_two():
    guild, u = _library_done()
    m = missions.accept(guild, u, missions.CODEX_NATURE)
    assert missions.can_turn_in(guild, m)
    earned = missions.turn_in(guild, m)
    assert [d.id for d in earned] == ["nature_codex"]
    assert guild.reputation["nature_coven"] == 1
    assert not u.has_item(data.CODEX_ITEM)
    assert not _codex_offers(guild, "blood_sanctuary")
    assert not _codex_offers(guild, "faith_cathedral")
    assert missions.closed(guild, missions.CODEX_BLOOD) and missions.closed(guild, missions.CODEX_FAITH)
    assert "blood_codex" not in guild.deeds_done and "faith_codex" not in guild.deeds_done


def test_a_deed_for_another_school_cannot_fire_after_the_first():
    guild, _u = _library_done()
    guild.deeds_done.append("faith_codex")
    event = factions.Event("mission", tags=("magic", "blood", "codex"), tag="magic")
    assert factions.settle(guild, event) == []


def test_the_shrine_board_lists_its_job_and_hands_the_codex_over():
    guild, u = _library_done()
    group = guild.groups[0]
    group.node = "blood_sanctuary"
    board = job_board.ShrineBoard(guild, group)
    codex = missions.TEMPLATES["blood_codex"]
    assert codex in board.get_templates()
    assert board.accept(codex) and board.turn_in(codex)
    assert "blood_codex" in guild.deeds_done
    assert "The Codex Delivered" in board.notice


def test_the_hub_for_a_shrine_node_opens_on_its_job_board_beside_the_initiation():
    assert [k for k, _label in tabs_for("shrine", world.node("faith_cathedral"))] == ["jobs", "initiation"]
    assert world.vendor("faith_cathedral", "shrine").name == "Brother Quillon"


def test_the_library_board_shows_both_its_jobs():
    u = Unit("player")
    guild = Guild([u], node="library")
    guild.deeds_done.append("library_initiate")
    group = guild.groups[0]
    group.node = "library"
    board = job_board.LibraryBoard(guild, group)
    assert {t.id for t in board.get_templates()} == {"library_dictionary", "library_ancient_codex"}

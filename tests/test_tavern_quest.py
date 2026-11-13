"""The Tavern's first job: three Potatoes from the Farm, a Jobs tab always on, a failure that stays on the board."""

from gartok import i18n, job_board, missions, orders, world
from gartok.clock import SECONDS_PER_DAY
from gartok.group import Group
from gartok.guild import Guild
from gartok.web.hub_session import HubSession
from gartok.web.map_session import MapSession
from tests.helpers import standard_unit

T = missions.TAVERN_POTATOES


def _guild():
    u = standard_unit()
    guild = Guild([u])
    guild.groups = [Group([u], "tavern")]
    return guild


def test_the_template_is_the_innkeepers_and_pays_twenty_copper():
    assert (T.giver, T.node, T.goal_item, T.goal_qty, T.reward, T.deadline_days) == (
        "innkeeper", "tavern", "Potato", 3, 20, 5)
    assert missions.TEMPLATES[T.id] is T and T.name and T.blurb


def test_it_is_offered_on_day_one_at_the_tavern_only():
    guild = _guild()
    assert guild.clock.day == 1 and T in missions.offers_at(guild, "tavern")
    assert T not in missions.offers_at(guild, "farm")


def test_it_does_not_feed_the_bankers_economic_deeds():
    assert "economic" not in T.tags


def test_the_tavern_has_a_jobs_tab_always_on():
    guild = _guild()
    hub = HubSession(MapSession(guild), guild.groups[0], orders.Order("recruit"))
    assert "jobs" in [k for k, _ in hub.tabs]
    assert world.node("tavern").has("innkeeper")


def test_accepting_shows_the_warning_and_the_job_goes_out():
    guild = _guild()
    board = job_board.TavernBoard(guild, guild.groups[0])
    assert board.get_templates() == [T]
    assert board.accept(T)
    assert "beers" in board.notice
    m = next(m for m in guild.missions if m.template_id == T.id)
    assert m.deadline_day == m.accepted_day + 5


def test_three_potatoes_turn_in_for_twenty_copper():
    guild = _guild()
    g = guild.groups[0]
    board = job_board.TavernBoard(guild, g)
    board.accept(T)
    assert not board.turn_in(T)
    leader = g.leader
    before = leader.money
    leader.give_to_pack("Potato", 3)
    assert board.turn_in(T)
    assert leader.money == before + 20 and leader.count_of("Potato") == 0
    assert board.get_templates() == [T]
    assert not board._is_offered(T)


def test_a_missed_deadline_fails_it_and_the_board_keeps_saying_so():
    guild = _guild()
    g = guild.groups[0]
    board = job_board.TavernBoard(guild, g)
    board.accept(T)
    m = guild.missions[0]
    m.state, m.failed_day = "failed", guild.clock.day
    guild.clock.seconds += 6 * SECONDS_PER_DAY
    assert board.get_templates() == [T]
    assert not board._is_offered(T)
    _, label, on = board._job_button(T, None, {})
    assert label == i18n.t("job_board.job_failed") and not on

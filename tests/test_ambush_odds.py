"""An opportunist ambush needs a pack that would take on the group (`encounters.would_attack`): the
chance of the ambush is rolled as ever, then a pack the group would sweep lets it be, silently.
Determined and sought fights never ask."""

import pathlib

import pytest

from gartok import campaign, data, encounters, forced, gather, hunt, orders, world
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import standard_unit
from tests.test_supply_run import HIT, _make_guild, _Rolls, _walk


def _band(n, level):
    return [encounters.build_enemy(level) for _ in range(n)]


def _wolves(n, level=0):
    return [encounters.build_enemy(level, race_pool=data.WILD_POOL) for _ in range(n)]


def _strong():
    return _band(8, 3)


def _weak():
    return _band(1, 0)


# ---- the measure --------------------------------------------------------- #

def test_eight_level_3_against_two_level_0_wolves_is_no_contest_and_a_lone_level_0_is():
    wolves = _wolves(2)
    assert encounters.pack_power(wolves, _strong()) < encounters.AMBUSH_MIN_POWER
    assert not encounters.would_attack(wolves, _strong())
    assert encounters.would_attack(wolves, _weak())


def test_numbers_weigh_more_than_a_level():
    wolves = _wolves(6, 1)
    assert encounters.would_attack(wolves, _band(2, 3))
    assert encounters.pack_power(wolves, _band(2, 3)) > encounters.pack_power(_wolves(2, 1), _band(2, 3))


def test_a_wounded_group_is_a_likelier_target_and_the_fallen_do_not_count():
    wolves = _wolves(3, 2)
    group = _band(3, 5)
    whole = encounters.pack_power(wolves, group)
    for u in group:
        u.hp = max(1, u.hp_max * 3 // 10)
    assert encounters.pack_power(wolves, group) > whole

    one, fallen = _band(1, 5), encounters.build_enemy(5)
    fallen.hp = 0
    assert encounters.pack_power(wolves, one + [fallen]) == encounters.pack_power(wolves, one)


def test_nobody_standing_on_either_side():
    assert encounters.pack_power(_wolves(2), []) == 1.0
    assert encounters.pack_power([], _weak()) == 0.0
    down = _wolves(2)
    for u in down:
        u.hp = 0
    assert not encounters.would_attack(down, _weak())


def test_the_ai_never_reads_the_measure():
    ai_dir = pathlib.Path(encounters.__file__).parent / "ai"
    text = "".join(p.read_text(encoding="utf-8") for p in ai_dir.glob("*.py"))
    assert "pack_power" not in text and "would_attack" not in text


# ---- the road ------------------------------------------------------------ #

def _arrive_at_the_road(monkeypatch, members, pack):
    monkeypatch.setattr(world, "ROAD_AMBUSH_CHANCE", 1.0)
    monkeypatch.setattr(forced.encounters, "roll_encounter", lambda table: pack)
    g = Group(members, node="city")
    guild = Guild(None, groups=[g])
    g.order = orders.travel(g, "road")
    return g, campaign.advance(guild)


def test_eight_level_3_walking_the_old_road_are_never_ambushed_by_two_wolves_and_nothing_shows(monkeypatch):
    g, result = _arrive_at_the_road(monkeypatch, _strong(), _wolves(2))
    assert g.node == "road" and g.order is None and g.pending is None
    assert not result.pending
    assert not any("ambush" in e.lower() or "wolf" in e.lower() or "pack" in e.lower() for e in result.events)


def test_a_lone_level_0_on_the_same_road_is_ambushed_by_the_same_wolves(monkeypatch):
    g, result = _arrive_at_the_road(monkeypatch, _weak(), _wolves(2))
    (grp, order), = result.pending
    assert grp is g and order.kind == "ambush" and len(order.pack) == 2


def test_the_chance_is_rolled_as_ever_and_only_a_hit_rolls_the_pack(monkeypatch):
    rolled = []
    monkeypatch.setattr(forced.encounters, "roll_encounter", lambda table: rolled.append(1) or _wolves(2))
    g = Group(_strong(), node="road")
    guild = Guild(None, groups=[g])

    monkeypatch.setattr(forced.random, "random", lambda: world.ROAD_AMBUSH_CHANCE * 1.01)
    assert forced.road_ambush_catch(guild, g, None, []) is None and not rolled
    monkeypatch.setattr(forced.random, "random", lambda: world.ROAD_AMBUSH_CHANCE * 0.99)
    assert forced.road_ambush_catch(guild, g, None, []) is None and len(rolled) == 1


# ---- the work ------------------------------------------------------------ #

def _shift(monkeypatch, members, pack):
    monkeypatch.setattr(gather, "ambushed", lambda *a, **k: True)
    monkeypatch.setattr(gather, "ambush_pack", lambda node_id: pack)
    for u in members:
        u.give_to_pack(gather.tool("mine"))
    guild = Guild(members, node="mine")
    guild.licences.add("mine")
    group = guild.groups[0]
    order = orders.work(guild, group, 8, gather=True)
    return guild.gather_shift(group, order)


def test_a_crew_the_pack_would_not_take_on_banks_its_shift_as_if_none_came(monkeypatch):
    events, ambush = _shift(monkeypatch, _strong(), _wolves(2))
    assert ambush is None
    assert any("gathered" in e for e in events) and not any("pack" in e for e in events)


def test_a_crew_the_pack_would_take_on_is_found_at_work(monkeypatch):
    events, ambush = _shift(monkeypatch, _weak(), _wolves(2))
    assert ambush.kind == "gather_ambush" and len(ambush.pack) == 2
    assert any("a pack finds" in e for e in events)


# ---- the caravan --------------------------------------------------------- #

def _caravan(monkeypatch, pack, members=None):
    monkeypatch.setattr(encounters, "roll_supply_ambush", lambda: pack)
    g, grp, units = _make_guild()
    if members is not None:
        grp.members = members
    grp.order = g.supply_leg(grp, grp.node, orders.supply_route(), rng=_Rolls(HIT))
    return g, grp


def test_a_caravan_the_raiders_would_not_take_on_walks_the_rest_of_the_leg(monkeypatch):
    g, grp = _caravan(monkeypatch, _wolves(2), _strong())
    owed = grp.order.owed
    assert owed > 0
    result = campaign.advance(g)
    assert not result.pending and grp.pending is None
    assert grp.order is not None and grp.order.owed == 0 and grp.order.remaining == pytest.approx(owed)
    _walk(g, grp)
    assert grp.order is None and g.supply_runs_completed == 1


def test_a_caravan_the_raiders_would_take_on_is_stopped(monkeypatch):
    g, grp = _caravan(monkeypatch, _wolves(2), _weak())
    result = campaign.advance(g)
    assert grp.pending.kind == "supply_ambush" and (grp, grp.pending) in result.pending


# ---- the hunt ------------------------------------------------------------ #

class _Always:
    def random(self):
        return 0.0


class _Never:
    def random(self):
        return 0.99


def _stretch(party, pack, hours=4, **kw):
    rolls = []
    state = hunt.HuntState(party, None, hours)
    out = hunt.hunt_stretch(state, rng=_Always(), roll_pack=lambda: rolls.append(1) or pack, **kw)
    return state, out, rolls


def test_a_hunt_the_pack_would_not_take_on_keeps_spending_its_hours_rolling_a_pack_each_time():
    state, (elapsed, ambushed), rolls = _stretch(_strong(), _wolves(2))
    assert (elapsed, ambushed) == (4, False) and len(rolls) == 4
    assert state.hours_left == 0 and state.hours_hunted == 4 and state.pack == []


def test_a_hunt_the_pack_would_take_on_ends_on_that_pack():
    pack = _wolves(2)
    state, (elapsed, ambushed), rolls = _stretch(_weak(), pack)
    assert (elapsed, ambushed) == (1, True) and len(rolls) == 1 and state.pack == pack


def test_a_pack_that_was_let_be_is_followed_by_a_fresh_roll():
    packs = iter([_wolves(2), _wolves(8, 2)])
    state = hunt.HuntState(_strong(), None, 4)
    elapsed, ambushed = hunt.hunt_stretch(state, rng=_Always(), roll_pack=lambda: next(packs))
    assert (elapsed, ambushed) == (2, True) and len(state.pack) == 8


def test_the_hunt_without_a_roll_is_as_before():
    state = hunt.HuntState(_strong(), None, 4)
    assert hunt.hunt_stretch(state, rng=_Always()) == (1, True) and state.pack == []


# ---- the fights that come whatever the odds ------------------------------ #

def test_the_biwolf_comes_whatever_the_odds(monkeypatch):
    monkeypatch.setattr(encounters, "AMBUSH_MIN_POWER", 2.0)
    state = hunt.HuntState(_strong(), None, 4)
    elapsed, ambushed = hunt.hunt_stretch(state, rng=_Never(), hour=17, lure=True,
                                          roll_pack=lambda: pytest.fail("the Biwolf is not rolled"))
    assert ambushed and state.biwolf


def test_the_city_raid_and_the_retake_come_whatever_the_odds(monkeypatch):
    monkeypatch.setattr(encounters, "AMBUSH_MIN_POWER", 2.0)
    monkeypatch.setattr(forced.random, "random", lambda: 0.0)
    unit = standard_unit()
    group = Group([unit], node="city")
    guild = Guild(None, groups=[group])
    guild.house.squatting = True
    assert forced.property_raid_catch(guild, group, None, []).kind == "eviction"

    group.node = world.WILDS_TERRITORY_NODE
    guild.wilds_claim_owner = "seized"
    assert forced.wilds_claim_retake_catch(guild, group, None, []).kind == "wilds_retake"


def test_the_play_log_tells_a_dismissed_pack_from_a_fight(monkeypatch, tmp_path):
    import json

    from gartok import recorder
    recorder.attach(str(tmp_path), Guild(_strong()))
    try:
        _shift(monkeypatch, _strong(), _wolves(2))
        _shift(monkeypatch, _weak(), _wolves(2))
    finally:
        recorder.detach()
    rows = [json.loads(line) for line in (tmp_path / recorder.FILE).read_text().splitlines()]
    rolls = [r for r in rows if r["e"] == "ambush_roll"]
    assert [r["result"] for r in rolls] == ["dismissed", "fight"]
    assert rolls[0]["node"] == "mine" and rolls[0]["foes"] == 2 and rolls[0]["hours"] == 8

"""The tanner's second job: the Biwolf. Hunting the Wilds after dark with fifteen
portions of meat in the packs draws him out (once, and only while the job is
out); his leather is the goal, and worn it adds 1 AC against non-humanoids."""

import random

from gartok import ai, data, encounters, hunt, items, loot, missions, world
from gartok.battle import Battle
from gartok.clock import Clock
from gartok.guild import Guild
from tests.helpers import Unit, fixed_d20


def _guild(clock_hour=14):
    random.seed(1)
    members = [Unit("player"), Unit("player")]
    return Guild(members, node="wilds", clock=Clock(clock_hour * 3600)), members


def _job(guild, signer):
    hides = missions.accept(guild, signer, missions.TANNER_HIDES)
    hides.state = "done"
    return missions.accept(guild, signer, missions.TANNER_BIWOLF)


def _stock_meat(unit, n):
    unit.give_to_pack(hunt.MEAT_ITEM, n)


class _Never:
    def random(self):
        return 1.0


def test_the_biwolf_job_is_offered_only_after_the_hides_are_in():
    guild, (signer, _) = _guild()
    offered = lambda: {t.id for t in missions.offers_at(guild, "city")}
    assert missions.TANNER_BIWOLF.id not in offered()
    hides = missions.accept(guild, signer, missions.TANNER_HIDES)
    assert missions.TANNER_BIWOLF.id not in offered()
    hides.state = "failed"
    assert missions.TANNER_BIWOLF.id not in offered()
    hides.state = "done"
    assert missions.TANNER_BIWOLF.id in offered()


def test_the_biwolf_job_has_no_deadline_and_survives_a_save():
    guild, (signer, _) = _guild()
    m = _job(guild, signer)
    assert m.deadline_day is None and missions.days_left(guild, m) is None
    guild.pass_time(24 * 90)
    assert missions.expire_overdue(guild) == []
    assert m.state == "active"
    back = missions.mission_from_dict(missions.mission_to_dict(m))
    assert back.deadline_day is None


def test_fifteen_meat_on_the_party_and_the_job_out_are_what_call_him():
    guild, (signer, mate) = _guild()
    assert not hunt.biwolf_lure(guild, [signer, mate])          # no job yet
    _job(guild, signer)
    _stock_meat(signer, 10)
    _stock_meat(mate, 4)
    assert not hunt.biwolf_lure(guild, [signer, mate])          # 14 is not enough
    _stock_meat(mate, 1)
    assert hunt.biwolf_lure(guild, [signer, mate])              # packs add up across the party
    assert not hunt.biwolf_lure(guild, [signer])                # only the hunters' own packs count


def test_he_comes_at_the_first_hour_after_dark_and_never_by_day():
    _, (signer, _) = _guild()
    st = hunt.HuntState([signer], world.node("wilds"), hours_left=8)
    elapsed, ambushed = hunt.hunt_stretch(st, _Never(), hour=9, lure=True)
    assert not ambushed and not st.biwolf and elapsed == 8      # 09:00-17:00 is all daylight

    st = hunt.HuntState([signer], world.node("wilds"), hours_left=8)
    elapsed, ambushed = hunt.hunt_stretch(st, _Never(), hour=14, lure=True)
    assert ambushed and st.biwolf and elapsed == 5              # 14..17 by day, 18:00 is dark

    st = hunt.HuntState([signer], world.node("wilds"), hours_left=8)
    elapsed, ambushed = hunt.hunt_stretch(st, _Never(), hour=20, lure=True)
    assert ambushed and st.biwolf and elapsed == 1

    st = hunt.HuntState([signer], world.node("wilds"), hours_left=8)
    elapsed, ambushed = hunt.hunt_stretch(st, _Never(), hour=20, lure=False)
    assert not ambushed and elapsed == 8                        # no lure, no Biwolf


def test_the_pack_is_the_biwolf_and_three_wolves_and_it_springs_once():
    guild, (signer, _) = _guild()
    m = _job(guild, signer)
    _stock_meat(signer, 15)
    assert hunt.biwolf_lure(guild, [signer])
    pack = hunt.biwolf_pack(guild)
    assert len(pack) == 4
    assert pack[0].name == "Biwolf" and pack[0].combat_level == 10
    assert [u.race["name"] for u in pack[1:]] == ["Wolf"] * 3
    assert m.ambush_done
    assert not hunt.biwolf_lure(guild, [signer])                # spent for good


def test_he_does_not_come_for_a_finished_job():
    guild, (signer, _) = _guild()
    m = _job(guild, signer)
    _stock_meat(signer, 15)
    m.state = "done"
    assert not hunt.biwolf_lure(guild, [signer])


def test_the_biwolf_always_drops_his_leather_and_a_plain_wolf_does_not():
    guild, (signer, _) = _guild()
    _job(guild, signer)
    _stock_meat(signer, 15)
    pack = hunt.biwolf_pack(guild)
    batt = Battle([signer], pack, lethal=True)
    pool = loot.field_loot(batt, [])
    assert pool.count(items.BIWOLF_LEATHER_ITEM) == 1

    wolves = Battle([signer], pack[1:], lethal=True)
    assert items.BIWOLF_LEATHER_ITEM not in loot.field_loot(wolves, [])


def test_the_leather_is_an_artifact_that_fits_the_slot():
    u = Unit("player")
    assert items.is_artifact(items.BIWOLF_LEATHER_ITEM)
    assert u.give_to_artifact(items.BIWOLF_LEATHER_ITEM)
    assert u.equipped_artifact == items.BIWOLF_LEATHER_ITEM
    _title, desc = items.item_tooltip(items.BIWOLF_LEATHER_ITEM)
    assert "+1 AC" in desc


def test_worn_it_adds_one_ac_against_beasts_and_not_against_humanoids():
    wearer = Unit("player")
    wearer.give_to_artifact(items.BIWOLF_LEATHER_ITEM)
    wolf = encounters.build_enemy(1, race_pool=data.WILD_POOL)
    batt = Battle([wearer, Unit("player")], [Unit("enemy"), wolf])
    worn, bare = batt.player_units
    human, beast = batt.enemy_units
    assert worn.ac_vs(human) == worn.ac
    assert worn.ac_vs(beast) == worn.ac + 1
    assert bare.ac_vs(beast) == bare.ac


def _wolf_attacks(wearing):
    from gartok import actions
    guild, (signer, _) = _guild()
    _job(guild, signer)
    _stock_meat(signer, 15)
    pack = hunt.biwolf_pack(guild)
    if wearing:
        signer.give_to_artifact(items.BIWOLF_LEATHER_ITEM)
    batt = Battle([signer], pack[1:2])
    me, wolf = batt.player_units[0], batt.enemy_units[0]
    me.pos, wolf.pos = (5, 5), (6, 5)
    wolf.ap = 2
    with fixed_d20(10):
        actions.Attack().execute(batt, wolf, me)
    return me, next(ln for ln in batt.log_lines if "vs AC" in ln)


def test_a_beast_attacking_the_wearer_rolls_against_the_raised_ac():
    me, line = _wolf_attacks(wearing=True)
    assert f"vs AC {me.ac + 1}" in line
    me, line = _wolf_attacks(wearing=False)
    assert f"vs AC {me.ac}" in line


def test_the_ai_plays_out_the_biwolf_fight_to_a_result():
    guild, members = _guild()
    signer = members[0]
    _job(guild, signer)
    _stock_meat(signer, 15)
    signer.give_to_artifact(items.BIWOLF_LEATHER_ITEM)
    pack = hunt.biwolf_pack(guild)
    batt = Battle(members, pack, lethal=True)
    guard = 0
    while batt.winner is None and guard < 2000:
        guard += 1
        ai.take_turn(batt, batt.active)
    assert batt.winner is not None
    assert any("Biwolf" in ln for ln in batt.log_lines)


def test_delivering_the_leather_ends_the_job_and_banks_the_deed():
    guild, (signer, mate) = _guild()
    m = _job(guild, signer)
    assert not missions.can_turn_in(guild, m)
    mate.give_to_pack(items.BIWOLF_LEATHER_ITEM)                # same group, other pack
    assert missions.can_turn_in(guild, m)
    earned = missions.turn_in(guild, m)
    assert m.state == "done"
    assert mate.count_of(items.BIWOLF_LEATHER_ITEM) == 0
    assert "tanners_biwolf" in guild.deeds_done
    assert guild.reputation["tanners"] == 1
    assert any(d.id == "tanners_biwolf" for d in earned)


def test_a_leather_already_worn_still_counts_and_is_taken_off_the_slot():
    guild, (signer, _) = _guild()
    m = _job(guild, signer)
    signer.give_to_artifact(items.BIWOLF_LEATHER_ITEM)
    assert missions.progress(guild, m) == 1
    missions.turn_in(guild, m)
    assert signer.equipped_artifact is None


def test_the_spent_ambush_survives_a_save():
    guild, (signer, _) = _guild()
    m = _job(guild, signer)
    m.ambush_done = True
    back = missions.mission_from_dict(missions.mission_to_dict(m))
    assert back.ambush_done and back.deadline_day is None


def test_the_hunt_screen_sends_the_biwolf_pack_at_night_and_the_ordinary_one_otherwise():
    from gartok.hunt_screen import HuntScreen
    from gartok.ui.tokens import fonts as ui_fonts

    def run(hour, meat):
        guild, (signer, _) = _guild(hour)
        _job(guild, signer)
        _stock_meat(signer, meat)
        st = hunt.HuntState([signer], world.node("wilds"), hours_left=0)
        scr = HuntScreen(ui_fonts(), guild, st, phase="setup",
                         on_ambush=lambda *_: None, on_done=lambda: None)
        st.hours_left = 8
        scr._do_stretch()
        return scr, st

    scr, st = run(hour=14, meat=15)
    assert scr.phase == "ambush" and st.biwolf
    assert scr.ambush_pack[0].name == "Biwolf" and len(scr.ambush_pack) == 4

    scr, st = run(hour=14, meat=14)
    assert not st.biwolf
    assert scr.phase != "ambush" or all(u.name != "Biwolf" for u in scr.ambush_pack)


def test_the_two_tanner_jobs_are_worth_two_reputation():
    guild, (signer, _) = _guild()
    hides = missions.accept(guild, signer, missions.TANNER_HIDES)
    signer.give_to_pack("1sqm Hide", 15)
    assert any(d.id == "tanners_hides" for d in missions.turn_in(guild, hides))
    assert guild.reputation["tanners"] == 1
    biwolf = missions.accept(guild, signer, missions.TANNER_BIWOLF)
    signer.give_to_pack(items.BIWOLF_LEATHER_ITEM)
    missions.turn_in(guild, biwolf)
    assert guild.reputation["tanners"] == 2


def test_a_failed_hides_job_comes_back_seven_days_after_the_failure():
    guild, (signer, _) = _guild()
    hides = missions.accept(guild, signer, missions.TANNER_HIDES)
    guild.clock.advance_hours(24 * (missions.TANNER_HIDES.deadline_days + 1))
    missions.expire_overdue(guild)
    assert hides.state == "failed" and hides.failed_day is not None
    offered = lambda: missions.TANNER_HIDES.id in {t.id for t in missions.offers_at(guild, "city")}
    assert not offered() and missions.retry_in(guild, missions.TANNER_HIDES) > 0
    guild.clock.advance_hours(24 * 6)
    assert not offered()
    guild.clock.advance_hours(24)
    assert offered() and missions.retry_in(guild, missions.TANNER_HIDES) == 0
    again = missions.accept(guild, signer, missions.TANNER_HIDES)
    assert again.state == "active" and not offered()
    signer.give_to_pack("1sqm Hide", 15)
    missions.turn_in(guild, again)
    assert not offered()                                        # done: never again
    assert missions.TANNER_BIWOLF.id in {t.id for t in missions.offers_at(guild, "city")}


def test_the_retry_wait_survives_a_save():
    guild, (signer, _) = _guild()
    m = missions.accept(guild, signer, missions.TANNER_HIDES)
    guild.pass_time(24 * 6)
    back = missions.mission_from_dict(missions.mission_to_dict(m))
    assert m.failed_day is not None and back.failed_day == m.failed_day


def test_losing_the_leather_fails_the_job_for_good():
    guild, (signer, mate) = _guild()
    m = _job(guild, signer)
    assert missions.fail_if_leather_lost(guild) is None          # no ambush yet: nothing lost
    _stock_meat(signer, 15)
    hunt.biwolf_pack(guild)
    mate.give_to_pack(items.BIWOLF_LEATHER_ITEM)
    assert missions.fail_if_leather_lost(guild) is None          # taken from the field
    mate.remove_named(items.BIWOLF_LEATHER_ITEM)
    assert missions.fail_if_leather_lost(guild) is m
    assert m.state == "failed"
    assert missions.TANNER_BIWOLF.id not in {t.id for t in missions.offers_at(guild, "city")}
    guild.pass_time(24 * 30)
    assert missions.TANNER_BIWOLF.id not in {t.id for t in missions.offers_at(guild, "city")}
    assert missions.retry_in(guild, missions.TANNER_BIWOLF) is None


def test_a_worn_or_banked_leather_is_not_lost():
    guild, (signer, _) = _guild()
    _job(guild, signer)
    _stock_meat(signer, 15)
    hunt.biwolf_pack(guild)
    signer.give_to_artifact(items.BIWOLF_LEATHER_ITEM)
    assert missions.fail_if_leather_lost(guild) is None
    signer.take_from_artifact()
    guild.bank.put(items.BIWOLF_LEATHER_ITEM)
    assert missions.fail_if_leather_lost(guild) is None

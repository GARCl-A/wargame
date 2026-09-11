"""The lumber yard: day-labour for copper, and the work-XP marks."""

import random

from tests.helpers import economy, persist, Unit, world, _unit


def test_lumber_yard_is_a_work_town_one_hour_from_the_city():
    n = world.node("lumber_yard")
    assert n.kind == "town" and n.work
    _, hours = world.route("city", "lumber_yard")
    assert hours == 1


def test_lumber_pay_is_by_the_whole_block():
    assert economy.lumber_pay(0) == 0
    assert economy.lumber_pay(3) == 0                 # short of a block: nothing
    assert economy.lumber_pay(4) == 3
    assert economy.lumber_pay(15) == 9                # three blocks, 3 h unpaid
    assert economy.lumber_pay(16) == 12               # a full day


def test_work_shift_pays_every_worker_and_banks_the_hours():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(4)
    a, b = Unit("player"), Unit("player")
    a.gold = b.gold = 0
    a._base_inventory = b._base_inventory = []
    for u in (a, b):
        u._derive_combat()
    guild = Guild([a, b], clock=Clock(6 * 3600))      # 06:00 day 1
    events = guild.work_shift([a, b], 16)
    assert a.gold == 12 and b.gold == 12
    assert a.work_hours == 16 and b.work_hours == 16
    assert guild.clock.hour_of_day == 22 and guild.clock.day == 1
    assert any("Lumber yard" in e for e in events)


def test_work_shift_crossing_midnight_runs_the_daily_meal():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(5)
    u = Unit("player")
    u.gold = 0
    u._base_inventory = ["Potato"]
    u._derive_combat()
    guild = Guild([u], clock=Clock(20 * 3600))        # 20:00 day 1
    guild.work_shift([u], 8)                          # -> 04:00 day 2, one meal
    assert guild.clock.day == 2
    assert u.gold == 6 and u.rations == 0 and u.unfed_days == 0


def test_work_xp_is_one_mark_per_16_hours_and_survives_a_save():
    u = _unit(seed=6, work_hours=0)
    assert u.work_xp == 0
    u.work_hours = 15
    assert u.work_xp == 0
    u.work_hours = 32
    assert u.work_xp == 2
    assert Unit.from_save(persist.unit_to_dict(u)).work_hours == 32


# --------------------------------------------------------------------------- #
# work-XP is gated like combat XP: nothing for a job you have outgrown         #
# --------------------------------------------------------------------------- #

def test_lumber_level_is_zero_unless_swinging_your_own_axe():
    u = _unit(seed=7)
    assert economy.lumber_level(u) == 0
    u.equipped_weapon = "Dagger"
    assert economy.lumber_level(u) == 0
    u.equipped_weapon = "Axe"
    assert economy.lumber_level(u) == economy.LUMBER_LEVEL_OWN_AXE == 1


def test_own_axe_pays_a_better_wage():
    assert economy.lumber_pay(16, level=0) == 12
    assert economy.lumber_pay(16, level=1) == 16


def test_outgrown_lumber_yard_pays_but_teaches_nothing():
    """A work-level-1 worker gets zero work-XP from the bare-handed job (level
    0 < their level 1) but full pay -- and full XP again once they bring their
    own Axe, which lifts the job to level 1."""
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(4)
    u = Unit("player")
    u.gold = 0
    u.work_hours = economy.LUMBER_XP_HOURS * 2          # work_xp 2 -> work level 1
    u._base_inventory = []
    u._derive_combat()
    before = u.work_hours
    guild = Guild([u], clock=Clock(6 * 3600))
    guild.work_shift([u], 16)
    assert u.gold == 12 and u.work_hours == before      # paid, but no XP: outgrown

    u.gold = 0
    u.give_to_hand("Axe")
    guild.work_shift([u], 16)
    assert u.gold == 16                                 # the better, own-Axe wage
    assert u.work_hours == before + 16                  # level 1 job teaches a level 1 worker


def test_hunting_is_a_level_3_job_that_outlasts_the_lumber_yard():
    from gartok import hunt
    u = Unit("player")
    u.work_hours = economy.LUMBER_XP_HOURS * 6          # work_xp 6 -> work level 2
    state = hunt.HuntState(party=[u], node=world.node("wilds"),
                           hours_left=0, hours_hunted=10)
    before = u.work_hours
    hunt.grant_meat(state)
    assert u.work_hours == before + 10                  # level 3 job still teaches a level 2 worker

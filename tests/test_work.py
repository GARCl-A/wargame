"""The lumber yard: day-labour for copper, and the work-XP marks."""

import random

from tests.helpers import Unit, _unit, economy, fixed_d20, packed, persist, world


def test_lumber_yard_is_a_work_town_one_hour_from_the_city():
    n = world.node("lumber_yard")
    assert n.kind == "town" and n.has("work")
    _, hours = world.route("city", "lumber_yard")
    assert hours == 1


def test_lumber_pay_is_by_the_whole_block():
    assert economy.lumber_pay(0) == 0
    assert economy.lumber_pay(3) == 0                 # short of a block: nothing
    assert economy.lumber_pay(4) == 1
    assert economy.lumber_pay(15) == 3                # three blocks, 3 h unpaid
    assert economy.lumber_pay(16) == 4                # a full day


def test_work_shift_pays_every_worker_and_banks_the_hours():
    from gartok.clock import Clock
    from gartok.guild import Guild
    random.seed(4)
    a, b = Unit("player"), Unit("player")
    a._base_inventory, b._base_inventory = [], []
    a.money = b.money = 0
    for u in (a, b):
        u._derive_combat()
    guild = Guild([a, b], clock=Clock(6 * 3600))      # 06:00 day 1
    events, _ = guild.work_shift([a, b], 16)
    assert a.money == 4 and b.money == 4
    assert a.work_hours == 16 and b.work_hours == 16
    assert guild.clock.hour_of_day == 22 and guild.clock.day == 1
    assert any("Lumber Yard" in e for e in events)


def test_work_shift_crossing_midnight_runs_the_daily_meal():
    from gartok.clock import Clock
    from gartok.guild import Guild
    random.seed(5)
    u = Unit("player")
    u.money = 0
    u._base_inventory = packed(["Potato"])
    u._derive_combat()
    guild = Guild([u], clock=Clock(20 * 3600))        # 20:00 day 1
    guild.work_shift([u], 8)                          # -> 04:00 day 2, one meal
    assert guild.clock.day == 2
    assert u.money == 2 and u.rations == 0 and u.unfed_days == 0


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


def test_lumber_level_counts_an_axe_carried_in_the_pack_too():
    """You don't have to fight with the Axe in hand to get credit for owning
    one -- it just has to be somewhere on you when you show up for the shift."""
    u = _unit(seed=7)
    u.equipped_weapon = "Dagger"
    u._base_inventory = []
    assert economy.lumber_level(u) == 0
    u._base_inventory = packed(["Axe"])
    assert economy.lumber_level(u) == economy.LUMBER_LEVEL_OWN_AXE == 1


def test_own_axe_pays_a_better_wage():
    assert economy.lumber_pay(16, level=0) == 4
    assert economy.lumber_pay(16, level=1) == 5


def test_outgrown_lumber_yard_pays_but_teaches_nothing():
    """A work-level-1 worker gets zero work-XP from the bare-handed job (level
    0 < their level 1) but full pay -- and full XP again once they bring their
    own Axe, which lifts the job to level 1."""
    from gartok.clock import Clock
    from gartok.guild import Guild
    random.seed(4)
    u = Unit("player")
    u.money = 0
    u.work_hours = economy.LUMBER_XP_HOURS * 2          # work_xp 2 -> work level 1
    u._base_inventory = []
    u._derive_combat()
    before = u.work_hours
    guild = Guild([u], clock=Clock(6 * 3600))
    guild.work_shift([u], 16)
    assert u.money == 4 and u.work_hours == before      # paid, but no XP: outgrown

    u.money = 0
    u.give_to_hand("Axe")
    guild.work_shift([u], 16)
    assert u.money == 5                                  # the better, own-Axe wage
    assert u.work_hours == before + 16                  # level 1 job teaches a level 1 worker


def test_hunting_is_a_level_3_job_that_outlasts_the_lumber_yard():
    from gartok import hunt
    u = Unit("player")
    u.work_hours = economy.LUMBER_XP_HOURS * 6          # work_xp 6 -> work level 2
    state = hunt.HuntState(party=[u], node=world.node("wilds"),
                           hours_left=0, hours_hunted=10)
    before = u.work_hours
    hunt.grant_haul(state)
    assert u.work_hours == before + 10 * 2              # level 3 job still teaches a level 2 worker, x2


# --------------------------------------------------------------------------- #
# Steady Pace: work counts as rest                                             #
# --------------------------------------------------------------------------- #

def _hurt_crew(with_talent):
    from gartok import orders
    from gartok.group import Group
    from gartok.guild import Guild
    random.seed(3)                                  # a unit with enough HP to be hurt
    u = Unit("player")
    u.hp = u.hp_max - 1
    assert 0 < u.hp < u.hp_max
    if with_talent:
        u.talents["work"] += ["carrier", "brisk_hands", "steady_pace"]
    g = Group([u], node="lumber_yard")
    guild = Guild(None, groups=[g])
    return guild, g, u, orders


def test_steady_pace_heals_a_working_group_like_rest():
    guild, g, u, orders = _hurt_crew(True)
    g.order = orders.garrison("lumber")
    guild.pass_time(8)
    assert u.hp == u.hp_max


def test_without_steady_pace_working_never_heals():
    guild, g, u, orders = _hurt_crew(False)
    g.order = orders.garrison("lumber")
    guild.pass_time(16)
    assert u.hp == u.hp_max - 1


def test_steady_pace_does_not_heal_a_travelling_group():
    guild, g, u, orders = _hurt_crew(True)
    g.order = orders.Order("travel", eta=16, remaining=16, dest="road", path=())
    guild.pass_time(16)
    assert u.hp == u.hp_max - 1


def test_steady_pace_sits_below_brisk_hands():
    from gartok import talents
    t = talents.TALENTS["steady_pace"]
    assert (t.track, t.tier, t.requires) == ("work", 3, "brisk_hands")


def test_a_hunting_party_does_not_rest_while_it_hunts():
    """The hunt spends hours with the group's own order consumed; those hours still count as exertion."""
    from gartok import campaign
    guild, g, u, _ = _hurt_crew(False)
    g.order = None
    campaign.advance(guild, dt=8, busy=[u])
    assert u.hp == u.hp_max - 1

    campaign.advance(guild, dt=8)                     # the same hours idle in town do heal
    assert u.hp == u.hp_max


def test_steady_pace_lets_a_hunter_recover_on_the_trail():
    from gartok import campaign
    guild, g, u, _ = _hurt_crew(True)
    g.order = None
    campaign.advance(guild, dt=8, busy=[u])
    assert u.hp == u.hp_max


def test_a_crafting_shift_is_not_rest():
    guild, g, u, _ = _hurt_crew(False)
    guild.pass_time(8, busy=[u])
    assert u.hp == u.hp_max - 1


def _performer(cha, instrument=True):
    u = Unit("player")
    u.set_base_attribute("charisma", cha)
    u._base_inventory = packed(["Musical Instrument"] if instrument else [])
    u.money = 0
    u._derive_combat()
    return u


def test_perform_pay_is_a_charisma_test_each_hour():
    with fixed_d20(20):
        assert economy.perform_pay(4, 2) == 4 * 3        # (20 + 2 - 16) // 2 per hour
        assert economy.perform_pay(1, 0) == 2
    with fixed_d20(10):
        assert economy.perform_pay(4, 2) == 0            # a flop draws nothing
    with fixed_d20(1):
        assert economy.perform_pay(4, -3) == 0           # never negative


def test_perform_expected_is_the_average_of_the_d20():
    ys = [economy.perform_expected(1, m) for m in range(-1, 5)]
    assert ys == sorted(ys)                              # more Charisma never pays less
    axe = economy.lumber_pay(16, level=1) / 16           # the lumber yard with an Axe, $/h
    assert economy.perform_expected(16, 2) > economy.lumber_pay(16, level=1)
    assert abs(economy.perform_expected(1, 1) - axe) < 0.05      # +1 is the Axe's wage


def _performer(cha, instrument=True):
    u = Unit("player")
    u.set_base_attribute("charisma", cha)
    u._base_inventory = packed(["Musical Instrument"] if instrument else [])
    u.money = 0
    u._derive_combat()
    return u


def test_perform_shift_tips_each_player_by_their_own_charisma():
    from gartok.clock import Clock
    from gartok.guild import Guild
    random.seed(6)
    star, dud = _performer(18), _performer(1)
    assert star.mod_charisma > 0 >= dud.mod_charisma
    guild = Guild([star, dud], clock=Clock(18 * 3600))
    with fixed_d20(18):
        events, _ = guild.perform_shift([star, dud], 4)
    assert star.money == 4 * ((18 + star.mod_charisma - 16) // 2) > 0
    assert dud.money == 4 * max(0, (18 + dud.mod_charisma - 16) // 2)
    assert star.work_hours == 4 * 2 and dud.work_hours == 4 * 2    # level 1 job, level 0 worker: x2
    assert guild.clock.hour_of_day == 22
    assert any("Tavern stage" in e for e in events)
    assert f"{star.name}: +8 work h (8/32 h to work level 1)." in events    # x2 for a level 0 worker


def test_perform_shift_needs_an_instrument():
    from gartok.clock import Clock
    from gartok.guild import Guild
    mute = _performer(16, instrument=False)
    guild = Guild([mute], clock=Clock(18 * 3600))
    events, _ = guild.perform_shift([mute], 4)
    assert mute.money == 0 and guild.clock.hour_of_day == 18
    assert events == ["Nobody here has an instrument to play."]


def test_only_those_with_an_instrument_play():
    from gartok.clock import Clock
    from gartok.guild import Guild
    bard, mute = _performer(18), _performer(18, instrument=False)
    guild = Guild([bard, mute], clock=Clock(18 * 3600))
    with fixed_d20(20):
        guild.perform_shift([bard, mute], 2)
    assert bard.money > 0 and mute.money == 0 and mute.work_hours == 0


def test_the_market_sells_the_musical_instrument():
    assert economy.PERFORM_ITEM in economy.MARKET_STOCK and economy.PERFORM_ITEM in economy.PRICES


def test_a_job_below_the_workers_level_says_it_teaches_nothing():
    u = Unit("player")
    u.work_hours = economy.LUMBER_XP_HOURS * 2          # work level 1
    before = u.work_hours
    assert u.bank_work(8, 0) == [f"{u.name}: no work XP -- this job is below work level 1."]
    assert u.work_hours == before


def test_work_xp_note_shows_progress_and_the_level_up():
    u = Unit("player")
    assert u.bank_work(6, 0) == [f"{u.name}: +6 work h (6/32 h to work level 1)."]
    lines = u.bank_work(26, 0)                           # 32 h in all: two marks, level 1
    assert u.work_level == 1
    assert lines[-1] == f"{u.name} reached work level 1!"
    assert lines[0].startswith(f"{u.name}: +26 work h (") and "to work level 2" in lines[0]


def test_every_activity_reports_the_work_xp_it_banked():
    from gartok import hunt
    from gartok.clock import Clock
    from gartok.guild import Guild
    u = Unit("player")
    guild = Guild([u], clock=Clock(6 * 3600))
    events, _ = guild.work_shift([u], 4)
    assert f"{u.name}: +4 work h (4/32 h to work level 1)." in events       # level 0 job, level 0 worker: x1
    lines = hunt.grant_haul(hunt.HuntState(party=[u], node=world.node("wilds"), hours_left=0, hours_hunted=2))
    assert f"{u.name}: +8 work h (12/32 h to work level 1)." in lines       # level 3 job: x4

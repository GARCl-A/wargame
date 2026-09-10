"""Hunger and encumbrance: the daily meal, the shared larder, the penalties."""

import random

from tests.helpers import abilities, data, Unit, _unit


def test_hunger_ramps_penalties_and_caps_hp():
    u = _unit(seed=5)
    fed_str, fed_hp = u.mod_strength, u.hp_max
    u.unfed_days = 1
    u._derive_combat()
    assert u.mod_strength == fed_str - 1                  # -2 to the score = -1 to the mod
    assert u.hunger_label == "hungry" and not u.incapacitated
    u.unfed_days = 2
    u._derive_combat()
    assert u.mod_strength == fed_str - 2 and u.hp_max == 1
    u.unfed_days = 3
    u._derive_combat()
    assert u.incapacitated and u.hunger_label == "starving to death"
    u.unfed_days = 0
    u._derive_combat()
    assert u.mod_strength == fed_str and u.hp_max == fed_hp   # re-derive never re-rolls HP


def test_encumbrance_penalises_str_dex_and_speed():
    from gartok.data import mod
    u = _unit(seed=5)
    u.equipped_weapon = None
    u._base_inventory = []
    u._derive_combat()
    assert not u.encumbered
    unloaded_speed = u.speed
    exp_str, exp_dex = mod(u.strength - 2), mod(u.dexterity - 2)
    u._base_inventory = ["Iron Bar"] * 20          # ~100 kg, well over carry_normal
    u._derive_combat()
    assert u.encumbered
    assert u.mod_strength == exp_str and u.mod_dexterity == exp_dex
    assert u.speed == max(1, unloaded_speed - 1)


def test_encumbrance_does_not_shrink_carry_capacity():
    u = _unit(seed=5)
    u.equipped_weapon = None
    u._base_inventory = []
    u._derive_combat()
    cap_n, cap_m = u.carry_normal, u.carry_max
    u._base_inventory = ["Iron Bar"] * 20
    u._derive_combat()
    assert u.encumbered and u.carry_normal == cap_n and u.carry_max == cap_m


def test_dropping_weight_lifts_encumbrance():
    u = _unit(seed=5)
    u.equipped_weapon = None
    u._base_inventory = ["Iron Bar"] * 20
    u._derive_combat()
    assert u.encumbered
    u._base_inventory = []
    u._derive_combat()
    assert not u.encumbered


def test_encumbrance_survives_a_save_round_trip():
    from gartok import persist
    u = _unit(seed=5)
    u._base_inventory = ["Iron Bar"] * 20
    u._derive_combat()
    assert u.encumbered
    u2 = Unit.from_save(persist.unit_to_dict(u))
    assert u2.encumbered and u2.mod_strength == u.mod_strength


def test_eating_a_ration_resets_hunger():
    u = _unit(seed=1)
    u._base_inventory = ["1kg Potato", "Rope"]
    u.unfed_days = 2
    assert u.consume_daily_food() == "ate"
    assert u.unfed_days == 0 and "1kg Potato" not in u._base_inventory
    assert "Rope" in u._base_inventory


def test_autotroph_never_eats_or_starves():
    u = _unit(seed=1)
    u._ability = abilities.get("autotroph")
    u._base_inventory = []
    for _ in range(6):
        assert u.consume_daily_food() == "ate"
    assert u.unfed_days == 0 and u.hunger_level == 0


def test_starving_without_food_eventually_kills():
    u = _unit(seed=2)
    u._base_inventory = []
    outcomes = [u.consume_daily_food() for _ in range(data.STARVATION_DEATH_DAYS)]
    assert outcomes[:-1] == ["hungry"] * (data.STARVATION_DEATH_DAYS - 1)
    assert outcomes[-1] == "dead"


def test_guild_pass_time_feeds_starves_and_buries():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(3)
    fed = Unit("player"); fed._base_inventory = ["1kg Meat", "1kg Meat"]
    fed.share_food = False                                  # keeps its stock to itself
    doomed = Unit("player"); doomed._base_inventory = []
    guild = Guild([fed, doomed], clock=Clock(6 * 3600))    # 06:00 day 1
    guild.pass_time(24)                                     # -> day 2
    assert fed.unfed_days == 0 and "1kg Meat" in fed._base_inventory
    assert doomed.unfed_days == 1 and doomed in guild.roster
    for _ in range(data.STARVATION_DEATH_DAYS):
        guild.pass_time(24)
    assert doomed not in guild.roster and fed in guild.roster


def test_eat_now_only_bites_when_hungry_and_carrying_food():
    u = _unit(seed=1)
    u._base_inventory = ["1kg Meat"]
    assert u.eat_now() is False                       # saciado: no meal, food kept
    assert u._base_inventory == ["1kg Meat"]
    u.unfed_days = 2
    assert u.eat_now() is True
    assert u.unfed_days == 0 and u._base_inventory == []
    u.unfed_days = 2
    assert u.eat_now() is False                       # hungry but nothing to eat


def test_a_sharer_feeds_a_foodless_guild_mate_on_the_daily_meal():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(3)
    mule = Unit("player"); mule._base_inventory = ["1kg Meat", "1kg Meat", "1kg Meat"]
    weakling = Unit("player"); weakling._base_inventory = []
    guild = Guild([mule, weakling], clock=Clock(6 * 3600))
    guild.pass_time(24)                                  # one day crossed
    assert weakling.unfed_days == 0                      # ate from the shared larder
    assert mule.unfed_days == 0
    assert guild.rations == 1                            # 3 - mule's meal - weakling's


def test_a_private_ration_is_never_touched_by_a_hungry_mate():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(3)
    hoarder = Unit("player"); hoarder._base_inventory = ["1kg Meat", "1kg Meat"]
    hoarder.share_food = False
    beggar = Unit("player"); beggar._base_inventory = []
    guild = Guild([hoarder, beggar], clock=Clock(6 * 3600))
    guild.pass_time(24)
    assert hoarder.unfed_days == 0 and hoarder.rations == 1
    assert beggar.unfed_days == 1                        # went hungry, hoarder didn't share


def test_everyone_eats_their_own_before_the_larder_is_raided():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(3)
    a = Unit("player"); a._base_inventory = ["1kg Meat"]          # exactly one, shared
    b = Unit("player"); b._base_inventory = ["1kg Meat"]          # exactly one, shared
    guild = Guild([a, b], clock=Clock(6 * 3600))
    guild.pass_time(24)
    assert a.unfed_days == 0 and b.unfed_days == 0       # neither lost their meal


def test_do_maintenance_feeds_the_hungry_without_waiting_for_the_day():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(3)
    u = Unit("player")
    u.unfed_days = 1
    u._base_inventory = ["1kg Meat"]
    u._derive_combat()
    guild = Guild([u], clock=Clock(10 * 3600))        # 10:00 day 1
    events = guild.do_maintenance()                   # 1 h stop, no day crossed
    assert guild.clock.day == 1 and guild.clock.hour_of_day == 11
    assert u.unfed_days == 0 and u.rations == 0
    assert any("eat" in e for e in events)


def test_hunger_survives_a_save_round_trip():
    from gartok import persist
    random.seed(7)
    u = Unit("player")
    u.unfed_days = 2
    u._derive_combat()
    v = Unit.from_save(persist.unit_to_dict(u))
    assert v.unfed_days == 2 and v.hp_max == 1
    assert v.mod_strength == u.mod_strength
    v.unfed_days = 0
    v._derive_combat()
    assert v.hp_max == v._hp_roll + v.mod_constitution + v._ability.hp_max

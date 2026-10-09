"""The economy sim (scripts/economy_activities.py layer 1, scripts/economy_guild.py layer 2):
the floor holds, the Wilds beat it for a level 2-3 squad, and a whole guild lives its days on
the real engine."""

import os
import random
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
sys.path.insert(0, SCRIPTS)

import economy_activities as act
import economy_guild as sim_mod

from gartok import arena, economy, items, world
from gartok.guild import Guild
from gartok.unit import Unit

_LIBRARY = sim_mod.FightLibrary(samples=6)     # real battles are slow: one shared cache for the file


def _lib():
    return _LIBRARY


def _sim(policy="lumber", **kw):
    kw.setdefault("library", _lib())
    return sim_mod.Sim(sim_mod.POLICIES[policy](), seed=kw.pop("seed", 1), **kw)


def _run(sim, days):
    try:
        while sim.elapsed < days:
            sim.policy.step(sim)
    except sim_mod.Wiped:
        pass
    return sim


# ------------------------------------------------------------------ #
# layer 1: the table, the floor, the Wilds                           #
# ------------------------------------------------------------------ #
def _rows(level, skill=None, trials=25):
    random.seed(0)
    probe = act.make_squad(3, level)
    arena_ai, hunt_ai = act.arena_row(3, level, trials), act.hunt_row(3, level, trials)
    fights = [arena_ai, hunt_ai] if skill is None else [
        act.arena_row(3, level, trials, skill=skill, samples=arena_ai.samples),
        act.hunt_row(3, level, trials, skill=skill, samples=hunt_ai.samples)]
    return [act.lumber_row(probe), *fights]


def test_the_floor_a_level_0_squad_eats_and_keeps_a_copper_at_the_lumber_yard():
    checks = act.judge(_rows(0), act.cheapest_meal(), 0)
    assert checks and all(ok for _, ok in checks), checks


def test_the_floor_check_fails_when_the_wage_stops_covering_the_meal(monkeypatch):
    monkeypatch.setattr(economy, "LUMBER_WAGE", 0)
    checks = act.judge(_rows(0), act.cheapest_meal(), 0)
    assert any(not ok for _, ok in checks)


def test_the_wilds_beat_the_lumber_floor_for_a_level_3_squad_that_wins_most_fights():
    checks = act.judge(_rows(3, skill=0.8), act.cheapest_meal(), 3)
    assert any("Wilds hunt" in text for text, _ in checks)
    assert all(ok for _, ok in checks), checks


def test_the_scrapper_is_a_leveling_job_not_judged_for_money():
    rows = {r.name: r for r in _rows(0, skill=0.95)}
    assert rows["Arena: Scrapper"].role == "leveling"
    assert all("Scrapper" not in text for text, _ in act.judge(list(rows.values()), act.cheapest_meal(), 0))
    assert rows["Arena: Scrapper"].combat_xp > 0


def test_the_wilds_cost_a_long_walk_that_the_per_day_figure_pays_for():
    assert act.trip_hours(3, 3, "wilds") >= 8
    hunt = act.hunt_row(3, 3, 20, skill=0.8, samples=act.hunt_row(3, 3, 20).samples)
    assert hunt.runs_per_day < 24 / hunt.hours


def test_one_activity_beats_another_only_when_it_wins_on_money_xp_and_risk():
    from economy_exploits import dominates
    rich = act.Row("rich", 16, income=9.0, combat_xp=1.0, work_marks=1.0)
    poor = act.Row("poor", 16, income=4.0, combat_xp=1.0, work_marks=1.0)
    assert dominates(rich, poor, 3)
    poor.combat_xp = 2.0
    assert not dominates(rich, poor, 3)
    poor.combat_xp, rich.death_rate = 1.0, 0.5
    assert not dominates(rich, poor, 3)


# ------------------------------------------------------------------ #
# layer 2: the fights                                                #
# ------------------------------------------------------------------ #
def test_the_fight_library_plays_real_battles_and_a_skill_picks_the_outcome():
    lib = _lib()
    rng = random.Random(0)
    assert lib.pool("arena", 0, 3) is lib.pool("arena", 0, 3)
    pool = lib.pool("wilds", 0, 3)
    assert {len(s.members) for s in pool} == {3}
    if any(s.won for s in pool):
        assert all(lib.draw("wilds", 0, 3, rng, skill=1.0).won for _ in range(10))
    if any(not s.won for s in pool):
        assert not any(lib.draw("wilds", 0, 3, rng, skill=0.0).won for _ in range(10))


def test_a_lost_fight_kills_and_a_wipe_ends_the_guild():
    sim = _sim()
    party = sim.members
    sample = sim_mod.Sample(False, 10, [(0, True, 0), (2, False, 1), (0, False, 0)], [], 0)
    survivors = sim.apply(sample, party)
    assert len(sim.guild.roster) == 2 and len(survivors) == 2
    assert sim.guild.roster[0].combat_xp >= 1
    wipe = sim_mod.Sample(False, 10, [(0, True, 0), (0, True, 0)], [], 0)
    with pytest.raises(sim_mod.Wiped):
        sim.apply(wipe, survivors)


def test_a_perfect_player_loses_nobody_in_a_fight_the_ai_won_bloodily():
    sample = sim_mod.Sample(True, 5, [(0, True, 0), (0, False, 0), (0, False, 0)], [], 0)
    perfect, average = _sim(), _sim()
    assert len(perfect.apply(sample, perfect.members, relief=0.0)) == 3
    assert len(average.apply(sample, average.members, relief=1.0)) == 2


def test_the_relief_is_one_for_the_ai_and_shrinks_as_the_player_gets_better():
    lib = _lib()
    assert lib.relief("wilds", 0, 3, None) == 1.0
    assert lib.relief("wilds", 0, 3, 1.0) == 0.0
    assert lib.relief("wilds", 0, 3, 0.9) <= lib.relief("wilds", 0, 3, 0.5)


def test_a_won_fight_hands_its_loot_to_the_survivors_to_sell_later():
    sim = _sim()
    sample = sim_mod.Sample(True, 5, [(0, False, 0)] * 3, ["Dagger", "Torch"], 0)
    sim.apply(sample, sim.members)
    assert sim.sellable["Dagger"] == 1 and sim.sellable["Torch"] == 1


def test_the_arena_stake_comes_out_and_the_purse_goes_to_a_winner():
    win = sim_mod.Sample(True, 5, [(2, False, 1)] * 3, [], 11)
    library = sim_mod.FightLibrary(samples=1)
    library.cache[("arena", (0, 0), 3)] = [win]
    sim = _sim(skill=1.0, library=library)
    before = sim.money
    sample = sim.bout()
    assert sample is win
    assert sim.money == before - 3 * len(sim.members) + win.purse
    assert sim.group.node == "arena"


def test_the_arena_refuses_a_squad_that_cannot_pay_the_stake():
    sim = _sim()
    for u in sim.members:
        u.money = 0
    assert sim.bout() is None


# ------------------------------------------------------------------ #
# layer 2: the real engine                                           #
# ------------------------------------------------------------------ #
def test_walking_takes_the_real_route_time_and_stops_where_it_was_sent():
    sim = _sim()
    before = sim.guild.clock.seconds
    sim.goto("market")
    assert sim.group.node == "market"
    assert sim.guild.clock.seconds > before


def test_an_ambush_on_the_road_is_fought_and_the_walk_goes_on(monkeypatch):
    monkeypatch.setattr(world, "ROAD_AMBUSH_CHANCE", 1.0)
    sim = _sim(skill=1.0)
    seen = []
    real = sim.library.draw
    sim.library.draw = lambda kind, *a, **kw: (seen.append(kind), real(kind, *a, **kw))[1]
    sim.goto("wilds")
    assert "road" in seen and sim.group.node == "wilds"


def test_the_floor_policy_lives_a_week_on_the_real_clock_and_stays_fed():
    sim = _run(_sim("lumber"), 7)
    assert len(sim.guild.roster) == 3 and sim.guild.clock.day >= 7
    axes = sum(economy.lumber_level(u) for u in sim.guild.roster)
    assert sim.money + axes * items.get("Axe").price > sim.start_money - 10
    assert all(u.unfed_days == 0 for u in sim.guild.roster)


def test_every_policy_runs_a_few_days_without_breaking():
    for name in ("cautious", "balanced", "greedy", "maxev"):
        sim = _run(_sim(name, seed=2), 4)
        assert sim.snapshots and sim.elapsed >= 4 or not sim.guild.roster, name


def test_a_guild_that_dies_is_reported_as_wiped():
    result = sim_mod.run_guild("greedy", days=15, seed=3, skill=None, library=_lib())
    assert result.members_end <= result.members_start
    assert result.wiped == (result.members_end == 0)


# ------------------------------------------------------------------ #
# layer 2: the market                                                #
# ------------------------------------------------------------------ #
def test_a_market_visit_buys_food_with_the_real_prices_and_the_money_it_has():
    sim = _sim()
    with sim.market() as shop:
        shop.buy_food(5)
    assert sim.rations > 0
    assert sim.money < sim.start_money
    assert sim.guild.shop("market").cash > economy.MARKET_CASH_START


def test_only_what_the_guild_picked_up_is_sold_and_only_up_to_the_markets_cash():
    sim = _sim()
    sim.members[0].give_to_pack("Dagger", 3)
    sim.sellable["Dagger"] = 2
    sim.guild.shop("market").cash = 0
    with sim.market() as shop:
        assert shop.sell_loot() == 0
    with sim.market() as shop:
        price = shop._price("Dagger")
        sim.guild.shop("market").cash = price
        assert shop.sell_loot() == price
    assert sim.members[0].count_of("Dagger") == 2


def test_finite_shelves_run_out_and_refill_each_morning():
    sim = _sim(restock=sim_mod.Restock(2, 1))
    assert sim.guild.shop("market").stock["Iron Bar"] == 2
    sim.guild.shop("market").stock["Iron Bar"] = 0
    sim.sleep(24)
    assert sim.guild.shop("market").stock["Iron Bar"] >= 1


def test_the_tighter_the_shelves_the_less_a_crafter_pulls_out_of_the_market():
    library = _lib()

    def profit(restock):
        runs = [sim_mod.run_guild("crafter", days=12, seed=i, library=library, restock=restock,
                                  recipes=["Bear Trap"], marks=(12,), capital=300)
                for i in range(6)]
        return sum(r.sold - r.input_spend for r in runs)

    assert profit(None) > profit(sim_mod.Restock(1, 1))


# ------------------------------------------------------------------ #
# the milestone, the report and the ranking                          #
# ------------------------------------------------------------------ #
def test_the_milestone_costs_less_for_what_the_guild_already_wears():
    sim = _sim()
    start = sim_mod.milestone_cost(sim)
    sim.members[0].equipped_armor = "Studded Leather"
    assert sim_mod.milestone_cost(sim) == start - items.get("Studded Leather").price
    sim.guild.rent_bank_chest()
    assert sim_mod.milestone_cost(sim) == start - items.get("Studded Leather").price - economy.BANK_CHEST_PRICE


def test_food_in_the_packs_counts_toward_the_milestones_seven_days():
    sim = _sim()
    start = sim_mod.milestone_cost(sim)
    with sim.market() as shop:
        shop.buy_food(5)
    cost_of_food = sim.rations * sim_mod.cheapest_food_price()
    assert sim_mod.milestone_cost(sim) == start - cost_of_food


def test_a_policy_that_never_reaches_the_milestone_reports_no_first_day():
    results = [sim_mod.run_guild("lumber", days=10, seed=i, library=_lib(), marks=(7, 10))
               for i in range(3)]
    summary = sim_mod.summarize(results, (7, 10))
    assert summary["milestone"] == 0 and summary["milestone_day"] is None
    assert "lumber" in sim_mod.report({"lumber": summary}, (7, 10), "label")


def test_the_ranking_averages_what_each_trait_earned_over_the_guilds_that_had_it():
    def result(net, *members):
        return sim_mod.Result("lumber", 0, False, len(members), len(members),
                              money={30: 10 + net * len(members)}, start_money=10,
                              traits=[dict(m) for m in members])

    elf = {"race": "Elf", "occupation": "Barber", "CHA mod": 0}
    orc = {"race": "Orc", "occupation": "Guard", "CHA mod": 2}
    ranked = sim_mod.rank_traits([result(30, elf), result(10, orc),
                                  result(20, {**elf, "occupation": "Guard"})], 30)
    assert ranked["race"]["Elf"][0] == 25 and ranked["race"]["Orc"][0] == 10
    assert ranked["occupation"]["Guard"][0] == 15 and ranked["CHA mod"][2][0] == 10
    assert "best-to-worst spread" in sim_mod.ranking_report(ranked, "x")


def test_a_members_traits_cover_every_attribute_and_the_starting_axe():
    traits = sim_mod.member_traits(Unit("player"))
    assert {"race", "occupation", "languages", "own Axe", "STR mod", "CHA mod"} <= set(traits)
    axe = Unit("player")
    axe.give_to_pack("Axe")
    assert sim_mod.member_traits(axe)["own Axe"] is True


def test_a_what_if_overrides_a_constant_and_an_item_price(monkeypatch):
    monkeypatch.setattr(economy, "LUMBER_WAGE", economy.LUMBER_WAGE)
    original = items.get("Lumber")
    sim_mod.apply_overrides(["economy.LUMBER_WAGE=2"], ["Lumber=9"])
    try:
        assert economy.LUMBER_WAGE == 2 and items.get("Lumber").price == 9
    finally:
        sim_mod.apply_overrides([f"economy.LUMBER_WAGE={economy.LUMBER_WAGE}"], [])
        sim_mod.apply_overrides(["economy.LUMBER_WAGE=1"], [f"Lumber={original.price}"])


def test_the_route_scan_prices_the_walk_between_markets(monkeypatch):
    from economy_exploits import scan_route
    assert scan_route()[0].area == "route"
    monkeypatch.setattr(economy, "MARKET_CASH_REGEN", 400)
    assert scan_route()[0].severity == "FRAGILE"


def test_unit_and_guild_are_the_real_ones():
    guild = _sim().guild
    assert isinstance(guild, Guild) and all(isinstance(u, Unit) for u in guild.roster)


def test_a_house_and_an_animal_drain_the_guild_every_day():
    free, owned = _sim(capital=300, seed=4), _sim(capital=300, seed=4, assets=["house", "Donkey"])
    assert owned.mouths == free.mouths + 1
    _run(free, 14)
    _run(owned, 14)
    assert owned.money < free.money - economy.CITY_PROPERTY_TAX


def test_an_unknown_asset_is_refused():
    with pytest.raises(ValueError):
        _sim(assets=["Dragon"])


def test_the_report_runs_every_part_in_the_plans_order_and_names_what_failed():
    import economy_report as report
    tiny = report.Settings(skill=0.8, trials=6, guilds=2, ranking_guilds=4, fuzz=10,
                           dominance_trials=4, library_samples=4, days=10)
    text, failed = report.build(tiny)
    parts = ("VERDICTS", "EXPLOITS", "ACTIVITIES", "SUSTAIN", "RANKING")
    order = [text.index(f"{i}. {name}") for i, name in enumerate(parts, 1)]
    assert order == sorted(order)
    for verdict in ("floor", "wilds", "day-30 milestone", "no exploit", "no dominant activity"):
        assert f"  {verdict}: " in text
    assert "floor" not in failed and "no exploit" not in failed


# ------------------------------------------------------------------ #
# racial level, the Medic, the Games, the Claim, the tavern          #
# ------------------------------------------------------------------ #
def _win(size=3, loot=()):
    return sim_mod.Sample(True, 5, [(0, False, 0)] * size, list(loot), 0)


def _lost(size=3):
    return sim_mod.Sample(False, 5, [(0, False, 0)] * size, [], 0)


def _fixed(**pools):
    """A library that has only the given pools, `kind=[samples]` at the level-3 squad (3, 3)."""
    library = sim_mod.FightLibrary(samples=1)
    for kind, samples in pools.items():
        library.cache[(kind, (3, 3), 3)] = samples
    return library


def test_a_squad_can_have_a_combat_level_without_the_work_level_and_is_less_tough():
    fighters, workers_too = act.make_squad(2, (2, 0)), act.make_squad(2, (2, 2))
    assert [u.combat_level for u in fighters] == [2, 2] and [u.work_level for u in fighters] == [0, 0]
    assert fighters[0].racial_level < workers_too[0].racial_level


def test_the_fight_library_keys_a_squad_by_both_levels():
    lib = sim_mod.FightLibrary(samples=1)
    assert len(lib.pool("arena", 1, 3)) == 1 and ("arena", (1, 1), 3) in lib.cache
    lib.pool("arena", (1, 0), 3)
    assert ("arena", (1, 0), 3) in lib.cache


def test_the_sim_plays_a_fight_at_the_squads_combat_and_work_levels():
    sim = _sim(level=3)
    assert sim.fight_level == (3, 3)
    for u in sim.members:
        u.set_track_level("work", 1)
    assert sim.fight_level == (3, 1)


def test_the_medic_mends_a_hurt_squad_in_an_hour_for_potions_at_a_discount():
    sim = _sim(medic=True, capital=300)
    victim = sim.members[0]
    victim.hp = max(1, victim.hp_max - 10)
    cost = round(act.medic_cost(victim.hp_max - victim.hp))
    before, hours = sim.money, sim.guild.clock.seconds
    assert sim.treat()
    assert victim.hp == victim.hp_max
    assert sim.money == before - cost and sim.treated == cost
    assert sim.guild.clock.seconds - hours >= 3600


def test_the_medic_turns_away_a_squad_that_could_not_eat_afterwards():
    sim = _sim(medic=True)
    for u in sim.members:
        u.money = 0
    sim.members[0].hp = 1
    assert not sim.treat()
    assert sim.members[0].hp == 1


def test_heal_goes_to_the_medic_when_there_is_one_and_to_a_bed_when_there_is_not():
    with_medic, without = _sim(medic=True, capital=300, level=3), _sim(capital=300, level=3)
    for sim in (with_medic, without):
        sim.members[0].hp = 1
    started = with_medic.guild.clock.seconds
    with_medic.heal()
    without.heal()
    assert with_medic.members[0].hp == with_medic.members[0].hp_max
    assert with_medic.guild.clock.seconds - started < without.guild.clock.seconds - started


def test_medic_costs_follow_the_backlog_formula():
    potion = items.get("Minor Healing Potion").price
    assert act.medic_cost(7) == pytest.approx(2 * potion * act.MEDIC_PRICE_FACTOR)
    assert act.medic_cost(0) == 0


def test_beating_the_champion_opens_the_games_bouts():
    library = _fixed(champion=[_win()])
    sim = _sim(level=3, capital=300, skill=1.0, library=library)
    assert not sim.champion_beaten
    assert sim.bout("champion") is library.cache[("champion", (3, 3), 3)][0]
    assert sim.champion_beaten


def test_the_games_policy_goes_for_the_champion_first_then_the_games():
    games = sim_mod.Games()
    sim = _sim("games", level=3, capital=400, skill=1.0, library=_fixed(
        champion=[_win()], brawl=[_win()], ctf=[_win()]))
    games.upkeep(sim)
    kinds = []
    real = sim.bout
    sim.bout = lambda kind="arena": (kinds.append(kind), real(kind))[1]
    assert games.adventure(sim) and games.adventure(sim)
    assert kinds[0] == "champion" and kinds[1] in ("brawl", "ctf")


def test_a_games_bout_that_loses_money_is_skipped():
    sim = _sim("games", level=3, capital=400, skill=0.05, library=_fixed(brawl=[_lost()], ctf=[_lost()]))
    sim.champion_beaten = True
    assert not sim_mod.Games().adventure(sim)


def test_arena_rows_cover_the_pit_and_the_games_with_a_ai_row_and_a_skilled_row():
    rows = act.arena_rows(3, 3, 6, [0.8], keys=("arena", "brawl"))
    assert set(rows) == {"arena", "brawl"}
    assert set(rows["brawl"]) == {None, 0.8}
    assert rows["brawl"][0.8].name == "Arena: Brawl" and rows["brawl"][0.8].role == "leveling"


def test_the_medic_lifts_the_cap_healing_puts_on_arena_bouts_a_day():
    plain = act.arena_row(3, 3, 8, bout=arena.brawl_bout(), skill=0.8)
    mended = act.arena_row(3, 3, 8, bout=arena.brawl_bout(), skill=0.8, samples=plain.samples, medic=True)
    assert mended.runs_per_day >= plain.runs_per_day
    assert mended.income < plain.income


def _claim_sim(monkeypatch, raids=0.0, **pools):
    monkeypatch.setattr(world, "ROAD_AMBUSH_CHANCE", 0.0)
    monkeypatch.setattr(economy, "WILDS_RAID_CHANCE", raids)
    library = _fixed(**pools)
    sim = _sim("claimer", level=3, capital=400, skill=1.0, library=library, horizon=40)
    return sim


def test_the_claim_campaign_runs_its_stages_and_is_established_after_ten_days(monkeypatch):
    sim = _claim_sim(monkeypatch, claim_clear=[_win()], claim_sweep=[_win()], raid=[_win()])
    sim.claim_run()
    guild = sim.guild
    assert guild.wilds_claim_stage == "ESTABLISHED" and guild.wilds_claim_owner == "guild"
    assert sim.claim_day is not None and sim.claim_lumber > 0
    assert sim.group.node == sim_mod.CLAIM_NODE


def test_a_lost_clearing_fight_ends_the_expedition_at_the_scouted_stage(monkeypatch):
    sim = _claim_sim(monkeypatch, claim_clear=[_lost()])
    sim.claim_run()
    assert sim.guild.wilds_claim_stage == "SCOUTED"


def test_a_raid_the_garrison_loses_starts_the_countdown_over(monkeypatch):
    sim = _claim_sim(monkeypatch, raids=1.0, claim_clear=[_win()], claim_sweep=[_win()], raid=[_lost()])
    sim.horizon = 3
    sim.claim_run()
    guild = sim.guild
    assert guild.wilds_claim_stage == "SUSTAINING"
    assert guild.wilds_claim_sustain_days_left == economy.WILDS_CLAIM_SUSTAIN_DAYS


def test_the_garrison_leaves_when_the_food_runs_low(monkeypatch):
    sim = _claim_sim(monkeypatch, claim_clear=[_win()], claim_sweep=[_win()], raid=[_win()])
    sim.claim_run()
    sim.guild.wilds_claim_stage = "SWEPT"
    for u in sim.members:
        for name, _ in list(u._base_inventory):
            if name in sim_mod.data.FOOD_ITEMS:
                u.remove_named(name, u.count_of(name))
    sim.group.order = None
    sim.hold_claim()
    assert sim.group.order is None


def test_arriving_at_a_seized_claim_means_a_fight_to_retake_it(monkeypatch):
    sim = _claim_sim(monkeypatch, raid=[_win()])
    guild = sim.guild
    guild.wilds_claim_stage, guild.wilds_claim_owner = "ESTABLISHED", "seized"
    sim.goto(sim_mod.CLAIM_NODE)
    assert guild.wilds_claim_owner == "guild"


def test_a_squad_must_afford_the_trip_before_the_claimer_policy_goes():
    sim = _sim("claimer", level=3, skill=1.0, library=_fixed())
    policy = sim_mod.Claimer()
    assert sim.claim_cost() > 0
    assert policy.buffer(sim) > sim_mod.Balanced().buffer(sim)
    assert not policy.adventure(sim)


def test_the_tavern_table_names_the_charisma_from_which_the_stage_beats_the_yard():
    text = act.tavern_table()
    assert "one or the other" in text and "from CHA +2" in text


def test_the_adventure_report_lists_the_ladder_the_claim_and_the_medic():
    table = {"claimer": sim_mod.summarize([sim_mod.run_guild(
        "lumber", days=2, seed=1, library=_lib(), marks=(2,))], (2,))}
    text = sim_mod.adventure_report(table, "t")
    assert "champion" in text and "claimer" in text and "medic $" in text


def test_a_mixed_guild_works_the_yard_while_it_heals_instead_of_resting():
    sim = _sim(mixed=True, level=3, capital=100)
    sim.keep_fed(low=10)
    sim.members[0].hp = max(1, sim.members[0].hp_max - 5)
    before = sim.money
    sim.heal()
    assert sim.money > before and sim.elapsed >= 1


# ------------------------------------------------------------------ #
# a growing guild: recruiting and the crew at the yard               #
# ------------------------------------------------------------------ #
def _stranger(sim):
    stranger = Unit("player")
    stranger.languages = list(sim.members[0].languages)
    return stranger


def _always(ok):
    from gartok import recruit
    return lambda *a, **kw: recruit.Pitch(ok, language="x")


def test_a_pitch_at_the_tavern_that_lands_adds_a_member_for_free(monkeypatch):
    from gartok import recruit
    sim = _sim(capital=50)
    sim.guild.taverna_pool, sim.guild.taverna_week = [_stranger(sim)], recruit.current_week(sim.guild.clock)
    monkeypatch.setattr(recruit, "convince", _always(True))
    before = sim.money
    assert sim.recruit("tavern") == 1
    assert len(sim.guild.roster) == 4 and sim.recruited == 1 and sim.money >= before


def test_the_prison_takes_the_bail_first_and_keeps_it_when_the_pitch_fails(monkeypatch):
    from gartok import recruit
    sim = _sim(capital=500)
    jailed = _stranger(sim)
    sim.guild.prison_pool, sim.guild.prison_week = [jailed], recruit.current_week(sim.guild.clock)
    monkeypatch.setattr(recruit, "convince", _always(False))
    before, bail = sim.money, recruit.bail_cost(jailed)
    assert sim.recruit("prison") == 0
    assert sim.money == before - bail and sim.bail_spent == bail
    assert len(sim.guild.roster) == 3


def test_a_stranger_the_guild_cannot_afford_to_bail_is_left_in_the_cell(monkeypatch):
    from gartok import recruit
    sim = _sim()
    sim.guild.prison_pool, sim.guild.prison_week = [_stranger(sim)], recruit.current_week(sim.guild.clock)
    monkeypatch.setattr(recruit, "convince", _always(True))
    assert sim.recruit("prison", reserve=10**6) == 0 and sim.pitches == 0


def test_the_extras_split_off_as_a_crew_that_works_the_yard_and_pays_the_squad():
    sim = _sim(size=5, level=0, capital=100)
    sim.seat_extras(3)
    assert sim.crew is not None and len(sim.crew.members) == 2 and len(sim.members) == 3
    sim.sleep()
    sim.pass_hours(30, busy=[])
    assert sim.crew.node == "lumber_yard"
    assert sum(u.money for u in sim.crew.members) > 0
    before = sim.money
    sim.crew_pay_in()
    assert sum(u.money for u in sim.crew.members) == 0 and sim.money == before


def test_a_squad_that_dies_ends_the_guild_even_if_the_crew_lives():
    sim = _sim(size=5)
    sim.seat_extras(3)
    sim.guild.remove_members(list(sim.main.members))
    with pytest.raises(sim_mod.Wiped):
        _ = sim.group

"""Economy sim v2, layer 1: what each activity pays a level-N squad, in copper and in XP.

Plan: docs/plans/economy_sim_v2.md. Every number comes from the real rules -- wages from
`economy`, hunt time and ambushes from `hunt`, fights from `Battle` + `ai`, loot from
`loot.field_loot`, XP from `progression` -- never a parallel model. Fights are replayed
`--trials` times, so risk is a measured rate that moves when combat changes.

Each activity has a role and a level band (`ROLES`); only rows inside the band for the
squad's level are judged:

  floor        lumber: a squad eats and keeps FLOOR_MARGIN copper a day, whatever its skill
  leveling     the Scrapper bout, then the Games (brawl, capture the flag): not money jobs, they
               lift a squad to combat level 1 and then up the ladder; the Wilds pay little XP
  income       the Wilds: out-earns the floor once the squad is level 2-3
  one-off      the champion bout and the Ribbit Brothers: a gate and a capstone, shown not judged
  side income  the tavern stage

The AI plays the squad badly next to a person, so a fight's win rate is a parameter:
the AI's own is shown first, then `--skills` for a player who wins that share.

    python scripts/economy_activities.py                       # level 0: floor + leveling
    python scripts/economy_activities.py --level 3             # the Wilds' band
    python scripts/economy_activities.py --level 3 --skills 0.5,0.8
"""

from __future__ import annotations

import argparse
import math
import os
import random
import statistics
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gartok import (
    ai,
    arena,
    data,
    economy,
    hunt,
    items,
    loot,
    matchup,
    orders,
    progression,
    world,
)
from gartok.battle import Battle
from gartok.guild import Guild
from gartok.guild_upkeep import HOURS_PER_HEAL, rest_heal
from gartok.scenario import ErmosScenario
from gartok.unit import Unit

WORK_DAY_HOURS = 16          # the longest shift the yard and the hunt offer
FLOOR_MARGIN = 1             # copper a member keeps after eating, doing the floor job
TURN_GUARD = 600
SECONDS_PER_HOUR = 3600
ROUND_SECONDS = 6
MEDIC_POTION_HP = 3.5        # HP one Minor Healing Potion restores (backlog B1)
MEDIC_PRICE_FACTOR = 0.7     # the Medic sells the potions it uses at this share of the catalogue price

# activity -> (role, lowest level, highest level) the squad is meant to do it at
ROLES = {
    "Lumber yard": ("floor", 0, 1),
    "Tavern show": ("side income", 0, 1),
    "Arena: Scrapper": ("leveling", 0, 0),
    "Arena: Challenge the Champion": ("one-off", 1, 4),
    "Arena: Brawl": ("leveling", 2, 5),
    "Arena: Capture the Flag": ("leveling", 2, 5),
    "Arena: The Ribbit Brothers": ("one-off", 3, 6),
    "Wilds hunt": ("income", 2, 4),
}

# the staked bouts, in the order the arena unlocks them; the boss needs six on the field
BOUTS = {
    "arena": arena.scrapper_bout,
    "champion": arena.champion_bout,
    "brawl": arena.brawl_bout,
    "ctf": arena.ctf_bout,
    "boss": arena.boss_bout,
}


def cheapest_meal():
    return min(items.get(n).price for n in data.FOOD_ITEMS if n != "Rotten Food")


def make_squad(size, level, team="player"):
    """`level` is one number for both tracks, or `(combat, work)`. The racial level (hit dice)
    is the two tracks added up, so a squad that only fights is not as tough as one that also works."""
    combat, work = level if isinstance(level, tuple) else (level, level)
    squad = []
    for _ in range(size):
        u = Unit(team)
        if combat:
            u.set_track_level("combat", combat)
        if work:
            u.set_track_level("work", work)
        squad.append(u)
    return squad


def medic_cost(damage):
    """Copper the Medic (backlog B1) charges to bring a member back from `damage` HP lost:
    the potions it would take, at a discount. Not built yet: the numbers are the backlog's."""
    return math.ceil(damage / MEDIC_POTION_HP) * items.get("Minor Healing Potion").price * MEDIC_PRICE_FACTOR


def rest_hp_per_day(squad):
    """HP a resting squad heals in a day (`rest_heal` every `HOURS_PER_HEAL` h, per member).
    A squad that works all day heals only in its sleep, one stretch in three: layer 2 shows it."""
    return statistics.mean(rest_heal(u) for u in squad) * 24 / HOURS_PER_HEAL


def trip_hours(size, level, node_id, samples=12):
    """Hours the real order engine takes to walk a squad from the City to `node_id`, averaged
    over random squads (speed depends on the members and what they carry). Leaves the global
    random state as it found it, so a seeded run is not disturbed."""
    state = random.getstate()
    try:
        speeds = [Guild(make_squad(size, level), node="city").groups[0].speed
                  for _ in range(samples)]
    finally:
        random.setstate(state)
    distance = world.route("city", node_id)[1]
    return statistics.mean(world.hours(distance, speed) for speed in speeds)


def play(squad, enemies, scenario, lethal):
    """One headless battle. Returns the Battle."""
    battle = Battle(list(squad), list(enemies), scenario=scenario, daylight=True, lethal=lethal)
    guard = 0
    while battle.winner is None and guard < TURN_GUARD:
        guard += 1
        ai.take_turn(battle, battle.active)
    return battle


def loot_value(pool):
    """Copper the market would pay for a loot pool (coins at face value)."""
    total = 0
    for name in pool:
        if items.is_coin(name):
            total += items.COIN_VALUE[name]
        else:
            total += economy.sell_price(name)
    return total


def days_to_next(thresholds, level, per_day):
    """Days of `per_day` XP to climb from `level` to the next, None if it never will."""
    if per_day <= 0 or level >= len(thresholds):
        return None
    prev = thresholds[level - 1] if level else 0
    return (thresholds[level] - prev) / per_day


def work_marks(hours, activity_level, worker_level):
    """Work-XP marks `hours` of a job bank for a worker (16 banked hours = 1 mark)."""
    return progression.work_xp_hours(hours, activity_level, worker_level) / economy.LUMBER_XP_HOURS


@dataclass
class Row:
    name: str
    hours: float                       # clock hours one run of the activity takes
    income: float = 0.0                # copper per member per run, before eating
    combat_xp: float = 0.0             # combat XP per member per run
    work_marks: float = 0.0            # work-XP marks per member per run
    food_kg: float = 0.0               # meat brought home per member per run (not counted in income)
    stake: float = 0.0                 # copper per member put up and lost on a defeat
    win_rate: float | None = None
    death_rate: float = 0.0            # fraction of members lost per run
    damage: float = 0.0                # average HP lost per member per run
    runs_per_day: float = 1.0          # how many times a day the squad can really do it
    trip_hours: float = 0.0            # one way from the City, walked there and back each run
    note: str = ""
    samples: list = field(default_factory=list)

    @property
    def per_day(self):
        return self.income * self.runs_per_day

    @property
    def role(self):
        return ROLES[self.name][0]

    def in_band(self, level):
        _, lo, hi = ROLES[self.name]
        return lo <= level <= hi


def lumber_row(squad, shift=WORK_DAY_HOURS):
    pay = statistics.mean(economy.lumber_pay(shift, economy.lumber_level(u)) for u in squad)
    marks = statistics.mean(work_marks(shift, economy.lumber_level(u), u.work_level) for u in squad)
    return Row("Lumber yard", shift, income=pay, work_marks=marks,
               note="own Axe pays 4/3 and teaches twice as fast (starting kit decides)")


def tavern_row(squad, shift=WORK_DAY_HOURS):
    """Judged per performer: only a member with a Musical Instrument can take the stage."""
    singers = [u for u in squad if economy.can_perform(u)]
    if not singers:
        return None
    tips = statistics.mean(economy.perform_expected(shift, data.mod(u.charisma)) for u in singers)
    marks = statistics.mean(work_marks(shift, economy.PERFORM_LEVEL, u.work_level) for u in singers)
    return Row("Tavern show", shift, income=tips, work_marks=marks,
               note=f"per performer; {len(singers)}/{len(squad)} own an instrument")


def tavern_table(shift=WORK_DAY_HOURS):
    """A day on the tavern's stage replaces a day at the yard (one body, one place), so the show
    only earns its keep from the Charisma at which its tips beat the wage. -> text."""
    yard, yard_axe = economy.lumber_pay(shift, 0), economy.lumber_pay(shift, economy.LUMBER_LEVEL_OWN_AXE)
    lines = [f"== the tavern against the yard, {shift} h a day (one or the other, never both)",
             f"   yard ${yard} ({yard_axe} with an Axe of your own); a show needs a Musical Instrument",
             f"{'CHA mod':>8}{'tips/day':>10}  beats the yard?"]
    first = None
    for cha in range(-2, 6):
        tips = economy.perform_expected(shift, cha)
        beats = "with an Axe" if tips > yard_axe else ("without an Axe" if tips > yard else "no")
        if first is None and tips > yard_axe:
            first = cha
        lines.append(f"{cha:>+8}{tips:>10.1f}  {beats}")
    lines.append(f"   the stage out-earns even an Axe-armed lumberjack from CHA {first:+d}"
                 if first is not None else "   the stage never out-earns the yard in this range")
    return "\n".join(lines)


def arena_row(size, level, trials, bout=None, skill=None, samples=None, medic=False):
    """A staked arena bout (the Pit's Scrapper, the champion, the Games). Non-lethal, so the
    cost of losing is the stake and the HP. `skill` replaces the AI's measured win rate with a
    player win probability. With a `medic` the bouts a day are not capped by healing: each
    member's damage is paid for in potions instead."""
    bout = bout or arena.scrapper_bout()
    if samples is None:
        samples = []
        for _ in range(trials):
            squad = make_squad(size, level)
            foes, scenario = matchup.build(world.node("arena"), bout, squad_size=size,
                                           guild=Guild(squad, node="city"))
            b = play(squad, foes, scenario, lethal=False)
            dmg = statistics.mean(max(0, u.hp_max - c.hp) for c, u in zip(b.player_units, squad))
            xp = statistics.mean(c.combat_xp_earned for c in b.player_units)
            samples.append((b.winner == "player", b.round_no, dmg, xp))
    won = [x for x in samples if x[0]] or samples
    lost = [x for x in samples if not x[0]] or samples
    ai_rate = sum(x[0] for x in samples) / len(samples)
    p = ai_rate if skill is None else skill
    mean = statistics.mean
    damage = mean(x[2] for x in samples) if skill is None else mean(x[2] for x in won)
    xp = p * mean(x[3] for x in won) + (1 - p) * mean(x[3] for x in lost)
    break_even = bout.entry * size / bout.purse
    squad = make_squad(size, level)
    trip = trip_hours(size, level, "arena")
    heal_cap = rest_hp_per_day(squad) / damage if damage else 1.0
    cycle_cap = 24 / (2 * trip + orders.APPROACH_HOURS)
    cure = medic_cost(damage) if medic else 0.0
    cap = (f"a {trip:.0f} h walk each way; the Medic mends {damage:.0f} HP for ${cure:.1f} a member"
           if medic else
           f"capped by healing ({rest_hp_per_day(squad):.0f} HP/day at rest) and a {trip:.0f} h walk each way")
    return Row(f"Arena: {bout.name.split(': ')[-1]}",
               mean(x[1] for x in samples) * ROUND_SECONDS / SECONDS_PER_HOUR,
               income=p * bout.purse / size - bout.entry - cure, combat_xp=xp, stake=bout.entry,
               win_rate=p, damage=damage,
               runs_per_day=cycle_cap if medic else min(heal_cap, cycle_cap), trip_hours=trip,
               samples=samples,
               note=(f"purse {bout.purse} split {size} ways, entry {bout.entry} each: break-even "
                     f"at {break_even * 100:.0f}% wins (AI wins {ai_rate * 100:.0f}%); bouts/day are {cap}"))


def arena_rows(size, level, trials, skills, medic=False, keys=None):
    """Every bout the Pit and the Games offer (or just `keys`): `{key: {None: AI row, skill: row,
    ...}}`. The boss (six a side) is played by a squad of six, whatever `size` is."""
    out = {}
    for key, make in BOUTS.items():
        if keys is not None and key not in keys:
            continue
        n = arena.BOSS_SQUAD if key == "boss" else size
        ai_row = arena_row(n, level, trials, bout=make(), medic=medic)
        out[key] = {None: ai_row}
        for skill in skills:
            out[key][skill] = arena_row(n, level, trials, bout=make(), skill=skill,
                                        samples=ai_row.samples, medic=medic)
    return out


def _hunt_live(size, level, trials, shift):
    """Hunts played out with real battles on the AI's side. Returns the per-fight samples
    `(won, loot_value, dead_fraction, xp_per_living_member)`, the meat and the hours spent."""
    fights = []
    meat = hours_used = 0
    for _ in range(trials):
        squad = make_squad(size, level)
        state = hunt.HuntState(party=squad, node=None, hours_left=shift)
        alive = list(squad)
        while state.hours_left > 0 and alive:
            _, ambushed = hunt.hunt_stretch(state)
            if not ambushed:
                continue
            b = play(alive, hunt.wilds_pack(), ErmosScenario(), lethal=True)
            dead = [u for c, u in zip(b.player_units, alive) if not c.alive]
            won = b.winner == "player"
            value = loot_value(loot.field_loot(
                b, [c for c in b.player_units if not c.alive])) if won else 0
            xp = statistics.mean(c.combat_xp_earned for c in b.player_units)
            fights.append((won, value, len(dead) / len(alive), xp))
            alive = [u for u in alive if u not in dead]
            state.party = alive
            if not won:
                break
        hours_used += shift - state.hours_left
        meat += state.meat
    return fights, meat, hours_used


def _hunt_skilled(size, level, trials, shift, skill, fights, rng):
    """The same hunt with each ambush won at probability `skill`; loot, XP and casualties
    are drawn from the fights the AI actually played, split by outcome. A better player also
    loses fewer members in the fights he wins: casualties in wins scale by `relief`,
    1 at the AI's own win rate down to 0 at a perfect record (an assumption, not data)."""
    won_pool = [f for f in fights if f[0]] or [(True, 0, 0.0, 0.0)]
    lost_pool = [f for f in fights if not f[0]] or [(False, 0, 1.0, 0.0)]
    ai_rate = sum(f[0] for f in fights) / len(fights) if fights else 0.0
    relief = min(1.0, (1 - skill) / (1 - ai_rate)) if ai_rate < 1 else 1.0
    meat = hours_used = loot_total = dead_total = xp_total = 0
    for _ in range(trials):
        state = hunt.HuntState(party=make_squad(size, level), node=None, hours_left=shift)
        while state.hours_left > 0 and state.party:
            _, ambushed = hunt.hunt_stretch(state, rng)
            if not ambushed:
                continue
            won = rng.random() < skill
            _, value, frac, xp = rng.choice(won_pool if won else lost_pool)
            loot_total += value
            xp_total += xp * len(state.party)
            dead = sum(rng.random() < frac * (relief if won else 1.0) for _ in state.party)
            state.party = state.party[dead:]
            dead_total += dead
            if not won:
                break
        hours_used += shift - state.hours_left
        meat += state.meat
    return meat, hours_used, loot_total, dead_total, xp_total


def hunt_row(size, level, trials, shift=WORK_DAY_HOURS, skill=None, samples=None):
    """A full-day hunt: meat by the hour, an ambush every ~7 h, loot off the winners."""
    trip = trip_hours(size, level, "wilds")
    if skill is None:
        fights, meat, hours_used = _hunt_live(size, level, trials, shift)
        loot_total = sum(f[1] for f in fights)
        dead_total = sum(f[2] * size for f in fights)
        xp_total = sum(f[3] * size for f in fights)
        win = sum(f[0] for f in fights) / len(fights) if fights else None
        note = f"meat is food, not copper; {len(fights) / trials:.1f} ambushes/run"
    else:
        fights = samples
        meat, hours_used, loot_total, dead_total, xp_total = _hunt_skilled(
            size, level, trials, shift, skill, fights, random.Random(trials))
        win = skill
        ai_rate = sum(f[0] for f in fights) / len(fights) if fights else 0
        note = f"meat is food, not copper; the AI wins {ai_rate * 100:.0f}% of these ambushes"
    note += (f"; a {trip:.0f} h walk each way (the Old Road's {world.ROAD_AMBUSH_CHANCE * 100:.0f}% "
             "ambush per pass is layer 2's)")
    hunted = hours_used / trials
    marks = work_marks(hunted, hunt.HUNT_LEVEL, level)
    return Row("Wilds hunt", hunted, income=loot_total / trials / size, trip_hours=trip,
               runs_per_day=24 / (hunted + 2 * trip + orders.APPROACH_HOURS),
               combat_xp=xp_total / trials / size, work_marks=marks,
               food_kg=meat / trials / size, win_rate=win,
               death_rate=dead_total / trials / size, samples=fights, note=note)


def judge(rows, meal, level):
    """-> [(check, ok)] for the rows whose band holds `level`. The floor job must clear
    FLOOR_MARGIN after the meal; an income job must out-earn the lumber floor (net of meal)."""
    lumber = next((r for r in rows if r.name == "Lumber yard"), None)
    checks = []
    for r in rows:
        if not r.in_band(level):
            continue
        net = r.per_day - meal
        if r.role == "floor":
            checks.append((f"{r.name}: net {net:+.2f}/member/day, need >= {FLOOR_MARGIN:+d}",
                           net >= FLOOR_MARGIN))
        elif r.role == "income" and lumber is not None:
            floor = lumber.per_day - meal
            text = (f"{r.name}: net {net:+.2f}/member/day, must beat the lumber floor "
                    f"({floor:+.2f})")
            checks.append((text, net > floor))
    return checks


def report(rows, meal, size, level, label=""):
    lines = [(f"== {label} -- squad of {size}, level {level}; cheapest meal "
              f"${meal}/member/day; day = {WORK_DAY_HOURS} h"), ""]
    lines.append(f"{'activity':<17}{'role':<12}{'hours':>6}{'$/run':>7}{'win%':>6}{'dead%':>6}"
                 f"{'cXP/d':>7}{'wXP/d':>7}{'d>C+1':>7}{'d>W+1':>7}{'meat':>6}{'net/day':>9}")
    for r in rows:
        win = f"{r.win_rate * 100:.0f}" if r.win_rate is not None else "-"
        unit = next(iter(make_squad(1, level)))
        dc = days_to_next(progression.COMBAT_XP_THRESHOLDS, unit.combat_level,
                          r.combat_xp * r.runs_per_day)
        dw = days_to_next(progression.WORK_XP_THRESHOLDS, unit.work_level,
                          r.work_marks * r.runs_per_day)
        fmt = lambda v: f"{v:.1f}" if v is not None else "-"
        flag = "" if r.in_band(level) else "*"
        lines.append(f"{r.name + flag:<17}{r.role:<12}{r.hours:>6.2f}{r.income:>7.2f}{win:>6}"
                     f"{r.death_rate * 100:>6.0f}{r.combat_xp * r.runs_per_day:>7.2f}"
                     f"{r.work_marks * r.runs_per_day:>7.2f}{fmt(dc):>7}{fmt(dw):>7}"
                     f"{r.food_kg:>6.2f}{r.per_day - meal:>9.2f}")
    lines.append("   (* outside its level band: shown, not judged; d>C+1 / d>W+1 = days to the next "
                 "combat / work level)")
    lines.append("")
    for r in rows:
        if r.note:
            lines.append(f"  {r.name}: {r.note}")
    lines.append("")
    checks = judge(rows, meal, level)
    for text, ok in checks:
        lines.append(f"{'PASS' if ok else 'FAIL'}  {text}")
    if not checks:
        lines.append("(no activity is judged at this level)")
    return "\n".join(lines), all(ok for _, ok in checks)


def build_tables(level, size, trials, skills, medic=False):
    """The layer-1 tables for a squad: `[(skill, label, rows)]`, the AI's own win rate first
    (`skill` None), then one per player skill; and the cheapest meal they are judged against.
    The Games are shown from level 1, where a squad can first reach the champion."""
    probe = make_squad(size, level)
    fixed = [r for r in (lumber_row(probe), tavern_row(probe)) if r]
    bouts = arena_rows(size, level, trials, skills, medic=medic)
    hunt_ai = hunt_row(size, level, trials)
    suffix = ", with a Medic" if medic else ""
    tables = [(None, "the AI plays the squad" + suffix,
               fixed + [b[None] for b in bouts.values()] + [hunt_ai])]
    for skill in skills:
        fights = [b[skill] for b in bouts.values()]
        fights.append(hunt_row(size, level, trials, skill=skill, samples=hunt_ai.samples))
        tables.append((skill, f"the player wins {skill * 100:.0f}% of fights" + suffix,
                       fixed + fights))
    return cheapest_meal(), tables


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", type=int, default=0)
    ap.add_argument("--squad", type=int, default=3)
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--skills", default="0.8,0.95",
                    help="player win probabilities shown beside the AI's own")
    ap.add_argument("--judge", type=float, default=0.8,
                    help="the skill the verdict and the exit code use")
    ap.add_argument("--medic", action="store_true",
                    help="bouts are healed by the Medic (backlog B1), paid in potions, not by resting")
    ap.add_argument("--medic-factor", type=float, default=None, metavar="F",
                    help=f"the Medic's price as a share of the potions (backlog: {MEDIC_PRICE_FACTOR})")
    args = ap.parse_args()
    random.seed(args.seed)
    if args.medic_factor is not None:
        globals()["MEDIC_PRICE_FACTOR"] = args.medic_factor

    meal, tables = build_tables(args.level, args.squad, args.trials,
                                [float(x) for x in args.skills.split(",")], medic=args.medic)
    verdict = True
    for skill, label, rows in tables:
        text, ok = report(rows, meal, args.squad, args.level, label)
        print(text + "\n")
        if skill == args.judge:
            verdict = ok
    sys.exit(0 if verdict else 1)


if __name__ == "__main__":
    main()

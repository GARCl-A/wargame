"""Economy sim v2, layer 1: what each activity pays a level-N squad, in copper and in XP.

Plan: docs/plans/economy_sim_v2.md. Every number comes from the real rules -- wages from
`economy`, hunt time and ambushes from `hunt`, fights from `Battle` + `ai`, loot from
`loot.field_loot`, XP from `progression` -- never a parallel model. Fights are replayed
`--trials` times, so risk is a measured rate that moves when combat changes.

Each activity has a role and a level band (`ROLES`); only rows inside the band for the
squad's level are judged:

  floor        lumber: a squad eats and keeps FLOOR_MARGIN copper a day, whatever its skill
  leveling     the Scrapper bout: not a money job, it lifts a squad to combat level 1
  income       the Wilds: out-earns the floor once the squad is level 2-3
  side income  the tavern stage

The AI plays the squad badly next to a person, so a fight's win rate is a parameter:
the AI's own is shown first, then `--skills` for a player who wins that share.

    python scripts/economy_activities.py                       # level 0: floor + leveling
    python scripts/economy_activities.py --level 3             # the Wilds' band
    python scripts/economy_activities.py --level 3 --skills 0.5,0.8
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gartok import ai, arena, data, economy, encounters, hunt, items, loot, progression
from gartok.battle import Battle
from gartok.scenario import ArenaScenario, ErmosScenario
from gartok.unit import Unit

WORK_DAY_HOURS = 16          # the longest shift the yard and the hunt offer
FLOOR_MARGIN = 1             # copper a member keeps after eating, doing the floor job
REST_HP_PER_DAY = 3          # natural healing at CON mod 0: 1 HP per 8 h (backlog, Medic B1)
TURN_GUARD = 600
SECONDS_PER_HOUR = 3600
ROUND_SECONDS = 6

# activity -> (role, lowest level, highest level) the squad is meant to do it at
ROLES = {
    "Lumber yard": ("floor", 0, 1),
    "Tavern show": ("side income", 0, 1),
    "Arena: Scrapper": ("leveling", 0, 0),
    "Wilds hunt": ("income", 2, 4),
}


def cheapest_meal():
    return min(items.get(n).price for n in data.FOOD_ITEMS if n != "Rotten Food")


def make_squad(size, level, team="player"):
    squad = []
    for _ in range(size):
        u = Unit(team)
        if level:
            u.set_track_level("combat", level)
            u.set_track_level("work", level)
        squad.append(u)
    return squad


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


def arena_row(size, level, trials, bout=None, skill=None, samples=None):
    """The staked Pit bout. Non-lethal, so the cost of losing is the stake and the HP.
    `skill` replaces the AI's measured win rate with a player win probability."""
    bout = bout or arena.scrapper_bout()
    if samples is None:
        samples = []
        for _ in range(trials):
            squad = make_squad(size, level)
            foes = [encounters.build_enemy(bout.level) for _ in range(bout.enemies)]
            b = play(squad, foes, ArenaScenario(), lethal=False)
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
    return Row(f"Arena: {bout.name.split(': ')[-1]}",
               mean(x[1] for x in samples) * ROUND_SECONDS / SECONDS_PER_HOUR,
               income=p * bout.purse / size - bout.entry, combat_xp=xp, stake=bout.entry,
               win_rate=p, damage=damage,
               runs_per_day=REST_HP_PER_DAY / damage if damage else 1.0, samples=samples,
               note=(f"purse {bout.purse} split {size} ways, entry {bout.entry} each: break-even "
                     f"at {break_even * 100:.0f}% wins (AI wins {ai_rate * 100:.0f}%); "
                     f"bouts/day are capped by healing ({REST_HP_PER_DAY} HP/day)"))


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
    hunted = hours_used / trials
    marks = work_marks(hunted, hunt.HUNT_LEVEL, level)
    return Row("Wilds hunt", hunted, income=loot_total / trials / size,
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
    args = ap.parse_args()
    random.seed(args.seed)

    probe = make_squad(args.squad, args.level)
    fixed = [r for r in (lumber_row(probe), tavern_row(probe)) if r]
    arena_ai = arena_row(args.squad, args.level, args.trials)
    hunt_ai = hunt_row(args.squad, args.level, args.trials)
    meal = cheapest_meal()

    verdict = True
    for skill in [None, *[float(x) for x in args.skills.split(",")]]:
        if skill is None:
            fights = [arena_ai, hunt_ai]
            label = "the AI plays the squad"
        else:
            fights = [arena_row(args.squad, args.level, args.trials, skill=skill,
                                samples=arena_ai.samples),
                      hunt_row(args.squad, args.level, args.trials, skill=skill,
                               samples=hunt_ai.samples)]
            label = f"the player wins {skill * 100:.0f}% of fights"
        text, ok = report(fixed + fights, meal, args.squad, args.level, label)
        print(text + "\n")
        if skill == args.judge:
            verdict = ok
    sys.exit(0 if verdict else 1)


if __name__ == "__main__":
    main()

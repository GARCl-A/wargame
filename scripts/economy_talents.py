"""What each work talent is worth, priced directly: one member with and without it.

A 30-day guild in `economy_guild.py` reaches two work picks at most, so the report's sustain runs
never see most of the work tree. This prices every talent on its own, from the rules that read it:
the yard's wage, the tavern's tips, `rest_heal`, the stagger threshold, `travel_mult`, the hunt's
hide, the deal fraction. A row's worth is in its own unit (hours, kg, HP, points of a roll); `$/day`
is that worth in copper on a day spent doing the thing it helps, blank when no day of the economy
turns on it (an attribute's combat weight is `balance_sim.py`'s STATS section).

Hours are priced at the yard's wage with an Axe of your own, HP at the Medic's price.

    python scripts/economy_talents.py
"""

from __future__ import annotations

import os
import random
import statistics
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(SCRIPTS))

import economy_activities as act

from gartok import animals, data, economy, items, magic, talents, vocations, world
from gartok.guild import Guild
from gartok.guild_upkeep import (
    HARDENED_NONLETHAL_CLEAR,
    HOURS_PER_HEAL,
    HOURS_PER_NONLETHAL_CLEAR,
    rest_heal,
)
from gartok.unit import Unit

DAY = act.WORK_DAY_HOURS
SAMPLES = 200                  # random members a row averages over
WORK_LEVEL = 5                 # enough picks for any talent and the two it requires
RACIAL_LEVEL = 3               # hit dice of the member resting: rest heals racial level x CON
CREW = 3
AXE = economy.LUMBER_LEVEL_OWN_AXE


def wage_per_hour():
    return economy.lumber_pay(DAY, AXE) / DAY


def copper_per_hp():
    return items.get("Minor Healing Potion").price * economy.MEDIC_PRICE_FACTOR / economy.MEDIC_POTION_HP


def _chain(talent_id):
    """The talent and every one it requires, root first."""
    out = []
    while talent_id:
        out.insert(0, talent_id)
        talent_id = talents.get(talent_id).requires
    return out


def pair(talent_id, rng):
    """Two copies of one random member at `WORK_LEVEL`: without the talent, and with it (the
    talents it requires are on both, so the gap is the talent's own)."""
    state, seed = random.getstate(), rng.random()
    try:
        twins = []
        for _ in range(2):
            random.seed(seed)
            twins.append(Unit("player"))
    finally:
        random.setstate(state)
    base, other = twins
    for u in twins:
        u.set_track_level("work", WORK_LEVEL)
        u.set_track_level("racial", RACIAL_LEVEL)
    chain = _chain(talent_id)
    for tid in chain[:-1]:
        base.choose_talent("work", tid)
        other.choose_talent("work", tid)
    other.choose_talent("work", chain[-1])
    return base, other


def mean_gap(talent_id, measure, samples=SAMPLES, seed=0):
    rng = random.Random(seed)
    return statistics.mean(measure(b) - measure(a) for a, b in (pair(talent_id, rng) for _ in range(samples)))


def fits(unit, name):
    """How many `name` the member packs on top of their kit before staggering."""
    n = 0
    while n < 200:
        unit.give_to_pack(name)
        unit._derive_combat()
        if unit.encumbered:
            break
        n += 1
    unit.remove_named(name, n + 1)
    unit._derive_combat()
    return n


def hours_to_full(heal_per_stretch, missing):
    return -(-missing // max(1, heal_per_stretch)) * HOURS_PER_HEAL


def p_contest(edge):
    """The chance a d20 + `edge` meets or beats a d20 (ties go to the roller)."""
    return sum(1 for a in range(1, 21) for b in range(1, 21) if a + edge >= b) / 400


def p_check(edge, dc):
    return sum(1 for r in range(1, 21) if r + edge >= dc) / 20


def mean_roll(edge):
    return statistics.mean(max(1, r + edge) for r in range(1, 21))


def trip_hours(node_id, mult=1.0):
    """Hours a fresh crew of `CREW` walks from the City to `node_id` and back."""
    state = random.getstate()
    try:
        random.seed(7)
        speed = Guild(act.make_squad(CREW, 0), node="city").groups[0].speed
    finally:
        random.setstate(state)
    return 2 * world.hours(world.route("city", node_id)[1], speed) * mult


# --------------------------------------------------------------------------- #
# one row per talent: (worth, unit, $ a day, how)                             #
# --------------------------------------------------------------------------- #
def _haul(tid):
    lumber = mean_gap(tid, lambda u: fits(u, "Lumber"), samples=60)
    ore = mean_gap(tid, lambda u: fits(u, "Iron Ore"), samples=60)
    return (lumber, "Lumber", None,
            (f"carried back before staggering (+{ore:.1f} Iron Ore); "
             f"${lumber * economy.sell_price('Lumber'):.0f} more a trip home from gathering"))


def _piecework(tid):
    gain = economy.lumber_pay(DAY, AXE) * talents.COIN_BONUS
    return (gain, "$", gain, f"on a {DAY} h yard wage with an Axe; also tips and the supply run")


def _brisk(tid):
    saved = DAY * talents.ACTIVITY_SPEEDUP
    return (saved, "h", saved * wage_per_hour(), f"of a {DAY} h shift handed back, priced at the wage")


def _steady(tid):
    rng = random.Random(0)
    hp = statistics.mean(rest_heal(pair(tid, rng)[1]) for _ in range(SAMPLES)) * DAY / HOURS_PER_HEAL
    wage = economy.lumber_pay(DAY, AXE)
    return (DAY, "h", wage, (f"of rest a wounded member works through instead ({hp:.1f} HP healed "
                             f"a {DAY} h shift); worth the day's wage, the Medic would charge "
                             f"${hp * copper_per_hp():.0f}"))


def _tips(tid):
    def tips(u):
        bonus = int(u.talent_bonus("tavern_perform_bonus"))
        return economy.perform_expected(DAY, u.mod_charisma + bonus)
    gain = mean_gap(tid, tips)
    return (gain, "$", gain, f"tips on a {DAY} h stage (needs a Musical Instrument)")


def _negotiator(tid):
    step = mean_gap(tid, lambda u: u.haggle_charisma_mod) * economy.CHA_DEAL_STEP
    return (step * 100, "$/100", None, "off every $100 bought or onto every $100 sold, when they speak")


def _fixer(tid):
    gain = p_contest(1) - p_contest(0)
    return (gain * 100, "pp", None, "on a recruit pitch against an even Charisma")


def _provisioner(tid):
    saved = CREW * act.cheapest_meal() * economy.CHA_DEAL_STEP
    return (saved, "$", saved, f"a day off {CREW} mouths of the cheapest meal")


def _craft(recipe):
    goal = items.recipe_goal(items.get_recipe(recipe))

    def make(tid):
        before = goal / mean_roll(0)
        after = goal / mean_roll(1)
        return (before - after, "h", (before - after) * wage_per_hour(),
                f"off a {before:.1f} h batch of {recipe} at INT +0")
    return make


def _clever(tid):
    goal = items.recipe_goal(items.get_recipe("Jerky"))
    edge = mean_gap(tid, lambda u: u.mod_intelligence)
    saved = goal / mean_roll(0) - goal / mean_roll(edge)
    return (edge, "INT mod", None, f"on average; {saved:.2f} h off a batch of Jerky, and every INT check")


def _linguist(tid):
    goal = magic.points_to_learn(0)
    before, after = goal / mean_roll(0), goal / mean_roll(2)
    return (before - after, "days", None, f"off {before:.0f} days of study to learn a language")


def _recipe(tid):
    return (None, "", None, "a random recipe of the shop; the crafter policy prices recipes")


def _attr(stat):
    def make(tid):
        edge = mean_gap(tid, lambda u: getattr(u, f"mod_{stat}"))
        return (edge, f"{stat[:3].upper()} mod", None, "on average; its combat weight: balance_sim.py STATS")
    return make


def _skinner(tid):
    hide = economy.sell_price("1sqm Hide")
    return (1, "Hide", hide, f"a hunt with meat, sold for ${hide} (the tanner keeps no target)")


def _fletcher(tid):
    return (data.QUIVER_AMMO, "arrows", None,
            f"a quiver topped up on rest for 1 Lumber (${items.get('Lumber').price})")


def _wheelwright(tid):
    return (2, "x HP", None, "per repair: half the Lumber and the hours on a broken wagon")


def _sturdy(tid):
    gain = mean_gap(tid, rest_heal)
    hp = mean_gap(tid, lambda u: u.hp_max)
    return (gain, "HP/8 h", None, f"of rest at racial level {RACIAL_LEVEL}; +{hp:.1f} max HP")


def _reserves(tid):
    meal = act.cheapest_meal()
    return (1, "meal", None, f"a day without food before hunger bites (a ${meal} meal of slack)")


def _rest(tid, triage=False):
    def heal(u):
        missing = u.hp_max // 2
        per = rest_heal(u, triage=triage and u.has_talent("triage"))
        return hours_to_full(per, missing)
    saved = -mean_gap(tid, heal)
    return (saved, "h", None,
            f"to heal from half HP at racial level {RACIAL_LEVEL}" + (f", for each of {CREW}" if triage else ""))


def _field_cook(tid):
    fire = items.get(economy.FIELD_CAMPFIRE_LUMBER).price + items.get(economy.FIELD_CAMPFIRE_COAL).price
    base, longer = economy.FIELD_CAMPFIRE_HOURS, economy.FIELD_CAMPFIRE_HOURS + 2
    saved = fire * (DAY / base - DAY / longer)
    return (saved, "$", None, f"of Lumber and Coal over {DAY} h of field cooking")


def _hardened(tid):
    saved = HOURS_PER_NONLETHAL_CLEAR - HARDENED_NONLETHAL_CLEAR
    return (saved, "h", None, "of rest to clear a knockout's non-lethal damage")


def _field_medic(tid):
    gain = p_check(2, data.FIRST_AID_DC) - p_check(0, data.FIRST_AID_DC)
    return (gain * 100, "pp", None, f"on first aid outside combat (d20 + WIS vs {data.FIRST_AID_DC})")


def _whisperer(tid):
    kg = animals.Animal("Donkey").back_load
    return (1, "animal", None, f"one more beast in the herd: a Donkey with a Pack Saddle carries {kg:g} kg")


def _pathfinder(tid):
    out = {n: trip_hours(n) * (1 - vocations.PATHFINDER_FACTOR) for n in ("wilds", "frontier_outpost")}
    return (out["wilds"], "h", None,
            (f"a City-Wilds round trip, as far as the Mine ({out['frontier_outpost']:.1f} h to the "
             f"Frontier Outpost and back)"))


ROWS = {
    "carrier": _haul, "heavy_haul": _haul, "piecework": _piecework, "brisk_hands": _brisk,
    "steady_pace": _steady, "charismatic": _tips, "troubadour": _tips, "negotiator": _negotiator,
    "fixer": _fixer, "provisioner": _provisioner, "clever": _clever, "linguist": _linguist,
    "crafter": _craft("Jerky"),
    "woodcarver": _craft("Shortbow"),
    "apothecary": _recipe, "blacksmith": _recipe, "nimble_fingers": _attr("dexterity"),
    "observant": _attr("wisdom"), "skinner": _skinner, "fletcher": _fletcher,
    "wheelwright": _wheelwright, "sturdy": _sturdy, "deep_reserves": _reserves,
    "restful_sleep": _rest, "triage": lambda tid: _rest(tid, triage=True),
    "field_cook": _field_cook, "hardened": _hardened, "field_medic": _field_medic,
    "beast_whisperer": _whisperer, "pathfinder": _pathfinder,
}


def rows():
    """`[(talent, worth, unit, $ a day, how)]` in the tree's order."""
    state = random.getstate()
    random.seed(0)
    try:
        return [(t, *ROWS[t.id](t.id)) for t in talents.TREE["work"]]
    finally:
        random.setstate(state)


def report():
    lines = [f"== every work talent on its own: one member with and without it ({SAMPLES} random members)",
             (f"   hours at the yard's wage with an Axe (${wage_per_hour():.2f}/h), HP at the Medic's "
              f"(${copper_per_hp():.2f}/HP); $/day only where a day of the economy turns on it"),
             f"{'talent':<16}{'tier':>4}{'worth':>9} {'':<9}{'$/day':>7}  how"]
    for t, worth, unit, per_day, how in rows():
        w = "" if worth is None else f"{worth:+.2f}"
        d = "" if per_day is None else f"{per_day:.2f}"
        lines.append(f"{t.name:<16}{t.tier:>4}{w:>9} {unit:<9}{d:>7}  {how}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())

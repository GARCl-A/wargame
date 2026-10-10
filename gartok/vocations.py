"""Vocations: the guild's founding trade, picked once at the draft.

A vocation is a list of six races and one fixed perk that the whole guild has,
not only the members of those races. The races steer the draft pool
(`draft_pool`); the perk is read by whatever it touches through the small
functions below, each taking the guild (`None` or a guild with no vocation
changes nothing). `scripts/vocation_report.py` prices each perk in copper per
guild-day.
"""

import random
from dataclasses import dataclass

from . import data
from .group import CAUTIOUS

WARBAND, DELVERS, WILDS, SCHOLARS, CARAVAN, MARSH = (
    "warband", "delvers", "wilds", "scholars", "caravan", "marsh")

COHESION_BONUS = 1          # Warband: added to Mental Defense in the daily cohesion roll only
GATHER_BONUS = 0.15         # Delvers: extra yield from gathering work
CAUTIOUS_AMBUSH = 0.8       # Wilds: x on the ambush chance while the group is Cautious
TRAVEL_FACTOR = 0.85        # Caravan: x on travel hours, after wagon and animal speed
FOOD_PAUSE_EVERY = 10       # Marsh: on every 10th day of the guild's clock no food ages
INFO_BONUS = 2              # Scholars: bonus on the INT roll that reveals enemy info (the modal is not built yet)

POOL_SIZE = 9


@dataclass(frozen=True)
class Vocation:
    id: str
    name: str
    races: tuple
    perk: str
    active: bool = True     # False: the perk waits on a system that does not exist yet


VOCATIONS = {v.id: v for v in (
    Vocation(WARBAND, "Warband",
             ("Orc", "Hobgoblin", "Goblin", "Goliath", "Gnoll", "Lizardfolk"),
             f"+{COHESION_BONUS} Mental Defense in the daily cohesion roll: fewer walk-outs "
             "from an overextended group."),
    Vocation(DELVERS, "Delvers",
             ("Dwarf", "Kobold", "Gnome", "Automaton", "Goblin", "Goliath"),
             f"+{GATHER_BONUS:.0%} yield from gathering: work shifts, and the meat, "
             "mushrooms and fruit of a hunt or forage."),
    Vocation(WILDS, "Wilds",
             ("Centaur", "Elf", "Treefolk", "Grippli", "Gnoll", "Sprite"),
             "Ambushes are 20% less likely while a group travels Cautious: on the Old Road "
             "and on a hunt."),
    Vocation(SCHOLARS, "Scholars",
             ("Kobold", "Gnome", "Elf", "Sprite", "Kenku", "Human"),
             f"+{INFO_BONUS} on the INT roll that reveals enemy information. No effect "
             "until the combat info modal exists.", active=False),
    Vocation(CARAVAN, "Caravan",
             ("Human", "Halfling", "Dwarf", "Kenku", "Automaton", "Centaur"),
             "Travel takes 15% fewer hours."),
    Vocation(MARSH, "Marsh",
             ("Grippli", "Lizardfolk", "Treefolk", "Halfling", "Kobold", "Kenku"),
             f"On every {FOOD_PAUSE_EVERY}th day no food in the guild ages."),
)}


def get(vocation_id):
    return VOCATIONS.get(vocation_id)


def of(guild):
    return get(guild.vocation)


def _is(guild, vocation_id):
    return guild.vocation == vocation_id


def cohesion_bonus(guild):
    return COHESION_BONUS if _is(guild, WARBAND) else 0


def gather_mult(guild):
    return 1 + GATHER_BONUS if _is(guild, DELVERS) else 1.0


def gather_pay(guild, copper, rng=random):
    """`copper` plus the Delvers' share, in whole coins: the fraction of a coin the
    bonus leaves over is paid out with that chance, so a small wage gets +15% on
    average and not whatever rounding gives."""
    extra = copper * (gather_mult(guild) - 1)
    whole = int(extra)
    return copper + whole + (rng.random() < extra - whole)


def travel_mult(guild):
    return TRAVEL_FACTOR if _is(guild, CARAVAN) else 1.0


def ambush_mult(guild, stance, scout=False):
    """The factor on a rolled ambush chance. *Normal* changes nothing; *Cautious*
    is 1 on its own, x0.8 with the Wilds perk and x0.9 with a Woodland Scout, and
    they multiply."""
    if stance != CAUTIOUS:
        return 1.0
    mult = 1.0
    if _is(guild, WILDS):
        mult *= CAUTIOUS_AMBUSH
    if scout:
        mult *= 0.9
    return mult


def food_pauses(guild):
    return _is(guild, MARSH) and guild.clock.day % FOOD_PAUSE_EVERY == 0


def draft_pool(vocation_id, size=POOL_SIZE, rng=random):
    """The races of a draft pool: one of each of the vocation's six, the rest drawn
    from the natural race table, in a shuffled order. With no vocation, all natural."""
    voc = get(vocation_id)
    races = [data.race_by_name(n) for n in voc.races] if voc else []
    races += [data.roll_race() for _ in range(size - len(races))]
    rng.shuffle(races)
    return races

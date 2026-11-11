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

from . import data, i18n
from .group import CAUTIOUS

WARBAND, DELVERS, WILDS, SCHOLARS, CARAVAN, MARSH = (
    "warband", "delvers", "wilds", "scholars", "caravan", "marsh")

MORALE_BONUS = 1            # Warband: added to a member's starting morale in a fight
GATHER_BONUS = 0.15         # Delvers: extra yield from gathering work
NIGHT_PROWLER_AMBUSH = 0.8    # Catfolk Night Prowler: x on the ambush chance at night, while Cautious
CAUTIOUS_AMBUSH = 0.8       # Wanderers: x on the ambush chance while the group is Cautious
TRAVEL_FACTOR = 0.85        # Caravan: x on travel hours, after wagon and animal speed
PATHFINDER_FACTOR = 0.90    # a Pathfinder in the group: x on travel hours, stacks with Caravan
HUNGER_RELIEF = 2           # Marsh: softens the attribute penalty of a Hungry or Starving member (not the last two days)
INFO_BONUS = 2              # Scholars: bonus on the INT roll that reveals enemy info (the opening read and Assess)

POOL_SIZE = 9


@dataclass(frozen=True)
class Vocation:
    id: str
    races: tuple
    active: bool = True     # False: the perk waits on a system that does not exist yet

    @property
    def name(self):
        return i18n.name("vocation", self.id)

    @property
    def perk(self):
        return i18n.desc("vocation", self.id, morale_bonus=MORALE_BONUS, gather_bonus=GATHER_BONUS,
                         info_bonus=INFO_BONUS, hunger_relief=HUNGER_RELIEF)

    @property
    def motto(self):
        return i18n.desc("vocation_motto", self.id)


VOCATIONS = {v.id: v for v in (
    Vocation(WARBAND, ("Orc", "Hobgoblin", "Goblin", "Goliath", "Gnoll", "Lizardfolk")),
    Vocation(DELVERS, ("Dwarf", "Kobold", "Gnome", "Automaton", "Goblin", "Goliath")),
    Vocation(WILDS, ("Centaur", "Elf", "Treefolk", "Grippli", "Gnoll", "Sprite")),
    Vocation(SCHOLARS, ("Kobold", "Gnome", "Elf", "Sprite", "Kenku", "Human")),
    Vocation(CARAVAN, ("Human", "Halfling", "Dwarf", "Catfolk", "Automaton", "Centaur")),
    Vocation(MARSH, ("Grippli", "Lizardfolk", "Treefolk", "Halfling", "Kobold", "Kenku")),
)}


def get(vocation_id):
    return VOCATIONS.get(vocation_id)


def of(guild):
    return get(guild.vocation)


def _is(guild, vocation_id):
    return guild.vocation == vocation_id


def morale_bonus(unit):
    return MORALE_BONUS if _is(unit, WARBAND) else 0


def info_bonus(guild):
    return INFO_BONUS if _is(guild, SCHOLARS) else 0


def gather_mult(guild):
    return 1 + GATHER_BONUS if _is(guild, DELVERS) else 1.0


def travel_mult(guild, group=None):
    mult = TRAVEL_FACTOR if _is(guild, CARAVAN) else 1.0
    if group is not None and group.has_talent("pathfinder"):
        mult *= PATHFINDER_FACTOR
    return mult


def night_mult(stance, prowler):
    """The factor a Night Prowler puts on the ambush chance of an hour after dark: Cautious only."""
    return NIGHT_PROWLER_AMBUSH if prowler and stance == CAUTIOUS else 1.0


def ambush_mult(guild, stance, scout=False, prowler=False):
    """The factor on a rolled ambush chance. *Normal* changes nothing; *Cautious*
    is 1 on its own, x0.8 with the Wanderers perk, x0.9 with a Woodland Scout and x0.8 at night
    with a Night Prowler, and they multiply."""
    if stance != CAUTIOUS:
        return 1.0
    mult = 1.0
    if _is(guild, WILDS):
        mult *= CAUTIOUS_AMBUSH
    if scout:
        mult *= 0.9
    if not guild.clock.is_daylight:
        mult *= night_mult(stance, prowler)
    return mult


def hunger_relief(unit):
    return HUNGER_RELIEF if _is(unit, MARSH) else 0


def draft_pool(vocation_id, size=POOL_SIZE, rng=random):
    """The races of a draft pool: one of each of the vocation's six, the rest drawn
    from the natural race table, in a shuffled order. With no vocation, all natural."""
    voc = get(vocation_id)
    races = [data.race_by_name(n) for n in voc.races] if voc else []
    races += [data.roll_race() for _ in range(size - len(races))]
    rng.shuffle(races)
    return races

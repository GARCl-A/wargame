"""Poisons: a named toxin that stacks and wears off one step at a time.

A venomous bite forces a Constitution save; a failed save adds one stack of the
poison to the *character* (it outlives the fight, see `unit_poison.py`). Each
stack eats `Poison.per_stack` points of one attribute, and one stack wears off
every `Poison.hours` of world time, the clock restarting after each step and on
every fresh bite. An Antidote lets the poisoned character roll another save to
shed a step at once (`unit_poison.PoisonMixin.apply_antidote`).

Mirrors `abilities.py` / `talents.py`: a frozen-dataclass registry, so a new
toxin (and later the poisoned oil) is one more entry here.
"""

from dataclasses import dataclass

from . import i18n

ANTIDOTE_COOLDOWN_HOURS = 24      # one antidote per character per this many hours


@dataclass(frozen=True)
class Poison:
    id: str
    attribute: str          # the score each stack eats
    per_stack: int = 1      # points lost per stack
    hours: int = 24         # time for one stack to wear off
    base_dc: int = 11       # save DC = this + the venomous creature's racial level

    @property
    def name(self):
        return i18n.name("poison", self.id)


_LIST = [
    Poison("giant_spider_venom", "dexterity"),
    Poison("snake_venom", "constitution"),
    Poison("gut_rot", "constitution", per_stack=2, hours=168),   # a rotten meal on a sick stomach
]

POISONS = {p.id: p for p in _LIST}


def get(poison_id):
    return POISONS[poison_id]


def save_dc(poison, attacker):
    """The Constitution save DC of `poison` as delivered by `attacker` (a Unit)."""
    return poison.base_dc + attacker.racial_level

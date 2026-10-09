"""The Medic's quick treatment: a visit to the City that mends a group's hurt, sick and
poisoned for the potions and doses it would take, at a discount (`economy.MEDIC_*`).

A patient's cost is the *expected* consumables: Minor Healing Potions for lost HP, one
First Aid Kit charge for sickness, Antidotes for poison (every dose assumed to take).
The clock moves for the whole group by the longest treatment picked. Anything past
`economy.MEDIC_MAX_HOURS` is not offered here.
"""

import math
from dataclasses import dataclass

from . import economy, items, poisons

POTION = "Minor Healing Potion"


@dataclass(frozen=True)
class Quote:
    uid: str
    name: str
    parts: tuple          # ((label, cost, hours), ...) one line per ailment
    cost: int
    hours: int
    offered: bool         # False: needs a hospital stay, not a visit

    @property
    def needs_care(self):
        return bool(self.parts)


def _price(item, share=1.0):
    return items.get(item).price * share * economy.MEDIC_PRICE_FACTOR


def _poison_part(pid, stacks):
    doses = math.ceil(stacks / 2)
    hours = max(1, poisons.get(pid).hours * math.ceil((stacks - 1) / 2))
    return (f"{poisons.get(pid).name} x{stacks}", round(doses * _price(items.ANTIDOTE_ITEM)), hours)


def quote(unit):
    """What treating `unit` costs and takes: a `Quote` (empty `parts` when they are fine)."""
    parts = []
    if unit.hp < unit.hp_max:
        potions = math.ceil((unit.hp_max - unit.hp) / economy.MEDIC_POTION_HP)
        parts.append((f"{unit.hp_max - unit.hp} HP", round(potions * _price(POTION)), economy.MEDIC_HP_HOURS))
    if unit.sick:
        kit = items.get(items.FIRST_AID_ITEM)
        parts.append(("Sickness", round(kit.price / kit.max_charges * economy.MEDIC_PRICE_FACTOR),
                      economy.MEDIC_SICKNESS_HOURS))
    for pid, st in unit.poisons.items():
        parts.append(_poison_part(pid, st["level"]))
    hours = max((h for _, _, h in parts), default=0)
    return Quote(unit.uid, unit.name, tuple(parts), sum(c for _, c, _ in parts), hours,
                 hours <= economy.MEDIC_MAX_HOURS)


def quotes(units):
    return [quote(u) for u in units]


def total(quote_list):
    """(copper, hours) for treating every quote in the list together."""
    return sum(q.cost for q in quote_list), max((q.hours for q in quote_list), default=0)


def cure(unit):
    """Leave `unit` at full HP, healthy and unpoisoned (the payment and the clock are the caller's)."""
    unit.sick = False
    unit.treated = False
    unit.poisons.clear()
    unit._apply_attributes()
    unit._derive_combat()
    unit.hp = unit.hp_max


def treat(guild, group, patients):
    """Treat `patients` (units of `group`): the group pays, the clock advances by the longest
    treatment, and every patient leaves at full HP, cured and unpoisoned. Returns
    `(ok, lines)`; nothing happens when the pick is empty, past the Medic's limit or unaffordable."""
    picked = [(u, quote(u)) for u in patients]
    picked = [(u, q) for u, q in picked if q.needs_care]
    if not picked:
        return False, ["Nobody picked needs treating."]
    if not all(q.offered for _, q in picked):
        return False, ["A longer treatment needs a hospital stay."]
    cost, hours = total([q for _, q in picked])
    if sum(u.money for u in group.members) < cost:
        return False, [f"The group cannot pay ${cost}."]
    economy.charge_richest_first(group.members, cost)
    events, _ = guild.pass_time(hours)
    for u, _ in picked:
        if u in guild.roster:
            cure(u)
    names = ", ".join(u.name for u, _ in picked)
    return True, [f"The Medic treats {names}: ${cost}, {hours} h."] + list(events)

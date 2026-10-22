"""Captured units: a foe bound in battle (`actions.Capture`) that a group then keeps.

A captive is not a member: it never fights, works or eats. It walks with the group (its speed
counts in the group's pace), takes `HERD_WEIGHT` of the group's herd limit like an animal
(`Group.herd_capacity`), and dies `CAPTIVE_DAYS` after its capture. One with a body worth
keeping (`CORPSES`, by its NPC slug) leaves that body in the leader's pack. A mission that wants
one alive takes it straight from the group (`missions.py`).
"""

from dataclasses import dataclass

from . import items

CAPTIVE_DAYS = 7
HERD_WEIGHT = 1

CORPSES = {"snake_dragon": items.SNAKE_DRAGON_CORPSE_ITEM}
CAPTURE_TOOLS = ("Rope", "Chains")


def capture_tool(combatant):
    """The Rope or Chains `combatant` would bind a captive with, or None."""
    return next((t for t in CAPTURE_TOOLS if t in combatant.inventory), None)


@dataclass
class Captive:
    unit: object                  # the bound Unit
    taken_day: int
    npc_slug: str | None = None

    herd_weight = HERD_WEIGHT

    @property
    def name(self):
        return self.unit.name

    def days_left(self, today):
        return max(0, self.taken_day + CAPTIVE_DAYS - today)


def take(guild, group, combatants):
    """After a won battle: every bound foe joins `group` as a captive. Returns the lines to show."""
    lines = []
    for c in combatants:
        group.captives.append(Captive(c.char, guild.clock.day, getattr(c.char, "npc_slug", None)))
        lines.append(f"{c.char.name} is led away in bonds -- a captive for {CAPTIVE_DAYS} days "
                     f"(group screen, QUESTS & CAPTIVES).")
    return lines


def release(group, captive):
    group.captives.remove(captive)
    return f"{captive.name} is set loose."


def daily(guild):
    """A day passed: captives whose days are up die, leaving any body worth keeping."""
    lines = []
    for group in guild.groups:
        for cap in [c for c in group.captives if c.days_left(guild.clock.day) <= 0]:
            group.captives.remove(cap)
            body = CORPSES.get(cap.npc_slug)
            if body and group.leader is not None:
                group.leader.give_to_pack(body)
                lines.append(f"{cap.name} dies in captivity; {group.leader.name} keeps the body.")
            else:
                lines.append(f"{cap.name} dies in captivity.")
    return lines


def to_dict(cap, unit_to_dict):
    return {"unit": unit_to_dict(cap.unit), "taken_day": cap.taken_day, "npc_slug": cap.npc_slug}


def from_dict(d, unit_from_save):
    unit = unit_from_save(d["unit"])
    unit.npc_slug = d["npc_slug"]
    return Captive(unit, d["taken_day"], d["npc_slug"])

"""Hunting the wilds: trade daylight for meat, at the risk of an ambush.

The first activity at the `wilds` world node (`world.py`). A picked party spends
a chosen number of hours in the open country; every hour carries a flat chance of
a pack finding them first (`encounters.roll_pack`). An ambush interrupts the
hunt -- fight it, and on a win the party may keep hunting the hours that are
left. Meat and work-experience are banked once, at the end, to whoever walked
back out.

Meat is the point: it pays no copper, but a haul feeds the guild for days and a
strong hunter can carry the whole roster's food (see `Unit.share_food`). The
lumber yard is the safe floor; the wilds are the gamble.

`app` owns the flow (map -> party picker -> `HuntScreen` <-> battle); this module
is the rules. `HuntState` is the live hunt, carried on `app._hunt` across any
ambush battles so a screen rebuilt after a fight can pick the hunt back up.
"""

import random
from dataclasses import dataclass

from . import encounters, progression

AMBUSH_CHANCE_PER_HOUR = 0.15   # ~one ambush per 6-7 h hunted
HUNT_MEAT_HOURS = 2             # hours of hunting per 1 kg of meat
HUNT_SHIFT_HOURS = (4, 8, 12, 16)   # lengths offered, like the lumber yard
MEAT_ITEM = "Meat"
HUNT_LEVEL = 3                   # the wilds' job level: real risk, so it keeps
                                 # paying work-XP well past where the lumber yard caps


@dataclass
class HuntState:
    party: list                    # the hunters (roster Units); trimmed to survivors after a fight
    node: object                   # the world node the hunt is at
    hours_left: int                # daylight still to spend
    hours_hunted: int = 0          # hours actually spent (drives the meat haul + work XP)
    fights: int = 0                # ambushes fought so far, for the tally line
    target: str = "meat"           # "meat" or "shrooms"
    shrooms_found: int = 0

    @property
    def meat(self):
        if self.target == "meat":
            return self.hours_hunted // HUNT_MEAT_HOURS
        return 0


def hunt_stretch(state, rng=random):
    """Spend hours one at a time until an ambush hits or the daylight runs out.
    Mutates `state` (`hours_left` down, `hours_hunted` up). Returns
    `(elapsed_hours, ambushed)`."""
    elapsed = 0
    chance = AMBUSH_CHANCE_PER_HOUR
    if any(u.has_talent("woodland_scout") for u in state.party):
        chance /= 2.0

    while state.hours_left > 0:
        state.hours_left -= 1
        state.hours_hunted += 1
        elapsed += 1
        if state.target == "shrooms" and rng.random() < 0.10:
            state.shrooms_found += 1
        if rng.random() < chance:
            return elapsed, True
    return elapsed, False


def wilds_pack(rng=random):
    """The pack that springs an ambush -- a scaled `encounters` roll, mostly
    wolves (see `encounters.WILDS_TABLE`)."""
    return encounters.roll_encounter(encounters.WILDS_TABLE, rng=rng)


def grant_haul(state):
    """Bank the hunt: hand the haul to the surviving hunters (round-robin
    into their packs) and credit each with the hours toward their work track.
    Idempotent guard is the caller's job -- call once, at the end. Returns the
    lines to show."""
    hunters = list(state.party)
    lines = []
    if not hunters:
        return ["Nobody made it back with the haul."]

    for u in hunters:
        old_work_lvl = u.work_level
        u.work_hours += progression.work_xp_hours(state.hours_hunted, HUNT_LEVEL, u.work_level)
        u.collect_levels()
        if u.work_level > old_work_lvl:
            lines.append(f"{u.name} reached work level {u.work_level}!")

    if state.target == "meat":
        meat = state.meat
        for i in range(meat):
            hunters[i % len(hunters)].give_to_pack(MEAT_ITEM)

        who = hunters[0].name if len(hunters) == 1 else f"{len(hunters)} hunters"
        if meat:
            lines.append(f"{who} bring back {meat} kg of meat "
                         f"({state.hours_hunted} h hunted).")
        else:
            lines.append(f"{who} come back empty-handed ({state.hours_hunted} h "
                         f"hunted -- not enough for a kill).")
    else:
        shrooms = state.shrooms_found
        for i in range(shrooms):
            hunters[i % len(hunters)].give_to_pack("Red Mushroom")

        who = hunters[0].name if len(hunters) == 1 else f"{len(hunters)} foragers"
        if shrooms:
            lines.append(f"{who} bring back {shrooms} Red Mushroom(s) "
                         f"({state.hours_hunted} h foraged).")
        else:
            lines.append(f"{who} come back empty-handed ({state.hours_hunted} h "
                         f"foraged).")
    if state.fights:
        pack = "pack" if state.fights == 1 else "packs"
        lines.append(f"Fought off {state.fights} {pack} along the way.")
    return lines

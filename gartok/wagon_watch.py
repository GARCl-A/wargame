"""A wagon left outside while the party goes into a dangerous place.

The Ancient Ruins and a hunt in the Wilds open the squad selector (`watch_screen.py`):
whoever stays behind minds the wagon. Any one member is a guard. Unguarded, the wagon and
the animals roll once when the party comes back out: the node's `wagon_risk` plus the
flightiest animal's chance to bolt (`data.BEASTS`), and a hit loses everything, silently.
Guarded, they are safe: no node has a random encounter of its own for the wagon yet.
"""

import random


def needs_watch(group):
    return bool(group.wagons)


def flight_chance(group):
    return max((a.race["flight"] for a in group.herd), default=0.0)


def risk(group, node):
    return min(1.0, node.wagon_risk + flight_chance(group))


def leave_outside(group, node, guarded, rng=random):
    """Roll for the wagon once the party is back out. True when it is gone."""
    if guarded or not group.wagons or rng.random() >= risk(group, node):
        return False
    for wagon in list(group.wagons):
        group.remove_wagon(wagon)
    group.herd.clear()
    return True

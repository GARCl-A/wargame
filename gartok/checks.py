"""The d20 a player's choice rolls outside a fight, handed to the screen that shows it.

A rule that rolls on the player's order (the tavern's pitch, a lock picked in the pack) puts a `Check` on
`guild.table`; the web server drains the table into the answer it is about to send and the client throws the
dice on a small tray over whatever screen is open (`dice.js`). The table is transient: it is never saved,
and the cap keeps a simulation that never drains it from growing it.
"""

from dataclasses import dataclass

TABLE_CAP = 16


@dataclass
class Check:
    who: str                 # the unit that rolled, for the caption
    nat: int
    mod: int
    total: int
    dc: int                  # the number to reach (the other side's total, in a contest)
    ok: bool
    label: str               # what it was ("picks the lock"), already translated
    theirs: tuple | None = None     # (nat, total) of the other side of a contest
    spare: tuple = ()               # the other dice of a joint pitch: thrown beside the one that counted


def put(guild, check):
    guild.table.append(check)
    del guild.table[:-TABLE_CAP]


def drain(guild):
    """The table as the roll records `dice.js` throws (the shape of a combat roll, no actor, no damage)."""
    out = []
    for c in guild.table:
        out.append({"actor": None, "target": None, "nat": c.nat, "mod": c.mod, "total": c.total,
                    "vs": "contest" if c.theirs else "dc", "dc": str(c.dc),
                    "outcome": "crit" if c.nat == 20 and c.ok else "fumble" if c.nat == 1 and not c.ok
                    else "hit" if c.ok else "miss",
                    "theirs": {"nat": c.theirs[0], "total": c.theirs[1]} if c.theirs else None,
                    "spare": list(c.spare), "damage": None, "passive": False, "label": f"{c.who} {c.label}"})
    guild.table.clear()
    return out

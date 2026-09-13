"""A locked chest (`data.CHEST_ITEM`): a pack item with its own lock, picked
outside battle (see `gear_screen.py`'s right-click send-to menu) rather than
through `actions.py` (that module is battle-only -- opening a chest happens
on the map, between fights).

Same idiom every other DC check in the game uses: `d20() + mod_dexterity >=
data.CHEST_DC`. A miss costs nothing -- the chest stays in the pack, try
again whenever -- so there is no failure state to track, just a bool.

The Bankers' trust mission (`missions.py`) hands out a different item,
`data.MISSION_CHEST_ITEM`, precisely so it is never mistaken for this one --
picking it early fails that mission and marks the opener a criminal instead
of quietly paying out (see `missions.open_mission_chest`, which reuses
`roll_lock` below for the same odds but not the same consequences).
"""

from . import data

GEM_YIELD_DICE = (1, 4)   # gems inside, rolled once per successful open: 1d4 + 1 (2..5)


def roll_lock(unit):
    """The pick-the-lock roll alone, no chest or inventory involved: None on
    a miss, otherwise the gems a hit yields. Shared with
    `missions.open_mission_chest`, which needs the same odds but a different
    outcome on success."""
    if data.d20() + unit.mod_dexterity < data.CHEST_DC:
        return None
    return data.roll(*GEM_YIELD_DICE) + 1


def try_open(unit):
    """Attempt to pick one `data.CHEST_ITEM` in `unit`'s pack. On success it
    is consumed and replaced with the gems inside; on a miss nothing changes.
    Returns `(opened, gems)` -- `gems` is 0 on a miss. No-op, `(False, 0)`, if
    `unit` isn't carrying one."""
    if data.CHEST_ITEM not in unit._base_inventory:
        return False, 0
    gems = roll_lock(unit)
    if gems is None:
        return False, 0
    unit._base_inventory.remove(data.CHEST_ITEM)
    for _ in range(gems):
        unit._base_inventory.append(data.GEM_ITEM)
    return True, gems

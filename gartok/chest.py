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


def roll_lock(unit, day=1):
    """The pick-the-lock roll alone, no chest or inventory involved: None on
    a miss, otherwise the gems a hit yields. Shared with
    `missions.open_mission_chest`, which needs the same odds but a different
    outcome on success."""
    roll = data.d20()
    if roll + unit.mod_dexterity < data.CHEST_DC and unit.can_use_luck(day):
        unit.use_luck(day)
        roll = data.d20()
    if roll + unit.mod_dexterity < data.CHEST_DC:
        return None
    return data.roll(*GEM_YIELD_DICE) + 1


def try_open(unit, day=1):
    """Attempt to pick one `data.CHEST_ITEM` in `unit`'s pack. On success it
    is consumed and replaced with the gems inside; on a miss nothing changes.
    Returns `(opened, gems)` -- `gems` is 0 on a miss. No-op, `(False, 0)`, if
    `unit` isn't carrying one."""
    if not unit.has_item(data.CHEST_ITEM):
        return False, 0
    gems = roll_lock(unit, day=day)
    if gems is None:
        return False, 0
    unit.remove_named(data.CHEST_ITEM)
    if gems:
        unit.give_to_pack(data.GEM_ITEM, gems)
    return True, gems

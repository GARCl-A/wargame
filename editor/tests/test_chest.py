"""The locked chest (chest.py): a pack item with its own DC, picked outside
battle. Same d20 + mod idiom as every other check in the game (`fixed_d20`
pins it, same as a death save or the guard test)."""

import random
from gartok import data
from tests.helpers import Unit, fixed_d20, packed

def _guild_of(*units):
    from gartok.guild import Guild
    return Guild(list(units))


def test_opening_the_regular_chest_ignores_a_sealed_one_in_the_same_pack():
    """Regression: the menu used to decide "is this the mission's sealed
    chest?" by re-scanning the whole pack for data.MISSION_CHEST_ITEM instead
    of looking at the item actually right-clicked -- a unit carrying both
    (e.g. via the sandbox editor) would always resolve as the sealed one,
    even when the player opened the ordinary Locked Chest."""
    from gartok.band_kit import BandKit

    random.seed(1)
    u = Unit("player")
    u.mod_dexterity = 0
    u._base_inventory = packed([data.MISSION_CHEST_ITEM, data.CHEST_ITEM])
    guild = _guild_of(u)
    gs = BandKit(guild, guild.groups[0])
    with fixed_d20(data.CHEST_DC):
        gs._menu_run([(u, 1)], "open", None)                 # the CHEST_ITEM row

    assert not u.has_item(data.CHEST_ITEM)
    assert u.has_item(data.MISSION_CHEST_ITEM)   # untouched -- the sealed one stays sealed
    assert u.has_item(data.GEM_ITEM)
    assert "picks the lock" in gs.notice and "trust mission" not in gs.notice

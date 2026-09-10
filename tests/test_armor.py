"""Worn armor: AC, the Dexterity cap, the speed hit, the weight."""

from tests.helpers import Combatant, data, economy, Unit, _unit


def _bare_human(strength=20, **over):
    """An unloaded Humano (Medio, cm 1.0, no natural armor). Strength 20 by
    default -> carry_normal 35 kg, room for a mid-weight armor before encumbrance."""
    u = _unit(**over)
    u.set_race("Human")
    u.base_attributes["strength"] = strength
    u._configure_race()                                # Humano mods are all 0
    u.equipped_weapon = u.equipped_offhand = None
    u._base_inventory = []
    u._derive_combat()
    return u


def test_armor_raises_ac_and_caps_dexterity():
    u = _bare_human(seed=1)
    u.dexterity = 18                                    # +4 Dexterity mod
    u._derive_combat()
    bare_ac = u.ac
    u.give_to_armor("Chainmail")                    # +3 AC, Dex to AC capped at +2, 10 kg
    assert not u.encumbered
    assert u.ac == bare_ac - 4 + 2 + 3
    assert u.equipped_armor == "Chainmail"


def test_leather_armor_keeps_full_dexterity():
    u = _bare_human(seed=1)
    u.dexterity = 18
    u._derive_combat()
    base = u.ac
    u.give_to_armor("Leather Jerkin")                   # +1 AC, no Dex cap
    assert not u.encumbered and u.ac == base + 1


def test_plate_slows_you_and_its_weight_encumbers_on_top():
    u = _bare_human(strength=10, seed=1)                # carry_normal 15 kg
    base_speed = u.speed
    u.give_to_armor("Plate Armor")               # -2 squares, and 28 kg overloads
    assert u.encumbered
    assert u.speed == max(1, base_speed - 2 - 1)        # armor -2, encumbrance -1


def test_equipping_armor_stows_the_old_piece():
    u = _bare_human(seed=1)
    u.give_to_armor("Leather Jerkin")
    u.give_to_armor("Chainmail")
    assert u.equipped_armor == "Chainmail"
    assert "Leather Jerkin" in u._base_inventory


def test_armor_weighs_the_same_worn_or_stowed():
    u = _bare_human(seed=1)
    base = u.load
    u.give_to_pack("Chainmail")
    stowed = u.load
    assert stowed == base + data.ARMOR["Chainmail"]["weight"]
    u.give_to_armor(u.take_from_pack(u._base_inventory.index("Chainmail")))
    assert u.load == stowed


def test_worn_armor_reaches_the_combatant():
    u = _bare_human(seed=1)
    u.give_to_armor("Chainmail")
    c = Combatant(u)
    assert c.ac == u.ac and c.speed == u.speed


def test_armor_is_stocked_and_priced_by_the_ac_it_grants():
    for name in data.ARMOR:
        assert name in economy.MARKET_STOCK and name in economy.PRICES
    assert (economy.PRICES["Leather Jerkin"] < economy.PRICES["Chainmail"]
            < economy.PRICES["Plate Armor"])


def test_armor_survives_a_save_round_trip():
    from gartok import persist
    u = _bare_human(seed=7)
    u.give_to_armor("Brigandine")
    ac, speed, enc = u.ac, u.speed, u.encumbered
    u2 = Unit.from_save(persist.unit_to_dict(u))
    assert u2.equipped_armor == "Brigandine"
    assert u2.ac == ac and u2.speed == speed and u2.encumbered == enc

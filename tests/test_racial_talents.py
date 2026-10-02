"""Tests for high-identity racial talents: Leshy Fruitful, Human Cosmopolitan,
and Halfling Luck, including the daily ability framework.
"""

from unittest.mock import patch
from tests.helpers import (Battle, Combatant, Unit, _FixedRNG, data,
                           economy, persist, recruit, talents)
from gartok import actions, chest
from gartok.guild import Guild
from gartok.group import Group


def _leshy():
    u = Unit("player", race=data.race_by_name("Leshy"))
    u.set_track_level("racial", 5)
    return u


def _human():
    u = Unit("player", race=data.race_by_name("Human"))
    u.set_track_level("racial", 5)
    return u


def _halfling():
    u = Unit("player", race=data.race_by_name("Halfling"))
    u.set_track_level("racial", 5)
    return u


# --------------------------------------------------------------------------- #
# Leshy: Fruitful                                                             #
# --------------------------------------------------------------------------- #

def test_leshy_fruitful_talent_produces_fruit_at_dawn():
    leshy = _leshy()
    assert leshy.choose_talent("racial", "fruitful")
    assert leshy.has_talent("fruitful")

    human = _human()
    human.unfed_days = 1

    g = Guild([leshy, human], name="Bloom Guild")

    assert not leshy.has_item("Fruit")
    events, _ = g._daily_upkeep()

    assert any("blooms at dawn" in e for e in events)
    # The fruit was produced; human ate it from the shared larder
    assert human.unfed_days == 0


def test_leshy_without_talent_does_not_produce_fruit():
    leshy = _leshy()
    g = Guild([leshy], name="No Bloom")
    events, _ = g._daily_upkeep()
    assert not any("blooms at dawn" in e for e in events)
    assert not leshy.has_item("Fruit")


# --------------------------------------------------------------------------- #
# Human: Cosmopolitan                                                         #
# --------------------------------------------------------------------------- #

def test_human_cosmopolitan_reduces_alignment_penalty_in_recruitment():
    recruiter = _human()
    recruiter.alignment = "Lawful and Good"
    candidate = _human()
    candidate.alignment = "Chaotic and Evil"  # distance 4

    # Baseline pitch without talent
    rng = _FixedRNG(10, 10)
    pitch_base = recruit.convince(recruiter, candidate, roster_size=1, rng=rng)
    dist_mod_base = [v for v, lbl in pitch_base.modifiers if "opposite alignment" in lbl][0]
    assert dist_mod_base == -1 * 4  # -4

    # With Cosmopolitan talent: effective distance 3 -> penalty -3
    assert recruiter.choose_talent("racial", "cosmopolitan")
    rng = _FixedRNG(10, 10)
    pitch_cosmo = recruit.convince(recruiter, candidate, roster_size=1, rng=rng)
    dist_mod_cosmo = [v for v, lbl in pitch_cosmo.modifiers if "opposite alignment" in lbl][0]
    assert dist_mod_cosmo == -1 * 3  # -3


def test_human_cosmopolitan_reduces_vendor_alignment_penalty():
    human = _human()
    human.alignment = "Chaotic and Evil"
    human.languages.append("Ankarin")
    vendor_align = "Lawful and Good"  # distance 4 -> penalty -0.10

    deal_base = economy.market_deal([human], "Ankarin", vendor_align)
    assert human.choose_talent("racial", "cosmopolitan")
    deal_cosmo = economy.market_deal([human], "Ankarin", vendor_align)

    # Cosmopolitan cuts distance to 3 -> -0.05 deal
    assert deal_cosmo > deal_base


# --------------------------------------------------------------------------- #
# Halfling: Halfling Luck                                                     #
# --------------------------------------------------------------------------- #

def test_halfling_luck_rerolls_missed_attack_in_combat():
    halfling = _halfling()
    assert halfling.choose_talent("racial", "halfling_luck")

    enemy = _human()
    enemy.hp = 20

    batt = Battle([halfling], [enemy], clock_day=1)
    h_c, e_c = batt.player_units[0], batt.enemy_units[0]
    h_c.pos, e_c.pos = (5, 5), (5, 6)

    # Force rolls: attack roll 2 (miss), reroll 19 (hit)
    with patch("gartok.actions.d20", side_effect=[2, 19, 4]):
        actions.ATTACK.execute(batt, h_c, e_c)

    assert any("Halfling Luck" in line for line in batt.log_lines)
    assert halfling.last_daily_luck_day == 1

    # Second attack on same day does NOT get a reroll
    batt.log_lines.clear()
    with patch("gartok.actions.d20", return_value=2):
        actions.ATTACK.execute(batt, h_c, e_c)
    assert not any("Halfling Luck" in line for line in batt.log_lines)


def test_halfling_luck_resets_on_next_day():
    halfling = _halfling()
    assert halfling.choose_talent("racial", "halfling_luck")
    halfling.use_luck(day=1)
    assert not halfling.can_use_luck(day=1)
    assert halfling.can_use_luck(day=2)


def test_halfling_luck_rerolls_chest_lockpick():
    halfling = _halfling()
    assert halfling.choose_talent("racial", "halfling_luck")
    halfling.give_to_pack(data.CHEST_ITEM)

    # First roll 2 (fails DC 15), reroll 18 (succeeds)
    with patch("gartok.chest.data.d20", side_effect=[2, 18]):
        opened, gems = chest.try_open(halfling, day=1)

    assert opened is True
    assert gems > 0
    assert halfling.last_daily_luck_day == 1


# --------------------------------------------------------------------------- #
# Persistence                                                                 #
# --------------------------------------------------------------------------- #

def test_daily_luck_persists_across_save_load():
    halfling = _halfling()
    assert halfling.choose_talent("racial", "halfling_luck")
    halfling.use_luck(day=5)

    saved = persist.unit_to_dict(halfling)
    assert saved["last_daily_luck_day"] == 5

    restored = Unit.from_save(saved)
    assert restored.last_daily_luck_day == 5
    assert not restored.can_use_luck(day=5)
    assert restored.can_use_luck(day=6)


# --------------------------------------------------------------------------- #
# Goliath: Giant's Grip & Large Weapons                                       #
# --------------------------------------------------------------------------- #

def _goliath():
    u = Unit("player", race=data.race_by_name("Goliath"))
    u.set_track_level("racial", 5)
    return u


def _centaur():
    u = Unit("player", race=data.race_by_name("Centaur"))
    u.set_track_level("racial", 5)
    return u


def test_large_weapon_stats_scaling():
    med_axe = data.WEAPONS["Axe"]
    large_axe = data.WEAPONS["Large Axe"]
    assert med_axe["size"] == "Medium"
    assert large_axe["size"] == "Large"
    assert med_axe["damage"] == (1, 8)
    assert large_axe["damage"] == (1, 10)
    assert large_axe["weight"] == med_axe["weight"] * 2

    med_sword = data.WEAPONS["Broadsword"]
    large_sword = data.WEAPONS["Large Broadsword"]
    assert med_sword["damage"] == (1, 12)
    assert large_sword["damage"] == (2, 8)
    assert large_sword["weight"] == med_sword["weight"] * 2


def test_large_weapon_wield_permissions():
    human = _human()
    assert not human.can_wield("Large Broadsword")
    assert not human.give_to_hand("Large Broadsword")
    assert human.equipped_weapon != "Large Broadsword"

    centaur = _centaur()
    assert centaur.size == "Large"
    assert centaur.can_wield("Large Broadsword")
    assert centaur.give_to_hand("Large Broadsword")
    assert centaur.equipped_weapon == "Large Broadsword"

    goliath = _goliath()
    assert goliath.size == "Medium"
    assert not goliath.can_wield("Large Broadsword")
    assert not goliath.give_to_hand("Large Broadsword")

    assert goliath.choose_talent("racial", "giant_grip")
    assert goliath.has_talent("giant_grip")
    assert goliath.can_wield("Large Broadsword")
    assert goliath.give_to_hand("Large Broadsword")
    assert goliath.equipped_weapon == "Large Broadsword"


def test_large_weapon_combat_and_load():
    goliath = _goliath()
    goliath.choose_talent("racial", "giant_grip")
    goliath.give_to_hand("Large Axe")

    c = Combatant(goliath)
    assert c.weapon["damage"] == (1, 10)
    assert c.weapon["weight"] == 6.0
    assert c.load >= 6.0


def test_large_weapon_pickup_and_dragselect():
    from gartok.dragselect import LoadoutMoveMixin
    from gartok.ground import GroundObject
    from gartok.actions import _pickable

    human = _human()
    centaur = _centaur()
    goliath = _goliath()
    goliath.choose_talent("racial", "giant_grip")

    assert not LoadoutMoveMixin._fits_slot(human, "hand", "Large Hammer")
    assert LoadoutMoveMixin._fits_slot(centaur, "hand", "Large Hammer")
    assert LoadoutMoveMixin._fits_slot(goliath, "hand", "Large Hammer")

    obj = GroundObject.weapon((0, 0), "Large Broadsword")
    c_human = Combatant(human)
    c_human.weapon_hand = False
    assert not _pickable(c_human, obj)

    c_goliath = Combatant(goliath)
    c_goliath.weapon_hand = False
    assert _pickable(c_goliath, obj)


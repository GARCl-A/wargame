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

    assert "Fruit" not in leshy._base_inventory
    events, _ = g._daily_upkeep()

    assert any("blooms at dawn" in e for e in events)
    # The fruit was produced; human ate it from the shared larder
    assert human.unfed_days == 0


def test_leshy_without_talent_does_not_produce_fruit():
    leshy = _leshy()
    g = Guild([leshy], name="No Bloom")
    events, _ = g._daily_upkeep()
    assert not any("blooms at dawn" in e for e in events)
    assert "Fruit" not in leshy._base_inventory


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
    halfling._base_inventory.append(data.CHEST_ITEM)

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

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


# --------------------------------------------------------------------------- #
# Additional Racial Talents Tests                                              #
# --------------------------------------------------------------------------- #

def _elf():
    u = Unit("player", race=data.race_by_name("Elf"))
    u.set_track_level("racial", 5)
    return u


def _orc():
    u = Unit("player", race=data.race_by_name("Orc"))
    u.set_track_level("racial", 5)
    return u


def _goblin():
    u = Unit("player", race=data.race_by_name("Goblin"))
    u.set_track_level("racial", 5)
    return u


def _automaton():
    u = Unit("player", race=data.race_by_name("Automaton"))
    u.set_track_level("racial", 5)
    return u


def _hobgoblin():
    u = Unit("player", race=data.race_by_name("Hobgoblin"))
    u.set_track_level("racial", 5)
    return u


def _lizardfolk():
    u = Unit("player", race=data.race_by_name("Lizardfolk"))
    u.set_track_level("racial", 5)
    return u


def _dwarf():
    u = Unit("player", race=data.race_by_name("Dwarf"))
    u.set_track_level("racial", 5)
    return u


def _kobold():
    u = Unit("player", race=data.race_by_name("Kobold"))
    u.set_track_level("racial", 5)
    return u


def _gnome():
    u = Unit("player", race=data.race_by_name("Gnome"))
    u.set_track_level("racial", 5)
    return u


def _kenku():
    u = Unit("player", race=data.race_by_name("Kenku"))
    u.set_track_level("racial", 5)
    return u


def test_elf_woodland_scout_halves_road_and_hunt_ambushes():
    from gartok import campaign, hunt
    elf = _elf()
    assert elf.choose_talent("racial", "woodland_scout")
    human = _human()

    g_scout = Group([elf], node="road")
    g_normal = Group([human], node="road")

    with patch("gartok.campaign.random.random", return_value=0.25):
        with patch("gartok.campaign.encounters.roll_encounter", return_value=["Goblin"]):
            order_scout = campaign._road_ambush_catch(g_scout, ["road"])
            order_normal = campaign._road_ambush_catch(g_normal, ["road"])
            assert order_scout is None
            assert order_normal is not None
            assert order_normal.kind == "ambush"

    class FakeRNG:
        def random(self):
            return 0.10

    state_scout = hunt.HuntState([elf], None, 4)
    _, amb_scout = hunt.hunt_stretch(state_scout, rng=FakeRNG())
    assert amb_scout is False

    state_normal = hunt.HuntState([human], None, 4)
    _, amb_normal = hunt.hunt_stretch(state_normal, rng=FakeRNG())
    assert amb_normal is True


def test_orc_intimidating_presence_uses_strength_for_demoralize():
    orc = _orc()
    orc.set_base_attribute("strength", 16)
    orc.set_base_attribute("charisma", 8)
    orc.languages = ["Ankarin"]
    target = _human()
    target.languages = ["Ankarin"]

    batt = Battle([orc], [target])
    o_c, t_c = batt.player_units[0], batt.enemy_units[0]
    o_c.pos, t_c.pos = (5, 5), (5, 6)

    batt.log_lines = []
    actions.DEMORALIZE.execute(batt, o_c, t_c)
    assert any("(CHA)" in line for line in batt.log_lines)
    assert not any("(STR)" in line for line in batt.log_lines)

    assert orc.choose_talent("racial", "intimidating_presence")
    batt.log_lines = []
    actions.DEMORALIZE.execute(batt, o_c, t_c)
    assert any("(STR)" in line for line in batt.log_lines)


def test_goblin_swarm_logic_speeds_up_work_with_allied_goblins():
    g1, g2, g3 = _goblin(), _goblin(), _goblin()
    assert g1.choose_talent("racial", "swarm_logic")
    assert g2.choose_talent("racial", "swarm_logic")
    assert g3.choose_talent("racial", "swarm_logic")

    guild = Guild([g1, g2, g3])
    assert guild.work_speedup([g1]) == 1.0
    assert round(guild.work_speedup([g1, g2]), 2) == 0.90
    assert round(guild.work_speedup([g1, g2, g3]), 2) == 0.80


def test_automaton_tireless_worker_provides_flat_work_speedup():
    auto = _automaton()
    assert auto.choose_talent("racial", "tireless_worker")
    assert auto.talent_bonus("activity_speed") == 0.25

    guild = Guild([auto])
    assert guild.work_speedup([auto]) == 0.75


def test_hobgoblin_phalanx_grants_ac_when_adjacent_to_ally():
    hob = _hobgoblin()
    assert hob.choose_talent("racial", "phalanx")
    ally = _human()
    enemy = _orc()

    batt = Battle([hob, ally], [enemy])
    h_c, a_c, e_c = batt.player_units[0], batt.player_units[1], batt.enemy_units[0]

    h_c.pos, a_c.pos = (5, 5), (0, 0)
    assert actions._phalanxed(batt, h_c) is False

    a_c.pos = (5, 6)
    assert actions._phalanxed(batt, h_c) is True

    e_c.pos = (4, 5)
    batt.log_lines = []
    with patch("gartok.actions.d20", return_value=10):
        actions.ATTACK.execute(batt, e_c, h_c)
    assert any("[Phalanx]" in line for line in batt.log_lines)


def test_lizardfolk_organic_harvester_boosts_meat_and_hide_loot():
    from gartok import campaign
    liz = _lizardfolk()
    assert liz.choose_talent("racial", "organic_harvester")
    guild = Guild([liz])

    enemy = Unit("enemy", race=data.BEAST_POOL[0])
    batt = Battle([liz], [enemy], lethal=True)
    batt.winner = "player"
    batt.enemy_units[0].hp = 0
    batt.enemy_units[0].status = "dead"

    with patch("gartok.loot.field_loot", return_value=["Meat"] * 5 + ["1sqm Hide"]):
        with patch("gartok.campaign.random.random", return_value=0.10):
            outcome = campaign.absorb_battle(guild, [liz], batt, node=None)
            assert outcome.loot_pool.count("Meat") == 6
            assert outcome.loot_pool.count("1sqm Hide") == 2


def test_dwarf_crafting_unlocks_dwarven_equipment_recipes():
    dwarf = _dwarf()
    assert "Dwarf Axe" not in dwarf.recipes
    assert "Dwarf Shield" not in dwarf.recipes
    assert "Dwarf Armor" not in dwarf.recipes

    assert dwarf.choose_talent("racial", "dwarf_crafting")
    assert dwarf.has_talent("dwarf_crafting")

    assert "Dwarf Axe" in dwarf.recipes
    assert "Dwarf Shield" in dwarf.recipes
    assert "Dwarf Armor" in dwarf.recipes


def test_kobold_trapper_unlocks_trap_recipes():
    kobold = _kobold()
    assert "Bear Trap" not in kobold.recipes
    assert "Alarm Trap" not in kobold.recipes

    assert kobold.choose_talent("racial", "kobold_trapper")
    assert kobold.has_talent("kobold_trapper")

    assert "Bear Trap" in kobold.recipes
    assert "Alarm Trap" in kobold.recipes


def test_gnome_magic_excitement_doubles_progress_die_on_first_study_day():
    from gartok import magic
    gnome = _gnome()
    assert gnome.choose_talent("racial", "gnome_magic_excitement")
    gnome.magic_source = "nature"
    gnome.gold = 100
    gnome.give_to_pack("Scroll of Magic Missile")
    gnome.study_target = "magic_missile"
    gnome.study_progress = 0

    rolls = []
    def fake_roll(n, sides):
        rolls.append((n, sides))
        return 10

    with patch("gartok.magic.data.roll", side_effect=fake_roll):
        magic.progress_study(gnome)

    assert len(rolls) == 1
    assert rolls[0] == (2, 20)
    assert gnome.study_progress > 0

    with patch("gartok.magic.data.roll", side_effect=fake_roll):
        magic.progress_study(gnome)

    assert len(rolls) == 2
    assert rolls[1] == (1, 20)


def test_kenku_faith_initiate_initiates_or_grants_free_spell():
    k1 = _kenku()
    k1.magic_source = None
    assert k1.choose_talent("racial", "kenku_faith_initiate")
    assert k1.has_talent("kenku_faith_initiate")
    assert k1.magic_source == "faith"
    assert len(k1.spells_known) == 0

    k2 = _kenku()
    k2.magic_source = "faith"
    k2.spells_known = ["light_globe"]
    assert k2.choose_talent("racial", "kenku_faith_initiate")
    assert k2.has_talent("kenku_faith_initiate")
    assert k2.magic_source == "faith"
    assert len(k2.spells_known) == 2
    assert k2.spells_known[1] in ("magic_missile", "floating_disk")


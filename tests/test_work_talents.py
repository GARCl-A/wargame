"""Tests for the expanded 30-node work talent tree (6 attribute roots x 5 talents each)."""

import math

import pytest

from gartok import campaign, data, economy, items, orders, talents, world
from tests.helpers import Unit, packed


def _make_worker(*talent_chain):
    u = Unit("player", name="Worker", race=data.race_by_name("Human"))
    u.money = 100
    u._base_inventory = []
    u.work_hours = economy.LUMBER_XP_HOURS * 30
    u._derive_combat()
    for t in talent_chain:
        assert u.choose_talent("work", t), f"failed to choose {t}"
    return u


def test_work_tree_structure_30_talents_6_roots():
    work_nodes = talents.TREE["work"]
    assert len(work_nodes) == 30

    roots = [t for t in work_nodes if not t.requires]
    assert len(roots) == 6
    assert [r.id for r in roots] == ["brawny", "charismatic", "clever", "nimble_fingers", "sturdy", "observant"]

    # Verify each root has exactly 5 talents in its subtree
    for r in roots:
        subtree = {r.id}
        changed = True
        while changed:
            changed = False
            for t in work_nodes:
                if t.requires in subtree and t.id not in subtree:
                    subtree.add(t.id)
                    changed = True
        assert len(subtree) == 5, f"Root {r.id} has {len(subtree)} talents: {subtree}"


# --------------------------------------------------------------------------- #
# STR: Heavy Haul                                                             #
# --------------------------------------------------------------------------- #

def _relief(u, pack):
    u._base_inventory = packed(pack)
    u._derive_combat()
    return u.carry_relief


def _enough(name, kg):
    return [name] * math.ceil(kg / items.item_weight(name))


def test_heavy_haul_widens_the_stagger_threshold_by_six_kg_of_non_equipment():
    u = _make_worker("brawny", "piecework")
    base = u.carry_normal
    assert _relief(u, _enough("Meat", 10)) == 0.0
    assert u.choose_talent("work", "heavy_haul")
    assert _relief(u, _enough("Meat", 10)) == 6.0
    assert u.carry_normal == round(base + 6.0, 1)
    assert _relief(u, _enough("Lumber", 10)) == 6.0
    assert _relief(u, ["Meat"]) == round(items.item_weight("Meat"), 1)


def test_heavy_haul_does_not_cover_equipment():
    u = _make_worker("brawny", "piecework", "heavy_haul")
    assert _relief(u, ["Axe", "Studded Leather"]) == 0.0


def test_heavy_haul_never_raises_the_carry_ceiling_nor_the_load():
    u = _make_worker("brawny", "piecework")
    _relief(u, _enough("Meat", 10))
    ceiling, load = u.carry_max, u.load
    assert u.choose_talent("work", "heavy_haul")
    assert (u.carry_max, u.load) == (ceiling, load)


# --------------------------------------------------------------------------- #
# CHA: Troubadour                                                             #
# --------------------------------------------------------------------------- #

def test_troubadour_boosts_tavern_performance():
    from gartok.guild import Guild
    u1 = _make_worker()
    u2 = _make_worker("charismatic", "fixer", "troubadour")
    u1.give_to_pack("Lute")
    u2.give_to_pack("Lute")

    # u2 has +1 CHA from charismatic and +1 from troubadour
    assert u2.talent_bonus("tavern_perform_bonus") == 1
    guild = Guild([u1, u2])
    events, _ = guild.perform_shift([u1, u2], 2)
    assert len(events) >= 1


# --------------------------------------------------------------------------- #
# DEX: Nimble Fingers, Woodcarver, Skinner, Wheelwright                       #
# --------------------------------------------------------------------------- #

def test_dex_tree_attributes_and_crafting_bonuses():
    u = Unit("player", name="Plain", race=data.race_by_name("Human"))
    u.work_hours = economy.LUMBER_XP_HOURS * 30
    u._derive_combat()
    base_dex = u.dexterity
    assert u.choose_talent("work", "nimble_fingers")
    assert u.dexterity == base_dex + 1

    assert u.choose_talent("work", "woodcarver")
    assert u.talent_bonus("woodcarver_bonus") == 1
    assert u.craft_bonus("carpenter") == u.craft_bonus("forge") + 1


def test_skinner_grants_extra_hide_from_hunts_and_battles():
    u = _make_worker("nimble_fingers", "skinner")
    from gartok.hunt import HuntState, grant_haul
    state = HuntState([u], world.node("wilds"), hours_left=0, target="meat")
    state.hours_hunted = 4
    state.yield_hours = 8
    grant_haul(state)
    assert u.count_of("1sqm Hide") == 1


def test_wheelwright_doubles_wagon_hp_repaired():
    from gartok.group import Group
    from gartok.guild import Guild
    from gartok.wagon import Wagon
    from tests.helpers import fixed_d20, packed

    def mend(*talents):
        u = _make_worker(*talents)
        u._base_inventory = packed(["Lumber"] * 5)
        wagon = Wagon("Carriage")
        wagon.hp = 1
        guild = Guild(None, groups=[Group([u], node="city", wagons=[wagon])])
        with fixed_d20(20):
            ok, _, _ = guild.repair_wagon([u], wagon)
        assert ok
        return wagon

    plain = mend()
    wright = mend("nimble_fingers", "woodcarver", "wheelwright")
    assert wright.hp == min(wright.hp_max, 1 + 2 * plain.repair_amount)
    assert wright.hp > plain.hp


# --------------------------------------------------------------------------- #
# CON: Sturdy, Deep Reserves, Restful Sleep, Field Cook, Hardened              #
# --------------------------------------------------------------------------- #

def test_con_tree_attributes_and_reserves():
    u = Unit("player", name="Plain", race=data.race_by_name("Human"))
    u.work_hours = economy.LUMBER_XP_HOURS * 30
    u._derive_combat()
    base_con = u.constitution
    assert u.choose_talent("work", "sturdy")
    assert u.constitution == base_con + 1

    assert u.choose_talent("work", "deep_reserves")
    # Deep Reserves: missing 1 meal still keeps hunger level at 0
    u.unfed_days = 1
    assert u.hunger_level == 0
    assert u.hunger_attribute_penalty == 0


def test_restful_sleep_and_hardened_accelerate_recovery():
    from gartok.guild_upkeep import rest_heal
    u = _make_worker("sturdy", "restful_sleep", "hardened")
    base_heal = max(1, u.racial_level * u.mod_constitution)
    assert rest_heal(u) == base_heal + 1

    # Hardened clears non-lethal damage in rest simulation
    from gartok.rest import _hp_after_ticks
    u.hp = 5
    u.hp_max = 10
    u.non_lethal_damage = 5
    # With hardened, non-lethal clears at tick 2 (16h threshold) instead of 3 (24h)
    hp_after_2_ticks = _hp_after_ticks(u, 2)
    assert hp_after_2_ticks >= 10


def test_field_cook_extends_campfire():
    u = _make_worker("sturdy", "deep_reserves", "field_cook")
    from gartok.group import Group
    g = Group([u], node="wilds")
    u.give_to_pack("Flint and Steel")
    u.give_to_pack("Lumber")
    u.give_to_pack("1kg Coal")
    assert g.can_light_campfire()
    assert g.light_campfire(clock_seconds=1000)
    # Field campfire lasts 6 hours (21600s) instead of 4 hours (14400s)
    assert g.campfire_expires == 1000 + 6 * 3600


# --------------------------------------------------------------------------- #
# WIS: Observant, Field Medic, Beast Whisperer, Triage, Pathfinder            #
# --------------------------------------------------------------------------- #

def test_wis_tree_attributes_and_beast_whisperer():
    u = Unit("player", name="Plain", race=data.race_by_name("Human"))
    u.work_hours = economy.LUMBER_XP_HOURS * 30
    u.base_attributes["wisdom"] = 12
    u._apply_attributes()
    u._derive_combat()
    base_wis = u.wisdom
    assert u.choose_talent("work", "observant")
    assert u.wisdom == base_wis + 1

    from gartok.group import Group
    g = Group([u])
    cap_before = g.herd_capacity
    assert u.choose_talent("work", "beast_whisperer")
    assert u.talent_bonus("herd_capacity_bonus") == 1
    assert g.herd_capacity == cap_before + 1


def test_field_medic_bonus_on_first_aid_and_stabilize():
    u = _make_worker("observant", "field_medic")
    assert u.talent_bonus("field_medic_bonus") == 2


def test_pathfinder_reduces_travel_pace():
    from gartok import vocations
    from gartok.group import Group
    from gartok.guild import Guild
    plain = Group([_make_worker()], node="city")
    scout = Group([_make_worker("observant", "beast_whisperer", "pathfinder")], node="city")
    guild = Guild(None, groups=[plain, scout])
    slow = orders.travel(plain, "farm", vocations.travel_mult(guild, plain))
    fast = orders.travel(scout, "farm", vocations.travel_mult(guild, scout))
    assert fast.eta == pytest.approx(slow.eta * vocations.PATHFINDER_FACTOR)
    assert orders.supply_hours(guild, scout) == pytest.approx(
        orders.supply_hours(guild, plain) * vocations.PATHFINDER_FACTOR)


def test_triage_and_restful_sleep_shorten_the_rest_plan_and_the_clock_agrees():
    import random

    from gartok import rest
    from gartok.clock import Clock
    from gartok.group import Group
    from gartok.guild import Guild
    from tests.helpers import packed

    def rest_party(*medic_talents):
        random.seed(11)
        medic = _make_worker(*medic_talents)
        hurt = _make_worker("sturdy", "restful_sleep")
        for u in (medic, hurt):
            u._base_inventory = packed(["Jerky"] * 12)
        hurt.hp = 1
        g = Group([medic, hurt], node="market")
        guild = Guild(None, groups=[g], clock=Clock(4 * 3600))
        return guild, g, hurt

    guild, g, _ = rest_party()
    slow = rest.until_full(guild, g)
    guild, g, hurt = rest_party("observant", "field_medic", "triage")
    plan = rest.until_full(guild, g)
    assert plan.available and plan.hours < slow.hours
    start = guild.clock.seconds
    g.order = orders.rest(plan.hours)
    while g.busy:
        campaign.advance(guild)
    assert guild.clock.seconds - start == round(plan.hours * 3600)
    assert hurt.hp == hurt.hp_max


def test_the_economy_report_prices_every_work_talent():
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
    import economy_talents

    assert set(economy_talents.ROWS) == {t.id for t in talents.TREE["work"]}


@pytest.mark.balance
def test_a_work_talent_is_priced_against_the_same_member_without_it():
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
    import economy_talents

    rows = {t.id: (worth, per_day) for t, worth, _unit, per_day, _how in economy_talents.rows()}
    assert rows["heavy_haul"][0] > rows["brawny"][0] > 0
    assert rows["piecework"][1] > 0
    assert rows["troubadour"][1] > 0
    assert rows["restful_sleep"][0] > 0 and rows["triage"][0] > 0
    assert rows["pathfinder"][0] > 0

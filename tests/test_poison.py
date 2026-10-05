"""Giant Spider Venom: a stacking, Dexterity-eating poison that outlives the fight,
wears off one step per 24h, and the Antidote (made of the spider's gland)."""

import random

import pytest

from gartok import actions, data, items, persist, poisons
from gartok.battle import Battle
from gartok.ground import GroundObject
from gartok.unit import Unit

VENOM = "giant_spider_venom"


def _human(dex=10):
    u = Unit("player", race=data.race_by_name("Human"))
    u.set_base_attribute("dexterity", dex)
    return u


def _spider(racial=0):
    random.seed(31)
    sp = Unit("enemy", race=data.race_by_name("Giant Spider"))
    if racial:
        sp.set_track_level("racial", racial)
    return sp


def _force(monkeypatch, attack=20, save=1):
    """Pin the attack roll and the Constitution save roll."""
    monkeypatch.setattr("gartok.actions.combat.d20", lambda: attack)
    monkeypatch.setattr(data, "d20", lambda: save)


def _fight(victim_unit=None, spider=None):
    victim_unit = victim_unit or _human()
    spider = spider or _spider()
    batt = Battle([victim_unit], [spider])
    sp = batt.enemy_units[0]
    victim = batt.player_units[0]
    sp.pos, victim.pos = (5, 5), (6, 5)
    batt.board.walls.clear()
    batt.ground[:] = [GroundObject.torch((5, 4))]
    sp.ap = 2
    return batt, sp, victim


# --------------------------------------------------------------------------- #
# the poison itself                                                            #
# --------------------------------------------------------------------------- #

def test_the_save_dc_is_11_plus_the_spiders_racial_level():
    spider = _spider(racial=4)
    assert poisons.save_dc(poisons.get(VENOM), spider) == 15
    assert poisons.save_dc(poisons.get(VENOM), _spider()) == 11


def test_each_stack_costs_a_point_of_dexterity():
    u = _human(dex=12)
    assert u.dexterity == 12
    u.add_poison(VENOM, 11)
    u.add_poison(VENOM, 13)
    assert u.dexterity == 10 and u.poisons[VENOM]["level"] == 2
    assert u.poisons[VENOM]["dc"] == 13                      # the worst DC seen is kept
    assert u.strength == u.base_attributes["strength"]       # only Dexterity is touched
    assert "Giant Spider Venom 2" in u.poison_label


def test_one_stack_wears_off_per_24_hours_and_the_clock_restarts():
    u = _human(dex=12)
    for _ in range(3):
        u.add_poison(VENOM, 11)
    assert u.dexterity == 9
    u.tick_poison(23)
    assert u.poisons[VENOM]["level"] == 3                    # not yet
    events = u.tick_poison(1)
    assert u.poisons[VENOM]["level"] == 2 and u.dexterity == 10 and events
    assert u.poisons[VENOM]["hours"] == 24                   # the next step starts its own 24h
    u.tick_poison(48)
    assert not u.poisoned and u.dexterity == 12


def test_a_fresh_bite_restarts_the_clock():
    u = _human()
    u.add_poison(VENOM, 11)
    u.tick_poison(20)
    u.add_poison(VENOM, 11)
    assert u.poisons[VENOM]["hours"] == 24 and u.poisons[VENOM]["level"] == 2


def test_poison_survives_a_save_and_old_saves_load_clean():
    u = _human(dex=14)
    u.add_poison(VENOM, 12)
    u.add_poison(VENOM, 12)
    u.antidote_cooldown = 9
    d = persist.unit_to_dict(u)
    back = Unit.from_save(d)
    assert back.poisons == u.poisons and back.antidote_cooldown == 9
    assert back.dexterity == u.dexterity == 12
    d.pop("poisons"), d.pop("antidote_cooldown")
    legacy = Unit.from_save(d)
    assert not legacy.poisoned and legacy.antidote_cooldown == 0


def test_the_world_clock_ticks_every_roster_members_poison():
    from gartok.guild import Guild
    g = Guild([Unit("player"), Unit("player")])
    member = g.roster[0]
    member.add_poison(VENOM, 11)
    member.add_poison(VENOM, 11)
    g.pass_time(24)
    assert member.poisons[VENOM]["level"] == 1


# --------------------------------------------------------------------------- #
# the bite                                                                     #
# --------------------------------------------------------------------------- #

def test_a_bite_that_hurts_forces_a_save_and_a_failure_poisons(monkeypatch):
    _force(monkeypatch, save=1)
    batt, sp, victim = _fight()
    actions._resolve_hit(batt, sp, victim, 20, 0, "", "bite")
    assert victim.char.poisons[VENOM]["level"] == 1
    assert victim.char.dexterity == 9                        # 10 - 1


def test_a_passed_save_leaves_no_poison(monkeypatch):
    _force(monkeypatch, save=20)
    batt, sp, victim = _fight()
    actions._resolve_hit(batt, sp, victim, 20, 0, "", "bite")
    assert not victim.char.poisoned


def test_a_miss_or_a_non_venomous_attacker_never_poisons(monkeypatch):
    _force(monkeypatch, save=1)
    batt, sp, victim = _fight()
    actions._resolve_hit(batt, sp, victim, 2, -50, "", "bite")      # a miss
    assert not victim.char.poisoned
    wolf = Unit("enemy", race=data.race_by_name("Wolf"))
    batt2 = Battle([_human()], [wolf])
    w, v = batt2.enemy_units[0], batt2.player_units[0]
    actions._resolve_hit(batt2, w, v, 20, 0, "", "bite")
    assert not v.char.poisoned


def test_the_stacks_pile_up_across_bites_and_across_the_fight(monkeypatch):
    _force(monkeypatch, save=1)
    batt, sp, victim = _fight()
    for _ in range(3):
        victim.hp = victim.hp_max
        victim.status = "up"
        actions._resolve_hit(batt, sp, victim, 20, 0, "", "bite")
    assert victim.char.poisons[VENOM]["level"] == 3
    assert victim.char.dexterity == 7


def test_a_body_already_on_the_ground_is_not_poisoned_again(monkeypatch):
    _force(monkeypatch, save=1)
    batt, sp, victim = _fight()
    victim.go_down(batt.log)
    actions._resolve_hit(batt, sp, victim, 20, 0, "", "bite")
    assert not victim.char.poisoned


def test_the_ai_spider_poisons_the_party(monkeypatch):
    from gartok import ai
    _force(monkeypatch, attack=20, save=1)
    batt, sp, victim = _fight()
    batt.active_index = 0
    ai.take_turn(batt, sp)
    assert victim.char.poisoned


# --------------------------------------------------------------------------- #
# a physical attribute at zero                                                 #
# --------------------------------------------------------------------------- #

def test_a_unit_with_a_physical_attribute_at_zero_starts_the_battle_dying():
    weak = _human(dex=3)
    for _ in range(3):
        weak.add_poison(VENOM, 11)
    assert weak.dexterity == 0 and weak.zeroed_attribute == "dexterity"
    batt = Battle([weak], [Unit("enemy")])
    assert batt.player_units[0].dying
    healthy = Battle([_human()], [Unit("enemy")])
    assert healthy.player_units[0].alive


def test_poison_that_takes_the_last_point_drops_the_victim_mid_fight(monkeypatch):
    _force(monkeypatch, save=1)
    batt, sp, victim = _fight(_human(dex=4))
    for _ in range(2):
        victim.char.add_poison(VENOM, 11)
    assert victim.alive and victim.char.dexterity == 2
    victim.char.add_poison(VENOM, 11)
    victim.char.add_poison(VENOM, 11)                       # one short of zero already
    victim.status = "up"
    actions._resolve_hit(batt, sp, victim, 20, 0, "", "bite")
    assert victim.char.dexterity <= 0 and victim.dying


@pytest.mark.parametrize("attr", ["strength", "constitution"])
def test_the_zero_rule_covers_all_three_physical_attributes(attr):
    u = _human()
    setattr(u, attr, 0)
    assert u.zeroed_attribute == attr
    u.intelligence = 0
    assert Unit("player", race=data.race_by_name("Human")).zeroed_attribute is None


# --------------------------------------------------------------------------- #
# the gland, the recipe and the Antidote                                       #
# --------------------------------------------------------------------------- #

def test_the_giant_spider_drops_a_venom_gland_half_the_time():
    from gartok import loot

    class Rolls:
        def __init__(self, v):
            self.v = v

        def random(self):
            return self.v

    sp = _spider()
    assert sp.race["drop_item"] == items.VENOM_GLAND_ITEM and sp.race["drop_chance"] == 0.5
    batt = Battle([_human()], [sp])
    assert loot.field_loot(batt, [], rng=Rolls(0.49)).count(items.VENOM_GLAND_ITEM) == 1
    assert items.VENOM_GLAND_ITEM not in loot.field_loot(batt, [], rng=Rolls(0.5))


def test_the_antidote_recipe_wants_a_gland():
    recipe = items.CRAFTING_RECIPES["Antidote"]
    assert items.VENOM_GLAND_ITEM in recipe.materials
    assert "Antidote" in items.APOTHECARY_RECIPES
    assert items.get("Antidote") is not None and items.get("Venom Gland") is not None


def test_an_antidote_save_sheds_one_stack_and_restarts_the_clock(monkeypatch):
    monkeypatch.setattr(data, "d20", lambda: 20)
    u = _human(dex=12)
    u.add_poison(VENOM, 12)
    u.add_poison(VENOM, 12)
    u.tick_poison(10)
    ok, _ = u.apply_antidote()
    assert ok and u.poisons[VENOM]["level"] == 1 and u.dexterity == 11
    assert u.poisons[VENOM]["hours"] == 24
    assert u.antidote_cooldown == poisons.ANTIDOTE_COOLDOWN_HOURS


def test_a_single_stack_clears_on_the_spot_instead_of_waiting_24h(monkeypatch):
    monkeypatch.setattr(data, "d20", lambda: 20)
    u = _human(dex=12)
    u.add_poison(VENOM, 12)
    ok, msg = u.apply_antidote()
    assert ok and not u.poisoned and "clears" in msg and u.dexterity == 12


def test_a_failed_antidote_save_burns_the_dose_and_the_day(monkeypatch):
    monkeypatch.setattr(data, "d20", lambda: 1)
    u = _human()
    u.add_poison(VENOM, 20)
    ok, msg = u.apply_antidote()
    assert not ok and "does not take" in msg
    assert u.poisons[VENOM]["level"] == 1 and u.antidote_cooldown == 24
    assert not u.can_take_antidote
    u.tick_poison(23)
    assert not u.can_take_antidote
    u.add_poison(VENOM, 20)
    u.tick_poison(1)
    assert u.can_take_antidote


def test_one_antidote_a_day_per_character_and_none_for_the_healthy():
    u = _human()
    assert not u.can_take_antidote                           # not poisoned
    u.add_poison(VENOM, 11)
    assert u.can_take_antidote
    u.antidote_cooldown = 10
    assert not u.can_take_antidote


def test_the_group_screen_offers_an_antidote_from_anyones_pack():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    g = Guild([Unit("player"), Unit("player")])
    grp = g.groups[0]
    patient = grp.members[0]
    scr = GroupScreen(None, g, grp, on_back=lambda: None)
    assert not scr._can_treat_poison()
    patient.add_poison(VENOM, 11)
    assert not scr._can_treat_poison()                       # poisoned, but nobody holds an antidote
    holder = grp.members[-1]
    holder.give_to_pack(items.ANTIDOTE_ITEM)
    assert scr._can_treat_poison()
    random.seed(1)
    scr._treat_poison()
    assert not holder.has_item(items.ANTIDOTE_ITEM)
    assert patient.antidote_cooldown == 24
    assert scr.notice and "Antidote" in scr.notice

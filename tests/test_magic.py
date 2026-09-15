"""Magic: casting, AI use, the taverna study system, and save/load.

The system (magic.py, CastSpellAction/ShareMagicAction in actions.py, AI use
in ai.py, the Sleeping condition, and the tavern's "study" garrison job in
guild.py) shipped across four commits with no dedicated tests -- this file is
that coverage. Also exercises the two bugs the gap let through: learned
spells were dropped on save/load (persist.unit_to_dict never wrote
magic_source/spells_known/study_target/study_progress), and Sleep Immunity
(the Elf's racial ability) never actually did anything (the check read a
dataclass field abilities.Ability never defined).
"""

import random

from tests.helpers import Battle, Unit, _melee_battle, fixed_d20
from gartok import actions, ai, data, magic, orders, persist
from gartok.group import Group
from gartok.guild import Guild


def _caster(a, spell_ids):
    a.spells_known = list(spell_ids)
    return a


# --------------------------------------------------------------------------- #
# casting                                                                      #
# --------------------------------------------------------------------------- #

def test_cast_unknown_spell_is_unavailable():
    batt, a, d = _melee_battle()
    a.ap = 2
    spell = actions.CastSpellAction("magic_missile")
    assert spell.available(batt, a) is False


def test_cast_magic_missile_hits_and_damages():
    batt, a, d = _melee_battle()
    _caster(a, ["magic_missile"])
    a.ap = 2
    d.hp = 20
    spell = actions.CastSpellAction("magic_missile")
    assert spell.available(batt, a)
    assert spell.can(batt, a, d)
    with fixed_d20(15):
        spell.execute(batt, a, d)
    assert a.ap == 1
    assert d.hp < 20


def test_cast_magic_missile_natural_1_is_a_critical_miss():
    batt, a, d = _melee_battle()
    _caster(a, ["magic_missile"])
    a.ap = 2
    d.hp = 20
    spell = actions.CastSpellAction("magic_missile")
    with fixed_d20(1):
        spell.execute(batt, a, d)
    assert d.hp == 20                  # no damage rolled on a fumble
    assert a.ap == 1                   # the point is still spent


def test_cast_magic_missile_out_of_range_cannot_target():
    batt, a, d = _melee_battle()
    _caster(a, ["magic_missile"])
    a.ap = 2
    d.pos = (a.pos[0] + 7, a.pos[1])   # range is 6
    spell = actions.CastSpellAction("magic_missile")
    assert spell.can(batt, a, d) is False


def test_cast_light_globe_drops_a_ground_object():
    batt, a, d = _melee_battle()
    _caster(a, ["light_globe"])
    a.ap = 2
    cell = (a.pos[0] - 1, a.pos[1])    # (5,6) is walled by the seeded scenario; one cell over is clear
    n = len(batt.ground)
    spell = actions.CastSpellAction("light_globe")
    assert spell.can(batt, a, cell)
    spell.execute(batt, a, cell)
    assert len(batt.ground) == n + 1
    assert batt.ground[-1].pos == cell


def test_cast_floating_disk_drops_a_ground_object():
    batt, a, d = _melee_battle()
    _caster(a, ["floating_disk"])
    a.ap = 2
    cell = (a.pos[0] - 1, a.pos[1])
    n = len(batt.ground)
    spell = actions.CastSpellAction("floating_disk")
    spell.execute(batt, a, cell)
    assert len(batt.ground) == n + 1
    assert batt.ground[-1].kind == "floating_disk"


def test_cast_sleep_hits_and_applies_the_sleeping_condition():
    batt, a, d = _melee_battle()
    _caster(a, ["sleep"])
    a.ap = 2
    spell = actions.CastSpellAction("sleep")
    with fixed_d20(20):
        spell.execute(batt, a, d)
    assert d.has_condition("sleeping")


def test_cast_sleep_is_resisted_on_a_low_roll():
    batt, a, d = _melee_battle()
    _caster(a, ["sleep"])
    a.ap = 2
    spell = actions.CastSpellAction("sleep")
    with fixed_d20(2):
        spell.execute(batt, a, d)
    assert not d.has_condition("sleeping")


def test_elf_is_immune_to_sleep():
    """Regression: `Ability` had no `sleep_immunity` field, so the Elf's own
    racial ability (data.py's "Elf" row -> ability id "sleep_immunity") never
    actually blocked the spell -- `getattr(ability, "sleep_immunity", False)`
    silently fell through to the default every time."""
    batt, a, d = _melee_battle()
    _caster(a, ["sleep"])
    a.ap = 2
    d.char.race = data.race_by_name("Elf")
    d.char._configure_race()
    with fixed_d20(20):
        actions.CastSpellAction("sleep").execute(batt, a, d)
    assert not d.has_condition("sleeping")


# --------------------------------------------------------------------------- #
# ShareMagicAction (Sprite Initiate)                                          #
# --------------------------------------------------------------------------- #

def test_share_magic_requires_the_sprite_initiate_talent():
    batt, a, d = _melee_battle()
    _caster(a, ["magic_missile"])
    a.ap = 2
    a.char.talents["racial"] = []
    assert actions.ShareMagicAction().available(batt, a) is False


def test_share_magic_teaches_an_ally_a_known_spell():
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")])
    a, mate, _ = batt.units
    a.pos, mate.pos = (5, 5), (5, 6)
    a.char.talents["racial"] = ["sprite_nature_initiate"]
    _caster(a, ["light_globe"])
    a.ap = 2
    assert actions.ShareMagicAction().available(batt, a)
    actions.ShareMagicAction().execute(batt, a)
    assert a.ap == 1
    assert "light_globe" in mate.spells_known


# --------------------------------------------------------------------------- #
# AI                                                                           #
# --------------------------------------------------------------------------- #

def test_ai_prioritizes_sleep_over_a_hand_attack():
    batt, a, d = _melee_battle()
    _caster(a, ["sleep"])
    pick = ai._pick_attack(batt, a, d)
    assert isinstance(pick, actions.SpellAction) and pick.spell.id == "sleep"


def test_ai_does_not_re_sleep_an_already_sleeping_target():
    from gartok.conditions import Sleeping
    batt, a, d = _melee_battle()
    _caster(a, ["sleep"])
    d.add_condition(Sleeping())
    pick = ai._pick_attack(batt, a, d)
    assert not (isinstance(pick, actions.SpellAction) and pick.spell.id == "sleep")


def test_ai_prefers_magic_missile_over_a_weak_hand_attack():
    batt, a, d = _melee_battle()
    _caster(a, ["magic_missile"])
    a.disarm()                         # unarmed: a weak hand die well under 2.5 avg
    pick = ai._pick_attack(batt, a, d)
    assert isinstance(pick, actions.SpellAction) and pick.spell.id == "magic_missile"


# --------------------------------------------------------------------------- #
# the taverna's "study" garrison job (guild.py's daily upkeep)                #
# --------------------------------------------------------------------------- #

def _student(spell_id="light_globe"):
    u = Unit("player")
    u.magic_source = "nature"
    u.study_target = spell_id
    u._base_inventory.append(f"Scroll of {magic.SPELLS[spell_id].name}")
    return u


def test_studying_accumulates_progress_toward_the_spell():
    random.seed(1)
    u = _student()
    u.gold = 1000
    g = Group([u], node="tavern")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("study")

    saved = data.roll
    data.roll = lambda n, faces: 10
    try:
        guild.pass_time(24)
    finally:
        data.roll = saved

    assert u.study_progress == 10 + u.mod_intelligence
    assert u.gold == 1000 - 15                    # economy.TAVERN_STUDY_COST_PER_DAY
    assert "light_globe" not in u.spells_known     # not enough points yet


def test_studying_masters_the_spell_once_enough_points_are_banked():
    random.seed(1)
    u = _student()
    u.gold = 1000
    u.study_progress = magic.points_to_learn(magic.SPELLS["light_globe"]) - 1
    g = Group([u], node="tavern")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("study")

    saved = data.roll
    data.roll = lambda n, faces: 20                # guarantee enough points regardless of INT mod
    try:
        guild.pass_time(24)
    finally:
        data.roll = saved

    assert "light_globe" in u.spells_known
    assert u.study_target is None
    assert u.study_progress == 0


def test_studying_without_gold_makes_no_progress():
    random.seed(1)
    u = _student()
    u.gold = 0
    g = Group([u], node="tavern")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("study")

    guild.pass_time(24)

    assert u.study_progress == 0
    assert u.gold == 0


def test_studying_without_the_scroll_makes_no_progress():
    random.seed(1)
    u = _student()
    u._base_inventory.clear()          # scroll consumed/sold/never bought
    u.gold = 1000
    g = Group([u], node="tavern")
    guild = Guild(None, groups=[g])
    g.order = orders.garrison("study")

    guild.pass_time(24)

    assert u.study_progress == 0
    assert u.gold == 1000 - 15         # the room is still rented either way


# --------------------------------------------------------------------------- #
# persistence (the headline bug: magic state was dropped on save/load)        #
# --------------------------------------------------------------------------- #

def test_magic_state_survives_a_save_round_trip():
    import os

    slot = persist.NUM_SLOTS - 1
    if os.path.exists(persist.slot_path(slot)):
        return
    random.seed(1)
    u = Unit("player")
    u.magic_source = "nature"
    u.spells_known = ["light_globe", "sleep"]
    u.study_target = "magic_missile"
    u.study_progress = 42
    guild = Guild([u])
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        back_u = back.roster[0]
        assert back_u.magic_source == "nature"
        assert back_u.spells_known == ["light_globe", "sleep"]
        assert back_u.study_target == "magic_missile"
        assert back_u.study_progress == 42
    finally:
        persist.delete_slot(slot)

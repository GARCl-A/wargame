"""Each school's own level-0 / level-1 spells: Grasping Roots (Nature 0), Hex (Blood 0), Spare
the Dying (Faith 0) and Healing Touch (Faith 1), what they do on the board and how the AI uses them;
a scroll for every spell, and Invisibility as the AI's way out of a lethal fight."""

import random

from gartok import actions, ai, data, items, magic
from gartok.battle import Battle
from gartok.scenario import ErmosScenario
from tests.helpers import Unit, _recruit, fixed_d20


def _duel(school, spell, caster_team="enemy"):
    random.seed(4)
    caster, foe = Unit(caster_team), Unit("player" if caster_team == "enemy" else "enemy")
    caster.add_magic_source(school)
    caster.set_spell_known(spell, True)
    sides = ([foe], [caster]) if caster_team == "enemy" else ([caster], [foe])
    b = Battle(*sides, scenario=ErmosScenario())
    b.board.walls = set()
    b.ambient_light = True
    me = next(u for u in b.units if u.char is caster)
    them = next(u for u in b.units if u.char is foe)
    me.pos, them.pos = (5, 5), (8, 5)
    me.ap = 2
    return b, me, them


def _scores(unit, **scores):
    for a in data.ATTRIBUTES:
        setattr(unit.char, a, scores.get(a, 11))
    unit.char._derive_combat()


def test_each_school_has_its_own_level_zero_and_level_one_and_a_scroll_for_each():
    for school in magic.SOURCES:
        own = [s for s in magic.SPELLS.values() if s.sources == (school,)]
        assert {0, 1} <= {s.level for s in own}, school
    for sid in ("grasping_roots", "hex", "spare_the_dying", "healing_touch"):
        spell = magic.SPELLS[sid]
        assert magic.spell_for_scroll(f"Scroll of {spell.name}") is spell
        assert items.get(f"Scroll of {spell.name}").spell_id == sid


# --- Grasping Roots ------------------------------------------------------------------ #

def test_grasping_roots_holds_a_foe_to_one_cell_through_its_next_turn():
    b, me, foe = _duel("nature", "grasping_roots")
    roots = actions.CastSpellAction("grasping_roots")
    assert roots.cost == 1 and roots.can(b, me, foe)
    walk = foe.speed
    with fixed_d20(20):
        roots.execute(b, me, foe)
    assert foe.has_condition("rooted") and foe.speed == 1 < walk
    me.end_turn(b.log)
    foe.start_turn(b.log)
    assert foe.speed == 1                       # still held through its own turn
    foe.end_turn(b.log)
    assert not foe.has_condition("rooted") and foe.speed == walk


def test_grasping_roots_rolls_int_against_ac_and_reaches_six():
    b, me, foe = _duel("nature", "grasping_roots")
    roots = actions.CastSpellAction("grasping_roots")
    with fixed_d20(1):
        roots.execute(b, me, foe)
    assert not foe.has_condition("rooted") and me.ap == 1
    foe.pos = (5 + 7, 5)
    assert not roots.can(b, me, foe)


def test_the_ai_roots_a_melee_foe_a_walk_away_when_holding_it_beats_the_shot():
    b, me, foe = _duel("nature", "grasping_roots")
    me.equip_weapon("Shortbow")
    me.ammo = 5
    _scores(foe, strength=18)
    foe.equip_weapon("Greataxe")
    assert ai._hex_or_roots(b, me, foe).id == "cast_grasping_roots"
    foe.pos = (6, 5)                          # already on it: roots hold nothing
    assert ai._hex_or_roots(b, me, foe) is None
    foe.pos = (5 + 2 + foe.speed + 1, 5)      # no walk brings it in reach this turn anyway
    assert ai._hex_or_roots(b, me, foe) is None


def test_the_ai_shoots_a_weak_foe_instead_of_rooting_it_but_always_roots_a_flag_runner():
    b, me, foe = _duel("nature", "grasping_roots")
    me.equip_weapon("Shortbow")
    me.ammo = 5
    _scores(foe, strength=6)
    foe.equip_weapon("Dagger")
    assert ai._hex_or_roots(b, me, foe) is None
    b.flags, b.flag_carrier = {"player": None, "enemy": (11, 5)}, {"player": None, "enemy": None}  # a walk from it
    assert ai._hex_or_roots(b, me, foe).id == "cast_grasping_roots"


# --- Hex ------------------------------------------------------------------------------ #

def test_hex_drops_only_the_even_scores_and_wears_off_after_the_foe_s_turn():
    b, me, foe = _duel("blood", "hex")
    _scores(foe, strength=14, dexterity=13, constitution=11, intelligence=10, wisdom=12, charisma=9)
    before = {a: getattr(foe, f"mod_{a}") for a in data.ATTRIBUTES}
    md, hp, hp_max = foe.mental_defense, foe.hp, foe.hp_max
    with fixed_d20(20):
        actions.CastSpellAction("hex").execute(b, me, foe)
    after = {a: getattr(foe, f"mod_{a}") for a in data.ATTRIBUTES}
    assert {a: before[a] - after[a] for a in data.ATTRIBUTES} == {
        "strength": 1, "dexterity": 0, "constitution": 0, "intelligence": 1, "wisdom": 1, "charisma": 0}
    assert foe.mental_defense == md - 1 and (foe.hp, foe.hp_max) == (hp, hp_max)   # odd CON: no HP
    assert foe.char.mod_strength == before["strength"]                               # the unit itself is untouched
    foe.start_turn(b.log)
    foe.end_turn(b.log)
    assert not foe.has_condition("hexed")
    assert {a: getattr(foe, f"mod_{a}") for a in data.ATTRIBUTES} == before


def test_an_even_con_costs_a_hit_point_per_hit_die_and_only_the_max_comes_back():
    b, me, foe = _duel("blood", "hex")
    _scores(foe, constitution=12)
    foe.char._level_hp_rolls = [3, 3]          # three hit dice
    foe.char._derive_combat()
    foe.hp = foe.hp_max = 30
    with fixed_d20(20):
        actions.CastSpellAction("hex").execute(b, me, foe)
    assert (foe.hp, foe.hp_max) == (27, 27)
    me.ap = 2
    with fixed_d20(20):
        actions.CastSpellAction("hex").execute(b, me, foe)
    assert (foe.hp, foe.hp_max) == (27, 27)          # a recast renews the hex, it takes no more
    foe.start_turn(b.log)
    foe.end_turn(b.log)
    assert (foe.hp, foe.hp_max) == (27, 30)


def test_hex_rolls_int_against_mental_defense_and_never_stacks():
    b, me, foe = _duel("blood", "hex")
    _scores(foe, strength=14)
    hex_spell = actions.CastSpellAction("hex")
    with fixed_d20(1):
        hex_spell.execute(b, me, foe)
    assert not foe.has_condition("hexed")
    with fixed_d20(20):
        hex_spell.execute(b, me, foe)
        me.ap = 2
        hex_spell.execute(b, me, foe)
    assert [c.id for c in foe.conditions].count("hexed") == 1
    assert foe.mod_strength == foe.char.mod_strength - 1


def test_the_ai_hexes_a_read_foe_when_the_hex_beats_its_own_blow():
    b, me, foe = _duel("blood", "hex")
    _scores(me, intelligence=16)
    me.drop_weapon()
    _scores(foe, strength=16, dexterity=12, constitution=11, intelligence=10, wisdom=10, charisma=9)
    foe.equip_weapon("Greataxe")
    b.intel.margin[me.team][foe] = -10
    assert ai._hex_or_roots(b, me, foe) is None            # attributes unread: Assess first
    b.intel.margin[me.team][foe] = 20
    assert ai._hex_or_roots(b, me, foe).id == "cast_hex"
    _scores(foe, strength=17, dexterity=13, constitution=11, intelligence=11, wisdom=11, charisma=9)
    assert ai._hex_or_roots(b, me, foe) is None            # odd scores: nothing gives


def test_the_ai_swings_rather_than_hex_unless_an_even_constitution_finishes_the_foe():
    b, me, foe = _duel("blood", "hex")
    _scores(me, strength=16, intelligence=12)
    me.equip_weapon("Greataxe")
    _scores(foe, strength=12, dexterity=12, constitution=12, intelligence=10, wisdom=10, charisma=10)
    b.intel.margin[me.team][foe] = 20
    assert ai._hex_or_roots(b, me, foe) is None
    foe.hp = 1
    assert ai._hex_or_roots(b, me, foe).id == "cast_hex"


# --- Spare the Dying and Healing Touch ------------------------------------------------ #

def _faith(spell):
    b, me, _foe = _duel("faith", spell)
    mate = _recruit(b, team=me.team)
    mate.pos = (5, 6)
    return b, me, mate


def test_spare_the_dying_stabilizes_a_dying_ally_in_reach_with_no_check():
    b, me, mate = _faith("spare_the_dying")
    spare = actions.CastSpellAction("spare_the_dying")
    assert not spare.can(b, me, mate)                      # up: nothing to spare
    mate.hp, mate.status = 0, "dying"
    assert spare.can(b, me, mate)
    with fixed_d20(1):
        spare.execute(b, me, mate)
    assert mate.status == "stable" and me.ap == 1
    mate.status, mate.pos = "dying", (5, 8)
    assert not spare.can(b, me, mate)                      # touch only


def test_healing_touch_heals_one_d6_with_nothing_added_and_raises_the_fallen():
    b, me, mate = _faith("healing_touch")
    touch = actions.CastSpellAction("healing_touch")
    mate.hp_max, mate.hp = 30, 10
    random.seed(2)
    touch.execute(b, me, mate)
    assert 11 <= mate.hp <= 16 and me.ap == 1
    mate.hp, mate.status = 0, "dying"
    touch.execute(b, me, mate)
    assert mate.status == "up" and 1 <= mate.hp <= 6
    me.hp_max, me.hp, me.ap = 30, 5, 2
    assert touch.can(b, me, me)                            # the caster may touch themself


def test_the_ai_heals_the_most_hurt_in_reach_and_lifts_a_dying_friend():
    b, me, mate = _faith("healing_touch")
    mate.hp_max, mate.hp = 30, 6
    me.hp = me.hp_max
    assert ai._try_healing_touch(b, me) and mate.hp > 6
    me.char.alignment = "Neutral and Good"
    me.ap = 2
    mate.hp, mate.status = 0, "dying"
    assert ai._ally_to_help(b, me) is mate


def test_a_good_ai_spares_a_dying_friend_with_the_spell_not_the_coin_flip():
    b, me, mate = _faith("spare_the_dying")
    me.char.alignment = "Lawful and Good"
    mate.hp, mate.status = 0, "dying"
    for foe in b.player_units:
        foe.pos = (20, 20)
    with fixed_d20(1):                                     # a Stabilize would fail on this roll
        ai.take_turn(b, me)
    assert mate.status == "stable"


# --- Level 2: the scrolls, and Invisibility as a way out ----------------------------- #

def test_every_spell_has_a_scroll_priced_by_its_level():
    from gartok import economy
    for spell in magic.SPELLS.values():
        scroll = items.get(f"Scroll of {spell.name}")
        assert scroll is not None and scroll.spell_id == spell.id, spell.id
        assert scroll.price == economy.scroll_price(spell.level), spell.id


def test_a_hurt_caster_a_foe_can_reach_vanishes():
    b, me, foe = _duel("nature", "invisibility")
    me.hp = me.hp_max // 4
    assert ai._try_vanish(b, me)
    assert me.has_condition("invisible") and me.ap == 0


def test_a_healthy_caster_does_not_spend_its_turn_vanishing():
    b, me, foe = _duel("nature", "invisibility")
    me.hp = me.hp_max
    assert not ai._try_vanish(b, me) and not me.has_condition("invisible")


def test_no_vanishing_in_an_arena_bout():
    b, me, foe = _duel("nature", "invisibility")
    b.lethal = False
    me.hp = me.hp_max // 4
    assert not ai._try_vanish(b, me)


def test_a_hurt_invisible_unit_makes_for_the_edge_instead_of_striking():
    from gartok.conditions import Invisible
    b, me, foe = _duel("nature", "invisibility")
    me.add_condition(Invisible())
    me.hp = me.hp_max // 3
    foe.pos = (6, 5)                                       # right beside it
    start = me.pos
    ai.take_turn(b, me)
    assert me.has_condition("invisible")                   # it never struck
    assert foe.hp == foe.hp_max and me.pos != start

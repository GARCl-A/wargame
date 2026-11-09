"""A unit that goes down lies Prone and lets go of what its hands hold; the kit it let go of comes back to the
ones that live (`Battle._lay_down_kit`, `Battle.return_dropped_gear`)."""

from gartok import ai
from gartok.web import wiki_session
from tests.helpers import _melee_battle, actions

SHIELD = "Dwarf Shield"
TWO_HANDER = "Glaive"


def _fell(batt, unit, **kw):
    unit.take_damage(unit.hp + 50, batt.log, **kw)


def _kit_on_the_ground(batt, unit):
    return sorted(o.kind for o in batt.ground if o.owner is unit)


def test_a_unit_that_goes_down_lies_prone_and_drops_its_weapon_beside_it():
    batt, a, _d = _melee_battle()
    held = a.weapon_name
    _fell(batt, a)
    assert a.dying and a.has_condition("prone") and not a.weapon_hand
    dropped = [o for o in batt.ground if o.owner is a]
    assert [(o.kind, o.weapon_name) for o in dropped] == [("weapon", held)]
    assert dropped[0].pos != a.pos and max(abs(dropped[0].pos[i] - a.pos[i]) for i in (0, 1)) == 1


def test_a_shield_and_a_torch_fall_with_the_weapon():
    batt, a, _d = _melee_battle()
    a.char.equipped_offhand = SHIELD
    a.shield_ac_delta = 0
    ac = a.ac
    _fell(batt, a)
    assert a.ac == ac - 2
    assert _kit_on_the_ground(batt, a) == ["shield", "weapon"]
    cells = [o.pos for o in batt.ground if o.owner is a]
    assert len(set(cells)) == 2

    batt, a, _d = _melee_battle()
    a.weapon_hand, a.torch_hand = False, True
    _fell(batt, a)
    assert not a.torch_hand and _kit_on_the_ground(batt, a) == ["torch"]


def test_a_natural_weapon_cannot_be_let_go():
    batt, a, _d = _melee_battle()
    a.weapon_hand = False
    _fell(batt, a)
    assert a.has_condition("prone") and _kit_on_the_ground(batt, a) == []


def test_a_knockout_falls_the_same_way():
    batt, a, _d = _melee_battle()
    _fell(batt, a, knockout=True)
    assert a.stable and a.has_condition("prone") and _kit_on_the_ground(batt, a) == ["weapon"]


def test_a_unit_hit_again_on_the_ground_drops_nothing_twice():
    batt, a, _d = _melee_battle()
    _fell(batt, a, knockout=True)
    _fell(batt, a)
    assert _kit_on_the_ground(batt, a) == ["weapon"] and len([c for c in a.conditions if c.id == "prone"]) == 1


def test_with_no_free_cell_around_it_the_kit_lands_on_its_own():
    batt, a, d = _melee_battle()
    batt.board.walls = {p for p in batt.board.neighbors(a.pos)} - {d.pos}
    _fell(batt, a)
    obj = next(o for o in batt.ground if o.owner is a)
    assert obj.pos == a.pos


def test_a_revived_unit_is_still_prone_and_goes_for_its_weapon():
    batt, a, _d = _melee_battle()
    _fell(batt, a)
    held = a.weapon_name
    a.status, a.hp = "up", 3
    assert a.has_condition("prone") and a.unarmed
    a.ap = 2
    ai.take_turn(batt, a)
    assert not a.has_condition("prone")
    assert a.weapon_hand and a.weapon_name == held
    assert not any(o.owner is a for o in batt.ground)


def test_a_shield_on_the_ground_goes_back_on_a_unit_with_an_empty_off_hand():
    batt, a, _d = _melee_battle()
    a.char.equipped_offhand = SHIELD
    a.shield_ac_delta = 0
    ac = a.ac
    held = a.weapon_name
    _fell(batt, a)
    a.status, a.hp, a.ap, a.conditions = "up", 3, 2, []
    batt.ground[:] = [o for o in batt.ground if o.is_shield]
    a.equip_weapon(held)
    assert a.can_take_shield and a.ac == ac - 2
    actions.PICK_UP.execute(batt, a, batt.ground[0])
    assert a.ac == ac and not any(o.is_shield for o in batt.ground)


def test_a_two_hander_leaves_no_hand_for_a_shield():
    batt, a, _d = _melee_battle()
    a.char.equipped_offhand = SHIELD
    a.equip_weapon(TWO_HANDER)
    assert not a.can_take_shield
    _fell(batt, a)
    assert _kit_on_the_ground(batt, a) == ["weapon"]


def test_the_battle_hands_back_what_a_living_unit_let_go_of():
    batt, a, _d = _melee_battle()
    a.char.equipped_offhand = SHIELD
    a.shield_ac_delta = 0
    ac = a.ac
    held = a.weapon_name
    _fell(batt, a, knockout=True)
    assert a.ac == ac - 2
    batt.return_dropped_gear()
    assert a.weapon_hand and a.weapon_name == held and a.ac == ac
    assert not [o for o in batt.ground if o.owner is a]


def test_a_dead_units_kit_stays_on_the_ground_as_loot():
    batt, a, _d = _melee_battle()
    _fell(batt, a)
    a.status = "dead"
    batt.return_dropped_gear()
    assert _kit_on_the_ground(batt, a) == ["weapon"] and not a.weapon_hand


def test_the_wiki_has_a_conditions_chapter_with_the_prone_rule():
    w = wiki_session.WikiSession(lambda: {"screen": "title"})
    st = w.chapter("conditions")
    prone = next(e for e in st["entries"] if e["id"] == "prone")
    assert prone["name"] == "Prone" and prone["kind"] == "Condition" and "0 HP" in prone["body"][0]
    assert "hungry" not in [e["id"] for e in st["entries"]]
    assert all("{" not in b for e in st["entries"] for b in e["body"])

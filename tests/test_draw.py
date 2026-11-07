"""Draw and stow: the hands, the pack they swap with, and the rules of `gartok/draw.py`."""

from gartok import actions, campaign, data, draw
from tests.helpers import _melee_battle, fixed_d20, standard_unit


def _armed(weapon="Dagger", pack=(), off=None):
    batt, a, d = _melee_battle()
    a.equip_weapon(weapon)
    a.inventory = list(pack)
    a.ap = 2
    a.pos, d.pos = (5, 5), (8, 5)
    if off:
        a.equipped_offhand = off
    return batt, a, d


def test_the_action_appears_only_when_the_own_pack_holds_something_to_draw():
    batt, a, _ = _armed(pack=["Rope"])
    assert not actions.DRAW.available(batt, a)
    a.inventory = ["Rope", "Dagger"]
    assert actions.DRAW.available(batt, a)


def test_a_thrown_weapon_is_replaced_from_the_pack():
    batt, a, d = _armed(pack=["Dagger"])
    with fixed_d20(1):
        actions.THROW.execute(batt, a, d)
    assert a.unarmed
    actions.DRAW.execute(batt, a, "Dagger")
    assert a.weapon_name == "Dagger" and not a.unarmed and a.inventory == []
    assert a.ap == 0


def test_a_swap_puts_the_old_weapon_in_the_pack_and_never_on_the_ground():
    batt, a, _ = _armed("Dagger", ["Axe"])
    ground = len(batt.ground)
    actions.DRAW.execute(batt, a, "Axe")
    assert a.weapon_name == "Axe" and a.inventory == ["Dagger"] and len(batt.ground) == ground


def test_a_two_hander_stows_both_hands_in_one_action():
    batt, a, _ = _armed("Dagger", ["Broadsword"])
    a.torch_hand = True
    actions.DRAW.execute(batt, a, "Broadsword")
    assert a.weapon_name == "Broadsword" and not a.torch_hand
    assert sorted(a.inventory) == sorted(["Dagger", data.TORCH_ITEM]) and a.ap == 1


def test_drawing_a_light_over_a_two_hander_leaves_the_weapon_hand_empty():
    batt, a, _ = _armed("Broadsword", [data.TORCH_ITEM])
    actions.DRAW.execute(batt, a, data.TORCH_ITEM)
    assert a.torch_hand and a.unarmed and a.inventory == ["Broadsword"]


def test_a_stow_empties_one_hand():
    batt, a, _ = _armed("Dagger", ["Axe"], off="Dwarf Shield")
    assert [o.target for o in draw.options(a) if o.stow] == ["stow:weapon", "stow:offhand"]
    actions.DRAW.execute(batt, a, "stow:offhand")
    assert a.equipped_offhand is None and sorted(a.inventory) == ["Axe", "Dwarf Shield"]
    assert a.weapon_name == "Dagger"


def test_the_shield_armor_follows_the_hand():
    batt, a, _ = _armed("Dagger", ["Dwarf Shield", "Axe"])
    before = a.ac
    actions.DRAW.execute(batt, a, "Dwarf Shield")
    assert a.ac == before + 2
    actions.DRAW.execute(batt, a, "stow:offhand")
    assert a.ac == before


def test_a_weapon_the_body_cannot_wield_is_listed_with_the_reason():
    batt, a, _ = _armed("Dagger", ["Huge Broadsword"])
    row = next(o for o in draw.options(a) if o.target == "Huge Broadsword")
    assert not row.ok and row.reason
    assert not actions.DRAW.available(batt, a)


def test_the_draw_is_in_the_combat_log():
    batt, a, _ = _armed("Dagger", ["Axe"])
    actions.DRAW.execute(batt, a, "Axe")
    text = str(batt.log_lines if hasattr(batt, "log_lines") else batt.log)
    assert "Axe" in text


def test_the_hands_come_back_to_the_character_after_the_fight():
    batt, a, _ = _armed("Dagger", ["Dwarf Shield", "Axe"])
    actions.DRAW.execute(batt, a, "Dwarf Shield")
    actions.DRAW.execute(batt, a, "Axe")
    member = a.char
    campaign._carry_forward(member, a)
    assert member.equipped_weapon == "Axe" and member.equipped_offhand == "Dwarf Shield"
    assert [n for n, _ in member._base_inventory if n in ("Dagger", "Axe", "Dwarf Shield")] == ["Dagger"]


def test_a_worn_shield_survives_a_fight_without_any_draw():
    _, a, _ = _armed("Dagger")
    a.char.equipped_offhand = "Dwarf Shield"
    campaign._carry_forward(a.char, a)
    assert a.char.equipped_offhand == "Dwarf Shield"


def test_the_ai_draws_a_spare_after_a_throw_before_looking_on_the_ground():
    from gartok.ai import movement
    batt, a, d = _armed("Dagger", ["Dagger", "Broadsword"])
    with fixed_d20(1):
        actions.THROW.execute(batt, a, d)
    assert movement._recover_weapon(batt, a)
    assert a.weapon_name == "Dagger" and a.inventory == ["Broadsword"]


def _thrower(pack):
    batt, a, d = _armed("Dagger", pack)
    a.char.talents["combat"] = ["strong", "agile", "long_reach", "ready_hand"]
    return batt, a, d


def test_ready_hand_needs_both_branches():
    from gartok import talents
    t = talents.get("ready_hand")
    assert t.needs == ("long_reach", "strong")
    u = standard_unit()
    u.talents["combat"] = ["agile", "long_reach"]
    assert not u.offerable("combat", t)
    u.talents["combat"].append("strong")
    assert u.offerable("combat", t)


def test_a_throw_with_ready_hand_draws_an_identical_weapon_for_free():
    batt, a, d = _thrower(["Dagger", "Dagger"])
    with fixed_d20(1):
        actions.THROW.execute(batt, a, d)
    assert a.weapon_name == "Dagger" and not a.unarmed and a.inventory == ["Dagger"]
    assert a.ap == 1


def test_without_a_spare_or_the_talent_the_hand_stays_empty():
    batt, a, d = _thrower([])
    with fixed_d20(1):
        actions.THROW.execute(batt, a, d)
    assert a.unarmed
    batt, a, d = _armed("Dagger", ["Dagger"])
    with fixed_d20(1):
        actions.THROW.execute(batt, a, d)
    assert a.unarmed


def test_the_ai_throws_with_a_spare_even_with_two_points_left():
    from gartok.ai.attack import _try_throw
    batt, a, d = _thrower(["Dagger"])
    assert a.ap == 2 and a.resupplies_throw
    with fixed_d20(1):
        assert _try_throw(batt, a, d, True)
    assert a.ap == 1 and a.weapon_name == "Dagger" and len([o for o in batt.ground if o.is_weapon]) == 1


def test_a_javelin_charge_also_draws_the_spare():
    batt, a, d = _thrower(["Shortspear"])
    a.equip_weapon("Shortspear")
    a.moved = 3
    with fixed_d20(1):
        actions.JAVELIN_CHARGE.execute(batt, a, d)
    assert a.weapon_name == "Shortspear" and not a.unarmed and a.inventory == []


def test_the_ai_throws_instead_of_demoralizing_when_the_throw_is_worth_more():
    from gartok.ai import reckon
    batt, a, d = _thrower(["Dagger"])
    a.ap = 1
    assert reckon._point_worth(batt, a, d) > 0
    a.char.talents["combat"].remove("ready_hand")
    assert reckon._point_worth(batt, a, d) == 0

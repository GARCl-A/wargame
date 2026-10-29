"""The field's loot split among the survivors, with no pygame (`spoils.Spoils`)."""

import subprocess
import sys

from gartok import aftermath
from gartok.spoils import Spoils
from tests.helpers import standard_unit


def test_spoils_loads_without_pygame():
    code = "import sys; sys.modules['pygame'] = None; import gartok.spoils, gartok.aftermath"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_the_pile_is_stacked():
    s = Spoils([standard_unit()], ["Axe", "Rope", "Axe"])
    assert s.pool == [("Axe", 2), ("Rope", 1)]


def test_part_of_a_stack_goes_to_the_pack_and_the_rest_stays():
    u = standard_unit()
    s = Spoils([u], ["Rope"] * 3)
    s.selected, s._sel_qty = [("pool", 0)], {("pool", 0): 2}
    s._give_many(u, "pack")
    assert u.count_of("Rope") == 2 and s.pool == [("Rope", 1)]


def test_a_worn_slot_takes_one_of_a_stack_and_the_rest_stays_on_the_field():
    u = standard_unit()
    u.equipped_offhand = None
    s = Spoils([u], ["Torch"] * 5)
    s.selected = [("pool", 0)]
    s._give_many(u, "offhand")
    assert u.equipped_offhand == "Torch" and s.pool == [("Torch", 4)]


def test_a_load_past_the_limit_keeps_the_pick():
    u = standard_unit()
    s = Spoils([u], ["Plate Armor"] * 2)
    s.selected = [("pool", 0)]
    s._give_many(u, "pack")
    assert s.selected == [("pool", 0)] and s.notice and u.count_of("Plate Armor") == 0


def test_a_pack_item_goes_back_to_the_field():
    u = standard_unit()
    s = Spoils([u], ["Axe"])
    s.selected = [("pool", 0)]
    s._give_many(u, "pack")
    idx = next(i for i, (n, _) in enumerate(u._base_inventory) if n == "Axe")
    s.selected = [(u, idx)]
    s._give_many("pool", "pack")
    assert s.pool == [("Axe", 1)] and u.count_of("Axe") == 0


def test_take_what_fits_leaves_only_what_nobody_can_carry():
    a, b = standard_unit(), standard_unit()
    s = Spoils([a, b], ["Rope", "Rope"] + ["Plate Armor"] * 3)
    s._auto_pick()
    assert a.count_of("Rope") + b.count_of("Rope") == 2
    assert s.pool == [("Plate Armor", 1)]
    assert all(u.load <= u.carry_max for u in (a, b))


def test_the_memorial_card_counts_the_days():
    u = standard_unit()
    u.joined_day = 3
    c = aftermath.card(aftermath.memorial(u, day=3, cause="Killed in combat"))
    assert c["days"] == "1 day with the guild" and c["span"] == "DAY 3 TO DAY 3"

"""The hubs' desks (`work_desk`, `medic.Ward`, `stables`, `ledger`, `rite.Initiation`, `workbench.Bench`,
`job_board`, `holdings.GarageDesk`, `claim_desk.ClaimDesk`): the rules both front-ends read, with no window."""

import subprocess
import sys

import pytest

from gartok import (
    claim_desk,
    economy,
    gather,
    holdings,
    items,
    job_board,
    ledger,
    medic,
    missions,
    rite,
    stables,
    work_desk,
    workbench,
    world,
)
from gartok.group import Group
from gartok.guild import Guild
from gartok.wagon import Wagon
from tests.helpers import standard_unit


def _band(node_id, copper=0):
    u = standard_unit()
    if copper:
        u.give_to_pack(items.COIN_ITEM, copper)
    guild = Guild([u])
    guild.groups = [Group([u], node_id)]
    return guild, guild.groups[0], u


def test_the_desks_load_without_pygame():
    code = ("import sys; sys.modules['pygame'] = None; "
            "import gartok.work_desk, gartok.medic, gartok.stables, gartok.ledger, gartok.rite, "
            "gartok.workbench, gartok.job_board, gartok.holdings, gartok.claim_desk")
    subprocess.run([sys.executable, "-c", code], check=True)


def test_the_work_desk_pays_each_worker_by_their_level():
    guild, g, u = _band("lumber_yard")
    desk = work_desk.WorkDesk(guild, g, world.node("lumber_yard"))
    assert desk._wage(8) == economy.work_pay("lumber_yard", 8, economy.work_level(u, "lumber_yard"))
    assert desk.hub_cards()[0]["label"] == f"wage for {work_desk.SHIFTS[-1]} h"


def test_the_gather_desk_buys_the_licence_or_says_why_not():
    node = world.node("lumber_yard")
    guild, g, _ = _band("lumber_yard")
    desk = work_desk.GatherDesk(guild, g, node)
    desk.buy_licence()
    assert not guild.has_licence("lumber_yard") and desk.notice == "not enough coin for the licence"
    guild, g, _ = _band("lumber_yard", copper=gather.licence_price("lumber_yard"))
    desk = work_desk.GatherDesk(guild, g, node)
    desk.buy_licence()
    assert guild.has_licence("lumber_yard") and "licence is the guild's" in desk.notice


def test_the_ward_picks_and_treats_the_hurt():
    guild, g, u = _band("apothecary", copper=500)
    u.hp = u.hp_max - 3
    ward = medic.Ward(guild, g)
    assert [q.uid for q in ward._quotes()] == [u.uid]
    ward._toggle(u.uid)
    ok, _ = ward._treat()
    assert ok and u.hp == u.hp_max and not ward.picked


def test_the_stables_sell_an_animal_and_buy_it_back_at_a_loss():
    guild, g, u = _band("farm", copper=500)
    desk = stables.Stables(guild, g)
    desk._buy_animal("Donkey")
    donkey = g.herd[0]
    paid = 500 - u.money
    desk._sell_animal(donkey)
    assert not g.herd and u.money == 500 - paid + stables.resale(donkey.price) < 500


def test_the_wagon_yard_numbers_two_wagons_of_a_kind():
    guild, g, _ = _band("carpenter", copper=1000)
    yard = stables.WagonYard(guild, g)
    yard._buy_wagon("Cart")
    yard._buy_wagon("Cart")
    assert [yard._wagon_label(w) for w in g.wagons] == ["Cart 1", "Cart 2"]


def test_the_ledger_desk_shows_the_gate_to_a_band_nobody_vouches_for():
    guild, g, _ = _band("ledger_hold")
    assert [p["key"] for p in ledger.LedgerDesk(guild, g, lambda: None).panels()] == ["gate"]


def test_the_initiation_names_its_school_and_terms():
    guild, g, _ = _band("nature_grove")
    desk = rite.Initiation(guild, g)
    assert desk.school == "nature"
    assert desk._terms()[0][0] == "The school" and desk._action() is None


def test_the_bench_lists_who_works_here_and_rolls_a_stint():
    guild, g, u = _band("smith")
    u.recipes.append("Bear Trap")
    bench = workbench.Bench(guild, g, "forge")
    assert bench.crafters == [u] and bench.selected_crafter is u
    assert [rid for rid, _, _ in bench._recipes(u)] == ["Bear Trap"]
    assert bench._get_missing_materials("Bear Trap")
    with pytest.raises(ValueError):
        bench._work("Bear Trap", 3)
    assert workbench.Bench(guild, g, "apothecary").crafters == []


def test_the_bench_sees_a_crafter_gone_and_picks_the_next():
    guild, g, u = _band("smith")
    mate = standard_unit()
    for x in (u, mate):
        x.recipes.append("Bear Trap")
    g.members.append(mate)
    bench = workbench.Bench(guild, g, "forge")
    g.members.remove(u)
    bench.refresh()
    assert bench.crafters == [mate] and bench.selected_crafter is mate


def test_the_tanner_board_signs_the_leader_and_pays_on_the_turn_in():
    guild, g, u = _band("tanner")
    board = job_board.TannerBoard(guild, g)
    t = board._template
    assert t is missions.TANNER_HIDES and board._offered
    assert board._job_button(t, None, {})[1:] == (board.accept_label, True)
    assert board.accept(t) and board._mission_of(t) is not None
    assert not board.turn_in(t)
    u.give_to_pack(t.goal_item, t.goal_qty)
    assert board.turn_in(t) and "paid out" in board.notice


def test_each_giver_has_its_board():
    guild, g, _ = _band("city")
    assert job_board.TrustBoard(guild, g).get_templates() == [missions.TRUST_CHEST]
    assert {fn for fn, _ in job_board.BOARDS} == {"tanner", "apothecary", "library", "shrine", "trust"}


def test_the_garage_desk_parks_a_wagon_and_takes_it_out():
    guild, g, _ = _band("city")
    g.wagons.append(Wagon())
    guild.house.owned = True
    guild.house.garage.tier = 1
    desk = holdings.GarageDesk(guild, g)
    desk._act("park_wagon:0")
    assert not g.wagons and len(desk.garage.wagons) == 1 and "parked" in desk.notice
    desk._act("take_wagon:0")
    assert len(g.wagons) == 1


def test_the_garage_desk_refuses_a_bay_the_party_cannot_pay():
    guild, g, _ = _band("city")
    guild.house.owned = True
    desk = holdings.GarageDesk(guild, g)
    desk._act("bay")
    assert desk.garage.tier == 0 and "a bay costs" in desk.notice


def test_a_bay_is_paid_from_the_coins_in_the_cart_and_adds_room_for_one_of_each():
    guild, g, u = _band("city")
    guild.house.owned = True
    u.money = 0
    cart = Wagon("Cart")
    cart.give_to_pack(items.COIN_ITEM, economy.GARAGE_PRICE + 4)
    g.wagons.append(cart)
    desk = holdings.GarageDesk(guild, g)
    assert desk.wealth == economy.GARAGE_PRICE + 4
    desk._act("bay")
    garage = guild.house.garage
    assert garage.tier == 1 and garage.wagon_room == 1 and garage.animal_room == 1 and cart.money == 4


def test_the_claim_desk_banks_the_lumber_in_the_cart_too():
    guild, g, u = _band(world.WILDS_TERRITORY_NODE)
    guild.wilds_claim_stage = "CLEARED"
    cart = Wagon("Cart")
    cart.give_to_pack("Lumber", 3)
    g.wagons.append(cart)
    u.give_to_pack("Lumber", 2)
    desk = claim_desk.ClaimDesk(guild, g)
    assert desk._party_lumber() == 5
    desk._deposit_lumber()
    assert guild.wilds_claim_fence_lumber == 5 and not cart.count_of("Lumber") and not u.count_of("Lumber")


def test_the_claim_desk_hands_out_only_the_lumber_a_pack_can_carry():
    guild, g, u = _band(world.WILDS_TERRITORY_NODE)
    u._base_inventory = []
    u._derive_combat()
    room = int((u.carry_max - u.load) // items.item_weight("Lumber"))
    guild.garrison_stock[world.WILDS_TERRITORY_NODE] = ["Lumber"] * (room + 3)
    claim_desk.ClaimDesk(guild, g)._collect_lumber()
    assert u.count_of("Lumber") == room
    assert guild.garrison_stock[world.WILDS_TERRITORY_NODE] == ["Lumber"] * 3


def test_the_claim_desk_scouts_and_banks_the_carried_lumber():
    guild, g, u = _band(world.WILDS_TERRITORY_NODE)
    desk = claim_desk.ClaimDesk(guild, g)
    desk._scout()
    assert guild.wilds_claim_stage == "SCOUTED" and "scouted" in desk.notice
    guild.wilds_claim_stage = "CLEARED"
    u.give_to_pack("Lumber", 3)
    assert desk._party_lumber() == 3
    desk._deposit_lumber()
    assert guild.wilds_claim_fence_lumber == 3 and not u.count_of("Lumber")


def test_the_claim_desk_garrisons_and_stands_down():
    guild, g, _ = _band(world.WILDS_TERRITORY_NODE)
    guild.wilds_claim_stage = "SWEPT"
    desk = claim_desk.ClaimDesk(guild, g)
    desk._start_garrison()
    assert g.order.kind == "garrison" and g.order.job == "lumber" and guild.wilds_claim_stage == "SUSTAINING"
    desk._toggle_garrison_job()
    assert g.order.job == "hold"
    desk._leave_garrison()
    assert g.order.kind != "garrison"

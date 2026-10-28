"""The hubs' simple desks (`work_desk`, `medic.Ward`, `stables`, `ledger`, `rite.Initiation`): the rules
both front-ends read, with no window."""

import subprocess
import sys

from gartok import (
    economy,
    gather,
    items,
    ledger,
    medic,
    rite,
    stables,
    work_desk,
    world,
)
from gartok.gather_screen import GatherScreen
from gartok.group import Group
from gartok.guild import Guild
from gartok.initiation_screen import InitiationScreen
from gartok.ledger_screen import LedgerScreen
from gartok.medic_screen import MedicScreen
from gartok.stables_screen import StablesScreen, WagonYardScreen
from gartok.work_screen import WorkScreen
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
            "import gartok.work_desk, gartok.medic, gartok.stables, gartok.ledger, gartok.rite")
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


def test_the_pygame_screens_are_the_same_desks():
    guild, g, _ = _band("lumber_yard")
    node = world.node("lumber_yard")
    assert isinstance(WorkScreen(None, guild, g, node, lambda: None), work_desk.WorkDesk)
    assert isinstance(GatherScreen(None, guild, g, node, lambda: None), work_desk.GatherDesk)
    assert isinstance(MedicScreen(None, guild, g, lambda: None), medic.Ward)
    assert isinstance(StablesScreen(None, guild, g, lambda: None), stables.Stables)
    assert isinstance(WagonYardScreen(None, guild, g, lambda: None), stables.WagonYard)
    assert isinstance(LedgerScreen(None, guild, g, lambda: None), ledger.LedgerDesk)
    guild, g, _ = _band("nature_grove")
    assert isinstance(InitiationScreen(None, guild, g, lambda: None), rite.Initiation)

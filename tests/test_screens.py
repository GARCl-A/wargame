"""Screens draw native at any size; the shared modal and drag plumbing."""

import random
from gartok.guild import Guild
from tests.helpers import Unit, data, economy, packed, standard_unit

def test_market_stepper_buys_the_quantity_in_one_drop_and_stops_at_the_purse():
    from gartok.trade import Counter
    random.seed(2)
    buyer = Unit("player")
    buyer._base_inventory = []
    buyer.carry_max = 10_000                          # keep load out of this test
    ms = Counter(Guild([buyer]), [buyer], None)
    ms.deal = []
    unit_price = economy.buy_price("Meat")

    ms.purse = unit_price * 100                       # plenty of coin and carry
    ms.selected = [("stock", "Meat")]
    ms.qty["Meat"] = 10
    ms._drop_on_zone(buyer, "pack")
    assert buyer.count_of("Meat") == 10
    assert ms.purse == unit_price * 90
    assert ms.qty.get("Meat", 1) == 1                 # the stepper resets after a buy

    buyer.carry_max = 10_000                          # _buy re-derived it; keep load out
    ms.purse = unit_price * 3                         # only three affordable
    ms.selected = [("stock", "Meat")]
    ms.qty["Meat"] = 10
    ms._drop_on_zone(buyer, "pack")
    assert buyer.count_of("Meat") == 13
    assert ms.purse == 0 and "3 of 10" in ms.notice


def test_the_band_multidrop_moves_every_picked_pack_item():
    from gartok.band_kit import BandKit
    from gartok.guild import Guild
    random.seed(4)
    a, b = Unit("player"), Unit("player")
    a._base_inventory = packed(["Rope", "Meat", "Torch"])
    b._base_inventory = []
    g = Guild([a, b])
    scr = BandKit(g, g.groups[0])
    scr.selected = [(a, 0), (a, 2)]                       # indices bracket a keeper
    scr._give_many(b, "pack")
    assert a._base_inventory == packed(["Meat"])     # the un-picked row is untouched
    assert sorted(b._base_inventory) == [("Rope", 1), ("Torch", 1)]
    assert scr.selected == []


def test_the_band_multidrop_on_a_hand_takes_the_first_that_fits():
    from gartok.band_kit import BandKit
    from gartok.guild import Guild
    random.seed(4)
    a = Unit("player")
    a.equipped_weapon = None
    a._base_inventory = packed(["Rope", "Dagger"])
    g = Guild([a])
    scr = BandKit(g, g.groups[0])
    scr.selected = [(a, 0), (a, 1)]
    scr._give_many(a, "hand")
    assert a.equipped_weapon == "Dagger" and a._base_inventory == packed(["Rope"])


def test_the_band_distributes_its_load():
    from gartok.band_kit import BandKit
    from gartok.guild import Guild
    u1, u2 = standard_unit(), standard_unit()
    u1._base_inventory = packed(["Stone Brick", "Stone Brick"])
    u2._base_inventory = []
    g = Guild([u1, u2])
    gs = BandKit(g, g.groups[0])
    gs._handle_button("distribute")
    # Heaviest items should be shared across members
    assert len(u1._base_inventory) == 1
    assert len(u2._base_inventory) == 1
    assert gs.notice is not None


def test_a_locked_item_is_exempt_from_distributing_the_load():
    from gartok import data
    from gartok.band_kit import BandKit
    from gartok.guild import Guild

    human = data.race_by_name("Human")
    u1 = Unit("player", race=human)
    u2 = Unit("player", race=human)
    for u in (u1, u2):
        u.set_base_attribute("strength", 10)
        u.equipped_weapon = u.equipped_offhand = u.equipped_armor = None
    u1._base_inventory = packed(["Rope"])
    u2._base_inventory = []
    g = Guild([u1, u2])
    gs = BandKit(g, g.groups[0])
    u1.toggle_lock("Rope")
    assert u1.locked_of("Rope") == 1

    gs._handle_button("distribute")
    assert u1._base_inventory == packed(["Rope"])          # stayed put, still locked


def test_the_band_scroll_menu_hidden_without_a_magic_source():
    from gartok.band_kit import BandKit
    from gartok.guild import Guild

    u = Unit("player")
    u.magic_sources = []
    u._base_inventory = packed(["Scroll of Light Globe"])
    g = Guild([u])
    gs = BandKit(g, g.groups[0])
    assert "study" not in [kind for kind, _label, _arg in gs._menu_rows([(u, 0)])]


def test_the_band_dictionary_right_click_offers_and_toggles_study():
    """Learning a language mirrors learning a spell (see RULES.md "Learning a
    language"): a `Dictionary of <Language>` offers a "study" row --
    no `magic_source` required, unlike scrolls."""
    from gartok.band_kit import BandKit
    from gartok.guild import Guild

    u = Unit("player")
    u.magic_sources = []
    u.languages = ["Ankarin"]
    u._base_inventory = packed(["Dictionary of Elvish"])
    g = Guild([u])
    gs = BandKit(g, g.groups[0])

    def study():
        kind, _label, arg = next(r for r in gs._menu_rows([(u, 0)]) if r[0] == "study")
        gs._menu_run([(u, 0)], kind, arg)

    study()
    assert u.study_target == "Elvish"

    study()                                  # still offered, now toggles off
    assert u.study_target is None


def test_the_band_dictionary_hidden_once_the_language_is_known():
    from gartok.band_kit import BandKit
    from gartok.guild import Guild

    u = Unit("player")
    u.languages = ["Ankarin", "Elvish"]
    u._base_inventory = packed(["Dictionary of Elvish"])
    g = Guild([u])
    gs = BandKit(g, g.groups[0])
    assert "study" not in [kind for kind, _label, _arg in gs._menu_rows([(u, 0)])]


def test_factions_get_unlocks():
    from gartok import factions
    bank_unlocks = factions.get_unlocks("bankers")
    assert any(u.title == "City Property" and u.rep_required == 4 for u in bank_unlocks)

    arena_unlocks = factions.get_unlocks("arena")
    assert any("The Games" in u.title for u in arena_unlocks)

    library_unlocks = factions.get_unlocks("library")
    assert any(u.title == "Expanded Catalog" and u.rep_required == 1 for u in library_unlocks)
    assert any(u.title == "Rare Manuscripts" and u.rep_required == 2 for u in library_unlocks)


def test_attribute_and_derived_help_catalogs():
    for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
        assert k in data.ATTRIBUTE_HELP
        title, desc = data.ATTRIBUTE_HELP[k]
        assert len(title) > 0 and len(desc) > 0

    for k in ("HP", "AC", "MD", "SPD", "INIT"):
        assert k in data.DERIVED_HELP
        title, desc = data.DERIVED_HELP[k]
        assert len(title) > 0 and len(desc) > 0


def test_a_member_studying_shows_the_study_track():
    from gartok.guild_sheet import GuildSheet
    u = Unit("player")
    u.study_target = "magic_missile"
    u.study_progress = 30
    tracks = GuildSheet._tracks(u)
    assert tracks[-1]["label"] == "Academic study" and "Magic Missile" in tracks[-1]["value"]


def test_market_equipping_stack_preserves_remainder():
    from gartok import items, world
    from gartok.trade import Counter

    mnode = next(n for n in world.NODES if n.kind == "market")
    shopper = Unit("player")
    shopper.equipped_offhand = None
    shopper._base_inventory = [items.create_instance("Torch", qty=5)]

    ms = Counter(None, [shopper], mnode)
    ms.selected = [(shopper, 0)]
    ms._drop_on_zone(shopper, "offhand")

    assert shopper.equipped_offhand == "Torch"
    assert len(shopper._base_inventory) == 1
    assert shopper._base_inventory[0].qty == 4


def test_bank_equipping_stack_preserves_remainder():
    from gartok.vault import BankVault

    u = Unit("player")
    u.equipped_offhand = None
    guild = Guild([u])
    guild.bank.put("Torch", 5)

    bs = BankVault(guild, [u])
    bs.selected = [("bank", 0)]
    bs._give_many(u, "offhand")

    assert u.equipped_offhand == "Torch"
    assert len(guild.bank.items) == 1
    assert guild.bank.items[0][1] == 4


def test_house_equipping_stack_preserves_remainder():
    from gartok.vault import HouseVault

    u = Unit("player")
    u.equipped_offhand = None
    guild = Guild([u])
    guild.house.owned = True
    guild.house.stash.put("Torch", 5)

    cps = HouseVault(guild, [u])
    cps.selected = [("house", 0)]
    cps._give_many(u, "offhand")

    assert u.equipped_offhand == "Torch"
    assert len(guild.house.stash.items) == 1
    assert guild.house.stash.items[0][1] == 4

"""The Bankers' trust mission (Sistema 4): accept hands over the sealed chest,
Ledger Hold's fortress ambush fires exactly once for that shipment, the
exchange trades chest for letter, and turning the letter in at the City
closes the arc's 4th deed once the three economic ones are already banked."""

import random

from tests.helpers import Battle, Unit, world
from gartok import campaign, chest, data, factions, missions, orders
from gartok.group import Group
from gartok.guild import Guild


def _guild_with_signer(node="city"):
    random.seed(1)
    signer = Unit("player")
    g = Group([signer], node=node)
    guild = Guild(None, groups=[g])
    return guild, g, signer


def test_accepting_the_trust_mission_hands_over_the_sealed_chest():
    guild, g, signer = _guild_with_signer()
    m = missions.accept(guild, signer, missions.TRUST_CHEST)
    assert data.MISSION_CHEST_ITEM in signer._base_inventory
    assert m.template_id == missions.TRUST_CHEST.id and not m.ambush_done


def test_pending_fortress_ambush_needs_an_active_mission_and_the_chest_in_hand():
    guild, g, signer = _guild_with_signer(node="ledger_hold")
    assert missions.pending_fortress_ambush(guild, g) is None   # no mission yet

    m = missions.accept(guild, signer, missions.TRUST_CHEST)
    assert missions.pending_fortress_ambush(guild, g) is m       # carrying it

    signer._base_inventory.remove(data.MISSION_CHEST_ITEM)
    assert missions.pending_fortress_ambush(guild, g) is None    # handed off already

    signer.give_to_pack(data.MISSION_CHEST_ITEM)
    m.ambush_done = True
    assert missions.pending_fortress_ambush(guild, g) is None    # already sprung


def test_the_fortress_ambush_never_fires_before_ledger_hold():
    """Regression: the ambush check used to skip the node entirely and could
    fire the moment the mission was active and the chest was in hand --
    including at the very node it was accepted at, or at any waypoint along
    the way. It must only ever hit at Ledger Hold itself. 'road' is also
    `unsafe` on its own (Sistema 2) -- zeroed out here so only the fortress
    check (or lack of it) is under test."""
    orig_chance, world.ROAD_AMBUSH_CHANCE = world.ROAD_AMBUSH_CHANCE, 0.0
    try:
        guild, g, signer = _guild_with_signer(node="city")
        missions.accept(guild, signer, missions.TRUST_CHEST)

        g.order = orders.travel(g, "market")      # a plain, unrelated errand -- direct edge
        result = campaign.advance(guild)
        assert g.node == "market" and not result.pending

        g.order = orders.travel(g, "city")        # back, then...
        campaign.advance(guild)
        g.order = orders.travel(g, "road")        # ...a direct edge onto the Old Road
        result2 = campaign.advance(guild)
        assert g.node == "road" and not result2.pending
        assert not missions._active_trust_mission(guild).ambush_done
    finally:
        world.ROAD_AMBUSH_CHANCE = orig_chance


def test_the_fortress_ambush_fires_once_through_campaign_advance():
    guild, g, signer = _guild_with_signer(node="road")
    missions.accept(guild, signer, missions.TRUST_CHEST)
    g.order = orders.travel(g, "ledger_hold")

    result = campaign.advance(guild)

    assert g.node == "ledger_hold" and g.order is None
    order = next(o for grp, o in result.pending if grp is g)
    assert order.kind == "ambush"
    assert len(order.pack) == campaign.FORTRESS_AMBUSH_SIZE
    mission = missions._active_trust_mission(guild)
    assert mission.ambush_done

    # resolve the fight, then send the group away and back -- must not ambush again
    fought = Battle([signer], list(order.pack))
    fought.winner = "player"
    fought.round_no = 1
    fought.player_units[0].status = "up"
    campaign.absorb_battle(guild, [signer], fought, node=world.node("ledger_hold"))
    campaign.resolve_road_ambush(guild, g, order)
    assert g.order.kind == "idle"

    g.order = orders.travel(g, "road")
    campaign.advance(guild)
    g.order = orders.travel(g, "ledger_hold")
    result2 = campaign.advance(guild)
    assert not result2.pending                  # no second ambush for the same shipment


def test_ledger_hold_exchanges_the_chest_for_a_letter():
    from gartok.ledger_screen import LedgerScreen
    guild, g, signer = _guild_with_signer(node="ledger_hold")
    missions.accept(guild, signer, missions.TRUST_CHEST)

    scr = LedgerScreen.__new__(LedgerScreen)
    scr.guild, scr.group, scr.on_done = guild, g, lambda: None
    scr.notice = None
    scr.buttons = [("exchange", None)]
    scr.mouse = (0, 0)

    class _Rect:
        def collidepoint(self, _px):
            return True
    scr.buttons = [("exchange", _Rect())]
    scr._click((0, 0))

    assert data.MISSION_CHEST_ITEM not in signer._base_inventory
    assert data.LETTER_ITEM in signer._base_inventory
    assert scr.notice and "letter of receipt" in scr.notice


def test_turning_in_the_letter_closes_bankers_trust_once_the_economic_deeds_are_done():
    guild, g, signer = _guild_with_signer()
    guild.deeds_done = ["bankers_good_for_business", "bankers_steady_customer",
                        "bankers_diverse_portfolio"]
    guild.reputation["bankers"] = 3
    m = missions.accept(guild, signer, missions.TRUST_CHEST)
    signer._base_inventory.remove(data.MISSION_CHEST_ITEM)
    signer.give_to_pack(data.LETTER_ITEM)

    assert missions.can_turn_in(guild, m)
    earned = missions.turn_in(guild, m)

    assert [d.id for d in earned] == ["bankers_trust"]
    assert guild.reputation["bankers"] == 4
    assert m.state == "done"


def test_turning_in_early_does_not_earn_the_deed_without_the_economic_three():
    guild, g, signer = _guild_with_signer()
    m = missions.accept(guild, signer, missions.TRUST_CHEST)
    signer._base_inventory.remove(data.MISSION_CHEST_ITEM)
    signer.give_to_pack(data.LETTER_ITEM)

    earned = missions.turn_in(guild, m)
    assert earned == [] and guild.reputation.get("bankers", 0) == 0


def test_opening_the_sealed_chest_early_fails_the_mission_and_marks_a_crime():
    guild, g, signer = _guild_with_signer()
    m = missions.accept(guild, signer, missions.TRUST_CHEST)
    from tests.helpers import fixed_d20
    with fixed_d20(data.CHEST_DC):
        opened, gems = missions.open_mission_chest(guild, signer)

    assert opened and gems >= 2
    assert data.MISSION_CHEST_ITEM not in signer._base_inventory
    assert signer._base_inventory.count(data.GEM_ITEM) == gems
    assert m.state == "failed"
    assert signer.crime == 1


def test_missing_the_lock_on_the_sealed_chest_costs_nothing():
    guild, g, signer = _guild_with_signer()
    m = missions.accept(guild, signer, missions.TRUST_CHEST)
    from tests.helpers import fixed_d20
    with fixed_d20(data.CHEST_DC - 1):
        opened, gems = missions.open_mission_chest(guild, signer)

    assert not opened and gems == 0
    assert data.MISSION_CHEST_ITEM in signer._base_inventory
    assert m.state == "active" and signer.crime == 0

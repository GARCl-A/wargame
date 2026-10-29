"""The guild's sheet with no pygame (`guild_sheet.GuildSheet`): the roster, a member's sheet, the charter."""

import random
import subprocess
import sys

from gartok.combatant import Combatant
from gartok.guild import Guild
from gartok.guild_sheet import GuildSheet
from gartok.unit import Unit
from tests.helpers import packed


def _two_band_guild():
    from gartok.group import Group
    from gartok.orders import Order
    a, b, c = Unit("player"), Unit("player"), Unit("player")
    idle = Group([a, b], node="city", leader=a)
    busy = Group([c], node="iron_mine", leader=c)
    busy.order = Order(kind="work", hours=8)
    return Guild([a, b, c], groups=[idle, busy]), a, b, c


def _shown(gs):
    return {m["key"] for b in gs._roster_bands() if not b["collapsed"] for m in b["members"]}


def test_the_sheet_and_the_kit_load_without_pygame():
    code = "import sys; sys.modules['pygame'] = None; import gartok.guild_sheet, gartok.band_kit, gartok.web.guild_session, gartok.web.report_session, gartok.web.wiki_session"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_the_sheet_opens_on_a_member_with_a_level_up_waiting():
    u0, u1 = Unit("player"), Unit("player")
    u1.combat_xp = 15
    u1.collect_levels()
    assert u1.pending_picks
    assert GuildSheet(Guild([u0, u1])).member is u1


def test_sharing_rations_is_a_toggle():
    u = Unit("player")
    gs = GuildSheet(Guild([u]))
    before = u.share_food
    gs._press("share_food")
    assert u.share_food is not before


def test_the_filters_split_bands_by_order_and_alert():
    g, a, b, c = _two_band_guild()
    b.unfed_days = 3
    gs = GuildSheet(g)
    gs.filter_mode = "idle"
    assert _shown(gs) == {a.uid, b.uid}
    gs.filter_mode = "busy"
    assert _shown(gs) == {c.uid}
    gs.filter_mode = "alerts"
    assert _shown(gs) == {b.uid}


def test_a_folded_band_hides_its_members():
    g, _a, _b, c = _two_band_guild()
    gs = GuildSheet(g)
    gs.collapsed_groups ^= {g.groups[0].gid}
    assert _shown(gs) == {c.uid}


def test_distribute_needs_a_band_of_two():
    g, a, _b, c = _two_band_guild()
    gs = GuildSheet(g)

    def live(u):
        row = next(r for r in gs._role_rows(u, g.group_of(u)) if r["key"] == "distribute")
        return row["action"][1]

    assert not live(c) and live(a)


def test_stat_breakdowns_sum_to_the_stat_they_explain():
    for _ in range(40):
        u = Unit("player")
        c = Combatant(u)
        assert sum(v for _, v in u.ac_breakdown()) == c.ac
        assert sum(v for _, v in u.md_breakdown()) == c.mental_defense
        assert sum(v for _, v in u.speed_breakdown()) == c.speed
        assert sum(v for _, v in u.initiative_breakdown()) == c.initiative_bonus()


def test_stat_breakdown_names_armor_and_overload():
    u = Unit("player")
    u.equipped_armor = "Chainmail"
    u._derive_combat()
    assert any("Chainmail" in label for label, _ in u.ac_breakdown())
    u._base_inventory = packed(["Iron Bar"] * 99)
    u._derive_combat()
    assert u.encumbered
    assert ("overloaded", -1) in u.speed_breakdown()


def test_the_charter_reports_slots_notices_and_holdings():
    from gartok.group import BASE_CAPACITY, Group
    random.seed(1)
    members = [Unit("player") for _ in range(BASE_CAPACITY + 4)]
    g = Guild(None, groups=[Group(members, node="city"), Group([Unit("player")], node="city")])
    gs = GuildSheet(g)

    rows = gs._group_rows()
    assert [r["size"] for r in rows] == [len(members), 1]
    assert rows[0]["over"] == len(members) - rows[0]["capacity"] > 0 and rows[0]["note"] == ""

    assert [tone for _, tone in gs._notices()] == ["warn"]     # over capacity, no one has given notice yet

    leaver = g.groups[0].members[1]
    g.leaving[leaver.uid] = g.clock.day + 4
    assert "leaves the guild in 4 days" in gs._group_rows()[0]["note"]
    notices = gs._notices()
    assert [tone for _, tone in notices] == ["bad"]            # the notice replaces the generic warning
    assert leaver.name in notices[0][0] and "4 days" in notices[0][0]

    holdings = {h["name"]: h for h in gs._holdings()}
    assert holdings["City house"]["status"] == "NOT OWNED"
    assert holdings["The Claim"]["status"] == "NOT CLAIMED"
    g.house.owned = True
    g.wilds_claim_stage, g.wilds_claim_owner = "ESTABLISHED", "guild"
    holdings = {h["name"]: h for h in gs._holdings()}
    assert holdings["City house"]["status"] == "OWNED"
    assert holdings["The Claim"]["status"] == "UNGUARDED" and holdings["The Claim"]["tone"] == "warn"


def test_an_unarmed_unarmored_member_reads_bare_hands_and_no_armour():
    u = Unit("player")
    u.equipped_weapon = u.equipped_armor = u.equipped_offhand = None
    u._derive_combat()
    gear = GuildSheet(Guild([u]))._gear_data(u, Combatant(u))
    assert gear["armor"] == "None" and gear["armor_note"] == ""


def test_a_member_card_says_how_many_recruits_they_may_still_sponsor():
    from gartok import recruit
    a, b = Unit("player"), Unit("player")
    g = Guild([a, b])
    b.recruited_by = a.uid
    gs = GuildSheet(g)
    text = gs._sponsor_line(a)
    cap = recruit.capacity(g, a)
    assert f"1 of {cap}" in text and (f"{cap - 1} more" in text or "none left" in text)
    assert "0 of" in gs._sponsor_line(b)


def test_a_sick_member_wears_the_badge_and_is_an_alert():
    g, a, b, _c = _two_band_guild()
    b.sick = True
    gs = GuildSheet(g)
    gs.filter_mode = "alerts"
    assert _shown(gs) == {b.uid}
    assert ("SICK", "bad") in gs._member_data(b, False)["badges"]
    assert "SICK" not in [lbl for lbl, _ in gs._member_data(a, False)["badges"]]

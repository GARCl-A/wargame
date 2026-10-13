import pytest
from gartok import data, factions, missions
from gartok.group import Group
from gartok.guild import Guild
from gartok.ledger_screen import LedgerScreen
from gartok.unit import Unit


def _setup_guild_at_ledger(bankers_trust_done=True):
    u = Unit("player")
    u.name = "Leader"
    group = Group([u], node="ledger_hold")
    guild = Guild(roster=[u], node="ledger_hold")
    guild.groups = [group]
    if bankers_trust_done:
        guild.deeds_done.append("bankers_trust")
    return guild, group, u


def test_make_treefolk_recruit():
    recruit = missions.make_treefolk_recruit()
    assert recruit.race["name"] == "Treefolk"
    assert recruit.base_attributes == {
        "strength": 13,
        "dexterity": 11,
        "constitution": 12,
        "intelligence": 10,
        "wisdom": 10,
        "charisma": 11,
    }
    # Treefolk mods: (-1, 0, 1, -1, 1, 0)
    assert recruit.strength == 12
    assert recruit.dexterity == 11
    assert recruit.constitution == 13
    assert recruit.intelligence == 9
    assert recruit.wisdom == 11
    assert recruit.charisma == 11
    assert recruit.racial_level == 0
    assert recruit.combat_xp == 0
    assert recruit.work_hours == 0
    assert recruit.portrait_file == "treefolk_recruit.png"
    assert recruit.portrait_id == "treefolk_recruit.png"


def test_treefolk_mission_offered_only_after_bankers_trust():
    guild_no_trust, _, _ = _setup_guild_at_ledger(bankers_trust_done=False)
    offers = missions.offers_at(guild_no_trust, "ledger_hold")
    assert not any(t.id == "ledger_treefolk" for t in offers)

    guild_trust, _, _ = _setup_guild_at_ledger(bankers_trust_done=True)
    offers = missions.offers_at(guild_trust, "ledger_hold")
    assert any(t.id == "ledger_treefolk" for t in offers)


def test_accept_treefolk_mentorship():
    guild, group, leader = _setup_guild_at_ledger()
    recruit = missions.make_treefolk_recruit()
    guild.add_member(recruit, group)

    m = missions.accept_treefolk_mentorship(guild, leader, recruit)
    assert m.template_id == "ledger_treefolk"
    assert m.recruit_uid == recruit.uid
    assert m.state == "active"
    assert recruit in guild.roster
    assert recruit in group.members


def test_treefolk_mentorship_turn_in_and_gear_return():
    guild, group, leader = _setup_guild_at_ledger()
    leader.money = 0
    recruit = missions.make_treefolk_recruit()
    guild.add_member(recruit, group)
    m = missions.accept_treefolk_mentorship(guild, leader, recruit)

    # Equip recruit with items
    recruit.equipped_weapon = "Axe"
    recruit.equipped_armor = "Studded Leather"
    recruit.give_to_pack("Red Mushroom", 3)

    # Level 0 recruit cannot be turned in
    assert not missions.can_turn_in(guild, m)
    assert missions.progress(guild, m) == 0

    # Train recruit to racial level 2
    # In progression, racial_level 2 requires racial_xp >= 4 (combat_level + work_level >= 4)
    recruit.set_track_level("combat", 2)
    recruit.set_track_level("work", 2)
    assert recruit.racial_level >= 2

    assert missions.progress(guild, m) == 1
    assert missions.can_turn_in(guild, m)

    # Turn in mission
    earned_deeds = missions.turn_in(guild, m)

    # 1. Recruit removed from guild
    assert recruit not in guild.roster
    assert recruit not in group.members
    assert m.state == "done"

    # 2. Gear & items returned to group leader
    assert leader.has_item("Axe")
    assert leader.has_item("Studded Leather")
    assert leader.count_of("Red Mushroom") == 3

    # 3. $230 reward received
    assert leader.money == 230

    # 4. Deed banked and faction reputation awarded
    assert any(d.id == "ledger_hold_mentoring" for d in earned_deeds)
    assert "ledger_hold_mentoring" in guild.deeds_done
    assert guild.reputation.get("ledger_hold") == 1


def test_ledger_screen_accept_and_deliver_buttons():
    guild, group, leader = _setup_guild_at_ledger()

    scr = LedgerScreen.__new__(LedgerScreen)
    scr.guild, scr.group, scr.on_done = guild, group, lambda: None
    scr.notice = None
    scr.mouse = (0, 0)

    class _Rect:
        def collidepoint(self, _px):
            return True

    # Click accept_mentorship
    scr.buttons = [("accept_mentorship", _Rect())]
    scr._click((0, 0))

    m = next((m for m in guild.missions if m.template_id == "ledger_treefolk"), None)
    assert m is not None and m.state == "active"
    recruit = next((u for u in guild.roster if u.uid == m.recruit_uid), None)
    assert recruit is not None

    # Train recruit to racial level 2
    recruit.set_track_level("combat", 4)
    assert recruit.racial_level >= 2

    # Click deliver_recruit
    scr.buttons = [("deliver_recruit", _Rect())]
    scr._click((0, 0))

    assert m.state == "done"
    assert recruit not in guild.roster
    assert "ledger_hold_mentoring" in guild.deeds_done
    assert scr.notice and "$230 reward" in scr.notice

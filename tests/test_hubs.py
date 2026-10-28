from gartok import world
from gartok.group import Group
from gartok.guild import Guild
from gartok.tavern import Tavern
from gartok.unit import Unit
from gartok.work_desk import WorkDesk
from tests.helpers import packed


def test_library_dictionary_mission_flow():
    from gartok import missions
    u = Unit("player")
    u.languages = ["Ankarin", "Elvish"]
    g = Guild([u])
    group = Group(list(g.roster), "library")

    offers = missions.offers_at(g, "library")
    assert any(t.id == "library_dictionary" for t in offers)

    template = next(t for t in offers if t.id == "library_dictionary")
    m = missions.accept(g, u, template)
    assert m.state == "active"
    assert missions.progress(g, m) == 0
    assert not missions.can_turn_in(g, m)

    u.give_to_pack("Dictionary of Elvish")
    assert missions.progress(g, m) == 1
    assert missions.can_turn_in(g, m)

    u.money = 0
    earned_deeds = missions.turn_in(g, m)
    assert m.state == "done"
    assert not u.has_item("Dictionary of Elvish")
    assert u.money == 250
    assert "library_initiate" in g.deeds_done
    assert g.reputation["library"] == 1


def test_library_shop_locked_before_rep_and_rejects_stocked_dictionaries():
    from gartok import missions
    from gartok.trade import library_stock_dictionaries
    u = Unit("player")
    g = Guild([u])
    group = Group(list(g.roster), "library")
    # Rep == 0: shop has no dictionaries
    assert library_stock_dictionaries(g) == []

    # Rep == 1: shop sells 1 dictionary
    g.reputation["library"] = 1
    stocked = library_stock_dictionaries(g)
    assert len(stocked) == 1
    stocked_dict = stocked[0]

    # Accepting mission and having the stocked dictionary does NOT count
    template = missions.LIBRARY_DICTIONARY
    m = missions.accept(g, u, template)
    u.give_to_pack(stocked_dict)
    assert missions.progress(g, m) == 0
    assert not missions.can_turn_in(g, m)


def test_the_tavern_rents_rooms_for_a_target_and_studies_from_a_mates_pack():
    u1 = Unit("player")
    u1.languages = ["Ankarin"]
    u1.magic_sources = ["nature"]
    u1.spells_known = []
    u2 = Unit("player")
    u2.languages = ["Ankarin"]
    u2.give_to_pack("Scroll of Magic Missile")
    u2.give_to_pack("Dictionary of Dwarvish")
    g = Guild([u1, u2])
    group = Group(list(g.roster), "city")
    desk = Tavern(g, group)

    desk._rent_study()
    assert group.order is None                      # nobody has a target yet
    u2.study_target = "Dwarvish"
    desk._rent_study()
    assert group.order.kind == "garrison" and group.order.job == "study"
    desk._cancel_study()
    assert group.order is None

    options = desk._available_study_options(u1)     # carried by u2
    assert len(options) >= 2
    desk._set_target(u1, options[0])
    assert u1.study_target == options[0]["id"]
    desk._stop_study(u1)
    assert u1.study_target is None


def test_the_tavern_stage_plays_a_show():
    from tests.helpers import fixed_d20
    bard, mute = Unit("player"), Unit("player")
    bard.set_base_attribute("charisma", 18)
    bard._base_inventory = packed(["Musical Instrument"])
    mute._base_inventory = []
    bard.money = mute.money = 0
    g = Guild([bard, mute])
    group = Group(list(g.roster), "city")
    desk = Tavern(g, group)
    desk.perform_hours = 2
    assert desk._performers() == [bard]
    desk.perform_off = {bard}
    assert not desk._performers()
    desk.perform_off = set()
    with fixed_d20(20):
        desk._perform()
    assert bard.money == 2 * ((20 + bard.mod_charisma - 16) // 2) > 0 and mute.money == 0
    assert "Tavern stage" in desk.notice


def test_the_work_tab_pays_by_each_workers_tool():
    from gartok import economy, progression
    u = Unit("player")
    u._base_inventory = []
    u.equipped_weapon = None
    g = Guild([u], node="lumber_yard")
    scr = WorkDesk(g, g.groups[0], world.node("lumber_yard"))
    assert scr._wage(16) == economy.work_pay("lumber_yard", 16, economy.work_level(u, "lumber_yard"))
    assert scr._crew_note(u, "Axe") is None
    u.work_hours = economy.LUMBER_XP_HOURS * next(x for x in range(1000) if progression.work_level(x) >= 1)
    note, tone = scr._crew_note(u, "Axe")
    assert "bare-handed" in note and tone == "money"
    assert scr.hub_cards()[0]["value"] == f"${scr._wage(16)}"

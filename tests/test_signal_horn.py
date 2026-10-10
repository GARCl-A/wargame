"""The artifact slot and the Signal Horn it carries: once per battle, 2 points,
+2 initiative to every ally within 10 squares (which can reorder the turns)."""

import random

from gartok import ai
from tests.helpers import Battle, Unit, actions, items, persist


def _band(n_allies=3, horn=True):
    random.seed(5)
    players = [Unit("player") for _ in range(n_allies + 1)]
    if horn:
        players[0].give_to_artifact("Signal Horn")
    batt = Battle(players, [Unit("enemy")])
    blower, *allies, foe = batt.units
    for i, u in enumerate(batt.units):
        u.pos = (2 + i, 5)
    foe.pos = (20, 5)
    for u, init in zip(batt.units, (20, 15, 10, 5, 1)):
        u.initiative = init
    batt.order = list(batt.units)
    batt.turn_idx = 0
    blower.ap = 2
    return batt, blower, allies, foe


# --------------------------------------------------------------------------- #
# the slot                                                                     #
# --------------------------------------------------------------------------- #

def test_horn_is_an_artifact_and_only_artifacts_fit_the_slot():
    u = Unit("player")
    assert items.is_artifact("Signal Horn") and not items.is_artifact("Dagger")
    assert u.fits_artifact("Signal Horn") and not u.fits_artifact("Dagger")
    assert not u.give_to_artifact("Dagger") and u.equipped_artifact is None
    assert u.give_to_artifact("Signal Horn") and u.equipped_artifact == "Signal Horn"


def test_equipping_an_artifact_returns_the_old_one_to_the_pack_and_take_empties_the_slot():
    u = Unit("player")
    u.give_to_artifact("Signal Horn")
    u.give_to_artifact("Signal Horn")
    assert u.count_of("Signal Horn") == 1
    assert u.take_from_artifact() == "Signal Horn" and u.equipped_artifact is None


def test_artifact_weighs_on_the_load():
    u = Unit("player")
    before = u.load
    u.give_to_artifact("Signal Horn")
    assert u.load == round(before + items.item_weight("Signal Horn"), 1)


def test_artifact_slot_survives_a_save_and_an_old_save_without_it_loads():
    u = Unit("player")
    u.give_to_artifact("Signal Horn")
    d = persist.unit_to_dict(u)
    assert Unit.from_save(d).equipped_artifact == "Signal Horn"
    del d["equipped_artifact"]
    assert Unit.from_save(d).equipped_artifact is None


def test_horn_is_tagged_artifact_and_not_sold_at_the_market():
    from gartok import economy
    assert "Signal Horn" not in economy.MARKET_STOCK
    assert items.item_tag("Signal Horn") == "ARTIFACT"


def test_drag_into_the_artifact_slot_only_takes_artifacts():
    from gartok.dragselect import LoadoutMoveMixin as DragSelectMixin
    u = Unit("player")
    assert DragSelectMixin._fits_slot(u, "artifact", "Signal Horn")
    assert not DragSelectMixin._fits_slot(u, "artifact", "Axe")


def test_screens_draw_the_artifact_slot():
    import pygame

    from gartok.group_screen import GroupScreen
    from gartok.guild import Guild
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    u = Unit("player")
    u.give_to_artifact("Signal Horn")
    scr = GroupScreen(ui_fonts(), (guild := Guild([u])), guild.groups[0], lambda: None)
    assert scr._member_dict(u, [])["artifact"]["name"] == "Signal Horn"
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1600, 1000)))
    assert any(zone == "artifact" for _, _, zone in scr.zones)


def test_editor_draws_the_artifact_row():
    import pygame

    from gartok.char_editor_screen import CharEditorScreen
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    scr = CharEditorScreen(ui_fonts(), lambda: None)
    u = Unit("player")
    u.give_to_artifact("Signal Horn")
    scr._load_unit(u)
    scr.mouse = (0, 0)
    scr.draw(pygame.Surface((1600, 1000)))


# --------------------------------------------------------------------------- #
# the action                                                                   #
# --------------------------------------------------------------------------- #

def test_horn_costs_two_points_and_gives_allies_two_initiative():
    batt, blower, allies, foe = _band()
    before = [a.initiative for a in allies]
    assert actions.SIGNAL_HORN.cost == 2
    assert actions.SIGNAL_HORN.available(batt, blower)
    actions.SIGNAL_HORN.execute(batt, blower)
    assert blower.ap == 0
    assert [a.initiative for a in allies] == [b + 2 for b in before]
    assert foe.initiative == 1 and blower.initiative == 20


def test_horn_is_once_per_battle():
    batt, blower, allies, foe = _band()
    actions.SIGNAL_HORN.execute(batt, blower)
    blower.ap = 2
    assert not actions.SIGNAL_HORN.available(batt, blower)
    assert "Already blown" in actions.SIGNAL_HORN.applicable(batt, blower)[1]
    gain = allies[0].initiative
    actions.SIGNAL_HORN.execute(batt, blower)
    assert allies[0].initiative == gain


def test_horn_needs_the_artifact_equipped_not_just_carried():
    batt, blower, _, _ = _band(horn=False)
    blower.char.give_to_pack("Signal Horn")
    assert not actions.SIGNAL_HORN.applicable(batt, blower)[0]
    assert not actions.SIGNAL_HORN.available(batt, blower)


def test_horn_needs_two_points_left():
    batt, blower, _, _ = _band()
    blower.ap = 1
    assert not actions.SIGNAL_HORN.available(batt, blower)


def test_horn_reaches_ten_squares_not_eleven():
    batt, blower, allies, _ = _band(n_allies=2)
    blower.pos = (0, 5)
    allies[0].pos, allies[1].pos = (10, 5), (11, 5)
    near, far = allies
    before = (near.initiative, far.initiative)
    actions.SIGNAL_HORN.execute(batt, blower)
    assert (near.initiative, far.initiative) == (before[0] + 2, before[1])


def test_horn_with_no_ally_in_range_is_not_available():
    batt, blower, allies, _ = _band(n_allies=1)
    allies[0].pos = (40, 5)
    assert not actions.SIGNAL_HORN.available(batt, blower)


def test_downed_allies_and_enemies_are_not_boosted():
    batt, blower, allies, foe = _band()
    allies[0].status = "dying"
    actions.SIGNAL_HORN.execute(batt, blower)
    assert allies[0].initiative == 15
    assert foe.initiative == 1


def test_horn_can_reorder_the_turns_for_allies_still_to_act():
    batt, blower, (a, b, c), foe = _band()
    a.initiative, b.initiative, c.initiative = 10, 9, 9
    batt.order = [blower, a, b, c, foe]
    # only c is in range
    a.pos = b.pos = (40, 5)
    actions.SIGNAL_HORN.execute(batt, blower)
    assert c.initiative == 11 and b.initiative == 9
    assert batt.order == [blower, c, a, b, foe]


def test_boost_overtakes_only_a_strictly_lower_initiative():
    batt, blower, (a, b, c), foe = _band()
    a.initiative, b.initiative, c.initiative = 12, 10, 8
    batt.order = [blower, a, b, c, foe]
    batt.raise_initiative([c], 2)                       # 10: ties b, does not pass it
    assert batt.order == [blower, a, b, c, foe]
    batt.raise_initiative([c], 1)                       # 11: passes b, not a
    assert batt.order == [blower, a, c, b, foe]


def test_boost_never_moves_anyone_across_the_active_unit():
    batt, blower, (a, b, c), foe = _band()
    batt.order = [a, blower, b, c, foe]
    batt.turn_idx = 1
    a.initiative, blower.initiative, b.initiative, c.initiative = 1, 5, 4, 3
    batt.raise_initiative([a, c], 10)
    assert batt.active is blower and batt.turn_idx == 1
    assert batt.order[0] is a                           # already acted: stays in the head
    assert batt.order[2:] == [c, b, foe]                # still to act: c climbs past b


def test_boost_lets_a_unit_already_acted_climb_among_the_acted():
    batt, blower, (a, b, c), foe = _band()
    batt.order = [a, b, blower, c, foe]
    batt.turn_idx = 2
    a.initiative, b.initiative = 9, 5
    batt.raise_initiative([b], 6)
    assert batt.order[:2] == [b, a] and batt.active is blower


def test_the_active_turn_goes_on_with_the_new_order():
    batt, blower, (a, b, c), foe = _band()
    a.initiative, b.initiative, c.initiative = 10, 9, 9
    batt.order = [blower, a, b, c, foe]
    a.pos = b.pos = (40, 5)
    actions.SIGNAL_HORN.execute(batt, blower)
    batt.end_turn()
    assert batt.active is c


# --------------------------------------------------------------------------- #
# the AI                                                                       #
# --------------------------------------------------------------------------- #

def _enemy_band(horn=True, allies=2):
    random.seed(7)
    foes = [Unit("enemy") for _ in range(allies + 1)]
    if horn:
        foes[0].give_to_artifact("Signal Horn")
    batt = Battle([Unit("player")], foes)
    lead, *rest = batt.enemy_units
    hero = batt.player_units[0]
    hero.pos = (0, 5)
    lead.pos = (14, 5)
    for i, u in enumerate(rest):
        u.pos = (15, 5 + i)
    for i, u in enumerate(batt.units):
        u.initiative = 20 - i
    batt.order = [lead, *rest, hero]
    batt.turn_idx = 0
    lead.ap = 2
    return batt, lead, rest, hero


def test_ai_blows_the_horn_while_the_fight_is_still_far():
    batt, lead, rest, hero = _enemy_band()
    before = [u.initiative for u in rest]
    ai.take_turn(batt, lead)
    assert "signal_horn" in lead.used_abilities
    assert [u.initiative for u in rest] == [b + 2 for b in before]


def test_ai_keeps_the_horn_when_a_foe_is_already_in_reach():
    batt, lead, rest, hero = _enemy_band()
    hero.pos = (13, 5)
    ai.take_turn(batt, lead)
    assert "signal_horn" not in lead.used_abilities


def test_ai_does_not_waste_the_horn_on_a_lone_ally():
    batt, lead, rest, hero = _enemy_band(allies=1)
    ai.take_turn(batt, lead)
    assert "signal_horn" not in lead.used_abilities


def test_ai_without_the_horn_is_unchanged():
    batt, lead, rest, hero = _enemy_band(horn=False)
    ai.take_turn(batt, lead)
    assert "signal_horn" not in lead.used_abilities


def test_ai_blows_it_only_once():
    batt, lead, rest, hero = _enemy_band()
    ai.take_turn(batt, lead)
    batt.turn_idx = 0
    lead.ap = 2
    gains = [u.initiative for u in rest]
    ai.take_turn(batt, lead)
    assert [u.initiative for u in rest] == gains

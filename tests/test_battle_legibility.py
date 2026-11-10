"""Reading the fight at a glance: each side's colour, the weapon in hand, the action named on the board."""

from gartok import abilities, ai, foe_card, intel, keywords, weapon_traits
from gartok.sheet import unit_to_ch
from tests.helpers import _melee_battle, _recruit, actions, fitted, fixed_d20


def test_a_weapon_names_its_own_action_and_a_plain_one_none():
    from gartok import items
    assert weapon_traits.action_name(items.get("Axe")) == "Cleave"
    assert weapon_traits.action_name(items.get("Broadsword")) == "Parry & Strike"
    assert weapon_traits.action_name(None) is None


def test_the_sheet_and_the_foe_card_carry_the_weapon_and_its_action():
    batt, a, d = _melee_battle()
    a.equip_weapon(fitted(a, "Axe"))
    d.equip_weapon(fitted(d, "Broadsword"))
    d.weapon_hand = True
    assert unit_to_ch(a)["weapon"]["action"] == "Cleave"
    card = foe_card.foe_card(intel.known_fields(batt, "player", d))
    assert card["weapon"]["name"] == fitted(d, "Broadsword") and card["weapon"]["action"] == "Parry & Strike"
    assert card["weapon"]["action_tip"].startswith("Parry & Strike\nWeapon action")
    assert all(label != "weapon" for label, _ in card["equipment"])


def test_a_disarmed_foe_shows_bare_hands():
    batt, _, d = _melee_battle()
    d.equip_weapon(fitted(d, "Broadsword"))
    d.disarm()
    card = foe_card.foe_card(intel.known_fields(batt, "player", d))
    assert card["weapon"]["name"] == "Unarmed" and card["weapon"]["action"] == "Wrest"
    assert card["weapon"]["action_tip"]


def test_a_plain_swing_is_not_named():
    batt, a, d = _melee_battle()
    a.ap = 2
    with fixed_d20(15):
        actions.ATTACK.execute(batt, a, d)
    assert batt.acts == []


def test_a_weapon_action_is_named_over_its_actor():
    batt, a, d1 = _melee_battle()
    a.equip_weapon(fitted(a, "Axe"))
    a.ap = 2
    d1.hp = d1.hp_max = 40
    d2 = _recruit(batt, team="enemy")
    d1.pos, d2.pos = (5, 6), (6, 6)
    with fixed_d20(18):
        actions.CLEAVE.execute(batt, a, d1)
    assert batt.acts == [(a, "Cleave", None)]


def test_a_shot_flies_to_its_target_unnamed():
    batt, a, d = _melee_battle()
    batt.board.walls = set()
    batt.ambient_light = True
    a.equip_weapon(fitted(a, "Shortbow"))
    a.ammo = 4
    a.pos, d.pos = (2, 5), (6, 5)
    a.ap = 2
    with fixed_d20(15):
        actions.ATTACK.execute(batt, a, d)
    assert batt.acts == [(a, None, (6, 5))]


def test_a_refused_action_shows_nothing():
    batt, a, d = _melee_battle()
    a.ap = 0
    actions.DEFEND.execute(batt, a)
    actions.THROW.execute(batt, a, d)
    assert batt.acts == []


def test_a_step_is_not_named():
    batt, a, _ = _melee_battle()
    a.ap = 2
    actions.MOVE.execute(batt, a, (5, 4))
    assert batt.acts == []


def test_the_ai_names_its_actions_too():
    batt, a, d = _melee_battle()
    for u in batt.units:
        u._ability = abilities.get("none")
    batt.board.walls = set()
    batt.board.elevation = {}
    batt.ambient_light = True
    d.equip_weapon(fitted(d, "Axe"))
    d.pos, a.pos = (5, 5), (6, 5)
    a.hp = a.hp_max = 30
    _recruit(batt, team="player").pos = (6, 6)
    batt.turn_idx = batt.order.index(d)
    d.ap = 2
    with fixed_d20(18):
        ai.take_turn(batt, d)
    assert (d, "Cleave", None) in batt.acts

NL = chr(10)


def test_the_foe_card_weapon_and_rules_open_their_wiki_entry_on_hover():
    batt, _, d = _melee_battle()
    d.equip_weapon(fitted(d, "Dagger"))
    card = foe_card.foe_card(intel.known_fields(batt, "player", d))
    tip = card["weapon"]["tip"].split(NL)
    assert tip[0] == fitted(d, "Dagger") and keywords.get("brutal").text in tip
    d.disarm()
    assert foe_card.foe_card(intel.known_fields(batt, "player", d))["weapon"]["tip"] == ""
    _, ability = foe_card._format("racial_ability", ("Mighty Shove", "Your Shove throws the target."))
    assert ability.split(NL) == ["Mighty Shove", "Racial ability", "Your Shove throws the target.", keywords.get("shove").text]
    _, talents = foe_card._format("talents", [("Savage Attacks", "Your Critical hits are Brutal 1.")])
    assert set(talents.split(NL)[2:]) == {keywords.get("brutal").text, keywords.get("critical_hit").text}


def test_the_foe_card_names_its_weapon_and_armour_in_the_players_language():
    from gartok import i18n
    batt, _, d = _melee_battle()
    d.equip_weapon(fitted(d, "Quarterstaff"))
    i18n.set_language("pt-br")
    try:
        card = foe_card.foe_card(intel.known_fields(batt, "player", d))
        assert card["weapon"]["name"] == i18n.name("item", fitted(d, "Quarterstaff")) != fitted(d, "Quarterstaff")
        assert card["weapon"]["tip"].split(NL)[0] == card["weapon"]["name"]
        d.disarm()
        assert foe_card.foe_card(intel.known_fields(batt, "player", d))["weapon"]["name"] == "Desarmado"
    finally:
        i18n.set_language("en")

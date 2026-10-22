"""Reading the fight at a glance: each side's colour, the weapon in hand, the action named on the board."""

import os

import pygame

from gartok import abilities, ai, battle_fx, foe_card, intel, weapon_traits
from gartok.ui import battle_panel, board_render, board_style
from gartok.ui.sheet_card import unit_to_ch
from gartok.ui.tokens import fonts
from tests.helpers import _melee_battle, _recruit, actions, fixed_d20

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _rect(*_):
    return pygame.Rect(0, 0, 40, 40)


def _seen(batt, fx, seen=None):
    fx.detect(batt, 40, _rect, _rect, seen=seen, color_of=lambda u: board_render.team_color(u.team))


# --------------------------------------------------------------------------- #
# side colours                                                                #
# --------------------------------------------------------------------------- #

def test_each_side_has_its_colour_and_any_further_side_is_the_third():
    assert board_render.team_color("player") == board_style.PLAYER_C
    assert board_render.team_color("enemy") == board_style.ENEMY_C
    assert board_render.team_color("ally") == board_style.ALLY_C
    assert board_render.team_color("undead") == board_style.THIRD_C
    assert board_render.team_color("bandits") == board_style.THIRD_C


def _chip(team, active=False):
    return {"name": "Ana", "team": team, "known": True, "active": active, "race": "Human",
            "portrait_id": None, "token": "A", "hp_frac": 1.0, "hp_steps": None, "dying": None}


def test_the_initiative_strip_marks_every_chip_with_its_side():
    pygame.init()
    surf = pygame.Surface((900, 46))
    rect = pygame.Rect(0, 0, 900, 46)
    teams = ("player", "ally", "enemy", "undead")
    battle_panel.draw_initiative(surf, fonts(), rect, [_chip(t, active=(t == "enemy")) for t in teams])
    label_w = 8 * 11
    cw = min(8 * 14, (rect.w - label_w - 12) // len(teams))
    for i, team in enumerate(teams):
        stripe = (label_w + i * cw + 2, rect.centery)
        assert surf.get_at(stripe)[:3] == board_render.team_color(team)


def test_the_turn_card_borders_in_the_acting_side():
    pygame.init()
    surf = pygame.Surface((400, 80))
    card = pygame.Rect(0, 0, 400, 74)
    data = {"name": "Bones", "race": "Human", "portrait_id": None, "token": "Z", "team": "undead",
            "stats": "", "ap": 2, "ap_max": 2, "walk": None, "note": None}
    battle_panel.draw_turn_card(surf, fonts(), card, data)
    assert surf.get_at((card.centerx, 0))[:3] == board_style.THIRD_C


# --------------------------------------------------------------------------- #
# the weapon in hand                                                          #
# --------------------------------------------------------------------------- #

def test_a_weapon_names_its_own_action_and_a_plain_one_none():
    from gartok import items
    assert weapon_traits.action_name(items.get("Axe")) == "Cleave"
    assert weapon_traits.action_name(items.get("Broadsword")) == "Parry & Strike"
    assert weapon_traits.action_name(None) is None


def test_the_sheet_and_the_foe_card_carry_the_weapon_and_its_action():
    batt, a, d = _melee_battle()
    a.equip_weapon("Axe")
    d.equip_weapon("Broadsword")
    d.weapon_hand = True
    assert unit_to_ch(a)["weapon"]["action"] == "Cleave"
    card = foe_card.foe_card(intel.known_fields(batt, "player", d))
    assert card["weapon"] == {"name": "Broadsword", "action": "Parry & Strike"}
    assert all(label != "weapon" for label, _ in card["equipment"])


def test_a_disarmed_foe_shows_bare_hands():
    batt, _, d = _melee_battle()
    d.equip_weapon("Broadsword")
    d.disarm()
    card = foe_card.foe_card(intel.known_fields(batt, "player", d))
    assert card["weapon"] == {"name": "unarmed", "action": None}


# --------------------------------------------------------------------------- #
# the action on the board                                                     #
# --------------------------------------------------------------------------- #

def test_a_plain_swing_is_not_named():
    batt, a, d = _melee_battle()
    a.ap = 2
    with fixed_d20(15):
        actions.ATTACK.execute(batt, a, d)
    assert batt.acts == []


def test_a_weapon_action_is_named_over_its_actor():
    batt, a, d1 = _melee_battle()
    a.equip_weapon("Axe")
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
    a.equip_weapon("Shortbow")
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
    d.equip_weapon("Axe")
    d.pos, a.pos = (5, 5), (6, 5)
    a.hp = a.hp_max = 30
    _recruit(batt, team="player").pos = (6, 6)
    batt.turn_idx = batt.order.index(d)
    d.ap = 2
    with fixed_d20(18):
        ai.take_turn(batt, d)
    assert (d, "Cleave", None) in batt.acts


def test_the_screen_floats_the_name_and_flies_the_shot_in_the_side_colour():
    batt, a, d = _melee_battle()
    batt.announce(a, "Power Shot", d.pos)
    fx = battle_fx.BattleFX()
    _seen(batt, fx)
    assert batt.acts == []
    assert [(f["text"], f["color"]) for f in fx._floaters] == [("Power Shot", board_style.PLAYER_C)]
    assert len(fx._shots) == 1 and fx._shots[0]["color"] == board_style.PLAYER_C
    fx.advance(battle_fx.SHOT_MS + battle_fx.TRAIL_MS)
    assert fx._shots == []


def test_an_unseen_actor_shows_neither_name_nor_shot():
    batt, a, d = _melee_battle()
    batt.announce(d, "Magic Missile", a.pos)
    fx = battle_fx.BattleFX()
    _seen(batt, fx, seen=lambda pos: pos != d.pos)
    assert fx._floaters == [] and fx._shots == []
    assert batt.acts == []


def test_the_shot_draws_inside_the_board():
    pygame.init()
    batt, a, d = _melee_battle()
    batt.announce(a, None, d.pos)
    fx = battle_fx.BattleFX()
    fx.detect(batt, 40, lambda u: pygame.Rect(u.pos[0] * 40, u.pos[1] * 40, 40, 40),
              lambda x, y: pygame.Rect(x * 40, y * 40, 40, 40))
    fx.advance(battle_fx.SHOT_MS // 2)
    surf = pygame.Surface((600, 400))
    board = pygame.Rect(0, 0, 600, 400)
    fx.draw(surf, fonts(), board)
    assert surf.get_bounding_rect().w > 0

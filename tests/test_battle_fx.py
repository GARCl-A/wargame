"""The log on the board: the hit flash, the crit banner, and the sounds the same events fire."""

import os
from types import SimpleNamespace

import pygame

from gartok import app as app_mod
from gartok import battle_fx, settings, sound
from gartok.actions.base import _resolve_hit
from gartok.ui import battle_panel, board_render
from gartok.ui.tokens import fonts
from tests.helpers import _melee_battle

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _rect(_u=None, *_):
    return pygame.Rect(0, 0, 40, 40)


def _cell(*_):
    return pygame.Rect(0, 0, 40, 40)


def _heard(monkeypatch):
    played = []
    monkeypatch.setattr(battle_fx.sound, "play", played.append)
    return played


def _watch(fx, batt, seen=None):
    fx.detect(batt, 40, _rect, _cell, seen=seen)


def test_a_crit_queues_its_cue_and_raises_the_banner_with_its_own_sound(monkeypatch):
    played = _heard(monkeypatch)
    batt, a, d = _melee_battle()
    d.hp = d.hp_max = 200
    fx = battle_fx.BattleFX()
    _watch(fx, batt)
    assert _resolve_hit(batt, a, d, 20, 0, "", "test") == "crit"
    assert ("crit", d.pos) in batt.cues
    _watch(fx, batt)
    assert fx.banner is not None and fx.banner_alpha() == 0.0
    assert played == ["crit"]
    assert batt.cues == []
    fx.advance(200)
    assert fx.banner_alpha() == 1.0
    fx.advance(battle_fx.BANNER_MS)
    assert fx.banner is None


def test_a_plain_hit_flashes_the_token_and_thuds(monkeypatch):
    played = _heard(monkeypatch)
    batt, a, d = _melee_battle()
    d.hp = d.hp_max = 200
    fx = battle_fx.BattleFX()
    _watch(fx, batt)
    d.ac_vs = lambda *a, **k: 5
    assert _resolve_hit(batt, a, d, 15, 0, "", "test") == "hit"
    _watch(fx, batt)
    assert played == ["hit"]
    assert fx.banner is None
    assert fx.flash_for(d) == 1.0
    fx.advance(battle_fx.FLASH_MS)
    assert fx.flash_for(d) == 0.0


def test_a_miss_whiffs(monkeypatch):
    played = _heard(monkeypatch)
    batt, a, d = _melee_battle()
    fx = battle_fx.BattleFX()
    _watch(fx, batt)
    d.ac_vs = lambda *a, **k: 99
    assert _resolve_hit(batt, a, d, 5, 0, "", "test") == "miss"
    _watch(fx, batt)
    assert played == ["miss"]


def test_a_fall_sounds_once_with_the_blow(monkeypatch):
    played = _heard(monkeypatch)
    batt, _, d = _melee_battle()
    fx = battle_fx.BattleFX()
    _watch(fx, batt)
    d.take_damage(d.hp + 50, batt.log)
    _watch(fx, batt)
    assert sorted(played) == ["fall", "hit"]
    _watch(fx, batt)
    assert sorted(played) == ["fall", "hit"]


def test_what_the_side_cannot_see_is_heard_but_never_shown(monkeypatch):
    played = _heard(monkeypatch)
    batt, a, d = _melee_battle()
    d.hp = d.hp_max = 200
    fx = battle_fx.BattleFX()
    dark = lambda pos: pos != d.pos
    _watch(fx, batt, seen=dark)
    _resolve_hit(batt, a, d, 20, 0, "", "test")
    _watch(fx, batt, seen=dark)
    assert played == ["crit"]
    assert fx.banner is None
    assert fx.flash_for(d) == 0.0
    assert fx._floaters == []


def test_the_flash_paints_the_token_red():
    pygame.init()
    tok = {"team": "player", "active": False, "race": "Human", "portrait_id": None, "token": "H",
           "hp_frac": 1.0, "hp_steps": None, "torch": False, "defending": False, "ferocity": False,
           "demoralized": False, "flag": None, "focus": None, "downed": False, "dying": None,
           "broken": False}
    plain, struck = pygame.Surface((64, 64)), pygame.Surface((64, 64))
    board_render.draw_unit(plain, fonts(), pygame.Rect(0, 0, 64, 64), tok)
    board_render.draw_unit(struck, fonts(), pygame.Rect(0, 0, 64, 64), {**tok, "flash": 1.0})
    probe = (32, 12)
    (r0, g0, _), (r1, g1, _) = plain.get_at(probe)[:3], struck.get_at(probe)[:3]
    assert r1 - g1 > r0 - g0 + 60


def test_the_banner_draws_inside_the_board_and_not_when_faded():
    pygame.init()
    surf = pygame.Surface((800, 600), pygame.SRCALPHA)
    board = pygame.Rect(100, 50, 600, 500)
    battle_panel.draw_crit_banner(surf, fonts(), board, "Critical hit", 0.0)
    assert surf.get_bounding_rect().w == 0
    battle_panel.draw_crit_banner(surf, fonts(), board, "Critical hit", 1.0)
    drawn = surf.get_bounding_rect()
    assert board.contains(drawn) and drawn.w == board.w
    assert drawn.centery < board.centery


def test_sound_is_silent_until_enabled(monkeypatch):
    monkeypatch.setattr(sound, "_sounds", None)
    sound.play("hit")
    sound.play("no such cue")


def test_volume_zero_plays_nothing(monkeypatch):
    calls = []
    fake = SimpleNamespace(set_volume=lambda v: None, play=lambda: calls.append(1))
    monkeypatch.setattr(sound, "_sounds", {"hit": [fake]})
    monkeypatch.setattr(settings, "get", lambda k: 0)
    sound.play("hit")
    assert calls == []
    monkeypatch.setattr(settings, "get", lambda k: 50)
    sound.play("hit")
    assert calls == [1]


def test_every_cue_file_ships_with_the_game():
    for cue, files in sound.CUES.items():
        assert cue in sound.LEVEL
        for f in files:
            assert os.path.isfile(os.path.join(sound.DIR, f)), f
    assert os.path.isfile(os.path.join(sound.DIR, "LICENSE.txt"))


def test_volume_label():
    assert settings.SPEC["volume"][2] in settings.SPEC["volume"][1]
    monkey = settings._values
    try:
        settings._values = {**{k: d for k, (_, _, d) in settings.SPEC.items()}, "volume": 0}
        assert settings.label("volume") == "VOLUME: OFF"
        settings._values["volume"] = 50
        assert settings.label("volume") == "VOLUME: 50%"
    finally:
        settings._values = monkey


def _dispatcher(money_after):
    guild = SimpleNamespace(money=10)

    def handle(_event):
        guild.money = money_after
    return SimpleNamespace(guild=guild, scene=SimpleNamespace(handle_event=handle))


def test_a_click_on_a_button_clicks_and_money_moving_chinks(monkeypatch):
    played = []
    monkeypatch.setattr(app_mod.sound, "play", played.append)
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0))

    fake = _dispatcher(4)
    monkeypatch.setattr(app_mod, "_pointer_hot", lambda: True)
    app_mod.App._dispatch(fake, click)
    assert played == ["click", "coins"]

    played.clear()
    fake = _dispatcher(10)
    monkeypatch.setattr(app_mod, "_pointer_hot", lambda: False)
    app_mod.App._dispatch(fake, click)
    assert played == []

"""Guild identity: name + banner (colour, emblem), picked at the draft.

Purely cosmetic (see RULES.md and gartok/guild.py's "identity" paragraph) --
`theme.set_player_color` recolours every unit token via `token_badge`.
"""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from tests.helpers import Unit
from gartok import artwork, theme
from gartok.guild import DEFAULT_BANNER_COLOR, DEFAULT_BANNER_ICON, Guild


def test_guild_falls_back_to_the_default_identity_when_none_is_given():
    guild = Guild([Unit("player")], node="city")
    assert guild.name == ""
    assert guild.banner_color == DEFAULT_BANNER_COLOR
    assert guild.banner_icon == DEFAULT_BANNER_ICON


def test_guild_keeps_an_explicitly_chosen_identity():
    guild = Guild([Unit("player")], node="city", name="The Iron Coin",
                  banner_color=(196, 90, 90), banner_icon="wolf-head")
    assert guild.name == "The Iron Coin"
    assert guild.banner_color == (196, 90, 90)
    assert guild.banner_icon == "wolf-head"


def test_banner_icon_resolves_a_known_slug_and_none_for_an_unknown_one():
    pygame.init()
    pygame.display.set_mode((1, 1))
    known = artwork.BANNER_ICONS[0][1]
    assert artwork.banner_icon(known, 24) is not None
    assert artwork.banner_icon("not-a-real-emblem", 24) is None


def test_set_player_color_changes_token_badges_default_fill():
    pygame.init()
    surf = pygame.display.set_mode((64, 64))
    try:
        u = Unit("player")
        fonts = theme.Fonts()
        theme.set_player_color((196, 90, 90))
        surf.fill((0, 0, 0))
        theme.token_badge(surf, (32, 32), u, fonts, r=10)
        corner = surf.get_at((32 - 9, 32))[:3]   # edge of the disc, clear of any glyph
        assert corner != (94, 156, 214)          # not the original default
    finally:
        theme.set_player_color((94, 156, 214))     # don't leak into other tests


def test_leadership_survives_a_save_round_trip_with_identity():
    """Sibling of test_persistence.py's leadership round-trip, but for the
    name/banner fields added alongside it."""
    from gartok import persist
    slot = persist.NUM_SLOTS - 1
    if os.path.exists(persist.slot_path(slot)):
        return                                    # never clobber a real save
    random.seed(12)
    guild = Guild([Unit("player")], node="city", name="Sable Wolves",
                  banner_color=(150, 112, 196), banner_icon="wolf-howl")
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.name == "Sable Wolves"
        assert back.banner_color == (150, 112, 196)
        assert back.banner_icon == "wolf-howl"
    finally:
        persist.delete_slot(slot)


def test_draft_screen_identity_phase_collects_name_and_banner():
    from gartok.theme import Fonts
    from gartok.draft_screen import DraftScreen

    pygame.init()
    screen = pygame.display.set_mode((1600, 900))
    random.seed(9)
    fonts = Fonts()
    result = {}

    def on_done(picks, leader, name, banner_color, banner_icon):
        result.update(picks=picks, leader=leader, name=name,
                      banner_color=banner_color, banner_icon=banner_icon)

    ds = DraftScreen(fonts, on_done)
    for _ in range(3):
        ds.draw(screen)
        rect, _unit = ds.card_rects[0]
        ds._click(rect.center)
    assert ds.phase == "identity"

    ds.draw(screen)                     # populates name_rect / color_rects / icon_rects
    ds._click(ds.name_rect.center)
    assert ds.editing_name
    for ch in "Sable Wolves":
        ds.handle_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=ch))
    ds.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=""))
    assert ds.guild_name == "Sable Wolves" and not ds.editing_name

    chosen_color = ds.color_rects[2][1]
    ds._click(ds.color_rects[2][0].center)
    assert ds.banner_color == chosen_color
    assert theme.PLAYER_C == chosen_color        # live preview actually applied

    chosen_icon = ds.icon_rects[3][1]
    ds._click(ds.icon_rects[3][0].center)
    assert ds.banner_icon == chosen_icon

    ds.draw(screen)                     # re-populates continue_rect at the final layout
    ds._click(ds.continue_rect.center)
    assert ds.phase == "leader"

    ds.draw(screen)
    rect, leader_unit = ds.card_rects[0]
    ds._click(rect.center)

    assert result["leader"] is leader_unit
    assert result["name"] == "Sable Wolves"
    assert result["banner_color"] == chosen_color
    assert result["banner_icon"] == chosen_icon
    theme.set_player_color((94, 156, 214))          # don't leak into other tests

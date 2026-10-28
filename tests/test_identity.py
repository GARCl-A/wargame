"""Guild identity: name + banner (colour, emblem), picked at the draft.

Purely cosmetic (see RULES.md and gartok/guild.py's "identity" paragraph) --
`banner.set_player_color` recolours every unit token via `token_badge`.
"""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from gartok import artwork
from gartok.guild import DEFAULT_BANNER_COLOR, DEFAULT_BANNER_ICON, Guild
from gartok.ui import banner, primitives
from gartok.ui.tokens import fonts
from tests.helpers import Unit


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
        banner.set_player_color((196, 90, 90))
        surf.fill((0, 0, 0))
        primitives.token_badge(surf, fonts(), (32, 32), u, r=10)
        corner = surf.get_at((32 - 9, 32))[:3]   # edge of the disc, clear of any glyph
        assert corner != (94, 156, 214)          # not the original default
    finally:
        banner.set_player_color(banner.DEFAULT_COLOR)     # don't leak into other tests


def test_leadership_survives_a_save_round_trip_with_identity():
    """Sibling of test_persistence.py's leadership round-trip, but for the
    name/banner fields added alongside it."""
    from gartok import persist
    slot = "testworld"
    if os.path.exists(persist.save_path(slot)):
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
        persist.delete_world(slot)










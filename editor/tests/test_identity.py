"""Guild identity: name + banner (colour, emblem), picked at the draft.

Purely cosmetic (see RULES.md and gartok/guild.py's "identity" paragraph) --
`banner.set_player_color` recolours every unit token via `token_badge`.
"""

import os
import random
import pygame
from editor import artwork
from gartok.guild import Guild
from editor.ui import banner, primitives
from editor.ui.tokens import fonts
from tests.helpers import Unit

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

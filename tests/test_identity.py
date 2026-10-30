"""Guild identity: name + banner (colour, emblem), picked at the draft.

Purely cosmetic (see RULES.md and gartok/guild.py's "identity" paragraph) --
`banner.set_player_color` recolours every unit token via `token_badge`.
"""

from gartok.guild import DEFAULT_BANNER_COLOR, DEFAULT_BANNER_ICON, Guild
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

"""The guild's banner colour: the one piece of run-wide presentation state.

Picked at the draft (`guild.BANNER_COLORS`) and recoloured onto every unit
token's disc by `primitives.token_badge`. The battle board keeps its fixed player/enemy colours
(`board_style`) for the token disc and cells; the banner colour only rings the
player's tokens there.
"""

from gartok.guild import DEFAULT_BANNER_COLOR

DEFAULT_COLOR = DEFAULT_BANNER_COLOR

_color = DEFAULT_COLOR


def player_color():
    return _color


def set_player_color(color):
    global _color
    _color = tuple(color)

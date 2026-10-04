"""The guild's banner colour: the one piece of run-wide presentation state.

Picked at the draft (`draft_screen`'s "identity" phase) and recoloured onto
every unit token's disc by `primitives.token_badge` and `combat_card`. A curated
palette, not a free picker -- named like a heraldry tincture list, distinct
enough from the enemy red to stay readable.

`set_player_color` is called once when a guild is created or loaded (`app.py`),
not per frame. It deliberately does not touch the battle board's player/enemy
colour-coding (`board_style`): that is a readability cue, not an identity.
"""

BANNER_COLORS = [
    ("Steel",   (94, 156, 214)),
    ("Teal",    (80, 176, 170)),
    ("Forest",  (104, 176, 108)),
    ("Amber",   (224, 158, 72)),
    ("Crimson", (196, 90, 90)),
    ("Violet",  (150, 112, 196)),
    ("Rose",    (206, 120, 152)),
    ("Slate",   (150, 150, 162)),
]

DEFAULT_COLOR = BANNER_COLORS[0][1]

_color = DEFAULT_COLOR


def player_color():
    return _color


def set_player_color(color):
    global _color
    _color = tuple(color)

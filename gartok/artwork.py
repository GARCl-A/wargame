"""Icon art loaded from `assets/icons/` (game-icons.net silhouettes).

The rest of the render path is procedural (see `theme.py` / `icons.py`); this is
the one module that pulls image files in. It exists because a real drawn
silhouette -- a goblin head, an orc head -- reads better on a unit token than a
single letter ever did.

Everything is cached by `(category, name, px, color)`, so a screen redraw is a
dict hit, not a decode. SVGs are rasterised once at the size asked for.

    from . import artwork
    surf = artwork.icon("head", "goblin-head", 24, color=theme.TOKEN_INK)
    surf = artwork.race_icon("Goblin", 24, color=theme.TOKEN_INK)   # by race name
"""

import functools
import os

import pygame

_HERE = os.path.dirname(os.path.abspath(__file__))
_ICONS = os.path.join(_HERE, "assets", "icons")

_WHITE = (255, 255, 255)


# Race -> head silhouette in assets/icons/head/. A few races have no exact glyph
# (Centaur, Leshy, Sprite) and borrow the nearest read. Keep every value pointing
# at a file that exists -- `icon()` falls back to None (caller draws the letter)
# if one goes missing, but a typo here would silently blank every token.
RACE_ICON = {
    "Dwarf":      "dwarf-face",
    "Automaton":  "robot-helmet",
    "Centaur":    "barbarian",
    "Elf":        "elf-ear",
    "Gnoll":      "fox-head",
    "Gnome":      "wizard-face",
    "Goblin":     "goblin-head",
    "Goliath":    "ogre",
    "Grippli":    "triton-head",
    "Halfling":   "baby-face",
    "Hobgoblin":  "orc-head",
    "Lizardfolk": "lizardman",
    "Human":      "caesar",
    "Kenku":      "kenku-head",
    "Kobold":     "horned-reptile",
    "Leshy":      "totem-head",
    "Orc":        "orc-head",
    "Sprite":     "air-man",
}


@functools.lru_cache(maxsize=1024)
def icon(category, name, px, color=_WHITE):
    """A `px`x`px` RGBA surface of `assets/icons/<category>/<name>.svg`, tinted
    `color`. Returns None if the file is absent (caller falls back to text)."""
    if not name:
        return None
    path = os.path.join(_ICONS, category, name + ".svg")
    if not os.path.isfile(path):
        return None
    px = max(1, int(px))
    try:
        surf = pygame.image.load_sized_svg(path, (px, px))
    except (pygame.error, AttributeError):
        surf = pygame.transform.smoothscale(pygame.image.load(path), (px, px))
    try:
        surf = surf.convert_alpha()
    except pygame.error:                       # no display (headless / tests)
        pass
    if tuple(color) != _WHITE:
        surf = surf.copy()
        surf.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return surf


def race_icon(race_name, px, color=_WHITE):
    """The head silhouette for a race, or None if the race isn't mapped."""
    return icon("head", RACE_ICON.get(race_name), px, color)

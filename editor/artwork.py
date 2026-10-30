"""Icon art loaded from `assets/icons/` (game-icons.net silhouettes).

The rest of the render path is procedural (see `icons.py`); this is
the one module that pulls image files in. It exists because a real drawn
silhouette -- a goblin head, an orc head -- reads better on a unit token than a
single letter ever did.

Everything is cached by `(category, name, px, color)`, so a screen redraw is a
dict hit, not a decode. SVGs are rasterised once at the size asked for.

    from editor import artwork
    from editor.ui import primitives
    surf = artwork.icon("head", "goblin-head", 24, color=primitives.TOKEN_INK)
    surf = artwork.race_icon("Goblin", 24, color=primitives.TOKEN_INK)   # by race name
"""

import functools
import os

import pygame

from gartok.art_files import (
    BANNER_ICONS,
    OCCUPATION_ICON,
    RACE_ICON,
    portrait_path,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ICONS = os.path.join(os.path.dirname(_HERE), "gartok", "assets", "icons")

_WHITE = (255, 255, 255)


def occupation_icon(occupation, px, color=_WHITE):
    slug = OCCUPATION_ICON.get(occupation)
    return icon(slug[0], slug[1], px, color) if slug else None


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
    slug = RACE_ICON.get(race_name)
    if slug is None and isinstance(race_name, str) and "," in race_name:
        slug = RACE_ICON.get(race_name.split(",")[0].strip())
    return icon("head", slug, px, color)


def _load_scaled_portrait(path, px):
    px = max(1, int(px))
    try:
        surf = pygame.image.load(path)
        if surf.get_size() != (px, px):
            surf = pygame.transform.smoothscale(surf, (px, px))
        try:
            surf = surf.convert_alpha()
        except pygame.error:
            pass
        return surf
    except Exception:
        return None


@functools.lru_cache(maxsize=256)
def portrait(race_name, portrait_id, px):
    """Circular medallion portrait for a unit, scaled to `(px, px)`.
    Returns None if the race has no portrait assets (caller falls back to `race_icon`)."""
    path = portrait_path(race_name, portrait_id)
    return None if path is None else _load_scaled_portrait(path, px)


_BANNER_ICON_CATEGORY = {slug: cat for cat, slug, _ in BANNER_ICONS}


def banner_icon(slug, px, color=_WHITE):
    """The emblem art for a `Guild.banner_icon` slug, or None if unmapped
    (an old save could carry a slug from a since-trimmed gallery)."""
    category = _BANNER_ICON_CATEGORY.get(slug)
    return icon(category, slug, px, color) if category else None

"""Icon art loaded from `assets/icons/` (game-icons.net silhouettes).

The rest of the render path is procedural (see `icons.py`); this is
the one module that pulls image files in. It exists because a real drawn
silhouette -- a goblin head, an orc head -- reads better on a unit token than a
single letter ever did.

Everything is cached by `(category, name, px, color)`, so a screen redraw is a
dict hit, not a decode. SVGs are rasterised once at the size asked for.

    from . import artwork
    from .ui import primitives
    surf = artwork.icon("head", "goblin-head", 24, color=primitives.TOKEN_INK)
    surf = artwork.race_icon("Goblin", 24, color=primitives.TOKEN_INK)   # by race name
"""

import functools
import os

import pygame

_HERE = os.path.dirname(os.path.abspath(__file__))
_ICONS = os.path.join(_HERE, "assets", "icons")
_PORTRAITS = os.path.join(_HERE, "assets", "portraits")

_WHITE = (255, 255, 255)


# Race -> head silhouette in assets/icons/head/. A few races have no exact glyph
# (Centaur, Treefolk, Sprite) and borrow the nearest read. Keep every value pointing
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
    "Leshy":      "sprout",
    "Treefolk":   "sprout",
    "Orc":        "orc-head",
    "Sprite":     "air-man",
    "Wolf":       "wolf-head",
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
    Returns None if the race has no portrait assets (caller falls back to `race_icon`).

    If `portrait_id` is a string (e.g. 'ribit.png', 'adelio', 'npc/bufo.png'),
    it pins to that specific image file so the generic race pool does not pick it.
    Otherwise, an integer selects deterministically from the numbered portraits in the pool."""
    if not race_name and not portrait_id:
        return None
    px = max(1, int(px))

    if isinstance(portrait_id, str) and not portrait_id.isdigit():
        p_str = portrait_id.strip()
        candidates = [p_str] if p_str.lower().endswith(".png") else [p_str, f"{p_str}.png"]
        search_dirs = []
        if race_name:
            r_clean = str(race_name).lower().strip()
            if r_clean == "leshy":
                r_clean = "treefolk"
            folder = os.path.join(_PORTRAITS, r_clean)
            if not os.path.isdir(folder):
                alt = r_clean.replace(" ", "_") if " " in r_clean else r_clean.replace("_", " ")
                folder = os.path.join(_PORTRAITS, alt)
            if os.path.isdir(folder):
                search_dirs.append(folder)
        search_dirs.extend([
            os.path.join(_PORTRAITS, "npc"),
            _PORTRAITS,
        ])
        for sdir in search_dirs:
            if not os.path.isdir(sdir):
                continue
            for cand in candidates:
                p_cand = os.path.join(sdir, cand)
                if os.path.isfile(p_cand):
                    return _load_scaled_portrait(p_cand, px)

    if not race_name:
        return None
    r_clean = str(race_name).lower().strip()
    if r_clean == "leshy":
        r_clean = "treefolk"
    folder = os.path.join(_PORTRAITS, r_clean)
    if not os.path.isdir(folder):
        alt = r_clean.replace(" ", "_") if " " in r_clean else r_clean.replace("_", " ")
        alt_folder = os.path.join(_PORTRAITS, alt)
        if os.path.isdir(alt_folder):
            folder = alt_folder
        else:
            return None

    def _sort_key(f):
        stem, _ = os.path.splitext(f)
        return (0, int(stem)) if stem.isdigit() else (1, stem)

    try:
        files = [f for f in sorted(os.listdir(folder), key=_sort_key) if f.lower().endswith(".png")]
    except OSError:
        return None
    if not files:
        return None

    numeric_pool = [f for f in files if os.path.splitext(f)[0].isdigit()]
    pool = numeric_pool if numeric_pool else files

    if isinstance(portrait_id, int) or (isinstance(portrait_id, str) and portrait_id.isdigit()):
        idx = abs(int(portrait_id)) % len(pool)
    else:
        idx = 0
    path = os.path.join(folder, pool[idx])
    return _load_scaled_portrait(path, px)


# A small curated gallery for the guild's banner emblem (see draft_screen.py's
# "identity" phase) -- (category, slug, label). Not every icon under assets/
# reads well tinted at emblem size on a flat disc; this is a hand-picked
# subset, same spirit as RACE_ICON above. `Guild.banner_icon` stores the slug.
BANNER_ICONS = [
    ("action", "shield-bash", "Shield"),
    ("body", "surrounded-shield", "Bulwark"),
    ("body", "bell-shield", "Vigil"),
    ("body", "sword-tie", "Blade"),
    ("action", "wolf-howl", "Wolf Cry"),
    ("head", "wolf-head", "Wolf"),
    ("head", "snake-bite", "Serpent"),
    ("body", "fire-silhouette", "Flame"),
    ("gui", "stars-stack", "Stars"),
    ("body", "psychic-waves", "Storm"),
]
_BANNER_ICON_CATEGORY = {slug: cat for cat, slug, _ in BANNER_ICONS}


def banner_icon(slug, px, color=_WHITE):
    """The emblem art for a `Guild.banner_icon` slug, or None if unmapped
    (an old save could carry a slug from a since-trimmed gallery)."""
    category = _BANNER_ICON_CATEGORY.get(slug)
    return icon(category, slug, px, color) if category else None

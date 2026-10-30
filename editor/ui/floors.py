"""Each place's floor on the battle board: sand and stone in the Arena, grass and trees in the
Wilds, packed earth on the roads, cobbles in the City, rock in the caves, flagstones elsewhere.

    FLOORS                                          -> the floor ids, in the editor's order
    texture(floor, cols, rows, walls)               -> the whole board at `TEX` px a cell (cached)
    blit_board(surf, view, floor, cols, rows, walls) -> the part of it `view` shows, at its zoom
    ground(floor, cols, rows, tile)                 -> the ground alone at `tile` px (the map editor)

The texture is painted once per board (ground, details, the cell lines, the walls and their
shadows) with private `Random`s seeded by the floor and each cell, so it never moves between
frames, a wall that opens changes only its own cell, and the game's dice are never touched. Presentation only: the rules and the AI
never read the floor. Colours are `board_style.FLOOR_STYLES`.
"""

import math
import random
from collections import OrderedDict

import pygame

from editor.ui.board_style import FLOOR_GRID, FLOOR_STYLES, WALL_SHADOW
from editor.ui.tokens import mix
from gartok.scenario import wall_kind

FLOORS = tuple(FLOOR_STYLES)
DEFAULT = "stone"
TEX = 48                         # px a cell in the cached texture; the view scales it to its zoom
_CACHE_SIZE = 4

_textures = OrderedDict()        # (floor, cols, rows, walls) -> Surface
_last_crop = [None, None]        # the crop `blit_board` scaled last: [key, Surface]


def style(floor):
    return FLOOR_STYLES.get(floor) or FLOOR_STYLES[DEFAULT]


def _noise(cols, rows, rng, scale=4):
    """Smooth low-frequency noise in [0, 1] per cell."""
    gw, gh = cols // scale + 2, rows // scale + 2
    grid = [[rng.random() for _ in range(gh)] for _ in range(gw)]
    out = {}
    for x in range(cols):
        for y in range(rows):
            fx, fy = x / scale, y / scale
            ix, iy = int(fx), int(fy)
            tx, ty = fx - ix, fy - iy
            tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
            a = grid[ix][iy] * (1 - tx) + grid[ix + 1][iy] * tx
            b = grid[ix][iy + 1] * (1 - tx) + grid[ix + 1][iy + 1] * tx
            out[(x, y)] = a * (1 - ty) + b * ty
    return out


def _shade(color, rng, amount):
    d = rng.randint(-amount, amount)
    return tuple(max(0, min(255, v + d)) for v in color)


def _base(s, n):
    if "bare" in s:                                # the grass wears to earth where the noise peaks
        return mix(mix(s["lo"], s["hi"], n), s["bare"], max(0.0, (n - 0.62) / 0.38) * 0.8)
    return mix(s["lo"], s["hi"], n)


def _ground_layer(s, cols, rows, tile, noise):
    tint = pygame.Surface((cols, rows))
    for cell, n in noise.items():
        tint.set_at(cell, _base(s, n))
    return pygame.transform.smoothscale(pygame.transform.scale(tint, (cols * 4, rows * 4)),
                                        (cols * tile, rows * tile))


# ---------------------------------------------------------------------- #
# the details each floor scatters over its cells                         #
# ---------------------------------------------------------------------- #
def _stone(surf, s, r, n, rng, near):
    slab = _shade(mix(s["lo"], s["hi"], n), rng, 3)
    surf.fill(slab, r.inflate(-2, -2))
    pygame.draw.rect(surf, s["joint"], r, 1)
    if rng.random() < 0.18:
        y = r.y + rng.randint(r.h // 4, r.h * 3 // 4)
        pygame.draw.line(surf, s["crack"], (r.x + 3, y), (r.x + rng.randint(r.w // 3, r.w - 4),
                                                          y + rng.randint(-r.h // 6, r.h // 6)))


def _arena(surf, s, r, n, rng, near):
    u = r.w / 48
    if near:                                       # a flagstone apron at the foot of every wall
        slab = _shade(s["apron"], rng, 2)
        surf.fill(slab, r)
        pygame.draw.rect(surf, mix(slab, s["joint"], 0.35), r.inflate(-2, -2), 1, border_radius=3)
        return
    base = _base(s, n)
    for _ in range(rng.randint(2, 6)):
        p = (r.x + rng.randint(2, r.w - 3), r.y + rng.randint(2, r.h - 3))
        pygame.draw.circle(surf, mix(base, s["grit"], rng.uniform(0.2, 0.5)), p, 1)
    if rng.random() < 0.12:
        p = (r.x + rng.randint(r.w // 6, r.w * 5 // 6), r.y + rng.randint(r.h // 6, r.h * 5 // 6))
        pygame.draw.ellipse(surf, mix(base, s["pebble"], 0.6), pygame.Rect(p, (round(6 * u), round(4 * u))))
    if rng.random() < 0.10:                        # drag marks in the sand
        y = r.y + rng.randint(r.h // 5, r.h * 4 // 5)
        pygame.draw.arc(surf, mix(base, s["drag"], 0.5), pygame.Rect(r.x + 4, y - 6, r.w - 8, 12), 0.3, 2.8, 1)
    if rng.random() < 0.04:                        # an old bloodstain
        p = (r.x + rng.randint(r.w // 4, r.w * 3 // 4), r.y + rng.randint(r.h // 4, r.h * 3 // 4))
        for _ in range(4):
            q = (p[0] + rng.randint(-5, 5), p[1] + rng.randint(-4, 4))
            pygame.draw.circle(surf, mix(base, s["stain"], 0.55), q, round(rng.randint(2, 4) * u))


def _grass(surf, s, r, n, rng, near):
    base = _base(s, n)
    tufts = 0 if n > 0.82 else rng.randint(3, 8)
    for _ in range(tufts):
        x, y = r.x + rng.randint(3, r.w - 4), r.y + rng.randint(6, r.h - 3)
        pygame.draw.line(surf, mix(base, s["blade"], rng.uniform(0.15, 0.4)),
                         (x, y), (x + rng.randint(-2, 2), y - rng.randint(3, 6)), 1)
    if rng.random() < 0.06:
        for _ in range(rng.randint(2, 4)):
            p = (r.x + rng.randint(6, r.w - 6), r.y + rng.randint(6, r.h - 6))
            pygame.draw.circle(surf, rng.choice(s["flowers"]), p, 1)
    if near and rng.random() < 0.55:               # roots spreading from the trees
        a = rng.uniform(0, 2 * math.pi)
        p = r.center
        for _ in range(4):
            q = (p[0] + math.cos(a) * r.w / 5, p[1] + math.sin(a) * r.w / 5)
            pygame.draw.line(surf, s["root"], p, q, 2)
            p, a = q, a + rng.uniform(-0.6, 0.6)
    if rng.random() < 0.05:
        p = (r.x + rng.randint(8, r.w - 10), r.y + rng.randint(8, r.h - 10))
        pygame.draw.ellipse(surf, s["pebble"], pygame.Rect(p, (8, 5)))


def _earth(surf, s, r, n, rng, near):
    base = _base(s, n)
    for _ in range(rng.randint(1, 4)):
        p = (r.x + rng.randint(3, r.w - 4), r.y + rng.randint(3, r.h - 4))
        pygame.draw.circle(surf, mix(base, s["pebble"], rng.uniform(0.3, 0.7)), p, 1)
    if n < 0.3:                                    # a few blades where the track is least worn
        for _ in range(rng.randint(1, 4)):
            x, y = r.x + rng.randint(3, r.w - 4), r.y + rng.randint(6, r.h - 3)
            pygame.draw.line(surf, mix(base, s["blade"], 0.5), (x, y), (x + rng.randint(-2, 2), y - 4), 1)
    if rng.random() < 0.2:                         # a dry crack
        p = (r.x + rng.randint(4, r.w // 2), r.y + rng.randint(r.h // 4, r.h * 3 // 4))
        for _ in range(3):
            q = (p[0] + rng.randint(r.w // 10, r.w // 5), p[1] + rng.randint(-r.h // 10, r.h // 10))
            pygame.draw.line(surf, mix(base, s["rut"], 0.7), p, q, 1)
            p = q
    if rng.random() < 0.08:
        p = (r.x + rng.randint(8, r.w - 12), r.y + rng.randint(8, r.h - 10))
        pygame.draw.ellipse(surf, s["pebble"], pygame.Rect(p, (7, 5)))


def _cobble(surf, s, r, n, rng, near):
    surf.fill(s["mortar"], r)
    k = 3
    step = r.w / k
    for i in range(k):
        for j in range(k):
            c = pygame.Rect(round(r.x + i * step) + 1, round(r.y + j * step) + 1,
                            round(step) - 2, round(step) - 2)
            tone = _shade(mix(s["lo"], s["hi"], n), rng, 6)
            pygame.draw.rect(surf, tone, c, border_radius=max(2, c.w // 3))
            pygame.draw.line(surf, mix(tone, s["cap"], 0.6), (c.x + 2, c.y + 1), (c.right - 3, c.y + 1))


def _cave(surf, s, r, n, rng, near):
    base = _base(s, n)
    if rng.random() < 0.07:                        # standing water in a hollow
        q = pygame.Rect(0, 0, rng.randint(r.w // 3, r.w * 2 // 3), rng.randint(r.h // 5, r.h // 3))
        q.center = (r.x + rng.randint(r.w // 3, r.w * 2 // 3), r.y + rng.randint(r.h // 3, r.h * 2 // 3))
        pygame.draw.ellipse(surf, s["puddle"], q)
    for _ in range(rng.randint(2, 7)):
        p = (r.x + rng.randint(2, r.w - 3), r.y + rng.randint(2, r.h - 3))
        pygame.draw.circle(surf, mix(base, s["speck"], rng.uniform(0.3, 0.8)), p, 1)
    if rng.random() < 0.06:
        p = (r.x + rng.randint(8, r.w - 8), r.y + rng.randint(8, r.h - 8))
        pygame.draw.circle(surf, s["speck"], p, 3)


_DETAIL = {"stone": _stone, "arena": _arena, "grass": _grass, "earth": _earth, "cobble": _cobble,
           "cave": _cave}


# ---------------------------------------------------------------------- #
# walls                                                                  #
# ---------------------------------------------------------------------- #
def _block(surf, s, r, cell, walls, rng):
    """A raised stone block, corners rounded only where a face is exposed, so clusters read
    as one mass."""
    wx, wy = cell
    open_n, open_s = (wx, wy - 1) not in walls, (wx, wy + 1) not in walls
    open_w, open_e = (wx - 1, wy) not in walls, (wx + 1, wy) not in walls
    rad = max(2, r.w // 8)
    kw = {"border_top_left_radius": rad if open_n and open_w else 0,
              "border_top_right_radius": rad if open_n and open_e else 0,
              "border_bottom_left_radius": rad if open_s and open_w else 0,
              "border_bottom_right_radius": rad if open_s and open_e else 0}
    r = r.inflate(-2, -2)
    pygame.draw.rect(surf, _shade(s["wall_fill"], rng, 4), r, **kw)
    lower = pygame.Rect(r.x, r.centery, r.w, r.h - r.h // 2)
    sh = pygame.Surface(lower.size, pygame.SRCALPHA)
    sh.fill((*s["wall_lo"], 55))
    surf.blit(sh, lower.topleft)
    pygame.draw.rect(surf, s["wall_lo"], r, 1, **kw)
    if open_n:
        pygame.draw.rect(surf, s["wall_hi"], pygame.Rect(r.x + 3, r.y + 3, r.w - 6, 4), border_radius=2)


def _rock(surf, s, r, cell, walls, rng):
    """A boulder: an irregular lump, lit on its top-left."""
    pts = []
    for i in range(9):
        a = i / 9 * 2 * math.pi
        k = rng.uniform(0.38, 0.5) * r.w
        pts.append((r.centerx + math.cos(a) * k, r.centery + math.sin(a) * k))
    pygame.draw.polygon(surf, _shade(s["wall_fill"], rng, 5), pts)
    pygame.draw.polygon(surf, s["wall_lo"], pts, 1)
    hi = pygame.Rect(0, 0, r.w // 3, r.h // 5)
    hi.center = (r.centerx - r.w // 8, r.centery - r.h // 5)
    pygame.draw.ellipse(surf, s["wall_hi"], hi)


def _tree(surf, s, r, cell, walls, rng):
    """A tree seen from above: the trunk's foot and a crown of leaves."""
    c, u = r.center, r.w / 48
    pygame.draw.circle(surf, s["trunk"], (c[0], round(c[1] + 6 * u)), round(6 * u))
    for i, (dx, dy, rad) in enumerate([(-6, -2, 15), (6, -4, 14), (0, -10, 15), (0, 2, 16)]):
        col = _shade(mix(s["leaf_lo"], s["leaf_hi"], i / 3), rng, 4)
        pygame.draw.circle(surf, col, (round(c[0] + dx * u), round(c[1] + (dy - 4) * u)), round(rad * u))
    for _ in range(6):
        p = (c[0] + round(rng.randint(-12, 12) * u), c[1] + round(rng.randint(-18, 4) * u))
        pygame.draw.circle(surf, s["leaf_speck"], p, max(1, round(2 * u)))


_WALL = {"block": _block, "rock": _rock, "tree": _tree}


def _shadows(cols, rows, tile, walls, round_cast):
    """The soft shadow every wall casts down and to the right."""
    sh = pygame.Surface((cols * tile, rows * tile), pygame.SRCALPHA)
    for x, y in walls:
        r = pygame.Rect(x * tile + tile // 6, y * tile + tile // 5, tile, tile)
        if round_cast:
            pygame.draw.ellipse(sh, WALL_SHADOW, r.inflate(tile // 8, -tile // 8))
        else:
            pygame.draw.rect(sh, WALL_SHADOW, r, border_radius=tile // 8)
    small = pygame.transform.smoothscale(sh, (max(1, cols * tile // 8), max(1, rows * tile // 8)))
    return pygame.transform.smoothscale(small, (cols * tile, rows * tile))


# ---------------------------------------------------------------------- #
def _cell_rng(floor, x, y):
    """A cell's own dice: opening a wall mid-fight repaints that cell, not the whole floor."""
    return random.Random(f"{floor}:{x},{y}")


def _paint(floor, cols, rows, walls, tile, with_walls):
    s = style(floor)
    noise = _noise(cols, rows, random.Random(f"{floor}:{cols}x{rows}"))
    surf = _ground_layer(s, cols, rows, tile, noise)
    near = {(x + dx, y + dy) for x, y in walls for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - walls
    detail = _DETAIL.get(floor, _stone)
    for x in range(cols):
        for y in range(rows):
            if (x, y) not in walls:
                detail(surf, s, pygame.Rect(x * tile, y * tile, tile, tile), noise[(x, y)], _cell_rng(floor, x, y),
                       (x, y) in near)
    if not with_walls:
        return surf
    grid = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    for x in range(cols + 1):
        pygame.draw.line(grid, FLOOR_GRID, (x * tile, 0), (x * tile, rows * tile))
    for y in range(rows + 1):
        pygame.draw.line(grid, FLOOR_GRID, (0, y * tile), (cols * tile, y * tile))
    surf.blit(grid, (0, 0))
    kind = wall_kind(floor)
    if walls:
        surf.blit(_shadows(cols, rows, tile, walls, kind != "block"), (0, 0))
    draw_wall = _WALL[kind]
    for x, y in sorted(walls, key=lambda c: (c[1], c[0])):
        draw_wall(surf, s, pygame.Rect(x * tile, y * tile, tile, tile), (x, y), walls, _cell_rng(floor, x, y))
    return surf


def _cached(key, make):
    surf = _textures.get(key)
    if surf is None:
        surf = make()
        _textures[key] = surf
        while len(_textures) > _CACHE_SIZE:
            _textures.popitem(last=False)
    else:
        _textures.move_to_end(key)
    return surf


def texture(floor, cols, rows, walls):
    walls = frozenset(walls)
    return _cached((floor, cols, rows, walls, TEX),
                   lambda: _paint(floor, cols, rows, walls, TEX, with_walls=True))


def ground(floor, cols, rows, tile):
    return _cached(("ground", floor, cols, rows, tile),
                   lambda: _paint(floor, cols, rows, frozenset(), tile, with_walls=False))


def blit_board(surf, view, floor, cols, rows, walls):
    """Draw the cells `view` shows of the board's texture, scaled to the view's tile."""
    walls = frozenset(walls)
    tex = texture(floor, cols, rows, walls)
    vr, tile = view.rect, view.tile
    x0 = max(0, math.floor(view.cam[0]))
    y0 = max(0, math.floor(view.cam[1]))
    x1 = min(cols, math.ceil(view.cam[0] + vr.w / tile))
    y1 = min(rows, math.ceil(view.cam[1] + vr.h / tile))
    if x1 <= x0 or y1 <= y0:
        return
    key = (floor, cols, rows, walls, tile, x0, y0, x1, y1)
    if _last_crop[0] != key:
        crop = tex.subsurface(pygame.Rect(x0 * TEX, y0 * TEX, (x1 - x0) * TEX, (y1 - y0) * TEX))
        size = ((x1 - x0) * tile, (y1 - y0) * tile)
        _last_crop[:] = [key, crop.copy() if size == crop.get_size() else pygame.transform.smoothscale(crop, size)]
    surf.blit(_last_crop[1], view.cell_rect(x0, y0).topleft)

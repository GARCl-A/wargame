"""The BOARD zone: terrain, props, unit tokens and the tactical overlay.

Everything draws through a `BoardView` (`board_style`) -- the view owns the
cell <-> pixel mapping, so these functions never know the camera or window.
Data in, nothing out: the board has no click targets of its own (the screen
hit-tests cells through `view.cell_at`).

Data shapes::

    terrain = {"cols": int, "rows": int, "walls": set[(x, y)],
               "elevation": {(x, y): z}, "water": set, "ropes": set,
               "fire": set,                       # optional: burning cells
               "floor": str}                      # optional: a `floors.FLOORS` id

    prop = {"kind": "torch" | "chest" | "relic" | "trap" | "disk" | "corpse" | "item",
            "pos": (x, y), "trap_type": str, "elevation": int,
            "size": int}                          # corpse: the body's footprint in cells

    token = {"team": "player" | "enemy", "active": bool,
             "race": str, "portrait_id": str | None, "token": str,
             "hp_frac": float, "hp_steps": int | None,   # steps: a foe's bar, in that many segments
             "torch": bool, "defending": bool,
             "ferocity": bool, "demoralized": bool,
             "flag": "player" | "enemy" | None,   # whose flag it carries
             "focus": None | "inspect" | "armed",
             "downed": bool, "dying": str | None,  # "2/3" death clock
             "broken": bool,
             "flash": float}                      # optional: 0..1, a hit just taken
"""

import pygame

from editor import artwork
from editor.ui import banner, floors
from editor.ui.primitives import TOKEN_INK, box, text
from editor.ui.tokens import T

from editor.ui.board_style import (
    ALLY_C,
    BADGE_INK,
    CHEST_TRIM,
    CHEST_WOOD,
    CORPSE_FILL,
    CORPSE_INK,
    CORPSE_RIM,
    CORPSE_SHADOW,
    CREATURE_INK,
    DANGER,
    DEMO_HL,
    DISK_CORE,
    DISK_HALO,
    DISK_RIM,
    ENEMY_C,
    FIRE_C,
    FIRE_CORE,
    HP_TRACK,
    INK_FAINT,
    LIGHT_C,
    MOVE_HL,
    NEUTRAL_C,
    OBJ_C,
    OK,
    PATH_DONE,
    PATH_PREV,
    PLAYER_C,
    PROP_EDGE,
    RELIC_C,
    RELIC_RIM,
    ROPE_C,
    THIRD_C,
    TORCH_BASE,
    TORCH_C,
    TRAP_BELL,
    TRAP_BELL_D,
    TRAP_C,
    TRAP_CLAPPER,
    TRAP_IRON,
    TRAP_PEG,
    TRAP_PLATE,
    TRAP_PLATE_D,
    TRAP_STEEL,
    TRAP_TEETH,
    TRAP_WIRE,
    WALL_LO,
    WARN,
    WATER_C,
    WEB_C,
)

_SIDE_C = {"player": PLAYER_C, "enemy": ENEMY_C, "ally": ALLY_C}


def team_color(team):
    """A side's colour as the seat sees it; every side past the first three is a third one."""
    return _SIDE_C.get(team, THIRD_C)


def hp_color(frac):
    return OK if frac > 0.4 else WARN if frac > 0.15 else DANGER


def hp_bar(surf, rect, frac, steps=None):
    """A health bar: continuous, or in `steps` equal segments (a foe's health is only known to the step)."""
    pygame.draw.rect(surf, HP_TRACK, rect)
    if not steps:
        pygame.draw.rect(surf, hp_color(frac), pygame.Rect(rect.x, rect.y, int(rect.w * frac), rect.h))
        return
    w = rect.w / steps
    for i in range(round(frac * steps)):
        left, right = round(rect.x + i * w), round(rect.x + (i + 1) * w)
        pygame.draw.rect(surf, hp_color(frac), pygame.Rect(left, rect.y, max(1, right - left - 1), rect.h))


def _badge(surf, F, center, w, label, fill):
    r = pygame.Rect(0, 0, w, 15)
    r.center = center
    box(surf, r, fill=fill, border=None)
    text(surf, F["micro"], label, r.center, BADGE_INK, center=True)


# ---------------------------------------------------------------------- #
# terrain                                                                #
# ---------------------------------------------------------------------- #
def draw_terrain(surf, F, view, terrain):
    """The place's floor with its walls (`floors.py`), then sunken pits, water, fire and
    ropes over it."""
    vr, tile = view.rect, view.tile
    elevation = terrain["elevation"]

    def vis(cx, cy):
        return view.cell_rect(cx, cy).colliderect(vr)

    floors.blit_board(surf, view, terrain.get("floor", floors.DEFAULT), terrain["cols"], terrain["rows"],
                      terrain["walls"])

    for (cx, cy), z in elevation.items():
        if not vis(cx, cy):
            continue
        r = view.cell_rect(cx, cy)
        k = min(1.0, -z / 6)
        surf.fill(WALL_LO, r)
        surf.fill(tuple(int(v * (1 - 0.5 * k)) for v in WALL_LO), r.inflate(-tile // 4, -tile // 4))
        text(surf, F["micro"], str(-z), r.center, INK_FAINT, center=True)

    for cx, cy in terrain["water"]:
        if not vis(cx, cy):
            continue
        deep = elevation.get((cx, cy), 0) < 0
        wl = pygame.Surface((tile, tile), pygame.SRCALPHA)
        wl.fill((*WATER_C, 150 if deep else 92))
        surf.blit(wl, view.cell_rect(cx, cy))

    for cx, cy in terrain.get("fire", ()):
        if vis(cx, cy):
            _flame(surf, view.cell_rect(cx, cy), tile)

    for cx, cy in terrain["ropes"]:
        if not vis(cx, cy):
            continue
        r = view.cell_rect(cx, cy)
        pygame.draw.line(surf, ROPE_C, (r.centerx, r.top + 3), (r.centerx, r.bottom - 3),
                         max(2, tile // 12))


def _flame(surf, r, tile):
    """A burning cell: an ember wash and a tongue of flame."""
    glow = pygame.Surface((tile, tile), pygame.SRCALPHA)
    glow.fill((*FIRE_C, 120))
    surf.blit(glow, r)
    cx, base, h, w = r.centerx, r.bottom - tile // 6, tile * 2 // 3, tile // 3
    pygame.draw.polygon(surf, FIRE_C, [(cx - w, base), (cx, base - h), (cx + w, base)])
    pygame.draw.polygon(surf, FIRE_CORE, [(cx - w // 2, base), (cx, base - h // 2), (cx + w // 2, base)])


# ---------------------------------------------------------------------- #
# props                                                                  #
# ---------------------------------------------------------------------- #
def draw_props(surf, F, view, props):
    for p in props:
        r = view.cell_rect(*p["pos"])
        kind = p["kind"]
        if kind == "torch":
            _torch(surf, view.tile, r.center)
        elif kind == "chest":
            d = view.tile // 3
            rect = pygame.Rect(r.centerx - d, r.centery - d // 2, d * 2, d)
            pygame.draw.rect(surf, CHEST_WOOD, rect)
            pygame.draw.rect(surf, CHEST_TRIM, rect, 2)
        elif kind == "relic":
            _diamond(surf, r.center, view.tile // 3, RELIC_C, RELIC_RIM)
        elif kind == "trap":
            _trap(surf, r.center, max(6, view.tile // 3), (p.get("trap_type") or "").lower())
        elif kind == "disk":
            _disk(surf, F, r, p.get("elevation", 0))
        elif kind == "corpse":
            size = p.get("size", 1)
            _corpse(surf, pygame.Rect(r.x, r.y, r.w * size, r.h * size))
        else:
            _diamond(surf, r.center, view.tile // 4, OBJ_C, PROP_EDGE)


def _corpse(surf, r):
    """The dead: a grey disc the size of a downed body, with a cross."""
    c, rad = r.center, r.w // 2 - 6
    pygame.draw.circle(surf, CORPSE_FILL, c, rad)
    pygame.draw.circle(surf, CORPSE_RIM, c, rad, 2)
    h, w, t = int(rad * 1.2), int(rad * 0.8), max(3, rad // 6)
    top = c[1] - h // 2 - rad // 10
    for (dx, dy), col in (((2, 2), CORPSE_SHADOW), ((0, 0), CORPSE_INK)):
        pygame.draw.rect(surf, col, pygame.Rect(c[0] - t // 2 + dx, top + dy, t, h))
        pygame.draw.rect(surf, col, pygame.Rect(c[0] - w // 2 + dx, top + h // 4 + dy, w, t))


def _diamond(surf, center, d, fill, edge):
    cx, cy = center
    pts = [(cx, cy - d), (cx + d, cy), (cx, cy + d), (cx - d, cy)]
    pygame.draw.polygon(surf, fill, pts)
    pygame.draw.polygon(surf, edge, pts, 2)


def _torch(surf, t, center):
    cx, cy = center
    glow = pygame.Surface((t * 2, t * 2), pygame.SRCALPHA)
    for rad, a in ((t * 3 // 4, 22), (t // 2, 34), (t // 4, 60)):
        pygame.draw.circle(glow, (*TORCH_C, a), (t, t), rad)
    surf.blit(glow, (cx - t, cy - t))
    pygame.draw.circle(surf, TORCH_BASE, (cx, cy + 4), 5)
    pygame.draw.circle(surf, TORCH_C, (cx, cy - 2), 6)
    pygame.draw.circle(surf, LIGHT_C, (cx, cy - 4), 3)


def _web(surf, center, d):
    cx, cy = center
    r = d * 3 // 2
    spokes = [(cx + dx * r // 2, cy + dy * r // 2)
              for dx, dy in ((2, 0), (1, 1), (0, 2), (-1, 1), (-2, 0), (-1, -1), (0, -2), (1, -1))]
    for p in spokes:
        pygame.draw.line(surf, WEB_C, center, p, 1)
    for k in (2, 3):
        ring = [(cx + (p[0] - cx) * k // 4, cy + (p[1] - cy) * k // 4) for p in spokes]
        pygame.draw.polygon(surf, WEB_C, ring, 1)


def _trap(surf, center, d, ttype):
    cx, cy = center
    if "web" in ttype:
        _web(surf, center, d)
    elif "bear" in ttype:
        pygame.draw.circle(surf, TRAP_STEEL, (cx, cy), d)
        pygame.draw.circle(surf, TRAP_IRON, (cx, cy), d, 2)
        pygame.draw.circle(surf, TRAP_PLATE, (cx, cy), max(2, d // 3))
        pygame.draw.circle(surf, TRAP_PLATE_D, (cx, cy), max(2, d // 3), 1)
        teeth_w = max(3, d // 2)
        for dx in (-d * 2 // 3, 0, d * 2 // 3 - teeth_w):
            for sign in (-1, 1):
                spike = [(cx + dx, cy + sign * (d // 2)), (cx + dx + teeth_w // 2, cy + sign),
                         (cx + dx + teeth_w, cy + sign * (d // 2))]
                pygame.draw.polygon(surf, TRAP_TEETH, spike)
                pygame.draw.polygon(surf, TRAP_IRON, spike, 1)
    elif "alarm" in ttype:
        w = d + 2
        pygame.draw.line(surf, TRAP_PEG, (cx - w, cy - d // 2), (cx - w, cy + d // 2), 3)
        pygame.draw.line(surf, TRAP_PEG, (cx + w, cy - d // 2), (cx + w, cy + d // 2), 3)
        pygame.draw.line(surf, TRAP_WIRE, (cx - w, cy - 2), (cx + w, cy - 2), 1)
        bell = [(cx - d // 2, cy + d // 2), (cx + d // 2, cy + d // 2),
                (cx + d // 4, cy - 2), (cx - d // 4, cy - 2)]
        pygame.draw.polygon(surf, TRAP_BELL, bell)
        pygame.draw.polygon(surf, TRAP_BELL_D, bell, 1)
        pygame.draw.circle(surf, TRAP_CLAPPER, (cx, cy + d // 2 + 1), max(2, d // 5))
    else:
        _diamond(surf, center, d, TRAP_C, PROP_EDGE)


def _disk(surf, F, r, elevation):
    cx, cy = r.center
    w = max(16, int(r.w * 0.75))
    h = max(10, int(r.h * 0.45))
    glow = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, DISK_HALO, (0, 0, w + 8, h + 8))
    pygame.draw.ellipse(glow, DISK_CORE, (4, 4, w, h))
    pygame.draw.ellipse(glow, (*DISK_RIM, 220), (4, 4, w, h), 2)
    surf.blit(glow, (cx - (w + 8) // 2, cy - (h + 8) // 2))
    text(surf, F["micro"], f"z={elevation}", (cx, cy - 2), DISK_RIM, center=True)


def draw_pennant(surf, r, color):
    pole = (r.x + r.w // 3, r.bottom - 5)
    pygame.draw.line(surf, T.TX, (pole[0], r.y + 5), pole, 3)
    flag = [(pole[0], r.y + 5), (pole[0] + r.w // 2, r.y + 12), (pole[0], r.y + 19)]
    pygame.draw.polygon(surf, color, flag)
    pygame.draw.polygon(surf, T.TX, flag, 1)


# ---------------------------------------------------------------------- #
# units                                                                  #
# ---------------------------------------------------------------------- #
def draw_creature(surf, F, r, token):
    pygame.draw.circle(surf, NEUTRAL_C, r.center, r.w // 2 - 6)
    text(surf, F["bodyb"], token, r.center, CREATURE_INK, center=True)


def draw_unit(surf, F, r, tok):
    """One unit on its footprint rect `r` -- standing token or downed body."""
    if tok["downed"]:
        _body(surf, F, r, tok)
    else:
        _standing(surf, F, r, tok)
    if tok.get("flash"):
        _flash(surf, r, tok["flash"])
    if tok.get("focus"):
        armed = tok["focus"] == "armed"
        pygame.draw.rect(surf, DANGER if armed else T.TX, r, 2 if armed else 1, border_radius=4)


def _flash(surf, r, amount):
    """A red burst over the token the instant it is struck, fading as `amount` drops."""
    veil = pygame.Surface(r.size, pygame.SRCALPHA)
    pygame.draw.circle(veil, (*DANGER, round(190 * amount)), (r.w // 2, r.h // 2), r.w // 2 - 4)
    surf.blit(veil, r.topleft)


def _body(surf, F, r, tok):
    center = r.center
    rad = r.w // 2 - 6
    base = team_color(tok["team"])
    pygame.draw.circle(surf, tuple(c // 3 + 12 for c in base), center, rad)
    ring = DANGER if tok["dying"] else T.TX_MUTED
    pygame.draw.circle(surf, ring, center, rad, 2)
    d = rad // 2
    pygame.draw.line(surf, ring, (center[0] - d, center[1] - d), (center[0] + d, center[1] + d), 2)
    pygame.draw.line(surf, ring, (center[0] - d, center[1] + d), (center[0] + d, center[1] - d), 2)
    if tok.get("obscured"):
        pygame.draw.circle(surf, INK_FAINT, center, rad, 1)
    if tok["dying"]:
        _badge(surf, F, (r.centerx, r.y + 8), 20, tok["dying"], DANGER)
    elif tok.get("broken"):
        _badge(surf, F, (r.centerx, r.y + 8), 34, "BRKN", WARN)


def _hostile(team):
    return team not in ("player", "ally")


def _plate(surf, r, team, active):
    """The base a token stands on: a disc for the squad and its allies, a diamond for a foe,
    in the side's colour -- the banner colour never decides which side a token is on."""
    c, h = r.center, r.w // 2 - 1
    side = team_color(team)
    fill = tuple(v // 2 for v in side)
    edge = T.BRASS if active else side
    if _hostile(team):
        pts = [(c[0], c[1] - h), (c[0] + h, c[1]), (c[0], c[1] + h), (c[0] - h, c[1])]
        pygame.draw.polygon(surf, fill, pts)
        pygame.draw.polygon(surf, edge, pts, 3)
    else:
        pygame.draw.circle(surf, fill, c, h - 1)
        pygame.draw.circle(surf, edge, c, h - 1, 3)


def _pennant(surf, r):
    x, y = r.x + 6, r.y + 4
    pygame.draw.line(surf, T.TX_MUTED, (x, y), (x, y + 16), 2)
    pygame.draw.polygon(surf, banner.player_color(), [(x + 1, y), (x + 13, y + 4), (x + 1, y + 8)])


def _standing(surf, F, r, tok):
    _plate(surf, r, tok["team"], tok["active"])
    inner = r.inflate(-10, -10)
    center = inner.center
    rad = inner.w // 2
    base = team_color(tok["team"])
    pygame.draw.circle(surf, base, center, rad - 1)
    if tok.get("torch"):
        pygame.draw.circle(surf, TORCH_C, center, rad, 2)
        pygame.draw.circle(surf, LIGHT_C, (r.right - 8, r.y + 8), 4)
    if tok.get("defending"):
        pygame.draw.circle(surf, T.TX, center, rad - 1, 2)
    if tok.get("ferocity"):
        pygame.draw.circle(surf, DANGER, center, rad, 2)
    if tok.get("obscured"):
        pygame.draw.circle(surf, INK_FAINT, center, rad, 2)
    _face(surf, F, center, rad - 1, round(rad * 1.5), tok)
    if tok["team"] == "player":
        _pennant(surf, r)
    if tok.get("demoralized"):
        pygame.draw.circle(surf, DEMO_HL, (r.x + 8, r.bottom - 14), 4)
    hp_bar(surf, pygame.Rect(r.x + 5, r.bottom - 8, r.w - 10, 4), tok["hp_frac"], tok.get("hp_steps"))
    if tok.get("flag"):
        _badge(surf, F, (r.centerx, r.y + 8), 34, "FLAG", team_color(tok["flag"]))


def _face(surf, F, center, port_r, sil_px, tok, font="bodyb"):
    """Portrait medallion, else the race silhouette, else the board letter."""
    port = artwork.portrait(tok["race"], tok.get("portrait_id"), port_r * 2)
    if port is not None:
        surf.blit(port, port.get_rect(center=center))
        return
    sil = artwork.race_icon(tok["race"], sil_px, TOKEN_INK)
    if sil is not None:
        surf.blit(sil, sil.get_rect(center=center))
    else:
        text(surf, F[font], tok["token"], center, TOKEN_INK, center=True)


def draw_face(surf, F, center, r, tok, *, fallback_color, known=True):
    """A small unit face for strips and cards: portrait, else a team disc with
    the race glyph; an unknown unit is a blank disc with '?'."""
    port = artwork.portrait(tok["race"], tok.get("portrait_id"), r * 2) if known else None
    if port is not None:
        surf.blit(port, port.get_rect(center=center))
        return
    pygame.draw.circle(surf, fallback_color if known else T.STEEL_HI, center, r)
    sil = artwork.race_icon(tok["race"], round(r * 1.6), TOKEN_INK) if known else None
    if sil is not None:
        surf.blit(sil, sil.get_rect(center=center))
    else:
        text(surf, F["micro"], tok["token"] if known else "?", center, TOKEN_INK, center=True)


# ---------------------------------------------------------------------- #
# tactical overlay                                                       #
# ---------------------------------------------------------------------- #
def tint_cells(surf, view, cells, color, alpha):
    cell = pygame.Surface((view.tile, view.tile), pygame.SRCALPHA)
    cell.fill((*color, alpha))
    for pos in cells:
        surf.blit(cell, view.cell_rect(*pos))


def draw_reach(surf, view, cells, color=MOVE_HL, alpha=40):
    """The cells the active unit can walk to: a tint plus an outline only on
    the region's outer edge."""
    tint_cells(surf, view, cells, color, alpha)
    for pos in cells:
        r = view.cell_rect(*pos)
        for (dx, dy), seg in (((1, 0), (r.right, r.top, r.right, r.bottom)),
                              ((-1, 0), (r.left, r.top, r.left, r.bottom)),
                              ((0, 1), (r.left, r.bottom, r.right, r.bottom)),
                              ((0, -1), (r.left, r.top, r.right, r.top))):
            if (pos[0] + dx, pos[1] + dy) not in cells:
                pygame.draw.line(surf, color, seg[:2], seg[2:], 2)


def draw_rings(surf, rects, color):
    for r in rects:
        pygame.draw.rect(surf, color, r, 3, border_radius=4)


def path_points(view, cells, footprint):
    off = view.tile * footprint // 2
    return [(view.cell_rect(cx, cy).x + off, view.cell_rect(cx, cy).y + off) for cx, cy in cells]


def draw_trail(surf, pts):
    """Where the active unit already walked this turn."""
    pygame.draw.lines(surf, PATH_DONE, False, pts, 2)
    for p in pts[1:]:
        pygame.draw.circle(surf, PATH_DONE, p, 2)


def draw_route(surf, F, pts, cost):
    """The planned route under the cursor, with its movement cost badge."""
    pygame.draw.lines(surf, PATH_PREV, False, pts, 3)
    for p in pts[1:-1]:
        pygame.draw.circle(surf, PATH_PREV, p, 3)
    end = pts[-1]
    pygame.draw.circle(surf, PATH_PREV, end, 8, 2)
    if cost is not None:
        badge = pygame.Rect(0, 0, 18, 15)
        badge.center = (end[0], end[1] - 15)
        box(surf, badge, fill=PATH_PREV, border=None)
        text(surf, F["micro"], str(cost), badge.center, BADGE_INK, center=True)


def draw_placement(surf, F, view, cells, hover, banner):
    """A pre-battle placement step (flag, traps): tint the legal cells,
    outline the hovered one if legal, and a banner across the board top."""
    tint_cells(surf, view, cells, PLAYER_C, 32)
    if hover is not None:
        pygame.draw.rect(surf, PLAYER_C, view.cell_rect(*hover), 2, border_radius=4)
    bar = pygame.Rect(view.rect.x, view.rect.y, view.rect.w, 30)
    box(surf, bar, fill=T.TABLE, border=PLAYER_C, width=1)
    text(surf, F["bodyb"], banner, bar.center, T.TX, center=True)

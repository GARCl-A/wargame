"""Design system: layout scale, palette, fonts, and drawing helpers.

One source of truth for how GARTOK Tactical looks. The screens (`draft_screen`,
`battle_screen`) and the light renderer draw only from here.

- `SP` is the spacing scale (4 / 8 / 12 / 16 / 24 / 32). Never hard-code a gap.
- Colours have *roles* (`INK`, `ACCENT`, `DANGER`, ...) plus a surface ramp
  (`SURFACE_0..3`). Old names (`TEXT`, `DIM`, `CARD_BG`, ...) are kept as aliases
  so nothing breaks.
- `Fonts` exposes two families: a weighted sans for labels/headings and a
  monospace for numbers, dice and the log.
- `Panel`, `chip`, `pips`, `text`, `Stack` keep the screens declarative.
"""

import math

import pygame

from . import artwork
from .battle import COLS, ROWS

# --- spacing scale ----------------------------------------------------------- #
SP = (4, 8, 12, 16, 24, 32)
SP1, SP2, SP3, SP4, SP5, SP6 = SP

RADIUS = 6

# --- layout ---------------------------------------------------------------- #
TILE = 48                             # default board zoom; the battle view now
                                     # picks its own tile size to fit the window
MIN_TILE, MAX_TILE = 18, 56           # zoom range of the battle board camera
MARGIN = SP4
INIT_H = 46                           # initiative strip above the grid

GRID_W, GRID_H = COLS * TILE, ROWS * TILE
GRID_X = MARGIN
GRID_Y = MARGIN + INIT_H + SP3

PANEL_W = 396
PANEL_X = GRID_X + GRID_W + MARGIN
PANEL_Y = MARGIN

LOG_Y = GRID_Y + GRID_H + MARGIN
LOG_H = 150

WIN_W = PANEL_X + PANEL_W + MARGIN
WIN_H = LOG_Y + LOG_H + MARGIN


def battle_layout(size):
    """Dock the action panel to the window's right edge and the log along the
    bottom; the board viewport fills everything left over. Recomputed each frame
    from the real window size, so the battle screen uses the whole window."""
    W, H = size
    pw = int(min(PANEL_W, max(260, W * 0.30)))
    panel_r = pygame.Rect(W - MARGIN - pw, MARGIN, pw, max(1, H - 2 * MARGIN))
    log_h = LOG_H if H > 620 else max(84, H // 4)
    left_w = max(1, panel_r.x - 2 * MARGIN)
    init = pygame.Rect(MARGIN, MARGIN, left_w, INIT_H)
    log = pygame.Rect(MARGIN, H - MARGIN - log_h, left_w, log_h)
    board_top = init.bottom + SP3
    board = pygame.Rect(MARGIN, board_top, left_w,
                        max(1, log.y - SP3 - board_top))
    return {"panel": panel_r, "log": log, "init": init, "board": board}


class BoardView:
    """Maps the board grid onto a pan/zoom pixel viewport. `fit` lays the whole
    board into a rect at a tile size that fills it (clamped to the zoom range);
    the wheel zooms around the cursor and a drag pans a board bigger than the
    view. All board<->screen conversion goes through `cell_rect` / `cell_at`."""

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.rect = pygame.Rect(0, 0, 1, 1)
        self.tile = TILE
        self.cam = [0.0, 0.0]              # board-cell offset of the viewport's top-left
        self._user_zoom = False           # once the player zooms, stop auto-fitting

    def fit(self, rect):
        self.rect = rect
        if not self._user_zoom:
            fit_tile = max(1, int(min(rect.w / self.cols, rect.h / self.rows)))
            self.tile = max(MIN_TILE, min(MAX_TILE, fit_tile))
        self._clamp()

    def _clamp(self):
        for i, view in enumerate((self.rect.w, self.rect.h)):
            span = (self.cols, self.rows)[i] * self.tile
            if span <= view:
                self.cam[i] = -(view - span) / 2 / self.tile     # centre a small board
            else:
                self.cam[i] = max(0.0, min(self.cam[i], (span - view) / self.tile))

    def cell_rect(self, cx, cy):
        x = self.rect.x + (cx - self.cam[0]) * self.tile
        y = self.rect.y + (cy - self.cam[1]) * self.tile
        return pygame.Rect(round(x), round(y), self.tile, self.tile)

    def cell_at(self, px, clamp=False):
        if not clamp and not self.rect.collidepoint(px):
            return None
        cx = math.floor((px[0] - self.rect.x) / self.tile + self.cam[0])
        cy = math.floor((px[1] - self.rect.y) / self.tile + self.cam[1])
        if clamp:
            return (max(0, min(self.cols - 1, cx)), max(0, min(self.rows - 1, cy)))
        if 0 <= cx < self.cols and 0 <= cy < self.rows:
            return (cx, cy)
        return None

    def center_on(self, cell):
        self.cam[0] = cell[0] + 0.5 - self.rect.w / 2 / self.tile
        self.cam[1] = cell[1] + 0.5 - self.rect.h / 2 / self.tile
        self._clamp()

    def zoom(self, px, steps):
        anchor = self.cell_at(px, clamp=True)
        new = max(MIN_TILE, min(MAX_TILE, self.tile + steps * 4))
        if new == self.tile:
            return
        self._user_zoom = True
        self.tile = new
        if anchor is not None and self.rect.collidepoint(px):
            self.cam[0] = anchor[0] + 0.5 - (px[0] - self.rect.x) / self.tile
            self.cam[1] = anchor[1] + 0.5 - (px[1] - self.rect.y) / self.tile
        self._clamp()

    def pan_px(self, dx, dy):
        self.cam[0] -= dx / self.tile
        self.cam[1] -= dy / self.tile
        self._clamp()


# --- palette --------------------------------------------------------------- #
# surface ramp: app -> well -> panel -> raised -> hover
SURFACE_0 = (18, 19, 24)
SURFACE_1 = (26, 28, 35)
SURFACE_2 = (33, 36, 45)
SURFACE_3 = (44, 48, 59)
SURFACE_4 = (56, 61, 74)

LINE      = (58, 63, 76)
LINE_SOFT = (40, 44, 54)

INK       = (230, 232, 237)
INK_DIM   = (154, 160, 172)
INK_FAINT = (104, 110, 122)

ACCENT    = (232, 194, 75)             # selection / active / focus (warm gold)
ACCENT_INK = (24, 20, 8)              # text on an accent fill

PLAYER_C  = (94, 156, 214)             # the default -- overwritten per-run by set_player_color
ENEMY_C   = (214, 103, 92)
NEUTRAL_C = (176, 170, 154)

OK        = (111, 191, 115)
WARN      = (224, 149, 75)
DANGER    = (214, 103, 92)
INFO      = (127, 168, 208)

# environment
BG        = SURFACE_0
NIGHT     = (4, 5, 12)
TORCH_C   = (240, 150, 55)
LIGHT_C   = (250, 225, 150)
OBJ_C     = (205, 180, 95)
WALL_FILL = (74, 78, 92)
WALL_HI   = (110, 116, 132)
WALL_LO   = (18, 19, 26)
FLOOR_A   = (44, 48, 56)               # battle board: the two checker tones
FLOOR_B   = (39, 43, 51)

# tactical overlay
MOVE_HL   = (78, 150, 96)
ATK_HL    = ENEMY_C
THROW_HL  = WARN
DEMO_HL   = (176, 116, 208)
PATH_PREV = (245, 232, 150)
PATH_DONE = (108, 138, 112)

# --- aliases (old names) -------------------------------------------------- #
GRID_LINE = LINE_SOFT
TEXT      = INK
DIM       = INK_DIM
KEY_C     = INFO
ACTIVE_C  = ACCENT
POS_C     = OK
NEG_C     = DANGER
CARD_BG   = SURFACE_2
CARD_HOV  = SURFACE_3
CARD_HEAD = SURFACE_3
CHIP_BG   = SURFACE_1


# --------------------------------------------------------------------------- #
# Fonts                                                                        #
# --------------------------------------------------------------------------- #

_SANS = "segoeui,calibri,arial"
_MONO = "consolas,dejavusansmono,couriernew"


class Fonts:
    """Built once after `pygame.init()`; handed to every screen."""

    def __init__(self):
        S = lambda name, size, bold=False: pygame.font.SysFont(name, size, bold=bold)

        # weighted sans: identity, headings, labels, running text
        self.title    = S(_SANS, 26, bold=True)
        self.heading  = S(_SANS, 15, bold=True)
        self.label    = S(_SANS, 11, bold=True)
        self.body     = S(_SANS, 14)
        self.body_sm  = S(_SANS, 12)
        self.body_bd  = S(_SANS, 14, bold=True)

        # monospace: numbers, dice math, the log
        self.num_lg   = S(_MONO, 26, bold=True)
        self.num      = S(_MONO, 19, bold=True)
        self.mono     = S(_MONO, 12)
        self.mono_sm  = S(_MONO, 11)

        # --- back-compat aliases used by sheet.py and older call sites --- #
        self.font      = self.body
        self.big       = self.title
        self.small     = self.body_sm
        self.tiny      = S(_SANS, 11)
        self.kw        = self.label
        self.card_name = S(_SANS, 17, bold=True)
        self.card_val  = self.num


# --------------------------------------------------------------------------- #
# text helpers                                                                 #
# --------------------------------------------------------------------------- #

def text(surf, s, font, color, pos, *, right=False, center=False, bottom=False):
    img = font.render(s, True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    elif right and bottom:
        rect.bottomright = pos
    elif right:
        rect.topright = pos
    elif bottom:
        rect.bottomleft = pos
    else:
        rect.topleft = pos
    surf.blit(img, rect)
    return rect


def tracked(surf, s, font, color, pos, spacing=1):
    """Render `s` with extra letter-spacing (for small uppercase labels)."""
    x, y = pos
    for ch in s:
        img = font.render(ch, True, color)
        surf.blit(img, (x, y))
        x += img.get_width() + spacing
    return x


def ellipsize(s, font, max_px):
    """`s` clipped with a trailing ellipsis so it renders within `max_px`."""
    if max_px <= 0 or font.size(s)[0] <= max_px:
        return s
    while s and font.size(s + "…")[0] > max_px:
        s = s[:-1]
    return s + "…"


def kg(w):
    """A weight in kilograms, trimmed (`2 kg`, not `2.0 kg`)."""
    return f"{w:g} kg"


def wrap_lines(lines, font, max_px):
    out = []
    for ln in lines:
        words = ln.split(" ")
        cur = ""
        for w in words:
            trial = w if not cur else cur + " " + w
            if font.size(trial)[0] <= max_px:
                cur = trial
            else:
                if cur:
                    out.append(cur)
                cur = w
        out.append(cur)
    return out


def blit_block(surf, lines, x, y, font, color=INK, lh=18):
    for i, ln in enumerate(lines):
        surf.blit(font.render(ln, True, color), (x, y + i * lh))
    return y + len(lines) * lh


# --------------------------------------------------------------------------- #
# widgets                                                                      #
# --------------------------------------------------------------------------- #

class Stack:
    """A vertical cursor: `s.gap(n)` then `s.row(h)` walks a column downward."""

    def __init__(self, x, y, w):
        self.x, self.y, self.w = x, y, w

    def gap(self, dy):
        self.y += dy
        return self

    def row(self, h):
        r = pygame.Rect(self.x, self.y, self.w, h)
        self.y += h
        return r


def panel(surf, rect, *, fill=SURFACE_1, border=LINE_SOFT, radius=RADIUS, width=1):
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    if border and width:
        pygame.draw.rect(surf, border, rect, width, border_radius=radius)
    return rect


TOKEN_INK = (15, 15, 20)                # ink for the race glyph / letter on a unit token

# The guild's banner colour, picked at the draft (see draft_screen.py's
# "identity" phase). A curated palette, not a free picker -- named like a
# heraldry tincture list, distinct enough from ENEMY_C to stay readable.
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


def set_player_color(color):
    """Recolour every unit token's disc (`token_badge`'s default fill) to the
    guild's chosen banner colour. Called once when a guild is created or
    loaded (`app.py`), not per frame. Deliberately does not touch
    `battle_screen`'s player/enemy colour-coding -- that one is a readability
    cue (tell your side from the enemy's), not an identity, and stays fixed."""
    global PLAYER_C
    PLAYER_C = tuple(color)


def token_badge(surf, center, unit, fonts, *, color=None, r=14):
    """The round unit token: a coloured disc carrying the unit's race silhouette
    (`artwork.race_icon`), falling back to its board letter when the race has no
    glyph. Used on every roster card (draft / guild / squad / loot / market /
    reward / sheet). `unit` may also be a bare letter string.

    `color` defaults to the live `PLAYER_C` (read here, not captured as a
    default-argument value, so `set_player_color` takes effect on every
    caller that doesn't pass its own colour -- which is all of them today)."""
    pygame.draw.circle(surf, color or PLAYER_C, center, r)
    race = getattr(unit, "race", None)
    sil = artwork.race_icon(race["name"], round(r * 1.6), TOKEN_INK) if race else None
    if sil is not None:
        surf.blit(sil, sil.get_rect(center=center))
    else:
        text(surf, getattr(unit, "token", unit), fonts.body_bd, TOKEN_INK,
             center, center=True)


def chip(surf, rect, label, value, fonts, *, accent=INFO):
    pygame.draw.rect(surf, SURFACE_1, rect, border_radius=RADIUS)
    text(surf, label, fonts.label, accent, (rect.centerx, rect.y + 7), center=True)
    text(surf, str(value), fonts.num, INK, (rect.centerx, rect.y + 24), center=True)


def section(surf, label, x, y, w, fonts, *, color=INFO):
    """A small tracked keyword with an underline; returns the y below it."""
    tracked(surf, label.upper(), fonts.label, color, (x, y))
    ry = y + 14
    pygame.draw.line(surf, LINE_SOFT, (x, ry), (x + w, ry))
    return ry + SP2


def set_pointer(hot):
    """Hand cursor while `hot` (hovering something clickable), arrow otherwise.
    A no-op if the platform/driver can't make system cursors (e.g. headless)."""
    try:
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if hot
                                else pygame.SYSTEM_CURSOR_ARROW)
    except pygame.error:
        pass


def pips(surf, center, count, total, *, r=6, gap=6, on=ACCENT, off=SURFACE_4):
    """A row of `total` dots, `count` filled, centred on `center`."""
    span = total * (2 * r) + (total - 1) * gap
    x = center[0] - span // 2 + r
    for i in range(total):
        pygame.draw.circle(surf, on if i < count else off, (x, center[1]), r)
        if i >= count:
            pygame.draw.circle(surf, LINE, (x, center[1]), r, 1)
        x += 2 * r + gap

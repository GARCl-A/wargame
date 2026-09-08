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

import pygame

from . import artwork
from .battle import COLS, ROWS

# --- spacing scale ----------------------------------------------------------- #
SP = (4, 8, 12, 16, 24, 32)
SP1, SP2, SP3, SP4, SP5, SP6 = SP

RADIUS = 6

# --- layout ---------------------------------------------------------------- #
TILE = 48
MARGIN = SP4
INIT_H = 46                            # initiative strip above the grid

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

PLAYER_C  = (94, 156, 214)
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


def token_badge(surf, center, unit, fonts, *, color=PLAYER_C, r=14):
    """The round unit token: a coloured disc carrying the unit's race silhouette
    (`artwork.race_icon`), falling back to its board letter when the race has no
    glyph. Used on every roster card (draft / guild / squad / loot / market /
    reward / sheet). `unit` may also be a bare letter string."""
    pygame.draw.circle(surf, color, center, r)
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

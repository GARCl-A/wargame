"""Legacy design system: the spacing scale, the blue-grey surface ramp and the
drawing helpers that the screens not yet on `gartok/ui/` still use.

Don't add new usage -- see `gartok/ui/README.md`. The board's palette and camera
live in `ui/board_style.py`, the banner colour in `ui/banner.py`, and the old
font bundle in `ui/tokens.py` (`LegacyFonts`, re-exported here as `Fonts`).

- `SP` is the spacing scale (4 / 8 / 12 / 16 / 24 / 32). Never hard-code a gap.
- Colours have *roles* (`INK`, `ACCENT`, `DANGER`, ...) plus a surface ramp
  (`SURFACE_0..3`). Old names (`TEXT`, `DIM`, `CARD_BG`, ...) are kept as aliases
  so nothing breaks.
- `Panel`, `chip`, `pips`, `text`, `Stack` keep the screens declarative.
"""

import pygame
from pygame import gfxdraw

from .ui.board_style import (  # noqa: F401 -- shared with the board
    DANGER,
    ENEMY_C,
    INK_FAINT,
    NEUTRAL_C,
    OK,
    PLAYER_C,
    WARN,
)
from .ui.tokens import LegacyFonts as Fonts  # noqa: F401 -- re-exported

# --- spacing scale ----------------------------------------------------------- #
SP = (4, 8, 12, 16, 24, 32)
SP1, SP2, SP3, SP4, SP5, SP6 = SP

RADIUS = 6
MARGIN = SP4


# --- palette --------------------------------------------------------------- #
# surface ramp: app -> well -> panel -> raised -> hover
SURFACE_0 = (18, 19, 24)
SURFACE_1 = (26, 28, 35)
SURFACE_2 = (33, 36, 45)
SURFACE_3 = (44, 48, 59)
SURFACE_4 = (56, 61, 74)

LINE      = (58, 63, 76)
LINE_SOFT = (40, 44, 54)

INK       = (255, 255, 255)
INK_DIM   = (200, 206, 218)

ACCENT    = (232, 194, 75)             # selection / active / focus (warm gold)
ACCENT_INK = (24, 20, 8)              # text on an accent fill

INFO      = (127, 168, 208)

BG        = SURFACE_0

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

def format_tooltip(title, description, fonts, max_px=260):
    """Formats a structured tooltip with an accent title and wrapped body lines."""
    lines = [(title, fonts.label, ACCENT)]
    for ln in wrap_lines([description], fonts.body_sm, max_px):
        lines.append((ln, fonts.body_sm, INK_DIM))
    return lines


def draw_tooltip(screen, font, lines, mouse_pos):
    """Draws a tooltip near the mouse. `lines` is a list of (text, font, color) tuples, 
    or just a string (which gets wrapped to a single style)."""
    if not lines:
        return
    if isinstance(lines, str):
        lines = [(ln, font, INK_DIM) for ln in wrap_lines(lines.split("\n"), font, 260)]
    if not lines:
        return

    tw = max(fo.size(s)[0] for s, fo, _ in lines) + 2 * SP3
    th = 2 * SP3 + sum(fo.get_height() + 2 for _, fo, _ in lines)
    W, H = screen.get_size()
    bx = min(mouse_pos[0] + 16, W - tw - SP2)
    by = min(mouse_pos[1] + 16, H - th - SP2)
    panel(screen, pygame.Rect(bx, by, tw, th), fill=SURFACE_2, border=LINE, width=1, radius=RADIUS)
    yy = by + SP3
    for s, fo, c in lines:
        text(screen, s, fo, c, (bx + SP3, yy))
        yy += fo.get_height() + 2


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
    if isinstance(lines, str):
        lines = [lines]
    
    flat_lines = []
    for ln in lines:
        flat_lines.extend(ln.split("\n"))

    for ln in flat_lines:
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

    def panel(self, surf, h, fill=(40, 44, 52), border=(68, 75, 89), radius=4, width=1):
        """Draws a panel of height h, advances y, and returns the rect."""
        r = pygame.Rect(self.x, self.y, self.w, h)
        panel(surf, r, fill=fill, border=border, radius=radius, width=width)
        self.y += h
        return r


def panel(surf, rect, *, fill=SURFACE_1, border=LINE_SOFT, radius=RADIUS, width=1):
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    if border and width:
        pygame.draw.rect(surf, border, rect, width, border_radius=radius)
    return rect


def smooth_circle(surf, color, center, radius, width=0):
    """Draws an anti-aliased circle. Replaces pygame.draw.circle where edges matter."""
    x, y = int(center[0]), int(center[1])
    r = int(radius)
    if width == 0:
        gfxdraw.filled_circle(surf, x, y, r, color)
        gfxdraw.aacircle(surf, x, y, r, color)
    else:
        pygame.draw.circle(surf, color, center, radius, width)
        gfxdraw.aacircle(surf, x, y, r, color)
        if width > 1:
            gfxdraw.aacircle(surf, x, y, r - width + 1, color)


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


def pips(surf, center, count, total, *, r=6, gap=6, on=ACCENT, off=SURFACE_4):
    """A row of `total` dots, `count` filled, centred on `center`."""
    span = total * (2 * r) + (total - 1) * gap
    x = center[0] - span // 2 + r
    for i in range(total):
        smooth_circle(surf, on if i < count else off, (x, center[1]), r)
        if i >= count:
            smooth_circle(surf, LINE, (x, center[1]), r, 1)
        x += 2 * r + gap

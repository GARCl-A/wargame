"""Tiny vector icons drawn with `pygame.draw` (no asset files).

`icon(surf, name, rect, color)` renders a line-art glyph fitted to `rect`. Used
for the action buttons and small status marks, so they scale with the layout and
stay theme-coloured.
"""

import pygame

__all__ = ["icon", "NAMES"]


def _box(rect, pad=0.18):
    """Inner square (x, y, s) with fractional padding."""
    s = min(rect.w, rect.h)
    p = s * pad
    inner = s - 2 * p
    cx = rect.x + rect.w / 2
    cy = rect.y + rect.h / 2
    return cx - inner / 2, cy - inner / 2, inner


def _lw(s):
    return max(2, int(s / 11))


# --------------------------------------------------------------------------- #

def _move(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    # footprint chevrons going up-right
    for i, t in enumerate((0.0, 0.45)):
        ox, oy = x + s * (0.15 + t), y + s * (0.7 - t)
        pygame.draw.lines(surf, c, False,
                          [(ox, oy + s * 0.22), (ox, oy), (ox + s * 0.22, oy)], w)
    pygame.draw.line(surf, c, (x + s * 0.15, y + s * 0.9),
                     (x + s * 0.9, y + s * 0.15), w)


def _sword(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.line(surf, c, (x + s * 0.15, y + s * 0.85),
                     (x + s * 0.8, y + s * 0.2), w)          # blade
    pygame.draw.line(surf, c, (x + s * 0.05, y + s * 0.6),
                     (x + s * 0.35, y + s * 0.9), w)         # guard
    pygame.draw.line(surf, c, (x + s * 0.0, y + s * 0.78),
                     (x + s * 0.22, y + s * 1.0), w)         # pommel


def _throw(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pts = [(x, y + s * 0.9), (x + s * 0.5, y - s * 0.05), (x + s * 0.95, y + s * 0.55)]
    pygame.draw.lines(surf, c, False, pts, w)               # arc
    # dagger at the end
    ex, ey = pts[-1]
    pygame.draw.line(surf, c, (ex - s * 0.12, ey - s * 0.12),
                     (ex + s * 0.14, ey + s * 0.14), w)
    pygame.draw.circle(surf, c, (int(pts[0][0]), int(pts[0][1])), max(2, int(s * 0.09)))


def _shout(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    # speech burst
    body = pygame.Rect(x, y + s * 0.12, s * 0.62, s * 0.5)
    pygame.draw.rect(surf, c, body, w, border_radius=int(s * 0.12))
    pygame.draw.polygon(surf, c, [(x + s * 0.16, y + s * 0.6),
                                  (x + s * 0.16, y + s * 0.9),
                                  (x + s * 0.42, y + s * 0.62)], 0)
    # motion lines
    for i in range(3):
        yy = y + s * (0.2 + i * 0.18)
        pygame.draw.line(surf, c, (x + s * 0.78, yy), (x + s * 0.98, yy), w)


def _hand(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.arc(surf, c, (x + s * 0.1, y + s * 0.2, s * 0.8, s * 0.9),
                    3.4, 6.1, w)
    for i in range(4):
        xx = x + s * (0.2 + i * 0.2)
        pygame.draw.line(surf, c, (xx, y + s * 0.42), (xx, y + s * (0.12 + i % 2 * 0.08)), w)


def _shield(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pts = [(x + s * 0.5, y), (x + s * 0.92, y + s * 0.16),
           (x + s * 0.78, y + s * 0.7), (x + s * 0.5, y + s * 0.98),
           (x + s * 0.22, y + s * 0.7), (x + s * 0.08, y + s * 0.16)]
    pygame.draw.polygon(surf, c, pts, w)


def _hourglass(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.line(surf, c, (x + s * 0.15, y), (x + s * 0.85, y), w)
    pygame.draw.line(surf, c, (x + s * 0.15, y + s), (x + s * 0.85, y + s), w)
    pygame.draw.lines(surf, c, False,
                      [(x + s * 0.15, y), (x + s * 0.85, y + s)], w)
    pygame.draw.lines(surf, c, False,
                      [(x + s * 0.85, y), (x + s * 0.15, y + s)], w)


def _restart(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.arc(surf, c, (x, y, s, s), 0.6, 5.6, w)
    pygame.draw.polygon(surf, c, [(x + s * 0.86, y + s * 0.0),
                                  (x + s * 1.02, y + s * 0.34),
                                  (x + s * 0.66, y + s * 0.24)])


def _pulse(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.lines(surf, c, False, [
        (x, y + s * 0.55), (x + s * 0.28, y + s * 0.55), (x + s * 0.42, y + s * 0.2),
        (x + s * 0.6, y + s * 0.9), (x + s * 0.72, y + s * 0.55), (x + s, y + s * 0.55),
    ], w)


def _cross(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.line(surf, c, (x + s * 0.5, y + s * 0.1), (x + s * 0.5, y + s * 0.9), w + 1)
    pygame.draw.line(surf, c, (x + s * 0.1, y + s * 0.5), (x + s * 0.9, y + s * 0.5), w + 1)


def _flee(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    # a doorway on the left, an arrow bolting out to the right
    pygame.draw.lines(surf, c, False,
                      [(x + s * 0.34, y), (x + s * 0.06, y),
                       (x + s * 0.06, y + s), (x + s * 0.34, y + s)], w)
    pygame.draw.line(surf, c, (x + s * 0.32, y + s * 0.5), (x + s * 0.96, y + s * 0.5), w)
    pygame.draw.lines(surf, c, False,
                      [(x + s * 0.68, y + s * 0.24), (x + s * 0.98, y + s * 0.5),
                       (x + s * 0.68, y + s * 0.76)], w)


def _eye(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.ellipse(surf, c, (x, y + s * 0.2, s, s * 0.6), w)
    pygame.draw.circle(surf, c, (int(x + s * 0.5), int(y + s * 0.5)), max(2, int(s * 0.14)))


_GLYPHS = {
    "move": _move, "attack": _sword, "throw": _throw, "demoralize": _shout,
    "pickup": _hand, "defend": _shield, "end": _hourglass, "restart": _restart,
    "stabilize": _pulse, "first_aid": _cross, "flee": _flee, "eye": _eye,
}

NAMES = tuple(_GLYPHS)


def icon(surf, name, rect, color):
    glyph = _GLYPHS.get(name)
    if glyph:
        glyph(surf, rect, color)

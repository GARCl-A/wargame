"""Tiny vector icons drawn with `pygame.draw` (no asset files).

`icon(surf, name, rect, color)` renders a line-art glyph fitted to `rect`. Used
for the action buttons and small status marks, so they scale with the layout and
stay palette-coloured.
"""

import pygame

__all__ = ["NAMES", "icon"]


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


def _push(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    # a wall on the right, an arrow shoving into it
    pygame.draw.line(surf, c, (x + s * 0.86, y), (x + s * 0.86, y + s), w)
    pygame.draw.line(surf, c, (x, y + s * 0.5), (x + s * 0.7, y + s * 0.5), w)
    pygame.draw.lines(surf, c, False,
                      [(x + s * 0.44, y + s * 0.24), (x + s * 0.72, y + s * 0.5),
                       (x + s * 0.44, y + s * 0.76)], w)


def _climb(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    # a zig-zag climbing line up two rails
    pygame.draw.line(surf, c, (x + s * 0.2, y), (x + s * 0.2, y + s), w)
    pygame.draw.line(surf, c, (x + s * 0.8, y), (x + s * 0.8, y + s), w)
    for i in range(3):
        yy = y + s * (0.2 + i * 0.3)
        pygame.draw.line(surf, c, (x + s * 0.2, yy), (x + s * 0.8, yy - s * 0.12), w)


def _drop(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    # a down arrow into an open box
    pygame.draw.line(surf, c, (x + s * 0.5, y), (x + s * 0.5, y + s * 0.62), w)
    pygame.draw.lines(surf, c, False,
                      [(x + s * 0.28, y + s * 0.4), (x + s * 0.5, y + s * 0.64),
                       (x + s * 0.72, y + s * 0.4)], w)
    pygame.draw.lines(surf, c, False,
                      [(x + s * 0.12, y + s * 0.66), (x + s * 0.12, y + s),
                       (x + s * 0.88, y + s), (x + s * 0.88, y + s * 0.66)], w)


def _jump(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    # a leaping arc from a low ledge to a low ledge
    pygame.draw.line(surf, c, (x, y + s * 0.9), (x + s * 0.2, y + s * 0.9), w)
    pygame.draw.line(surf, c, (x + s * 0.8, y + s * 0.9), (x + s, y + s * 0.9), w)
    pygame.draw.arc(surf, c, (x + s * 0.15, y, s * 0.7, s * 1.4), 0.5, 2.6, w)


def _bite(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    # top teeth
    pygame.draw.line(surf, c, (x + s * 0.1, y + s * 0.3), (x + s * 0.9, y + s * 0.3), w)
    pygame.draw.polygon(surf, c, [(x + s * 0.2, y + s * 0.3), (x + s * 0.4, y + s * 0.6), (x + s * 0.6, y + s * 0.3)], w)
    # bottom teeth
    pygame.draw.line(surf, c, (x + s * 0.1, y + s * 0.7), (x + s * 0.9, y + s * 0.7), w)
    pygame.draw.polygon(surf, c, [(x + s * 0.4, y + s * 0.7), (x + s * 0.6, y + s * 0.4), (x + s * 0.8, y + s * 0.7)], w)


def _web(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    cx, cy = x + s / 2, y + s / 2
    tips = [(x + s * fx, y + s * fy) for fx, fy in
            ((0, 0.5), (0.15, 0.15), (0.5, 0), (0.85, 0.15), (1, 0.5), (0.85, 0.85), (0.5, 1), (0.15, 0.85))]
    for t in tips:
        pygame.draw.line(surf, c, (cx, cy), t, w)
    ring = [(cx + (t[0] - cx) * 0.55, cy + (t[1] - cy) * 0.55) for t in tips]
    pygame.draw.polygon(surf, c, ring, w)


def _horn(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    # a flared horn blowing to the right, with two sound arcs
    pygame.draw.polygon(surf, c, [(x, y + s * 0.42), (x + s * 0.5, y + s * 0.42),
                                  (x + s * 0.72, y + s * 0.18), (x + s * 0.72, y + s * 0.82),
                                  (x + s * 0.5, y + s * 0.58), (x, y + s * 0.58)], w)
    pygame.draw.arc(surf, c, (x + s * 0.7, y + s * 0.3, s * 0.3, s * 0.4), -1.0, 1.0, w)
    pygame.draw.arc(surf, c, (x + s * 0.55, y + s * 0.12, s * 0.45, s * 0.76), -1.0, 1.0, w)


def _lock(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    # closed shackle over a body -- exempt from distribute_load
    pygame.draw.arc(surf, c, (x + s * 0.16, y, s * 0.68, s * 0.68), 0.3, 2.85, w)
    body = pygame.Rect(x, y + s * 0.42, s, s * 0.56)
    pygame.draw.rect(surf, c, body, w, border_radius=max(1, int(s * 0.1)))


def _unlock(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    # shackle swung open -- free to move in distribute_load
    pygame.draw.arc(surf, c, (x - s * 0.08, y - s * 0.1, s * 0.68, s * 0.68), 0.95, 3.45, w)
    body = pygame.Rect(x, y + s * 0.42, s, s * 0.56)
    pygame.draw.rect(surf, c, body, w, border_radius=max(1, int(s * 0.1)))


def _sneak_attack(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.lines(surf, c, False, [(x, y + s * 0.4), (x + s * 0.35, y), (x + s * 0.7, y)], w)
    pygame.draw.line(surf, c, (x + s * 0.2, y + s * 0.6), (x + s * 0.85, y + s * 0.15), w + 1)
    pygame.draw.line(surf, c, (x + s * 0.15, y + s * 0.45), (x + s * 0.35, y + s * 0.75), w)
    pygame.draw.line(surf, c, (x + s * 0.05, y + s * 0.75), (x + s * 0.2, y + s * 0.6), w)
    pygame.draw.line(surf, c, (x + s * 0.95, y + s * 0.1), (x + s * 0.75, y + s * 0.05), w)
    pygame.draw.line(surf, c, (x + s * 0.9, y + s * 0.3), (x + s * 0.95, y + s * 0.1), w)


def _cleave(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.arc(surf, c, (x, y + s * 0.05, s * 0.9, s * 0.9), 0.2, 2.7, w + 1)
    pygame.draw.polygon(surf, c, [(x + s * 0.6, y + s * 0.1), (x + s * 0.95, y + s * 0.3),
                                  (x + s * 0.8, y + s * 0.65), (x + s * 0.5, y + s * 0.45)], w)
    pygame.draw.line(surf, c, (x + s * 0.55, y + s * 0.4), (x + s * 0.1, y + s * 0.9), w)
    pygame.draw.line(surf, c, (x + s * 0.15, y + s * 0.2), (x + s * 0.35, y + s * 0.4), w)
    pygame.draw.line(surf, c, (x + s * 0.3, y + s * 0.1), (x + s * 0.5, y + s * 0.3), w)


def _precise_thrust(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.line(surf, c, (x + s * 0.1, y + s * 0.85), (x + s * 0.88, y + s * 0.18), w)
    pygame.draw.arc(surf, c, (x + s * 0.15, y + s * 0.65, s * 0.3, s * 0.25), 0.5, 3.5, w)
    cx, cy = x + s * 0.85, y + s * 0.2
    pts = [(cx, cy - s * 0.16), (cx + s * 0.14, cy), (cx, cy + s * 0.16), (cx - s * 0.14, cy)]
    pygame.draw.polygon(surf, c, pts, w)


def _repel_strike(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.line(surf, c, (x + s * 0.35, y + s * 0.1), (x + s * 0.35, y + s * 0.85), w + 1)
    pygame.draw.line(surf, c, (x + s * 0.2, y + s * 0.7), (x + s * 0.5, y + s * 0.7), w)
    pygame.draw.arc(surf, c, (x + s * 0.35, y + s * 0.25, s * 0.35, s * 0.5), -1.2, 1.2, w)
    pygame.draw.arc(surf, c, (x + s * 0.45, y + s * 0.12, s * 0.5, s * 0.76), -1.2, 1.2, w)


def _maiming_strike(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.line(surf, c, (x + s * 0.15, y + s * 0.15), (x + s * 0.65, y + s * 0.65), w)
    pygame.draw.rect(surf, c, pygame.Rect(x + s * 0.5, y + s * 0.4, s * 0.35, s * 0.25), w)
    pygame.draw.lines(surf, c, False,
                      [(x + s * 0.1, y + s * 0.85), (x + s * 0.45, y + s * 0.85),
                       (x + s * 0.55, y + s * 0.75), (x + s * 0.65, y + s * 0.95),
                       (x + s * 0.9, y + s * 0.85)], w)


def _armor_pierce(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.line(surf, c, (x + s * 0.6, y + s * 0.1), (x + s * 0.6, y + s * 0.4), w + 1)
    pygame.draw.line(surf, c, (x + s * 0.6, y + s * 0.6), (x + s * 0.6, y + s * 0.9), w + 1)
    pygame.draw.polygon(surf, c, [(x + s * 0.1, y + s * 0.5), (x + s * 0.85, y + s * 0.44),
                                  (x + s * 0.85, y + s * 0.56)], 0)
    pygame.draw.line(surf, c, (x + s * 0.65, y + s * 0.35), (x + s * 0.8, y + s * 0.25), w)
    pygame.draw.line(surf, c, (x + s * 0.65, y + s * 0.65), (x + s * 0.8, y + s * 0.75), w)


def _power_shot(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.arc(surf, c, (x + s * 0.05, y + s * 0.1, s * 0.5, s * 0.8), -1.4, 1.4, w)
    pygame.draw.line(surf, c, (x + s * 0.15, y + s * 0.5), (x + s * 0.95, y + s * 0.5), w + 1)
    pygame.draw.lines(surf, c, False, [(x + s * 0.78, y + s * 0.32), (x + s * 0.96, y + s * 0.5),
                                       (x + s * 0.78, y + s * 0.68)], w)
    pygame.draw.line(surf, c, (x + s * 0.4, y + s * 0.28), (x + s * 0.6, y + s * 0.28), w)
    pygame.draw.line(surf, c, (x + s * 0.4, y + s * 0.72), (x + s * 0.6, y + s * 0.72), w)


def _extreme_shot(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.arc(surf, c, (x, y + s * 0.1, s * 0.88, s * 0.9), 0.4, 2.5, w)
    pygame.draw.lines(surf, c, False, [(x + s * 0.75, y + s * 0.45), (x + s * 0.88, y + s * 0.6),
                                       (x + s * 0.88, y + s * 0.42)], w)
    pygame.draw.circle(surf, c, (int(x + s * 0.85), int(y + s * 0.65)), max(2, int(s * 0.14)), w)
    pygame.draw.line(surf, c, (x + s * 0.1, y + s * 0.85), (x + s * 0.3, y + s * 0.85), w)
    pygame.draw.line(surf, c, (x + s * 0.4, y + s * 0.85), (x + s * 0.6, y + s * 0.85), w)


def _hook_shield(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    s_pts = [(x + s * 0.65, y + s * 0.15), (x + s * 0.95, y + s * 0.25),
             (x + s * 0.85, y + s * 0.75), (x + s * 0.65, y + s * 0.95)]
    pygame.draw.lines(surf, c, False, s_pts, w)
    pygame.draw.line(surf, c, (x + s * 0.05, y + s * 0.85), (x + s * 0.55, y + s * 0.35), w)
    pygame.draw.lines(surf, c, False,
                      [(x + s * 0.55, y + s * 0.35), (x + s * 0.7, y + s * 0.2),
                       (x + s * 0.8, y + s * 0.28), (x + s * 0.7, y + s * 0.42)], w + 1)


def _javelin_charge(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.line(surf, c, (x + s * 0.05, y + s * 0.5), (x + s * 0.92, y + s * 0.5), w)
    pts = [(x + s * 0.72, y + s * 0.38), (x + s * 0.95, y + s * 0.5),
           (x + s * 0.72, y + s * 0.62), (x + s * 0.76, y + s * 0.5)]
    pygame.draw.polygon(surf, c, pts, 0)
    for ox in (0.15, 0.35):
        pygame.draw.lines(surf, c, False,
                          [(x + s * ox, y + s * 0.25), (x + s * (ox + 0.12), y + s * 0.5),
                           (x + s * ox, y + s * 0.75)], w)


def _parry_strike(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.line(surf, c, (x + s * 0.15, y + s * 0.85), (x + s * 0.75, y + s * 0.15), w)
    pygame.draw.line(surf, c, (x + s * 0.1, y + s * 0.65), (x + s * 0.35, y + s * 0.9), w)
    pygame.draw.line(surf, c, (x + s * 0.25, y + s * 0.2), (x + s * 0.9, y + s * 0.8), w + 1)
    pygame.draw.line(surf, c, (x + s * 0.2, y + s * 0.35), (x + s * 0.4, y + s * 0.15), w)
    cx, cy = x + s * 0.48, y + s * 0.48
    pygame.draw.line(surf, c, (cx - s * 0.1, cy), (cx + s * 0.1, cy), w)
    pygame.draw.line(surf, c, (cx, cy - s * 0.1), (cx, cy + s * 0.1), w)


def _long_thrust(surf, rect, c):
    x, y, s = _box(rect)
    w = _lw(s)
    pygame.draw.line(surf, c, (x + s * 0.05, y + s * 0.95), (x + s * 0.68, y + s * 0.32), w)
    pygame.draw.polygon(surf, c, [(x + s * 0.62, y + s * 0.26), (x + s * 0.95, y + s * 0.05),
                                  (x + s * 0.74, y + s * 0.38)], 0)
    pygame.draw.arc(surf, c, (x + s * 0.55, y + s * 0.02, s * 0.42, s * 0.42), 1.6, 3.4, w)
    for ox in (0.1, 0.26):
        pygame.draw.line(surf, c, (x + s * ox, y + s * 0.6), (x + s * (ox + 0.1), y + s * 0.5), w)


_GLYPHS = {
    "move": _move, "attack": _sword, "attack_tongue": _throw, "throw": _throw,
    "demoralize": _shout, "assess": _eye, "eat_corpse": _bite, "spin_web": _web, "signal_horn": _horn,
    "pickup": _hand, "defend": _shield, "end": _hourglass, "delay": _restart, "restart": _restart,
    "stabilize": _pulse, "first_aid": _cross, "flee": _flee, "eye": _eye,
    "push": _push, "climb": _climb, "drop": _drop, "jump": _jump,
    "grab": _hand, "escape_grapple": _flee, "zombie_bite": _bite,
    "lock": _lock, "unlock": _unlock,
    "sneak_attack": _sneak_attack, "cleave": _cleave, "precise_thrust": _precise_thrust,
    "repel_strike": _repel_strike, "maiming_strike": _maiming_strike, "armor_pierce": _armor_pierce,
    "power_shot": _power_shot, "extreme_shot": _extreme_shot, "hook_shield": _hook_shield,
    "javelin_charge": _javelin_charge, "parry_strike": _parry_strike, "long_thrust": _long_thrust,
    "tail_sweep": _cleave, "lift_rider": _hand, "pixie_dust": _jump,
}

NAMES = tuple(_GLYPHS)


def icon(surf, name, rect, color):
    glyph = _GLYPHS.get(name)
    if glyph:
        glyph(surf, rect, color)

"""Item silhouettes drawn in code: one generator per category, tinted by material.

Data in, pixels out like the rest of `gartok.ui`: `draw_item_icon(surf, rect, kind, tone, rim,
**shape)` knows nothing about `ItemDef`. The shapes live in a 100x100 box, are drawn at 4x on a
transparent layer and scaled down, which is what keeps the edges smooth.
"""

import math

import pygame

from .tokens import T, mix

SS = 4


def _rot(pts, deg, c=(50, 50)):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(c[0] + (x - c[0]) * ca - (y - c[1]) * sa, c[1] + (x - c[0]) * sa + (y - c[1]) * ca) for x, y in pts]


def _blade(g, tone, dark, length=56, width=9, guard=22, taper=0.35, deg=45):
    """A sword or dagger standing upright, then turned. `length` is the blade, in box units."""
    top = 50 - length / 2 - 10
    base = top + length
    hw = width / 2
    blade = [(50, top), (50 + hw, top + length * taper), (50 + hw, base), (50 - hw, base), (50 - hw, top + length * taper)]
    g.poly(_rot(blade, deg), tone)
    g.line(_rot([(50, top + 6), (50, base - 2)], deg), dark, 1.4)
    g.poly(_rot([(50 - guard / 2, base), (50 + guard / 2, base), (50 + guard / 2, base + 4), (50 - guard / 2, base + 4)], deg), dark)
    g.poly(_rot([(47, base + 4), (53, base + 4), (53, base + 16), (47, base + 16)], deg), dark)
    cx, cy = _rot([(50, base + 19)], deg)[0]
    g.circle((cx, cy), 4.5, dark)


def _bow(g, tone, dark, draw=1.0):
    """A bow strung and bent, pointing right; `draw` pulls the string back."""
    pts_out, pts_in = [], []
    for i in range(21):
        t = i / 20
        a = math.radians(-70 + 140 * t)
        pts_out.append((30 + 38 * math.cos(a), 50 + 46 * math.sin(a)))
        pts_in.append((30 + 30 * math.cos(a), 50 + 46 * math.sin(a)))
    g.poly(pts_out + pts_in[::-1], tone)
    top, bot = pts_out[0], pts_out[-1]
    string = mix(tone, (255, 255, 255), .55)
    g.line([top, (30 - 14 * draw, 50), bot], string, 1.4)
    g.line([(30 - 14 * draw, 50), (88, 50)], string, 2.4)
    g.poly([(88, 50), (78, 44), (78, 56)], string)


def _armor(g, tone, dark, heavy=0.0):
    """A body armour front: shoulders, torso and a belt; `heavy` (0-1) adds pauldrons and rivets."""
    body = [(36, 18), (44, 22), (56, 22), (64, 18), (82, 26), (78, 44), (68, 42), (70, 84),
            (30, 84), (32, 42), (22, 44), (18, 26)]
    g.poly(body, tone)
    g.poly([(44, 22), (56, 22), (50, 34)], dark)
    g.poly([(31, 66), (69, 66), (69, 72), (31, 72)], dark)
    if heavy:
        for x in (18, 82):
            g.circle((x, 30), 11 * (0.6 + 0.4 * heavy), tone)
            g.circle((x, 30), 11 * (0.6 + 0.4 * heavy), dark, 1.6)
        for x in (38, 50, 62):
            g.circle((x, 52), 2.2, dark)
    g.line([(50, 34), (50, 66)], dark, 1.2)


def _flask(g, tone, dark, liquid=(176, 66, 58)):
    g.poly([(42, 14), (58, 14), (58, 36), (42, 36)], tone)
    g.poly([(40, 8), (60, 8), (60, 15), (40, 15)], dark)
    g.circle((50, 62), 28, tone)
    g.circle((50, 64), 23, liquid)
    g.poly([(23, 52), (77, 52), (77, 40), (23, 40)], tone)
    g.circle((41, 58), 5, mix(liquid, (255, 255, 255), .45))
    g.circle((50, 62), 28, dark, 2)


KINDS = {"blade": _blade, "bow": _bow, "armor": _armor, "flask": _flask}


class _Canvas:
    def __init__(self, size):
        self.s = size / 100
        self.surf = pygame.Surface((size, size), pygame.SRCALPHA)

    def _p(self, pts):
        return [(x * self.s, y * self.s) for x, y in pts]

    def poly(self, pts, col):
        pygame.draw.polygon(self.surf, col, self._p(pts))

    def line(self, pts, col, w):
        pygame.draw.lines(self.surf, col, False, self._p(pts), max(1, round(w * self.s)))

    def circle(self, c, r, col, width=0):
        pygame.draw.circle(self.surf, col, (c[0] * self.s, c[1] * self.s), r * self.s,
                           max(1, round(width * self.s)) if width else 0)


def draw_item_icon(surf, rect, kind, tone, rim=None, **shape):
    """Paint `kind` ("blade" / "bow" / "armor" / "flask") into `rect`: a dark plate with an
    optional `rim` colour (rarity), the silhouette in `tone`, its details a shade darker."""
    side = min(rect.w, rect.h)
    box = pygame.Rect(0, 0, side, side)
    box.center = rect.center
    pygame.draw.rect(surf, T.STEEL, box, border_radius=T.S // 2)
    pygame.draw.rect(surf, rim or T.STEEL_LINE, box, 2 if rim else 1, border_radius=T.S // 2)
    inner = side * 0.8
    g = _Canvas(int(inner * SS))
    KINDS[kind](g, tone, mix(tone, (0, 0, 0), .55), **shape)
    icon = pygame.transform.smoothscale(g.surf, (int(inner), int(inner)))
    surf.blit(icon, icon.get_rect(center=box.center))

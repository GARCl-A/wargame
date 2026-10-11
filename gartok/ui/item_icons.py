"""Item silhouettes drawn in code: one generator per kind, tinted by material.

Data in, pixels out like the rest of `gartok.ui`: `draw_item_icon(surf, rect, kind, tone, rim,
**shape)` knows nothing about `ItemDef`; `gartok/item_icon.py` is the adapter that turns an item
into (kind, tone, rim, shape). Shapes live in a 100x100 box, are drawn at 4x on a transparent
layer and scaled down, which keeps the edges smooth. A generator paints with `g.tone` (the
material), `g.dark` (its details) and `g.lite` (a highlight); `accent` in the shape is a second
colour for the part that is not the material (a liquid, a seal, a gem).
"""

import math

import pygame

from .tokens import T, mix

SS = 4

TONES = {
    "iron": (150, 158, 170), "steel": (190, 198, 210), "wood": (150, 108, 66), "oak": (112, 78, 46),
    "leather": (160, 120, 76), "brass": T.BRASS, "gold": (226, 186, 72), "copper": (190, 112, 68),
    "cloth": (156, 146, 126), "bone": (216, 208, 186), "stone": (132, 132, 138), "coal": (74, 74, 82),
    "paper": (214, 200, 164), "glass": (190, 205, 215), "red": (176, 66, 58), "green": (106, 146, 98),
    "purple": (150, 100, 182), "blue": (84, 124, 176), "flesh": (196, 98, 84), "salt": (226, 226, 222),
    "fruit": (190, 62, 52), "potato": (176, 140, 86), "mushroom": (190, 70, 62), "rot": (118, 130, 80),
    "amber": (214, 150, 52), "jerky": (128, 72, 54), "fur": (140, 118, 98), "storm": (122, 150, 196),
}


def _rot(pts, deg, c=(50, 50)):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(c[0] + (x - c[0]) * ca - (y - c[1]) * sa, c[1] + (x - c[0]) * sa + (y - c[1]) * ca) for x, y in pts]


def _arc(cx, cy, rx, ry, a0, a1, n=20):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def _rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _blade(g, length=56, width=9, guard=22, taper=0.35, deg=45):
    top = 50 - length / 2 - 10
    base = top + length
    hw = width / 2
    blade = [(50, top), (50 + hw, top + length * taper), (50 + hw, base), (50 - hw, base), (50 - hw, top + length * taper)]
    g.poly(_rot(blade, deg), g.tone)
    g.line(_rot([(50, top + 6), (50, base - 2)], deg), g.dark, 1.4)
    g.poly(_rot(_rect(50 - guard / 2, base, guard, 4), deg), g.dark)
    g.poly(_rot(_rect(47, base + 4, 6, 12), deg), g.dark)
    g.circle(_rot([(50, base + 19)], deg)[0], 4.5, g.dark)


def _hafted(g, head="axe", length=76, deg=40, double=False, size=1.0, metal=None):
    """A shaft with a head on top (axe, hammer, pick, spear, club, bare staff), drawn upright and turned."""
    top = 50 - length / 2
    bot = 50 + length / 2
    shaft_w = 4.5
    if head == "club":
        body = [(44, top), (56, top), (60, top + 14), (55, bot - 8), (53, bot), (47, bot), (45, bot - 8), (40, top + 14)]
        g.poly(_rot(body, deg), g.tone)
        g.line(_rot([(46, top + 8), (46, bot - 14)], deg), g.dark, 1.2)
        for y in (top + 16, top + 28):
            g.line(_rot([(41, y), (59, y)], deg), g.dark, 1.2)
        return
    g.poly(_rot(_rect(50 - shaft_w / 2, top + 4, shaft_w, length - 4), deg), g.tone)
    g.poly(_rot(_rect(50 - 3.4, bot - 8, 6.8, 8), deg), g.dark)
    if head == "staff":
        for y in (top + 2, bot - 14):
            g.poly(_rot(_rect(46, y, 8, 8), deg), g.dark)
        return
    s = size
    hc = metal or g.lite
    if head == "axe":
        side = [(50, top + 6), (50 + 26 * s, top - 2), (50 + 32 * s, top + 16 * s), (50 + 26 * s, top + 34 * s), (50, top + 28 * s)]
        g.poly(_rot(side, deg), hc)
        if double:
            g.poly(_rot([(50 - x + 50, y) for x, y in side], deg), hc)
        g.line(_rot([(54, top + 12), (50 + 26 * s, top + 16 * s)], deg), g.dark, 1.2)
    elif head == "hammer":
        w, h = 17 * s, 20 * s
        g.poly(_rot(_rect(50 - w, top, 2 * w, h), deg), hc)
        g.poly(_rot(_rect(50 - w, top, 2 * w, 5), deg), g.dark)
    elif head == "pick":
        sw = [(50, top + 14), (50 - 28 * s, top + 22), (50 - 40 * s, top + 36), (50 - 26 * s, top + 24 * s + 4),
              (50, top + 20), (50 + 26 * s, top + 24 * s + 4), (50 + 40 * s, top + 36), (50 + 28 * s, top + 22)]
        g.poly(_rot(sw, deg), hc)
    elif head == "spear":
        g.poly(_rot([(50, top - 6), (58, top + 14), (50, top + 22), (42, top + 14)], deg), hc)
        g.line(_rot([(50, top), (50, top + 18)], deg), g.dark, 1.2)


def _bow(g, draw=1.0):
    pts_out = _arc(30, 50, 38, 46, -70, 70)
    pts_in = _arc(30, 50, 30, 46, -70, 70)
    g.poly(pts_out + pts_in[::-1], g.tone)
    string = mix(g.tone, (255, 255, 255), .55)
    g.line([pts_out[0], (30 - 14 * draw, 50), pts_out[-1]], string, 1.4)
    g.line([(30 - 14 * draw, 50), (88, 50)], string, 2.4)
    g.poly([(88, 50), (78, 44), (78, 56)], string)


def _crossbow(g):
    g.poly(_rect(16, 45, 62, 10), g.tone)
    g.poly([(16, 45), (8, 52), (16, 55)], g.dark)
    g.poly(_arc(70, 50, 12, 38, -90, 90) + _arc(70, 50, 7, 38, 90, -90), g.dark)
    string = mix(g.tone, (255, 255, 255), .55)
    g.line([(70, 12), (46, 50), (70, 88)], string, 1.6)
    g.line([(46, 50), (84, 50)], g.dark, 2)
    g.poly([(84, 50), (76, 46), (76, 54)], g.lite)


def _shield(g, boss=None):
    body = [(24, 14), (76, 14), (76, 48), (50, 88), (24, 48)]
    g.poly(body, g.tone)
    g.line(body + [body[0]], g.dark, 2.4)
    g.line([(50, 18), (50, 80)], g.dark, 1)
    g.circle((50, 44), 11, boss or g.lite)
    g.circle((50, 44), 11, g.dark, 1.6)


def _armor(g, style="plain", pauldrons=0.0, trim=None):
    body = [(36, 18), (44, 22), (56, 22), (64, 18), (82, 26), (78, 44), (68, 42), (70, 84),
            (30, 84), (32, 42), (22, 44), (18, 26)]
    g.poly(body, g.tone)
    g.poly([(44, 22), (56, 22), (50, 34)], g.dark)
    g.poly(_rect(31, 66, 38, 6), trim or g.dark)
    if style == "studded":
        for x in (36, 46, 56, 66):
            for y in (44, 56):
                g.circle((x - 2, y), 2.2, g.lite)
    elif style == "mail":
        for y in range(40, 66, 6):
            for x in range(34 + (y // 6 % 2) * 3, 68, 6):
                g.circle((x, y), 2, g.dark, 0.8)
    elif style == "plates":
        for y in (46, 56, 66):
            g.line([(32, y), (68, y)], g.dark, 1.6)
        g.line([(50, 34), (50, 66)], g.dark, 1.2)
    else:
        g.line([(50, 34), (50, 66)], g.dark, 1.2)
    if pauldrons:
        for x in (18, 82):
            r = 11 * (0.6 + 0.4 * pauldrons)
            g.circle((x, 30), r, trim or g.tone)
            g.circle((x, 30), r, g.dark, 1.6)
    if style == "plates":
        for x in (38, 62):
            g.circle((x, 52), 2.2, g.dark)


def _cloak(g):
    g.poly([(36, 14), (64, 14), (86, 84), (14, 84)], g.tone)
    g.poly([(36, 14), (64, 14), (58, 30), (42, 30)], g.dark)
    g.line([(50, 30), (50, 84)], g.dark, 1.2)
    g.line([(30, 84), (36, 40)], g.dark, 1)
    g.line([(70, 84), (64, 40)], g.dark, 1)
    g.circle((50, 32), 4, g.lite)


def _flask(g, accent=(176, 66, 58), empty=False):
    g.poly(_rect(42, 14, 16, 22), g.tone)
    g.poly(_rect(40, 8, 20, 7), g.dark)
    g.circle((50, 62), 28, g.tone)
    if not empty:
        g.circle((50, 64), 23, accent)
    g.poly([(23, 52), (77, 52), (77, 40), (23, 40)], g.tone)
    g.circle((41, 58), 5, mix(accent if not empty else g.tone, (255, 255, 255), .5))
    g.circle((50, 62), 28, g.dark, 2)


def _ink(g, accent=(40, 44, 70)):
    g.poly(_rect(34, 42, 32, 40), g.tone)
    g.poly(_rect(42, 34, 16, 10), g.tone)
    g.poly(_rect(40, 28, 20, 7), g.dark)
    g.poly(_rect(38, 50, 24, 26), accent)
    g.poly([(58, 30), (84, 6), (80, 22), (66, 34)], g.lite)
    g.line([(60, 32), (82, 9)], g.dark, 1)


def _blob(cx, cy, rx, ry, wobble=0.0, n=36, dip=0.0):
    """A rounded outline, optionally wobbly or dipped at the top (an apple's stem well)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = 1 + wobble * math.sin(3 * a) + wobble * .6 * math.cos(5 * a)
        y = cy + ry * r * math.sin(a)
        y += dip * math.exp(-((math.degrees(a) - 270) / 24) ** 2)
        pts.append((cx + rx * r * math.cos(a), y))
    return pts


def _steak(g):
    """A cut of meat: a fat rim, a lean middle, marbling and a small bone."""
    g.poly(_blob(50, 54, 38, 30, .05), mix(g.tone, (255, 236, 220), .6))
    g.poly(_blob(50, 54, 33, 25, .05), g.tone)
    for a, b in (((30, 46), (48, 52)), ((44, 64), (68, 58)), ((52, 42), (70, 46))):
        g.line([a, b], g.lite, 2)
    g.circle((66, 62), 6, mix(g.tone, (255, 255, 255), .8))
    g.circle((66, 62), 3, g.dark)


def _apple(g, rot=False):
    body = _blob(50, 58, 30, 28, 0, dip=7)
    g.poly(body, g.tone)
    g.line(body + [body[0]], g.dark, 1.4)
    g.line([(50, 36), (54, 18)], g.dark, 2.6)
    g.poly([(54, 24), (76, 14), (70, 34)], (106, 146, 98) if not rot else (90, 100, 60))
    if rot:
        g.poly(_blob(38, 64, 11, 9, .15), g.dark)
        g.poly(_blob(64, 52, 8, 7, .15), g.dark)
        for x in (28, 74):
            g.line([(x, 14), (x + 6, 8), (x, 2)], (140, 150, 90), 1.4)
    else:
        g.circle((36, 50), 6, g.lite)


def _potato(g):
    g.poly([(18, 56), (26, 36), (50, 28), (76, 34), (86, 54), (74, 72), (44, 76), (24, 70)], g.tone)
    for x, y in ((38, 46), (58, 42), (64, 60), (34, 62)):
        g.circle((x, y), 2.4, g.dark)
    g.circle((34, 42), 6, g.lite)


def _mug(g):
    g.poly(_rect(24, 30, 38, 52), g.tone)
    g.line(_arc(62, 56, 14, 16, -90, 90), g.dark, 4)
    g.poly(_rect(26, 38, 34, 38), (214, 150, 52))
    for x in (30, 42, 54):
        g.circle((x, 30), 8, (240, 236, 222))
    g.line([(34, 44), (34, 72)], g.lite, 2)
    g.line([(46, 44), (46, 72)], g.lite, 2)


def _jerky(g):
    for i, y in enumerate((26, 44, 62)):
        pts = [(14 + i * 4, y), (80 + i * 3, y - 6), (86 + i * 3, y + 10), (20 + i * 4, y + 16)]
        g.poly(pts, g.tone if i != 1 else mix(g.tone, (0, 0, 0), .15))
        g.line([(24 + i * 4, y + 4), (76 + i * 3, y)], g.dark, 1.2)


def _sack(g, accent=None):
    g.poly([(30, 38), (70, 38), (82, 82), (18, 82)], g.tone)
    g.poly(_arc(50, 38, 20, 12, 180, 360), g.tone)
    g.line([(34, 36), (66, 36)], g.dark, 2.4)
    g.poly([(32, 30), (50, 20), (68, 30), (50, 36)], g.dark)
    for x, y in ((40, 62), (54, 70), (60, 56), (34, 74)):
        g.circle((x, y), 1.8, accent or g.dark)


def _drop(g):
    g.poly([(50, 8), (74, 50), (74, 62), (50, 84), (26, 62), (26, 50)], g.tone)
    g.circle((50, 62), 24, g.tone)
    g.circle((42, 58), 6, g.lite)
    g.circle((50, 62), 24, g.dark, 1.4)


def _hide(g):
    g.poly([(26, 18), (40, 22), (60, 22), (74, 18), (86, 34), (74, 46), (80, 70), (66, 86), (60, 74),
            (40, 74), (34, 86), (20, 70), (26, 46), (14, 34)], g.tone)
    g.line([(50, 28), (50, 68)], g.dark, 1.2)
    for x, y in ((38, 40), (62, 44), (44, 58), (58, 62)):
        g.circle((x, y), 3, g.dark)


def _mushroom(g):
    g.poly([(42, 50), (58, 50), (60, 84), (40, 84)], (226, 218, 196))
    g.poly(_arc(50, 52, 34, 34, 180, 360) + [(84, 52), (16, 52)], g.tone)
    for x, y in ((38, 38), (56, 32), (66, 44), (46, 46)):
        g.circle((x, y), 4, (240, 236, 222))


def _logs(g):
    for cx, cy in ((34, 66), (66, 66), (50, 36)):
        g.circle((cx, cy), 19, g.tone)
        g.circle((cx, cy), 19, g.dark, 1.6)
        g.circle((cx, cy), 12, g.lite)
        g.circle((cx, cy), 12, g.dark, 1)
        g.circle((cx, cy), 5, g.dark, 1)


def _ingot(g):
    g.poly([(14, 70), (30, 36), (82, 36), (90, 70)], g.tone)
    g.poly([(14, 70), (90, 70), (86, 80), (18, 80)], g.dark)
    g.poly([(32, 40), (78, 40), (80, 46), (28, 46)], g.lite)
    g.line([(40, 56), (70, 56)], g.dark, 1.4)


def _rocks(g, flecks=None):
    g.poly([(14, 78), (22, 46), (44, 34), (58, 50), (54, 78)], g.tone)
    g.poly([(46, 78), (58, 44), (82, 40), (90, 66), (84, 78)], mix(g.tone, (0, 0, 0), .2))
    g.poly([(36, 56), (52, 22), (72, 26), (66, 56)], g.lite)
    for x, y in ((28, 62), (66, 62), (56, 34), (76, 54)):
        g.circle((x, y), 3, flecks or g.dark)


def _brick(g):
    g.poly(_rect(12, 28, 76, 44), g.tone)
    for y in (42, 57):
        g.line([(12, y), (88, y)], g.dark, 1.6)
    for x, y0 in ((36, 28), (64, 42), (36, 57)):
        g.line([(x, y0), (x, y0 + 15)], g.dark, 1.6)
    g.poly(_rect(12, 28, 76, 4), g.lite)


def _sheet(g, ruled=True):
    g.poly([(24, 10), (60, 10), (78, 28), (78, 90), (24, 90)], g.tone)
    g.poly([(60, 10), (78, 28), (60, 28)], g.dark)
    if ruled:
        for y in (42, 54, 66, 78):
            g.line([(34, y), (68, y)], g.dark, 1.4)


def _horn(g, accent=None):
    """A curved horn: a bezier spine whose width grows from the mouthpiece to the bell."""
    p0, p1, p2 = (16, 22), (26, 84), (88, 70)
    spine = [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
              (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / 24 for i in range(25))]
    left, right = [], []
    for i, (x, y) in enumerate(spine):
        nx, ny = spine[min(i + 1, 24)][0] - spine[max(i - 1, 0)][0], spine[min(i + 1, 24)][1] - spine[max(i - 1, 0)][1]
        norm = math.hypot(nx, ny) or 1
        w = 2.5 + 15 * (i / 24) ** 1.5
        left.append((x - ny / norm * w, y + nx / norm * w))
        right.append((x + ny / norm * w, y - nx / norm * w))
    g.poly(left + right[::-1], g.tone)
    g.line(left, g.dark, 1.2)
    g.line(right, g.dark, 1.2)
    g.line([left[-1], right[-1]], g.dark, 3)
    band = 10
    g.line([left[band], right[band]], accent or g.dark, 3.4)
    g.line([left[band + 5], right[band + 5]], accent or g.dark, 3.4)


def _scroll(g, accent=(176, 66, 58)):
    g.poly(_rect(20, 30, 60, 40), g.tone)
    for x in (20, 80):
        g.poly(_arc(x, 50, 8, 22, 0, 360), g.lite)
        g.line(_arc(x, 50, 8, 22, 0, 360), g.dark, 1.2)
    for y in (42, 50, 58):
        g.line([(30, y), (70, y - 1)], g.dark, 1.2)
    g.poly(_rect(46, 28, 8, 44), accent)
    g.circle((50, 50), 6, accent)
    g.circle((50, 50), 6, g.dark, 1)


def _book(g, accent=None, clasp=False):
    g.poly(_rect(22, 12, 58, 76), g.tone)
    g.poly(_rect(22, 12, 8, 76), g.dark)
    g.poly(_rect(80, 14, 5, 72), (226, 218, 196))
    g.poly(_rect(36, 28, 36, 22), accent or g.dark)
    g.line([(40, 60), (68, 60)], g.dark, 1.6)
    g.line([(40, 68), (62, 68)], g.dark, 1.6)
    if clasp:
        g.poly(_rect(76, 44, 10, 12), (226, 186, 72))
        g.poly(_rect(22, 12, 58, 6), (226, 186, 72))
        g.poly(_rect(22, 82, 58, 6), (226, 186, 72))


def _torch(g):
    g.poly(_rot(_rect(46, 44, 8, 46), 18), g.tone)
    flame = [(50, 4), (66, 28), (62, 46), (38, 46), (34, 28)]
    g.poly(_rot(flame, 18, (50, 46)), (226, 140, 48))
    g.poly(_rot([(50, 20), (58, 34), (56, 46), (44, 46), (42, 34)], 18, (50, 46)), (250, 214, 110))


def _lantern(g):
    g.line(_arc(50, 18, 14, 14, 180, 360), g.dark, 2.4)
    g.poly(_rect(30, 28, 40, 6), g.dark)
    g.poly(_rect(34, 34, 32, 40), TONES["glass"])
    g.poly([(50, 40), (58, 54), (54, 68), (46, 68), (42, 54)], (240, 190, 80))
    for x in (34, 66):
        g.poly(_rect(x - 1, 34, 3, 40), g.dark)
    g.poly(_rect(28, 74, 44, 8), g.dark)


def _aid_kit(g):
    g.poly(_rect(16, 30, 68, 50), g.tone)
    g.poly(_rect(16, 30, 68, 8), g.dark)
    g.poly(_rect(38, 20, 24, 12), g.dark)
    g.poly(_rect(44, 44, 12, 28), (176, 66, 58))
    g.poly(_rect(36, 52, 28, 12), (176, 66, 58))


def _quiver(g):
    g.poly(_rot([(38, 30), (62, 30), (58, 90), (42, 90)], 18), g.tone)
    g.line(_rot([(40, 52), (60, 52)], 18), g.dark, 2)
    for dx in (-8, 0, 8):
        g.line(_rot([(50 + dx, 30), (50 + dx, 8)], 18, (50, 30)), g.lite, 2)
        g.poly(_rot([(50 + dx - 3, 14), (50 + dx + 3, 14), (50 + dx, 4)], 18, (50, 30)), g.dark)


def _chest(g, sealed=False):
    g.poly(_rect(14, 42, 72, 42), g.tone)
    g.poly(_arc(50, 42, 36, 24, 180, 360) + [(86, 42), (14, 42)], g.lite)
    g.line(_arc(50, 42, 36, 24, 180, 360), g.dark, 1.6)
    g.line([(14, 42), (86, 42)], g.dark, 2)
    for x in (28, 72):
        g.poly(_rect(x - 3, 24, 6, 60), g.dark)
    g.poly(_rect(44, 38, 12, 16), (226, 186, 72))
    if sealed:
        g.circle((50, 60), 7, (176, 66, 58))
        g.circle((50, 60), 7, g.dark, 1)
    else:
        g.circle((50, 46), 2, g.dark)


def _beartrap(g):
    g.circle((50, 54), 30, g.tone)
    g.circle((50, 54), 22, g.dark, 2)
    for a in range(0, 180, 20):
        g.poly([(50 + 22 * math.cos(math.radians(a + 180)), 54 + 22 * math.sin(math.radians(a + 180))),
                (50 + 30 * math.cos(math.radians(a + 190)), 54 + 30 * math.sin(math.radians(a + 190))),
                (50 + 30 * math.cos(math.radians(a + 170)), 54 + 30 * math.sin(math.radians(a + 170)))], g.lite)
    g.poly(_rect(14, 52, 72, 6), g.dark)
    g.circle((50, 55), 5, g.lite)
    g.line([(86, 55), (96, 70), (92, 90)], g.dark, 1.6)


def _alarm(g):
    g.poly(_rect(10, 80, 10, 8), g.dark)
    g.line([(15, 80), (15, 26)], g.tone, 4)
    g.line([(85, 80), (85, 26)], g.tone, 4)
    g.line([(15, 40), (50, 56), (85, 40)], g.lite, 1.6)
    g.poly(_arc(50, 62, 14, 14, 180, 360) + [(64, 74), (36, 74)], (226, 186, 72))
    g.circle((50, 78), 3.5, g.dark)
    g.line([(26, 52), (22, 44)], g.dark, 1.4)
    g.line([(74, 52), (78, 44)], g.dark, 1.4)


def _coin(g, mark="c"):
    g.circle((50, 50), 36, g.tone)
    g.circle((50, 50), 36, g.dark, 2.4)
    g.circle((50, 50), 27, g.dark, 1.2)
    g.circle((38, 38), 8, g.lite)
    if mark == "g":
        g.poly([(50, 30), (56, 46), (72, 48), (60, 58), (64, 74), (50, 64), (36, 74), (40, 58), (28, 48), (44, 46)], g.dark)
    else:
        g.poly(_rect(46, 32, 8, 36), g.dark)


def _saddle(g):
    g.poly([(18, 40), (82, 40), (88, 74), (12, 74)], g.tone)
    g.poly([(26, 18), (74, 18), (74, 44), (26, 44)], g.lite)
    g.line([(30, 56), (70, 56)], g.dark, 1.6)
    g.poly(_rect(12, 62, 20, 22), g.dark)
    g.poly(_rect(68, 62, 20, 22), g.dark)


def _harness(g):
    g.line(_arc(50, 46, 28, 32, 0, 360), g.tone, 8)
    g.line(_arc(50, 46, 28, 32, 0, 360), g.dark, 1.2)
    g.line([(50, 78), (50, 94)], g.tone, 5)
    g.circle((50, 14), 5, g.lite)
    g.line([(22, 46), (6, 56)], g.tone, 4)
    g.line([(78, 46), (94, 56)], g.tone, 4)
    g.circle((50, 80), 4, g.dark)


def _rope(g):
    for i, r in enumerate((34, 26, 18, 10)):
        g.circle((50, 56), r, g.tone if i % 2 == 0 else g.lite, 6)
    g.line([(50, 56), (82, 18), (92, 20)], g.tone, 5)


def _scissors(g):
    g.line([(34, 18), (68, 70)], g.tone, 7)
    g.line([(66, 18), (32, 70)], g.lite, 7)
    g.circle((50, 46), 4, g.dark)
    g.circle((30, 82), 10, g.dark, 4)
    g.circle((70, 82), 10, g.dark, 4)


def _shovel(g):
    g.line(_rot([(50, 6), (50, 56)], 30), g.tone, 6)
    g.poly(_rot(_rect(42, 4, 16, 6), 30), g.dark)
    g.poly(_rot([(34, 52), (66, 52), (62, 90), (50, 98), (38, 90)], 30, (50, 50)), g.lite)
    g.line(_rot([(50, 56), (50, 92)], 30, (50, 50)), g.dark, 1.2)


def _chisel(g):
    g.poly(_rot(_rect(44, 8, 12, 40), 35), g.tone)
    g.poly(_rot(_rect(41, 6, 18, 6), 35), g.dark)
    g.poly(_rot([(45, 48), (55, 48), (56, 86), (50, 94), (44, 86)], 35), g.lite)
    g.line(_rot([(50, 52), (50, 88)], 35), g.dark, 1)


def _pliers(g):
    g.poly(_rot([(40, 10), (50, 40), (46, 52), (36, 24)], 0), g.tone)
    g.poly([(60, 10), (50, 40), (54, 52), (64, 24)], g.tone)
    g.poly([(46, 48), (54, 48), (62, 88), (52, 88), (50, 66), (48, 88), (38, 88)], g.lite)
    g.circle((50, 46), 4, g.dark)
    g.line([(38, 88), (46, 88)], g.dark, 3)
    g.line([(54, 88), (62, 88)], g.dark, 3)


def _compass(g, accent=(176, 66, 58)):
    g.circle((50, 54), 36, g.tone)
    g.circle((50, 54), 36, g.dark, 2.4)
    g.circle((50, 54), 29, g.lite)
    g.circle((50, 16), 5, g.dark, 2.4)
    g.poly([(50, 28), (57, 54), (43, 54)], accent)
    g.poly([(50, 80), (57, 54), (43, 54)], g.dark)
    g.circle((50, 54), 3, g.tone)


def _cards(g):
    for i, deg in enumerate((-22, 0, 22)):
        card = _rot(_rect(34, 16, 32, 50), deg, (50, 80))
        g.poly(card, (232, 226, 210) if i != 2 else (226, 220, 200))
        g.line(card + [card[0]], g.dark, 1.4)
    g.poly(_rot([(50, 30), (58, 42), (50, 54), (42, 42)], 22, (50, 80)), (176, 66, 58))


def _lute(g):
    g.poly(_rot(_arc(50, 66, 24, 28, 0, 360, 24), -30, (50, 60)), g.tone)
    g.circle(_rot([(50, 66)], -30, (50, 60))[0], 7, g.dark)
    g.poly(_rot(_rect(46, 8, 8, 40), -30, (50, 60)), g.dark)
    g.poly(_rot(_rect(42, 4, 16, 8), -30, (50, 60)), g.lite)
    g.line(_rot([(50, 14), (50, 80)], -30, (50, 60)), g.lite, 1)


def _holy(g):
    for a in range(0, 360, 30):
        g.line([(50 + 22 * math.cos(math.radians(a)), 50 + 22 * math.sin(math.radians(a))),
                (50 + 40 * math.cos(math.radians(a)), 50 + 40 * math.sin(math.radians(a)))], g.lite, 3)
    g.circle((50, 50), 22, g.tone)
    g.circle((50, 50), 22, g.dark, 2)
    g.poly(_rect(46, 32, 8, 36), g.dark)
    g.poly(_rect(36, 42, 28, 8), g.dark)


def _chains(g):
    pts = [(20, 24), (36, 40), (52, 56), (68, 72), (82, 84)]
    for i, (x, y) in enumerate(pts):
        w, h = (16, 10) if i % 2 == 0 else (10, 16)
        g.line(_rot(_arc(x, y, w, h, 0, 360, 20), 0, (x, y)), g.tone if i % 2 == 0 else g.lite, 3.4)


def _map(g, accent=(176, 66, 58)):
    g.poly([(10, 24), (36, 18), (62, 26), (90, 18), (90, 76), (62, 84), (36, 76), (10, 82)], g.tone)
    for x in (36, 62):
        g.line([(x, 22), (x, 80)], g.dark, 1)
    g.line([(20, 66), (34, 50), (50, 58), (66, 40), (80, 48)], g.dark, 1.6)
    g.line([(60, 56), (76, 72)], accent, 3.4)
    g.line([(76, 56), (60, 72)], accent, 3.4)


def _gem(g):
    g.poly([(26, 38), (36, 22), (64, 22), (74, 38), (50, 84)], g.tone)
    g.poly([(26, 38), (74, 38), (50, 84)], mix(g.tone, (0, 0, 0), .25))
    g.poly([(36, 22), (50, 38), (64, 22)], g.lite)
    g.line([(26, 38), (74, 38)], g.dark, 1.2)
    g.line([(50, 38), (50, 84)], g.dark, 1)


def _gems(g):
    for (x, y, s), tint in zip(((32, 62, .8), (66, 60, .7), (50, 32, 1.0)),
                               (g.tone, mix(g.tone, (80, 160, 200), .5), mix(g.tone, (210, 70, 90), .5))):
        pts = [(x - 20 * s, y - 8 * s), (x - 12 * s, y - 22 * s), (x + 12 * s, y - 22 * s), (x + 20 * s, y - 8 * s), (x, y + 24 * s)]
        g.poly(pts, tint)
        g.line(pts + [pts[0]], g.dark, 1.2)
        g.poly([pts[1], (x, y - 8 * s), pts[2]], g.lite)


def _letter(g, accent=(176, 66, 58)):
    g.poly(_rect(12, 26, 76, 50), g.tone)
    g.line([(12, 26), (50, 54), (88, 26)], g.dark, 1.6)
    g.line([(12, 76), (40, 50)], g.dark, 1)
    g.line([(88, 76), (60, 50)], g.dark, 1)
    g.circle((50, 54), 7, accent)
    g.circle((50, 54), 7, g.dark, 1)


def _lightning(g):
    _hide(g)
    g.poly([(56, 22), (36, 52), (50, 52), (42, 80), (68, 44), (54, 44)], (240, 226, 120))


KINDS = {
    "blade": _blade, "hafted": _hafted, "bow": _bow, "crossbow": _crossbow, "shield": _shield,
    "armor": _armor, "cloak": _cloak, "flask": _flask, "ink": _ink,
    "steak": _steak, "apple": _apple, "potato": _potato, "mug": _mug, "jerky": _jerky,
    "sack": _sack, "drop": _drop, "hide": _hide, "mushroom": _mushroom, "logs": _logs,
    "ingot": _ingot, "rocks": _rocks, "brick": _brick, "sheet": _sheet, "horn": _horn,
    "scroll": _scroll, "book": _book, "torch": _torch, "lantern": _lantern,
    "aid_kit": _aid_kit, "quiver": _quiver, "chest": _chest, "beartrap": _beartrap, "alarm": _alarm,
    "coin": _coin, "saddle": _saddle, "harness": _harness,
    "rope": _rope, "scissors": _scissors, "shovel": _shovel, "chisel": _chisel, "pliers": _pliers,
    "compass": _compass, "cards": _cards, "lute": _lute, "holy": _holy, "chains": _chains, "map": _map,
    "gem": _gem, "gems": _gems, "letter": _letter, "storm_hide": _lightning,
}


class _Canvas:
    def __init__(self, size, tone):
        self.s = size / 100
        self.surf = pygame.Surface((size, size), pygame.SRCALPHA)
        self.tone = tone
        self.dark = mix(tone, (0, 0, 0), .55)
        self.lite = mix(tone, (255, 255, 255), .3)

    def _p(self, pts):
        return [(x * self.s, y * self.s) for x, y in pts]

    def poly(self, pts, col):
        pygame.draw.polygon(self.surf, col, self._p(pts))

    def line(self, pts, col, w):
        pygame.draw.lines(self.surf, col, False, self._p(pts), max(1, round(w * self.s)))

    def circle(self, c, r, col, width=0):
        pygame.draw.circle(self.surf, col, (c[0] * self.s, c[1] * self.s), r * self.s,
                           max(1, round(width * self.s)) if width else 0)


def draw_item_icon(surf, rect, kind, tone, rim=None, scale=0.8, **shape):
    """Paint `kind` into `rect`: a dark plate with an optional `rim` colour (rarity), the
    silhouette in `tone` filling `scale` of the plate (a Large weapon passes more), details a
    shade darker. `shape` is what the kind's generator takes."""
    side = min(rect.w, rect.h)
    box = pygame.Rect(0, 0, side, side)
    box.center = rect.center
    pygame.draw.rect(surf, T.STEEL, box, border_radius=T.S // 2)
    pygame.draw.rect(surf, rim or T.STEEL_LINE, box, 2 if rim else 1, border_radius=T.S // 2)
    inner = int(side * scale)
    g = _Canvas(inner * SS, tone)
    KINDS[kind](g, **shape)
    icon = pygame.transform.smoothscale(g.surf, (inner, inner))
    surf.blit(icon, icon.get_rect(center=box.center))

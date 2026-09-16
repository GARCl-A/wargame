"""The MAP zone: paper laid on the table, drawn from a node graph the
caller supplies (nodes/edges/terrain wash/region radii), plus the groups
standing on it. Mirrors `map_screen`'s node-graph drawing but in the
war-table's own ink-on-paper language instead of painted markers on a
dark ground.

Every function takes its graph/group data as parameters rather than
reading module globals, so a caller can drive this with `world.NODES` /
`world.EDGES` / real `Group` objects the same way the prototype drives it
with its own mock dicts. `pos` and `region_r` share whatever world-space
units the caller's `MapCamera` was built with -- the camera doesn't care
whether that's raw coordinates or a normalised 0..1 canvas, as long as
`region_r` is expressed in the same units as `pos`.
"""

import math
import random

import pygame

from .tokens import T, mix

NODE_R = 15


def paper_surface(size, seed=11):
    rnd = random.Random(seed)
    s = pygame.Surface(size).convert()
    s.fill(T.PAPER)
    for _ in range(120):                       # fibre / stain
        r = rnd.randint(30, 150)
        blob = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        c = T.PAPER_HI if rnd.random() < 0.5 else T.PAPER_LOW
        pygame.draw.circle(blob, (*c, 16), (r, r), r)
        s.blit(blob, (rnd.randrange(-r, size[0]), rnd.randrange(-r, size[1])))
    # vignette: paper darkens at the edges, helps it read as an object
    vig = pygame.Surface(size, pygame.SRCALPHA)
    for i in range(48):
        a = int(70 * (1 - i / 48) ** 2)
        pygame.draw.rect(vig, (30, 24, 16, a),
                         pygame.Rect(i, i, size[0] - 2 * i, size[1] - 2 * i), 1)
    s.blit(vig, (0, 0))
    return s


def glyph_tree(s, p, c, k):
    x, y = p
    pygame.draw.polygon(s, c, [(x, y - k), (x - k * .6, y + k * .5), (x + k * .6, y + k * .5)])
    pygame.draw.line(s, c, (x, y + k * .4), (x, y + k * .9), 1)


def glyph_hill(s, p, c, k):
    x, y = p
    pygame.draw.lines(s, c, False, [(x - k, y + k * .5), (x - k * .3, y - k * .6),
                                    (x + k * .2, y + k * .1), (x + k * .7, y - k * .4),
                                    (x + k * 1.2, y + k * .5)], 1)


def glyph_house(s, p, c, k):
    x, y = p
    pygame.draw.rect(s, c, pygame.Rect(x - k * .5, y - k * .1, k, k * .7), 1)
    pygame.draw.lines(s, c, False, [(x - k * .7, y - k * .1), (x, y - k * .7),
                                    (x + k * .7, y - k * .1)], 1)


GLYPH = {"green": glyph_tree, "rock": glyph_hill, "town": glyph_house}


def near_seg(p, a, b, tol):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1e-6
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - (a[0] + dx * t), p[1] - (a[1] + dy * t)) < tol


def draw_dotted(surf, a, b, color, r=2, step=10, recess=0):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy) or 1e-6
    ux, uy = dx / d, dy / d
    s0, s1 = recess, d - recess
    if s1 <= s0:
        return
    n = max(int((s1 - s0) // step), 1)
    for i in range(n + 1):
        t = s0 + (s1 - s0) * i / n
        pygame.draw.circle(surf, color, (int(a[0] + ux * t), int(a[1] + uy * t)), r)


def draw_map_node(surf, F, key, node, p, selected=False, icon_fn=None):
    """`icon_fn(surf, node, center)`, when given, replaces the built-in
    house/keep/hill glyph dispatch -- lets a caller with a real icon set
    (e.g. `artwork.icon`) draw its own mark instead of being limited to
    these three hand-drawn shapes."""
    x, y = int(p[0]), int(p[1])
    # ink mark: a hollow circle, no colour-filled disc
    pygame.draw.circle(surf, T.PAPER_HI, (x, y), NODE_R + 2)
    pygame.draw.circle(surf, T.INK, (x, y), NODE_R, 2)
    if icon_fn is not None:
        icon_fn(surf, node, (x, y))
    elif node["icon"] == "town":
        glyph_house(surf, (x, y), T.INK, 11)
    elif node["icon"] == "keep":
        pygame.draw.rect(surf, T.INK, pygame.Rect(x - 6, y - 5, 12, 10), 2)
        pygame.draw.line(surf, T.INK, (x, y - 5), (x, y - 10), 2)
    else:
        pygame.draw.polygon(surf, T.INK, [(x, y - 7), (x - 6, y + 5), (x + 6, y + 5)], 2)
    if selected:
        pygame.draw.circle(surf, T.BRASS, (x, y), NODE_R + 7, 2)

    lab = F["inkb"].render(node["name"], True, T.INK)
    r = lab.get_rect(midtop=(x, y + NODE_R + 6))
    halo = pygame.Surface((r.w + 10, r.h + 4), pygame.SRCALPHA)
    halo.fill((*T.PAPER, 190))
    surf.blit(halo, (r.x - 5, r.y - 2))
    surf.blit(lab, r)


def draw_pawn(surf, p, color=T.BRASS, alert=False):
    """A metal pawn: shadow + body + highlight -- the only metal on the paper."""
    x, y = int(p[0]), int(p[1])
    pygame.draw.ellipse(surf, (60, 48, 34), pygame.Rect(x - 9, y + 4, 18, 6))
    pygame.draw.polygon(surf, mix(color, (0, 0, 0), .45),
                        [(x - 7, y + 6), (x - 4, y - 4), (x + 4, y - 4), (x + 7, y + 6)])
    pygame.draw.circle(surf, color, (x, y - 8), 6)
    pygame.draw.circle(surf, mix(color, (255, 255, 255), .35), (x - 2, y - 10), 2)
    if alert:
        pygame.draw.circle(surf, T.BLOOD, (x + 9, y - 13), 5)
        pygame.draw.circle(surf, (250, 240, 230), (x + 9, y - 13), 5, 1)


def group_point(g, w2s, nodes):
    if isinstance(g["at"], tuple):
        a, b, t = g["at"]
        pa, pb = w2s(nodes[a]["pos"]), w2s(nodes[b]["pos"])
        return (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t)
    return w2s(nodes[g["at"]]["pos"])


def _hover_route(nodes, edges, start, hover_node):
    """Cheapest path (Dijkstra over hour-weighted edges) from `start` to
    `hover_node`, as a set of `frozenset({a, b})` edge pairs plus its
    total cost -- used to highlight the route a click would send a group
    down before it's actually sent."""
    adj = {k: {} for k in nodes}
    for u, v, w in edges:
        adj[u][v] = w
        adj[v][u] = w

    q = [(0, start, [])]
    visited = set()
    while q:
        q.sort()
        cost, u, path = q.pop(0)
        if u == hover_node:
            full = path + [u]
            pairs = {frozenset((full[i], full[i + 1])) for i in range(len(full) - 1)}
            return pairs, cost
        if u in visited:
            continue
        visited.add(u)
        for v, w in adj[u].items():
            if v not in visited:
                q.append((cost + w, v, path + [u]))
    return set(), 0


def draw_map(surf, F, rect, cam, nodes, edges, wash, region_r, groups, selected, mpos,
             minimap_size=None, icon_fn=None):
    inner = pygame.Rect(rect.x + T.S, rect.y + T.S, rect.w - T.S * 2, rect.h - T.S)
    cam.set_rect(inner)

    # the paper's shadow on the table
    for i in range(6):
        pygame.draw.rect(surf, mix(T.TABLE, (0, 0, 0), .5),
                         inner.inflate(i * 2, i * 2), 1, border_radius=2)
    surf.blit(paper_surface(inner.size), inner.topleft)
    old_clip = surf.get_clip()
    surf.set_clip(inner)

    w2s = cam.world_to_screen
    zoom = cam.zoom
    segs = [(w2s(nodes[a]["pos"]), w2s(nodes[b]["pos"])) for a, b, _ in edges]

    # 1. terrain washes
    layer = pygame.Surface(inner.size, pygame.SRCALPHA)
    for k, n in nodes.items():
        c = wash[n["terrain"]]
        cx, cy = w2s(n["pos"])
        cx, cy = cx - inner.x, cy - inner.y
        R = region_r[k] * zoom
        rnd = random.Random(hash(k) & 0xFFFF)
        for _ in range(10):
            a = rnd.uniform(0, math.tau)
            d = rnd.uniform(0, R * .45)
            br = rnd.uniform(R * .34, R * .58)
            blob = pygame.Surface((br * 2, br * 2), pygame.SRCALPHA)
            pygame.draw.circle(blob, (*c, 52), (br, br), br)
            layer.blit(blob, (cx + math.cos(a) * d - br, cy + math.sin(a) * d - br),
                       special_flags=pygame.BLEND_RGBA_MAX)
    surf.blit(layer, inner.topleft)

    # 2. terrain glyphs
    centers = [w2s(n["pos"]) for n in nodes.values()]
    for k, n in nodes.items():
        c = mix(wash[n["terrain"]], T.INK, .45)
        cx, cy = w2s(n["pos"])
        R = region_r[k] * zoom
        rnd = random.Random((hash(k) & 0xFFFF) ^ 0x5AD)
        placed, tries = 0, 0
        # `R` (the on-screen, zoomed radius), not the raw `region_r[k]` --
        # a caller whose region_r is a small fraction (a normalised 0..1
        # world, say) would floor this target to 0 and never place a glyph.
        while placed < R // 2 and tries < 700:
            tries += 1
            a = rnd.uniform(0, math.tau)
            d = R * math.sqrt(rnd.uniform(.12, 1.0))
            p = (cx + math.cos(a) * d, cy + math.sin(a) * d)
            if not inner.inflate(-T.S, -T.S).collidepoint(p):
                continue
            if any(math.hypot(p[0] - c2[0], p[1] - c2[1]) < NODE_R + 30 for c2 in centers):
                continue
            if any(near_seg(p, s[0], s[1], 16) for s in segs):
                continue
            GLYPH[n["terrain"]](surf, p, c, rnd.uniform(6, 10))
            placed += 1

    # 2.5 hover route preview
    g_sel = next(g for g in groups if g["key"] == selected)
    hover_path_edges = set()
    hover_node = None
    hover_cost = 0
    if not g_sel["busy"] and isinstance(g_sel["at"], str) and inner.collidepoint(mpos):
        for k, n in nodes.items():
            cx, cy = w2s(n["pos"])
            if math.hypot(mpos[0] - cx, mpos[1] - cy) < region_r[k] * zoom:
                hover_node = k
                break
        if hover_node and hover_node != g_sel["at"]:
            hover_path_edges, hover_cost = _hover_route(nodes, edges, g_sel["at"], hover_node)

    # 3. dotted roads
    for (pa, pb), (u, v, hours) in zip(segs, edges):
        if frozenset((u, v)) in hover_path_edges:
            pygame.draw.aaline(surf, T.INK, pa, pb)
            pygame.draw.aaline(surf, T.INK, (pa[0] + 1, pa[1]), (pb[0] + 1, pb[1]))
            pygame.draw.aaline(surf, T.INK, (pa[0], pa[1] + 1), (pb[0], pb[1] + 1))
        else:
            draw_dotted(surf, pa, pb, T.INK_SOFT, 2, 11, recess=NODE_R + 8)

    # 4. nodes
    sel_at = next((g["at"] for g in groups if g["key"] == selected), None)
    for k, n in nodes.items():
        draw_map_node(surf, F, k, n, w2s(n["pos"]), selected=(k == sel_at), icon_fn=icon_fn)

    # 5. pawns
    for g in groups:
        p = group_point(g, w2s, nodes)
        col = T.BRASS if g["key"] == selected else T.BRASS_DIM
        draw_pawn(surf, (p[0] + 16, p[1] - 12), col, alert=g.get("alert", False))

    # 6. hover tooltip
    if hover_node and hover_node != g_sel["at"] and hover_path_edges:
        hx, hy = w2s(nodes[hover_node]["pos"])
        tt = F["bodyb"].render(f"  Travel {int(hover_cost)} h  ", True, T.PAPER)
        ttr = tt.get_rect(midbottom=(hx, hy - 20))
        if ttr.right > inner.right:
            ttr.right = inner.right - 4
        if ttr.left < inner.left:
            ttr.left = inner.left + 4
        pygame.draw.rect(surf, T.INK, ttr)
        surf.blit(tt, ttr)

    surf.set_clip(old_clip)
    return draw_minimap(surf, F, inner, cam, nodes, edges, size=minimap_size)


def draw_minimap(surf, F, map_rect, cam, nodes, edges, size=None):
    """`size`, when given, is `(w, h)` in px. Left at None, the minimap
    scales with the map area it sits in instead of a fixed box, so it
    stays proportionate whether the map panel is a phone-sized pane or a
    full monitor."""
    if size is None:
        w = max(120, min(220, round(map_rect.w * 0.16)))
        h = max(72, min(140, round(map_rect.h * 0.20)))
    else:
        w, h = size
    box = pygame.Rect(map_rect.right - w - T.S * 2, map_rect.bottom - h - T.S * 2, w, h)
    pygame.draw.rect(surf, T.STEEL, box)
    pygame.draw.rect(surf, T.STEEL_LINE, box, 1)

    xs = [n["pos"][0] for n in nodes.values()]
    ys = [n["pos"][1] for n in nodes.values()]

    # padding proportional to the nodes' own spread -- a fixed pixel/unit
    # pad would swamp a tightly-clustered graph and barely show on a
    # spread-out one
    pad_x = max((max(xs) - min(xs)) * 0.15, 1.0)
    pad_y = max((max(ys) - min(ys)) * 0.15, 1.0)
    min_x, max_x = min(xs) - pad_x, max(xs) + pad_x
    min_y, max_y = min(ys) - pad_y, max(ys) + pad_y

    mz = min((w - 24) / (max_x - min_x), (h - 24) / (max_y - min_y))
    ox = box.centerx - (min_x + max_x) / 2 * mz
    oy = box.centery - (min_y + max_y) / 2 * mz

    def m(p):
        return (int(ox + p[0] * mz), int(oy + p[1] * mz))

    for a, b, _ in edges:
        pygame.draw.line(surf, T.STEEL_LINE, m(nodes[a]["pos"]), m(nodes[b]["pos"]), 1)
    for n in nodes.values():
        pygame.draw.circle(surf, T.TX_FAINT, m(n["pos"]), 2)

    # the current viewport rectangle
    p0 = cam.screen_to_world(map_rect.topleft)
    p1 = cam.screen_to_world(map_rect.bottomright)

    vw = (p1[0] - p0[0]) * mz
    vh = (p1[1] - p0[1]) * mz
    vr = pygame.Rect(0, 0, vw, vh)
    vr.center = m(cam.cam)

    clip = surf.get_clip()
    surf.set_clip(box)
    pygame.draw.rect(surf, T.BRASS, vr, 1)
    surf.set_clip(clip)

    return box, (ox, oy, mz)

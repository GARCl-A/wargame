"""Pan/zoom camera over a continuous world-space node graph -- zooms/pans
around a screen-space *center* instead of a fixed top-left, and with no
forced "fit the whole graph" step: it just centers on the nodes it's given
and lets the caller zoom/pan from there."""

import pygame


class MapCamera:

    def __init__(self, nodes, world_w=400.0, world_h=300.0,
                 min_zoom=1.5, max_zoom=10.0, initial_zoom=4.0):
        self.WORLD_W, self.WORLD_H = world_w, world_h
        self.MIN_ZOOM, self.MAX_ZOOM = min_zoom, max_zoom
        self.rect = pygame.Rect(0, 0, 1, 1)
        self.zoom = initial_zoom
        self.cam = [0.0, 0.0]
        self.touched = False                  # the player zoomed or panned: stop re-framing on resize
        self._fit_size = None
        self._center_on(nodes)

    def _center_on(self, nodes):
        xs = [n["pos"][0] for n in nodes.values()]
        ys = [n["pos"][1] for n in nodes.values()]
        self.cam = [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2]

    def set_rect(self, rect):
        self.rect = rect

    def autofit(self, nodes, pad, reserve_bottom=0, floor=0.0, radii=None):
        """Frame every node inside the rect (`pad` = (x, y) px kept clear for labels,
        `reserve_bottom` px kept clear for an overlay, `floor` the smallest zoom worth
        framing at: a window too small for it overflows instead of piling labels) -- once per rect size, and
        never after the player has taken the camera. `radii` (node -> world units) widens a
        node's box by the terrain drawn around it, so a big region is not cut at the edge."""
        if self.touched or self._fit_size == self.rect.size:
            return
        self._fit_size = self.rect.size
        r = radii or {}
        xs = [n["pos"][0] + d * r.get(k, 0) for k, n in nodes.items() for d in (-1, 1)]
        ys = [n["pos"][1] + d * r.get(k, 0) for k, n in nodes.items() for d in (-1, 1)]
        span_x, span_y = max(max(xs) - min(xs), 1e-6), max(max(ys) - min(ys), 1e-6)
        avail_w = max(1, self.rect.w - 2 * pad[0])
        avail_h = max(1, self.rect.h - 2 * pad[1] - reserve_bottom)
        self.zoom = max(floor, min(avail_w / span_x, avail_h / span_y))
        self.clamp()
        self.cam = [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2 + reserve_bottom / 2 / self.zoom]

    def clamp(self):
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self.zoom))

    def world_to_screen(self, p):
        return (self.rect.centerx + (p[0] - self.cam[0]) * self.zoom,
                self.rect.centery + (p[1] - self.cam[1]) * self.zoom)

    def screen_to_world(self, px):
        return ((px[0] - self.rect.centerx) / self.zoom + self.cam[0],
                (px[1] - self.rect.centery) / self.zoom + self.cam[1])

    def zoom_at(self, px, steps):
        if not self.rect.collidepoint(px):
            return
        self.touched = True
        anchor = self.screen_to_world(px)
        self.zoom *= (1.0 + steps * 0.15)
        self.clamp()
        self.cam[0] = anchor[0] - (px[0] - self.rect.centerx) / self.zoom
        self.cam[1] = anchor[1] - (px[1] - self.rect.centery) / self.zoom

    def pan_px(self, dx, dy):
        self.touched = True
        self.cam[0] -= dx / self.zoom
        self.cam[1] -= dy / self.zoom
        self.clamp()

    def recenter(self, wx, wy):
        """Jump the camera to world-space `(wx, wy)`, clamped in bounds --
        e.g. a minimap click."""
        self.touched = True
        self.cam = [wx, wy]
        self.clamp()

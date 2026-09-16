"""Pan/zoom camera over a continuous world-space node graph -- the
war-table's analogue of `map_screen.MapCamera`, but zoom/pan around a
screen-space *center* instead of a fixed top-left, and with no forced
"fit the whole graph" step: it just centers on the nodes it's given and
lets the caller zoom/pan from there."""

import pygame


class MapCamera:

    def __init__(self, nodes, world_w=400.0, world_h=300.0,
                 min_zoom=1.5, max_zoom=10.0, initial_zoom=4.0):
        self.WORLD_W, self.WORLD_H = world_w, world_h
        self.MIN_ZOOM, self.MAX_ZOOM = min_zoom, max_zoom
        self.rect = pygame.Rect(0, 0, 1, 1)
        self.zoom = initial_zoom
        self.cam = [0.0, 0.0]
        self._center_on(nodes)

    def _center_on(self, nodes):
        xs = [n["pos"][0] for n in nodes.values()]
        ys = [n["pos"][1] for n in nodes.values()]
        self.cam = [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2]

    def set_rect(self, rect):
        self.rect = rect

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
        anchor = self.screen_to_world(px)
        self.zoom *= (1.0 + steps * 0.15)
        self.clamp()
        self.cam[0] = anchor[0] - (px[0] - self.rect.centerx) / self.zoom
        self.cam[1] = anchor[1] - (px[1] - self.rect.centery) / self.zoom

    def pan_px(self, dx, dy):
        self.cam[0] -= dx / self.zoom
        self.cam[1] -= dy / self.zoom
        self.clamp()

    def recenter(self, wx, wy):
        """Jump the camera to world-space `(wx, wy)`, clamped in bounds --
        e.g. a minimap click."""
        self.cam = [wx, wy]
        self.clamp()

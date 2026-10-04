"""The battle board's look: palette, camera and screen layout.

The board renderer (`battle_screen`, `battle_fx`, `lighting`, the map editor)
draws a dark playfield with its own colour roles -- floor, walls, light,
movement/attack highlights -- that the war-table `T` palette has no use for.
Fixed values: nothing here changes at runtime (the banner colour lives in
`banner.py`).

- `battle_layout(size)` docks the action panel and log to the window and leaves
  the rest to the board viewport.
- `BoardView` maps the grid onto a pan/zoom pixel viewport.
"""

import math

import pygame

# --- colours --------------------------------------------------------------- #
PLAYER_C  = (94, 156, 214)
ENEMY_C   = (214, 103, 92)
NEUTRAL_C = (176, 170, 154)

OK        = (111, 191, 115)
WARN      = (224, 149, 75)
DANGER    = (214, 103, 92)
INK_FAINT = (156, 162, 174)

NIGHT     = (4, 5, 12)
TORCH_C   = (240, 150, 55)
LIGHT_C   = (250, 225, 150)
OBJ_C     = (205, 180, 95)
WALL_FILL = (74, 78, 92)
WALL_HI   = (110, 116, 132)
WALL_LO   = (18, 19, 26)
FLOOR_A   = (44, 48, 56)               # the two checker tones
FLOOR_B   = (39, 43, 51)

# tactical overlay
MOVE_HL   = (78, 150, 96)
ATK_HL    = ENEMY_C
THROW_HL  = WARN
DEMO_HL   = (176, 116, 208)
PATH_PREV = (245, 232, 150)
PATH_DONE = (108, 138, 112)

# --- layout ---------------------------------------------------------------- #
TILE = 48                             # default board zoom; the view picks its own tile size to fit
MIN_TILE, MAX_TILE = 18, 56           # zoom range of the camera
MARGIN = 16
GAP = 12
INIT_H = 46                           # initiative strip above the grid
PANEL_W = 396
LOG_H = 150


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
    board_top = init.bottom + GAP
    board = pygame.Rect(MARGIN, board_top, left_w,
                        max(1, log.y - GAP - board_top))
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

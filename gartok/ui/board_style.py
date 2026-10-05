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

from .tokens import T

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

# terrain and props
WATER_C      = (74, 128, 174)
ROPE_C       = (198, 160, 104)
WALL_SHADOW  = (0, 0, 0, 110)
PROP_EDGE    = (25, 22, 12)
BADGE_INK    = (20, 18, 8)              # text on a filled badge (cost, death clock)
HP_TRACK     = (30, 30, 36)
CREATURE_INK = (25, 25, 25)
TORCH_BASE   = (58, 52, 46)
CHEST_WOOD   = (139, 90, 43)
CHEST_TRIM   = (218, 165, 32)
RELIC_C      = (120, 200, 255)
RELIC_RIM    = (255, 255, 255)
DISK_HALO    = (80, 220, 240, 80)
DISK_CORE    = (30, 160, 200, 180)
DISK_RIM     = (180, 245, 255)
TRAP_C       = (160, 50, 40)
TRAP_STEEL   = (70, 70, 75)
TRAP_IRON    = (35, 35, 40)
TRAP_PLATE   = (130, 60, 50)
TRAP_PLATE_D = (40, 20, 20)
TRAP_TEETH   = (200, 205, 215)
TRAP_PEG     = (90, 60, 35)
TRAP_WIRE    = (210, 210, 220)
WEB_C        = (225, 225, 235)
TRAP_BELL    = (220, 175, 45)
TRAP_BELL_D  = (50, 40, 15)
TRAP_CLAPPER = (60, 50, 20)
LOG_HURT     = (206, 150, 140)


def aim_color(kind):
    """The highlight for an aimed action of `kind` ("heal", "demo", "attack",
    "move", "spell", "throw") -- shared by the board overlay and the armed
    action button so both read as the same intent."""
    return {"heal": OK, "demo": DEMO_HL, "attack": ATK_HL, "move": MOVE_HL,
            "spell": T.BRASS, "throw": THROW_HL}.get(kind, T.BRASS)

# --- layout ---------------------------------------------------------------- #
TILE = 48                             # default board zoom; the view picks its own tile size to fit
MIN_TILE, MAX_TILE = 14, 160          # zoom range of the camera
ZOOM_STEP = 1.15                      # tile size multiplier per wheel notch
OVERSCROLL = 0.5                      # fraction of the viewport the camera may pan past the board edge
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
    view, up to `OVERSCROLL` of a viewport past its edge. All board<->screen
    conversion goes through `cell_rect` / `cell_at`."""

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
                slack = view * OVERSCROLL / self.tile
                self.cam[i] = max(-slack, min(self.cam[i], (span - view) / self.tile + slack))

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
        new = round(self.tile * ZOOM_STEP ** steps)
        if new == self.tile:
            new += 1 if steps > 0 else -1
        new = max(MIN_TILE, min(MAX_TILE, new))
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

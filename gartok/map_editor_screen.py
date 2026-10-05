"""Scenario creator: lay out a battle map and its props.

A sandbox reached from the editor hub. Paint the 16x12 board directly -- walls,
torches, the player and enemy deployment zones -- flip the lighting flags, and
SAVE writes it to `maps/<slug>.json` (`map_lib`), versioned in git like the NPC
library. `scenario.CustomScenario` turns a saved map back into a playable battle.

The NPC START tool is different: click a cell and pick a character from the NPC
library (`npc_lib`) to stand there -- that is how you pin Adelio (or any
hand-built opponent) to a spot. The cell shows the NPC's initial; right-click
clears it. `map_lib.npc_units` loads those NPCs back when a battle is built.

The grid previews the lighting: with a dark map, everything outside a torch's
reach (walls block it) is dimmed, so you see what the squad will actually see.

Left-drag paints with the active tool; right-drag (or the ERASE tool) rubs cells
out. CLEAR wipes the board. Nothing is procedural -- a fresh board is empty and
every cell is placed by hand. Loading a library entry brings it back to edit;
NEW starts blank. `on_back` returns to the editor hub.
"""

from collections import deque

import pygame

from . import data, items, map_lib, npc_lib
from .board import COLS, ROWS, Board, grid_distance
from .screen import Screen
from .ui.board_style import (
    ENEMY_C,
    FLOOR_A,
    FLOOR_B,
    NIGHT,
    PLAYER_C,
    TORCH_C,
    WALL_FILL,
    WALL_HI,
)
from .ui.primitives import (
    caps,
    draw_button,
    ellipsize,
    section,
    set_pointer,
    text,
)
from .ui.tokens import T

_MAX_NAME = 28

_NPC_C = (168, 124, 214)                  # named-NPC deploy zone (violet)
_PIT_C = (58, 56, 74)                     # a pit cell (recessed dark)
_ROPE_C = (198, 160, 104)                 # a rope over the pit edge (tan)
_WATER_C = (74, 128, 174)                 # a flooded cell (blue)
_TRAP_C = (205, 115, 65)                 # trap marker (rust orange)
_SECRET_WALL_C = (195, 175, 100)          # secret wall (brass tone)
_ESCAPE_C = (50, 170, 160)                # escape zone (cyan/teal)
_CHEST_C = (165, 110, 55)                 # container/chest (wood)
_RELIC_C = (185, 95, 205)                 # ground item / relic (magenta)

_MAX_DEPTH = 6
_MIN_SIZE, _MAX_SIZE = 8, 48              # grid dimensions the editor allows

_TOOLS = [("wall", "WALL"), ("secret_wall", "SECRET WALL"),
          ("torch", "TORCH"), ("trap", "TRAP"),
          ("chest", "CONTAINER"), ("item", "ITEM"),
          ("pit", "PIT"), ("water", "WATER"),
          ("rope", "ROPE"), ("escape", "ESCAPE"),
          ("player", "PLAYER"), ("enemy", "ENEMY"),
          ("npc", "NPC"), ("erase", "ERASE")]

_LAYER_C = {"wall": WALL_HI, "secret_wall": _SECRET_WALL_C,
            "torch": TORCH_C, "trap": _TRAP_C, "chest": _CHEST_C,
            "item": _RELIC_C, "pit": (120, 116, 150),
            "water": _WATER_C, "rope": _ROPE_C, "escape": _ESCAPE_C,
            "player": PLAYER_C, "enemy": ENEMY_C, "npc": _NPC_C}

_ITEM_CATALOG = sorted(set(
    list(items.all_items().keys()) +
    [data.CODEX_ITEM, "50 Copper", "100 Copper", "Scroll of Sleep", "Scroll of Light", "Amethyst"]
))


class MapEditorScreen(Screen):
    native = True

    def __init__(self, fonts, on_back):
        super().__init__()
        self.F = fonts
        self.on_back = on_back
        self.hits = []                        # [(rect, action)] rebuilt each frame
        self.tool = "wall"
        self.pit_depth = 1                    # PIT tool paints holes this many levels deep
        self.painting = None                  # "add" | "del" while a drag is live
        self.edit_name = False
        self.name_buf = ""
        self.notice = None                    # (text, colour)
        self.confirm_delete = None            # slug awaiting a delete confirm
        self.library = []
        self.npc_rows = []                    # npc_lib.list_npcs() for the picker
        self.picking = None                   # (kind, cell) or None
        self.picker_hits = []
        self.picker_scroll = 0
        self._picker_box = pygame.Rect(0, 0, 0, 0)
        self._grid = (0, 0, 0)                # (x, y, cell) written each frame
        self._light_sig = None                # (walls, torches) the dark set was built for
        self._dark = frozenset()              # cells no torch reaches, when the map is dark
        self._load(map_lib.new_map())

    # ------------------------------------------------------------------ #
    def _load(self, m, slug=None):
        cs = lambda k: {tuple(c) for c in m.get(k, [])}
        self.name = m.get("name", "Untitled")
        self.cols = int(m.get("cols") or COLS)
        self.rows = int(m.get("rows") or ROWS)
        self.walls = cs("walls")
        self.secret_walls = cs("secret_walls")
        self.walls.update(self.secret_walls)
        self.torches = cs("torches")
        self.zone_p = cs("deploy_player")
        self.zone_e = cs("deploy_enemy")
        self.elev = {(e[0], e[1]): e[2] for e in m.get("elevation", []) if len(e) >= 3}
        self.ropes = cs("ropes")
        self.water = cs("water")
        self.npc_at = {(e[0], e[1]): e[2] for e in m.get("deploy_npc", []) if len(e) >= 3}
        self.traps = {(e[0], e[1]): e[2] for e in m.get("traps", []) if len(e) >= 3}
        self.escape_cells = cs("escape_cells")
        self.chests = {(e[0], e[1]): list(e[2]) for e in m.get("chests", []) if len(e) >= 3}
        self.relics = {(e[0], e[1]): e[2] for e in m.get("relics", []) if len(e) >= 3}
        self.ambient = bool(m.get("ambient_light"))
        self.outdoor = bool(m.get("outdoor"))
        self.slug = slug
        self.edit_name = False
        self.picking = None
        self.picker_scroll = 0
        self.confirm_delete = None
        self.notice = None
        self._refresh_library()

    def _refresh_library(self):
        self.library = map_lib.list_maps()
        self.npc_rows = npc_lib.list_npcs()

    def _npc_name(self, slug):
        return next((r["name"] for r in self.npc_rows if r["slug"] == slug), slug)

    def _to_dict(self):
        srt = lambda s: sorted([list(c) for c in s])
        return {"name": self.name, "cols": self.cols, "rows": self.rows,
                "walls": srt(self.walls),
                "secret_walls": srt(self.secret_walls),
                "torches": srt(self.torches),
                "deploy_player": srt(self.zone_p), "deploy_enemy": srt(self.zone_e),
                "deploy_npc": sorted([x, y, slug] for (x, y), slug in self.npc_at.items()),
                "elevation": sorted([x, y, z] for (x, y), z in self.elev.items()),
                "ropes": srt(self.ropes), "water": srt(self.water),
                "traps": sorted([x, y, t] for (x, y), t in self.traps.items()),
                "escape_cells": srt(self.escape_cells),
                "chests": sorted([x, y, list(itms)] for (x, y), itms in self.chests.items()),
                "relics": sorted([x, y, r] for (x, y), r in self.relics.items()),
                "ambient_light": self.ambient and not self.outdoor,
                "outdoor": self.outdoor}

    def _save(self):
        self.slug = map_lib.save_map(self._to_dict(), self.slug)
        self._refresh_library()
        if self._sealed():
            self.notice = ("saved -- but walls seal the two sides off", T.BRASS)
        else:
            self.notice = (f"saved  ·  maps/{self.slug}.json", T.GREEN)

    # ------------------------------------------------------------------ #
    def _sealed(self):
        """Can a walker cross from the player side to the enemy side? A map that
        walls one off would drop units with no path to the fight."""
        walls = self.walls
        board = self._preview_board()
        enemy = self.zone_e | set(self.npc_at)
        starts = {c for c in (self.zone_p or {(0, y) for y in range(self.rows)})
                  if c not in walls}
        goals = {c for c in (enemy or {(self.cols - 1, y) for y in range(self.rows)})
                  if c not in walls}
        if not starts or not goals:
            return True
        seen = set(starts)
        q = deque(starts)
        while q:
            cur = q.popleft()
            if cur in goals:
                return False
            for nb in board.neighbors(cur):
                if nb not in seen and nb not in walls:
                    seen.add(nb)
                    q.append(nb)
        return True

    # ------------------------------------------------------------------ #
    def _cell_at(self, pos):
        gx, gy, cs = self._grid
        if cs <= 0 or pos[0] < gx or pos[1] < gy:
            return None
        x, y = (pos[0] - gx) // cs, (pos[1] - gy) // cs
        if 0 <= x < self.cols and 0 <= y < self.rows:
            return (int(x), int(y))
        return None

    def _preview_board(self):
        return Board(walls=self.walls, elevation=dict(self.elev), ropes=self.ropes,
                     water=self.water, cols=self.cols, rows=self.rows)

    def _clamp_to_grid(self):
        """After a resize: drop everything that fell outside the new bounds."""
        inb = lambda c: 0 <= c[0] < self.cols and 0 <= c[1] < self.rows
        for s in (self.walls, self.secret_walls, self.torches, self.zone_p, self.zone_e,
                  self.ropes, self.water, self.escape_cells):
            s.difference_update({c for c in s if not inb(c)})
        self.elev = {c: z for c, z in self.elev.items() if inb(c)}
        self.npc_at = {c: v for c, v in self.npc_at.items() if inb(c)}
        self.traps = {c: v for c, v in self.traps.items() if inb(c)}
        self.chests = {c: v for c, v in self.chests.items() if inb(c)}
        self.relics = {c: v for c, v in self.relics.items() if inb(c)}
        self._light_sig = None

    def _apply(self, cell, mode):
        had_rope = cell in self.ropes
        had_water = cell in self.water
        had_elev = self.elev.get(cell)
        for s in (self.walls, self.secret_walls, self.torches, self.zone_p, self.zone_e,
                  self.ropes, self.water, self.escape_cells):
            s.discard(cell)                    # surface layers are mutually exclusive
        self.npc_at.pop(cell, None)
        self.elev.pop(cell, None)
        self.traps.pop(cell, None)
        self.chests.pop(cell, None)
        self.relics.pop(cell, None)
        if mode != "add":
            return
        if self.tool in ("wall", "torch", "player", "enemy", "escape"):
            {"wall": self.walls, "torch": self.torches,
             "player": self.zone_p, "enemy": self.zone_e,
             "escape": self.escape_cells}[self.tool].add(cell)
        elif self.tool == "secret_wall":
            self.walls.add(cell)
            self.secret_walls.add(cell)
        elif self.tool == "pit":
            self.elev[cell] = -self.pit_depth
            if had_rope:
                self.ropes.add(cell)          # deepening a roped pit keeps the rope
            if had_water:
                self.water.add(cell)          # a flooded pit stays flooded
        elif self.tool == "water":
            self.water.add(cell)              # flat cell -> puddle; over a pit -> deep water
            if had_elev:
                self.elev[cell] = had_elev
            if had_rope:
                self.ropes.add(cell)

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def handle_event(self, event):
        if self.edit_name and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                self._commit_name()
            elif event.key == pygame.K_BACKSPACE:
                self.name_buf = self.name_buf[:-1]
            elif event.unicode.isprintable() and len(self.name_buf) < _MAX_NAME:
                self.name_buf += event.unicode
            return

        if self.picking is not None:
            if event.type == pygame.MOUSEWHEEL:
                self.picker_scroll = max(0, self.picker_scroll - event.y * 30)
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 4:
                    self.picker_scroll = max(0, self.picker_scroll - 30)
                elif event.button == 5:
                    self.picker_scroll += 30
                elif event.button == 1:
                    self._picker_click(event.pos)
                else:
                    self.picking = None
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            cell = self._cell_at(event.pos)
            if cell is not None:
                if self.edit_name:
                    self._commit_name()
                self.notice = None
                if self.tool == "npc":            # click-to-assign, not a drag
                    if event.button == 3:
                        self.npc_at.pop(cell, None)
                    elif not self.npc_rows:
                        self.notice = ("no NPCs yet -- build one in the character creator",
                                       T.BRASS)
                    else:
                        self.picking = ("npc", cell)
                        self.picker_scroll = 0
                    return
                if self.tool == "chest":          # click to manage container items
                    if event.button == 3:
                        self.chests.pop(cell, None)
                    else:
                        if cell not in self.chests:
                            self.chests[cell] = []
                        for s in (self.walls, self.secret_walls, self.torches, self.zone_p,
                                  self.zone_e, self.ropes, self.water, self.escape_cells):
                            s.discard(cell)
                        self.npc_at.pop(cell, None)
                        self.relics.pop(cell, None)
                        self.picking = ("chest", cell)
                        self.picker_scroll = 0
                    return
                if self.tool == "item":           # click to select ground relic/item
                    if event.button == 3:
                        self.relics.pop(cell, None)
                    else:
                        for s in (self.walls, self.secret_walls, self.torches, self.zone_p,
                                  self.zone_e, self.ropes, self.water, self.escape_cells):
                            s.discard(cell)
                        self.npc_at.pop(cell, None)
                        self.chests.pop(cell, None)
                        self.picking = ("item", cell)
                        self.picker_scroll = 0
                    return
                if self.tool == "trap":           # click to place/toggle, not a drag
                    if event.button == 3:
                        self.traps.pop(cell, None)
                    else:
                        cur = self.traps.get(cell)
                        self.traps[cell] = "alarm trap" if cur == "bear trap" else "bear trap"
                        for s in (self.walls, self.secret_walls, self.torches, self.zone_p,
                                  self.zone_e, self.ropes, self.water, self.escape_cells):
                            s.discard(cell)
                        self.npc_at.pop(cell, None)
                        self.elev.pop(cell, None)
                        self.chests.pop(cell, None)
                        self.relics.pop(cell, None)
                    return
                if self.tool == "rope":           # toggle on a pit cell, not a drag
                    if event.button == 3:
                        self.ropes.discard(cell)
                    elif cell in self.elev:
                        self.ropes.symmetric_difference_update({cell})
                    else:
                        self.notice = ("rope needs a pit cell under it", T.BRASS)
                    return
                self.painting = "del" if event.button == 3 else "add"
                self._apply(cell, self.painting)
                return
            if event.button == 1:
                self._click(event.pos)
            return
        if event.type == pygame.MOUSEMOTION and self.painting:
            cell = self._cell_at(event.pos)
            if cell is not None:
                self._apply(cell, self.painting)
            return
        if event.type == pygame.MOUSEBUTTONUP:
            self.painting = None

    def _commit_name(self):
        self.name = self.name_buf.strip() or "Untitled"
        self.edit_name = False

    def _picker_click(self, px):
        if not self._picker_box.collidepoint(px):
            self.picking = None
            return
        if isinstance(self.picking, tuple) and len(self.picking) == 2 and isinstance(self.picking[0], int):
            kind, cell = "npc", self.picking
        else:
            kind, cell = self.picking[0], self.picking[1]

        for rect, action in self.picker_hits:
            if rect.collidepoint(px):
                act_type = action[0]
                if act_type == "set_npc":
                    self.npc_at[cell] = action[1]
                    self.picking = None
                elif act_type == "set_relic":
                    self.relics[cell] = action[1]
                    self.picking = None
                elif act_type == "open_chest_add":
                    self.picking = ("chest_add", cell)
                    self.picker_scroll = 0
                elif act_type == "chest_remove_item":
                    idx = action[1]
                    cur = self.chests.setdefault(cell, [])
                    if 0 <= idx < len(cur):
                        cur.pop(idx)
                elif act_type == "chest_add_item":
                    self.chests.setdefault(cell, []).append(action[1])
                    self.picking = ("chest", cell)
                    self.picker_scroll = 0
                elif act_type == "chest_back":
                    self.picking = ("chest", cell)
                    self.picker_scroll = 0
                elif act_type == "close":
                    self.picking = None
                return

    def _click(self, px):
        if self.edit_name:
            self._commit_name()
        for rect, action in self.hits:
            if rect.collidepoint(px):
                self._do(action)
                return

    def _do(self, action):
        kind = action[0]
        if kind == "back":
            self.on_back()
        elif kind == "save":
            self._save()
        elif kind == "new":
            self._load(map_lib.new_map())
        elif kind == "tool":
            self.tool = action[1]
        elif kind == "name":
            self.edit_name = True
            self.name_buf = "" if self.name == "Untitled" else self.name
        elif kind == "ambient":
            if not self.outdoor:              # OUTDOOR forces ambient light on
                self.ambient = not self.ambient
        elif kind == "outdoor":
            self.outdoor = not self.outdoor
        elif kind == "clear":
            self.walls, self.secret_walls, self.torches = set(), set(), set()
            self.zone_p, self.zone_e, self.npc_at = set(), set(), {}
            self.elev, self.ropes, self.water, self.escape_cells = {}, set(), set(), set()
            self.traps, self.chests, self.relics = {}, {}, {}
            self._light_sig = None
            self.notice = None
        elif kind == "depth":
            self.pit_depth = max(1, min(_MAX_DEPTH, self.pit_depth + action[1]))
        elif kind == "size":
            axis, delta = action[1]
            if axis == "w":
                self.cols = max(_MIN_SIZE, min(_MAX_SIZE, self.cols + delta))
            else:
                self.rows = max(_MIN_SIZE, min(_MAX_SIZE, self.rows + delta))
            self._clamp_to_grid()
        elif kind == "load":
            self._load(map_lib.load_map(action[1]), slug=action[1])
        elif kind == "ask_delete":
            self.confirm_delete = action[1]
        elif kind == "delete":
            map_lib.delete_map(action[1])
            if self.slug == action[1]:
                self.slug = None
            self.confirm_delete = None
            self._refresh_library()
        elif kind == "delete_no":
            self.confirm_delete = None

    # ------------------------------------------------------------------ #
    # drawing                                                            #
    # ------------------------------------------------------------------ #
    def _btn(self, screen, rect, label, *, on=False, danger=False, font=None):
        draw_button(screen, self.F, rect, label, primary=on, danger=danger and on,
                    mpos=self.mouse, fnt=font)

    def draw(self, screen):
        F = self.F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.hits = []
        pad = T.S * 2 if W < 1500 else T.S * 3

        text(screen, F["titleb"], "SCENARIO CREATOR", (pad, pad - 2), T.TX)
        if self.notice:
            sub, scol = self.notice
        else:
            sub = f"editing  {self.slug}" if self.slug else "unsaved  ·  a blank board"
            scol = T.TX_MUTED
        text(screen, F["body_sm"], sub, (pad, pad + 28), scol)

        narrow = W < 980
        bw, bh = (84, 28) if narrow else (108, 30)
        bx = W - pad - bw
        for key, label in (("back", "BACK"), ("save", "SAVE"), ("new", "NEW")):
            r = pygame.Rect(bx, pad, bw, bh)
            self._btn(screen, r, label, font=F["microb"] if narrow else F["bodyb"])
            self.hits.append((r, (key,)))
            bx -= bw + T.S

        top = pad + 52
        gap = T.S * 2
        rcw = max(220, min(280, int(W * 0.30)))
        left_w = W - 2 * pad - rcw - gap
        self._draw_grid(screen, pygame.Rect(pad, top, left_w, H - top - pad))
        self._draw_panel(screen, pygame.Rect(W - pad - rcw, top, rcw, H - top - pad))
        if self.picking is not None:
            self._draw_picker(screen)

        set_pointer(any(r.collidepoint(self.mouse) for r, _ in self.hits)
                    or self.picking is not None
                    or self._cell_at(self.mouse) is not None)

    # ------------------------------------------------------------------ #
    def _draw_grid(self, screen, area):
        cols, rows = self.cols, self.rows
        cell = max(6, min(area.w // cols, (area.h - 40) // rows))  # 40px below for the hint
        gw, gh = cell * cols, cell * rows
        gx = area.x + (area.w - gw) // 2
        gy = area.y + max(0, (area.h - 40 - gh) // 2)
        self._grid = (gx, gy, cell)

        lit = self.ambient or self.outdoor
        for cy in range(rows):
            for cx in range(cols):
                tone = FLOOR_A if (cx + cy) & 1 else FLOOR_B
                screen.fill(tone, (gx + cx * cell, gy + cy * cell, cell, cell))

        for (cx, cy), z in self.elev.items():    # a pit: recessed dark, darker the deeper
            r = pygame.Rect(gx + cx * cell, gy + cy * cell, cell, cell)
            shade = min(1.0, -z / _MAX_DEPTH)
            screen.fill(_PIT_C, r)
            screen.fill(tuple(int(c * (1 - 0.55 * shade)) for c in _PIT_C),
                        r.inflate(-cell // 4, -cell // 4))

        for cx, cy in self.water:                # deep over a pit, a shallow puddle otherwise
            deep = self.elev.get((cx, cy), 0) < 0
            wl = pygame.Surface((cell, cell), pygame.SRCALPHA)
            wl.fill((*_WATER_C, 150 if deep else 90))
            screen.blit(wl, (gx + cx * cell, gy + cy * cell))

        if not lit:                              # dim the floor no torch reaches;
            self._sync_dark()                    # painted walls/zones stay crisp on top
            veil = pygame.Surface((cell, cell), pygame.SRCALPHA)
            veil.fill((*NIGHT, 175))
            for cx, cy in self._dark:
                screen.blit(veil, (gx + cx * cell, gy + cy * cell))

        zone_layer = pygame.Surface((gw, gh), pygame.SRCALPHA)
        for (cx, cy), col in ([(c, _LAYER_C["player"]) for c in self.zone_p]
                              + [(c, _LAYER_C["enemy"]) for c in self.zone_e]
                              + [(c, _LAYER_C["npc"]) for c in self.npc_at]):
            r = pygame.Rect(cx * cell, cy * cell, cell, cell)
            zone_layer.fill((*col, 110), r)
            pygame.draw.rect(zone_layer, (*col, 255), r, 2)
        screen.blit(zone_layer, (gx, gy))

        for (cx, cy), slug in self.npc_at.items():   # the NPC's initial on its cell
            initial = (self._npc_name(slug).strip() or "?")[0].upper()
            text(screen, self.F["bodyb"], initial,
                 (gx + cx * cell + cell // 2, gy + cy * cell + cell // 2), T.TX, center=True)

        for cx in range(cols + 1):
            x = gx + cx * cell
            pygame.draw.line(screen, T.STEEL_LINE, (x, gy), (x, gy + gh))
        for cy in range(rows + 1):
            y = gy + cy * cell
            pygame.draw.line(screen, T.STEEL_LINE, (gx, y), (gx + gw, y))

        for (cx, cy), z in self.elev.items():        # depth number in the pit
            text(screen, self.F["body_sm"], str(-z),
                 (gx + cx * cell + cell // 2, gy + cy * cell + cell // 2), T.TX_MUTED, center=True)
        for cx, cy in self.ropes:                    # rope hanging over the edge
            rx = gx + cx * cell + cell // 2
            pygame.draw.line(screen, _ROPE_C, (rx, gy + cy * cell + 2),
                             (rx, gy + (cy + 1) * cell - 2), max(2, cell // 9))
        for cx, cy in self.escape_cells:
            r = pygame.Rect(gx + cx * cell, gy + cy * cell, cell, cell)
            el = pygame.Surface((cell, cell), pygame.SRCALPHA)
            el.fill((*_ESCAPE_C, 80))
            screen.blit(el, (gx + cx * cell, gy + cy * cell))
            pygame.draw.rect(screen, _ESCAPE_C, r, 2)
            fnt = self.F["microb"] if cell < 24 else self.F["body_sm"]
            text(screen, fnt, "ESC", r.center, _ESCAPE_C, center=True)

        for wx, wy in self.walls:
            r = pygame.Rect(gx + wx * cell + 1, gy + wy * cell + 1, cell - 2, cell - 2)
            pygame.draw.rect(screen, WALL_FILL, r, border_radius=3)
            if (wx, wy) in self.secret_walls:
                pygame.draw.rect(screen, _SECRET_WALL_C, r, 2, border_radius=3)
                fnt = self.F["microb"] if cell < 22 else self.F["bodyb"]
                text(screen, fnt, "S", r.center, _SECRET_WALL_C, center=True)
            else:
                pygame.draw.rect(screen, WALL_HI, r, 1, border_radius=3)

        for tx, ty in self.torches:
            c = (gx + tx * cell + cell // 2, gy + ty * cell + cell // 2)
            glow = pygame.Surface((cell, cell), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*TORCH_C, 70), (cell // 2, cell // 2), cell // 2)
            screen.blit(glow, (gx + tx * cell, gy + ty * cell))
            pygame.draw.circle(screen, TORCH_C, c, max(2, cell // 6))

        for (cx, cy), itms in self.chests.items():
            r = pygame.Rect(gx + cx * cell + 2, gy + cy * cell + 2, cell - 4, cell - 4)
            pygame.draw.rect(screen, _CHEST_C, r, border_radius=3)
            pygame.draw.rect(screen, (220, 180, 100), r, 1, border_radius=3)
            fnt = self.F["microb"] if cell < 22 else self.F["bodyb"]
            lbl = f"{len(itms)}" if len(itms) > 0 else "C"
            text(screen, fnt, lbl, r.center, (255, 250, 230), center=True)

        for (cx, cy), item_name in self.relics.items():
            r = pygame.Rect(gx + cx * cell, gy + cy * cell, cell, cell)
            pts = [(r.centerx, r.y + 2), (r.right - 3, r.centery),
                   (r.centerx, r.bottom - 3), (r.x + 3, r.centery)]
            pygame.draw.polygon(screen, _RELIC_C, pts)
            pygame.draw.polygon(screen, T.STEEL_LINE, pts, 1)
            fnt = self.F["microb"] if cell < 22 else self.F["bodyb"]
            text(screen, fnt, "I", r.center, T.TX, center=True)

        for (cx, cy), ttype in self.traps.items():
            r = pygame.Rect(gx + cx * cell, gy + cy * cell, cell, cell)
            col = (205, 90, 60) if "alarm" in str(ttype).lower() else (145, 140, 135)
            pygame.draw.circle(screen, col, r.center, max(3, cell // 3))
            pygame.draw.circle(screen, T.STEEL_LINE, r.center, max(3, cell // 3), 1)
            initial = "A" if "alarm" in str(ttype).lower() else "B"
            fnt = self.F["microb"] if cell < 22 else self.F["bodyb"]
            text(screen, fnt, initial, r.center, T.TX, center=True)

        pygame.draw.rect(screen, T.STEEL_LINE, (gx, gy, gw, gh), 1)

        hov = self._cell_at(self.mouse)
        if hov is not None:
            hr = pygame.Rect(gx + hov[0] * cell, gy + hov[1] * cell, cell, cell)
            col = T.BLOOD if self.tool == "erase" else _LAYER_C.get(self.tool, T.BRASS)
            pygame.draw.rect(screen, col, hr, 2)

        size = f"{cols}x{rows}"
        if self.tool == "npc":
            hint = f"{size}  ·  click a cell to pick an NPC  ·  right-click clears"
        elif self.tool == "trap":
            hint = f"{size}  ·  click to toggle Bear Trap (B) / Alarm Trap (A)  ·  right-click clears"
        elif self.tool == "chest":
            hint = f"{size}  ·  click to manage container loot  ·  right-click removes"
        elif self.tool == "item":
            hint = f"{size}  ·  click to place an item or relic  ·  right-click removes"
        elif self.tool == "secret_wall":
            hint = f"{size}  ·  left-drag paints secret walls  ·  right-drag erases (revealed by Investigate)"
        elif self.tool == "escape":
            hint = f"{size}  ·  left-drag paints escape zone (retreat/win area)  ·  right-drag erases"
        elif self.tool == "pit":
            hint = (f"{size}  ·  left-drag digs pits {self.pit_depth} deep  ·  "
                    "right-drag fills  ·  DEPTH sets how deep")
        elif self.tool == "water":
            hint = (f"{size}  ·  left-drag floods (puddle = difficult terrain; "
                    "over a pit = deep water, swim across)  ·  right-drag drains")
        elif self.tool == "rope":
            hint = f"{size}  ·  click a pit cell to hang a rope (easier climb)  ·  right-click removes"
        else:
            lightnote = ("lit throughout" if lit
                         else f"dark outside torchlight  ·  {len(self.torches)} torch(es)")
            hint = f"{size}  ·  left-drag paints, right-drag erases  ·  " + lightnote

        if hov is not None:
            if hov in self.chests:
                itms = self.chests[hov]
                loot_str = ", ".join(itms) if itms else "empty"
                hint += f"  ·  chest @ {hov}: [{loot_str}]"
            elif hov in self.relics:
                hint += f"  ·  item @ {hov}: {self.relics[hov]}"
            elif hov in self.traps:
                hint += f"  ·  trap @ {hov}: {self.traps[hov]}"
            elif hov in self.npc_at:
                hint += f"  ·  NPC @ {hov}: {self._npc_name(self.npc_at[hov])}"

        text(screen, self.F["body_sm"], hint, (gx, gy + gh + T.S), T.TX_FAINT)
        if self._sealed():
            text(screen, self.F["body_sm"], "walls seal the two sides off -- no path across",
                 (gx, gy + gh + T.S + 16), T.BRASS)

    def _sync_dark(self):
        """Recompute `self._dark` -- cells beyond every torch's reach, walls
        blocking -- only when the walls or torches changed since last time."""
        sig = (frozenset(self.walls), frozenset(self.torches), self.cols, self.rows)
        if sig == self._light_sig:
            return
        self._light_sig = sig
        board = self._preview_board()
        reached = set()
        for t in self.torches:
            for cy in range(self.rows):
                for cx in range(self.cols):
                    p = (cx, cy)
                    if p not in reached and grid_distance(t, p) <= data.TORCH_RADIUS \
                            and board.los_clear(t, p):
                        reached.add(p)
        self._dark = frozenset((cx, cy) for cy in range(self.rows)
                                for cx in range(self.cols) if (cx, cy) not in reached)

    # ------------------------------------------------------------------ #
    def _draw_panel(self, screen, rect):
        F = self.F
        pygame.draw.rect(screen, T.STEEL, rect)
        pygame.draw.rect(screen, T.STEEL_LINE, rect, 1)
        pad = T.S * 2
        x = rect.x + pad
        w = rect.w - 2 * pad
        y = rect.y + pad

        y = section(screen, F, "TOOLS", x, y, w)
        col_w = (w - T.S) // 2
        rh = 24
        for i, (key, label) in enumerate(_TOOLS):
            col = i // 7
            row = i % 7
            bx = x + col * (col_w + T.S)
            by = y + row * (rh + 4)
            r = pygame.Rect(bx, by, col_w, rh)
            on = self.tool == key
            self._btn(screen, r, label, on=on, danger=(key == "erase"), font=F["microb"])
            swatch = pygame.Rect(r.right - 14, r.centery - 4, 8, 8)
            if key in _LAYER_C:
                pygame.draw.rect(screen, _LAYER_C[key], swatch, border_radius=2)
            self.hits.append((r, ("tool", key)))
        y += 7 * (rh + 4) + T.S // 2

        if self.tool in ("pit", "rope"):
            r = pygame.Rect(x, y, w, 24)
            self._stepper(screen, r, f"PIT DEPTH  {self.pit_depth}", "depth")
            y += 24 + T.S // 2

        r = pygame.Rect(x, y, w, 24)
        self._btn(screen, r, "CLEAR")
        self.hits.append((r, ("clear",)))
        y += 24 + pad

        y = section(screen, F, "SETTINGS", x, y, w)
        nr = pygame.Rect(x, y, w, 26)
        editing = self.edit_name
        hot = nr.collidepoint(self.mouse) or editing
        pygame.draw.rect(screen, T.STEEL_HI if hot else T.TABLE, nr)
        pygame.draw.rect(screen, T.BRASS if hot else T.STEEL_LINE, nr, 1)
        caps(screen, F["micro"], "NAME", (nr.x + T.S, nr.centery - 5), T.TX_FAINT)
        vx = nr.x + T.S + F["micro"].size("NAME")[0] + T.S
        shown = (self.name_buf + "|") if editing else self.name
        text(screen, F["body_sm"], ellipsize(shown, F["body_sm"], nr.right - T.S - vx),
             (vx, nr.centery - 6), T.TX)
        self.hits.append((nr, ("name",)))
        y += 26 + T.S // 2

        for axis, lbl, val in (("w", "WIDTH", self.cols), ("h", "HEIGHT", self.rows)):
            r = pygame.Rect(x, y, w, 24)
            self._stepper(screen, r, f"{lbl}  {val}", "size", axis)
            y += 24 + T.S // 2
        y += T.S // 2

        for key, label, val, note in (
                ("ambient", "AMBIENT LIGHT",
                 self.outdoor or self.ambient, self.outdoor),
                ("outdoor", "OUTDOOR (follows daylight)", self.outdoor, False)):
            r = pygame.Rect(x, y, w, 24)
            self._btn(screen, r, label + ("   ·  forced" if note else ""),
                       on=bool(val))
            self.hits.append((r, (key,)))
            y += 24 + T.S // 2
        y += T.S

        y = section(screen, F, "MAP LIBRARY", x, y, w)
        text(screen, F["micro"], "maps/", (rect.right - pad, y - 20), T.TX_FAINT, right=True)
        if not self.library:
            text(screen, F["body_sm"], "no saved maps yet — SAVE writes one here",
                 (x, y + 2), T.TX_FAINT)
        prev = screen.get_clip()
        screen.set_clip(rect.inflate(-T.S, -T.S))
        for row in self.library:
            if y > rect.bottom - 24:
                break
            rr = pygame.Rect(x, y, w, 26)
            cur = row["slug"] == self.slug
            hot = rr.collidepoint(self.mouse)
            pygame.draw.rect(screen, T.STEEL_HI if (hot or cur) else T.TABLE, rr)
            pygame.draw.rect(screen, T.BRASS if cur else T.STEEL_LINE, rr, 1)
            text(screen, F["body_sm"], ellipsize(row["name"], F["body_sm"], int(rr.w * 0.6)),
                 (rr.x + T.S, rr.y + 5), T.TX)
            meta = ("field" if row["outdoor"] else "indoor") + f" · {row['walls']}w"
            if self.confirm_delete == row["slug"]:
                yb = pygame.Rect(rr.right - 40, rr.y + 3, 18, 20)
                nb = pygame.Rect(rr.right - 20, rr.y + 3, 18, 20)
                self._btn(screen, yb, "y", on=True, danger=True)
                self._btn(screen, nb, "n")
                self.hits.append((yb, ("delete", row["slug"])))
                self.hits.append((nb, ("delete_no",)))
            else:
                text(screen, F["micro"], meta, (rr.right - 26, rr.y + 6), T.TX_FAINT,
                     right=True)
                self.hits.append((rr, ("load", row["slug"])))
                xb = pygame.Rect(rr.right - 20, rr.y + 3, 18, 20)
                h = xb.collidepoint(self.mouse)
                text(screen, F["bodyb"], "×", xb.center, T.BLOOD if h else T.TX_FAINT,
                     center=True)
                self.hits.append((xb, ("ask_delete", row["slug"])))
            y += 28
        screen.set_clip(prev)

    def _stepper(self, screen, r, label, kind, axis=None):
        """A labelled row with a [-] [+] pair on its right edge."""
        pygame.draw.rect(screen, T.TABLE, r)
        pygame.draw.rect(screen, T.STEEL_LINE, r, 1)
        caps(screen, self.F["micro"], label, (r.x + T.S, r.centery - 5), T.TX)
        for sym, d, side in (("-", -1, r.right - 46), ("+", 1, r.right - 24)):
            b = pygame.Rect(side, r.y + 3, 18, 18)
            self._btn(screen, b, sym, font=self.F["bodyb"])
            self.hits.append((b, (kind, d if axis is None else (axis, d))))

    # ------------------------------------------------------------------ #
    def _draw_picker(self, screen):
        """Modal manager for NPCs, ground items/relics, and containers/chests."""
        F = self.F
        W, H = screen.get_size()
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 190))
        screen.blit(veil, (0, 0))

        if isinstance(self.picking, tuple) and len(self.picking) == 2 and isinstance(self.picking[0], int):
            kind, cell = "npc", self.picking
        else:
            kind, cell = self.picking[0], self.picking[1]

        cx, cy = cell
        self.picker_hits = []
        pad = T.S * 2
        margin = T.S * 2
        pw = min(W - 2 * margin, 460)
        ph = min(H - 2 * margin, 460)
        box = pygame.Rect((W - pw) // 2, (H - ph) // 2, pw, ph)
        self._picker_box = box

        pygame.draw.rect(screen, T.STEEL, box)
        border_c = _LAYER_C.get(kind, T.BRASS)
        pygame.draw.rect(screen, border_c, box, 2)

        list_top = box.y + 54
        list_h = box.h - 54 - 46
        list_rect = pygame.Rect(box.x + pad, list_top, pw - 2 * pad, list_h)
        btn_y = box.bottom - 38

        if kind == "npc":
            text(screen, F["titleb"], f"NPC for cell {cx},{cy}", (box.x + pad, box.y + 12), T.TX)
            text(screen, F["micro"], "Select an NPC from the library to stand here",
                 (box.x + pad, box.y + 34), T.TX_FAINT)
            rows = self.npc_rows
            rh = 30
            total_h = len(rows) * rh
            max_scroll = max(0, total_h - list_h)
            self.picker_scroll = max(0, min(self.picker_scroll, max_scroll))

            prev = screen.get_clip()
            screen.set_clip(list_rect)
            cur = self.npc_at.get(cell)
            for i, row in enumerate(rows):
                ry = list_top + i * rh - self.picker_scroll
                if ry + rh < list_top or ry > list_top + list_h:
                    continue
                rr = pygame.Rect(list_rect.x, ry, list_rect.w, rh - 4)
                sel = row["slug"] == cur
                hov = rr.collidepoint(self.mouse)
                pygame.draw.rect(screen, T.STEEL_HI if (hov or sel) else T.TABLE, rr)
                pygame.draw.rect(screen, _NPC_C if sel else T.STEEL_LINE, rr, 1)
                text(screen, F["body_sm"], ellipsize(row["name"], F["body_sm"], int(rr.w * 0.5)),
                     (rr.x + T.S, rr.centery - 6), _NPC_C if sel else T.TX)
                meta = f"{row['race']} · {row['occupation']}"
                text(screen, F["micro"], ellipsize(meta, F["micro"], int(rr.w * 0.45)),
                     (rr.right - T.S, rr.centery - 5), T.TX_FAINT, right=True)
                self.picker_hits.append((rr, ("set_npc", row["slug"])))
            screen.set_clip(prev)

            cb = pygame.Rect(box.right - pad - 80, btn_y, 80, 26)
            self._btn(screen, cb, "CANCEL", font=F["microb"])
            self.picker_hits.append((cb, ("close", None)))

        elif kind == "item":
            text(screen, F["titleb"], f"Item for cell {cx},{cy}", (box.x + pad, box.y + 12), T.TX)
            text(screen, F["micro"], "Pick an item or relic to sit on the ground",
                 (box.x + pad, box.y + 34), T.TX_FAINT)
            rows = _ITEM_CATALOG
            rh = 28
            total_h = len(rows) * rh
            max_scroll = max(0, total_h - list_h)
            self.picker_scroll = max(0, min(self.picker_scroll, max_scroll))

            prev = screen.get_clip()
            screen.set_clip(list_rect)
            cur = self.relics.get(cell)
            for i, itm in enumerate(rows):
                ry = list_top + i * rh - self.picker_scroll
                if ry + rh < list_top or ry > list_top + list_h:
                    continue
                rr = pygame.Rect(list_rect.x, ry, list_rect.w, rh - 4)
                sel = itm == cur
                hov = rr.collidepoint(self.mouse)
                pygame.draw.rect(screen, T.STEEL_HI if (hov or sel) else T.TABLE, rr)
                pygame.draw.rect(screen, _RELIC_C if sel else T.STEEL_LINE, rr, 1)
                text(screen, F["body_sm"], ellipsize(itm, F["body_sm"], int(rr.w * 0.8)),
                     (rr.x + T.S, rr.centery - 6), _RELIC_C if sel else T.TX)
                self.picker_hits.append((rr, ("set_relic", itm)))
            screen.set_clip(prev)

            cb = pygame.Rect(box.right - pad - 80, btn_y, 80, 26)
            self._btn(screen, cb, "CANCEL", font=F["microb"])
            self.picker_hits.append((cb, ("close", None)))

        elif kind == "chest":
            items_list = self.chests.setdefault(cell, [])
            text(screen, F["titleb"], f"Container at {cx},{cy}", (box.x + pad, box.y + 12), T.TX)
            sub = f"{len(items_list)} item(s) inside this container"
            text(screen, F["micro"], sub, (box.x + pad, box.y + 34), T.TX_FAINT)

            prev = screen.get_clip()
            screen.set_clip(list_rect)
            if not items_list:
                text(screen, F["body_sm"], "This chest is currently empty.",
                     (list_rect.x + T.S, list_top + 16), T.TX_MUTED)
                text(screen, F["micro"], "Click [+ ADD ITEM] below to add loot.",
                     (list_rect.x + T.S, list_top + 40), T.TX_FAINT)
            else:
                rh = 30
                total_h = len(items_list) * rh
                max_scroll = max(0, total_h - list_h)
                self.picker_scroll = max(0, min(self.picker_scroll, max_scroll))

                for i, itm in enumerate(items_list):
                    ry = list_top + i * rh - self.picker_scroll
                    if ry + rh < list_top or ry > list_top + list_h:
                        continue
                    rr = pygame.Rect(list_rect.x, ry, list_rect.w, rh - 4)
                    pygame.draw.rect(screen, T.TABLE, rr)
                    pygame.draw.rect(screen, T.STEEL_LINE, rr, 1)
                    text(screen, F["body_sm"], ellipsize(str(itm), F["body_sm"], int(rr.w - 40)),
                         (rr.x + T.S, rr.centery - 6), T.TX)
                    xb = pygame.Rect(rr.right - 26, rr.y + 3, 20, 20)
                    h = xb.collidepoint(self.mouse)
                    text(screen, F["bodyb"], "×", xb.center, T.BLOOD if h else T.TX_FAINT, center=True)
                    self.picker_hits.append((xb, ("chest_remove_item", i)))
            screen.set_clip(prev)

            ab = pygame.Rect(box.x + pad, btn_y, 110, 26)
            self._btn(screen, ab, "+ ADD ITEM", font=F["microb"])
            self.picker_hits.append((ab, ("open_chest_add", None)))

            db = pygame.Rect(box.right - pad - 80, btn_y, 80, 26)
            self._btn(screen, db, "DONE", on=True, font=F["microb"])
            self.picker_hits.append((db, ("close", None)))

        elif kind == "chest_add":
            text(screen, F["titleb"], f"Add Item to Container {cx},{cy}", (box.x + pad, box.y + 12), T.TX)
            text(screen, F["micro"], "Click an item from the catalog to place inside",
                 (box.x + pad, box.y + 34), T.TX_FAINT)
            rows = _ITEM_CATALOG
            rh = 28
            total_h = len(rows) * rh
            max_scroll = max(0, total_h - list_h)
            self.picker_scroll = max(0, min(self.picker_scroll, max_scroll))

            prev = screen.get_clip()
            screen.set_clip(list_rect)
            for i, itm in enumerate(rows):
                ry = list_top + i * rh - self.picker_scroll
                if ry + rh < list_top or ry > list_top + list_h:
                    continue
                rr = pygame.Rect(list_rect.x, ry, list_rect.w, rh - 4)
                hov = rr.collidepoint(self.mouse)
                pygame.draw.rect(screen, T.STEEL_HI if hov else T.TABLE, rr)
                pygame.draw.rect(screen, _CHEST_C if hov else T.STEEL_LINE, rr, 1)
                text(screen, F["body_sm"], ellipsize(itm, F["body_sm"], int(rr.w * 0.8)),
                     (rr.x + T.S, rr.centery - 6), _CHEST_C if hov else T.TX)
                self.picker_hits.append((rr, ("chest_add_item", itm)))
            screen.set_clip(prev)

            bb = pygame.Rect(box.x + pad, btn_y, 80, 26)
            self._btn(screen, bb, "< BACK", font=F["microb"])
            self.picker_hits.append((bb, ("chest_back", None)))

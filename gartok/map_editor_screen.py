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

from . import data, map_lib, npc_lib
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

_MAX_DEPTH = 6
_MIN_SIZE, _MAX_SIZE = 8, 48              # grid dimensions the editor allows

_TOOLS = [("wall", "WALL"), ("torch", "TORCH"), ("pit", "PIT"), ("water", "WATER"),
          ("rope", "ROPE"), ("player", "PLAYER START"), ("enemy", "ENEMY START"),
          ("npc", "NPC START"), ("erase", "ERASE")]

_LAYER_C = {"wall": WALL_HI, "torch": TORCH_C, "pit": (120, 116, 150),
            "water": _WATER_C, "rope": _ROPE_C,
            "player": PLAYER_C, "enemy": ENEMY_C, "npc": _NPC_C}


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
        self.picking = None                   # cell awaiting an NPC choice, or None
        self.picker_hits = []
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
        self.torches = cs("torches")
        self.zone_p = cs("deploy_player")
        self.zone_e = cs("deploy_enemy")
        self.elev = {(e[0], e[1]): e[2] for e in m.get("elevation", []) if len(e) >= 3}
        self.ropes = cs("ropes")
        self.water = cs("water")
        self.npc_at = {(e[0], e[1]): e[2] for e in m.get("deploy_npc", []) if len(e) >= 3}
        self.ambient = bool(m.get("ambient_light"))
        self.outdoor = bool(m.get("outdoor"))
        self.slug = slug
        self.edit_name = False
        self.picking = None
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
                "walls": srt(self.walls), "torches": srt(self.torches),
                "deploy_player": srt(self.zone_p), "deploy_enemy": srt(self.zone_e),
                "deploy_npc": sorted([x, y, slug] for (x, y), slug in self.npc_at.items()),
                "elevation": sorted([x, y, z] for (x, y), z in self.elev.items()),
                "ropes": srt(self.ropes), "water": srt(self.water),
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
        for s in (self.walls, self.torches, self.zone_p, self.zone_e,
                  self.ropes, self.water):
            s.difference_update({c for c in s if not inb(c)})
        self.elev = {c: z for c, z in self.elev.items() if inb(c)}
        self.npc_at = {c: v for c, v in self.npc_at.items() if inb(c)}
        self._light_sig = None

    def _apply(self, cell, mode):
        had_rope = cell in self.ropes
        had_water = cell in self.water
        had_elev = self.elev.get(cell)
        for s in (self.walls, self.torches, self.zone_p, self.zone_e,
                  self.ropes, self.water):
            s.discard(cell)                    # surface layers are mutually exclusive
        self.npc_at.pop(cell, None)
        self.elev.pop(cell, None)
        if mode != "add":
            return
        if self.tool in ("wall", "torch", "player", "enemy"):
            {"wall": self.walls, "torch": self.torches,
             "player": self.zone_p, "enemy": self.zone_e}[self.tool].add(cell)
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
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
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
                        self.picking = cell
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
        for rect, slug in self.picker_hits:
            if rect.collidepoint(px):
                self.npc_at[self.picking] = slug
                self.picking = None
                return
        self.picking = None                   # clicked outside -> cancel

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
            self.walls, self.torches = set(), set()
            self.zone_p, self.zone_e, self.npc_at = set(), set(), {}
            self.elev, self.ropes, self.water = {}, set(), set()
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

        for wx, wy in self.walls:
            r = pygame.Rect(gx + wx * cell + 1, gy + wy * cell + 1, cell - 2, cell - 2)
            pygame.draw.rect(screen, WALL_FILL, r, border_radius=3)
            pygame.draw.rect(screen, WALL_HI, r, 1, border_radius=3)

        for tx, ty in self.torches:
            c = (gx + tx * cell + cell // 2, gy + ty * cell + cell // 2)
            glow = pygame.Surface((cell, cell), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*TORCH_C, 70), (cell // 2, cell // 2), cell // 2)
            screen.blit(glow, (gx + tx * cell, gy + ty * cell))
            pygame.draw.circle(screen, TORCH_C, c, max(2, cell // 6))

        pygame.draw.rect(screen, T.STEEL_LINE, (gx, gy, gw, gh), 1)

        hov = self._cell_at(self.mouse)
        if hov is not None:
            hr = pygame.Rect(gx + hov[0] * cell, gy + hov[1] * cell, cell, cell)
            col = T.BLOOD if self.tool == "erase" else _LAYER_C.get(self.tool, T.BRASS)
            pygame.draw.rect(screen, col, hr, 2)

        size = f"{cols}x{rows}"
        if self.tool == "npc":
            hint = f"{size}  ·  click a cell to pick an NPC  ·  right-click clears"
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
        for key, label in _TOOLS:
            r = pygame.Rect(x, y, w, 26)
            on = self.tool == key
            self._btn(screen, r, label, on=on, danger=(key == "erase"))
            swatch = pygame.Rect(r.right - 20, r.centery - 6, 12, 12)
            if key in _LAYER_C:
                pygame.draw.rect(screen, _LAYER_C[key], swatch, border_radius=2)
            self.hits.append((r, ("tool", key)))
            y += 26 + T.S // 2
        y += T.S // 2

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
        """Modal list of NPC-library characters -- pick one to stand on
        `self.picking`. Click a row to assign, anywhere else to cancel."""
        F = self.F
        W, H = screen.get_size()
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 190))
        screen.blit(veil, (0, 0))

        rows = self.npc_rows
        rh, pad = 30, T.S * 2
        margin = T.S * 2
        pw = min(W - 2 * margin, 420)
        ph = min(H - 2 * margin, 56 + rh * len(rows) + T.S * 2)
        box = pygame.Rect((W - pw) // 2, (H - ph) // 2, pw, ph)
        pygame.draw.rect(screen, T.STEEL, box)
        pygame.draw.rect(screen, _NPC_C, box, 2)
        cx, cy = self.picking
        text(screen, F["titleb"], f"NPC for cell {cx},{cy}", (box.x + pad, box.y + 12), T.TX)

        prev = screen.get_clip()
        screen.set_clip(box.inflate(-2, -2))
        self.picker_hits = []
        cur = self.npc_at.get(self.picking)
        for i, row in enumerate(rows):
            rr = pygame.Rect(box.x + pad, box.y + 46 + i * rh, pw - 2 * pad, rh - T.S // 2)
            if rr.bottom > box.bottom - T.S * 2:
                continue
            sel = row["slug"] == cur
            hov = rr.collidepoint(self.mouse)
            pygame.draw.rect(screen, T.STEEL_HI if (hov or sel) else T.TABLE, rr)
            pygame.draw.rect(screen, _NPC_C if sel else T.STEEL_LINE, rr, 1)
            text(screen, F["body_sm"], ellipsize(row["name"], F["body_sm"], int(rr.w * 0.5)),
                 (rr.x + T.S, rr.centery - 6), _NPC_C if sel else T.TX)
            meta = f"{row['race']} · {row['occupation']}"
            text(screen, F["micro"], ellipsize(meta, F["micro"], int(rr.w * 0.45)),
                 (rr.right - T.S, rr.centery - 5), T.TX_FAINT, right=True)
            self.picker_hits.append((rr, row["slug"]))
        screen.set_clip(prev)
        text(screen, F["body_sm"], "click outside to cancel",
             (box.x + pad, box.bottom - 20), T.TX_FAINT)

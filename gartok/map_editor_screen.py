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
from .board import COLS, ROWS, Board, grid_distance, neighbors
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, ENEMY_C, FLOOR_A, FLOOR_B, INK,
                    INK_DIM, INK_FAINT, LINE, LINE_SOFT, MARGIN, NIGHT, OK,
                    PLAYER_C, RADIUS, SP1, SP2, SP3, SP4, SP5, SURFACE_0,
                    SURFACE_1, SURFACE_2, SURFACE_3, TORCH_C, WALL_FILL,
                    WALL_HI, WARN, ellipsize, panel, section, set_pointer, text)

_MAX_NAME = 28

_NPC_C = (168, 124, 214)                  # named-NPC deploy zone (violet)
_PIT_C = (58, 56, 74)                     # a pit cell (recessed dark)
_ROPE_C = (198, 160, 104)                 # a rope over the pit edge (tan)

_MAX_DEPTH = 6

_TOOLS = [("wall", "WALL"), ("torch", "TORCH"), ("pit", "PIT"), ("rope", "ROPE"),
          ("player", "PLAYER START"), ("enemy", "ENEMY START"),
          ("npc", "NPC START"), ("erase", "ERASE")]

_LAYER_C = {"wall": WALL_HI, "torch": TORCH_C, "pit": (120, 116, 150), "rope": _ROPE_C,
            "player": PLAYER_C, "enemy": ENEMY_C, "npc": _NPC_C}


class MapEditorScreen(Screen):
    native = True

    def __init__(self, fonts, on_back):
        super().__init__()
        self.fonts = fonts
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
        self.walls = cs("walls")
        self.torches = cs("torches")
        self.zone_p = cs("deploy_player")
        self.zone_e = cs("deploy_enemy")
        self.elev = {(e[0], e[1]): e[2] for e in m.get("elevation", []) if len(e) >= 3}
        self.ropes = cs("ropes")
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
        return {"name": self.name, "cols": COLS, "rows": ROWS,
                "walls": srt(self.walls), "torches": srt(self.torches),
                "deploy_player": srt(self.zone_p), "deploy_enemy": srt(self.zone_e),
                "deploy_npc": sorted([x, y, slug] for (x, y), slug in self.npc_at.items()),
                "elevation": sorted([x, y, z] for (x, y), z in self.elev.items()),
                "ropes": srt(self.ropes),
                "ambient_light": self.ambient and not self.outdoor,
                "outdoor": self.outdoor}

    def _save(self):
        self.slug = map_lib.save_map(self._to_dict(), self.slug)
        self._refresh_library()
        if self._sealed():
            self.notice = ("saved -- but walls seal the two sides off", WARN)
        else:
            self.notice = (f"saved  ·  maps/{self.slug}.json", OK)

    # ------------------------------------------------------------------ #
    def _sealed(self):
        """Can a walker cross from the player side to the enemy side? A map that
        walls one off would drop units with no path to the fight."""
        walls = self.walls
        enemy = self.zone_e | set(self.npc_at)
        starts = {c for c in (self.zone_p or {(0, y) for y in range(ROWS)})
                  if c not in walls}
        goals = {c for c in (enemy or {(COLS - 1, y) for y in range(ROWS)})
                 if c not in walls}
        if not starts or not goals:
            return True
        seen = set(starts)
        q = deque(starts)
        while q:
            cur = q.popleft()
            if cur in goals:
                return False
            for nb in neighbors(cur):
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
        if 0 <= x < COLS and 0 <= y < ROWS:
            return (int(x), int(y))
        return None

    def _apply(self, cell, mode):
        had_rope = cell in self.ropes
        for s in (self.walls, self.torches, self.zone_p, self.zone_e, self.ropes):
            s.discard(cell)                    # a cell belongs to one layer at most
        self.npc_at.pop(cell, None)
        self.elev.pop(cell, None)
        if mode == "add" and self.tool in ("wall", "torch", "player", "enemy"):
            {"wall": self.walls, "torch": self.torches,
             "player": self.zone_p, "enemy": self.zone_e}[self.tool].add(cell)
        elif mode == "add" and self.tool == "pit":
            self.elev[cell] = -self.pit_depth
            if had_rope:
                self.ropes.add(cell)          # deepening a roped pit keeps the rope

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
                                       WARN)
                    else:
                        self.picking = cell
                    return
                if self.tool == "rope":           # toggle on a pit cell, not a drag
                    if event.button == 3:
                        self.ropes.discard(cell)
                    elif cell in self.elev:
                        self.ropes.symmetric_difference_update({cell})
                    else:
                        self.notice = ("rope needs a pit cell under it", WARN)
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
            self.elev, self.ropes = {}, set()
            self.notice = None
        elif kind == "depth":
            self.pit_depth = max(1, min(_MAX_DEPTH, self.pit_depth + action[1]))
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
        hot = rect.collidepoint(self.mouse)
        edge = DANGER if danger else ACCENT
        panel(screen, rect, fill=edge if on else (SURFACE_3 if hot else SURFACE_2),
              border=edge if (on or hot) else LINE_SOFT, width=1, radius=4)
        col = ACCENT_INK if on else (DANGER if danger else (ACCENT if hot else INK_DIM))
        text(screen, label, font or self.fonts.label, col, rect.center, center=True)

    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        screen.fill(SURFACE_0)
        self.hits = []
        pad = MARGIN if W < 1500 else SP5

        text(screen, "SCENARIO CREATOR", f.title, INK, (pad, pad - 2))
        if self.notice:
            sub, scol = self.notice
        else:
            sub = f"editing  {self.slug}" if self.slug else "unsaved  ·  a blank board"
            scol = INK_DIM
        text(screen, sub, f.body_sm, scol, (pad, pad + 28))

        narrow = W < 980
        bw, bh = (84, 28) if narrow else (108, 30)
        bx = W - pad - bw
        for key, label in (("back", "BACK"), ("save", "SAVE"), ("new", "NEW")):
            r = pygame.Rect(bx, pad, bw, bh)
            self._btn(screen, r, label, font=f.label if narrow else f.body_bd)
            self.hits.append((r, (key,)))
            bx -= bw + SP2

        top = pad + 52
        gap = SP4
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
        cell = max(6, min(area.w // COLS, (area.h - 40) // ROWS))  # 40px below for the hint
        gw, gh = cell * COLS, cell * ROWS
        gx = area.x + (area.w - gw) // 2
        gy = area.y + max(0, (area.h - 40 - gh) // 2)
        self._grid = (gx, gy, cell)

        lit = self.ambient or self.outdoor
        for cy in range(ROWS):
            for cx in range(COLS):
                tone = FLOOR_A if (cx + cy) & 1 else FLOOR_B
                screen.fill(tone, (gx + cx * cell, gy + cy * cell, cell, cell))

        for (cx, cy), z in self.elev.items():    # a pit: recessed dark, darker the deeper
            r = pygame.Rect(gx + cx * cell, gy + cy * cell, cell, cell)
            shade = min(1.0, -z / _MAX_DEPTH)
            screen.fill(_PIT_C, r)
            screen.fill(tuple(int(c * (1 - 0.55 * shade)) for c in _PIT_C),
                        r.inflate(-cell // 4, -cell // 4))

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
            text(screen, initial, self.fonts.body_bd, INK,
                 (gx + cx * cell + cell // 2, gy + cy * cell + cell // 2), center=True)

        for cx in range(COLS + 1):
            x = gx + cx * cell
            pygame.draw.line(screen, LINE_SOFT, (x, gy), (x, gy + gh))
        for cy in range(ROWS + 1):
            y = gy + cy * cell
            pygame.draw.line(screen, LINE_SOFT, (gx, y), (gx + gw, y))

        for (cx, cy), z in self.elev.items():        # depth number in the pit
            text(screen, str(-z), self.fonts.body_sm, INK_DIM,
                 (gx + cx * cell + cell // 2, gy + cy * cell + cell // 2), center=True)
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

        pygame.draw.rect(screen, LINE, (gx, gy, gw, gh), 1)

        hov = self._cell_at(self.mouse)
        if hov is not None:
            hr = pygame.Rect(gx + hov[0] * cell, gy + hov[1] * cell, cell, cell)
            col = DANGER if self.tool == "erase" else _LAYER_C.get(self.tool, ACCENT)
            pygame.draw.rect(screen, col, hr, 2)

        if self.tool == "npc":
            hint = f"{COLS}x{ROWS}  ·  click a cell to pick an NPC  ·  right-click clears"
        elif self.tool == "pit":
            hint = (f"{COLS}x{ROWS}  ·  left-drag digs pits {self.pit_depth} deep  ·  "
                    "right-drag fills  ·  DEPTH sets how deep")
        elif self.tool == "rope":
            hint = f"{COLS}x{ROWS}  ·  click a pit cell to hang a rope (easier climb)  ·  right-click removes"
        else:
            lightnote = ("lit throughout" if lit
                         else f"dark outside torchlight  ·  {len(self.torches)} torch(es)")
            hint = f"{COLS}x{ROWS}  ·  left-drag paints, right-drag erases  ·  " + lightnote
        text(screen, hint, self.fonts.body_sm, INK_FAINT, (gx, gy + gh + SP2))
        if self._sealed():
            text(screen, "walls seal the two sides off -- no path across",
                 self.fonts.body_sm, WARN, (gx, gy + gh + SP2 + 16))

    def _sync_dark(self):
        """Recompute `self._dark` -- cells beyond every torch's reach, walls
        blocking -- only when the walls or torches changed since last time."""
        sig = (frozenset(self.walls), frozenset(self.torches))
        if sig == self._light_sig:
            return
        self._light_sig = sig
        board = Board(walls=self.walls)
        reached = set()
        for t in self.torches:
            for cy in range(ROWS):
                for cx in range(COLS):
                    p = (cx, cy)
                    if p not in reached and grid_distance(t, p) <= data.TORCH_RADIUS \
                            and board.los_clear(t, p):
                        reached.add(p)
        self._dark = frozenset((cx, cy) for cy in range(ROWS) for cx in range(COLS)
                               if (cx, cy) not in reached)

    # ------------------------------------------------------------------ #
    def _draw_panel(self, screen, rect):
        f = self.fonts
        panel(screen, rect, fill=SURFACE_1, border=LINE_SOFT, radius=RADIUS)
        x = rect.x + SP3
        w = rect.w - 2 * SP3
        y = rect.y + SP3

        y = section(screen, "TOOLS", x, y, w, f)
        for key, label in _TOOLS:
            r = pygame.Rect(x, y, w, 26)
            on = self.tool == key
            self._btn(screen, r, label, on=on, danger=(key == "erase" and on))
            swatch = pygame.Rect(r.right - 20, r.centery - 6, 12, 12)
            if key in _LAYER_C:
                pygame.draw.rect(screen, _LAYER_C[key], swatch, border_radius=2)
            self.hits.append((r, ("tool", key)))
            y += 26 + SP1
        y += SP1

        if self.tool in ("pit", "rope"):
            r = pygame.Rect(x, y, w, 24)
            panel(screen, r, fill=SURFACE_2, border=LINE_SOFT, width=1, radius=4)
            text(screen, f"PIT DEPTH  {self.pit_depth}", f.label, INK,
                 (r.x + SP2, r.centery - 5))
            for lbl, d, side in (("-", -1, r.right - 46), ("+", 1, r.right - 24)):
                b = pygame.Rect(side, r.y + 3, 18, 18)
                self._btn(screen, b, lbl, font=f.body_bd)
                self.hits.append((b, ("depth", d)))
            y += 24 + SP1

        r = pygame.Rect(x, y, w, 24)
        self._btn(screen, r, "CLEAR")
        self.hits.append((r, ("clear",)))
        y += 24 + SP3

        y = section(screen, "SETTINGS", x, y, w, f)
        nr = pygame.Rect(x, y, w, 26)
        editing = self.edit_name
        hot = nr.collidepoint(self.mouse)
        panel(screen, nr, fill=SURFACE_3 if (hot or editing) else SURFACE_2,
              border=ACCENT if (hot or editing) else LINE, width=1, radius=4)
        text(screen, "NAME", f.label, INK_FAINT, (nr.x + SP2, nr.centery - 5))
        vx = nr.x + SP2 + f.label.size("NAME")[0] + SP2
        shown = (self.name_buf + "|") if editing else self.name
        text(screen, ellipsize(shown, f.body_sm, nr.right - SP2 - vx), f.body_sm,
             INK, (vx, nr.centery - 6))
        self.hits.append((nr, ("name",)))
        y += 26 + SP1

        for key, label, val, note in (
                ("ambient", "AMBIENT LIGHT",
                 self.outdoor or self.ambient, self.outdoor),
                ("outdoor", "OUTDOOR (follows daylight)", self.outdoor, False)):
            r = pygame.Rect(x, y, w, 24)
            self._btn(screen, r, label + ("   ·  forced" if note else ""),
                      on=bool(val))
            self.hits.append((r, (key,)))
            y += 24 + SP1
        y += SP2

        y = section(screen, "MAP LIBRARY", x, y, w, f)
        text(screen, "maps/", f.mono_sm, INK_FAINT, (rect.right - SP3, y - 20),
             right=True)
        if not self.library:
            text(screen, "no saved maps yet — SAVE writes one here", f.body_sm,
                 INK_FAINT, (x, y + 2))
        prev = screen.get_clip()
        screen.set_clip(rect.inflate(-SP2, -SP2))
        for row in self.library:
            if y > rect.bottom - 24:
                break
            rr = pygame.Rect(x, y, w, 26)
            cur = row["slug"] == self.slug
            hot = rr.collidepoint(self.mouse)
            panel(screen, rr, fill=SURFACE_3 if (hot or cur) else SURFACE_2,
                  border=ACCENT if cur else (LINE if hot else LINE_SOFT),
                  width=1, radius=4)
            text(screen, ellipsize(row["name"], f.body_sm, int(rr.w * 0.6)),
                 f.body_sm, INK, (rr.x + SP2, rr.y + 5))
            meta = ("field" if row["outdoor"] else "indoor") + f" · {row['walls']}w"
            if self.confirm_delete == row["slug"]:
                yb = pygame.Rect(rr.right - 40, rr.y + 3, 18, 20)
                nb = pygame.Rect(rr.right - 20, rr.y + 3, 18, 20)
                self._btn(screen, yb, "y", danger=True)
                self._btn(screen, nb, "n")
                self.hits.append((yb, ("delete", row["slug"])))
                self.hits.append((nb, ("delete_no",)))
            else:
                text(screen, meta, f.mono_sm, INK_FAINT,
                     (rr.right - 26, rr.y + 6), right=True)
                self.hits.append((rr, ("load", row["slug"])))
                xb = pygame.Rect(rr.right - 20, rr.y + 3, 18, 20)
                h = xb.collidepoint(self.mouse)
                text(screen, "×", f.body_bd, DANGER if h else INK_FAINT,
                     xb.center, center=True)
                self.hits.append((xb, ("ask_delete", row["slug"])))
            y += 28
        screen.set_clip(prev)

    # ------------------------------------------------------------------ #
    def _draw_picker(self, screen):
        """Modal list of NPC-library characters -- pick one to stand on
        `self.picking`. Click a row to assign, anywhere else to cancel."""
        f = self.fonts
        W, H = screen.get_size()
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 190))
        screen.blit(veil, (0, 0))

        rows = self.npc_rows
        rh, pad = 30, SP4
        pw = min(W - 2 * MARGIN, 420)
        ph = min(H - 2 * MARGIN, 56 + rh * len(rows) + SP3)
        box = pygame.Rect((W - pw) // 2, (H - ph) // 2, pw, ph)
        panel(screen, box, fill=SURFACE_2, border=_NPC_C, width=2, radius=8)
        cx, cy = self.picking
        text(screen, f"NPC for cell {cx},{cy}", f.title, INK, (box.x + pad, box.y + 12))

        prev = screen.get_clip()
        screen.set_clip(box.inflate(-2, -2))
        self.picker_hits = []
        cur = self.npc_at.get(self.picking)
        for i, row in enumerate(rows):
            rr = pygame.Rect(box.x + pad, box.y + 46 + i * rh, pw - 2 * pad, rh - SP1)
            if rr.bottom > box.bottom - SP3:
                continue
            sel = row["slug"] == cur
            hov = rr.collidepoint(self.mouse)
            panel(screen, rr, fill=SURFACE_3 if (hov or sel) else SURFACE_1,
                  border=_NPC_C if sel else (LINE if hov else LINE_SOFT), width=1, radius=4)
            text(screen, ellipsize(row["name"], f.body_sm, int(rr.w * 0.5)), f.body_sm,
                 _NPC_C if sel else INK, (rr.x + SP2, rr.centery - 6))
            meta = f"{row['race']} · {row['occupation']}"
            text(screen, ellipsize(meta, f.mono_sm, int(rr.w * 0.45)), f.mono_sm,
                 INK_FAINT, (rr.right - SP2, rr.centery - 5), right=True)
            self.picker_hits.append((rr, row["slug"]))
        screen.set_clip(prev)
        text(screen, "click outside to cancel", f.body_sm, INK_FAINT,
             (box.x + pad, box.bottom - 20))

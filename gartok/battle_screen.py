"""Battle screen: the tactical grid, the initiative strip, the action panel and
the log. Drawing only -- rules live in `battle` / `actions` / `vision`."""

import math
import random

import pygame

from . import actions, ai, artwork, data, icons, vision
from .board import cells
from .lighting import LightRenderer
from .scenario import own_half
from .screen import Screen
from .sheet import character_sheet
from .theme import (ACCENT, ACCENT_INK, ATK_HL, BG, DANGER, DEMO_HL, ENEMY_C,
                    FLOOR_A, FLOOR_B, INFO, INK, INK_DIM, INK_FAINT, LIGHT_C,
                    LINE_SOFT, MOVE_HL, NEUTRAL_C, OBJ_C, OK,
                    PATH_DONE, PATH_PREV, PLAYER_C, RADIUS, SP1, SP2, SP3,
                    SURFACE_0, SURFACE_1, SURFACE_2, SURFACE_3, SURFACE_4,
                    THROW_HL, TORCH_C, WALL_FILL, WALL_HI, WALL_LO, WARN,
                    BoardView, Stack, battle_layout, panel, pips, text, tracked,
                    wrap_lines)

_WATER_C = (74, 128, 174)              # a flooded cell (blue), matches the editor

ENEMY_DELAY = 450  # ms between AI actions


def _sgn(v):
    return (v > 0) - (v < 0)


class BattleScreen(Screen):
    # Native: draws straight to the real window and lays itself out from its
    # size each frame (theme.battle_layout). The board sits in a pan/zoom camera
    # (theme.BoardView), so a hand-authored map of any size is playable.
    native = True

    def __init__(self, fonts, battle, on_battle_end):
        super().__init__()
        self.fonts = fonts
        self.battle = battle
        self.on_battle_end = on_battle_end
        self.lighting = LightRenderer()
        self.view = BoardView(battle.board.cols, battle.board.rows)
        self._pan = None                      # (mouse, cam) anchor while dragging the board
        self._centered_on = None              # unit the camera last snapped to
        self.inspect = None
        self.inspect_open = True
        self.enemy_timer = 0
        self.aim_action = None
        self.view_squad = False
        self.buttons = []

        self._obs = []
        self._visible = set()

        # combat juice -- purely presentational, driven by HP deltas each frame
        self._hp_seen = {}      # id(unit) -> last hp we drew
        self._floaters = []     # rising damage / heal numbers
        self._react = {}        # id(unit) -> {kind, t, dur, [dir]} squash + hop

    # ------------------------------------------------------------------ #
    # events                                                             #
    # ------------------------------------------------------------------ #
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE and self._is_player_turn():
                self.aim_action = None
                self.battle.end_turn()
            elif event.key == pygame.K_l:
                self.view_squad = not self.view_squad
        elif event.type == pygame.MOUSEWHEEL:
            self.view.zoom(pygame.mouse.get_pos(), event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (2, 3):
            if self.view.rect.collidepoint(event.pos):
                self._pan = (event.pos, list(self.view.cam))
        elif event.type == pygame.MOUSEBUTTONUP and event.button in (2, 3):
            self._pan = None
        elif event.type == pygame.MOUSEMOTION and self._pan is not None:
            (ax, ay), cam0 = self._pan
            self.view.cam = list(cam0)
            self.view.pan_px(event.pos[0] - ax, event.pos[1] - ay)

    def update(self, dt):
        b = self.battle
        self._advance_fx(dt)
        self._detect_fx()
        # keep the acting unit in frame on a board too big to fit the viewport
        if (b.winner is None and self._pan is None and self.view.rect.w > 2
                and self._centered_on is not b.active):
            self._centered_on = b.active
            if not self.view.rect.collidepoint(self.view.cell_rect(*b.active.pos).center):
                self.view.center_on(b.active.pos)
        if b.winner is not None:
            return
        if b.awaiting_flag:                  # plant the flag before anyone acts
            return
        if b.active.team == "enemy":
            self.enemy_timer += dt
            if self.enemy_timer >= ENEMY_DELAY:
                self.enemy_timer = 0
                ai.take_turn(b, b.active)
        else:
            self.enemy_timer = 0

    # ------------------------------------------------------------------ #
    # battle logic                                                       #
    # ------------------------------------------------------------------ #
    def _is_player_turn(self):
        b = self.battle
        return b and b.winner is None and b.active.team == "player"

    def _observers(self):
        return vision.observers(self.battle, self.view_squad)

    def _enemy_visible(self, u):
        return vision.enemy_visible(self.battle, self._obs, u)

    def _tile_at_px(self, px):
        return self.view.cell_at(px)

    def _click(self, px):
        b = self.battle
        if b.winner is not None:
            self.on_battle_end(b)
            return
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "inspect_toggle":
                    self.inspect_open = not self.inspect_open
                else:
                    self._action_click(key)
                return

        tile = self._tile_at_px(px)
        if tile is None:
            return

        if b.awaiting_flag:
            if self._can_plant_flag(tile):
                b.flags["player"] = tile
                b.scenario.auto_place_enemy_flag(b)
            return

        self._obs = self._observers()
        clicked = b.unit_at(tile, include_downed=True)
        if clicked is not None and clicked.team == "enemy" \
                and not self._enemy_visible(clicked):
            clicked = None
        if clicked is not None:
            self.inspect = clicked
            self.inspect_open = True

        if not self._is_player_turn():
            return
        actor = b.active

        if self.aim_action is not None and self.aim_action.target == "cell":
            if self.aim_action.can(b, actor, tile):
                self.aim_action.execute(b, actor, tile)
                self.aim_action = None
                self._after_player_action()
            return

        if self.aim_action is not None:
            # `unit_at` returns whichever unit sits on the tile first; when a
            # standing unit shares the cell with a downed one (bodies do not
            # occupy), pick the unit on the tile the action can actually target.
            if clicked is None or not self.aim_action.can(b, actor, clicked):
                clicked = next((u for u in b.units
                                if tile in b.cells_of(u)
                                and self.aim_action.can(b, actor, u)), clicked)
            if clicked is not None and self.aim_action.can(b, actor, clicked):
                self.aim_action.execute(b, actor, clicked)
                self.aim_action = None
                self._after_player_action()
            return

        if clicked is not None and clicked.team == "enemy":
            if actions.ATTACK.can(b, actor, clicked):
                actions.ATTACK.execute(b, actor, clicked)
                self._after_player_action()
            return
        if clicked is None:
            dest = self._anchor_of_click(actor, tile)
            if dest is not None:
                actions.MOVE.execute(b, actor, dest)
                self._after_player_action()

    def _anchor_of_click(self, unit, tile):
        reach = self.battle.reachable(unit)
        if tile in reach:
            return tile
        if unit.footprint > 1:
            cand = [a for a in reach if tile in cells(a, unit.footprint)]
            if cand:
                return min(cand, key=lambda a: reach[a])
        return None

    def _action_click(self, action):
        b = self.battle
        if not self._is_player_turn():
            return
        if action is actions.END:
            self.aim_action = None
            b.end_turn()
            return
        if action.aimed:
            if self.aim_action is action or not action.available(b, b.active):
                self.aim_action = None
            else:
                self.aim_action = action
            return
        if action.can(b, b.active):
            self.aim_action = None
            action.execute(b, b.active)
            self._after_player_action()

    def _after_player_action(self):
        b = self.battle
        if b.is_ctf:                          # stepping onto the enemy flag ends it now
            b.check_objective()
        if b.winner is not None or b.active.team != "player":
            return
        act = b.active
        if act.ap < 1 and not b.reachable(act):
            self.aim_action = None
            b.end_turn()

    # ------------------------------------------------------------------ #
    # combat juice: floating numbers + hit reactions                      #
    # ------------------------------------------------------------------ #
    def _detect_fx(self):
        """Compare each unit's HP to last frame; spawn a floating number and a
        hit reaction on a change, and a lunge on whoever is acting."""
        b = self.battle
        actor = b.active if b.winner is None else None
        for u in b.units:
            hp = u.hp
            prev = self._hp_seen.get(id(u))
            self._hp_seen[id(u)] = hp
            if prev is None or hp == prev:
                continue
            r = self._unit_rect(u)
            delta = hp - prev
            if delta < 0:
                self._spawn_floater(r, str(delta), DANGER)
                self._react[id(u)] = {"kind": "hit", "t": 0.0, "dur": 260.0}
                if actor and actor.alive and actor.team != u.team and actor is not u:
                    ax, ay = actor.pos
                    self._react[id(actor)] = {
                        "kind": "lunge", "t": 0.0, "dur": 200.0,
                        "dir": (_sgn(u.pos[0] - ax), _sgn(u.pos[1] - ay))}
            else:
                self._spawn_floater(r, f"+{delta}", OK)
                self._react[id(u)] = {"kind": "hit", "t": 0.0, "dur": 240.0}

    def _spawn_floater(self, r, s, color):
        stack = sum(1 for f in self._floaters
                    if abs(f["x"] - r.centerx) < self.view.tile and f["age"] < 240)
        self._floaters.append({
            "x": r.centerx + random.randint(-4, 4),
            "y": r.top - 6 - 14 * stack,
            "vy": -0.03, "age": 0.0, "hold": 140.0,
            "alpha": 255.0, "fade": 0.28, "text": s, "color": color})

    def _advance_fx(self, dt):
        for f in self._floaters:
            f["y"] += f["vy"] * dt
            f["age"] += dt
            if f["age"] > f["hold"]:
                f["alpha"] -= f["fade"] * dt
        self._floaters = [f for f in self._floaters if f["alpha"] > 0]
        for k in list(self._react):
            self._react[k]["t"] += dt
            if self._react[k]["t"] >= self._react[k]["dur"]:
                del self._react[k]

    def _fx_rect(self, u, r):
        """Offset + squash `r` for the unit's current hit reaction (a 3px hop on a
        hit, a shove toward the target on a lunge)."""
        fx = self._react.get(id(u))
        if not fx:
            return r
        wave = math.sin(math.pi * min(1.0, fx["t"] / fx["dur"]))
        if fx["kind"] == "lunge":
            dx, dy, sq = fx["dir"][0] * 5 * wave, fx["dir"][1] * 5 * wave, 0.09 * wave
        else:
            dx, dy, sq = 0.0, -3 * wave, 0.14 * wave
        out = pygame.Rect(0, 0, round(r.w * (1 + sq)), round(r.h * (1 - sq)))
        out.midbottom = (r.centerx + round(dx), r.bottom + round(dy))
        return out

    def _draw_floaters(self, screen):
        f = self.fonts
        clip = screen.get_clip()
        screen.set_clip(self.view.rect)
        for fl in self._floaters:
            a = max(0, min(255, int(fl["alpha"])))
            img = f.num.render(fl["text"], True, fl["color"])
            sh = f.num.render(fl["text"], True, (12, 12, 16))
            img.set_alpha(a)
            sh.set_alpha(a // 2)
            rect = img.get_rect(center=(int(fl["x"]), int(fl["y"])))
            screen.blit(sh, rect.move(1, 1))
            screen.blit(img, rect)
        screen.set_clip(clip)

    # ------------------------------------------------------------------ #
    # drawing                                                            #
    # ------------------------------------------------------------------ #
    def draw(self, screen):
        screen.fill(BG)
        self._L = battle_layout(screen.get_size())
        self.view.cols, self.view.rows = self.battle.board.cols, self.battle.board.rows
        self.view.fit(self._L["board"])

        self._obs = self._observers()
        self._visible = vision.visible_cells(self.battle, self._obs)

        clip = screen.get_clip()
        screen.set_clip(self.view.rect)
        self._draw_grid(screen)
        self._draw_ground(screen)
        self.lighting.draw(screen, self.battle, self._visible, self._obs, self.view)
        self._draw_creatures(screen)
        self._draw_units(screen)
        if self.battle.is_ctf:
            self._draw_flags(screen)
        self._draw_tactical(screen)              # overlay: above the fog
        if self.battle.awaiting_flag:
            self._draw_flag_setup(screen)
        self._draw_floaters(screen)
        screen.set_clip(clip)

        self._draw_initiative(screen)
        self._draw_panel(screen)
        self._draw_log(screen)
        if self.battle.winner:
            self._draw_winner(screen)

    def _cell_rect(self, cx, cy):
        return self.view.cell_rect(cx, cy)

    def _unit_rect(self, u):
        r = self.view.cell_rect(*u.pos)
        t = self.view.tile
        return pygame.Rect(r.x, r.y, t * u.footprint, t * u.footprint)

    def _draw_grid(self, screen):
        """A flat tactical board drawn from the design system -- a quiet checker
        for the floor, raised stone blocks for the walls (corners rounded only
        where a wall face is exposed, so clusters read as one mass)."""
        board = self.battle.board
        walls = board.walls
        view = self.view
        vr = view.rect
        tile = view.tile
        vis = lambda cx, cy: view.cell_rect(cx, cy).colliderect(vr)
        for cy in range(board.rows):
            for cx in range(board.cols):
                if vis(cx, cy):
                    tone = FLOOR_A if (cx + cy) & 1 else FLOOR_B
                    screen.fill(tone, view.cell_rect(cx, cy))

        for (cx, cy), z in board.elevation.items():   # a pit: sunken, darker the deeper
            if not vis(cx, cy):
                continue
            r = view.cell_rect(cx, cy)
            k = min(1.0, -z / 6)
            screen.fill(WALL_LO, r)
            screen.fill(tuple(int(v * (1 - 0.5 * k)) for v in WALL_LO),
                        r.inflate(-tile // 4, -tile // 4))
            text(screen, str(-z), self.fonts.mono_sm, INK_FAINT, r.center, center=True)

        for cx, cy in board.water:                     # deep over a pit, a shallow puddle otherwise
            if not vis(cx, cy):
                continue
            deep = board.elevation.get((cx, cy), 0) < 0
            wl = pygame.Surface((tile, tile), pygame.SRCALPHA)
            wl.fill((*_WATER_C, 150 if deep else 92))
            screen.blit(wl, view.cell_rect(cx, cy))

        for cx, cy in board.ropes:
            if not vis(cx, cy):
                continue
            r = view.cell_rect(cx, cy)
            pygame.draw.line(screen, (198, 160, 104),
                             (r.centerx, r.top + 3), (r.centerx, r.bottom - 3),
                             max(2, tile // 12))

        for cx in range(board.cols + 1):
            x = round(vr.x + (cx - view.cam[0]) * tile)
            pygame.draw.line(screen, LINE_SOFT, (x, vr.top), (x, vr.bottom))
        for cy in range(board.rows + 1):
            y = round(vr.y + (cy - view.cam[1]) * tile)
            pygame.draw.line(screen, LINE_SOFT, (vr.left, y), (vr.right, y))

        # drop shadow: a dark block offset down-right, painted before the walls
        # so each block covers its neighbours' shadows -> only the exposed south
        # and east faces cast onto the floor, and the grid reads as 2.5D
        shadow = pygame.Surface((tile, tile), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 110), shadow.get_rect(), border_radius=RADIUS)
        for wx, wy in walls:
            if vis(wx, wy):
                r = view.cell_rect(wx, wy)
                screen.blit(shadow, (r.x + 5, r.y + 5))

        for wx, wy in walls:
            if vis(wx, wy):
                self._draw_wall_block(screen, wx, wy, walls)

    def _draw_wall_block(self, screen, wx, wy, walls):
        r = self._cell_rect(wx, wy).inflate(-2, -2)
        open_n = (wx, wy - 1) not in walls
        open_s = (wx, wy + 1) not in walls
        open_w = (wx - 1, wy) not in walls
        open_e = (wx + 1, wy) not in walls
        rad = lambda a, b: RADIUS if a and b else 0
        kw = dict(border_top_left_radius=rad(open_n, open_w),
                  border_top_right_radius=rad(open_n, open_e),
                  border_bottom_left_radius=rad(open_s, open_w),
                  border_bottom_right_radius=rad(open_s, open_e))
        pygame.draw.rect(screen, WALL_FILL, r, **kw)
        # lower half a touch darker -> a hint of volume
        lower = pygame.Rect(r.x, r.centery, r.w, r.h - r.h // 2)
        sh = pygame.Surface(lower.size, pygame.SRCALPHA)
        sh.fill((*WALL_LO, 55))
        screen.blit(sh, lower.topleft)
        pygame.draw.rect(screen, WALL_LO, r, 1, **kw)
        if open_n:                                   # exposed top face -> bevel
            cap = pygame.Rect(r.x + 3, r.y + 3, r.w - 6, 4)
            pygame.draw.rect(screen, WALL_HI, cap, border_radius=2)

    # ------------------------------------------------------------------ #
    # tactical overlay                                                   #
    # ------------------------------------------------------------------ #
    def _hovered_anchor(self):
        if not self._is_player_turn() or self.aim_action is not None:
            return None
        tile = self._tile_at_px(self.mouse)
        if tile is None:
            return None
        return self._anchor_of_click(self.battle.active, tile)

    def _path_points(self, cells_, footprint):
        off = self.view.tile * footprint // 2
        return [(self.view.cell_rect(cx, cy).x + off,
                 self.view.cell_rect(cx, cy).y + off) for cx, cy in cells_]

    def _draw_tactical(self, screen):
        b = self.battle
        if not self._is_player_turn():
            return
        actor = b.active

        board = b.board
        cell = pygame.Surface((self.view.tile, self.view.tile), pygame.SRCALPHA)

        if self.aim_action is not None:
            if self.aim_action in (actions.STABILIZE, actions.FIRST_AID):
                color = OK
            elif self.aim_action is actions.DEMORALIZE:
                color = DEMO_HL
            elif self.aim_action in (actions.CLIMB, actions.DROP, actions.JUMP,
                                     actions.SWIM):
                color = MOVE_HL
            else:
                color = THROW_HL
            cell.fill((*color, 46))
            for pos in self.aim_action.highlight_cells(b, actor):
                if 0 <= pos[0] < board.cols and 0 <= pos[1] < board.rows:
                    screen.blit(cell, self._cell_rect(*pos))
            for u in self.aim_action.highlight_targets(b, actor):
                if u.team == actor.team or self._enemy_visible(u):
                    pygame.draw.rect(screen, color, self._unit_rect(u), 3, border_radius=4)
            return

        # reachable footprint tint + border
        reach_cells = b.reachable_cells(actor)
        cell.fill((*MOVE_HL, 40))
        for pos in reach_cells:
            screen.blit(cell, self._cell_rect(*pos))
        for pos in reach_cells:
            r = self._cell_rect(*pos)
            for (dx, dy), seg in (((1, 0), (r.right, r.top, r.right, r.bottom)),
                                  ((-1, 0), (r.left, r.top, r.left, r.bottom)),
                                  ((0, 1), (r.left, r.bottom, r.right, r.bottom)),
                                  ((0, -1), (r.left, r.top, r.right, r.top))):
                if (pos[0] + dx, pos[1] + dy) not in reach_cells:
                    pygame.draw.line(screen, (*MOVE_HL, 210), seg[:2], seg[2:], 2)

        for u in b.units:
            if u.alive and u.team == "enemy" and actions.ATTACK.can(b, actor, u):
                pygame.draw.rect(screen, ATK_HL, self._unit_rect(u), 3, border_radius=4)

        # walked-this-turn trail
        if len(actor.path) >= 2:
            pts = self._path_points(actor.path, actor.footprint)
            pygame.draw.lines(screen, PATH_DONE, False, pts, 2)
            for p in pts[1:]:
                pygame.draw.circle(screen, PATH_DONE, p, 2)

        # planned route under the cursor
        anchor = self._hovered_anchor()
        if anchor is not None and anchor != actor.pos:
            route = b.path_to(actor, anchor)
            if len(route) >= 2:
                pts = self._path_points(route, actor.footprint)
                pygame.draw.lines(screen, PATH_PREV, False, pts, 3)
                for p in pts[1:-1]:
                    pygame.draw.circle(screen, PATH_PREV, p, 3)
                end = pts[-1]
                pygame.draw.circle(screen, PATH_PREV, end, 8, 2)
                cost = b.reachable(actor).get(anchor)
                if cost is not None:
                    badge = pygame.Rect(0, 0, 18, 15)
                    badge.center = (end[0], end[1] - 15)
                    panel(screen, badge, fill=PATH_PREV, border=None, radius=4)
                    text(screen, str(cost), self.fonts.mono_sm, (20, 18, 8),
                         badge.center, center=True)

    # ------------------------------------------------------------------ #
    # scene props                                                        #
    # ------------------------------------------------------------------ #
    def _draw_torch(self, screen, pos):
        t = self.view.tile
        cx, cy = self._cell_rect(*pos).center
        glow = pygame.Surface((t * 2, t * 2), pygame.SRCALPHA)
        for rad, a in ((t * 3 // 4, 22), (t // 2, 34), (t // 4, 60)):
            pygame.draw.circle(glow, (*TORCH_C, a), (t, t), rad)
        screen.blit(glow, (cx - t, cy - t))
        pygame.draw.circle(screen, (58, 52, 46), (cx, cy + 4), 5)
        pygame.draw.circle(screen, TORCH_C, (cx, cy - 2), 6)
        pygame.draw.circle(screen, LIGHT_C, (cx, cy - 4), 3)

    def _draw_ground(self, screen):
        for o in self.battle.ground:
            if o.pos not in self._visible:
                continue
            if o.is_torch:
                self._draw_torch(screen, o.pos)
            else:
                cx, cy = self._cell_rect(*o.pos).center
                d = self.view.tile // 4
                pts = [(cx, cy - d), (cx + d, cy), (cx, cy + d), (cx - d, cy)]
                pygame.draw.polygon(screen, OBJ_C, pts)
                pygame.draw.polygon(screen, (25, 22, 12), pts, 2)

    # ------------------------------------------------------------------ #
    # capture the flag                                                   #
    # ------------------------------------------------------------------ #
    def _can_plant_flag(self, tile):
        b = self.battle
        x, y = tile
        return (x in own_half("player", b.board.cols) and 0 <= y < b.board.rows
                and tile not in b.board.walls and b.unit_at(tile) is None)

    def _draw_pennant(self, screen, pos, color):
        r = self._cell_rect(*pos)
        pole = (r.x + r.w // 3, r.bottom - 5)
        pygame.draw.line(screen, INK, (pole[0], r.y + 5), pole, 3)
        flag = [(pole[0], r.y + 5), (pole[0] + r.w // 2, r.y + 12),
                (pole[0], r.y + 19)]
        pygame.draw.polygon(screen, color, flag)
        pygame.draw.polygon(screen, INK, flag, 1)

    def _draw_flags(self, screen):
        for team, pos in self.battle.flags.items():
            if pos is None:
                continue
            # your own flag you always know; the enemy's you have to find --
            # it stays hidden until a cell you can see falls on it.
            if team == "enemy" and pos not in self._visible:
                continue
            self._draw_pennant(screen, pos, PLAYER_C if team == "player" else ENEMY_C)

    def _draw_flag_setup(self, screen):
        f = self.fonts
        board = self.battle.board
        tint = pygame.Surface((self.view.tile, self.view.tile), pygame.SRCALPHA)
        tint.fill((*PLAYER_C, 32))
        hover = self._tile_at_px(self.mouse)
        for x in own_half("player", board.cols):
            for y in range(board.rows):
                if (x, y) in board.walls:
                    continue
                screen.blit(tint, self._cell_rect(x, y))
        if hover is not None and self._can_plant_flag(hover):
            pygame.draw.rect(screen, PLAYER_C, self._cell_rect(*hover), 2, border_radius=4)
        banner = pygame.Rect(self.view.rect.x, self.view.rect.y, self.view.rect.w, 30)
        panel(screen, banner, fill=SURFACE_2, border=PLAYER_C, width=1)
        text(screen, "CAPTURE THE FLAG  ·  click a cell in your half to plant your flag",
             f.body_bd, INK, banner.center, center=True)

    def _draw_creatures(self, screen):
        f = self.fonts
        for cr in self.battle.creatures:
            if cr.pos not in self._visible:
                continue
            r = self._cell_rect(*cr.pos)
            pygame.draw.circle(screen, NEUTRAL_C, r.center, r.w // 2 - 6)
            text(screen, cr.token, f.body_bd, (25, 25, 25), r.center, center=True)

    def _draw_body(self, screen, u, r):
        """A downed unit: dying (with its death counter) or stable, on the ground."""
        f = self.fonts
        center = r.center
        rad = r.w // 2 - 6
        base = PLAYER_C if u.team == "player" else ENEMY_C
        pygame.draw.circle(screen, tuple(c // 3 + 12 for c in base), center, rad)
        ring = DANGER if u.dying else INK_DIM
        pygame.draw.circle(screen, ring, center, rad, 2)
        d = rad // 2
        pygame.draw.line(screen, ring, (center[0] - d, center[1] - d),
                         (center[0] + d, center[1] + d), 2)
        pygame.draw.line(screen, ring, (center[0] - d, center[1] + d),
                         (center[0] + d, center[1] - d), 2)
        if u.dying:
            badge = pygame.Rect(0, 0, 20, 15)
            badge.center = (r.centerx, r.y + 8)
            panel(screen, badge, fill=DANGER, border=None, radius=4)
            text(screen, f"{u.death_clock}/{data.DYING_TURNS}", f.mono_sm, (20, 18, 8),
                 badge.center, center=True)
        elif u.broken:
            badge = pygame.Rect(0, 0, 34, 15)
            badge.center = (r.centerx, r.y + 8)
            panel(screen, badge, fill=WARN, border=None, radius=4)
            text(screen, "BRKN", f.mono_sm, (20, 18, 8), badge.center, center=True)
        if self.inspect is u:
            pygame.draw.rect(screen, INK, r, 1, border_radius=4)

    def _draw_units(self, screen):
        f = self.fonts
        b = self.battle
        for u in b.units:
            if u.dead or u.fled:
                continue
            if u.team == "enemy" and not self._enemy_visible(u) \
                    and not (self._is_player_turn() and u.alive
                             and actions.ATTACK.can(b, b.active, u)):
                continue
            r = self._fx_rect(u, self._unit_rect(u))
            if u.downed:
                self._draw_body(screen, u, r)
                continue
            center = r.center
            rad = r.w // 2
            base = PLAYER_C if u.team == "player" else ENEMY_C
            if u is b.active and b.winner is None:
                pygame.draw.circle(screen, ACCENT, center, rad - 1)
            pygame.draw.circle(screen, base, center, rad - 5)
            pygame.draw.circle(screen, (*base, 60), center, rad - 5, 1)
            if u.has_torch:
                pygame.draw.circle(screen, TORCH_C, center, rad - 3, 2)
                pygame.draw.circle(screen, LIGHT_C, (r.right - 8, r.y + 8), 4)
            if u.defending:
                pygame.draw.circle(screen, INK, center, rad - 5, 2)
            if getattr(u, "ferocity_pending", False):
                pygame.draw.circle(screen, DANGER, center, rad - 3, 2)
            if u.demoralized:
                pygame.draw.circle(screen, DEMO_HL, (r.x + 8, r.y + 8), 4)
            sil = artwork.race_icon(u.race["name"], round(rad * 1.5), (15, 15, 20))
            if sil is not None:
                screen.blit(sil, sil.get_rect(center=center))
            else:
                text(screen, u.token, f.body_bd, (15, 15, 20), center, center=True)

            frac = max(0, u.hp) / u.hp_max
            bar = pygame.Rect(r.x + 5, r.bottom - 8, r.w - 10, 4)
            pygame.draw.rect(screen, (30, 30, 36), bar)
            pygame.draw.rect(screen, OK if frac > 0.4 else WARN if frac > 0.15 else DANGER,
                             pygame.Rect(bar.x, bar.y, int(bar.w * frac), bar.h))
            if self.inspect is u:
                pygame.draw.rect(screen, INK, r, 1, border_radius=4)

    # ------------------------------------------------------------------ #
    # initiative strip                                                   #
    # ------------------------------------------------------------------ #
    def _draw_initiative(self, screen):
        f = self.fonts
        b = self.battle
        strip = self._L["init"]
        panel(screen, strip, fill=SURFACE_1)
        tracked(screen, "INITIATIVE", f.label, INK_FAINT, (strip.x + SP2, strip.y + SP1))

        living = [u for u in b.order if u.alive or u.dying]
        n = max(1, len(living))
        avail = max(1, strip.w - 92 - SP2)
        cw = max(24, min(112, avail // n))
        x = strip.x + 88
        y = strip.y + 6
        for u in living:
            r = pygame.Rect(x, y, cw - SP1, strip.h - 12)
            is_active = u is b.active and b.winner is None
            known = u.team == "player" or self._enemy_visible(u)
            fill = SURFACE_3 if is_active else SURFACE_2
            panel(screen, r, fill=fill,
                  border=ACCENT if is_active else LINE_SOFT,
                  width=2 if is_active else 1, radius=4)
            tcol = PLAYER_C if u.team == "player" else ENEMY_C
            dot = (r.x + 12, r.centery - 3)
            pygame.draw.circle(screen, tcol if known else SURFACE_4, dot, 8)
            sil = artwork.race_icon(u.race["name"], 13, (12, 12, 16)) if known else None
            if sil is not None:
                screen.blit(sil, sil.get_rect(center=dot))
            else:
                text(screen, u.token if known else "?", f.mono_sm, (12, 12, 16),
                     dot, center=True)
            nm = (u.name.split()[0] if known else "Enemy")
            col = INK if is_active else INK_DIM
            clip = screen.get_clip()
            screen.set_clip(r.inflate(-6, -6))
            text(screen, nm, f.body_sm, col, (r.x + 26, r.y + 4))
            screen.set_clip(clip)
            if u.dying:
                text(screen, f"dying {u.death_clock}/{data.DYING_TURNS}", f.mono_sm,
                     DANGER, (r.x + 8, r.bottom - 14))
            elif known:
                frac = max(0, u.hp) / u.hp_max
                hb = pygame.Rect(r.x + 8, r.bottom - 9, r.w - 16, 4)
                pygame.draw.rect(screen, (30, 30, 36), hb)
                pygame.draw.rect(screen, OK if frac > 0.4 else WARN if frac > 0.15 else DANGER,
                                 pygame.Rect(hb.x, hb.y, int(hb.w * frac), hb.h))
            x += cw

    # ------------------------------------------------------------------ #
    # panel                                                              #
    # ------------------------------------------------------------------ #
    def _draw_panel(self, screen):
        f = self.fonts
        b = self.battle
        pr = self._L["panel"]
        s = Stack(pr.x, pr.y, pr.w)

        # --- header ------------------------------------------------- #
        head = s.row(30)
        title = ("VICTORY" if b.winner else "AID THE DOWNED" if b.mopping_up
                 else f"Round {b.round_no}")
        text(screen, title, f.title, ACCENT if b.winner else WARN if b.mopping_up else INK,
             (head.x, head.y - 4))
        vision_active = self._is_player_turn() and not self.view_squad
        vtxt = "ACTIVE" if vision_active else "SQUAD"
        text(screen, f"vision {vtxt}  [L]", f.body_sm,
             ACCENT if vision_active else INK_DIM,
             (head.right, head.y + 4), right=True)
        s.gap(SP3)

        if b.winner is None:
            self._draw_turn_card(screen, s)
            s.gap(SP3)
            self._draw_hint(screen, s)
            s.gap(SP3)

        self.buttons = []
        self._draw_actions(screen, s)
        s.gap(SP3)
        self._draw_inspect(screen, s)

    def _draw_turn_card(self, screen, s):
        f = self.fonts
        b = self.battle
        act = b.active
        card = s.row(74)
        mine = act.team == "player"
        panel(screen, card, fill=SURFACE_2,
              border=PLAYER_C if mine else ENEMY_C, width=1)

        dot = (card.x + SP3 + 11, card.y + 21)
        pygame.draw.circle(screen, PLAYER_C if mine else ENEMY_C, dot, 13)
        text(screen, act.token, f.body_bd, (15, 15, 20), dot, center=True)
        text(screen, act.name, f.heading, INK, (dot[0] + 24, card.y + 7))
        marks = "  ".join(x for x in (
            "defending" if act.defending else "",
            "demoralized" if act.demoralized else "") if x)
        extra = "".join((
            f"   arrows {act.ammo}" if act.needs_ammo else "",
            f"   kit {act.first_aid_charges}x" if act.first_aid_charges else "",
            f"   {marks}" if marks else "",
        ))
        text(screen, f"HP {max(act.hp,0)}/{act.hp_max}   AC {act.ac}   MD {act.mental_defense}" + extra,
             f.mono_sm, INK_DIM, (dot[0] + 24, card.y + 28))

        # AP pips (label above, pips below), right-aligned
        px = card.right - SP3 - 19
        text(screen, "ACTION", f.label, INK_FAINT, (px + 4, card.y + 8), center=True)
        pips(screen, (px, card.y + 30), act.ap, 2, r=7, gap=8)

        base = card.y + 50
        if act.walking:
            text(screen, f"walk {act.moved}/{act.speed}", f.mono_sm,
                 INK_DIM, (card.x + SP3, base))
            track = pygame.Rect(card.x + SP3 + 116, base + 4, card.right - card.x - SP3 - 128, 5)
            pygame.draw.rect(screen, SURFACE_4, track, border_radius=2)
            frac = min(1.0, act.moved / max(1, act.speed))
            pygame.draw.rect(screen, MOVE_HL,
                             pygame.Rect(track.x, track.y, int(track.w * frac), track.h),
                             border_radius=2)
        elif mine:
            vd = vision.vision_desc(act) if not self.view_squad else "vision: whole squad  [L]"
            text(screen, vd, f.mono_sm, INK_FAINT, (card.x + SP3, base))

    def _draw_hint(self, screen, s):
        row = s.row(16)
        if not self._is_player_turn():
            return
        if self.aim_action is actions.DEMORALIZE:
            msg, col = "click a purple enemy to Demoralize", DEMO_HL
        elif self.aim_action is actions.THROW:
            msg, col = "click an enemy in the orange range", THROW_HL
        elif self.aim_action in (actions.STABILIZE, actions.FIRST_AID):
            msg, col = "click an adjacent downed ally (green)", OK
        elif actions.FLEE.available(self.battle, self.battle.active):
            msg, col = "at the map edge: you can Flee the fight", OK
        elif self.battle.mopping_up:
            msg, col = ("enemies down  ·  stabilize the downed or space "
                        "to let the counter run"), WARN
        elif self.battle.is_ctf:
            msg, col = "reach the red flag to win  ·  guard your own", INFO
        else:
            msg, col = "green square: move  ·  enemy: attack  ·  space: end", INK_DIM
        text(screen, msg, self.fonts.body_sm, col, (row.x, row.y))

    def _draw_actions(self, screen, s):
        f = self.fonts
        b = self.battle
        my_turn = b.winner is None and self._is_player_turn()
        act = b.active
        # Climb/Drop only make sense at a pit edge -- hide them elsewhere. Push
        # and Jump are general moves; they stay on the panel, greyed when unusable.
        contextual = (actions.STABILIZE, actions.FIRST_AID,
                      actions.CLIMB, actions.DROP, actions.SWIM)

        for action in actions.PANEL_ACTIONS:
            if action in contextual and not (my_turn and action.available(b, act)):
                continue
            enabled = my_turn if action is actions.END else (
                my_turn and action.available(b, act))
            armed = action.aimed and self.aim_action is action
            r = s.row(34)
            s.gap(SP1)
            arm_c = DEMO_HL if action is actions.DEMORALIZE else \
                THROW_HL if action is actions.THROW else ACCENT
            fill = arm_c if armed else SURFACE_2 if enabled else SURFACE_1
            panel(screen, r, fill=fill,
                  border=arm_c if armed else LINE_SOFT, width=1)
            ink = ACCENT_INK if armed else INK if enabled else INK_FAINT

            ibox = pygame.Rect(r.x + SP2, r.y + 5, 24, 24)
            icons.icon(screen, action.id, ibox, ink)

            label = f"{action.name}: click the target" if armed else action.name
            text(screen, label, f.body_bd, ink, (ibox.right + SP2, r.y + 9))

            if action.cost:
                cx = r.right - SP3
                text(screen, str(action.cost), self.fonts.mono_sm, ink, (cx, r.centery - 6),
                     right=True)
                pygame.draw.circle(screen, ink, (cx - 16, r.centery), 3)
            self.buttons.append((action, r))

    def _draw_inspect(self, screen, s):
        f = self.fonts
        b = self.battle
        insp = self.inspect
        if insp and insp.team == "enemy" and not self._enemy_visible(insp):
            insp = None
        if insp and (insp.dead or insp.fled):
            insp = None
        who = insp or (b.active if b.winner is None else None)
        if who is None:
            return

        s.gap(SP2)
        head = s.row(20)
        caret = "v" if self.inspect_open else ">"
        label = "INSPECT" if who is insp else "ACTIVE UNIT"
        tracked(screen, f"{caret}  {label}", f.label, INFO, (head.x, head.y + 3))
        text(screen, "click a unit", f.body_sm, INK_FAINT,
             (head.right, head.y + 3), right=True)
        self.buttons.append(("inspect_toggle", head))
        pygame.draw.line(screen, LINE_SOFT, (head.x, head.bottom + 2),
                         (head.right, head.bottom + 2))

        if not self.inspect_open:
            return
        s.gap(SP3)
        body = s.row(4)
        lines = wrap_lines(character_sheet(who), f.mono_sm, self._L["panel"].w - SP2)
        y = body.y
        for i, ln in enumerate(lines):
            col = INK if i == 0 else INK_DIM
            text(screen, ln, f.mono_sm if i else f.body_bd, col, (body.x, y))
            y += 15 if i else 20

    # ------------------------------------------------------------------ #
    # log                                                                #
    # ------------------------------------------------------------------ #
    _LOG_RULES = (
        (("---", "***", "Round"), INK_FAINT),
        (("CRITICAL HIT",), WARN),
        (("DEAD", "dies.", "goes down, dying", "coup de grace", "Victory:",
          "*** Victory", "doesn't survive"), DANGER),
        (("is dying", "BROKEN", "ferocity runs out"), WARN),
        (("takes", "damage"), (206, 150, 140)),
        (("-> misses", "no effect", "critical miss", "misses again", "-> fail"), INK_FAINT),
        (("-> hit", "-> lands", "regenerates", "recovers", "recompo", "stabiliz",
          "survives", "-> success", "repaired", "back online"), OK),
    )

    def _log_color(self, line):
        for needles, col in self._LOG_RULES:
            if any(nd in line for nd in needles):
                return col
        return INK_DIM

    def _draw_log(self, screen):
        f = self.fonts
        well = self._L["log"]
        panel(screen, well, fill=SURFACE_0, border=LINE_SOFT)
        tracked(screen, "LOG", f.label, INK_FAINT, (well.x + SP2, well.y + SP1))
        rows = max(1, (well.h - 24) // 17)
        lines = self.battle.log_lines[-rows:]
        y = well.y + 22
        for i, ln in enumerate(lines):
            last = i == len(lines) - 1
            col = INK if last else self._log_color(ln)
            text(screen, ln[:180], f.mono_sm, col, (well.x + SP3, y))
            y += 17

    def _draw_winner(self, screen):
        f = self.fonts
        b = self.battle
        txt = "You won" if b.winner == "player" else "The AI won"
        box = pygame.Rect(0, 0, 360, 92)
        box.center = self.view.rect.center
        panel(screen, box, fill=SURFACE_2, border=ACCENT, width=2, radius=RADIUS)
        text(screen, txt, f.title, INK, (box.centerx, box.y + 30), center=True)
        text(screen, "click to continue", f.body, INK_DIM,
             (box.centerx, box.y + 62), center=True)

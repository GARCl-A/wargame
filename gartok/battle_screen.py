"""Battle screen: the tactical grid, the initiative strip, the action panel and
the log. Drawing delegates to `board_render` (playfield) and `battle_panel`
(chrome); rules live in `battle` / `actions` / `vision`; combat juice
(floaters, hit reactions) lives in `battle_fx`."""

import json
import os
import random
import time

import pygame

from . import actions, ai, data, settings, vision
from .battle_fx import BattleFX
from .board import cells
from .lighting import LightRenderer
from .scenario import own_half
from .screen import Screen
from .ui import battle_panel, board_render, board_style, primitives as ui_primitives
from .ui.board_style import BoardView, battle_layout
from .ui.sheet_card import draw_sheet as draw_sheet_card, sheet_height, unit_to_ch
from .ui.tokens import T

ENEMY_DELAY = 450  # ms between AI actions

ARROW_STEPS = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
               pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}


DEBUG_EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug_exports")


class BattleScreen(Screen):
    native = True

    def __init__(self, fonts, battle, on_battle_end, controllers=None):
        super().__init__()
        self.F = fonts
        self.battle = battle
        self.on_battle_end = on_battle_end
        sink_controllers = battle.sink.controllers if battle.sink else {}
        self.controllers = {"player": "human", "enemy": "ai", **sink_controllers, **(controllers or {})}
        humans = [t for t in ("player", "enemy") if self.controllers[t] == "human"]
        self._viewer = humans[0] if humans else "player"   # whose eyes the board is drawn through
        self._seat = self._viewer              # the team sitting at the screen (two humans share it)
        self._handoff = None                   # a team about to take the seat: the board stays hidden
        self.lighting = LightRenderer()
        self.view = BoardView(battle.board.cols, battle.board.rows)
        self._pan = None                      # (mouse, cam) anchor while dragging the board
        self._chord = set()                   # arrow keys pressed in the current chord window
        self._chord_ms = 0
        self._centered_on = None              # unit the camera last snapped to
        self.inspect = None
        self.inspect_open = True
        self._armed = None                    # enemy a repeat click on it will now attack
        self.enemy_timer = 0
        self.aim_action = None
        self.height_prompt = None
        self.show_magic_menu = False
        self.show_blocked_actions = False
        self.view_squad = False
        self.action_tab = "combat"            # "combat" | "utility"
        self.actions_scroll = 0
        self._actions_scroll_rect = None
        self._actions_max_scroll = 0
        self._hotkey_actions = []
        self.buttons = []
        self.log_scroll = 0                   # lines scrolled up from the live bottom
        self._log_len_seen = 0

        self._obs = []
        self._visible = set()

        self.fx = BattleFX()    # combat juice: floaters + hit reactions (battle_fx.py)

    # ------------------------------------------------------------------ #
    # events                                                             #
    # ------------------------------------------------------------------ #
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE and self._is_player_turn():
                self.aim_action = None
                self.battle.end_turn()
            elif event.key == pygame.K_TAB and self._is_player_turn():
                self.action_tab = "utility" if self.action_tab == "combat" else "combat"
                self.actions_scroll = 0
                self.aim_action = None
            elif event.key in ARROW_STEPS and self._is_player_turn():
                self._chord.add(event.key)
                self._chord_ms = settings.get("chord_ms")
            elif event.key == pygame.K_l:
                self.view_squad = not self.view_squad
            elif event.key == pygame.K_a and self._is_player_turn():
                self._confirm_armed_attack()
            elif pygame.K_1 <= event.key <= pygame.K_9:
                self._hotkey_action(event.key - pygame.K_1)
        elif event.type == pygame.MOUSEWHEEL:
            act_rect = getattr(self, "_actions_scroll_rect", None)
            log_rect = getattr(self, "_L", None) and self._L.get("log")
            if act_rect and act_rect.collidepoint(self.mouse):
                max_s = getattr(self, "_actions_max_scroll", 0)
                self.actions_scroll = max(0, min(max_s, self.actions_scroll - event.y * 34))
            elif log_rect and log_rect.collidepoint(self.mouse):
                self.log_scroll = max(0, self.log_scroll + event.y)
            else:
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

    def handle_escape(self):
        if getattr(self, "height_prompt", None) is not None:
            self.height_prompt = None
            return True
        if self.aim_action is not None:
            self.aim_action = None
            return True
        return False

    def update(self, dt):
        b = self.battle
        self.fx.advance(dt)
        if self._chord:
            self._chord_ms -= dt
            if self._chord_ms <= 0:
                self._step_with_arrows()
        self.fx.detect(b, self.view.tile, self._unit_rect, self._cell_rect)
        if (b.winner is None and self._pan is None and self.view.rect.w > 2
                and self._centered_on is not b.active):
            self._centered_on = b.active
            if not self.view.rect.collidepoint(self.view.cell_rect(*b.active.pos).center):
                self.view.center_on(b.active.pos)
        if b.winner is not None:
            if b.sink is not None and not b.sink.closed:
                b.sink.end(b)
            return
        if self._autoplace_setup():
            return
        if b.awaiting_flag or b.awaiting_trap:
            return
        self._check_handoff()
        if not self._human(b.active.team):
            self.enemy_timer += dt
            if self.enemy_timer >= ENEMY_DELAY:
                self.enemy_timer = 0
                ai.take_turn(b, b.active)
        else:
            self.enemy_timer = 0

    # ------------------------------------------------------------------ #
    # battle logic                                                       #
    # ------------------------------------------------------------------ #
    def _human(self, team):
        return self.controllers.get(team) == "human"

    @property
    def me(self):
        """The team whose eyes the board is drawn through: the active team on a human's turn,
        else whoever looked last."""
        b = self.battle
        if b.winner is None and self._human(b.active.team):
            self._viewer = b.active.team
        return self._viewer

    @property
    def foe(self):
        return "enemy" if self.me == "player" else "player"

    def _is_player_turn(self):
        b = self.battle
        return bool(b and b.winner is None and self._handoff is None
                    and self._human(b.active.team))

    def _autoplace_setup(self):
        """A side no person controls gets its flag planted and its traps skipped, so the fight
        can begin."""
        b = self.battle
        if b.awaiting_flag and not self._human("player"):
            tiles = [(x, y) for x in own_half("player", b.board.cols) for y in range(b.board.rows)
                     if b.can_plant_flag((x, y))]
            b.plant_flag(random.choice(tiles) if tiles else (0, b.board.rows // 2))
            return True
        if b.awaiting_trap and not self._human("player"):
            b.trap_setup_queue.clear()
            return True
        return False

    def _check_handoff(self):
        """With two people at one screen, hide the board between their turns."""
        team = self.battle.active.team
        if (self._human("player") and self._human("enemy") and self._human(team)
                and team != self._seat and self._handoff is None):
            self._handoff = team

    def _observers(self):
        return vision.observers(self.battle, self.view_squad, self.me)

    def _enemy_visible(self, u):
        return vision.enemy_visible(self.battle, self._obs, u)

    def _tile_at_px(self, px):
        return self.view.cell_at(px)

    def tutorial_key(self):
        return "battle"

    def _disk_height_options(self, actor, tile):
        b = self.battle
        caster_z = b.elevation(actor)
        pit_z = b.board.elevation_at(tile)
        raw = {0, caster_z, pit_z}
        sorted_z = sorted(raw, reverse=True)
        opts = []
        for z in sorted_z:
            tags = []
            if z == 0:
                tags.append("Ground")
            if z == caster_z:
                tags.append("Caster")
            if z == pit_z and pit_z != 0:
                tags.append("Pit floor")
            tag_str = f" ({'/'.join(tags)})" if tags else ""
            opts.append((z, f"z={z}{tag_str}"))
        return opts

    def _click(self, px):
        b = self.battle
        if b.winner is not None:
            self.on_battle_end(b)
            return
        if self._handoff is not None:
            self._seat, self._handoff = self._handoff, None
            self._centered_on = None
            return

        if getattr(self, "height_prompt", None) is not None:
            for key, rect in self.buttons:
                if rect.collidepoint(px):
                    if key == "prompt_cancel":
                        self.height_prompt = None
                        return
                    elif isinstance(key, tuple) and key[0] == "prompt_height":
                        z = key[1]
                        prompt = self.height_prompt
                        self.height_prompt = None
                        prompt["action"].execute(b, b.active, prompt["tile"], elevation=z)
                        self.aim_action = None
                        self._after_player_action()
                        return
            self.height_prompt = None
            return
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "inspect_toggle":
                    self.inspect_open = not self.inspect_open
                elif key == "magic_back":
                    self.show_magic_menu = False
                    self.aim_action = None
                elif key == "magic_menu":
                    self.show_magic_menu = True
                    self.aim_action = None
                elif key == "toggle_blocked":
                    self.show_blocked_actions = not self.show_blocked_actions
                elif key == "tab_combat":
                    self.action_tab = "combat"
                    self.actions_scroll = 0
                    self.aim_action = None
                elif key == "tab_utility":
                    self.action_tab = "utility"
                    self.actions_scroll = 0
                    self.aim_action = None
                elif key == "export_state":
                    self._export_state()
                else:
                    self._action_click(key)
                return

        tile = self._tile_at_px(px)
        if tile is None:
            return

        if b.awaiting_flag:
            if b.can_plant_flag(tile):
                b.plant_flag(tile)
            return

        trapper = b.awaiting_trap
        if trapper:
            if b.can_plant_trap(trapper, tile):
                b.plant_trap(trapper, tile)
            return

        self._obs = self._observers()
        clicked = b.unit_at(tile, include_downed=True)
        if clicked is not None and clicked.team == self.foe \
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
                if getattr(self.aim_action, "spell_id", None) == "floating_disk":
                    opts = self._disk_height_options(actor, tile)
                    if len(opts) > 1:
                        self.height_prompt = {"action": self.aim_action, "tile": tile, "options": opts}
                        return
                    else:
                        elev = opts[0][0] if opts else 0
                        self.aim_action.execute(b, actor, tile, elevation=elev)
                else:
                    self.aim_action.execute(b, actor, tile)
                self.aim_action = None
                self._after_player_action()
            return

        if self.aim_action is not None:
            if clicked is None or not self.aim_action.can(b, actor, clicked):
                clicked = next((u for u in b.units
                                if tile in b.cells_of(u)
                                and self.aim_action.can(b, actor, u)), clicked)
            if clicked is not None and self.aim_action.can(b, actor, clicked):
                self.aim_action.execute(b, actor, clicked)
                self.aim_action = None
                self._after_player_action()
            return

        if clicked is not None and clicked.alive and clicked.team == self.foe:
            if self._armed is not clicked:
                self._armed = clicked
                return
            if actions.ATTACK.can(b, actor, clicked):
                actions.ATTACK.execute(b, actor, clicked)
                self._armed = None
                self._after_player_action()
            return
        if clicked is None or not clicked.alive:        # a body on the floor does not block the cell
            dest = self._anchor_of_click(actor, tile)
            if dest is not None:
                actions.MOVE.execute(b, actor, dest)
                self._after_player_action()

    def _step_with_arrows(self):
        """One step in the direction the arrows of the chord add up to: two
        perpendicular arrows pressed together make a diagonal, opposite ones cancel."""
        keys, self._chord = self._chord, set()
        dx = sum(ARROW_STEPS[k][0] for k in keys)
        dy = sum(ARROW_STEPS[k][1] for k in keys)
        b = self.battle
        if ((dx, dy) == (0, 0) or not self._is_player_turn() or self.aim_action is not None
                or b.awaiting_flag or b.awaiting_trap):
            return
        actor = b.active
        dest = (actor.pos[0] + dx, actor.pos[1] + dy)
        if dest in b.reachable(actor):
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

    def _confirm_armed_attack(self):
        b = self.battle
        target = self._armed
        if target is None or not actions.ATTACK.can(b, b.active, target):
            return
        actions.ATTACK.execute(b, b.active, target)
        self._armed = None
        self._after_player_action()

    def _hotkey_action(self, idx):
        if idx < len(self._hotkey_actions):
            self._action_click(self._hotkey_actions[idx])

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
        if b.is_ctf:
            b.check_objective()
        if b.winner is not None or not self._human(b.active.team):
            return
        act = b.active
        if act.ap < 1 and not b.reachable(act):
            self.aim_action = None
            b.end_turn()

    def _hovered_anchor(self):
        if not self._is_player_turn() or self.aim_action is not None:
            return None
        tile = self._tile_at_px(self.mouse)
        if tile is None:
            return None
        return self._anchor_of_click(self.battle.active, tile)

    @staticmethod
    def _aim_kind(action):
        if action in (actions.STABILIZE, actions.FIRST_AID, actions.DRINK_POTION,
                      actions.MOUNT, actions.WAKE_UP):
            return "heal"
        if action in (actions.DEMORALIZE, actions.EAT_CORPSE):
            return "demo"
        if action in (actions.ATTACK, actions.ATTACK_TONGUE):
            return "attack"
        if action in (actions.CLIMB, actions.DROP, actions.JUMP,
                      actions.SWIM, actions.DISMOUNT, actions.PUSH):
            return "move"
        if getattr(action, "spell_id", None) is not None:
            return "spell"
        return "throw"

    def _hint_message(self):
        if not self._is_player_turn():
            return None, None
        spell_id = getattr(self.aim_action, "spell_id", None)
        if self.aim_action is actions.ATTACK:
            return "click a highlighted enemy to Attack (Flank: ally on opposite side grants +2 to hit)", board_style.ATK_HL
        elif self.aim_action is actions.DEMORALIZE:
            return "click a purple enemy to Demoralize", board_style.DEMO_HL
        elif self.aim_action is actions.ATTACK_TONGUE:
            return "click an enemy in tongue range", board_style.ATK_HL
        elif self.aim_action is actions.THROW:
            return "click an enemy in the orange range", board_style.THROW_HL
        elif self.aim_action in (actions.STABILIZE, actions.FIRST_AID):
            return "click an adjacent downed ally (green)", board_style.OK
        elif self.aim_action is actions.DRINK_POTION:
            return "click self or damaged ally to drink potion", board_style.OK
        elif self.aim_action is actions.MOUNT:
            return "click an adjacent allied Centaur to mount", board_style.OK
        elif self.aim_action is actions.DISMOUNT:
            return "click an adjacent free cell to dismount", board_style.MOVE_HL
        elif self.aim_action is actions.WAKE_UP:
            return "click an adjacent sleeping ally to wake them", board_style.OK
        elif self.aim_action is actions.EAT_CORPSE:
            return "click an adjacent dead enemy corpse to devour", board_style.DEMO_HL
        elif self.aim_action is actions.PUSH:
            return "click an adjacent unit to push", board_style.MOVE_HL
        elif self.aim_action is actions.CLIMB:
            return "click an adjacent ledge cell to climb", board_style.MOVE_HL
        elif self.aim_action is actions.DROP:
            return "click a cell below to drop down", board_style.MOVE_HL
        elif self.aim_action is actions.JUMP:
            return "click a cell to jump over a pit", board_style.MOVE_HL
        elif self.aim_action is actions.SWIM:
            return "click a water cell within reach to swim", board_style.MOVE_HL
        elif spell_id == "sleep":
            return "click enemy within 6 cells to cast Sleep", T.BRASS
        elif spell_id == "magic_missile":
            return "click enemy within 6 cells to cast Magic Missile", T.BRASS
        elif spell_id == "light_globe":
            return "click empty cell within 6 cells to conjure Light Globe", T.BRASS
        elif spell_id == "floating_disk":
            return "click empty cell within 6 cells to summon Floating Disk", T.BRASS
        elif spell_id is not None:
            return f"click target within range to cast {self.aim_action.name}", T.BRASS
        elif actions.FLEE.available(self.battle, self.battle.active):
            return "at the map edge: you can Flee the fight", board_style.OK
        elif self.battle.mopping_up:
            return ("enemies down  ·  stabilize the downed or space "
                    "to let the counter run"), board_style.WARN
        elif self.battle.is_ctf:
            return ("grab the enemy flag and bring it home to win  ·  "
                    "guard your own, and whoever's carrying it"), T.TX_MUTED
        else:
            return "green square: move  ·  enemy: attack  ·  space: end", T.TX_MUTED

    def _cell_rect(self, cx, cy):
        return self.view.cell_rect(cx, cy)

    def _unit_rect(self, u):
        r = self.view.cell_rect(*u.pos)
        t = self.view.tile
        return pygame.Rect(r.x, r.y, t * u.footprint, t * u.footprint)

    # ------------------------------------------------------------------ #
    # drawing                                                            #
    # ------------------------------------------------------------------ #
    def draw(self, screen):
        screen.fill(T.TABLE)
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
        self._draw_tactical(screen)
        if self.battle.awaiting_flag:
            self._draw_flag_setup(screen)
        if self.battle.awaiting_trap:
            self._draw_trap_setup(screen)
        self.fx.draw(screen, self.F, self.view.rect)
        screen.set_clip(clip)

        self._draw_initiative(screen)
        self._draw_panel(screen)
        self._draw_log(screen)
        if self.battle.winner:
            self._draw_winner(screen)
        else:
            self._draw_tooltips(screen)
        if self._handoff is not None:
            self._draw_handoff(screen)

    def _draw_grid(self, screen):
        b = self.battle.board
        terrain = {
            "cols": b.cols, "rows": b.rows, "walls": b.walls,
            "elevation": b.elevation, "water": getattr(b, "water", set()),
            "ropes": getattr(b, "ropes", set()),
        }
        board_render.draw_terrain(screen, self.F, self.view, terrain)

    def _draw_ground(self, screen):
        props = []
        for o in self.battle.ground:
            if o.pos not in self._visible:
                continue
            kind = ("torch" if o.is_torch else
                    "chest" if getattr(o, "is_chest", False) else
                    "relic" if getattr(o, "is_relic", False) else
                    "trap" if getattr(o, "is_trap", False) else
                    "disk" if getattr(o, "is_disk", False) else "item")
            props.append({
                "kind": kind,
                "pos": o.pos,
                "trap_type": getattr(o, "trap_type", ""),
                "elevation": getattr(o, "elevation", 0),
            })
        board_render.draw_props(screen, self.F, self.view, props)

    def _draw_creatures(self, screen):
        for cr in self.battle.creatures:
            if cr.pos in self._visible:
                board_render.draw_creature(screen, self.F, self._cell_rect(*cr.pos), cr.token)

    def _draw_units(self, screen):
        b = self.battle
        for u in b.units:
            if u.dead or u.fled:
                continue
            if u.team == self.foe and not self._enemy_visible(u) \
                    and not (self._is_player_turn() and u.alive
                             and actions.ATTACK.can(b, b.active, u)):
                continue
            r = self.fx.rect_for(u, self._unit_rect(u))
            focus = "armed" if (self.inspect is u and self._armed is u) else ("inspect" if self.inspect is u else None)
            flag = next((t for t, c in b.flag_carrier.items() if c is u), None) if b.is_ctf else None
            tok = {
                "team": u.team,
                "active": u is b.active and b.winner is None,
                "race": u.race["name"],
                "portrait_id": getattr(u, "portrait_id", None),
                "token": u.token,
                "hp_frac": max(0, u.hp) / u.hp_max,
                "torch": u.has_torch,
                "defending": u.defending,
                "ferocity": getattr(u, "ferocity_pending", False),
                "demoralized": u.demoralized,
                "flag": flag,
                "focus": focus,
                "downed": u.downed,
                "dying": f"{u.death_clock}/{data.DYING_TURNS}" if u.dying else None,
                "broken": u.broken,
            }
            board_render.draw_unit(screen, self.F, r, tok)

    def _draw_pennant(self, screen, pos, color):
        board_render.draw_pennant(screen, self._cell_rect(*pos), color)

    def _draw_flags(self, screen):
        for team in self.battle.flags:
            pos = self.battle.flag_pos(team)
            if pos is None:
                continue
            if team == self.foe and pos not in self._visible:
                continue
            self._draw_pennant(screen, pos, board_render.team_color(team))

    def _draw_flag_setup(self, screen):
        board = self.battle.board
        valid = [
            (x, y) for x in own_half("player", board.cols)
            for y in range(board.rows) if (x, y) not in board.walls
        ]
        hover = self._tile_at_px(self.mouse)
        if hover is not None and not self.battle.can_plant_flag(hover):
            hover = None
        banner = "CAPTURE THE FLAG  ·  click a cell in your half to plant your flag"
        board_render.draw_placement(screen, self.F, self.view, valid, hover, banner)

    def _draw_trap_setup(self, screen):
        board = self.battle.board
        trapper = self.battle.awaiting_trap
        candidates = [
            p for c in self.battle.cells_of(trapper) for p in board.neighbors(c)
            if board.in_bounds(p) and self.battle.can_plant_trap(trapper, p)
        ]
        hover = self._tile_at_px(self.mouse)
        if hover is not None and not self.battle.can_plant_trap(trapper, hover):
            hover = None
        trap_type = "Bear Trap" if "Bear Trap" in trapper.inventory else "Alarm Trap"
        banner = f"TRAP PLACEMENT  ·  {trapper.name} is placing a {trap_type}"
        board_render.draw_placement(screen, self.F, self.view, candidates, hover, banner)

    def _draw_tactical(self, screen):
        b = self.battle
        if not self._is_player_turn():
            return
        actor = b.active

        if self.aim_action is not None:
            kind = self._aim_kind(self.aim_action)
            color = board_style.aim_color(kind)
            highlight_cells = [
                pos for pos in self.aim_action.highlight_cells(b, actor)
                if 0 <= pos[0] < b.board.cols and 0 <= pos[1] < b.board.rows
            ]
            board_render.tint_cells(screen, self.view, highlight_cells, color, 46)
            target_rects = [
                self._unit_rect(u) for u in self.aim_action.highlight_targets(b, actor)
                if u.team == actor.team or self._enemy_visible(u)
            ]
            board_render.draw_rings(screen, target_rects, color)
            return

        reach_cells = b.reachable_cells(actor)
        board_render.draw_reach(screen, self.view, reach_cells)

        atk_rects = [
            self._unit_rect(u) for u in b.units
            if u.alive and u.team == self.foe and (actions.ATTACK.can(b, actor, u)
                                                  or actions.ATTACK_TONGUE.can(b, actor, u))
        ]
        board_render.draw_rings(screen, atk_rects, board_style.ATK_HL)

        if len(actor.path) >= 2:
            pts = board_render.path_points(self.view, actor.path, actor.footprint)
            board_render.draw_trail(screen, pts)

        anchor = self._hovered_anchor()
        if anchor is not None and anchor != actor.pos:
            route = b.path_to(actor, anchor)
            if len(route) >= 2:
                pts = board_render.path_points(self.view, route, actor.footprint)
                cost = b.reachable(actor).get(anchor)
                board_render.draw_route(screen, self.F, pts, cost)

    def _draw_initiative(self, screen):
        b = self.battle
        entries = []
        for u in b.order:
            if not (u.alive or u.dying):
                continue
            known = u.team == self.me or self._enemy_visible(u)
            entries.append({
                "name": u.name.split()[0] if known else "Enemy",
                "team": u.team,
                "known": known,
                "active": u is b.active and b.winner is None,
                "race": u.race["name"],
                "portrait_id": getattr(u, "portrait_id", None),
                "token": u.token if known else "?",
                "hp_frac": max(0, u.hp) / u.hp_max,
                "dying": f"{u.death_clock}/{data.DYING_TURNS}" if u.dying else None,
            })
        battle_panel.draw_initiative(screen, self.F, self._L["init"], entries)

    def _draw_panel(self, screen):
        b = self.battle
        pr = self._L["panel"]
        F = self.F

        title = ("VICTORY" if b.winner else "AID THE DOWNED" if b.mopping_up else f"Round {b.round_no}")
        state = "victory" if b.winner else "mopping" if b.mopping_up else None
        vision_active = self._is_player_turn() and not self.view_squad
        head_r = pygame.Rect(pr.x, pr.y, pr.w, battle_panel.TITLE_H)
        battle_panel.draw_title(screen, F, head_r, title, state, vision_active)

        cur_y = head_r.bottom + T.S * 2
        if b.winner is None:
            act = b.active
            card_r = pygame.Rect(pr.x, cur_y, pr.w, battle_panel.TURN_CARD_H)
            marks = "  ".join(x for x in (
                "defending" if act.defending else "",
                "demoralized" if act.demoralized else "") if x)
            extra = "".join((
                f"   arrows {act.ammo}" if act.needs_ammo else "",
                f"   kit {act.first_aid_charges}x" if act.first_aid_charges else "",
                f"   {marks}" if marks else "",
            ))
            stats = f"HP {max(act.hp, 0)}/{act.hp_max}   AC {act.ac}   MD {act.mental_defense}" + extra
            vd = vision.vision_desc(act) if not self.view_squad else "vision: whole squad  [L]"
            card_data = {
                "name": act.name,
                "race": act.race["name"],
                "portrait_id": act.portrait_id,
                "token": act.token,
                "mine": act.team == self.me,
                "stats": stats,
                "ap": act.ap,
                "ap_max": 2,
                "walk": (act.moved, act.speed) if act.walking else None,
                "note": None if act.walking or act.team != self.me else vd,
            }
            battle_panel.draw_turn_card(screen, F, card_r, card_data)
            cur_y = card_r.bottom + T.S * 2

            hint_r = pygame.Rect(pr.x, cur_y, pr.w, battle_panel.HINT_H)
            msg, col = self._hint_message()
            battle_panel.draw_hint(screen, F, hint_r, msg, col)
            cur_y = hint_r.bottom + T.S * 2
        else:
            card_r = pygame.Rect(pr.x, cur_y, pr.w, battle_panel.VICTORY_CARD_H)
            vdata = {
                "won": b.winner == self.me,
                "stabilized": [u.name for u in b.units if u.team == self.me and u.status in ("stable", "broken")],
                "fallen": [u.name for u in b.units if u.team == self.me and u.status == "dead"],
            }
            battle_panel.draw_victory_card(screen, F, card_r, vdata)
            cur_y = card_r.bottom + T.S * 2

        self.buttons = []

        insp = self.inspect
        if insp and insp.team == self.foe and not self._enemy_visible(insp):
            insp = None
        if insp and (insp.dead or insp.fled):
            insp = None
        who = insp or (b.active if b.winner is None else None)

        inspect_h = 0
        if who is not None:
            inspect_h = battle_panel.inspect_height(
                self.inspect_open, who is insp and self._armed is insp, sheet_height("compact")
            )

        inspect_top = pr.bottom - inspect_h
        actions_h = max(40, inspect_top - (T.S if inspect_h else 0) - cur_y)
        actions_rect = pygame.Rect(pr.x, cur_y, pr.w, actions_h)

        if b.winner is None:
            self._draw_actions(screen, actions_rect)

        if who is not None:
            inspect_rect = pygame.Rect(pr.x, inspect_top, pr.w, inspect_h)
            self._draw_inspect(screen, inspect_rect, who, insp)

    def _draw_actions(self, screen, area_rect):
        F = self.F
        b = self.battle
        my_turn = b.winner is None and self._is_player_turn()
        act = b.active

        if getattr(self, "height_prompt", None) is not None:
            self.buttons.extend(
                battle_panel.draw_height_prompt(screen, F, area_rect, self.height_prompt["options"])
            )
            return

        if getattr(self, "show_magic_menu", False):
            btn_back = pygame.Rect(area_rect.x, area_rect.y, area_rect.w, battle_panel.BACK_H)
            battle_panel.draw_back_bar(screen, F, btn_back, "< Back to Actions")
            self.buttons.append(("magic_back", btn_back))

            scroll_y = btn_back.bottom + T.S // 2
            scroll_rect = pygame.Rect(area_rect.x, scroll_y, area_rect.w, max(20, area_rect.bottom - scroll_y))
            self._actions_scroll_rect = scroll_rect

            items_data = []
            for sp_id in act.char.spells_known:
                action = actions.CastSpellAction(sp_id)
                enabled = my_turn and action.available(b, act)
                armed = getattr(self.aim_action, "id", None) == action.id
                label = action.name if not armed else f"{action.name}: target"
                items_data.append({
                    "key": action,
                    "label": label,
                    "enabled": enabled,
                    "armed": armed,
                    "icon": None,
                    "cost": action.cost,
                    "cost_style": "count",
                    "aim": "spell",
                    "center": False,
                })

            res = battle_panel.draw_action_list(screen, F, scroll_rect, items_data, self.actions_scroll)
            self.actions_scroll = res["scroll"]
            self._actions_max_scroll = res["max_scroll"]
            self.buttons.extend(res["buttons"])
            return

        tab_r = pygame.Rect(area_rect.x, area_rect.y, area_rect.w, battle_panel.TAB_H)
        self.buttons.extend(
            battle_panel.draw_action_tabs(screen, F, tab_r, self.action_tab, self.show_blocked_actions, self.mouse)
        )

        tab_actions = actions.COMBAT_ACTIONS if self.action_tab == "combat" else actions.UTILITY_ACTIONS
        contextual = (actions.CLIMB, actions.DROP, actions.SWIM)

        visible_items = []
        if self.action_tab == "combat" and act.char.spells_known:
            visible_items.append({
                "key": "magic_menu",
                "label": "Cast Spell",
                "enabled": my_turn,
                "armed": False,
                "icon": None,
                "cost": 0,
                "cost_style": "pips",
                "aim": None,
                "center": True,
            })

        hotkey_i = 0
        self._hotkey_actions = []

        for action in tab_actions:
            applies, reason = action.applicable(b, act)
            if action in contextual and not (my_turn and action.available(b, act)):
                continue
            if not applies and not self.show_blocked_actions:
                continue

            enabled = applies and (my_turn if action is actions.END else (my_turn and action.available(b, act)))
            armed = action.aimed and self.aim_action is action

            hotkey_num = None
            if hotkey_i < 9:
                hotkey_i += 1
                hotkey_num = hotkey_i
                self._hotkey_actions.append(action)

            label = action.name if not armed else f"{action.name}: click the target"
            if not applies:
                label += f" ({reason})"
            if hotkey_num is not None:
                label = f"[{hotkey_num}] {label}"

            visible_items.append({
                "key": action,
                "label": label,
                "enabled": enabled,
                "armed": armed,
                "icon": action.id,
                "cost": action.cost,
                "cost_style": "pips",
                "aim": self._aim_kind(action),
                "center": False,
            })

        scroll_y = area_rect.y + battle_panel.TAB_H + T.S // 2
        scroll_rect = pygame.Rect(area_rect.x, scroll_y, area_rect.w, max(20, area_rect.bottom - scroll_y))
        self._actions_scroll_rect = scroll_rect

        res = battle_panel.draw_action_list(screen, F, scroll_rect, visible_items, self.actions_scroll)
        self.actions_scroll = res["scroll"]
        self._actions_max_scroll = res["max_scroll"]
        self.buttons.extend(res["buttons"])

    def _draw_inspect(self, screen, rect, who, insp):
        F = self.F
        armed = who is insp and self._armed is insp
        label = "INSPECT" if who is insp else "ACTIVE UNIT"
        head, cur_y = battle_panel.draw_inspect_header(screen, F, rect, label, self.inspect_open, armed)
        self.buttons.append(("inspect_toggle", head))

        if not self.inspect_open:
            return

        ch = unit_to_ch(who)
        card_rect = pygame.Rect(rect.x, cur_y, rect.w - T.S, 0)
        h, tooltip = draw_sheet_card(screen, F, card_rect, ch, density="compact", mouse=self.mouse)
        if tooltip:
            ui_primitives.draw_tooltip(screen, F, tooltip, self.mouse)

    def _log_color(self, line):
        return battle_panel.log_color(line)

    def _draw_log(self, screen):
        F = self.F
        well = self._L["log"]
        all_lines = self.battle.log_lines
        total = len(all_lines)
        rows = battle_panel.log_rows(well)

        added = max(0, total - self._log_len_seen)
        if self.log_scroll > 0:
            self.log_scroll += added
        self._log_len_seen = total
        max_scroll = max(0, total - rows)
        self.log_scroll = min(self.log_scroll, max_scroll)

        end = total - self.log_scroll
        start = max(0, end - rows)
        lines = all_lines[start:end]

        export_r = battle_panel.draw_log(screen, F, well, lines, self.log_scroll)
        self.buttons.append(("export_state", export_r))

    def _draw_tooltips(self, screen):
        mpos = pygame.mouse.get_pos()
        hovered_action = None
        btn_rect = None
        for action, rect in self.buttons:
            if isinstance(action, actions.Action) and rect.collidepoint(mpos):
                hovered_action = action
                btn_rect = rect
                break

        desc = getattr(hovered_action, "desc", "") if hovered_action else ""
        if desc and btn_rect:
            battle_panel.draw_action_tip(screen, self.F, btn_rect, desc)

    def _draw_winner(self, screen):
        txt = self._winner_text()
        battle_panel.draw_winner(screen, self.F, self.view.rect.center, txt)

    def _winner_text(self):
        winner = self.battle.winner
        if self._human("player") and self._human("enemy"):
            return "Player 1 won" if winner == "player" else "Player 2 won"
        if self._human(winner):
            return "You won"
        return "The AI won"

    def _draw_handoff(self, screen):
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        seat = "Player 1" if self._handoff == "player" else "Player 2"
        ui_primitives.text(screen, self.F["titleb"], f"{seat}'s turn", (W // 2, H // 2 - 24), T.TX, center=True)
        ui_primitives.text(screen, self.F["body"], "Click when only you are looking at the screen",
                           (W // 2, H // 2 + 12), T.TX_MUTED, center=True)

    def _export_state(self):
        b = self.battle
        os.makedirs(DEBUG_EXPORT_DIR, exist_ok=True)
        path = os.path.join(DEBUG_EXPORT_DIR, f"battle_{int(time.time())}.json")
        snapshot = {
            "round": b.round_no,
            "turn_idx": b.turn_idx,
            "winner": b.winner,
            "lethal": b.lethal,
            "arena": b.arena,
            "is_ctf": b.is_ctf,
            "ambient_light": b.ambient_light,
            "board": {
                "cols": b.board.cols,
                "rows": b.board.rows,
                "walls": sorted(b.board.walls),
                "elevation": {f"{x},{y}": z for (x, y), z in b.board.elevation.items()},
                "water": sorted(getattr(b.board, "water", set())),
                "deep_water": sorted(getattr(b.board, "deep_water", set())),
            },
            "units": [
                {
                    "name": u.name,
                    "team": u.team,
                    "pos": list(u.pos),
                    "footprint": u.footprint,
                    "status": u.status,
                    "hp": u.hp,
                    "hp_max": u.hp_max,
                    "ap": u.ap,
                    "alive": u.alive,
                    "downed": u.downed,
                    "conditions": [c.id for c in u.conditions],
                    "active": u is b.active,
                }
                for u in b.units
            ],
            "ground": [{"pos": list(o.pos), "kind": o.kind} for o in b.ground],
            "log": list(b.log_lines),
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, indent=2, default=str)
        b.log(f"State exported to {os.path.relpath(path)}")

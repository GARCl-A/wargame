"""Battle screen: the tactical grid, the initiative strip, the action panel and
the log. Drawing delegates to `board_render` (playfield) and `battle_panel`
(chrome); rules live in `battle` / `actions` / `vision`; combat juice
(floaters, hit reactions) lives in `battle_fx`."""

import json
import os
import random
import time

import pygame

from . import actions, ai, intel, settings, vision
from .battle_draw import BattleDrawMixin
from .battle_fx import BattleFX
from .board import cells
from .foe_card import foe_card
from .lighting import LightRenderer
from .scenario import own_half
from .screen import Screen
from .ui import board_style, foe_panel
from .ui.board_style import BoardView
from .ui.sheet_card import sheet_height
from .ui.tokens import T

ENEMY_DELAY = 450  # ms between AI actions

FELLED_STREAK_SECONDS = 1.0     # longest pause that still counts as the same run of clicks
ARROW_STEPS = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
               pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}


DEBUG_EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug_exports")


class BattleScreen(BattleDrawMixin, Screen):
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
        self.inspect_scroll = 0
        self._foe_inspect_rect = None
        self._foe_max_scroll = 0
        self._armed = None                    # enemy a repeat click on it will now attack
        self._felled = None                   # (actor, body, time of last click): a click streak that outlived its target
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
        self._skip_traps_rect = None
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
                b = self.battle
                if actions.DEFEND.can(b, b.active):
                    actions.DEFEND.execute(b, b.active)
                b.end_turn()
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
            foe_rect = getattr(self, "_foe_inspect_rect", None)
            log_rect = getattr(self, "_L", None) and self._L.get("log")
            if act_rect and act_rect.collidepoint(self.mouse):
                max_s = getattr(self, "_actions_max_scroll", 0)
                self.actions_scroll = max(0, min(max_s, self.actions_scroll - event.y * 34))
            elif foe_rect and foe_rect.collidepoint(self.mouse):
                max_s = getattr(self, "_foe_max_scroll", 0)
                self.inspect_scroll = max(0, min(max_s, self.inspect_scroll - event.y * 20))
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

    def _foe_card(self, u):
        return foe_card(intel.known_fields(self.battle, self.me, u))

    def _inspect_body_h(self, who):
        """Height of what the INSPECT panel shows for `who`: a foe's card grows as its fields open."""
        if who.team == self.foe:
            return foe_panel.card_height(self._foe_card(who))
        return sheet_height("compact")

    def _hp_bar(self, u):
        """A foe's health shows in steps (what `intel` lets its viewer know); your own is exact."""
        if u.team == self.foe:
            return {"hp_frac": intel.health_steps(u) / intel.STEPS, "hp_steps": intel.STEPS}
        return {"hp_frac": max(0, u.hp) / u.hp_max, "hp_steps": None}

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

        if (b.awaiting_trap and self._skip_traps_rect is not None
                and self._skip_traps_rect.collidepoint(px)):
            b.skip_traps()
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
            if self.inspect is not clicked:
                self.inspect_scroll = 0
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
                self._note_felled(actor, clicked)
                self.aim_action = None
                self._after_player_action()
            return

        if clicked is not None and clicked.alive and clicked.team == self.foe:
            if self._armed is not clicked:
                self._armed = clicked
                return
            if actions.ATTACK.can(b, actor, clicked):
                actions.ATTACK.execute(b, actor, clicked)
                self._note_felled(actor, clicked)
                self._armed = None
                self._after_player_action()
            return
        if clicked is not None and self._felled_streak(actor, clicked):
            return
        if clicked is None or not clicked.alive:        # a body on the floor does not block the cell
            dest = self._anchor_of_click(actor, tile)
            if dest is not None:
                actions.MOVE.execute(b, actor, dest)
                self._after_player_action()

    def _note_felled(self, actor, target):
        if not target.alive:
            self._felled = (actor, target, time.monotonic())

    def _felled_streak(self, actor, body):
        """True while the player keeps clicking the body they just brought down: those
        clicks were meant for the attack, and a late one would walk onto the cell."""
        now = time.monotonic()
        streak = (self._felled is not None and self._felled[:2] == (actor, body)
                  and now - self._felled[2] <= FELLED_STREAK_SECONDS)
        self._felled = (actor, body, now) if streak else None
        return streak

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
            return "green square: move  ·  enemy: attack  ·  space: defend and end", T.TX_MUTED

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

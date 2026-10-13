"""Everything BattleScreen paints: the board, the initiative strip, the action panel, the log and the overlays.

Mixed into `battle_screen.BattleScreen`; input and turn flow stay there."""

import pygame

from . import actions, data, vision
from .scenario import own_half
from .ui import battle_panel, board_render, board_style, foe_panel
from .ui import primitives as ui_primitives
from .ui.board_style import battle_layout
from .ui.sheet_card import draw_sheet as draw_sheet_card
from .ui.sheet_card import unit_to_ch
from .ui.tokens import T


class BattleDrawMixin:
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
                **self._hp_bar(u),
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
        self._skip_traps_rect = pygame.Rect(self.view.rect.right - 168, self.view.rect.y + 38, 160, 28)
        ui_primitives.draw_button(screen, self.F, self._skip_traps_rect, "PLACE NOTHING", mpos=self.mouse)

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
                **self._hp_bar(u),
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
            desired_body_h = self._inspect_body_h(who)
            avail_panel = pr.h - (cur_y - pr.y)
            max_inspect_total = max(battle_panel.INSPECT_HEAD_H + 40, avail_panel - 180)
            inspect_h = battle_panel.inspect_height(
                self.inspect_open, who is insp and self._armed is insp, desired_body_h
            )
            inspect_h = min(inspect_h, max_inspect_total)

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

        if who.team == self.foe:
            card = self._foe_card(who)
            card_h = max(40, rect.bottom - cur_y)
            area = pygame.Rect(rect.x, cur_y, rect.w - T.S, card_h)
            self._foe_inspect_rect = area
            self._foe_max_scroll = max(0, foe_panel.card_height(card) - card_h)
            tooltip = foe_panel.draw_foe_card(screen, F, area, card, self.mouse, self.inspect_scroll)
        else:
            card_rect = pygame.Rect(rect.x, cur_y, rect.w - T.S, 0)
            _, tooltip = draw_sheet_card(screen, F, card_rect, unit_to_ch(who), density="compact", mouse=self.mouse)
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
        scroll_r = getattr(self, "_actions_scroll_rect", None)
        for action, rect in self.buttons:
            if isinstance(action, actions.Action) and rect.collidepoint(mpos):
                if scroll_r is not None and not scroll_r.collidepoint(mpos):
                    continue
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

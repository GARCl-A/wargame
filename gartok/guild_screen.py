"""Guild screen: the central administrative and character hub of the guild.

Roster-and-character view across all active bands. Displays member status,
loadout, combat metrics, command posts, and progression with support for
geographically dispersed groups.
"""

import pygame

from . import artwork, data, factions, items, magic, progression, talents
from .combatant import Combatant
from .group import BASE_CAPACITY
from .screen import Screen
from .theme import set_pointer
from .ui.primitives import (caps, contained, draw_button, draw_tooltip, ellipsize, hline,
                            panel, scrollbar, section, smooth_circle, tabs, text, tracked, wrap,
                            token_badge)
from .ui.sheet_card import _to_hit, _weapon_line, draw_row, unit_to_ch
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

TABS = (("members", "MEMBERS"), ("reputations", "REPUTATIONS"))

LIST_MIN, LIST_MAX = 280, 380         # roster column width clamps

# --------------------------------------------------------------------------- #
# High-contrast, accessible cRPG palette (enhanced readability on dark theme) #
# --------------------------------------------------------------------------- #
TX_HIGH = (245, 246, 250)      # primary headings, key values, member names
TX_MED  = (185, 192, 205)      # secondary descriptions, subtitles, labels (crisp)
TX_DIM  = (140, 146, 160)      # captions, structural metadata
BORDER_SUBTLE = (48, 52, 62)   # dark steel frame outlines
BORDER_ACTIVE = T.BRASS        # warm gold reserved for active selection and CTAs


def _draw_metric_chip(screen, F, rect, label, value, mouse, tip):
    """Draws a compact, aligned metric cell inside the tactical weapon profile."""
    hov = rect.collidepoint(mouse)
    pygame.draw.rect(screen, T.STEEL_HI if hov else T.STEEL, rect)
    pygame.draw.rect(screen, BORDER_ACTIVE if hov else BORDER_SUBTLE, rect, 1)
    caps(screen, F["micro"], label, (rect.x + 6, rect.centery), TX_DIM)
    text(screen, F["bodyb"], value, (rect.right - 8, rect.centery - 7), TX_HIGH, right=True)
    return hov, tip


class GuildScreen(Screen):
    native = True                        # app draws us straight to the window

    def __init__(self, fonts, guild, on_back, on_level=None, on_manage=None, on_bank=None):
        super().__init__()
        self.fonts = fonts
        self._F = None
        self.guild = guild
        self.roster = guild.roster
        self.battles_won = guild.battles_won
        self.on_back = on_back
        self.on_level = on_level             # open the level screen for a member
        self.on_manage = on_manage           # open the Manage Gear screen
        self.on_bank = on_bank               # open local bank/storage screen
        self.tab = "members"                  # "members" | "reputations"
        pending = [u for u in self.roster if u.pending_picks]
        self.member = pending[0] if pending else (self.roster[0] if self.roster else None)

        self.tab_hits = []                  # [(rect, key)]
        self.member_hits = []              # [(rect, unit)]
        self.buttons = []                  # [(key, rect)]
        self.accordion_hits = []           # [(rect, group)]
        self.filter_hits = []              # [(rect, filter_key)]

        self._hot = False
        self.tooltip = None
        self._rep_scroll = 0
        self._rep_max_scroll = 0
        self._roster_scroll = 0
        self._roster_max_scroll = 0

        self.collapsed_groups = set()      # set of group gids currently folded
        self.filter_mode = "all"           # "all" | "here" | "mission" | "idle"

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return f"guild.{self.tab}"

    def tutorial_badge_rect(self, size):
        W, H = size
        pad = 16 if W < 1500 else 24
        return pygame.Rect(W - pad - 28, pad - 4, 28, 28)

    def tutorial_anchor(self, size):
        W, H = size
        pad = 16 if W < 1500 else 24
        return (W - pad - 340, pad + 32, 340, "down")

    # ------------------------------------------------------------------ #
    def _is_group_leader(self, unit):
        group = self.guild.group_of(unit)
        return group is not None and group.leader is unit

    def _recruited_by(self, unit):
        if not getattr(unit, "recruited_by", None):
            return None
        who = next((u for u in self.roster if u.uid == unit.recruited_by), None)
        return who.name if who else "someone long gone"

    def handle_event(self, event):
        super().handle_event(event)
        if event.type == pygame.MOUSEWHEEL:
            if self.tab == "reputations":
                self._rep_scroll = max(0, min(self._rep_max_scroll, self._rep_scroll - event.y * 36))
                return
            else:
                self._roster_scroll = max(0, min(self._roster_max_scroll, self._roster_scroll - event.y * 36))
                return
        elif event.type == pygame.KEYDOWN and self.tab == "reputations":
            if event.key in (pygame.K_UP, pygame.K_k):
                self._rep_scroll = max(0, min(self._rep_max_scroll, self._rep_scroll - 36))
                return
            elif event.key in (pygame.K_DOWN, pygame.K_j):
                self._rep_scroll = max(0, min(self._rep_max_scroll, self._rep_scroll + 36))
                return
            elif event.key == pygame.K_PAGEUP:
                self._rep_scroll = max(0, min(self._rep_max_scroll, self._rep_scroll - 200))
                return
            elif event.key == pygame.K_PAGEDOWN:
                self._rep_scroll = max(0, min(self._rep_max_scroll, self._rep_scroll + 200))
                return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            px = event.pos

            # 1. Filter hits
            for rect, mode in self.filter_hits:
                if rect.collidepoint(px):
                    self.filter_mode = mode
                    self._roster_scroll = 0
                    return

            # 2. Accordion header folds
            for rect, grp in self.accordion_hits:
                if rect.collidepoint(px):
                    gid = getattr(grp, "gid", str(id(grp)))
                    if gid in self.collapsed_groups:
                        self.collapsed_groups.remove(gid)
                    else:
                        self.collapsed_groups.add(gid)
                    return

            # 3. Action buttons
            for key, rect in self.buttons:
                if rect.collidepoint(px):
                    if key.startswith("roster_level:") and self.on_level:
                        uid = key.split(":", 1)[1]
                        target = next((u for u in self.roster if u.uid == uid), None)
                        if target:
                            self.member = target
                            self.on_level(target)
                    elif key == "level" and self.on_level and self.member is not None:
                        self.on_level(self.member)
                    elif key == "share_food" and self.member is not None:
                        self.member.share_food = not self.member.share_food
                    elif key == "group_leader" and self.member is not None:
                        group = self.guild.group_of(self.member)
                        if group:
                            group.set_leader(self.member)
                    elif key == "guild_leader" and self.member is not None:
                        self.guild.set_leader(self.member)
                    elif key == "distribute" and self.member is not None:
                        group = self.guild.group_of(self.member)
                        if group and len(group.members) > 1:
                            group.distribute_load()
                    elif key == "vault" and self.on_bank:
                        self.on_bank()
                    elif key == "manage" and self.on_manage:
                        self.on_manage()
                    elif key == "back":
                        self.on_back()
                    return

            # 4. Tab navigation
            for rect, key in self.tab_hits:
                if rect.collidepoint(px):
                    self.tab = key
                    return

            # 5. Member selection
            for rect, unit in self.member_hits:
                if rect.collidepoint(px):
                    self.member = unit
                    return

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.buttons = []
        self.member_hits = []
        self.tab_hits = []
        self._hot = False
        self.tooltip = None

        pending = [u for u in self.roster if u.pending_picks]
        if self.member not in self.roster:
            self.member = pending[0] if pending else (self.roster[0] if self.roster else None)

        pad = 16 if W < 1500 else 24
        banner = (pad + 16, pad + 14)
        smooth_circle(screen, self.guild.banner_color, banner, 16)
        art = artwork.banner_icon(self.guild.banner_icon, 22, (15, 15, 20))
        if art is not None:
            screen.blit(art, art.get_rect(center=banner))

        text(screen, F["titleb"], self.guild.name or "The Guild", (pad + 36, pad - 2), TX_HIGH)
        text(screen, F["body_sm"], "Central guild command, company roster and progression", (pad + 36, pad + 24), TX_MED)
        extra_lvl = f"  ·  {len(pending)} ready to level up" if pending else ""
        sub = f"{self.battles_won} battle victories  ·  {len(self.roster)} total members{extra_lvl}"
        sub_col = T.BRASS if pending else TX_MED
        text(screen, F["body"], ellipsize(sub, F["body"], W - 2 * pad), (pad, pad + 46), sub_col)

        self._draw_tabs(screen, F, W, pad)

        top = pad + 76
        bottom = H - 64
        if self.tab == "reputations":
            self._draw_reputacoes(screen, F, W, top, bottom, pad)
        else:
            list_w = int(min(max(W * 0.24, LIST_MIN), LIST_MAX))
            det_w = W - 2 * pad - list_w - 16
            det_h = bottom - top
            list_rect = pygame.Rect(pad, top, list_w, det_h)
            det_rect = pygame.Rect(pad + list_w + 16, top, det_w, det_h)
            self._draw_roster(screen, F, list_rect)
            if self.member is not None:
                self._draw_detail(screen, F, det_rect, self.member)

        self._draw_footer(screen, F, W, H, pad)

        if self.tooltip:
            draw_tooltip(screen, F, self.tooltip, self.mouse)

        set_pointer(self._hot)

    # ------------------------------------------------------------------ #
    # LEFT COLUMN: Roster with Quick Filters & Collapsible Bands Accordion#
    # ------------------------------------------------------------------ #
    def _draw_roster(self, screen, F, rect):
        mouse = self.mouse
        self.accordion_hits = []
        self.filter_hits = []

        # 1. Quick Filter Pills at the top
        filters = [("ALL", "all"), ("HERE", "here"), ("EXPEDITION", "mission"), ("IDLE", "idle")]
        gap = 4
        fw = (rect.w - (len(filters) - 1) * gap) // len(filters)
        fy = rect.y
        fh = 24
        for i, (label, key) in enumerate(filters):
            fr = pygame.Rect(rect.x + i * (fw + gap), fy, fw, fh)
            active = self.filter_mode == key
            hov = fr.collidepoint(mouse)
            pygame.draw.rect(screen, T.STEEL_HI if (active or hov) else T.STEEL, fr)
            pygame.draw.rect(screen, T.BRASS if active else (TX_MED if hov else BORDER_SUBTLE), fr, 1)
            caps(screen, F["microb"], label, (fr.centerx, fr.centery),
                 T.BRASS if active else (TX_HIGH if hov else TX_MED), center=True)
            self.filter_hits.append((fr, key))
            if hov:
                self._hot = True
                curr_loc = getattr(self.guild.group_of(self.member), "node", "Camp").title() if self.member else "Current Node"
                tip = {
                    "all": "Show all recruits across every company band",
                    "here": f"Show only members currently at {curr_loc}",
                    "mission": "Show members on active travel or labor operations",
                    "idle": "Show members resting or idle in settlement",
                }.get(key, "")
                self.tooltip = tip

        # 2. Roster Tree / Accordion View (Scrollable)
        roster_top = fy + fh + 8
        footer_h = 30
        roster_h = rect.bottom - roster_top - footer_h
        view_rect = pygame.Rect(rect.x, roster_top, rect.w, roster_h)

        ref_node = getattr(self.guild.group_of(self.member), "node", None) if self.member else None

        cur_y = roster_top - self._roster_scroll
        content_start_y = cur_y

        with contained(screen, view_rect):
            # Iterate each band in the guild
            for grp in self.guild.groups:
                grp_node = getattr(grp, "node", "camp") or "camp"
                is_idle = getattr(grp, "order", None) is None or grp.order.kind == "idle"

                # Filter members of this group
                members = []
                for m in grp.members:
                    if self.filter_mode == "here" and ref_node and grp_node != ref_node:
                        continue
                    if self.filter_mode == "mission" and is_idle:
                        continue
                    if self.filter_mode == "idle" and not is_idle:
                        continue
                    members.append(m)

                if not members and self.filter_mode != "all":
                    continue

                gid = getattr(grp, "gid", str(id(grp)))
                collapsed = gid in self.collapsed_groups

                # Accordion Band Header
                head_h = 28
                hr = pygame.Rect(rect.x, cur_y, rect.w, head_h)
                hov_h = hr.collidepoint(mouse)
                pygame.draw.rect(screen, T.STEEL_HI if hov_h else T.STEEL, hr)
                pygame.draw.rect(screen, T.BRASS if hov_h else BORDER_SUBTLE, hr, 1)

                arrow = "▶" if collapsed else "▼"
                node_title = grp_node.replace('_', ' ').title() if isinstance(grp_node, str) else "Camp"
                order_title = grp.order.kind.title() if (getattr(grp, "order", None) and getattr(grp.order, "kind", None)) else "Idle"
                head_title = f"{arrow} {grp.display_name} ({len(grp.members)})"
                text(screen, F["bodyb"], ellipsize(head_title, F["bodyb"], hr.w - 120), (hr.x + 8, hr.y + 4), TX_HIGH)
                caps(screen, F["micro"], f"@{node_title}", (hr.right - 8, hr.y + 7), TX_MED, right=True)

                self.accordion_hits.append((hr, grp))
                if hov_h:
                    self._hot = True
                    self.tooltip = (f"{grp.display_name} (Click to {'expand' if collapsed else 'collapse'})\n"
                                    f"Location: {node_title}\n"
                                    f"Current Task: {order_title}")

                cur_y += head_h + 4

                # Render members if band is expanded
                if not collapsed:
                    card_h = 60
                    for unit in members:
                        cr = pygame.Rect(rect.x, cur_y, rect.w, card_h)
                        sel = unit is self.member
                        hov_c = cr.collidepoint(mouse)
                        if hov_c and not sel:
                            self._hot = True

                        c = Combatant(unit)
                        self._draw_member_card(screen, F, cr, unit, c, grp, selected=sel)
                        self.member_hits.append((cr, unit))
                        cur_y += card_h + 4

                cur_y += 4

        # Compute max scroll and handle boundaries
        total_content_h = (cur_y - content_start_y)
        self._roster_max_scroll = max(0, total_content_h - roster_h)
        if self._roster_scroll > self._roster_max_scroll:
            self._roster_scroll = self._roster_max_scroll

        if self._roster_max_scroll > 0:
            scrollbar(screen, pygame.Rect(rect.right - 6, roster_top, 6, roster_h),
                      self._roster_scroll, self._roster_max_scroll, total_content_h)

        # 3. Compact Status Footer
        foot_r = pygame.Rect(rect.x, rect.bottom - footer_h, rect.w, footer_h)
        pygame.draw.rect(screen, T.STEEL, foot_r)
        pygame.draw.rect(screen, BORDER_SUBTLE, foot_r, 1)
        pending_cnt = sum(1 for u in self.roster if u.pending_picks)
        lvl_str = f" · {pending_cnt} Ready to Level" if pending_cnt else ""
        foot_msg = f"{len(self.roster)} Recruits · {len(self.guild.groups)} Band(s){lvl_str}"
        caps(screen, F["micro"], foot_msg, (foot_r.centerx, foot_r.centery), TX_MED, center=True)

    def _draw_member_card(self, screen, F, rect, unit, c, group=None, selected=False):
        pygame.draw.rect(screen, T.STEEL_HI if selected else T.STEEL, rect)
        pygame.draw.rect(screen, T.BRASS if selected else BORDER_SUBTLE, rect, 1)

        # Token medallion
        cx = rect.x + 22
        token_badge(screen, F, (cx, rect.centery), unit, r=16)

        # Name
        text(screen, F["bodyb"], unit.name, (rect.x + 46, rect.centery - 16), TX_HIGH)

        # Race + Status Tag
        race_name = unit.race["name"] if isinstance(unit.race, dict) else str(unit.race)
        tag = None
        tag_col = T.BRASS
        if unit.pending_picks:
            tag = "LEVEL UP"
            tag_col = T.BRASS
        elif unit.hunger_level >= 2:
            tag = "HUNGRY"
            tag_col = T.BLOOD
        elif unit is self.guild.leader:
            tag = "SOVEREIGN"
            tag_col = T.BRASS
        elif self._is_group_leader(unit):
            tag = "COMMANDER"
            tag_col = TX_MED

        node_val = getattr(group, "node", None) if group else None
        node_name = node_val.replace('_', ' ').title() if isinstance(node_val, str) else ""
        sub_parts = [race_name]
        if node_name:
            sub_parts.append(f"@{node_name}")
        if tag:
            sub_parts.append(tag)
        sub_str = " · ".join(sub_parts)
        caps(screen, F["micro"], ellipsize(sub_str, F["micro"], rect.w - 170),
             (rect.x + 46, rect.centery + 4), tag_col if tag else TX_MED)

        # Trailing stats on the right: HP X/Y and Load X/Y kg
        cur_hp = max(0, getattr(unit, "hp", unit.hp_max))
        max_hp = unit.hp_max
        hp_col = T.GREEN if cur_hp >= max_hp else T.BLOOD if cur_hp <= max_hp // 2 else T.BRASS
        text(screen, F["bodyb"], f"HP {cur_hp}/{max_hp}", (rect.right - 10, rect.centery - 15), hp_col, right=True)

        load_cur = unit.load
        load_norm = unit.carry_normal
        over = load_cur > load_norm
        load_col = T.BLOOD if over else TX_MED
        text(screen, F["body"], f"{load_cur:g}/{load_norm:g} kg", (rect.right - 10, rect.centery + 3), load_col, right=True)

    # ------------------------------------------------------------------ #
    # CENTER & RIGHT PANELS: Character Sheet, Tactics, Progression       #
    # ------------------------------------------------------------------ #
    def _draw_detail(self, screen, F, rect, unit):
        mouse = self.mouse
        panel(screen, rect)
        pad = 16
        inner_w = rect.w - 2 * pad
        col_gap = 20
        col_a_w = int((inner_w - col_gap) * 0.50)
        col_b_w = inner_w - col_gap - col_a_w
        col_a_x = rect.x + pad
        col_b_x = col_a_x + col_a_w + col_gap

        self._draw_detail_tactical(screen, F, col_a_x, rect.y + pad, col_a_w, unit, mouse)
        self._draw_detail_progression(screen, F, col_b_x, rect.y + pad, col_b_w, unit, mouse)

    def _draw_detail_tactical(self, screen, F, x, y, w, unit, mouse):
        # 1. Identity, Demographics, and Node Hero Badge
        token_badge(screen, F, (x + 22, y + 22), unit, r=20)
        text(screen, F["titleb"], unit.name, (x + 52, y - 4), TX_HIGH)

        race_name = unit.race["name"] if isinstance(unit.race, dict) else str(unit.race)
        sub = f"{race_name} · {unit.age} yrs · {unit.alignment.upper()}"
        text(screen, F["body_sm"], ellipsize(sub, F["body_sm"], w - 240), (x + 52, y + 24), TX_MED)

        grp = self.guild.group_of(unit)
        grp_name = grp.display_name if grp else "Unassigned"
        node_val = getattr(grp, "node", None) if grp else None
        node_name = node_val.replace('_', ' ').title() if isinstance(node_val, str) else "Camp"
        order_name = grp.order.kind.title() if (grp and getattr(grp, "order", None) and getattr(grp.order, "kind", None)) else "Idle"

        # Location Hero Badge with Shortcut on the Top Right
        badge_w = 210
        badge_h = 42
        badge_r = pygame.Rect(x + w - badge_w, y - 2, badge_w, badge_h)
        pygame.draw.rect(screen, T.STEEL, badge_r)
        pygame.draw.rect(screen, BORDER_SUBTLE, badge_r, 1)

        caps(screen, F["microb"], f"{node_name.upper()} · {order_name.upper()}",
             (badge_r.centerx, badge_r.y + 6), TX_HIGH, center=True)

        view_map_r = pygame.Rect(badge_r.x + 8, badge_r.y + 21, badge_r.w - 16, 17)
        hov_map = view_map_r.collidepoint(mouse)
        pygame.draw.rect(screen, T.STEEL_HI if hov_map else T.TABLE, view_map_r)
        pygame.draw.rect(screen, T.BRASS if hov_map else BORDER_SUBTLE, view_map_r, 1)
        caps(screen, F["micro"], "[ VIEW ON MAP ]", (view_map_r.centerx, view_map_r.centery),
             T.BRASS if hov_map else TX_MED, center=True)
        self.buttons.append(("view_map", view_map_r))
        if hov_map:
            self._hot = True
            self.tooltip = (f"Geographic Position:\nLocated at {node_name} with {grp_name}.\n"
                            f"Current Task: {order_name}.")

        y += 56

        # 2. Vitals Chips
        c = Combatant(unit)
        ch = unit_to_ch(c)
        cur_hp, max_hp = ch["hp"]
        hp_col = T.GREEN if cur_hp >= max_hp else T.BLOOD if cur_hp <= max_hp // 2 else T.BRASS
        vitals = [
            ("HP", f"{cur_hp}/{max_hp}", hp_col, "Hit Points"),
            ("AC", str(ch["ac"]), TX_HIGH, "Armor Class"),
            ("MD", str(ch["md"]), TX_HIGH, "Mental Defense"),
            ("SPD", str(ch["spd"]), TX_HIGH, "Tactical Speed (hexes/turn)"),
            ("INIT", str(ch["init"]), TX_HIGH, "Initiative Modifier"),
        ]
        chip_gap = 6
        chip_w = (w - (len(vitals) - 1) * chip_gap) // len(vitals)
        for i, (label, val, vcol, vtip) in enumerate(vitals):
            cr = pygame.Rect(x + i * (chip_w + chip_gap), y, chip_w, 42)
            pygame.draw.rect(screen, T.TABLE, cr)
            pygame.draw.rect(screen, T.BRASS if cr.collidepoint(mouse) else BORDER_SUBTLE, cr, 1)
            caps(screen, F["micro"], label, (cr.centerx, cr.y + 4), TX_DIM, center=True)
            text(screen, F["head"], val, (cr.centerx, cr.y + 18), vcol, center=True)
            if cr.collidepoint(mouse):
                self._hot = True
                self.tooltip = f"{label}: {vtip}"
        y += 48

        # 3. Attributes Grid
        attr_gap = 6
        attr_w = (w - (len(ch["attrs"]) - 1) * attr_gap) // len(ch["attrs"])
        for i, (k, val, mod, pen_flag) in enumerate(ch["attrs"]):
            ar = pygame.Rect(x + i * (attr_w + attr_gap), y, attr_w, 50)
            pygame.draw.rect(screen, T.TABLE, ar)
            pygame.draw.rect(screen, T.BRASS if ar.collidepoint(mouse) else BORDER_SUBTLE, ar, 1)
            caps(screen, F["microb"], k, (ar.centerx, ar.y + 4), TX_DIM, center=True)
            text(screen, F["head"], str(val), (ar.centerx, ar.y + 16), T.BLOOD if pen_flag else TX_HIGH, center=True)
            mcol = T.GREEN if mod > 0 else T.BLOOD if mod < 0 else TX_DIM
            mstr = f"{mod:+}" if mod != 0 else "+0"
            text(screen, F["micro"], mstr, (ar.centerx, ar.y + 34), mcol, center=True)
            if ar.collidepoint(mouse):
                self._hot = True
                self.tooltip = f"{k} attribute: {val} (modifier {mstr})"
        y += 56

        # 4. Weapon & Combat Profile (Aligned Compact Grid)
        y = section(screen, F, "TACTICAL COMBAT & ATTACK PROFILE", x, y, w)
        bab, src = _to_hit(c)
        wname, dmg, reach = _weapon_line(c)

        wbox = pygame.Rect(x, y, w, 62)
        pygame.draw.rect(screen, T.TABLE, wbox)
        pygame.draw.rect(screen, BORDER_SUBTLE, wbox, 1)

        # Top row: Name on left, tags on right
        text(screen, F["bodyb"], wname, (wbox.x + 10, wbox.y + 6), TX_HIGH)
        caps(screen, F["micro"], reach, (wbox.right - 10, wbox.y + 8), TX_MED, right=True)

        # Bottom row: 4 Aligned Metric Chips
        chip_gap = 6
        w_avail = wbox.w - 20
        w_atk = 100
        w_dmg = 120
        w_rch = 90
        w_brd = max(70, w_avail - (w_atk + w_dmg + w_rch + chip_gap * 3))

        grid_y = wbox.y + 28
        grid_h = 24
        atk_str = f"{bab:+}" if bab != 0 else "+0"
        c1 = pygame.Rect(wbox.x + 10, grid_y, w_atk, grid_h)
        h1, t1 = _draw_metric_chip(screen, F, c1, "ATTACK", atk_str, mouse,
                                   f"Attack Modifier: {atk_str}\nGoverned by: {src}\nIn combat: d20 {atk_str} test vs target Armor Class")
        if h1:
            self._hot, self.tooltip = True, t1

        c2 = pygame.Rect(c1.right + chip_gap, grid_y, w_dmg, grid_h)
        clean_dmg = dmg.split("(")[0].strip() if "(" in dmg else dmg
        h2, t2 = _draw_metric_chip(screen, F, c2, "DAMAGE", clean_dmg, mouse,
                                   f"Damage Roll: {dmg}\nBase weapon dice + {src} damage modifier on hit")
        if h2:
            self._hot, self.tooltip = True, t2

        w_obj = unit.weapon
        reach_meters = f"{w_obj.range * 1.5:g}m" if (w_obj and getattr(w_obj, "range", 0) > 0) else "1.5m"
        c3 = pygame.Rect(c2.right + chip_gap, grid_y, w_rch, grid_h)
        h3, t3 = _draw_metric_chip(screen, F, c3, "REACH", reach_meters, mouse,
                                   f"Tactical Reach / Range: {reach_meters}")
        if h3:
            self._hot, self.tooltip = True, t3

        spd_pen = f"-{unit.armor.speed_penalty} SPD" if (unit.armor and getattr(unit.armor, "speed_penalty", 0) > 0) else "0 SPD"
        c4 = pygame.Rect(c3.right + chip_gap, grid_y, w_brd, grid_h)
        h4, t4 = _draw_metric_chip(screen, F, c4, "BURDEN", spd_pen, mouse,
                                   f"Armor Movement Burden: {spd_pen}\nDeducted from movement speed")
        if h4:
            self._hot, self.tooltip = True, t4

        y += 68

        # 5. Equipment & Segmented 3-Zone Load Bar
        y = section(screen, F, "EQUIPMENT & WEIGHT CAPACITY", x, y, w)
        gear_box = pygame.Rect(x, y, w, 70)
        pygame.draw.rect(screen, T.TABLE, gear_box)
        pygame.draw.rect(screen, BORDER_SUBTLE, gear_box, 1)

        offhand = getattr(unit, "equipped_offhand", None)
        if not offhand:
            if getattr(c, "torch_hand", False):
                offhand = "Torch"
            elif getattr(c, "lantern_hand", False):
                offhand = "Lantern"
        hands_str = f"{wname} + {offhand}" if offhand and offhand != "None" else wname
        armor_str = unit.armor_name if unit.armor else "None"

        gy = gear_box.y + 8
        caps(screen, F["microb"], "HANDS:", (x + 12, gy), TX_DIM)
        text(screen, F["body_sm"], hands_str, (x + 64, gy - 1), TX_HIGH)
        caps(screen, F["microb"], "ARMOR:", (x + w // 2, gy), TX_DIM)
        text(screen, F["body_sm"], armor_str, (x + w // 2 + 54, gy - 1), TX_HIGH)
        gy += 20

        wealth_str = f"Coins: {unit.gold} C (copper)"
        rat_cnt = getattr(unit, "rations", 0)
        rations_str = f"Rations: {rat_cnt} in pack"
        rat_col = T.GREEN if rat_cnt > 0 else (TX_MED if unit.ability.id == "autotroph" else T.BLOOD)
        text(screen, F["body_sm"], wealth_str, (x + 12, gy), T.BRASS)
        text(screen, F["body_sm"], rations_str, (x + w // 2, gy), rat_col)
        y += 76

        # Segmented 3-Zone Load Bar
        load_cur = unit.load
        load_norm = unit.carry_normal
        load_max = unit.carry_max

        overloaded = load_cur > load_norm
        immobile = load_cur > load_max

        if immobile:
            status_txt = "IMMOBILE (EXCEEDS MAX CEILING)"
            status_col = T.BLOOD
        elif overloaded:
            status_txt = "OVERLOADED (-2 SPD, -2 STR/DEX)"
            status_col = (224, 149, 75)   # Amber
        else:
            status_txt = "UNENCUMBERED (NORMAL)"
            status_col = T.GREEN

        caps(screen, F["micro"], f"CARGO: {load_cur:g} / {load_norm:g} KG", (x, y), TX_HIGH)
        caps(screen, F["microb"], status_txt, (x + w, y), status_col, right=True)
        y += 14

        bar_rect = pygame.Rect(x, y, w, 10)
        pygame.draw.rect(screen, T.STEEL_LINE, bar_rect, 1)
        pygame.draw.rect(screen, T.TABLE, (bar_rect.x + 1, bar_rect.y + 1, bar_rect.w - 2, bar_rect.h - 2))

        norm_ratio = min(1.0, load_norm / load_max) if load_max else 0.5
        norm_x = bar_rect.x + int((bar_rect.w - 2) * norm_ratio)

        cur_ratio = min(1.0, load_cur / load_max) if load_max else 0
        fill_w = int((bar_rect.w - 2) * cur_ratio)

        if fill_w > 0:
            fill_col = T.BLOOD if immobile else ((224, 149, 75) if overloaded else T.GREEN)
            pygame.draw.rect(screen, fill_col, (bar_rect.x + 1, bar_rect.y + 1, fill_w, bar_rect.h - 2))

        # Divider tick at normal limit
        pygame.draw.line(screen, (220, 220, 230), (norm_x, bar_rect.y - 1), (norm_x, bar_rect.bottom + 1), 2)
        y += 14

        # Legend under bar
        caps(screen, F["micro"], "0 kg (Free)", (x, y), TX_DIM)
        caps(screen, F["micro"], f"▲ Threshold: {load_norm:g} kg", (norm_x, y), TX_MED, center=True)
        caps(screen, F["micro"], f"Ceiling: {load_max:g} kg (Immobile)", (x + w, y), TX_DIM, right=True)
        y += 20

        # 6. Racial Trait & Languages
        y = section(screen, F, "RACIAL TRAIT & LANGUAGES", x, y, w)
        ab_name, ab_desc = ch["ability"]
        trait_box = pygame.Rect(x, y, w, 56)
        pygame.draw.rect(screen, T.TABLE, trait_box)
        pygame.draw.rect(screen, BORDER_SUBTLE, trait_box, 1)
        text(screen, F["bodyb"], ab_name, (trait_box.x + 10, trait_box.y + 6), TX_HIGH)
        ty = trait_box.y + 22
        for line in wrap(F["micro"], ab_desc, w - 20):
            if ty > trait_box.bottom - 12:
                break
            text(screen, F["micro"], line, (trait_box.x + 10, ty), TX_MED)
            ty += 14
        y += 62

        langs_str = ", ".join(ch["langs"]) or "none"
        caps(screen, F["microb"], "LANGUAGES:", (x, y), TX_DIM)
        text(screen, F["body_sm"], langs_str, (x + 80, y - 1), TX_MED)

    def _draw_detail_progression(self, screen, F, bx, a, bw, unit, mouse):
        # 1. Military Posts, Ranks & Command (No mobile iOS switches!)
        a = section(screen, F, "COMMAND ROLES & LOGISTICS", bx, a, bw)
        group = self.guild.group_of(unit)
        is_group_leader = self._is_group_leader(unit)
        is_guild_leader = unit is self.guild.leader
        cap = BASE_CAPACITY + unit.mod_charisma + (unit.racial_level // 2)
        free_swap = self.guild.leader_swaps_used < 1

        # Post 1: Guild Sovereign
        if is_guild_leader:
            g_box = pygame.Rect(bx, a, bw, 46)
            pygame.draw.rect(screen, T.STEEL, g_box)
            pygame.draw.rect(screen, T.BRASS, g_box, 1)
            text(screen, F["bodyb"], "★ GUILD SOVEREIGN", (g_box.x + 10, g_box.y + 6), T.BRASS)
            caps(screen, F["microb"], "SUPREME LEADER", (g_box.right - 10, g_box.y + 7), T.GREEN, right=True)
            text(screen, F["micro"], "Supreme commander of the guild. Adds CHA bonus to taverna recruitment.",
                 (g_box.x + 10, g_box.y + 24), TX_MED)
        else:
            g_box = pygame.Rect(bx, a, bw, 46)
            pygame.draw.rect(screen, T.STEEL, g_box)
            pygame.draw.rect(screen, BORDER_SUBTLE, g_box, 1)
            text(screen, F["bodyb"], "GUILD SOVEREIGNTY", (g_box.x + 10, g_box.y + 6), TX_HIGH)
            sub_swap = "1 free transfer remaining" if free_swap else "No free transfer left"
            text(screen, F["micro"], sub_swap, (g_box.x + 10, g_box.y + 24), TX_MED)

            trans_btn = pygame.Rect(g_box.right - 180, g_box.y + 10, 170, 26)
            draw_button(screen, F, trans_btn, "TRANSFER LEADERSHIP", enabled=free_swap, ghost=True, mpos=mouse)
            if free_swap:
                self.buttons.append(("guild_leader", trans_btn))
            if trans_btn.collidepoint(mouse):
                self._hot = True
                self.tooltip = "Transfer Guild Leadership:\nPromotes this member to supreme leader of the organization."
        a += 52

        # Post 2: Band Commander
        if is_group_leader:
            b_box = pygame.Rect(bx, a, bw, 46)
            pygame.draw.rect(screen, T.STEEL, b_box)
            pygame.draw.rect(screen, BORDER_SUBTLE, b_box, 1)
            text(screen, F["bodyb"], "BAND COMMANDER", (b_box.x + 10, b_box.y + 6), TX_HIGH)
            caps(screen, F["microb"], "IN COMMAND", (b_box.right - 10, b_box.y + 7), T.GREEN, right=True)
            grp_name = group.display_name if group else "Band"
            text(screen, F["micro"], f"Commands {grp_name} (Capacity: {cap} members).",
                 (b_box.x + 10, b_box.y + 24), TX_MED)
        else:
            b_box = pygame.Rect(bx, a, bw, 46)
            pygame.draw.rect(screen, T.STEEL, b_box)
            pygame.draw.rect(screen, BORDER_SUBTLE, b_box, 1)
            text(screen, F["bodyb"], "BAND COMMANDER", (b_box.x + 10, b_box.y + 6), TX_HIGH)
            can_cmd = group is not None and len(group.members) > 1
            text(screen, F["micro"], f"Appoint as commander (Capacity: {cap} members)",
                 (b_box.x + 10, b_box.y + 24), TX_MED)

            cmd_btn = pygame.Rect(b_box.right - 170, b_box.y + 10, 160, 26)
            draw_button(screen, F, cmd_btn, "APPOINT COMMANDER", enabled=can_cmd, ghost=True, mpos=mouse)
            if can_cmd:
                self.buttons.append(("group_leader", cmd_btn))
            if cmd_btn.collidepoint(mouse):
                self._hot = True
                self.tooltip = f"Appoint Band Commander:\nDesignates this member to lead {group.display_name if group else 'the band'}."
        a += 52

        # Post 3: Ration Logistics Protocol
        r_box = pygame.Rect(bx, a, bw, 46)
        pygame.draw.rect(screen, T.STEEL, r_box)
        pygame.draw.rect(screen, BORDER_SUBTLE, r_box, 1)
        text(screen, F["bodyb"], "RATION LOGISTICS", (r_box.x + 10, r_box.y + 6), TX_HIGH)
        can_share = unit.ability.id != "autotroph"
        sub_r = "Pools rations with starving comrades" if unit.share_food else "Private pack: keeps all food private"
        if not can_share:
            sub_r = "Autotroph: does not consume or carry rations"
        text(screen, F["micro"], sub_r, (r_box.x + 10, r_box.y + 24), TX_MED)

        toggle_w = 150
        tog_btn = pygame.Rect(r_box.right - toggle_w - 10, r_box.y + 10, toggle_w, 26)
        tog_label = "[ POOL WITH BAND ]" if unit.share_food else "[ PRIVATE PACK ]"
        draw_button(screen, F, tog_btn, tog_label, enabled=can_share, primary=unit.share_food, ghost=not unit.share_food, mpos=mouse)
        if can_share:
            self.buttons.append(("share_food", tog_btn))
        if tog_btn.collidepoint(mouse):
            self._hot = True
            self.tooltip = "Ration Logistics:\nToggle between pooling rations with starving squadmates or keeping food strictly in private pack."
        a += 52

        # 2. Progression Hero Action Button (Navigates to Talent Tree)
        if self.on_level:
            level_pend = bool(unit.pending_picks)
            lb = pygame.Rect(bx, a, bw, 34 if level_pend else 28)
            n_picks = len(unit.pending_picks)
            pick_s = "PICK" if n_picks == 1 else "PICKS"
            lvl_text = f"★ LEVEL UP READY ({n_picks} {pick_s} AVAILABLE)  ➔" if level_pend else "VIEW TALENT TREE & STATS  ➔"
            draw_button(screen, F, lb, lvl_text, primary=level_pend, ghost=not level_pend, mpos=mouse)
            self.buttons.append(("level", lb))
            if lb.collidepoint(mouse):
                self._hot = True
                self.tooltip = ("Character Progression:\n"
                                "Opens the Talent Tree screen.\n"
                                "Spend picks to unlock abilities and customize this unit's build!")
            a += (42 if level_pend else 34)

        # 3. Progression Tracks: Combat vs Base Labor (Work) Duality
        a = section(screen, F, "EXPERIENCE & PROGRESSION TRACKS", bx, a, bw)
        a = self._draw_progression_tracks(screen, F, bx, a, bw, unit, mouse)

        # 4. Active Talents & Traits
        a = section(screen, F, "ACTIVE TALENTS & TRAITS", bx, a, bw)
        all_tids = []
        for tr in talents.TRACKS:
            all_tids.extend(unit.talents.get(tr, []))

        if all_tids:
            tx = bx
            ty = a
            for tid in all_tids:
                t_obj = talents.get(tid)
                t_name = t_obj.name if t_obj else tid.title()
                tw = F["microb"].size(t_name.upper())[0] + 16
                if tx + tw > bx + bw:
                    tx = bx
                    ty += 24
                tr_rect = pygame.Rect(tx, ty, tw, 20)
                pygame.draw.rect(screen, T.TABLE, tr_rect)
                pygame.draw.rect(screen, T.BRASS if tr_rect.collidepoint(mouse) else BORDER_SUBTLE, tr_rect, 1)
                caps(screen, F["microb"], t_name, (tr_rect.centerx, tr_rect.centery),
                     T.BRASS if tr_rect.collidepoint(mouse) else TX_HIGH, center=True)
                if tr_rect.collidepoint(mouse):
                    self._hot = True
                    desc = t_obj.desc if t_obj else "Special talent effect."
                    track_name = t_obj.track.title() if t_obj else "Talent"
                    self.tooltip = f"{t_name} ({track_name}):\n{desc}"
                tx += tw + 6
            a = ty + 26
        else:
            text(screen, F["body_sm"], "No talents chosen yet — gain levels to unlock picks.", (bx, a), TX_DIM)
            a += 20

        # 5. Personal Record
        a = section(screen, F, "PERSONAL RECORD", bx, a, bw)
        recruiter = self._recruited_by(unit)
        rec_str = f"Recruited by {recruiter}" if recruiter else "Founding member of the guild"
        text(screen, F["body_sm"], rec_str, (bx, a), TX_MED)
        a += 18
        if getattr(unit, "arena_title", False):
            text(screen, F["body_sm"], "Champion of the Pit", (bx, a), T.BRASS)
            a += 18
        if getattr(unit, "bio", ""):
            for line in wrap(F["micro"], unit.bio, bw):
                text(screen, F["micro"], line, (bx, a), TX_DIM)
                a += 14

    def _draw_progression_tracks(self, screen, F, bx, a, bw, unit, mouse):
        # 1. Combat Track
        combat_top = a
        into_c, span_c = progression.to_next(progression.COMBAT_XP_THRESHOLDS, unit.combat_xp)
        xp_c_str = f"{into_c}/{span_c} XP" if span_c else "MAX"
        tracked(screen, F["microb"], "COMBAT CAREER", (bx, a), T.BRASS)
        text(screen, F["micro"], f"LVL {unit.combat_level}  ({xp_c_str})", (bx + bw, a), TX_HIGH, right=True)
        a += 16

        bar_c = pygame.Rect(bx, a, bw, 6)
        pygame.draw.rect(screen, T.STEEL_LINE, bar_c, 1)
        pygame.draw.rect(screen, T.TABLE, (bar_c.x + 1, bar_c.y + 1, bar_c.w - 2, bar_c.h - 2))
        if span_c:
            fillw = int((bar_c.w - 2) * max(0, min(into_c, span_c)) / span_c)
            if fillw > 0:
                pygame.draw.rect(screen, T.BRASS, (bar_c.x + 1, bar_c.y + 1, fillw, bar_c.h - 2))
        a += 11

        combat_req = (f"Down standing enemies of Lv {unit.combat_level}+ (Arena, Wilds, Ambushes)."
                      if unit.combat_level > 0
                      else "Down standing enemies of Lv 0+ (Arena, Wilds, Ambushes).")
        for line in wrap(F["body_sm"], combat_req, bw):
            text(screen, F["body_sm"], line, (bx, a), TX_MED)
            a += 15

        c_rect = pygame.Rect(bx, combat_top, bw, a - combat_top)
        if c_rect.collidepoint(mouse):
            self.tooltip = (
                f"Combat XP Rule:\n"
                f"Downing an enemy grants (enemy level - {unit.combat_level}) + 1 XP.\n"
                f"Enemies below Lv {unit.combat_level} grant 0 XP.\n"
                f"Double XP is credited upon victorious battle completion."
            )
        a += 10

        # 2. Base Labor & Work Track (Work XP)
        work_top = a
        into_w, span_w = progression.to_next(progression.WORK_XP_THRESHOLDS, unit.work_xp)
        xp_w_str = f"{into_w}/{span_w} XP" if span_w else "MAX"
        tracked(screen, F["microb"], "BASE LABOR & WORK", (bx, a), T.BRASS)
        text(screen, F["micro"], f"LVL {unit.work_level}  ({xp_w_str})", (bx + bw, a), TX_HIGH, right=True)
        a += 16

        bar_w = pygame.Rect(bx, a, bw, 6)
        pygame.draw.rect(screen, T.STEEL_LINE, bar_w, 1)
        pygame.draw.rect(screen, T.TABLE, (bar_w.x + 1, bar_w.y + 1, bar_w.w - 2, bar_w.h - 2))
        if span_w:
            fillw = int((bar_w.w - 2) * max(0, min(into_w, span_w)) / span_w)
            if fillw > 0:
                pygame.draw.rect(screen, T.BRASS, (bar_w.x + 1, bar_w.y + 1, fillw, bar_w.h - 2))
        a += 11

        jobs = progression.eligible_work_activities(unit.work_level, unit)
        work_req = ("Facility labor: " + ", ".join(jobs)
                    if jobs
                    else f"No standard facilities teach past Lv {unit.work_level} yet.")
        for line in wrap(F["body_sm"], work_req, bw):
            text(screen, F["body_sm"], line, (bx, a), TX_MED)
            a += 15

        w_rect = pygame.Rect(bx, work_top, bw, a - work_top)
        if w_rect.collidepoint(mouse):
            self.tooltip = (
                f"Work XP Rule:\n"
                f"1 mark banked per 16 hours of facility day-labour.\n"
                f"Activity level must be >= worker level (Lv {unit.work_level}+) to teach.\n"
                f"Outgrown tasks continue to pay wages but grant 0 XP."
            )
        a += 10

        # 3. Racial Track
        racial_top = a
        into_r, span_r = progression.to_next(progression.RACIAL_XP_THRESHOLDS, unit.racial_xp)
        xp_r_str = f"{into_r}/{span_r} lvls" if span_r else "MAX"
        tracked(screen, F["microb"], "RACIAL MATURITY", (bx, a), T.BRASS)
        text(screen, F["micro"], f"LVL {unit.racial_level}  ({xp_r_str})", (bx + bw, a), TX_HIGH, right=True)
        a += 16

        bar_r = pygame.Rect(bx, a, bw, 6)
        pygame.draw.rect(screen, T.STEEL_LINE, bar_r, 1)
        pygame.draw.rect(screen, T.TABLE, (bar_r.x + 1, bar_r.y + 1, bar_r.w - 2, bar_r.h - 2))
        if span_r:
            fillw = int((bar_r.w - 2) * max(0, min(into_r, span_r)) / span_r)
            if fillw > 0:
                pygame.draw.rect(screen, T.BRASS, (bar_r.x + 1, bar_r.y + 1, fillw, bar_r.h - 2))
        a += 11

        racial_req = f"Total track levels: {unit.racial_xp} (Combat {unit.combat_level} + Work {unit.work_level}). Grants +1 HD/lvl."
        if unit.racial_level < 5:
            racial_req += f" First racial talent at Lv 5 ({5 - unit.racial_level} to go)."
        else:
            racial_req += " Racial talent tree unlocked."
        for line in wrap(F["body_sm"], racial_req, bw):
            text(screen, F["body_sm"], line, (bx, a), TX_MED)
            a += 15

        r_rect = pygame.Rect(bx, racial_top, bw, a - racial_top)
        if r_rect.collidepoint(mouse):
            self.tooltip = (
                f"Racial Track Rule:\n"
                f"Racial XP is the sum of Combat Level ({unit.combat_level}) and Work Level ({unit.work_level}).\n"
                f"Each racial level grants 1 additional Hit Die roll (+CON mod) on max HP.\n"
                f"Racial talent picks unlock at Racial Level 5."
            )
        a += 10

        # 4. Study Track
        if unit.study_target:
            study_top = a
            total_needed = magic.points_to_learn(0)
            target_name = unit.study_target
            if unit.study_target in magic.SPELLS:
                spell = magic.SPELLS[unit.study_target]
                target_name = spell.name
                total_needed = magic.points_to_learn(spell.level)

            cur_pts = min(unit.study_progress, total_needed)
            tracked(screen, F["microb"], "ACADEMIC STUDY", (bx, a), T.BRASS)
            text(screen, F["micro"], f"{target_name}  ({cur_pts}/{total_needed} pts)", (bx + bw, a), TX_HIGH, right=True)
            a += 16

            bar_s = pygame.Rect(bx, a, bw, 6)
            pygame.draw.rect(screen, T.STEEL_LINE, bar_s, 1)
            pygame.draw.rect(screen, T.TABLE, (bar_s.x + 1, bar_s.y + 1, bar_s.w - 2, bar_s.h - 2))
            if total_needed > 0:
                fillw = int((bar_s.w - 2) * max(0, min(cur_pts, total_needed)) / total_needed)
                if fillw > 0:
                    pygame.draw.rect(screen, T.BRASS, (bar_s.x + 1, bar_s.y + 1, fillw, bar_s.h - 2))
            a += 11

            study_req = "Studying at taverna (rent rooms). Rolls daily progress toward mastery."
            for line in wrap(F["body_sm"], study_req, bw):
                text(screen, F["body_sm"], line, (bx, a), TX_MED)
                a += 15

            s_rect = pygame.Rect(bx, study_top, bw, a - study_top)
            if s_rect.collidepoint(mouse):
                self.tooltip = (
                    f"Study Rule:\n"
                    f"Target: {target_name}\n"
                    f"Accumulated: {cur_pts} / {total_needed} points.\n"
                    f"Rolls 1d20 + INT mod per day during 'Study' order at a Taverna."
                )
        return a

    def _item_tag(self, item):
        return items.item_tag(item)

    # ------------------------------------------------------------------ #
    def _draw_tabs(self, screen, F, W, pad):
        has_tutorial = self.tutorial_key() is not None
        x = W - pad - (36 if has_tutorial else 0)
        tab_rects = tabs(screen, F, (x, pad - 4), [t[0] for t in TABS], self.tab, mpos=self.mouse, right=True)
        for key, r in tab_rects.items():
            self.tab_hits.append((r, key))
            if r.collidepoint(self.mouse):
                self._hot = True

    def _draw_reputacoes(self, screen, F, W, top, bottom, outer):
        done = set(self.guild.deeds_done)
        x = outer
        w = min(W - 2 * outer, 900)
        view_h = bottom - top
        view_rect = pygame.Rect(x, top, w + 20, view_h)

        y_start = top + 16 - self._rep_scroll
        y = y_start

        with contained(screen, view_rect):
            for i, fac in enumerate(factions.FACTIONS.values()):
                if i:
                    hline(screen, x, x + w, y)
                    y += 24
                rep = self.guild.reputation.get(fac.id, 0)
                tracked(screen, F["microb"], fac.name.upper(), (x, y), T.BRASS)
                text(screen, F["big"], str(rep), (x, y + 14), T.BRASS)
                text(screen, F["body_sm"], fac.blurb, (x + 56, y + 26), TX_MED)
                y += 56

                y = section(screen, F, "DEEDS", x, y, w)
                deeds = factions.DEEDS_BY_FACTION[fac.id]
                if not deeds:
                    text(screen, F["body_sm"], "None yet — this faction's standing doesn't move.",
                         (x, y), TX_DIM)
                    y += 20
                for d in deeds:
                    got = d.id in done
                    smooth_circle(screen, T.GREEN if got else TX_DIM, (x + 4, y + 8), 4,
                                  0 if got else 1)
                    text(screen, F["body"], d.name, (x + 16, y), T.GREEN if got else TX_HIGH)
                    text(screen, F["body_sm"], f"{d.blurb}  (+{d.rep} rep)" + ("" if got else "  --  open"),
                         (x + 200, y + 2), TX_MED)
                    y += 24
                y += 16

                unlocks = factions.get_unlocks(fac.id)
                if unlocks:
                    y = section(screen, F, "NEXT UNLOCKS", x, y, w)
                    for u in unlocks:
                        unlocked = rep >= u.rep_required
                        col = T.GREEN if unlocked else TX_MED
                        status = "UNLOCKED" if unlocked else f"Req: Rep {u.rep_required}"
                        text(screen, F["body"], f"{u.title} ({status})", (x + 16, y), col)
                        text(screen, F["body_sm"], u.description, (x + 240, y + 2), TX_DIM)
                        y += 24
                    y += 16

                y += 24

        total_h = (y - y_start) + 24
        self._rep_content_h = total_h
        self._rep_max_scroll = max(0, total_h - view_h)
        if self._rep_scroll > self._rep_max_scroll:
            self._rep_scroll = self._rep_max_scroll

        if self._rep_max_scroll > 0:
            scrollbar(screen, pygame.Rect(x, top, w + 16, view_h),
                      self._rep_scroll, self._rep_max_scroll, total_h)

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen, F, W, H, pad):
        mouse = self.mouse
        FOOTER_H = 52
        y = H - FOOTER_H
        rx = W - pad
        btn_h = 36

        # 1. Primary button: BACK TO MAP (Always right-aligned)
        back_w = 200
        back_rect = pygame.Rect(rx - back_w, y, back_w, btn_h)
        draw_button(screen, F, back_rect, "BACK TO MAP", primary=True, mpos=mouse)
        self.buttons.append(("back", back_rect))
        if back_rect.collidepoint(mouse):
            self._hot = True
        rx = back_rect.x - 12

        # 2. Contextual Action: DISTRIBUTE BAND LOAD
        can_distribute = False
        dist_tooltip = ""
        grp = self.guild.group_of(self.member) if self.member else None
        if grp is not None:
            # Check if there are 2 or more members at the exact same location
            same_node_members = [m for m in grp.members if getattr(self.guild.group_of(m), "node", None) == grp.node]
            if len(grp.members) <= 1:
                dist_tooltip = "Cannot distribute load: Member is traveling alone."
            elif len(same_node_members) <= 1:
                dist_tooltip = "Cannot distribute load: Requires 2+ band members in the same physical location."
            else:
                can_distribute = True
                loc_title = grp.node.replace('_', ' ').title() if isinstance(grp.node, str) else "Camp"
                dist_tooltip = f"Distribute load evenly across {len(same_node_members)} band members at {loc_title}."
        else:
            dist_tooltip = "Member is unassigned."

        dist_w = 200
        dist_rect = pygame.Rect(rx - dist_w, y, dist_w, btn_h)
        draw_button(screen, F, dist_rect, "DISTRIBUTE BAND LOAD", enabled=can_distribute, mpos=mouse)
        if can_distribute:
            self.buttons.append(("distribute", dist_rect))
        if dist_rect.collidepoint(mouse):
            self._hot = True
            self.tooltip = dist_tooltip
        rx = dist_rect.x - 12

        # 3. Contextual Action: LOCAL STORAGE / VAULT
        at_city = grp and grp.node == "city"
        has_bank = self.guild.bank_capacity > 0
        can_vault = at_city and has_bank
        vault_label = "OPEN CITY VAULT" if can_vault else "NO LOCAL VAULT"
        vault_tip = (f"Access the guild's strongbox in the City ({self.guild.bank_capacity} kg capacity)."
                     if can_vault else "Vault is located in the City. Member must be in the City to access stored gear.")

        vault_w = 170
        vault_rect = pygame.Rect(rx - vault_w, y, vault_w, btn_h)
        draw_button(screen, F, vault_rect, vault_label, enabled=can_vault, ghost=True, mpos=mouse)
        if can_vault:
            self.buttons.append(("vault", vault_rect))
        if vault_rect.collidepoint(mouse):
            self._hot = True
            self.tooltip = vault_tip
        rx = vault_rect.x - 12

        # 4. Manage Gear (If provided)
        if self.on_manage:
            gear_w = 150
            gear_rect = pygame.Rect(rx - gear_w, y, gear_w, btn_h)
            draw_button(screen, F, gear_rect, "MANAGE GEAR", ghost=True, mpos=mouse)
            self.buttons.append(("manage", gear_rect))
            if gear_rect.collidepoint(mouse):
                self._hot = True
                self.tooltip = "Manage Gear:\nOpen the full equipment and loadout exchange screen."

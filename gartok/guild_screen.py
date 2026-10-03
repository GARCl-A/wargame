"""Guild screen: the roster-and-gear view between outings.

Master-detail: a column of member cards on the left picks who you are looking
at; a wide panel on the right lays that member's loadout out with room to
breathe -- stat chips, a carry bar, and the HANDS / BODY / PACK slots.

Migrated fully onto `gartok.ui`: data-driven drawing via `gartok.ui.primitives`,
`gartok.ui.sheet_card`, and `gartok.ui.tokens`.
"""

import pygame

from . import artwork, factions, items, magic, progression
from .combatant import Combatant
from .screen import Screen
from .theme import set_pointer
from .ui.primitives import (caps, contained, draw_button, draw_tooltip, ellipsize, hline,
                            panel, scrollbar, section, smooth_circle, tabs, text, tracked, wrap)
from .ui.sheet_card import draw_row, draw_sheet, unit_to_ch
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

TABS = (("members", "MEMBERS"), ("reputations", "REPUTATIONS"))

LIST_MIN, LIST_MAX = 264, 380         # roster column width clamps
DET_MAX = 1120                        # detail panel width cap on very wide screens


class GuildScreen(Screen):
    native = True                        # app draws us straight to the window

    def __init__(self, fonts, guild, on_back, on_level=None, on_manage=None):
        super().__init__()
        self.fonts = fonts
        self._F = None
        self.guild = guild
        self.roster = guild.roster
        self.battles_won = guild.battles_won
        self.on_back = on_back
        self.on_level = on_level             # open the level screen for a member
        self.on_manage = on_manage           # open the Manage Gear screen (multi-member loadout)
        self.tab = "members"                  # "members" (roster+gear) | "reputations"
        pending = [u for u in self.roster if u.pending_picks]
        self.member = pending[0] if pending else (self.roster[0] if self.roster else None)   # card shown on the right
        self.tab_hits = []                  # [(rect, key)]
        self.member_hits = []              # [(rect, unit)] -- list cards select the member
        self.buttons = []                  # [(key, rect)]
        self._hot = False
        self.tooltip = None
        self._rep_scroll = 0
        self._rep_max_scroll = 0

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py) -- one id per tab, since that's the actual
    # teachable moment (MEMBERS vs REPUTATIONS are different screens in
    # everything but name)                                               #
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
        """Name of the member who recruited `unit`, or None (draft member, or the
        recruiter has since been lost)."""
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
                    elif key == "back":
                        self.on_back()
                    return

            for rect, key in self.tab_hits:
                if rect.collidepoint(px):
                    self.tab = key
                    return

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

        text(screen, F["titleb"], self.guild.name or "The Guild", (pad + 36, pad - 2), T.TX)
        text(screen, F["body_sm"], "Manage your roster and character progression", (pad + 36, pad + 24), T.TX_FAINT)
        extra_lvl = f"  ·  {len(pending)} ready to level up" if pending else ""
        sub = f"{self.battles_won} wins  ·  {len(self.roster)} members{extra_lvl}"
        sub_col = T.BRASS if pending else T.TX_MUTED
        text(screen, F["body"], ellipsize(sub, F["body"], W - 2 * pad), (pad, pad + 46), sub_col)

        self._draw_tabs(screen, F, W, pad)

        top = pad + 76
        bottom = H - 64
        if self.tab == "reputations":
            self._draw_reputacoes(screen, F, W, top, bottom, pad)
        else:
            list_w = int(min(max(W * 0.24, LIST_MIN), LIST_MAX))
            det_w = min(DET_MAX, W - 2 * pad - list_w - 16)
            det_h = bottom - top
            list_rect = pygame.Rect(pad, top, list_w, bottom - top)
            det_rect = pygame.Rect(pad + list_w + 16, top, det_w, det_h)
            self._draw_roster(screen, F, list_rect)
            if self.member is not None:
                self._draw_detail(screen, F, det_rect, self.member)

        self._draw_footer(screen, F, W, H, pad)

        if self.tooltip:
            draw_tooltip(screen, F, self.tooltip, self.mouse)

        set_pointer(self._hot)

    # ------------------------------------------------------------------ #
    def _draw_roster(self, screen, F, rect):
        """The left column: one compact card per member, the open one lit."""
        n = max(1, len(self.roster))
        gap = 8
        row_h = min(74, max(56, (rect.h - (n - 1) * gap) // n))
        mouse = self.mouse
        for i, unit in enumerate(self.roster):
            r = pygame.Rect(rect.x, rect.y + i * (row_h + gap), rect.w, row_h)
            if r.bottom > rect.bottom + 2:
                break

            sel = unit is self.member
            hov = r.collidepoint(mouse)
            if hov and not sel:
                self._hot = True

            c = Combatant(unit)
            ch = unit_to_ch(c)
            tag = None
            if unit.pending_picks:
                tag = "LEVEL UP"
            elif unit is self.guild.leader:
                tag = "GUILD LEADER"
            elif self._is_group_leader(unit):
                tag = "GROUP LEADER"

            draw_row(screen, F, r, ch, selected=sel, tag=tag)
            self.member_hits.append((r, unit))

    # ------------------------------------------------------------------ #
    def _draw_detail(self, screen, F, rect, unit):
        mouse = self.mouse
        panel(screen, rect)
        pad = 16
        x = rect.x + pad
        inner = rect.w - 2 * pad

        # Layout: sheet on the left, management card on the right
        col_a = min(440, int(inner * 0.55))
        bx = x + col_a + 24
        bw = rect.right - pad - bx

        sheet_rect = pygame.Rect(x, rect.y + pad, col_a, rect.h - 2 * pad)
        c = Combatant(unit)
        ch = unit_to_ch(c)
        _, tip = draw_sheet(screen, F, sheet_rect, ch, density="full", mouse=mouse)
        if tip:
            self.tooltip = tip

        # --- right column: Guild Management --- #
        a = rect.y + pad
        a = section(screen, F, "GUILD MANAGEMENT", bx, a, bw)

        # Level up
        if self.on_level:
            level_pend = bool(unit.pending_picks)
            lb = pygame.Rect(bx, a, 168, 24)
            draw_button(screen, F, lb, "LEVEL UP" if level_pend else "LEVEL",
                        primary=level_pend, ghost=not level_pend, mpos=mouse)
            self.buttons.append(("level", lb))
            if lb.collidepoint(mouse):
                self._hot = True
                self.tooltip = ("XP and leveling system:\n"
                                "Characters earn XP in Combat, Work, or Racial tracks.\n"
                                "When a track levels up, they earn a pick for that tree.\n"
                                "Combat and Work XP both feed into Racial XP!")
            a += 32

        # Sharing Food
        if unit.ability.id != "autotroph":
            sf = pygame.Rect(bx, a, 168, 24)
            draw_button(screen, F, sf, "SHARING FOOD" if unit.share_food else "RATIONS PRIVATE",
                        primary=unit.share_food, ghost=not unit.share_food, mpos=mouse)
            self.buttons.append(("share_food", sf))
            if sf.collidepoint(mouse):
                self._hot = True
            a += 32

        # Leadership
        group = self.guild.group_of(unit)
        is_group_leader = self._is_group_leader(unit)
        is_guild_leader = unit is self.guild.leader

        from .group import BASE_CAPACITY
        cap = BASE_CAPACITY + unit.mod_charisma + (unit.racial_level // 2)
        text(screen, F["micro"], f"leads up to {cap} members", (bx, a), T.TX_MUTED)
        a += 18

        gl = pygame.Rect(bx, a, 168, 24)
        draw_button(screen, F, gl, "GROUP LEADER" if is_group_leader else "MAKE GROUP LEADER",
                    primary=is_group_leader, ghost=not is_group_leader, mpos=mouse)
        if not is_group_leader and group is not None and len(group.members) > 1:
            self.buttons.append(("group_leader", gl))
        if gl.collidepoint(mouse):
            self._hot = True

        free_swap = self.guild.leader_swaps_used < 1
        a += 26
        gl2 = pygame.Rect(bx, a, 168, 24)
        label = ("GUILD LEADER" if is_guild_leader
                 else "MAKE GUILD LEADER" if free_swap
                 else "NO FREE CHANGE LEFT")
        draw_button(screen, F, gl2, label,
                    primary=is_guild_leader, ghost=not is_guild_leader,
                    enabled=(is_guild_leader or free_swap), mpos=mouse)
        if not is_guild_leader and free_swap:
            self.buttons.append(("guild_leader", gl2))
        if gl2.collidepoint(mouse):
            self._hot = True

        # --- Progression & XP --- #
        a += 34
        a = section(screen, F, "EXPERIENCE & PROGRESSION", bx, a, bw)
        self._draw_progression_tracks(screen, F, bx, a, bw, unit, mouse)

    def _draw_progression_tracks(self, screen, F, bx, a, bw, unit, mouse):
        # 1. Combat Track
        combat_top = a
        into_c, span_c = progression.to_next(progression.COMBAT_XP_THRESHOLDS, unit.combat_xp)
        xp_c_str = f"{into_c}/{span_c} XP" if span_c else "MAX"
        tracked(screen, F["microb"], "COMBAT", (bx, a), T.BRASS)
        text(screen, F["micro"], f"LVL {unit.combat_level}  ({xp_c_str})", (bx + bw, a), T.TX, right=True)
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
            text(screen, F["body_sm"], line, (bx, a), T.TX_MUTED)
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

        # 2. Work Track
        work_top = a
        into_w, span_w = progression.to_next(progression.WORK_XP_THRESHOLDS, unit.work_xp)
        xp_w_str = f"{into_w}/{span_w} XP" if span_w else "MAX"
        tracked(screen, F["microb"], "WORK", (bx, a), T.BRASS)
        text(screen, F["micro"], f"LVL {unit.work_level}  ({xp_w_str})", (bx + bw, a), T.TX, right=True)
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
        work_req = ("Execute: " + ", ".join(jobs)
                    if jobs
                    else f"No standard activities teach past Lv {unit.work_level} yet.")
        for line in wrap(F["body_sm"], work_req, bw):
            text(screen, F["body_sm"], line, (bx, a), T.TX_MUTED)
            a += 15

        w_rect = pygame.Rect(bx, work_top, bw, a - work_top)
        if w_rect.collidepoint(mouse):
            self.tooltip = (
                f"Work XP Rule:\n"
                f"1 mark banked per 16 hours of day-labour.\n"
                f"Activity level must be >= worker level (Lv {unit.work_level}+) to teach.\n"
                f"Outgrown tasks continue to pay wages but grant 0 XP."
            )
        a += 10

        # 3. Racial Track
        racial_top = a
        into_r, span_r = progression.to_next(progression.RACIAL_XP_THRESHOLDS, unit.racial_xp)
        xp_r_str = f"{into_r}/{span_r} lvls" if span_r else "MAX"
        tracked(screen, F["microb"], "RACIAL", (bx, a), T.BRASS)
        text(screen, F["micro"], f"LVL {unit.racial_level}  ({xp_r_str})", (bx + bw, a), T.TX, right=True)
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
            text(screen, F["body_sm"], line, (bx, a), T.TX_MUTED)
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
            tracked(screen, F["microb"], "STUDY", (bx, a), T.BRASS)
            text(screen, F["micro"], f"{target_name}  ({cur_pts}/{total_needed} pts)", (bx + bw, a), T.TX, right=True)
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
                text(screen, F["body_sm"], line, (bx, a), T.TX_MUTED)
                a += 15

            s_rect = pygame.Rect(bx, study_top, bw, a - study_top)
            if s_rect.collidepoint(mouse):
                self.tooltip = (
                    f"Study Rule:\n"
                    f"Target: {target_name}\n"
                    f"Accumulated: {cur_pts} / {total_needed} points.\n"
                    f"Rolls 1d20 + INT mod per day during 'Study' order at a Taverna."
                )

    def _item_tag(self, item):
        return items.item_tag(item)

    # ------------------------------------------------------------------ #
    def _draw_tabs(self, screen, F, W, pad):
        """Right-aligned tab strip on the title row: MEMBERS | REPUTATIONS."""
        has_tutorial = self.tutorial_key() is not None
        x = W - pad - (36 if has_tutorial else 0)
        tab_rects = tabs(screen, F, (x, pad - 4), [t[0] for t in TABS], self.tab, mpos=self.mouse, right=True)
        for key, r in tab_rects.items():
            self.tab_hits.append((r, key))
            if r.collidepoint(self.mouse):
                self._hot = True

    def _draw_reputacoes(self, screen, F, W, top, bottom, outer):
        """The REPUTATIONS tab: per faction, the score, the deeds that earn it
        (done + open) and what the score unlocks. Fully scrollable when content
        overflows vertical view."""
        done = set(self.guild.deeds_done)
        x = outer
        w = min(W - 2 * outer, 900)
        view_h = bottom - top
        view_rect = pygame.Rect(x, top, w + 20, view_h)

        # Pre-measure / layout with scroll offset
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
                text(screen, F["body_sm"], fac.blurb, (x + 56, y + 26), T.TX_MUTED)
                y += 56

                y = section(screen, F, "DEEDS", x, y, w)
                deeds = factions.DEEDS_BY_FACTION[fac.id]
                if not deeds:
                    text(screen, F["body_sm"], "None yet — this faction's standing doesn't move.",
                         (x, y), T.TX_FAINT)
                    y += 20
                for d in deeds:
                    got = d.id in done
                    smooth_circle(screen, T.GREEN if got else T.TX_FAINT, (x + 4, y + 8), 4,
                                  0 if got else 1)
                    text(screen, F["body"], d.name, (x + 16, y), T.GREEN if got else T.TX)
                    text(screen, F["body_sm"], f"{d.blurb}  (+{d.rep} rep)" + ("" if got else "  --  open"),
                         (x + 200, y + 2), T.TX_MUTED)
                    y += 24
                y += 16

                unlocks = factions.get_unlocks(fac.id)
                if unlocks:
                    y = section(screen, F, "NEXT UNLOCKS", x, y, w)
                    for u in unlocks:
                        unlocked = rep >= u.rep_required
                        col = T.GREEN if unlocked else T.TX_MUTED
                        status = "UNLOCKED" if unlocked else f"Req: Rep {u.rep_required}"
                        text(screen, F["body"], f"{u.title} ({status})", (x + 16, y), col)
                        text(screen, F["body_sm"], u.description, (x + 240, y + 2), T.TX_FAINT)
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
        show_distribute = False
        if self.member is not None:
            grp = self.guild.group_of(self.member)
            show_distribute = bool(grp and len(grp.members) > 1)

        FOOTER_H = 52
        y = H - FOOTER_H
        rx = W - pad
        btn_h = 36

        # Primary button: BACK TO MAP
        back_w = 220
        back_rect = pygame.Rect(rx - back_w, y, back_w, btn_h)
        draw_button(screen, F, back_rect, "BACK TO MAP", primary=True, mpos=self.mouse)
        self.buttons.append(("back", back_rect))
        if back_rect.collidepoint(self.mouse):
            self._hot = True
        rx = back_rect.x - 16

        # Secondary button: DISTRIBUTE LOAD (if enabled)
        if show_distribute:
            dist_w = 180
            dist_rect = pygame.Rect(rx - dist_w, y, dist_w, btn_h)
            draw_button(screen, F, dist_rect, "DISTRIBUTE LOAD", mpos=self.mouse)
            self.buttons.append(("distribute", dist_rect))
            if dist_rect.collidepoint(self.mouse):
                self._hot = True

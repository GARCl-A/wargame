"""Guild screen: the roster-and-gear view between outings.

Master-detail: a column of member cards on the left picks who you are looking
at; a wide panel on the right lays that member's loadout out with room to
breathe -- stat chips, a carry bar, and the HANDS / BODY / PACK slots.

A weapon is an item: it can sit in a member's pack or be held in a hand. Each
doll has two hand slots -- the weapon hand (a weapon, 1 or 2 handed) and the off
hand (a torch, for now) -- plus a body slot for armor. Move items by:

- **drag** an item onto a HAND / OFF HAND / BODY / PACK slot, onto another
  MEMBER in the list (drops into their pack), or onto THROW AWAY, or
- **click** it to pick it up and click the destination (click it again, or click
  away, to put it back), and
- **shift/ctrl-click** to carry several pack items at once (a multi-drop onto a
  hand/armor slot takes the first that fits and keeps the rest).

The transfer edits the persistent `equipped_weapon` / `equipped_offhand` /
`equipped_armor` / `_base_inventory`, which every battle re-seeds a `Combatant`
from -- so the next fight starts with the new loadout. `Unit.load` / `.ac` / ...
read straight off that loadout, so the cards stay truthful with no extra
bookkeeping; the full-sheet modal wraps the member in a throwaway `Combatant`.

This screen renders at the real window resolution (`native = True`): `app` hands
`draw` the window surface and un-scaled mouse coords, so the layout can use the
whole maximized screen. Reached from the map (opening it passes no time).
`on_back()` returns to the map; `on_menu()` to the slot menu.
"""

import pygame

from . import artwork, factions, items, magic, progression
from .combatant import Combatant
from .screen import Screen
from .ui.sheet_card import draw_row, draw_sheet, unit_to_ch
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP2, SP3, SP4, SP5,
                    SURFACE_0, SURFACE_1, SURFACE_2, SURFACE_3, SURFACE_4,
                    TOKEN_INK, WARN,
                    ellipsize, kg, panel, section, set_pointer, token_badge,
                    text, tracked, draw_tooltip, wrap_lines, format_tooltip)
from .widgets import ButtonsMixin, footer_bar


TABS = (("members", "MEMBERS"), ("reputations", "REPUTATIONS"))

LIST_MIN, LIST_MAX = 264, 380         # roster column width clamps
DET_MAX = 1120                        # detail panel width cap on very wide screens


class GuildScreen(ButtonsMixin, Screen):
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

    def _ui_fonts(self):
        if self._F is None:
            from .ui.tokens import fonts as ui_fonts
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
        pad = MARGIN if W < 1500 else SP5
        return pygame.Rect(W - pad - 28, pad - 4, 28, 28)

    def tutorial_anchor(self, size):
        W, H = size
        pad = MARGIN if W < 1500 else SP5
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
        f = self.fonts
        W, H = screen.get_size()
        screen.fill(SURFACE_0)
        self.zones = []
        self.sources = []
        self.buttons = []
        self.member_hits = []
        self.tab_hits = []
        self._pack_area = None
        self._hot = False
        self.tooltip = None

        pending = [u for u in self.roster if u.pending_picks]
        if self.member not in self.roster:
            self.member = pending[0] if pending else (self.roster[0] if self.roster else None)

        pad = MARGIN if W < 1500 else SP5
        banner = (pad + 16, pad + 14)
        pygame.draw.circle(screen, self.guild.banner_color, banner, 16)
        art = artwork.banner_icon(self.guild.banner_icon, 22, TOKEN_INK)
        if art is not None:
            screen.blit(art, art.get_rect(center=banner))
        text(screen, self.guild.name or "The Guild", f.title, INK, (pad + 34, pad - 2))
        text(screen, "Manage your roster and character progression", f.body_sm, INK_FAINT, (pad + 34, pad + 26))
        extra_lvl = f"  ·  {len(pending)} ready to level up" if pending else ""
        sub, col = (f"{self.battles_won} wins  ·  {len(self.roster)} members{extra_lvl}",
                    ACCENT if pending else INK_DIM)
        text(screen, ellipsize(sub, f.body, W - 2 * pad), f.body, col, (pad, pad + 44))

        self._draw_tabs(screen, W, pad)

        top = pad + 76
        bottom = H - 64
        if self.tab == "reputations":
            self._draw_reputacoes(screen, W, top, pad)
        else:
            list_w = int(min(max(W * 0.24, LIST_MIN), LIST_MAX))
            det_w = min(DET_MAX, W - 2 * pad - list_w - SP4)
            det_h = bottom - top
            list_rect = pygame.Rect(pad, top, list_w, bottom - top)
            det_rect = pygame.Rect(pad + list_w + SP4, top, det_w, det_h)
            self._draw_roster(screen, list_rect)
            if self.member is not None:
                self._draw_detail(screen, det_rect, self.member)

        self._draw_footer(screen, W, H, pad)
        
        if getattr(self, "tooltip", None):
            draw_tooltip(screen, f.body_sm, self.tooltip, self.mouse)

        set_pointer(self._hot)

    # ------------------------------------------------------------------ #
    def _draw_roster(self, screen, rect):
        """The left column: one compact card per member, the open one lit."""
        f = self.fonts
        n = max(1, len(self.roster))
        gap = SP2
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

            draw_row(screen, self._ui_fonts(), r, ch, selected=sel, tag=tag)
            
            self.member_hits.append((r, unit))

    # ------------------------------------------------------------------ #

    def _pill(self, screen, r, label, *, accent=False, dot=False):
        """A small labelled button with a hover fill. Feeds `self._hot` for the
        pointer cursor."""
        hov = r.collidepoint(self.mouse)
        if hov:
            self._hot = True
        base = ACCENT if accent else INK_DIM
        fill = ACCENT if (accent and hov) else SURFACE_4 if hov else SURFACE_1
        ink = ACCENT_INK if (accent and hov) else INK if hov else base
        panel(screen, r, fill=fill, border=ACCENT if accent else LINE_SOFT,
              width=1, radius=RADIUS)
        text(screen, label, self.fonts.label, ink,
             (r.centerx + (4 if dot else 0), r.centery), center=True)
        if dot:
            pygame.draw.circle(screen, ink, (r.x + 9, r.centery), 3)

    def _draw_detail(self, screen, rect, unit):
        f = self.fonts
        mouse = self.mouse
        panel(screen, rect, fill=SURFACE_2, border=LINE_SOFT, width=2, radius=RADIUS)
        pad = SP4
        x = rect.x + pad
        inner = rect.w - 2 * pad

        # Layout: sheet on the left, management card on the right
        col_a = min(440, int(inner * 0.55))
        bx = x + col_a + SP5
        bw = rect.right - pad - bx

        sheet_rect = pygame.Rect(x, rect.y + pad, col_a, rect.h - 2 * pad)
        c = Combatant(unit)
        ch = unit_to_ch(c)
        _, tip = draw_sheet(screen, self._ui_fonts(), sheet_rect, ch, density="full", mouse=mouse)
        if tip:
            self.tooltip = tip

        # --- right column: Guild Management --- #
        a = rect.y + pad
        a = section(screen, "GUILD MANAGEMENT", bx, a, bw, f)
        
        # Level up
        if self.on_level:
            level_pend = bool(unit.pending_picks)
            lb = pygame.Rect(bx, a, 168, 22)
            self._pill(screen, lb, "LEVEL UP" if level_pend else "LEVEL",
                       accent=level_pend, dot=level_pend)
            self.buttons.append(("level", lb))
            if lb.collidepoint(mouse):
                self.tooltip = ("XP and leveling system:\n"
                                "Characters earn XP in Combat, Work, or Racial tracks.\n"
                                "When a track levels up, they earn a pick for that tree.\n"
                                "Combat and Work XP both feed into Racial XP!")
            a += 32

        # Sharing Food
        if unit.ability.id != "autotroph":
            sf = pygame.Rect(bx, a, 168, 22)
            self._pill(screen, sf, "SHARING FOOD" if unit.share_food else "RATIONS PRIVATE",
                       dot=unit.share_food)
            self.buttons.append(("share_food", sf))
            a += 32

        # Leadership
        group = self.guild.group_of(unit)
        is_group_leader = self._is_group_leader(unit)
        is_guild_leader = unit is self.guild.leader
        
        from .group import BASE_CAPACITY
        cap = BASE_CAPACITY + unit.mod_charisma + (unit.racial_level // 2)
        text(screen, f"leads up to {cap} members", f.mono_sm, INK_DIM, (bx, a))
        a += 18
        
        gl = pygame.Rect(bx, a, 168, 22)
        self._pill(screen, gl, "GROUP LEADER" if is_group_leader else "MAKE GROUP LEADER",
                   accent=is_group_leader)
        if not is_group_leader and group is not None and len(group.members) > 1:
            self.buttons.append(("group_leader", gl))

        free_swap = self.guild.leader_swaps_used < 1
        a += 26
        gl2 = pygame.Rect(bx, a, 168, 22)
        label = ("GUILD LEADER" if is_guild_leader
                 else "MAKE GUILD LEADER" if free_swap
                 else "no free change left")
        self._pill(screen, gl2, label, accent=is_guild_leader)
        if not is_guild_leader and free_swap:
            self.buttons.append(("guild_leader", gl2))

        # --- Progression & XP --- #
        a += 34
        a = section(screen, "EXPERIENCE & PROGRESSION", bx, a, bw, f)
        self._draw_progression_tracks(screen, bx, a, bw, unit, mouse)

    def _draw_progression_tracks(self, screen, bx, a, bw, unit, mouse):
        f = self.fonts

        # 1. Combat Track
        combat_top = a
        into_c, span_c = progression.to_next(progression.COMBAT_XP_THRESHOLDS, unit.combat_xp)
        xp_c_str = f"{into_c}/{span_c} XP" if span_c else "MAX"
        tracked(screen, "COMBAT", f.label, INFO, (bx, a))
        text(screen, f"LVL {unit.combat_level}  ({xp_c_str})", f.mono_sm, INK, (bx + bw, a - 1), right=True)
        a += 16

        bar_c = pygame.Rect(bx, a, bw, 7)
        panel(screen, bar_c, fill=SURFACE_0, border=LINE_SOFT, width=1, radius=3)
        if span_c:
            fillw = int((bar_c.w - 2) * max(0, min(into_c, span_c)) / span_c)
            if fillw > 0:
                pygame.draw.rect(screen, ACCENT, (bar_c.x + 1, bar_c.y + 1, fillw, bar_c.h - 2), border_radius=2)
        a += 11

        combat_req = (f"Down standing enemies of Lv {unit.combat_level}+ (Arena, Wilds, Ambushes)."
                      if unit.combat_level > 0
                      else "Down standing enemies of Lv 0+ (Arena, Wilds, Ambushes).")
        for line in wrap_lines([combat_req], f.body_sm, bw):
            text(screen, line, f.body_sm, INK_DIM, (bx, a))
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
        tracked(screen, "WORK", f.label, INFO, (bx, a))
        text(screen, f"LVL {unit.work_level}  ({xp_w_str})", f.mono_sm, INK, (bx + bw, a - 1), right=True)
        a += 16

        bar_w = pygame.Rect(bx, a, bw, 7)
        panel(screen, bar_w, fill=SURFACE_0, border=LINE_SOFT, width=1, radius=3)
        if span_w:
            fillw = int((bar_w.w - 2) * max(0, min(into_w, span_w)) / span_w)
            if fillw > 0:
                pygame.draw.rect(screen, ACCENT, (bar_w.x + 1, bar_w.y + 1, fillw, bar_w.h - 2), border_radius=2)
        a += 11

        jobs = progression.eligible_work_activities(unit.work_level, unit)
        work_req = ("Execute: " + ", ".join(jobs)
                    if jobs
                    else f"No standard activities teach past Lv {unit.work_level} yet.")
        for line in wrap_lines([work_req], f.body_sm, bw):
            text(screen, line, f.body_sm, INK_DIM, (bx, a))
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
        tracked(screen, "RACIAL", f.label, INFO, (bx, a))
        text(screen, f"LVL {unit.racial_level}  ({xp_r_str})", f.mono_sm, INK, (bx + bw, a - 1), right=True)
        a += 16

        bar_r = pygame.Rect(bx, a, bw, 7)
        panel(screen, bar_r, fill=SURFACE_0, border=LINE_SOFT, width=1, radius=3)
        if span_r:
            fillw = int((bar_r.w - 2) * max(0, min(into_r, span_r)) / span_r)
            if fillw > 0:
                pygame.draw.rect(screen, ACCENT, (bar_r.x + 1, bar_r.y + 1, fillw, bar_r.h - 2), border_radius=2)
        a += 11

        racial_req = f"Total track levels: {unit.racial_xp} (Combat {unit.combat_level} + Work {unit.work_level}). Grants +1 HD/lvl."
        if unit.racial_level < 5:
            racial_req += f" First racial talent at Lv 5 ({5 - unit.racial_level} to go)."
        else:
            racial_req += " Racial talent tree unlocked."
        for line in wrap_lines([racial_req], f.body_sm, bw):
            text(screen, line, f.body_sm, INK_DIM, (bx, a))
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
            tracked(screen, "STUDY", f.label, INFO, (bx, a))
            text(screen, f"{target_name}  ({cur_pts}/{total_needed} pts)", f.mono_sm, INK, (bx + bw, a - 1), right=True)
            a += 16

            bar_s = pygame.Rect(bx, a, bw, 7)
            panel(screen, bar_s, fill=SURFACE_0, border=LINE_SOFT, width=1, radius=3)
            if total_needed > 0:
                fillw = int((bar_s.w - 2) * max(0, min(cur_pts, total_needed)) / total_needed)
                if fillw > 0:
                    pygame.draw.rect(screen, ACCENT, (bar_s.x + 1, bar_s.y + 1, fillw, bar_s.h - 2), border_radius=2)
            a += 11

            study_req = "Studying at taverna (rent rooms). Rolls daily progress toward mastery."
            for line in wrap_lines([study_req], f.body_sm, bw):
                text(screen, line, f.body_sm, INK_DIM, (bx, a))
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
    def _draw_tabs(self, screen, W, pad):
        """Right-aligned pill strip on the title row: MEMBERS | REPUTATIONS."""
        f = self.fonts
        has_tutorial = self.tutorial_key() is not None
        x = W - pad - (28 + SP2 if has_tutorial else 0)
        for key, lbl in reversed(TABS):
            w = f.body_bd.size(lbl)[0] + 2 * SP3
            r = pygame.Rect(x - w, pad - 4, w, 28)
            x = r.x - SP2
            active = self.tab == key
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if (active or hov) else SURFACE_1,
                  border=ACCENT if active else LINE_SOFT, width=2 if active else 1,
                  radius=RADIUS)
            text(screen, lbl, f.body_bd, ACCENT if active else INK_DIM,
                 r.center, center=True)
            self.tab_hits.append((r, key))

    def _draw_reputacoes(self, screen, W, top, outer):
        """The REPUTATIONS tab: per faction, the score, the deeds that earn it
        (done + open) and -- arena only -- what the score unlocks. A flowing list
        (no fixed-height box), so it grows with the faction count. Reputation
        moves only by completing deeds (`factions`)."""
        f = self.fonts
        done = set(self.guild.deeds_done)
        x = outer
        w = min(W - 2 * outer, 900)
        y = top + SP2

        for i, fac in enumerate(factions.FACTIONS.values()):
            if i:
                pygame.draw.line(screen, LINE_SOFT, (x, y), (x + w, y))
                y += SP4
            rep = self.guild.reputation.get(fac.id, 0)
            tracked(screen, fac.name.upper(), f.label, INFO, (x, y))
            text(screen, str(rep), f.num_lg, ACCENT, (x, y + 14))
            text(screen, fac.blurb, f.body_sm, INK_DIM, (x + 56, y + 26))
            y += 52

            y = section(screen, "DEEDS", x, y, w, f)
            deeds = factions.DEEDS_BY_FACTION[fac.id]
            if not deeds:
                text(screen, "None yet — this faction's standing doesn't move.",
                     f.body_sm, INK_FAINT, (x, y))
                y += 20
            for d in deeds:
                got = d.id in done
                pygame.draw.circle(screen, OK if got else INK_FAINT, (x + 4, y + 8), 4,
                                   0 if got else 1)
                text(screen, d.name, f.body, OK if got else INK, (x + 16, y))
                text(screen, f"{d.blurb}  (+{d.rep} rep)" + ("" if got else "  --  open"),
                     f.body_sm, INK_DIM, (x + 200, y + 2))
                y += 24
            y += SP3

            unlocks = factions.get_unlocks(fac.id)
            if unlocks:
                y = section(screen, "NEXT UNLOCKS", x, y, w, f)
                for u in unlocks:
                    unlocked = rep >= u.rep_required
                    col = OK if unlocked else INK_DIM
                    status = "UNLOCKED" if unlocked else f"Req: Rep {u.rep_required}"
                    text(screen, f"{u.title} ({status})", f.body, col, (x + 16, y))
                    text(screen, u.description, f.body_sm, INK_FAINT, (x + 240, y + 2))
                    y += 24
                y += SP3

            y += SP4

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen, W, H, pad):
        show_distribute = False
        if self.member is not None:
            grp = self.guild.group_of(self.member)
            show_distribute = bool(grp and len(grp.members) > 1)
        footer_bar(self, screen,
                  secondary=("distribute", "DISTRIBUTE LOAD") if show_distribute else None,
                  primary=("back", "BACK TO MAP"), margin=pad)

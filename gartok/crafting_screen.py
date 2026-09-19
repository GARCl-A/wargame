"""The Forge: craft items using recipes and materials.

Requires members to have learned recipes.
Materials are consumed immediately.
Progress requires rolling a 1d20+INT over hours.
"""

from collections import Counter

import pygame

from . import data, economy
from .screen import Screen
from .ui.primitives import (caps, draw_button, footer_bar, panel, section, text,
                            token_badge)
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .widgets import ButtonsMixin

SIDE_W = 340

class CraftingScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.group = group
        self.on_done = on_done
        # List members that have recipes
        self.crafters = [u for u in group.members if u.recipes]
        self.selected_crafter = self.crafters[0] if self.crafters else None

        self.buttons = []         # [(key, rect)]
        self.roster_rows = []     # [(rect, member)]
        self.notices = []

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False,
                   danger=False, font=None, sub=None):
        """Draws through `ui.primitives.draw_button`, keeping `ButtonsMixin`'s
        own hit-registration bookkeeping (`self.buttons`/`self._hot`) -- see
        `map_screen.MapScreen.add_button` for the precedent."""
        draw_button(surf, self._F, rect, label, sub=sub, primary=primary, danger=danger,
                   enabled=enabled, mpos=self.mouse, fnt=font)
        hov = enabled and rect.collidepoint(self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or hov
        return hov

    def handle_escape(self):
        return False

    def _has_materials(self, crafter, recipe):
        recipe_data = data.CRAFTING_RECIPES.get(recipe)
        if not recipe_data:
            return False
        need = Counter(recipe_data["materials"])
        return all(crafter.count_of(mat) >= qty for mat, qty in need.items())

    def handle_event(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        px = event.pos
        
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "done":
                    self.on_done()
                elif key.startswith("work:"):
                    parts = key.split(":")
                    hours = int(parts[1])
                    recipe = parts[2]
                    self.notices = self.guild.crafting_shift(self.selected_crafter, recipe, hours)
                return

        for rect, m in self.roster_rows:
            if rect.collidepoint(px):
                self.selected_crafter = m
                self.notices = []
                return

    def draw(self, screen):
        F = self._F
        m = T.S * 3
        screen.fill(T.TABLE)
        self._reset_buttons()
        self.roster_rows = []

        text(screen, F["titleb"], "THE FORGE", (m, m - 2), T.TX)
        text(screen, F["body"], "forge weapons and armor  ·  needs recipes and materials",
             (m, m + 30), T.TX_MUTED)

        top = m + 62
        left_panel = pygame.Rect(m, top, SIDE_W, screen.get_height() - top - 72)
        right_panel = pygame.Rect(left_panel.right + m, top,
                                  screen.get_width() - left_panel.right - 2 * m, left_panel.h)

        self._draw_roster(screen, left_panel)
        self._draw_crafting(screen, right_panel)
        self._draw_footer(screen)

    def _draw_roster(self, screen, area):
        from .combatant import Combatant
        from .ui.sheet_card import draw_row, unit_to_ch

        F = self._F
        panel(screen, area)
        y = section(screen, F, "CRAFTERS", area.x + 12, area.y + 12, area.w - 24)

        def _trailing(surf, r, ch):
            u = ch["unit"]
            caps(surf, F["micro"], f"{len(u.recipes)} RECIPES", (r.right - T.S * 2, r.centery - 10), T.TX_MUTED, right=True)
            if u.crafting_target:
                caps(surf, F["micro"], "IN PROGRESS", (r.right - T.S * 2, r.centery + 10), T.BRASS, right=True)

        for m in self.group.members:
            if not m.recipes:
                continue

            r = pygame.Rect(area.x + 12, y, area.w - 24, 74)
            sel = m is self.selected_crafter
            
            c = Combatant(m)
            draw_row(screen, F, r, unit_to_ch(c), selected=sel, draw_trailing=_trailing)

            self.roster_rows.append((r, m))
            y += 74 + T.S

    def _draw_crafting(self, screen, area):
        F = self._F
        panel(screen, area)
        x = area.x + 12
        w = area.w - 24
        y = section(screen, F, "RECIPES", x, area.y + 12, w)

        if not self.selected_crafter:
            return

        m = self.selected_crafter

        for r_name in m.recipes:
            r_data = data.CRAFTING_RECIPES.get(r_name)
            if not r_data:
                continue

            is_active = m.crafting_target == r_name
            r = pygame.Rect(x, y, w, 110)
            hov = r.collidepoint(self.mouse)
            panel(screen, r, hover=is_active or hov, width=2 if is_active else 1)

            text(screen, F["bodyb"], r_name, (r.x + T.S, r.y + T.S), T.TX)

            target_val = sum(economy.PRICES.get(mat, 10) for mat in r_data["materials"]) + r_data["complexity"]

            materials_str = ", ".join(r_data["materials"])

            if is_active:
                status_color = T.BRASS
                status_text = f"IN PROGRESS: {m.crafting_progress}/{target_val} progress"
            else:
                has_mat = self._has_materials(m, r_name)
                status_color = T.GREEN if has_mat else T.BLOOD
                status_text = f"Target Progress: {target_val} (Roll: 1d20 + {m.mod_intelligence})"
                if not has_mat:
                    status_text += " - MISSING MATERIALS"

            text(screen, F["body_sm"], f"Materials: {materials_str}",
                 (r.x + T.S, r.y + T.S + 20), T.TX_MUTED)
            text(screen, F["body_sm"], status_text, (r.x + T.S, r.y + T.S + 40), status_color)

            if is_active or self._has_materials(m, r_name):
                bw = 100
                bx = r.x + T.S
                by = r.y + T.S + 65
                for h in [1, 4, 8]:
                    btn_r = pygame.Rect(bx, by, bw, 32)
                    self.add_button(screen, btn_r, f"work:{h}:{r_name}", f"Work {h}h",
                                    font=F["body_sm"])
                    bx += bw + T.S
            else:
                text(screen, F["body_sm"], "Requires materials in personal pack to start.",
                     (r.x + T.S, r.y + T.S + 65), T.TX_FAINT)

            y += 110 + T.S

    def _draw_footer(self, screen):
        F = self._F
        m = T.S * 3
        y = screen.get_height() - 52
        ny = y - 22
        for notice in self.notices:
            text(screen, F["body_sm"], notice, (m, ny), T.BRASS)
            ny -= 20

        footer_bar(self, screen, F, primary=("done", "LEAVE THE FORGE"))

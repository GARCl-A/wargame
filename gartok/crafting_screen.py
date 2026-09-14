"""The Forge: craft items using recipes and materials.

Requires members to have learned recipes.
Materials are consumed immediately.
Progress requires rolling a 1d20+INT over hours.
"""

import pygame

from . import data, economy
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, ellipsize, panel, section,
                    text, token_badge)

SIDE_W = 340

class CraftingScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.on_done = on_done
        # List members that have recipes
        self.crafters = [u for u in group.members if u.recipes]
        self.selected_crafter = self.crafters[0] if self.crafters else None
        
        self.buttons = []         # [(key, rect)]
        self.roster_rows = []     # [(rect, member)]
        self.notices = []

    def handle_escape(self):
        return False

    def _has_materials(self, crafter, recipe):
        recipe_data = data.CRAFTING_RECIPES.get(recipe)
        if not recipe_data:
            return False
        inv = list(crafter._base_inventory)
        for mat in recipe_data["materials"]:
            if mat in inv:
                inv.remove(mat)
            else:
                return False
        return True

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
        f = self.fonts
        screen.fill((18, 19, 24))
        self.buttons = []
        self.roster_rows = []

        text(screen, "THE FORGE", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, "forge weapons and armor  ·  needs recipes and materials", f.body, INK_DIM,
             (MARGIN, MARGIN + 30))

        top = MARGIN + 62
        left_panel = pygame.Rect(MARGIN, top, SIDE_W, screen.get_height() - top - 72)
        right_panel = pygame.Rect(left_panel.right + MARGIN, top,
                                  screen.get_width() - left_panel.right - 2 * MARGIN, left_panel.h)

        self._draw_roster(screen, left_panel)
        self._draw_crafting(screen, right_panel)
        self._draw_footer(screen)

    def _draw_roster(self, screen, area):
        f = self.fonts
        panel(screen, area, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
        x = area.x + SP3
        w = area.w - 2 * SP3
        y = section(screen, "CRAFTERS", x, area.y + SP3, w, f)

        if not self.crafters:
            text(screen, "No one in this group knows any recipes.", f.body_sm, INK_FAINT, (x, y))
            return

        for m in self.crafters:
            r = pygame.Rect(x, y, w, 52)
            sel = m is self.selected_crafter
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=ACCENT if sel else SURFACE_3 if hov else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=1, radius=RADIUS)

            tok = (r.x + SP2 + 12, r.y + SP2 + 12)
            token_badge(screen, tok, m, f)
            text(screen, m.name, f.body, ACCENT_INK if sel else INK, (tok[0] + 24, r.y + SP2))
            text(screen, f"{len(m.recipes)} recipes known", f.body_sm,
                 ACCENT_INK if sel else INK_DIM, (tok[0] + 24, r.y + SP2 + 18))
            
            if m.crafting_target:
                text(screen, "in progress", f.label, INFO, (r.right - SP2, r.y + SP2), right=True)

            self.roster_rows.append((r, m))
            y += 52 + SP2

    def _draw_crafting(self, screen, area):
        f = self.fonts
        panel(screen, area, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
        x = area.x + SP3
        w = area.w - 2 * SP3
        y = section(screen, "RECIPES", x, area.y + SP3, w, f)

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
            panel(screen, r, fill=SURFACE_3 if hov else SURFACE_1,
                  border=INFO if is_active else LINE_SOFT, width=2 if is_active else 1, radius=RADIUS)
                  
            text(screen, r_name, f.body_bd, INK, (r.x + SP2, r.y + SP2))
            
            target_val = sum(data.PRICES.get(mat, 10) for mat in r_data["materials"]) + r_data["complexity"]
            
            materials_str = ", ".join(r_data["materials"])
            
            if is_active:
                status_color = INFO
                status_text = f"IN PROGRESS: {m.crafting_progress}/{target_val} progress"
            else:
                has_mat = self._has_materials(m, r_name)
                status_color = OK if has_mat else DANGER
                status_text = f"Target Progress: {target_val} (Roll: 1d20 + {m.mod_intelligence})"
                if not has_mat:
                    status_text += " - MISSING MATERIALS"

            text(screen, f"Materials: {materials_str}", f.body_sm, INK_DIM, (r.x + SP2, r.y + SP2 + 20))
            text(screen, status_text, f.body_sm, status_color, (r.x + SP2, r.y + SP2 + 40))

            if is_active or self._has_materials(m, r_name):
                # Draw buttons for 1h, 4h, 8h
                bw = 100
                bx = r.x + SP2
                by = r.y + SP2 + 65
                for h in [1, 4, 8]:
                    btn_r = pygame.Rect(bx, by, bw, 32)
                    b_hov = btn_r.collidepoint(self.mouse)
                    panel(screen, btn_r, fill=SURFACE_3 if b_hov else SURFACE_2, border=LINE_SOFT, radius=RADIUS)
                    text(screen, f"Work {h}h", f.body_sm, INK, btn_r.center, center=True)
                    self.buttons.append((f"work:{h}:{r_name}", btn_r))
                    bx += bw + SP2
            else:
                text(screen, "Requires materials in personal pack to start.", f.body_sm, INK_FAINT, (r.x + SP2, r.y + SP2 + 65))
            
            y += 110 + SP2

    def _draw_footer(self, screen):
        f = self.fonts
        y = screen.get_height() - 52

        ny = y - 22
        for notice in self.notices:
            text(screen, notice, f.body_sm, INFO, (MARGIN, ny))
            ny -= 20

        done = pygame.Rect(screen.get_width() - MARGIN - 240, y, 240, 36)
        hovd = done.collidepoint(self.mouse)
        panel(screen, done, fill=ACCENT if hovd else SURFACE_3, border=ACCENT,
              width=1, radius=RADIUS)
        text(screen, "LEAVE THE FORGE", f.body_bd, ACCENT_INK if hovd else ACCENT,
             done.center, center=True)
        self.buttons.append(("done", done))

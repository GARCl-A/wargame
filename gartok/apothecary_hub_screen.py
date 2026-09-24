"""The Apothecary Hub: wraps crafting and jobs in a single tabbed screen."""

import pygame

from .screen import Screen
from .crafting_screen import CraftingScreen
from .apothecary_mission_screen import ApothecaryMissionScreen
from .ui.primitives import draw_button
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class ApothecaryHubScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.tab = "craft"
        
        self.craft_screen = CraftingScreen(fonts, guild, group, on_done,
                                           title="THE APOTHECARY",
                                           subtitle="brew potions and draughts  ·  needs recipes and materials")
        self.jobs_screen = ApothecaryMissionScreen(self._F, guild, group, on_done)
        
        self.buttons = []

    def active_screen(self):
        return self.craft_screen if self.tab == "craft" else self.jobs_screen

    def handle_escape(self):
        return self.active_screen().handle_escape()

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            px = event.pos
            for key, rect in self.buttons:
                if rect.collidepoint(px):
                    self.tab = key
                    return

        self.active_screen().mouse = self.mouse
        self.active_screen().handle_event(event)

    def update(self, dt):
        self.active_screen().update(dt)

    def draw(self, screen):
        # Draw the active screen
        self.active_screen().mouse = self.mouse
        self.active_screen().draw(screen)
        
        self._hot = getattr(self.active_screen(), '_hot', False)

        # Draw our tabs in the top right
        m = T.S * 3
        bw = 120
        F = self._F
        
        # We start from the right edge
        self.buttons = []
        x = screen.get_width() - m - bw
        
        # Jobs tab
        r_jobs = pygame.Rect(x, m, bw, 32)
        draw_button(screen, F, r_jobs, "JOBS", primary=self.tab == "jobs", 
                    enabled=self.tab != "jobs", mpos=self.mouse)
        if self.tab != "jobs":
            self.buttons.append(("jobs", r_jobs))
        self._hot = self._hot or r_jobs.collidepoint(self.mouse)
        
        x -= bw + T.S
        
        # Craft tab
        r_craft = pygame.Rect(x, m, bw, 32)
        draw_button(screen, F, r_craft, "CRAFT", primary=self.tab == "craft", 
                    enabled=self.tab != "craft", mpos=self.mouse)
        if self.tab != "craft":
            self.buttons.append(("craft", r_craft))
        self._hot = self._hot or r_craft.collidepoint(self.mouse)

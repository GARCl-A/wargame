"""The Bank Hub: wraps the strongbox and bankers' jobs in a single tabbed screen."""

import pygame

from .screen import Screen
from .bank_screen import BankScreen
from .trust_screen import TrustScreen
from .ui.primitives import draw_button
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class BankHubScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.tab = "vault"
        
        self.vault_screen = BankScreen(fonts, guild, group, on_done)
        self.jobs_screen = TrustScreen(self._F, guild, group, on_done)
        
        self.buttons = []

    def active_screen(self):
        return self.vault_screen if self.tab == "vault" else self.jobs_screen

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
        
        # Vault tab
        r_vault = pygame.Rect(x, m, bw, 32)
        draw_button(screen, F, r_vault, "VAULT", primary=self.tab == "vault", 
                    enabled=self.tab != "vault", mpos=self.mouse)
        if self.tab != "vault":
            self.buttons.append(("vault", r_vault))
        self._hot = self._hot or r_vault.collidepoint(self.mouse)

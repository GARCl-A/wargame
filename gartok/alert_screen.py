"""Generic alert popup used for starvation, death, and hunger notifications."""

import pygame

from .screen import Screen
from .theme import (ACCENT, DANGER, INK, INK_DIM, LINE_SOFT, RADIUS, SP2, SP3,
                    SURFACE_1, SURFACE_2, SURFACE_3, panel, set_pointer, text)


class AlertScreen(Screen):
    def __init__(self, fonts, resume_to, title, messages, on_done, is_danger=False):
        super().__init__()
        self.fonts = fonts
        self.resume_to = resume_to
        self.native = getattr(resume_to, "native", False)
        self.title = title
        self.messages = messages
        self.on_done = on_done
        self.is_danger = is_danger
        self.buttons = []

    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "ok":
                    self.on_done()
                return

    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        
        # Draw background scene
        try:
            self.resume_to.mouse = (-1, -1)
            self.resume_to.draw(screen)
        except Exception:
            screen.fill(SURFACE_1)
            
        # Draw veil
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((6, 7, 12, 210))
        screen.blit(veil, (0, 0))

        # Measure content
        title_surf = f.title.render(self.title, True, DANGER if self.is_danger else ACCENT)
        msg_surfs = [f.body.render(m, True, INK) for m in self.messages]
        
        box_w = max([title_surf.get_width()] + [s.get_width() for s in msg_surfs]) + SP3 * 2
        box_w = max(box_w, 400)
        box_h = SP3 * 2 + title_surf.get_height() + SP2 + sum(s.get_height() + 4 for s in msg_surfs) + SP3 + 40
        
        bx = (W - box_w) // 2
        by = (H - box_h) // 2

        # Draw box
        panel(screen, (bx, by, box_w, box_h))
        
        y = by + SP3
        screen.blit(title_surf, (bx + SP3, y))
        y += title_surf.get_height() + SP2
        
        for s in msg_surfs:
            screen.blit(s, (bx + SP3, y))
            y += s.get_height() + 4
            
        y += SP3

        # OK button
        self.buttons = []
        bw, bh = max(120, f.label.size("OK")[0] + 32), 40
        btn_rect = pygame.Rect(bx + box_w - SP3 - bw, by + box_h - SP3 - bh, bw, bh)
        
        hover = btn_rect.collidepoint(self.mouse)
        bg = SURFACE_3 if hover else SURFACE_2
        pygame.draw.rect(screen, bg, btn_rect, border_radius=RADIUS)
        pygame.draw.rect(screen, LINE_SOFT, btn_rect, 1, border_radius=RADIUS)
        text(screen, "OK", f.label, INK if hover else INK_DIM, btn_rect.center, center=True)
        self.buttons.append(("ok", btn_rect))

        set_pointer(hover)

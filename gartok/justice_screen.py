"""The guard catches up: shown when `campaign.advance` pauses a group at a
jurisdiction node because the guard test (`justice.catch`) caught one or more
of its members with a rap sheet. Three ways out, decided for the WHOLE catch
at once -- the group can't do two different things with itself simultaneously:

- ACCEPT ARREST -- `campaign.resolve_guard_prison`, resolved right here.
- FIGHT THE PATROL -- `app._start_guard_battle` drops the whole group into a
  real, lethal fight; `app._battle_end` reads the crime consequences back
  through `campaign.resolve_guard_fight_aftermath` once it's over.
- RUN -- `campaign.resolve_guard_flee`, resolved right here.
"""

import pygame

from .screen import Screen
from .theme import (ACCENT, DANGER, INFO, INK, INK_DIM, LINE_SOFT,
                    MARGIN, RADIUS, SP2, SP3, SURFACE_2, SURFACE_3,
                    panel, text, token_badge)


class GuardScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, order, caught, on_prison, on_flee, on_fight):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.order = order
        self.caught = caught          # roster Units the guard test caught
        self.on_prison = on_prison
        self.on_flee = on_flee
        self.on_fight = on_fight
        self.buttons = []             # [(key, rect)]

    def tutorial_key(self):
        return None

    # ------------------------------------------------------------------ #
    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "prison":
                self.on_prison(self.group, self.order)
            elif key == "flee":
                self.on_flee(self.group, self.order)
            elif key == "fight":
                self.on_fight(self.group, self.order)
            return

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((24, 18, 18))
        self.buttons = []

        text(screen, "THE GUARD", f.title, INK, (MARGIN, MARGIN - 2))
        names = ", ".join(u.name for u in self.caught)
        text(screen, f"{names} -- recognised on sight.", f.body, DANGER,
             (MARGIN, MARGIN + 30))

        top = MARGIN + 80
        for u in self.caught:
            r = pygame.Rect(MARGIN, top, 420, 48)
            panel(screen, r, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
            tok = (r.x + SP3 + 12, r.y + 12)
            token_badge(screen, tok, u, f)
            text(screen, u.name, f.body_bd, INK, (tok[0] + 24, r.y + 6))
            text(screen, f"crime: {u.crime}", f.body_sm, INK_DIM, (tok[0] + 24, r.y + 24))
            top = r.bottom + SP2

        top += SP2
        w = min(560, screen.get_width() - 2 * MARGIN)

        top = self._option(screen, "prison", "ACCEPT ARREST",
                           "Crime clears to 0 -- time served in the City's cells.",
                           top, w, INFO)
        top = self._option(screen, "fight", "FIGHT THE PATROL",
                           "Lethal. Living through it adds to the rap sheet, not clears it.",
                           top, w, DANGER)
        if self.order.prev_node is not None:      # nowhere left to fall back to otherwise
            top = self._option(screen, "flee", "RUN",
                               "Fall back the way the group came.",
                               top, w, ACCENT)

    def _option(self, screen, key, label, sub, top, w, col):
        f = self.fonts
        r = pygame.Rect(MARGIN, top, w, 56)
        hov = r.collidepoint(self.mouse)
        panel(screen, r, fill=SURFACE_3 if hov else SURFACE_2, border=col,
              width=2 if hov else 1, radius=RADIUS)
        text(screen, label, f.body_bd, col, (r.x + SP3, r.y + 8))
        text(screen, sub, f.body_sm, INK_DIM, (r.x + SP3, r.y + 30))
        self.buttons.append((key, r))
        return r.bottom + SP2

"""The guard catches up: shown when `campaign.advance` pauses a group at a
jurisdiction node because the guard test (`justice.catch`) caught one or more
of its members with a rap sheet. Three ways out, decided for the WHOLE catch
at once -- the group can't do two different things with itself simultaneously:

- ACCEPT ARREST -- `campaign.resolve_guard_prison`, resolved right here.
- FIGHT THE PATROL -- `app._start_guard_battle` drops the whole group into a
  real, lethal fight; `app._battle_end` reads the crime consequences back
  through `campaign.resolve_guard_fight_aftermath` once it's over.
- RUN -- `campaign.resolve_guard_flee`, resolved right here. Falling back can
  itself land the group on a new "guard" (re-caught) or "ambush" (an unsafe
  fallback node) pause -- `app._resolve_guard_flee` re-queues that through the
  normal `_pending` dispatch, so this same screen (or a forced battle) can
  come right back up instead of the flee being the end of it.
"""

import pygame

from .screen import Screen
from .theme import set_pointer, token_badge
from .ui.primitives import draw_card, header, panel, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class GuardScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, order, caught, on_prison, on_flee, on_fight):
        super().__init__()
        self.fonts = fonts
        self._F = None
        self.guild = guild
        self.group = group
        self.order = order
        self.caught = caught          # roster Units the guard test caught
        self.on_prison = on_prison
        self.on_flee = on_flee
        self.on_fight = on_fight
        self.buttons = []             # [(key, rect)]

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

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
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.buttons = []

        head = pygame.Rect(0, 0, W, T.S * 9)
        names = ", ".join(u.name for u in self.caught)
        sub = f"{names} -- recognised on sight."
        header(screen, F, head, "THE GUARD", sub, (), None, mpos=self.mouse)

        top = head.bottom + T.S * 4
        for u in self.caught:
            r = pygame.Rect(T.S * 3, top, 420, 48)
            panel(screen, r)
            tok = (r.x + T.S * 2, r.y + 12)
            token_badge(screen, tok, u, self.fonts)
            text(screen, F["bodyb"], u.name, (tok[0] + 24, r.y + 6), T.TX)
            text(screen, F["body_sm"], f"crime: {u.crime}", (tok[0] + 24, r.y + 24), T.TX_MUTED)
            top = r.bottom + T.S * 2

        top += T.S * 2
        w = min(560, W - 2 * T.S * 3)

        top = self._option(screen, F, "prison", "ACCEPT ARREST",
                           "Crime clears to 0 -- time served in the City's cells.",
                           top, w)
        top = self._option(screen, F, "fight", "FIGHT THE PATROL",
                           "Lethal. Living through it adds to the rap sheet, not clears it.",
                           top, w)
        if self.order.prev_node is not None:      # nowhere left to fall back to otherwise
            top = self._option(screen, F, "flee", "RUN",
                               "Fall back the way the group came.",
                               top, w)

        set_pointer(any(r.collidepoint(self.mouse) for _, r in self.buttons))

    def _option(self, screen, F, key, label, sub, top, w):
        r = pygame.Rect(T.S * 3, top, w, 72)
        hov = r.collidepoint(self.mouse)
        draw_card(screen, F, r, label, subtitle=sub, hover=hov)
        self.buttons.append((key, r))
        return r.bottom + T.S * 2

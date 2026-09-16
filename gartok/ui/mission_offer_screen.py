"""Base class for city NPC screens offering a single active job."""

import pygame

from .. import factions, missions
from ..screen import Screen
from .primitives import caps, draw_button, panel, text, wrap
from .tokens import T

CARD_W = 560


class MissionOfferScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.notice = None
        self.buttons = []              # [(key, rect)]
        self._hot = False

    # ------------------------------------------------------------------ #
    # Subclasses must implement these properties and methods:
    # ------------------------------------------------------------------ #
    @property
    def title_text(self):
        raise NotImplementedError

    @property
    def subtitle_text(self):
        raise NotImplementedError

    @property
    def accept_label(self):
        raise NotImplementedError

    @property
    def leave_label(self):
        raise NotImplementedError

    def get_template(self):
        raise NotImplementedError

    def get_req_str(self, t):
        raise NotImplementedError

    def get_status_str(self, t, progress, ready, days_left):
        raise NotImplementedError

    def get_turn_in_label(self, t, progress, ready):
        raise NotImplementedError

    def get_success_notice(self, reward):
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    @property
    def _template(self):
        return self.get_template()

    @property
    def _offered(self):
        """Whether `_template` can be freshly accepted here right now
        (`missions.offers_at` -- the "one job out at a time" rule)."""
        t = self._template
        return t is not None and t in missions.offers_at(self.guild, self.group.node)

    @property
    def _active(self):
        """This giver's one job out right now, if any, regardless of who's
        holding it."""
        t = self._template
        if t is None:
            return None
        return next((m for m in self.guild.missions
                     if m.template_id == t.id and m.state == "active"), None)

    @property
    def _mission(self):
        """The active job, but only if the group standing here right now is
        the one sharing it (its signer is one of `self.group.members`)."""
        m = self._active
        if m is None:
            return None
        return m if any(u.uid == m.unit_uid for u in self.group.members) else None

    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "accept":
                t = self._template
                if t is not None and self._offered:
                    missions.accept(self.guild, self.group.leader, t)
            elif key == "turn_in":
                m = self._mission
                if m is not None and missions.can_turn_in(self.guild, m):
                    t = missions.template_of(m)
                    earned = missions.turn_in(self.guild, m)
                    self.notice = self.get_success_notice(t.reward)
                    for d in earned:
                        self.notice += "  ·  " + factions.deed_notice(d)
            elif key == "done":
                self.on_done()
                return
            return

    def draw(self, screen):
        F = self.fonts
        screen.fill(T.TABLE)
        self.buttons.clear()

        caps(screen, F["big"], self.title_text, (T.S * 3, T.S * 3), T.TX)
        text(screen, F["body"], self.subtitle_text, (T.S * 3, T.S * 3 + 36), T.TX_MUTED)

        t = self._template
        if t is None:
            card = pygame.Rect(T.S * 3, T.S * 3 + 80,
                               min(CARD_W, screen.get_width() - 2 * T.S * 3), 150)
            panel(screen, card)
            text(screen, F["body_sm"], "Nothing on offer here right now.", (card.x + T.S * 3, card.y + T.S * 3), T.TX_FAINT)
            self._draw_footer(screen)
            return

        m = self._mission
        card_w = min(CARD_W, screen.get_width() - 2 * T.S * 3)
        w = card_w - 2 * T.S * 3
        lines = wrap(F["body_sm"], t.blurb, w) if m is None else []
        desc_h = len(lines) * 18 if lines else 20
        card_h = 20 + desc_h + 16 + 20 + 30 + 36 + 2 * T.S * 3 + 10
        card = pygame.Rect(T.S * 3, T.S * 3 + 80, card_w, max(150, card_h))
        panel(screen, card)
        
        x, y = card.x + T.S * 3, card.y + T.S * 3

        caps(screen, F["head"], t.name, (x, y), T.TX)
        y += 26
        
        offered = self._offered
        if m is None:
            for ln in lines:
                text(screen, F["body_sm"], ln, (x, y), T.TX_MUTED)
                y += 18
            y += 16
            
            req_str = self.get_req_str(t)
            text(screen, F["body_sm"], req_str, (x, y), T.BRASS)
            y += 30
            
            r = pygame.Rect(x, y, w, 36)
            label = self.accept_label if offered else "ALREADY OUT WITH ANOTHER GROUP"
            draw_button(screen, F, r, label, enabled=offered, primary=offered, mpos=self.mouse)
            self.buttons.append(("accept", r))
        else:
            progress = missions.progress(self.guild, m)
            ready = progress >= t.goal_qty
            days_left = m.deadline_day - self.guild.clock.day
            
            status_str = self.get_status_str(t, progress, ready, days_left)
            text(screen, F["body"], status_str, (x, y), T.GREEN if ready else T.TX_MUTED)
            y += 30
            
            r = pygame.Rect(x, y, w, 36)
            label = self.get_turn_in_label(t, progress, ready)
            draw_button(screen, F, r, label, enabled=ready, primary=ready, mpos=self.mouse)
            self.buttons.append(("turn_in", r))

        self._draw_footer(screen)

    def _draw_footer(self, screen):
        F = self.fonts
        
        if self.notice:
            notice_rect = pygame.Rect(T.S * 3, screen.get_height() - T.S * 6, screen.get_width() - 240 - T.S * 6, 36)
            text(screen, F["body"], self.notice, (notice_rect.x, notice_rect.centery - 6), T.BRASS)

        r = pygame.Rect(screen.get_width() - 240 - T.S * 3, screen.get_height() - 36 - T.S * 3, 240, 36)
        draw_button(screen, F, r, self.leave_label, mpos=self.mouse)
        self.buttons.append(("done", r))

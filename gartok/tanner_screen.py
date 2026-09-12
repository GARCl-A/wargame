"""The tanner: a City NPC offering a paid, time-boxed job (`missions.py`) --
distinct from the market (buy/sell, unlimited except a few scarce lines) and
the bank (shared storage). `self.group` is just whoever walked up right now --
the group's **leader** is who actually signs (same "who speaks for the group"
convention as market haggling), and the job then travels with that unit, not
this particular group (see `missions.py`'s module docstring).
"""

import pygame

from . import factions, missions
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, INFO, INK, INK_DIM, INK_FAINT, LINE_SOFT,
                    MARGIN, OK, RADIUS, SP3, SURFACE_1, SURFACE_2, SURFACE_3,
                    panel, text)

CARD_W = 560


class TannerScreen(Screen):
    native = True
    GIVER = "tanner"

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.notice = None
        self.buttons = []              # [(key, rect)]

    # No soft tutorial card yet (see `tutorial.py`'s `TUTORIALS`) -- the base
    # `Screen.tutorial_key` default (None) is correct until one is authored.

    # ------------------------------------------------------------------ #
    @property
    def _template(self):
        """The one job this NPC hands out at this node -- resolved by giver +
        node (like `missions.offers_at` itself reads), not a hardcoded id, so
        a second template here doesn't need a new branch in this screen."""
        return next((t for t in missions.TEMPLATES.values()
                     if t.giver == self.GIVER and t.node == self.group.node), None)

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
                    reward = missions.template_of(m).reward
                    earned = missions.turn_in(self.guild, m)
                    self.notice = f"paid out {reward} copper, split across the group."
                    for d in earned:
                        self.notice += "  ·  " + factions.deed_notice(d)
            elif key == "done":
                self.on_done()
                return
            return

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self.buttons = []

        text(screen, "THE TANNER", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, "\"Bring me hide and I'll pay well for it.\"", f.body, INK_DIM,
             (MARGIN, MARGIN + 30))

        card = pygame.Rect(MARGIN, MARGIN + 70,
                           min(CARD_W, screen.get_width() - 2 * MARGIN), 150)
        panel(screen, card, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
        x, y, w = card.x + SP3, card.y + SP3, card.w - 2 * SP3
        t = self._template
        if t is None:
            text(screen, "Nothing on offer here right now.", f.body_sm, INK_DIM, (x, y))
            self._draw_footer(screen)
            return
        m = self._mission

        text(screen, t.name, f.body_bd, INK, (x, y))
        y += 20
        offered = self._offered
        if m is None:
            text(screen, t.blurb, f.body_sm, INK_DIM, (x, y))
            y += 34
            text(screen, f"goal: {t.goal_qty}x {t.goal_item}  ·  pay: {t.reward} "
                 f"copper  ·  deadline: {t.deadline_days} days", f.mono_sm, INFO, (x, y))
            y += 30
            r = pygame.Rect(x, y, w, 36)
            hov = offered and r.collidepoint(self.mouse)
            panel(screen, r, fill=ACCENT if hov else SURFACE_3 if offered else SURFACE_1,
                  border=ACCENT if offered else LINE_SOFT, width=1, radius=RADIUS)
            label = "ACCEPT THE JOB" if offered else "ALREADY OUT WITH ANOTHER GROUP"
            text(screen, label, f.body_bd,
                 ACCENT_INK if hov else ACCENT if offered else INK_FAINT,
                 r.center, center=True)
            if offered:
                self.buttons.append(("accept", r))
        else:
            progress = missions.progress(self.guild, m)
            ready = progress >= t.goal_qty
            days_left = m.deadline_day - self.guild.clock.day
            text(screen, f"{progress} / {t.goal_qty} {t.goal_item}  ·  "
                 f"{days_left} day(s) left", f.body_sm, OK if ready else INK_DIM, (x, y))
            y += 30
            r = pygame.Rect(x, y, w, 36)
            hov = ready and r.collidepoint(self.mouse)
            panel(screen, r, fill=ACCENT if hov else SURFACE_3 if ready else SURFACE_1,
                  border=ACCENT if ready else LINE_SOFT, width=1, radius=RADIUS)
            label = "TURN IN" if ready else f"NEED {t.goal_qty - progress} MORE"
            text(screen, label, f.body_bd,
                 ACCENT_INK if hov else ACCENT if ready else INK_FAINT,
                 r.center, center=True)
            if ready:
                self.buttons.append(("turn_in", r))

        self._draw_footer(screen)

    def _draw_footer(self, screen):
        f = self.fonts
        y = screen.get_height() - 52
        if self.notice:
            text(screen, self.notice, f.body_sm, INFO, (MARGIN, y - 22))

        done = pygame.Rect(screen.get_width() - MARGIN - 240, y, 240, 36)
        hovd = done.collidepoint(self.mouse)
        panel(screen, done, fill=ACCENT if hovd else SURFACE_3, border=ACCENT,
              width=1, radius=RADIUS)
        text(screen, "LEAVE THE TANNER", f.body_bd, ACCENT_INK if hovd else ACCENT,
             done.center, center=True)
        self.buttons.append(("done", done))

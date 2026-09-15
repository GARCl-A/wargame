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
from .theme import (INFO, INK, INK_DIM, LINE_SOFT, MARGIN, OK, RADIUS, SP3,
                    SURFACE_2, panel, text, wrap_lines, blit_block)
from .widgets import ButtonsMixin, footer_bar

CARD_W = 560


class TannerScreen(ButtonsMixin, Screen):
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
        self._hot = False

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
        self._reset_buttons()

        text(screen, "THE TANNER", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, "\"Bring me hide and I'll pay well for it.\"", f.body, INK_DIM,
             (MARGIN, MARGIN + 30))

        t = self._template
        if t is None:
            card = pygame.Rect(MARGIN, MARGIN + 70,
                               min(CARD_W, screen.get_width() - 2 * MARGIN), 150)
            panel(screen, card, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
            text(screen, "Nothing on offer here right now.", f.body_sm, INK_DIM, (card.x + SP3, card.y + SP3))
            self._draw_footer(screen)
            return
        m = self._mission
        card_w = min(CARD_W, screen.get_width() - 2 * MARGIN)
        w = card_w - 2 * SP3
        lines = wrap_lines([t.blurb], f.body_sm, w) if m is None else []
        desc_h = len(lines) * 18 if lines else 20
        card_h = 20 + desc_h + 16 + 20 + 30 + 36 + 2 * SP3 + 10
        card = pygame.Rect(MARGIN, MARGIN + 70, card_w, max(150, card_h))
        panel(screen, card, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
        x, y = card.x + SP3, card.y + SP3

        text(screen, t.name, f.body_bd, INK, (x, y))
        y += 20
        offered = self._offered
        if m is None:
            y = blit_block(screen, lines, x, y, f.body_sm, INK_DIM, lh=18)
            y += 16
            text(screen, f"goal: {t.goal_qty}x {t.goal_item}  ·  pay: {t.reward} "
                 f"copper  ·  deadline: {t.deadline_days} days", f.mono_sm, INFO, (x, y))
            y += 30
            r = pygame.Rect(x, y, w, 36)
            label = "ACCEPT THE JOB" if offered else "ALREADY OUT WITH ANOTHER GROUP"
            self.add_button(screen, r, "accept", label, enabled=offered, primary=offered)
        else:
            progress = missions.progress(self.guild, m)
            ready = progress >= t.goal_qty
            days_left = m.deadline_day - self.guild.clock.day
            text(screen, f"{progress} / {t.goal_qty} {t.goal_item}  ·  "
                 f"{days_left} day(s) left", f.body_sm, OK if ready else INK_DIM, (x, y))
            y += 30
            r = pygame.Rect(x, y, w, 36)
            label = "TURN IN" if ready else f"NEED {t.goal_qty - progress} MORE"
            self.add_button(screen, r, "turn_in", label, enabled=ready, primary=ready)

        self._draw_footer(screen)

    def _draw_footer(self, screen):
        footer_bar(self, screen, primary=("done", "LEAVE THE TANNER"), notice=self.notice)

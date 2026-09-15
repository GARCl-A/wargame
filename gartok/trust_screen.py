"""The Bankers' trust mission: offered and turned in at the City (Ankareth),
same "one job out at a time" shape `missions.py` already gives every giver --
this is a dedicated screen rather than a reuse of `tanner_screen.py` because
the flavor (a test of trust, not a gathering job) and giver ("bankers", not
"tanner") are different enough to read as their own place, even though the
underlying mechanism (`missions.accept`/`can_turn_in`/`turn_in`) is identical.

Accepting hands the signer a sealed chest (`missions.TRUST_CHEST.starting_item`)
instead of asking the guild to gather anything; the "goal" `turn_in` counts is
a letter of receipt, traded for the chest at Ledger Hold
(`ledger_screen.py`) once the group gets there safely.
"""

import pygame

from . import factions, missions
from .screen import Screen
from .theme import (INFO, INK, INK_DIM, LINE_SOFT, MARGIN, OK, RADIUS, SP3,
                    SURFACE_2, panel, text, wrap_lines, blit_block)
from .widgets import ButtonsMixin, footer_bar

CARD_W = 560


class TrustScreen(ButtonsMixin, Screen):
    native = True
    TEMPLATE = missions.TRUST_CHEST

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.notice = None
        self.buttons = []              # [(key, rect)]
        self._hot = False

    # No soft tutorial card yet (see tanner_screen.py's own note).

    # ------------------------------------------------------------------ #
    @property
    def _offered(self):
        return self.TEMPLATE in missions.offers_at(self.guild, self.group.node)

    @property
    def _active(self):
        return next((m for m in self.guild.missions
                    if m.template_id == self.TEMPLATE.id and m.state == "active"), None)

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
                if self._offered:
                    missions.accept(self.guild, self.group.leader, self.TEMPLATE)
            elif key == "turn_in":
                m = self._mission
                if m is not None and missions.can_turn_in(self.guild, m):
                    earned = missions.turn_in(self.guild, m)
                    self.notice = "the Bankers accept the letter -- your trust is earned."
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

        text(screen, "THE BANKERS", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, "\"Prove the guild can be trusted with something precious.\"",
             f.body, INK_DIM, (MARGIN, MARGIN + 30))

        card_w = min(CARD_W, screen.get_width() - 2 * MARGIN)
        w = card_w - 2 * SP3
        t = self.TEMPLATE
        m = self._mission
        lines = wrap_lines([t.blurb], f.body_sm, w) if m is None else []
        desc_h = len(lines) * 18 if lines else 20
        card_h = 20 + desc_h + 16 + 20 + 30 + 36 + 2 * SP3 + 10
        card = pygame.Rect(MARGIN, MARGIN + 70, card_w, max(150, card_h))
        panel(screen, card, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
        x, y = card.x + SP3, card.y + SP3

        text(screen, t.name, f.body_bd, INK, (x, y))
        y += 20
        if m is None:
            y = blit_block(screen, lines, x, y, f.body_sm, INK_DIM, lh=18)
            y += 16
            text(screen, f"carry: {t.starting_item}  ·  bring back: {t.goal_item}  ·  "
                 f"deadline: {t.deadline_days} days", f.mono_sm, INFO, (x, y))
            y += 30
            offered = self._offered
            r = pygame.Rect(x, y, w, 36)
            label = "ACCEPT THE TEST OF TRUST" if offered else "ALREADY OUT WITH ANOTHER GROUP"
            self.add_button(screen, r, "accept", label, enabled=offered, primary=offered)
        else:
            progress = missions.progress(self.guild, m)
            ready = progress >= t.goal_qty
            days_left = m.deadline_day - self.guild.clock.day
            status = (f"{t.goal_item} in hand  ·  {days_left} day(s) left" if ready else
                      f"carrying the sealed chest to Ledger Hold  ·  {days_left} day(s) left")
            text(screen, status, f.body_sm, OK if ready else INK_DIM, (x, y))
            y += 30
            r = pygame.Rect(x, y, w, 36)
            label = "TURN IN THE LETTER" if ready else "NOT BACK YET"
            self.add_button(screen, r, "turn_in", label, enabled=ready, primary=ready)

        self._draw_footer(screen)

    def _draw_footer(self, screen):
        footer_bar(self, screen, primary=("done", "LEAVE THE BANKERS"), notice=self.notice)

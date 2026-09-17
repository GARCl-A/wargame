"""Base class for city NPC screens offering a single active job."""

import pygame

from .. import factions, missions
from ..screen import Screen
from ..theme import set_pointer
from .primitives import caps, draw_button, hline, modal_card, text, wrap
from .tokens import T

CARD_W = 560
FOOTER_H = T.S * 4 + 34   # gap + divider + gap + leave button


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
        card_w = min(CARD_W, screen.get_width() - 2 * T.S * 3)
        w = card_w - 2 * T.S * 3
        t = self._template

        screen.fill(T.TABLE)
        self.buttons.clear()

        rows = self._content_rows(screen, t, w)
        content_h = sum(h for h, _ in rows)
        card = modal_card(screen, (card_w, content_h + FOOTER_H + 2 * T.S * 3))

        x, y = card.x + T.S * 3, card.y + T.S * 3
        for h, draw_row in rows:
            draw_row(x, y)
            y += h

        self._draw_leave_row(screen, card, y)

    def _content_rows(self, screen, t, w):
        """`(height, draw_row(x, y))` per line of card content -- the same
        list both sums to the card's height and paints it, so the two can
        never drift the way a hand-computed height formula would."""
        F = self.fonts

        def row(font, s, color, h, fn=caps):
            return (h, lambda x, y: fn(screen, font, s, (x, y), color))

        rows = [
            row(F["big"], self.title_text, T.TX, 32),
            row(F["body"], self.subtitle_text, T.TX_MUTED, 40, fn=text),
        ]

        if t is None:
            rows.append(row(F["body_sm"], "Nothing on offer here right now.", T.TX_FAINT, 36, fn=text))
            return rows

        rows.append(row(F["head"], t.name, T.TX, 26))

        m = self._mission
        offered = self._offered
        if m is None:
            for ln in wrap(F["body_sm"], t.blurb, w):
                rows.append(row(F["body_sm"], ln, T.TX_MUTED, 18, fn=text))
            rows.append((16, lambda x, y: None))
            rows.append(row(F["body_sm"], self.get_req_str(t), T.BRASS, 30, fn=text))

            label = self.accept_label if offered else "ALREADY OUT WITH ANOTHER GROUP"

            def draw_accept(x, y):
                r = pygame.Rect(x, y, w, 36)
                draw_button(screen, F, r, label, enabled=offered, primary=offered, mpos=self.mouse)
                self.buttons.append(("accept", r))
            rows.append((36, draw_accept))
        else:
            progress = missions.progress(self.guild, m)
            ready = progress >= t.goal_qty
            days_left = m.deadline_day - self.guild.clock.day
            status_str = self.get_status_str(t, progress, ready, days_left)
            rows.append(row(F["body"], status_str, T.GREEN if ready else T.TX_MUTED, 30, fn=text))

            label = self.get_turn_in_label(t, progress, ready)

            def draw_turn_in(x, y):
                r = pygame.Rect(x, y, w, 36)
                draw_button(screen, F, r, label, enabled=ready, primary=ready, mpos=self.mouse)
                self.buttons.append(("turn_in", r))
            rows.append((36, draw_turn_in))

        return rows

    def _draw_leave_row(self, screen, card, y):
        """Draws forward from `y` (the content rows' end) for exactly
        `FOOTER_H` -- keeping the footer sized off the same rows that size
        the card, instead of a second anchor from `card.bottom` that can
        drift out of sync with a shorter card and overlap the last row."""
        F = self.fonts
        x = card.x + T.S * 3

        if self.notice:
            text(screen, F["body_sm"], self.notice, (x, y + T.S), T.BRASS)

        y += T.S * 2
        hline(screen, x, card.right - T.S * 3, y)
        y += T.S * 2
        r = pygame.Rect(card.right - T.S * 3 - 220, y, 220, 34)
        draw_button(screen, F, r, self.leave_label, mpos=self.mouse)
        self.buttons.append(("done", r))

        set_pointer(any(rect.collidepoint(self.mouse) for _, rect in self.buttons))

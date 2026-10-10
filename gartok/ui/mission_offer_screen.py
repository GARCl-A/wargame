"""Base class for city NPC screens offering a single active job."""

import pygame

from .. import factions, missions
from ..screen import Screen
from .primitives import (
    caps,
    contained,
    draw_button,
    hline,
    modal_card,
    set_pointer,
    text,
    wrap,
)
from .tokens import T, mix
from .tokens import fonts as ui_fonts

CARD_W = 560

TAG_COLOR = {
    "economic": T.BRASS,
    "trust": T.BRASS,
    "bankers": T.BRASS_DIM,
    "apothecary": T.GREEN,
    "library": T.TX_MUTED,
    "tanner": T.TX_MUTED,
    "scholarly": T.TX_MUTED,
    "ruins": T.BLOOD,
}


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

    # Subclasses must implement these properties and methods:
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
    def _completed(self):
        t = self._template
        if t is None:
            return False
        return any(m.template_id == t.id and m.state in ("done", "failed")
                   for m in self.guild.missions)

    @property
    def _mission(self):
        """The active job, but only if the group standing here right now is
        the one sharing it (its signer is one of `self.group.members`)."""
        m = self._active
        if m is None:
            return None
        return m if any(u.uid == m.unit_uid for u in self.group.members) else None

    def tutorial_key(self):
        return "missions"

    def handle_escape(self):
        self.on_done()
        return True

    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "accept":
                t = self._template
                if t is not None and self._offered:
                    missions.accept(self.guild, self.group.leader, t)
                    self.notice = None
            elif key == "turn_in":
                m = self._mission
                if m is not None and missions.can_turn_in(self.guild, m):
                    t = missions.template_of(m)
                    earned = missions.turn_in(self.guild, m)
                    self.notice = self.get_success_notice(t.reward)
                    if t.reward_recipe:
                        self.notice += f"  ·  the group learns to craft the {t.reward_recipe}"
                    for d in earned:
                        self.notice += "  ·  " + factions.deed_notice(d)
            elif key == "done":
                self.on_done()
                return
            return

    def draw(self, screen):
        F = self.fonts if (isinstance(self.fonts, dict) and "body" in self.fonts) else ui_fonts()
        screen.fill(T.TABLE)
        self.buttons.clear()

        card_w = min(CARD_W, screen.get_width() - 2 * T.S * 3)
        pad = T.S * 3
        inner_w = card_w - 2 * pad

        t = self._template
        m = self._mission
        offered = self._offered

        subtitle_lines = wrap(F["body"], self.subtitle_text, inner_w) if self.subtitle_text else []
        header_h = 30 + (len(subtitle_lines) * 22 if subtitle_lines else 0)

        qpad = T.S * 2
        qw = inner_w - 2 * qpad

        if t is None:
            quest_card_h = 70
        else:
            tags = getattr(t, "tags", ()) or ((t.tag,) if getattr(t, "tag", None) else ())
            title_h = 24
            tags_h = 22 if tags else 0

            blurb_lines = wrap(F["body_sm"], t.blurb, qw) if getattr(t, "blurb", None) else []
            blurb_h = len(blurb_lines) * 18

            if m is None:
                req_str = self.get_req_str(t)
                req_lines = wrap(F["body_sm"], req_str, qw)
                req_h = len(req_lines) * 20
                detail_h = req_h
            else:
                progress = missions.progress(self.guild, m)
                ready = progress >= t.goal_qty
                days_left = missions.days_left(self.guild, m)
                status_str = self.get_status_str(t, progress, ready, days_left)
                status_lines = wrap(F["body"], status_str, qw)
                detail_h = len(status_lines) * 24

            btn_h = 36
            quest_card_h = (qpad + title_h +
                            (tags_h + 8 if tags else 0) +
                            (blurb_h + 12 if blurb_lines else 0) +
                            detail_h + 16 + btn_h + qpad)

        notice_lines = []
        notice_h = 0
        if self.notice:
            notice_lines = wrap(F["body_sm"], self.notice, inner_w - 24)
            notice_h = 10 + len(notice_lines) * 18 + 10

        footer_btn_h = 34
        footer_h = T.S * 2 + 1 + T.S * 2 + footer_btn_h

        card_h = pad + header_h + T.S * 2 + quest_card_h
        if self.notice:
            card_h += T.S * 2 + notice_h
        card_h += footer_h + pad

        card = modal_card(screen, (card_w, card_h))

        with contained(screen, card):
            cx = card.x + pad
            cy = card.y + pad

            caps(screen, F["head"], self.title_text, (cx, cy), T.TX)
            cy += 30
            for ln in subtitle_lines:
                text(screen, F["body"], ln, (cx, cy), T.TX_MUTED)
                cy += 22

            cy += T.S * 2

            quest_rect = pygame.Rect(cx, cy, inner_w, quest_card_h)
            pygame.draw.rect(screen, T.STEEL_HI, quest_rect, border_radius=4)
            pygame.draw.rect(screen, T.STEEL_LINE, quest_rect, 1, border_radius=4)

            with contained(screen, quest_rect):
                if t is None:
                    text(screen, F["body_sm"], "Nothing on offer here right now.",
                         quest_rect.center, T.TX_FAINT, center=True)
                else:
                    qx = quest_rect.x + qpad
                    qy = quest_rect.y + qpad

                    caps(screen, F["head"], t.name, (qx, qy), T.TX)
                    qy += 24

                    if tags:
                        qy += 4
                        tx = qx
                        for tag in tags:
                            label = tag.upper()
                            col = TAG_COLOR.get(tag.lower(), T.TX_MUTED)
                            pw = F["microb"].size(label)[0] + 12
                            pill = pygame.Rect(tx, qy, pw, 18)
                            pygame.draw.rect(screen, T.TABLE, pill, border_radius=4)
                            pygame.draw.rect(screen, col, pill, 1, border_radius=4)
                            text(screen, F["microb"], label, pill.center, col, center=True)
                            tx += pw + T.S
                        qy += 22 + 4

                    if blurb_lines:
                        for ln in blurb_lines:
                            text(screen, F["body_sm"], ln, (qx, qy), T.TX_MUTED)
                            qy += 18
                        qy += 12

                    if m is None:
                        for ln in req_lines:
                            text(screen, F["body_sm"], ln, (qx, qy), T.BRASS)
                            qy += 20

                        wait = missions.retry_in(self.guild, t)
                        if wait:
                            label = f"FAILED -- TRY AGAIN IN {wait} DAY(S)"
                        elif self._completed:
                            label = ("JOB COMPLETED" if any(x.template_id == t.id and x.state == "done"
                                                            for x in self.guild.missions)
                                     else "JOB FAILED")
                        elif offered:
                            label = self.accept_label
                        else:
                            label = "ALREADY OUT WITH ANOTHER GROUP"

                        btn_r = pygame.Rect(qx, quest_rect.bottom - qpad - btn_h, qw, btn_h)
                        draw_button(screen, F, btn_r, label, enabled=offered, primary=offered, mpos=self.mouse)
                        self.buttons.append(("accept", btn_r))
                    else:
                        for ln in status_lines:
                            text(screen, F["body"], ln, (qx, qy), T.GREEN if ready else T.TX_MUTED)
                            qy += 24

                        label = self.get_turn_in_label(t, progress, ready)
                        btn_r = pygame.Rect(qx, quest_rect.bottom - qpad - btn_h, qw, btn_h)
                        draw_button(screen, F, btn_r, label, enabled=ready, primary=ready, mpos=self.mouse)
                        self.buttons.append(("turn_in", btn_r))

            cy = quest_rect.bottom

            if self.notice:
                cy += T.S * 2
                r_notice = pygame.Rect(cx, cy, inner_w, notice_h)
                pygame.draw.rect(screen, mix(T.BRASS, T.TABLE, 0.90), r_notice, border_radius=4)
                pygame.draw.rect(screen, mix(T.BRASS, T.STEEL_LINE, 0.4), r_notice, 1, border_radius=4)
                with contained(screen, r_notice):
                    ny = r_notice.y + 10
                    for ln in notice_lines:
                        text(screen, F["body_sm"], ln, (r_notice.x + 12, ny), T.BRASS)
                        ny += 18
                cy = r_notice.bottom

            cy += T.S * 2
            hline(screen, cx, card.right - pad, cy)

            bw = 180
            btn_leave = pygame.Rect(card.right - pad - bw, card.bottom - pad - footer_btn_h, bw, footer_btn_h)
            draw_button(screen, F, btn_leave, self.leave_label, mpos=self.mouse)
            self.buttons.append(("done", btn_leave))

        self._hot = any(rect.collidepoint(self.mouse) for _, rect in self.buttons)
        set_pointer(self._hot)

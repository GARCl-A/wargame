"""Base class for NPC screens that list the jobs a giver has on the board."""

import pygame

from .. import factions, missions, world
from ..item_icon import draw_icon
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
from .vendor_panel import draw_vendor, draw_vendor_name

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
    VENDOR = None      # (node id, function) of the keeper whose face the card shows

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.notice = None
        keeper = world.vendor(*self.VENDOR) if self.VENDOR else None
        self.vendor_card = keeper.card if keeper else None
        self.buttons = []              # [(key, rect)]; key is "done" or (action, template id)
        self._hot = False
        self.scroll = 0
        self._max_scroll = 0

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

    def get_templates(self):
        """Every job the board shows, top to bottom. The default is the one
        `get_template` picks; a giver with several jobs at once overrides this."""
        t = self.get_template()
        return [] if t is None else [t]

    def get_req_str(self, t):
        raise NotImplementedError

    def get_status_str(self, t, progress, ready, days_left):
        raise NotImplementedError

    def get_turn_in_label(self, t, progress, ready):
        raise NotImplementedError

    def footer_action(self):
        """`(label, enabled)` for a second button beside the leave one (a keeper buying
        something), or None for none."""
        return None

    def run_footer_action(self):
        """Press the footer action: -> the notice to show."""
        return None

    def get_success_notice(self, reward):
        raise NotImplementedError

    @property
    def _template(self):
        """The first job on the board."""
        return next(iter(self.get_templates()), None)

    def _is_offered(self, t):
        """Whether `t` can be freshly accepted here right now
        (`missions.offers_at` -- the "one job out at a time" rule)."""
        return t in missions.offers_at(self.guild, self.group.node)

    def _active_of(self, t):
        """`t`'s job out right now, if any, regardless of who's holding it."""
        return next((m for m in self.guild.missions
                     if m.template_id == t.id and m.state == "active"), None)

    def _completed_of(self, t):
        return any(m.template_id == t.id and m.state in ("done", "failed")
                   for m in self.guild.missions)

    def _mission_of(self, t):
        """`t`'s active job, but only if the group standing here right now is
        the one sharing it (its signer is one of `self.group.members`)."""
        m = self._active_of(t)
        if m is None:
            return None
        return m if any(u.uid == m.unit_uid for u in self.group.members) else None

    @property
    def _offered(self):
        t = self._template
        return t is not None and self._is_offered(t)

    @property
    def _active(self):
        t = self._template
        return None if t is None else self._active_of(t)

    @property
    def _completed(self):
        t = self._template
        return t is not None and self._completed_of(t)

    @property
    def _mission(self):
        t = self._template
        return None if t is None else self._mission_of(t)

    def tutorial_key(self):
        return "missions"

    def handle_escape(self):
        self.on_done()
        return True

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and self._max_scroll:
            self.scroll = max(0, min(self._max_scroll, self.scroll - event.y * 40))
            return
        super().handle_event(event)

    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "done":
                self.on_done()
                return
            if key == "footer_action":
                self.notice = self.run_footer_action()
                return
            action, tid = key
            t = missions.TEMPLATES[tid]
            if action == "accept":
                if self._is_offered(t):
                    missions.accept(self.guild, self.group.leader, t)
                    self.notice = None
            elif action == "turn_in":
                m = self._mission_of(t)
                if m is not None and missions.can_turn_in(self.guild, m):
                    earned = missions.turn_in(self.guild, m)
                    self.notice = self.get_success_notice(t.reward)
                    if t.reward_recipe:
                        self.notice += f"  ·  the group learns to craft the {t.reward_recipe}"
                    if t.reward_item:
                        self.notice += f"  ·  you are given a {t.reward_item}"
                    for d in earned:
                        self.notice += "  ·  " + factions.deed_notice(d)
            return

    def _quest_layout(self, F, t, qw):
        """Everything a job's card needs to be sized and drawn, worked out once."""
        qpad = T.S * 2
        m = self._mission_of(t)
        tags = getattr(t, "tags", ()) or ((t.tag,) if getattr(t, "tag", None) else ())
        blurb_lines = wrap(F["body_sm"], t.blurb, qw) if getattr(t, "blurb", None) else []
        lay = {"t": t, "m": m, "tags": tags, "blurb_lines": blurb_lines}
        if m is None:
            lay["req_lines"] = wrap(F["body_sm"], self.get_req_str(t), qw)
            detail_h = len(lay["req_lines"]) * 20
        else:
            progress = missions.progress(self.guild, m)
            lay["progress"] = progress
            lay["ready"] = progress >= t.goal_qty
            lay["status_lines"] = wrap(F["body"], self.get_status_str(
                t, progress, lay["ready"], missions.days_left(self.guild, m)), qw)
            detail_h = len(lay["status_lines"]) * 24
        lay["h"] = (qpad + 24 + (22 + 8 if tags else 0) + (len(blurb_lines) * 18 + 12 if blurb_lines else 0)
                    + detail_h + 16 + 36 + qpad)
        return lay

    def _draw_quest(self, screen, F, rect, lay):
        t, m, qpad, btn_h = lay["t"], lay["m"], T.S * 2, 36
        qw = rect.w - 2 * qpad
        pygame.draw.rect(screen, T.STEEL_HI, rect, border_radius=4)
        pygame.draw.rect(screen, T.STEEL_LINE, rect, 1, border_radius=4)
        with contained(screen, rect):
            qx = rect.x + qpad
            qy = rect.y + qpad
            draw_icon(screen, pygame.Rect(rect.right - qpad - T.S * 5, qy, T.S * 5, T.S * 5), t.goal_item)
            caps(screen, F["head"], t.name, (qx, qy), T.TX)
            qy += 24
            if lay["tags"]:
                qy += 4
                tx = qx
                for tag in lay["tags"]:
                    label = tag.upper()
                    col = TAG_COLOR.get(tag.lower(), T.TX_MUTED)
                    pw = F["microb"].size(label)[0] + 12
                    pill = pygame.Rect(tx, qy, pw, 18)
                    pygame.draw.rect(screen, T.TABLE, pill, border_radius=4)
                    pygame.draw.rect(screen, col, pill, 1, border_radius=4)
                    text(screen, F["microb"], label, pill.center, col, center=True)
                    tx += pw + T.S
                qy += 22 + 4
            if lay["blurb_lines"]:
                for ln in lay["blurb_lines"]:
                    text(screen, F["body_sm"], ln, (qx, qy), T.TX_MUTED)
                    qy += 18
                qy += 12
            btn_r = pygame.Rect(qx, rect.bottom - qpad - btn_h, qw, btn_h)
            if m is None:
                for ln in lay["req_lines"]:
                    text(screen, F["body_sm"], ln, (qx, qy), T.BRASS)
                    qy += 20
                offered = self._is_offered(t)
                wait = missions.retry_in(self.guild, t)
                if wait:
                    label = f"FAILED -- TRY AGAIN IN {wait} DAY(S)"
                elif missions.closed(self.guild, t):
                    label = "FAILED -- IT WENT TO ANOTHER SCHOOL"
                elif self._completed_of(t):
                    label = ("JOB COMPLETED" if any(x.template_id == t.id and x.state == "done"
                                                    for x in self.guild.missions)
                             else "JOB FAILED")
                elif offered:
                    label = self.accept_label
                else:
                    label = "ALREADY OUT WITH ANOTHER GROUP"
                draw_button(screen, F, btn_r, label, enabled=offered, primary=offered, mpos=self.mouse)
                self.buttons.append((("accept", t.id), btn_r))
            else:
                for ln in lay["status_lines"]:
                    text(screen, F["body"], ln, (qx, qy), T.GREEN if lay["ready"] else T.TX_MUTED)
                    qy += 24
                ready = lay["ready"]
                label = self.get_turn_in_label(t, lay["progress"], ready)
                draw_button(screen, F, btn_r, label, enabled=ready, primary=ready, mpos=self.mouse)
                self.buttons.append((("turn_in", t.id), btn_r))

    def draw(self, screen):
        F = self.fonts if (isinstance(self.fonts, dict) and "body" in self.fonts) else ui_fonts()
        screen.fill(T.TABLE)
        self.buttons.clear()

        card_w = min(CARD_W, screen.get_width() - 2 * T.S * 3)
        pad = T.S * 3
        inner_w = card_w - 2 * pad
        gap = T.S

        face = T.S * 7 if self.vendor_card else 0
        subtitle_lines = (wrap(F["body"], self.subtitle_text, inner_w - face - T.S * 2)
                          if self.subtitle_text else [])
        name_h = 20 if self.vendor_card else 0
        header_h = max(30 + name_h + (len(subtitle_lines) * 22 if subtitle_lines else 0), face)

        layouts = [self._quest_layout(F, t, inner_w - 4 * T.S) for t in self.get_templates()]
        list_h = (sum(lay["h"] for lay in layouts) + gap * (len(layouts) - 1)) if layouts else 70

        notice_lines = []
        notice_h = 0
        if self.notice:
            notice_lines = wrap(F["body_sm"], self.notice, inner_w - 24)
            notice_h = 10 + len(notice_lines) * 18 + 10

        footer_btn_h = 34
        footer_h = T.S * 2 + 1 + T.S * 2 + footer_btn_h
        chrome_h = pad + header_h + T.S * 2 + (T.S * 2 + notice_h if self.notice else 0) + footer_h + pad
        visible_h = max(120, min(list_h, screen.get_height() - T.S * 4 - chrome_h))
        self._max_scroll = max(0, list_h - visible_h)
        self.scroll = min(self.scroll, self._max_scroll)

        card = modal_card(screen, (card_w, chrome_h + visible_h))

        with contained(screen, card):
            cx = card.x + pad
            cy = card.y + pad

            draw_vendor(screen, F, (cx + inner_w - face, cy), self.vendor_card, size=face)
            caps(screen, F["head"], self.title_text, (cx, cy), T.TX)
            draw_vendor_name(screen, F, (cx, cy + 28), self.vendor_card)
            cy += 30 + name_h
            for ln in subtitle_lines:
                text(screen, F["body"], ln, (cx, cy), T.TX_MUTED)
                cy += 22

            cy += T.S * 2

            list_rect = pygame.Rect(cx, cy, inner_w, visible_h)
            with contained(screen, list_rect):
                if not layouts:
                    box = pygame.Rect(cx, cy, inner_w, 70)
                    pygame.draw.rect(screen, T.STEEL_HI, box, border_radius=4)
                    pygame.draw.rect(screen, T.STEEL_LINE, box, 1, border_radius=4)
                    text(screen, F["body_sm"], "Nothing on offer here right now.",
                         box.center, T.TX_FAINT, center=True)
                y = cy - self.scroll
                for lay in layouts:
                    self._draw_quest(screen, F, pygame.Rect(cx, y, inner_w, lay["h"]), lay)
                    y += lay["h"] + gap
            self.buttons = [(k, r.clip(list_rect)) for k, r in self.buttons]
            self.buttons = [(k, r) for k, r in self.buttons if r.w and r.h]

            cy = list_rect.bottom

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
            extra = self.footer_action()
            if extra is not None:
                label, enabled = extra
                aw = min(T.S * 36, btn_leave.x - cx - T.S * 2)
                btn_extra = pygame.Rect(btn_leave.x - T.S * 2 - aw, btn_leave.y, aw, footer_btn_h)
                draw_button(screen, F, btn_extra, label, enabled=enabled, primary=enabled, mpos=self.mouse)
                if enabled:
                    self.buttons.append(("footer_action", btn_extra))

        self._hot = any(rect.collidepoint(self.mouse) for _, rect in self.buttons)
        set_pointer(self._hot)

"""Base class for NPC screens that list the jobs a giver has on the board."""

import pygame

from .. import factions, missions, world
from ..constants import fmt_money
from ..item_icon import draw_icon
from ..screen import Screen
from .hub_body import draw_chip, draw_panel
from .hub_frame import button_width, hub_button
from .primitives import caps, contained, ellipsize, set_pointer, small_caps, text, wrap
from .tokens import T, mix
from .tokens import fonts as ui_fonts
from .vendor_panel import draw_vendor, draw_vendor_name

CARD_MIN_W = T.S * 70           # a job card's width; the board lays as many columns as fit
CARD_PAD = T.S * 3
ICON = T.S * 7
BTN_H = T.S * 5 + 4

TAG_TONE = {"economic": "money", "trust": "money", "bankers": "money", "apothecary": "good", "ruins": "bad"}


class MissionOfferScreen(Screen):
    native = True
    VENDOR = None      # (node id, function) of the keeper whose face the card shows
    framed = False     # a hub's tab: the hub draws the keeper, the tabs and the back

    def hub_cards(self):
        """The jobs board's cards: how many jobs are up, how many the guild holds here."""
        templates = self.get_templates()
        ids = {t.id for t in templates}
        held = sum(1 for m in self.guild.missions if m.template_id in ids and m.state == "active")
        purse = sum(u.money for u in self.group.members)
        return [{"label": "jobs on the board", "value": str(len(templates))},
                {"label": "taken", "value": str(held)},
                {"label": "party purse", "value": fmt_money(purse), "tone": "money"}]

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

    def _quest_layout(self, F, t, w):
        """Everything a job's card needs to be sized and drawn, worked out once for a card `w` wide."""
        m = self._mission_of(t)
        tags = getattr(t, "tags", ()) or ((t.tag,) if getattr(t, "tag", None) else ())
        tw = w - CARD_PAD * 2 - ICON - T.S * 2
        body = F["hub_body"]
        lay = {"t": t, "m": m, "tags": tags,
               "blurb_lines": wrap(body, t.blurb, tw) if getattr(t, "blurb", None) else []}
        if m is None:
            lay["detail"] = wrap(body, self.get_req_str(t), tw)
        else:
            progress = missions.progress(self.guild, m)
            lay["progress"] = progress
            lay["ready"] = progress >= t.goal_qty
            lay["detail"] = wrap(body, self.get_status_str(t, progress, lay["ready"],
                                                           missions.days_left(self.guild, m)), tw)
        lh = body.get_linesize()
        text_h = (T.S * 4 + (T.S * 4 if tags else 0) + (len(lay["blurb_lines"]) * lh + T.S if lay["blurb_lines"] else 0)
                  + len(lay["detail"]) * lh + T.S * 2 + BTN_H)
        lay["h"] = CARD_PAD * 2 + max(ICON, text_h)
        return lay

    def _job_button(self, t, m, lay):
        """`(key, label, enabled)` of the button at the foot of `t`'s card."""
        if m is not None:
            ready = lay["ready"]
            return ("turn_in", t.id), self.get_turn_in_label(t, lay["progress"], ready), ready
        offered = self._is_offered(t)
        wait = missions.retry_in(self.guild, t)
        if wait:
            label = f"Failed: try again in {wait} day{'s' if wait != 1 else ''}"
        elif missions.closed(self.guild, t):
            label = "Failed: it went to another school"
        elif self._completed_of(t):
            done = any(x.template_id == t.id and x.state == "done" for x in self.guild.missions)
            label = "Job completed" if done else "Job failed"
        elif offered:
            label = self.accept_label
        else:
            label = "Out with another group"
        return ("accept", t.id), label, offered

    def _draw_quest(self, screen, F, rect, lay):
        t, m = lay["t"], lay["m"]
        pygame.draw.rect(screen, mix(T.STEEL, T.BRASS, 0.05) if m else mix(T.STEEL, T.TABLE, 0.35), rect,
                         border_radius=6)
        pygame.draw.rect(screen, T.BRASS_DIM if m else T.STEEL_LINE, rect, 1, border_radius=6)
        icon = pygame.Rect(rect.x + CARD_PAD, rect.y + CARD_PAD, ICON, ICON)
        draw_icon(screen, icon, t.goal_item)
        x = icon.right + T.S * 2
        right = rect.right - CARD_PAD
        y = rect.y + CARD_PAD - 2
        small_caps(screen, F["hub_card"], F["hub_card_sc"], ellipsize(t.name, F["hub_card"], right - x), (x, y), T.TX)
        y += T.S * 4
        if lay["tags"]:
            cx = x
            for tag in lay["tags"]:
                cx = draw_chip(screen, F, (cx, y), tag.lower(), TAG_TONE.get(tag.lower(), "muted")).right + T.S
            y += T.S * 4
        lh = F["hub_body"].get_linesize()
        for ln in lay["blurb_lines"]:
            text(screen, F["hub_body"], ln, (x, y), T.TX_MUTED)
            y += lh
        if lay["blurb_lines"]:
            y += T.S
        color = T.BRASS if m is None else (T.GREEN if lay["ready"] else T.TX)
        for ln in lay["detail"]:
            text(screen, F["hub_body"], ln, (x, y), color)
            y += lh
        key, label, enabled = self._job_button(t, m, lay)
        btn = pygame.Rect(x, rect.bottom - CARD_PAD - BTN_H, right - x, BTN_H)
        hub_button(screen, F, btn, label, primary=True, enabled=enabled, mpos=self.mouse)
        self.buttons.append((key, btn))

    def draw(self, screen):
        F = ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.buttons.clear()
        m = T.S * 5

        top = 0
        if not self.framed:
            face = draw_vendor(screen, F, (T.S * 3, T.S * 3), self.vendor_card, size=T.S * 7) if self.vendor_card else 0
            caps(screen, F["head"], self.title_text, (T.S * 3 + face, T.S * 3), T.TX)
            draw_vendor_name(screen, F, (T.S * 3 + face, T.S * 7), self.vendor_card)
            top = T.S * 12
        notice_lines = wrap(F["hub_body"], self.notice, W - 2 * m) if self.notice else []
        lh = F["hub_body"].get_linesize()
        bottom = H - T.S * 4 - len(notice_lines) * lh - (T.S * 9 if not self.framed else 0)
        panel_r = pygame.Rect(m, top, W - 2 * m, bottom - top)
        inner = draw_panel(screen, F, panel_r, "Jobs", self.subtitle_text or None)

        extra = self.footer_action()
        list_bottom = inner.bottom
        if extra is not None:
            foot_y = panel_r.bottom - T.S * 11
            pygame.draw.line(screen, T.STEEL_LINE, (panel_r.x, foot_y), (panel_r.right - 1, foot_y))
            label, enabled = extra
            b = pygame.Rect(inner.x, foot_y + T.S * 3, inner.w, BTN_H + T.S)
            hub_button(screen, F, b, label, primary=True, enabled=enabled, mpos=self.mouse)
            if enabled:
                self.buttons.append(("footer_action", b))
            list_bottom = foot_y - T.S * 2
        list_rect = pygame.Rect(inner.x - T.S, inner.y, inner.w + T.S * 2, list_bottom - inner.y)

        templates = self.get_templates()
        cols = max(1, min(3, list_rect.w // CARD_MIN_W))
        gap = T.S * 2
        col_w = (list_rect.w - gap * (cols - 1)) // cols
        layouts = [self._quest_layout(F, t, col_w) for t in templates]
        heights = [0] * cols
        placed = []
        for lay in layouts:
            c = heights.index(min(heights))
            placed.append((c, heights[c], lay))
            heights[c] += lay["h"] + gap
        list_h = max(heights) - gap if layouts else 0
        self._max_scroll = max(0, list_h - list_rect.h)
        self.scroll = min(self.scroll, self._max_scroll)

        job_buttons = []
        with contained(screen, list_rect):
            if not layouts:
                text(screen, F["hub_body"], "Nothing on offer here right now.", (inner.x, inner.y), T.TX_FAINT)
            outer, self.buttons = self.buttons, []
            for c, y, lay in placed:
                self._draw_quest(screen, F, pygame.Rect(list_rect.x + c * (col_w + gap), list_rect.y + y - self.scroll,
                                                        col_w, lay["h"]), lay)
            job_buttons, self.buttons = self.buttons, outer
        self.buttons += [(k, r.clip(list_rect)) for k, r in job_buttons if r.clip(list_rect).w]
        if self._max_scroll:
            text(screen, F["hub_sub"], "scroll for more jobs", (inner.right, panel_r.bottom - T.S * 3), T.TX_FAINT,
                 right=True)

        y = panel_r.bottom + T.S
        for ln in notice_lines:
            text(screen, F["hub_body"], ln, (m, y), T.BRASS)
            y += lh
        if not self.framed:
            leave = pygame.Rect(m, H - T.S * 9, button_width(F, self.leave_label), T.S * 6)
            hub_button(screen, F, leave, self.leave_label, mpos=self.mouse)
            self.buttons.append(("done", leave))

        self._hot = any(rect.collidepoint(self.mouse) for _, rect in self.buttons)
        set_pointer(self._hot)

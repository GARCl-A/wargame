"""Level screen: one XP track per column, its talent tree below, picks to spend.

Opened from a member's card on the guild screen (`on_level`). Each track shows a
progress bar to the next level and the nodes of `talents.TREE[track]`; a track
with an unspent pick lights its available nodes -- click one to take it
(`Unit.choose_talent`). The mean of the track levels drives hit dice, handled on
XP gain, so nothing to do here but spend picks. `on_back` returns to the guild.

Renders at the real window resolution (`native = True`), like the guild screen.
"""

import pygame

from . import progression, talents
from .screen import Screen
from .theme import (ACCENT, INFO, INK, INK_DIM, INK_FAINT, LINE_SOFT, MARGIN, OK,
                    RADIUS, SP2, SP3, SP4, SP5, SURFACE_0, SURFACE_1, SURFACE_2,
                    SURFACE_3, panel, set_pointer, text, token_badge, tracked,
                    wrap_lines)

_TRACK_XP = {"combat": progression.COMBAT_XP_THRESHOLDS,
             "work": progression.WORK_XP_THRESHOLDS}
_TRACK_LABEL = {"combat": "COMBAT", "work": "WORK"}


def _check(surf, cx, cy, col):
    """A small drawn checkmark (no font glyph -- those go missing in bold)."""
    pygame.draw.lines(surf, col, False,
                      [(cx - 4, cy), (cx - 1, cy + 4), (cx + 5, cy - 5)], 2)


class LevelScreen(Screen):
    native = True

    def __init__(self, fonts, unit, on_back, on_change=None):
        super().__init__()
        self.fonts = fonts
        self.unit = unit
        self.on_back = on_back
        self.on_change = on_change            # called after a pick lands (autosave)
        self.node_hits = []                  # [(rect, track, talent_id)]
        self.buttons = []                   # [(key, rect)]
        self._hot = False                   # cursor is over something clickable

    # ------------------------------------------------------------------ #
    def _click(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px) and key == "back":
                self.on_back()
                return
        for rect, track, tid in self.node_hits:
            if rect.collidepoint(px):
                if self.unit.choose_talent(track, tid) and self.on_change:
                    self.on_change()
                return

    def _node_state(self, track, t):
        u = self.unit
        if t.id in u.talents[track]:
            return "taken"
        blocked = t.requires and t.requires not in u.talents[track]
        if not blocked and u.picks_available(track) > 0:
            return "open"
        return "locked"

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        u = self.unit
        W, H = screen.get_size()
        screen.fill(SURFACE_0)
        self.node_hits = []
        self.buttons = []
        pad = MARGIN if W < 1500 else SP5

        text(screen, "PROGRESSION", f.title, INK, (pad, pad))

        iy = pad + 46
        tok = (pad + 17, iy + 15)
        token_badge(screen, tok, u, f, r=17)
        text(screen, u.name, f.card_name, INK, (tok[0] + 30, iy))
        dice = len(u._level_hp_rolls)
        sub = (f"{u.race['name']}  ·  {u.occupation['name']}  ·  mean level {u.mean_level}"
               + (f"  ·  +{dice} hit {'die' if dice == 1 else 'dice'}" if dice else ""))
        text(screen, sub, f.body_sm, INK_DIM, (tok[0] + 30, iy + 22))

        div = iy + 48
        pygame.draw.line(screen, LINE_SOFT, (pad, div), (W - pad, div))

        top = div + SP4
        gap = SP4
        col_w = min(560, (W - 2 * pad - gap) // 2)
        self._hot = False
        for i, track in enumerate(talents.TRACKS):
            x = pad + i * (col_w + gap)
            self._draw_track(screen, track, x, top, col_w, H - top - 68)

        self._draw_footer(screen, W, H, pad)
        set_pointer(self._hot)

    # ------------------------------------------------------------------ #
    def _draw_track(self, screen, track, x, y, w, h):
        f = self.fonts
        u = self.unit
        panel(screen, pygame.Rect(x, y, w, h), fill=SURFACE_1, border=LINE_SOFT, radius=RADIUS)
        ix = x + SP4
        iw = w - 2 * SP4
        cy = y + SP4

        level = u.track_level[track]
        picks = u.picks_available(track)
        tracked(screen, _TRACK_LABEL[track], f.label, INFO, (ix, cy))
        text(screen, f"LEVEL {level}", f.body_bd, INK, (ix + iw, cy - 2), right=True)
        cy += 20

        xp = u.combat_xp if track == "combat" else u.work_xp
        into, span = progression.to_next(_TRACK_XP[track], xp)
        bar = pygame.Rect(ix, cy, iw, 10)
        panel(screen, bar, fill=SURFACE_0, border=LINE_SOFT, width=1, radius=4)
        if span:
            fillw = int((bar.w - 2) * into / span)
            if fillw:
                pygame.draw.rect(screen, ACCENT, (bar.x + 1, bar.y + 1, fillw, bar.h - 2),
                                 border_radius=3)
            label = f"{into} / {span} XP to level {level + 1}"
        else:
            label = "top of the track"
        cy += 16
        text(screen, label, f.mono_sm, INK_DIM, (ix, cy))
        cy += 18
        if picks:
            text(screen, f"{picks} pick{'s' if picks > 1 else ''} to spend "
                 "— choose below", f.body_sm, ACCENT, (ix, cy))
            cy += 16
        cy += SP2

        for t in talents.TREE[track]:
            cy = self._draw_node(screen, track, t, ix, cy, iw)

    def _draw_node(self, screen, track, t, x, y, w):
        f = self.fonts
        state = self._node_state(track, t)
        # a locked node collapses to its name + "needs X" -- the tree can run deep
        desc_lines = ([] if state == "locked"
                      else wrap_lines([t.effect], f.body_sm, w - 2 * SP3 - 10))
        rect = pygame.Rect(x, y, w, (26 if state == "locked" else 32)
                           + len(desc_lines) * 15)
        hov = state == "open" and rect.collidepoint(self.mouse)

        fill = {"taken": SURFACE_2, "open": SURFACE_3 if hov else SURFACE_2,
                "locked": SURFACE_1}[state]
        border = {"taken": OK, "open": ACCENT, "locked": LINE_SOFT}[state]
        panel(screen, rect, fill=fill, border=border,
              width=2 if state != "locked" else 1, radius=RADIUS)

        namecol = {"taken": OK, "open": ACCENT, "locked": INK_DIM}[state]
        if state == "taken":
            _check(screen, x + SP3 + 3, y + SP3 + 4, OK)
            text(screen, t.name, f.body_bd, namecol, (x + SP3 + 14, y + SP2))
        else:
            text(screen, t.name, f.body_bd, namecol, (x + SP3, y + SP2))

        if state == "taken":
            text(screen, "TAKEN", f.label, OK, (rect.right - SP3, y + SP2 + 2), right=True)
        elif state == "open":
            text(screen, "CLICK TO TAKE", f.label, ACCENT if hov else INK_FAINT,
                 (rect.right - SP3, y + SP2 + 2), right=True)
        elif t.requires:
            req = talents.get(t.requires)
            text(screen, f"needs {req.name}", f.label, INK_FAINT,
                 (rect.right - SP3, y + SP2 + 2), right=True)

        yy = y + 26
        for ln in desc_lines:
            text(screen, ln, f.body_sm, INK_DIM if state != "locked" else INK_FAINT,
                 (x + SP3, yy))
            yy += 15
        if state == "open":
            self.node_hits.append((rect, track, t.id))
            if hov:
                self._hot = True
        return rect.bottom + SP2

    def _draw_footer(self, screen, W, H, pad):
        f = self.fonts
        b = pygame.Rect(pad, H - 52, 150, 36)
        hov = b.collidepoint(self.mouse)
        col = INK if hov else INK_DIM
        panel(screen, b, fill=SURFACE_3 if hov else SURFACE_2, border=LINE_SOFT,
              width=1, radius=RADIUS)
        cx, cy = b.x + SP4, b.centery
        pygame.draw.lines(screen, col, False,
                          [(cx + 3, cy - 4), (cx - 2, cy), (cx + 3, cy + 4)], 2)
        text(screen, "BACK", f.body_bd, col, (cx + 14, cy - 7))
        self.buttons.append(("back", b))
        if hov:
            self._hot = True

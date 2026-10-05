"""Level screen: one XP track per column, its talent tree drawn as a node graph.

Opened from a member's card on the guild screen (`on_level`). Each track shows a
progress bar to the next level and the tree of `talents.TREE[track]` laid out as
a graph -- a root identity up top, the actions it unlocks branching below, joined
by connectors so it reads at a glance what leads to what and how deep a branch
runs. A track with an unspent pick lights its available nodes; click a lit node
to take it (`Unit.choose_talent`). Hovering any node pops a detail card. The
racial track (its level = the other two summed, on a scale) drives hit dice,
handled on XP gain, so nothing to do here but spend picks. `on_back` returns to
the guild.

Renders at the real window resolution (`native = True`), like the guild screen.
Modernized to the `gartok/ui/` design system.
"""

import math

import pygame

from . import artwork, progression, talents
from .combatant import Combatant
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .ui.primitives import (
    caps,
    draw_button,
    draw_tooltip,
    footer_bar,
    hline,
    panel,
    text,
    wrap,
)
from .ui.sheet_card import draw_row, unit_to_ch
from .ui.tokens import T, mix
from .ui.tokens import fonts as ui_fonts

_TRACK_XP = {"combat": progression.COMBAT_XP_THRESHOLDS,
             "work": progression.WORK_XP_THRESHOLDS,
             "racial": progression.RACIAL_XP_THRESHOLDS}
_TRACK_LABEL = {"combat": "COMBAT", "work": "WORK", "racial": "RACIAL"}


def _check(surf, cx, cy, col):
    """A small drawn checkmark (no font glyph -- those go missing in bold)."""
    pygame.draw.lines(surf, col, False,
                      [(cx - 4, cy), (cx - 1, cy + 4), (cx + 5, cy - 5)], 2)



def _tree_layout(track, race=None):
    """Map every node of a track to (column, depth). Column is in leaf units: a
    parent sits at the mean of its children, each leaf takes the next slot.
    Purely `requires`-driven, so a deeper tree lays itself out the same way.
    The racial track is race-gated, so it needs `race`. Returns (pos, span, depths)."""
    nodes = talents.racial_tree(race) if track == "racial" else talents.TREE[track]
    kids = {t.id: [c for c in nodes if c.requires == t.id] for t in nodes}
    roots = [t for t in nodes if not t.requires]
    pos, cursor = {}, [0.0]

    def place(t, depth):
        cs = kids[t.id]
        if cs:
            col = sum(place(c, depth + 1) for c in cs) / len(cs)
        else:
            col, cursor[0] = cursor[0], cursor[0] + 1.2
        pos[t.id] = (col, depth)
        return col

    for i, r in enumerate(roots):
        if i:
            cursor[0] += 0.7                     # a gap between root groups
        place(r, 0)
    depths = 1 + max((d for _, d in pos.values()), default=0)
    return pos, max(cursor[0], 1.0), depths


class LevelScreen(SheetModalMixin, Screen):
    native = True

    def __init__(self, fonts, unit, on_back, on_change=None):
        super().__init__()
        self.fonts = fonts
        self._F = fonts if (isinstance(fonts, dict) and "body" in fonts) else ui_fonts()
        self.unit = unit
        self.on_back = on_back
        self.on_change = on_change            # called after a pick lands (autosave)
        self.node_hits = []                  # [(rect, track, talent_id)]
        self.buttons = []                   # [(key, rect)]
        self._hot = False                   # cursor is over something clickable
        self._hover = None                  # (track, talent) under the cursor
        self.info_hits = []

    # ------------------------------------------------------------------ #
    # tutorial (screen.py)                                               #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "level"

    def tutorial_badge_rect(self, size):
        W, H = size
        pad = T.S * 3 if W < 1500 else T.S * 5
        return pygame.Rect(W - pad - 28, pad + (74 - 28) // 2, 28, 28)

    def handle_escape(self):
        if self.sheet_open:
            self.close_sheet_on_click()
            return True
        return False

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.handle_escape()
            return
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)

    def add_button(self, surf, rect, key, label, enabled=True, primary=False, danger=False):
        self.buttons.append((key, rect))
        if rect.collidepoint(self.mouse):
            self._hot = True
        return draw_button(surf, self._F, rect, label, primary=primary, enabled=enabled,
                           danger=danger, mpos=self.mouse)

    def _click(self, px):
        if self.close_sheet_on_click():
            return
        for rect, unit in getattr(self, "info_hits", []):
            if rect.collidepoint(px):
                self.open_sheet(unit)
                return
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "back":
                    self.on_back()
                elif key == "sheet":
                    self.open_sheet(self.unit)
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
        F = self._F
        u = self.unit
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.node_hits = []
        self.buttons = []
        self.info_hits = []
        self._hover = None
        self._hp_hover = False
        self._hot = False
        pad = T.S * 3 if W < 1500 else T.S * 5

        # title + explainer
        text(screen, F["titleb"], "PROGRESSION", (pad, pad), T.TX)
        text(screen, F["body_sm"],
             "Level up: pick one talent in each track. Locked (grey) nodes need the previous node first.",
             (pad, pad + 38), T.TX_MUTED)

        # Character card row in top right
        has_tut = self.tutorial_key() is not None
        offset = 28 + T.S * 2 if has_tut else 0
        r = pygame.Rect(W - 400 - pad - offset, pad, 400, 74)
        c = Combatant(u)
        draw_row(screen, F, r, unit_to_ch(c))

        if not self.sheet_open:
            self.buttons.append(("sheet", r))
            if r.collidepoint(self.mouse):
                self._hot = True

        div = max(pad + 80, r.bottom + pad)
        hline(screen, pad, W - pad, div)

        top = div + T.S * 4
        gap = T.S * 3
        col_w = min(480, (W - 2 * pad - 2 * gap) // 3)

        for i, track in enumerate(talents.TRACKS):
            x = pad + i * (col_w + gap)
            self._draw_track(screen, track, x, top, col_w, H - top - 68)

        self._draw_tooltip(screen)
        self._draw_footer(screen, F, pad)
        self.draw_sheet_modal(screen, F)

    # ------------------------------------------------------------------ #
    def _draw_track(self, screen, track, x, y, w, h):
        F = self._F
        u = self.unit
        panel(screen, pygame.Rect(x, y, w, h))
        ix = x + T.S * 3
        iw = w - 2 * T.S * 3
        cy = y + T.S * 3

        level = u.track_level[track]
        picks = u.picks_available(track)
        caps(screen, F["microb"], _TRACK_LABEL[track], (ix, cy), T.BRASS)
        caps(screen, F["bodyb"], f"LEVEL {level}", (ix + iw, cy - 2), T.TX, right=True)
        cy += 22

        xp = {"combat": u.combat_xp, "work": u.work_xp, "racial": u.racial_xp}[track]
        into, span = progression.to_next(_TRACK_XP[track], xp)
        bar = pygame.Rect(ix, cy, iw, 10)
        pygame.draw.rect(screen, T.TABLE, bar, border_radius=3)
        pygame.draw.rect(screen, T.STEEL_LINE, bar, 1, border_radius=3)

        if span:
            fillw = int((bar.w - 2) * into / span)
            if fillw:
                pygame.draw.rect(screen, T.BRASS, (bar.x + 1, bar.y + 1, fillw, bar.h - 2),
                                 border_radius=2)
            unit_lbl = "levels" if track == "racial" else "XP"
            label = f"{into} / {span} {unit_lbl} to level {level + 1}"
        else:
            label = "top of the track"
        cy += 16
        text(screen, F["micro"], label, (ix, cy), T.TX_MUTED)
        cy += 18

        if picks:
            text(screen, F["body_sm"], f"{picks} pick{'s' if picks > 1 else ''} to spend "
                 "— choose a lit node", (ix, cy), T.BRASS)
        elif track == "racial" and u.racial_level < 5:
            text(screen, F["micro"], "first racial talent unlocks at racial level 5",
                 (ix, cy), T.TX_FAINT)
        cy += 18

        ty = cy + T.S * 2
        self._draw_tree(screen, track, ix, ty, iw, y + h - T.S * 3 - ty)

    def _draw_tree(self, screen, track, x, y, w, h):
        nodes = (talents.racial_tree(self.unit.race["name"]) if track == "racial"
                 else talents.TREE[track])
        if not nodes:
            text(screen, self._F["body_sm"], "no racial talents for this lineage yet",
                 (x, y + 4), T.TX_FAINT)
            return
        pos, span, depths = _tree_layout(track, self.unit.race["name"])
        unit_w = w / span
        pitch = min(h / depths, 128)
        top = y + max(0.0, (h - pitch * depths) * 0.32)
        node = int(max(34, min(54, unit_w * 0.6, pitch * 0.5)))

        def xy(tid):
            col, depth = pos[tid]
            return (round(x + unit_w * (col + 0.5)),
                    round(top + pitch * (depth + 0.5)))

        # Connectors first
        for t in nodes:
            if not t.requires:
                continue
            px, py = xy(t.requires)
            qx, qy = xy(t.id)
            py += node // 2 + 2
            qy -= node // 2 + 2
            st = self._node_state(track, t)
            col = T.GREEN if st == "taken" else T.BRASS if st == "open" else T.STEEL_LINE
            midy = (py + qy) // 2
            pygame.draw.lines(screen, col, False,
                              [(px, py), (px, midy), (qx, midy), (qx, qy)],
                              3 if st == "taken" else 2)

        for t in nodes:
            self._draw_node(screen, track, t, *xy(t.id), node, is_root=not t.requires)

    def _draw_node(self, screen, track, t, cx, cy, s, *, is_root):
        F = self._F
        state = self._node_state(track, t)
        rs = s + 6 if is_root else s
        rect = pygame.Rect(0, 0, rs, rs)
        rect.center = (cx, cy)
        hov = rect.collidepoint(self.mouse)

        fill = T.STEEL_HI if (state == "open" and hov) else T.STEEL if state in ("taken", "open") else mix(T.TABLE, T.STEEL, 0.4)
        edge = T.GREEN if state == "taken" else T.BRASS if state == "open" else T.STEEL_LINE

        if state == "open":
            k = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 380)
            glow = mix(T.TABLE, T.BRASS, 0.25 + 0.55 * k)
            pygame.draw.rect(screen, glow, rect.inflate(8, 8), 2, border_radius=6)

        pygame.draw.rect(screen, fill, rect, border_radius=4)
        pygame.draw.rect(screen, edge, rect, 2 if state != "locked" else 1, border_radius=4)

        iconcol = T.GREEN if state == "taken" else T.BRASS if state == "open" else T.TX_FAINT
        img = (artwork.icon(*t.icon.split("/"), int(rs * 0.62), color=iconcol)
               if t.icon else None)
        if img is not None:
            screen.blit(img, img.get_rect(center=rect.center))
        else:
            text(screen, F["head"], t.name[:1], rect.center, iconcol, center=True)

        # Tier badge
        badge_bg = T.STEEL_LINE if state == "locked" else T.STEEL_HI
        pygame.draw.circle(screen, badge_bg, rect.topleft, 8)
        text(screen, F["micro"], str(t.tier), rect.topleft,
             T.TX_FAINT if state == "locked" else T.TX_MUTED, center=True)

        if state == "taken":
            pygame.draw.circle(screen, T.GREEN, rect.topright, 8)
            _check(screen, rect.right, rect.top, T.TABLE)

        if state == "open" and not self.sheet_open:
            self.node_hits.append((rect, track, t.id))
        if hov and not self.sheet_open:
            self._hover = (track, t)
            if state == "open":
                self._hot = True

    def _draw_tooltip(self, screen):
        if self.sheet_open or not self._hover:
            return
        F = self._F
        track, t = self._hover
        state = self._node_state(track, t)

        if state == "taken":
            status, scol = "Taken", T.GREEN
        elif state == "open":
            status, scol = "Available — click to take", T.BRASS
        elif t.requires and t.requires not in self.unit.talents[track]:
            req = talents.get(t.requires)
            status, scol = f"Requires {req.name if req else t.requires}", T.TX_FAINT
        else:
            status, scol = "Needs a level-up pick in this track", T.TX_FAINT

        lines = [(t.name, F["bodyb"], T.TX)]
        for ln in t.effect.split("\n"):
            for sub in wrap(F["body_sm"], ln, 260):
                lines.append((sub, F["body_sm"], T.TX_MUTED))
        lines.append((status, F["microb"], scol))

        draw_tooltip(screen, F, lines, self.mouse)

    def _draw_footer(self, screen, F, pad):
        footer_bar(self, screen, F, back=("back", "BACK"), margin=pad)

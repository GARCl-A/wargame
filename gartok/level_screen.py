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
"""

import math

import pygame

from . import artwork, progression, talents
from .screen import Screen
from .theme import (ACCENT, INFO, INK, INK_DIM, INK_FAINT, LINE, LINE_SOFT,
                    MARGIN, OK, RADIUS, SP2, SP3, SP4, SP5, SURFACE_0,
                    SURFACE_1, SURFACE_2, SURFACE_3, SURFACE_4, panel,
                    set_pointer, text, token_badge, tracked, wrap_lines)

_TRACK_XP = {"combat": progression.COMBAT_XP_THRESHOLDS,
             "work": progression.WORK_XP_THRESHOLDS,
             "racial": progression.RACIAL_XP_THRESHOLDS}
_TRACK_LABEL = {"combat": "COMBAT", "work": "WORK", "racial": "RACIAL"}


def _check(surf, cx, cy, col):
    """A small drawn checkmark (no font glyph -- those go missing in bold)."""
    pygame.draw.lines(surf, col, False,
                      [(cx - 4, cy), (cx - 1, cy + 4), (cx + 5, cy - 5)], 2)


def _lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


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
        self._hover = None                  # (track, talent) under the cursor

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "level"

    def tutorial_anchor(self, size):
        w, _h = size
        pad = MARGIN if w < 1500 else SP5
        return self.footer_anchor(size, margin=pad)

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
        self._hover = None
        pad = MARGIN if W < 1500 else SP5

        text(screen, "PROGRESSION", f.title, INK, (pad, pad))

        iy = pad + 46
        tok = (pad + 17, iy + 15)
        token_badge(screen, tok, u, f, r=17)
        text(screen, u.name, f.card_name, INK, (tok[0] + 30, iy))
        dice = len(u._level_hp_rolls)
        sub = (f"{u.race['name']}  ·  {u.occupation['name']}  ·  "
               f"racial level {u.racial_level}  ·  {1 + dice} hit "
               f"{'die' if dice == 0 else 'dice'}")
        text(screen, sub, f.body_sm, INK_DIM, (tok[0] + 30, iy + 22))

        div = iy + 48
        pygame.draw.line(screen, LINE_SOFT, (pad, div), (W - pad, div))

        top = div + SP4
        gap = SP4
        col_w = min(480, (W - 2 * pad - 2 * gap) // 3)
        self._hot = False
        for i, track in enumerate(talents.TRACKS):
            x = pad + i * (col_w + gap)
            self._draw_track(screen, track, x, top, col_w, H - top - 68)

        self._draw_tooltip(screen)
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

        xp = {"combat": u.combat_xp, "work": u.work_xp, "racial": u.racial_xp}[track]
        into, span = progression.to_next(_TRACK_XP[track], xp)
        bar = pygame.Rect(ix, cy, iw, 10)
        panel(screen, bar, fill=SURFACE_0, border=LINE_SOFT, width=1, radius=4)
        if span:
            fillw = int((bar.w - 2) * into / span)
            if fillw:
                pygame.draw.rect(screen, ACCENT, (bar.x + 1, bar.y + 1, fillw, bar.h - 2),
                                 border_radius=3)
            unit = "levels" if track == "racial" else "XP"
            label = f"{into} / {span} {unit} to level {level + 1}"
        else:
            label = "top of the track"
        cy += 16
        text(screen, label, f.mono_sm, INK_DIM, (ix, cy))
        cy += 18
        if picks:
            text(screen, f"{picks} pick{'s' if picks > 1 else ''} to spend "
                 "— choose a lit node", f.body_sm, ACCENT, (ix, cy))
        cy += 18

        ty = cy + SP2
        self._draw_tree(screen, track, ix, ty, iw, y + h - SP4 - ty)

    def _draw_tree(self, screen, track, x, y, w, h):
        nodes = (talents.racial_tree(self.unit.race["name"]) if track == "racial"
                 else talents.TREE[track])
        if not nodes:
            text(screen, "no racial talents for this lineage yet",
                 self.fonts.body_sm, INK_FAINT, (x, y + 4))
            return
        pos, span, depths = _tree_layout(track, self.unit.race["name"])
        unit_w = w / span
        pitch = min(h / depths, 128)
        # sit the tree high in the panel -- the empty room below reads as
        # "the branch keeps going", which is the point
        top = y + max(0.0, (h - pitch * depths) * 0.32)
        node = int(max(34, min(54, unit_w * 0.6, pitch * 0.5)))

        def xy(tid):
            col, depth = pos[tid]
            return (round(x + unit_w * (col + 0.5)),
                    round(top + pitch * (depth + 0.5)))

        # connectors first, so the nodes sit on top of them
        for t in nodes:
            if not t.requires:
                continue
            px, py = xy(t.requires)
            qx, qy = xy(t.id)
            py += node // 2 + 2
            qy -= node // 2 + 2
            st = self._node_state(track, t)
            col = OK if st == "taken" else ACCENT if st == "open" else LINE
            midy = (py + qy) // 2
            pygame.draw.lines(screen, col, False,
                              [(px, py), (px, midy), (qx, midy), (qx, qy)],
                              3 if st == "taken" else 2)

        for t in nodes:
            self._draw_node(screen, track, t, *xy(t.id), node, is_root=not t.requires)

    def _draw_node(self, screen, track, t, cx, cy, s, *, is_root):
        f = self.fonts
        state = self._node_state(track, t)
        rs = s + 6 if is_root else s
        rect = pygame.Rect(0, 0, rs, rs)
        rect.center = (cx, cy)
        hov = rect.collidepoint(self.mouse)

        fill = {"taken": SURFACE_2, "open": SURFACE_3 if hov else SURFACE_2,
                "locked": SURFACE_1}[state]
        edge = {"taken": OK, "open": ACCENT, "locked": LINE_SOFT}[state]
        if state == "open":
            k = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 380)
            pygame.draw.rect(screen, _lerp(SURFACE_1, ACCENT, 0.25 + 0.55 * k),
                             rect.inflate(10, 10), 2, border_radius=RADIUS + 3)
        panel(screen, rect, fill=fill, border=edge,
              width=2 if state != "locked" else 1, radius=RADIUS)

        iconcol = {"taken": OK, "open": ACCENT, "locked": INK_FAINT}[state]
        img = (artwork.icon(*t.icon.split("/"), int(rs * 0.62), color=iconcol)
               if t.icon else None)
        if img is not None:
            screen.blit(img, img.get_rect(center=rect.center))
        else:
            text(screen, t.name[:1], f.card_name, iconcol, rect.center, center=True)

        # tier badge -- how deep the branch runs, dimmed with the tile
        pygame.draw.circle(screen, SURFACE_3 if state == "locked" else SURFACE_4,
                           rect.topleft, 8)
        text(screen, str(t.tier), f.label,
             INK_FAINT if state == "locked" else INK_DIM, rect.topleft, center=True)
        if state == "taken":
            pygame.draw.circle(screen, OK, rect.topright, 8)
            _check(screen, rect.right, rect.top, SURFACE_0)

        if state == "open":
            self.node_hits.append((rect, track, t.id))
        if hov:
            self._hover = (track, t)
            if state == "open":
                self._hot = True

    def _draw_tooltip(self, screen):
        if not self._hover:
            return
        f = self.fonts
        track, t = self._hover
        state = self._node_state(track, t)
        if state == "taken":
            status, scol = "Taken", OK
        elif state == "open":
            status, scol = "Available — click to take", ACCENT
        elif t.requires and t.requires not in self.unit.talents[track]:
            status, scol = f"Requires {talents.get(t.requires).name}", INK_FAINT
        else:
            status, scol = "Needs a level-up pick in this track", INK_FAINT

        lines = ([(t.name, f.body_bd, INK)]
                 + [(ln, f.body_sm, INK_DIM)
                    for ln in wrap_lines([t.effect], f.body_sm, 240)]
                 + [(status, f.label, scol)])
        tw = max(fo.size(s)[0] for s, fo, _ in lines) + 2 * SP3
        th = 2 * SP3 + len(lines) * 16
        W, H = screen.get_size()
        bx = min(self.mouse[0] + 16, W - tw - SP2)
        by = min(self.mouse[1] + 16, H - th - SP2)
        panel(screen, pygame.Rect(bx, by, tw, th), fill=SURFACE_2, border=LINE,
              width=1, radius=RADIUS)
        yy = by + SP3
        for s, fo, c in lines:
            text(screen, s, fo, c, (bx + SP3, yy))
            yy += 16

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

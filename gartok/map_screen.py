"""World map: give orders to groups, then advance the world.

Draws `world.NODES` as a graph -- points joined by edges labelled with their
travel cost in hours. The guild is one or more **groups** (`gartok/group.py`):
each stands on its own node and carries its own squad. `self.selected` is the
group every click in this screen acts on -- pick a different row in the GROUPS
list to switch. Clicking a node issues that group a **travel order**
(`orders.travel`) instead of moving it there on the spot; the side panel's
per-node actions (fight, shop, work, ...) issue the matching order too. Nothing
actually *happens* until **ADVANCE**, which calls `campaign.advance` -- the tick
jumps the world to the soonest order completion, resolves travel/work silently,
and hands any other kind back to `app` to play its screen. **MAINTENANCE**
forces a short 1 h stop instead (still through the same tick, so an order in
flight stays in sync with the clock).

A group with no order sitting on the same node as another idle group may
**SPLIT** (peel some of its members into a new group) or **MERGE** (fold a
co-located group into it) -- both physical, both instant, neither costs time.

`on_guild` opens the roster/gear screen; `on_wipe` fires if a tick starves the
guild out entirely. Leaving to the main menu is Esc -> the pause menu (`app`),
not a button here.
"""

import pygame

from . import arena, orders, world
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, ENEMY_C, INFO, INK, INK_DIM,
                    INK_FAINT, LINE, LINE_SOFT, MARGIN, NEUTRAL_C, OK, RADIUS, SP2, SP3, SP4,
                    SURFACE_0, SURFACE_1, SURFACE_2, SURFACE_3, WARN,
                    panel, section, text, tracked, wrap_lines)

SIDE_W = 372
GROUND_DAY = (34, 37, 44)
GROUND_NIGHT = (21, 23, 32)
KIND_COLOR = {"battle": ENEMY_C, "market": INFO, "tavern": WARN, "town": NEUTRAL_C,
              "wilds": OK}
KIND_BADGE = {"battle": "COMBAT", "market": "MARKET", "tavern": "TAVERN", "town": "STOP",
              "wilds": "WILDS"}
WORK_HOURS = (4, 8, 12, 16)


class MapScreen(Screen):
    native = True

    def __init__(self, fonts, guild, on_guild, on_wipe, on_advance):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.on_guild = on_guild
        self.on_wipe = on_wipe
        self.on_advance = on_advance
        self.selected = guild.groups[0]
        self.mode = "map"                     # "map" | "split"
        self.split_picks = set()              # unit uids toggled to leave, while splitting
        self.notices = []                     # lines shown after a tick (route, meals, deaths)
        self.hits = []                        # [(rect, node)]
        self.buttons = []                     # [(key, rect)]
        self.group_rows = []                 # [(rect, group)]
        self.split_rows = []                 # [(rect, unit)]
        self._terr = None                    # cached terrain fill (key, surface)

    # ------------------------------------------------------------------ #
    def _here(self):
        return world.node(self.selected.node)

    def _hovered_node(self):
        for rect, n in self.hits:
            if rect.collidepoint(self.mouse):
                return n
        return None

    def _select(self, group):
        self.selected = group
        self.mode = "map"

    def _issue(self, order):
        if not self.selected.busy:
            self.selected.order = order

    def _go(self, target):
        if self.selected.busy or target.id == self.selected.node:
            return
        try:
            self.selected.order = orders.travel(self.selected, target.id)
        except ValueError:
            pass

    def _click(self, px):
        if self.mode == "split":
            self._click_split(px)
            return
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                self._handle_button(key)
                return
        for rect, g in self.group_rows:
            if rect.collidepoint(px):
                self._select(g)
                return
        for rect, n in self.hits:
            if rect.collidepoint(px):
                self._go(n)
                return

    def _handle_button(self, key):
        if key == "guild":
            self.on_guild()
        elif key == "advance":
            self.on_advance()
        elif key == "maintain":
            self.on_advance(dt=1)
        elif key == "split":
            self.mode, self.split_picks = "split", set()
        elif key.startswith("merge:"):
            other = self._group_by_gid(key[len("merge:"):])
            if other is not None:
                self.guild.merge_groups(self.selected, other)
        elif key.startswith("work:"):
            self._issue(orders.work(self.guild, self.selected, int(key.split(":")[1])))
        elif key in orders.INTERACTIVE_KINDS:
            self._issue(orders.interactive(key))

    def _group_by_gid(self, gid):
        return next((g for g in self.guild.groups if g.gid == gid), None)

    def _click_split(self, px):
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "split_confirm" and self.split_picks:
                    chosen = [u for u in self.selected.members if u.uid in self.split_picks]
                    try:
                        self._select(self.guild.split_group(self.selected, chosen))
                    except ValueError:
                        self.mode = "map"
                else:
                    self.mode = "map"
                return
        for rect, u in self.split_rows:
            if rect.collidepoint(px):
                self.split_picks.symmetric_difference_update({u.uid})
                return

    # ------------------------------------------------------------------ #
    def _area(self, screen):
        top = MARGIN + 64
        W, H = screen.get_size()
        w = W - 3 * MARGIN - SIDE_W
        return pygame.Rect(MARGIN, top, w, H - top - 64)

    def _node_xy(self, area, n):
        pad = 48                              # keep markers + labels off the frame
        return (int(area.x + pad + n.pos[0] * (area.w - 2 * pad)),
                int(area.y + pad + n.pos[1] * (area.h - 2 * pad)))

    def _terrain(self, size, daylight):
        """Cached fill for the map area: a top-down vertical gradient, a sparse
        contour speckle and a soft vignette. Rebuilt only on size/phase change."""
        key = (size, daylight)
        if self._terr and self._terr[0] == key:
            return self._terr[1]
        w, h = size
        surf = pygame.Surface(size).convert()
        base = GROUND_DAY if daylight else GROUND_NIGHT
        lift = 12 if daylight else 7
        for y in range(h):
            t = y / max(1, h - 1)
            surf.fill(tuple(int(base[i] + lift - 2 * lift * t) for i in range(3)),
                      (0, y, w, 1))

        overlay = pygame.Surface(size, pygame.SRCALPHA)
        speck = (235, 240, 255) if not daylight else (0, 0, 0)
        for gy in range(14, h, 26):
            for gx in range(14, w, 26):
                hsh = (gx * 73856093) ^ (gy * 19349663)
                if hsh % 4 == 0:
                    p = (gx + (hsh >> 3) % 7 - 3, gy + (hsh >> 6) % 7 - 3)
                    pygame.draw.circle(overlay, (*speck, 9 if daylight else 12), p, 1)
        depth, peak = 74, (85 if daylight else 150)
        for i in range(depth):
            a = int(peak * (1 - i / depth) ** 2)
            pygame.draw.rect(overlay, (*SURFACE_0, a), (i, i, w - 2 * i, h - 2 * i), 1)
        surf.blit(overlay, (0, 0))
        self._terr = (key, surf)
        return surf

    def draw(self, screen):
        f = self.fonts
        screen.fill(SURFACE_0)
        self.hits = []
        self.buttons = []
        self.group_rows = []
        self.split_rows = []
        clock = self.guild.clock

        hungry = self.guild.hungry
        rations = self.guild.rations
        text(screen, "MAP", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, f"{clock.label}   ·   {len(self.guild)} members"
             + (f" ({len(hungry)} hungry)" if hungry else "")
             + f"   ·   {rations} rations"
             + f"   ·   {self.guild.gold} copper   ·   {self.guild.battles_won} wins"
             f"   ·   arena reputation {self.guild.arena_reputation}",
             f.body, INK_DIM, (MARGIN, MARGIN + 30))
        if arena.defense_due(self.guild):
            champ = arena.champion_of(self.guild)
            text(screen, f"TITLE DEFENSE: {champ.name} must defend the Champion of the "
                 f"Pit at the Arena by day {arena.defense_deadline(self.guild)}",
                 f.body_sm, WARN, (MARGIN, MARGIN + 48))

        area = self._area(screen)
        panel(screen, area, fill=GROUND_DAY if clock.is_daylight else GROUND_NIGHT,
              border=LINE_SOFT, radius=RADIUS)
        clip = screen.get_clip()
        screen.set_clip(area)
        screen.blit(self._terrain(area.size, clock.is_daylight), area.topleft)
        self._draw_edges(screen, area)
        self._draw_nodes(screen, area)
        self._draw_legend(screen, area)
        screen.set_clip(clip)
        pygame.draw.rect(screen, LINE_SOFT, area, 1, border_radius=RADIUS)

        self._draw_tooltip(screen, area)
        if self.mode == "split":
            self._draw_split_panel(screen, area)
        else:
            self._draw_side(screen, area)
        self._draw_footer(screen)

    # ------------------------------------------------------------------ #
    def _route_pairs(self):
        hov = self._hovered_node()
        if hov is None or hov.id == self.selected.node:
            return set()
        path, _ = world.route(self.selected.node, hov.id)
        path = path or []
        return {frozenset(p) for p in zip(path, path[1:])}

    def _draw_edges(self, screen, area):
        f = self.fonts
        route_pairs = self._route_pairs()
        segs = []
        for a, b, w in world.EDGES:
            pa = self._node_xy(area, world.node(a))
            pb = self._node_xy(area, world.node(b))
            on_route = frozenset((a, b)) in route_pairs
            pygame.draw.line(screen, SURFACE_0, pa, pb, 7)          # carved bed
            pygame.draw.line(screen, ACCENT if on_route else LINE, pa, pb,
                             4 if on_route else 2)
            segs.append((pa, pb, w, on_route))

        for pa, pb, w, on_route in segs:                            # cost pills on top
            mid = ((pa[0] + pb[0]) // 2, (pa[1] + pb[1]) // 2)
            s = f"{w} h"
            r = pygame.Rect(0, 0, f.mono_sm.size(s)[0] + 12, 16)
            r.center = mid
            panel(screen, r, fill=SURFACE_2,
                  border=ACCENT if on_route else LINE_SOFT, radius=8)
            text(screen, s, f.mono_sm, ACCENT if on_route else INK_FAINT,
                 r.center, center=True)

    def _glyph(self, screen, kind, x, y):
        c = (14, 15, 20)
        if kind == "battle":                                       # crossed blades
            pygame.draw.line(screen, c, (x - 5, y - 5), (x + 5, y + 5), 2)
            pygame.draw.line(screen, c, (x - 5, y + 5), (x + 5, y - 5), 2)
        elif kind == "market":                                     # coin
            pygame.draw.circle(screen, c, (x, y), 5, 2)
            pygame.draw.line(screen, c, (x, y - 2), (x, y + 2), 2)
        elif kind == "tavern":                                    # tankard
            pygame.draw.rect(screen, c, (x - 4, y - 4, 7, 9), 2)
            pygame.draw.arc(screen, c, (x + 2, y - 4, 6, 8), -1.4, 1.4, 2)
        elif kind == "work":                                        # axe
            pygame.draw.line(screen, c, (x - 4, y + 6), (x + 3, y - 6), 2)
            pygame.draw.arc(screen, c, (x + 1, y - 8, 7, 8), 1.2, 4.2, 2)
        elif kind == "wilds":                                       # bow
            pygame.draw.arc(screen, c, (x - 6, y - 6, 10, 12), -1.3, 1.3, 2)
            pygame.draw.line(screen, c, (x - 4, y - 5), (x - 4, y + 5), 2)
            pygame.draw.line(screen, c, (x - 4, y), (x + 6, y), 2)
        else:                                                      # town roofline
            pygame.draw.lines(screen, c, False,
                              [(x - 5, y + 4), (x - 5, y - 1), (x, y - 5),
                               (x + 5, y - 1), (x + 5, y + 4)], 2)

    def _draw_marker(self, screen, x, y, n, here, hovered, others=0):
        col = KIND_COLOR[n.kind]
        sh = pygame.Surface((36, 16), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 95), sh.get_rect())
        screen.blit(sh, (x - 18, y + 5))

        if here:
            pygame.draw.circle(screen, ACCENT, (x, y), 13)
            pygame.draw.circle(screen, ACCENT_INK, (x, y), 13, 2)
            text(screen, "G", self.fonts.body_bd, ACCENT_INK, (x, y), center=True)
            pygame.draw.line(screen, ACCENT_INK, (x, y - 13), (x, y - 30), 2)
            pygame.draw.polygon(screen, ACCENT,
                                [(x + 1, y - 30), (x + 15, y - 26), (x + 1, y - 20)])
        else:
            if n.kind in ("battle", "wilds"):                       # danger aura
                aura = pygame.Surface((54, 54), pygame.SRCALPHA)
                pygame.draw.circle(aura, (*col, 24), (27, 27), 27)
                pygame.draw.circle(aura, (*col, 30), (27, 27), 18)
                screen.blit(aura, (x - 27, y - 27))
            pygame.draw.circle(screen, col, (x, y), 12)
            pygame.draw.circle(screen, tuple(c // 2 for c in col), (x, y), 12, 2)
            if n.work:
                self._glyph(screen, "work", x, y)
            else:
                self._glyph(screen, n.kind, x, y)
            if hovered:
                pygame.draw.circle(screen, INK, (x, y), 16, 2)

        if others:                                                 # other groups standing here
            badge = pygame.Rect(0, 0, 22, 16)
            badge.center = (x + 15, y - 15)
            panel(screen, badge, fill=SURFACE_3, border=ACCENT, radius=8)
            text(screen, f"+{others}", self.fonts.label, ACCENT, badge.center, center=True)

    def _draw_nodes(self, screen, area):
        f = self.fonts
        hov = self._hovered_node()
        for n in world.NODES:
            x, y = self._node_xy(area, n)
            self.hits.append((pygame.Rect(x - 46, y - 34, 92, 66), n))
            here = n.id == self.selected.node
            occupants = sum(1 for g in self.guild.groups if g.node == n.id)
            others = occupants - (1 if here else 0)
            self._draw_marker(screen, x, y, n, here, n is hov, others)

            active = here or n is hov
            r = pygame.Rect(0, 0, f.body_sm.size(n.name)[0] + 14, 18)
            r.center = (x, y + 27)
            panel(screen, r, fill=ACCENT if here else SURFACE_2,
                  border=ACCENT if active else LINE_SOFT, radius=9)
            text(screen, n.name, f.body_sm,
                 ACCENT_INK if here else INK if active else INK_DIM,
                 r.center, center=True)

    @staticmethod
    def _wilds_actions():
        """The activities on offer in the wilds -- (button key, label, one-liner).
        Just Hunt for now; foraging and the like slot in here later."""
        return [("hunt", "GO HUNTING",
                 "spend the day for meat  ·  a pack may find you first")]

    def _draw_legend(self, screen, area):
        f = self.fonts
        rows = [("battle", "combat"), ("market", "market"),
                ("tavern", "tavern"), ("wilds", "wilds"), ("town", "stop")]
        box = pygame.Rect(0, 0, 116, 15 * len(rows) + 12)
        box.topright = (area.right - SP3, area.y + SP3)
        panel(screen, box, fill=SURFACE_1, border=LINE_SOFT, radius=6)
        y = box.y + 9
        for kind, name in rows:
            pygame.draw.circle(screen, KIND_COLOR[kind], (box.x + 13, y + 3), 5)
            text(screen, name, f.body_sm, INK_DIM, (box.x + 26, y - 3))
            y += 15

    def _draw_tooltip(self, screen, area):
        hov = self._hovered_node()
        if hov is None or hov.id == self.selected.node:
            return
        f = self.fonts
        _, hours = world.route(self.selected.node, hov.id)
        busy = "  (group is busy)" if self.selected.busy else ""
        s = f"{hov.name}   ·   {hours} h   ·   click to send{busy}"
        r = pygame.Rect(0, 0, f.body_sm.size(s)[0] + 18, 22)
        r.topleft = (self.mouse[0] + 14, self.mouse[1] - 6)
        r.clamp_ip(area.inflate(-SP2, -SP2))
        panel(screen, r.move(0, 2), fill=SURFACE_0, border=None, radius=6)
        panel(screen, r, fill=SURFACE_3, border=ACCENT, radius=6)
        text(screen, s, f.body_sm, INK, r.center, center=True)

    # ------------------------------------------------------------------ #
    def _order_status(self, group):
        """One-line status for a group's GROUPS-list row."""
        o = group.order
        if o is None or o.kind == "idle":
            return "idle"
        if o.kind == "travel":
            return f"→ {world.node(o.dest).name} ({o.remaining:g} h)"
        if o.kind == "work":
            return f"working ({o.remaining:g} h left)"
        return f"heading to {o.kind} ({o.remaining:g} h)"

    def _draw_groups(self, screen, cx, y, cw, f):
        y = section(screen, "GROUPS", cx, y, cw, f)
        for g in self.guild.groups:
            sel = g is self.selected
            r = pygame.Rect(cx, y, cw, 30)
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if (sel or hov) else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=2 if sel else 1, radius=8)
            name = g.name or f"Group ({len(g.members)})"
            text(screen, name, f.body_sm, ACCENT if sel else INK, (r.x + SP2, r.y + 3))
            text(screen, f"{world.node(g.node).name}  ·  {self._order_status(g)}",
                 f.label, INK_DIM, (r.x + SP2, r.y + 16))
            self.group_rows.append((r, g))
            y += 34
        return y + SP2

    def _draw_group_actions(self, screen, cx, y, cw, f):
        """SPLIT (peel members off) / MERGE (fold in a co-located idle group,
        one row per such group -- there can be more than one)."""
        g = self.selected
        if g.busy:
            return y
        if len(g.members) > 1:
            r = pygame.Rect(cx, y, cw, 30)
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if hov else SURFACE_1, border=LINE_SOFT, radius=8)
            text(screen, "SPLIT", f.body_sm, INK, r.center, center=True)
            self.buttons.append(("split", r))
            y += 34
        mates = [o for o in self.guild.groups if o is not g and o.node == g.node and not o.busy]
        for o in mates:
            mr = pygame.Rect(cx, y, cw, 30)
            hov = mr.collidepoint(self.mouse)
            panel(screen, mr, fill=SURFACE_3 if hov else SURFACE_1, border=LINE_SOFT, radius=8)
            name = o.name or f"Group ({len(o.members)})"
            text(screen, f"MERGE WITH {name}", f.body_sm, INK, mr.center, center=True)
            self.buttons.append((f"merge:{o.gid}", mr))
            y += 34
        return y

    def _draw_side(self, screen, area):
        f = self.fonts
        here = self._here()
        x = area.right + MARGIN
        rect = pygame.Rect(x, area.y, SIDE_W, area.h)
        panel(screen, rect, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)

        pad = SP4
        cx = x + pad
        cw = SIDE_W - 2 * pad
        y = area.y + pad

        y = self._draw_groups(screen, cx, y, cw, f)
        y = self._draw_group_actions(screen, cx, y, cw, f)
        y += SP2

        tracked(screen, "SELECTED GROUP IS AT", f.label, INFO, (cx, y))
        y += 18
        text(screen, here.name, f.heading, INK, (cx, y))
        y += 24
        tracked(screen, KIND_BADGE[here.kind], f.label, KIND_COLOR[here.kind], (cx, y))
        y += 22
        for ln in wrap_lines([here.blurb], f.body_sm, cw):
            text(screen, ln, f.body_sm, INK_DIM, (cx, y))
            y += 16

        y += SP3
        y = section(screen, "HERE", cx, y, cw, f)
        if self.selected.busy:
            text(screen, f"Busy: {self._order_status(self.selected)}", f.body_sm,
                 WARN, (cx, y))
        elif here.is_battle:
            br = pygame.Rect(cx, y, cw, 38)
            hovb = br.collidepoint(self.mouse)
            panel(screen, br, fill=ACCENT if hovb else SURFACE_3,
                  border=ACCENT, width=1, radius=RADIUS)
            defense = here.arena and arena.defense_due(self.guild)
            label = ("DEFEND YOUR TITLE" if defense
                     else "BET AT THE ARENA" if here.arena else "ATTACK")
            text(screen, label, f.body_bd, ACCENT_INK if hovb else ACCENT,
                 br.center, center=True)
            self.buttons.append(("arena", br))
            y += 44
            note = ("1v1 for the Champion of the Pit -- no stake, no backup" if defense
                    else "non-lethal · stake copper, win the purse" if here.arena
                    else "lethal combat · loot the bodies")
            text(screen, note, f.body_sm,
                 WARN if defense else INK_FAINT, (cx, y))
        elif here.is_market:
            mr = pygame.Rect(cx, y, cw, 38)
            hovm = mr.collidepoint(self.mouse)
            panel(screen, mr, fill=SURFACE_3 if hovm else SURFACE_1,
                  border=LINE_SOFT, width=1, radius=RADIUS)
            text(screen, "ENTER THE MARKET", f.body_bd, INK_DIM, mr.center, center=True)
            self.buttons.append(("market", mr))
        elif here.is_tavern:
            tr = pygame.Rect(cx, y, cw, 38)
            hovt = tr.collidepoint(self.mouse)
            panel(screen, tr, fill=SURFACE_3 if hovt else SURFACE_1,
                  border=LINE_SOFT, width=1, radius=RADIUS)
            text(screen, "ENTER THE TAVERN", f.body_bd, INK_DIM, tr.center, center=True)
            self.buttons.append(("recruit", tr))
            y += 44
            text(screen, "talk a stranger into signing with the guild", f.body_sm,
                 INK_FAINT, (cx, y))
        elif here.work:
            tracked(screen, "WORK A SHIFT", f.label, INK_DIM, (cx, y))
            y += 18
            gap = SP2
            cw4 = (cw - 3 * gap) // 4
            for i, h in enumerate(WORK_HOURS):
                r = pygame.Rect(cx + i * (cw4 + gap), y, cw4, 34)
                hov = r.collidepoint(self.mouse)
                panel(screen, r, fill=SURFACE_3 if hov else SURFACE_1,
                      border=LINE_SOFT, width=1, radius=RADIUS)
                text(screen, f"{h} h", f.body_sm, INK, r.center, center=True)
                self.buttons.append((f"work:{h}", r))
            y += 42
            text(screen, "trade hours of the day for copper  ·  pays little, but it's sure",
                 f.body_sm, INK_FAINT, (cx, y))
        elif here.is_wilds:
            for key, label, note in self._wilds_actions():
                r = pygame.Rect(cx, y, cw, 38)
                hov = r.collidepoint(self.mouse)
                panel(screen, r, fill=SURFACE_3 if hov else SURFACE_1,
                      border=LINE_SOFT, width=1, radius=RADIUS)
                text(screen, label, f.body_bd, INK_DIM, r.center, center=True)
                self.buttons.append((key, r))
                y += 42
                text(screen, note, f.body_sm, INK_FAINT, (cx, y))
                y += 20
        elif here.bank:
            br = pygame.Rect(cx, y, cw, 38)
            hovb = br.collidepoint(self.mouse)
            panel(screen, br, fill=SURFACE_3 if hovb else SURFACE_1,
                  border=LINE_SOFT, width=1, radius=RADIUS)
            text(screen, "VISIT THE BANK", f.body_bd, INK_DIM, br.center, center=True)
            self.buttons.append(("bank", br))
            y += 44
            chest = (f"strongbox: {self.guild.bank_load:g} / {self.guild.bank_capacity} kg"
                     if self.guild.bank_unlocked
                     else "rent a strongbox  ·  stash gear the guild isn't carrying")
            text(screen, chest, f.body_sm, INK_FAINT, (cx, y))
        else:
            text(screen, "Nothing happens here. A safe stop.", f.body_sm,
                 INK_FAINT, (cx, y))

        y += 60
        y = section(screen, "FROM HERE YOU CAN REACH", cx, y, cw, f)
        for nid, hours in sorted(world.neighbors(here.id), key=lambda t: t[1]):
            n = world.node(nid)
            text(screen, n.name, f.body_sm, INK_DIM, (cx, y))
            text(screen, f"{hours} h", f.mono_sm, INK_FAINT, (cx + cw, y), right=True)
            y += 17

        if self.notices:
            lines = [w for ln in self.notices for w in wrap_lines([ln], f.body_sm, cw)]
            yy = rect.bottom - pad - 13 * len(lines)
            for ln in lines:
                col = DANGER if "starved" in ln else INFO
                text(screen, ln, f.body_sm, col, (cx, yy))
                yy += 13

    def _draw_split_panel(self, screen, area):
        f = self.fonts
        x = area.right + MARGIN
        rect = pygame.Rect(x, area.y, SIDE_W, area.h)
        panel(screen, rect, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)

        pad = SP4
        cx = x + pad
        cw = SIDE_W - 2 * pad
        y = area.y + pad
        text(screen, "SPLIT GROUP", f.heading, INK, (cx, y))
        y += 26
        text(screen, "pick who LEAVES to form a new group", f.body_sm, INK_DIM, (cx, y))
        y += 26

        for u in self.selected.members:
            picked = u.uid in self.split_picks
            r = pygame.Rect(cx, y, cw, 30)
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if (picked or hov) else SURFACE_1,
                  border=ACCENT if picked else LINE_SOFT, width=2 if picked else 1, radius=8)
            text(screen, u.name, f.body_sm, ACCENT if picked else INK, (r.x + SP2, r.y + 3))
            text(screen, "leaving" if picked else "stays", f.label,
                 ACCENT if picked else INK_FAINT, (r.right - SP2, r.y + 3), right=True)
            self.split_rows.append((r, u))
            y += 34

        y = rect.bottom - pad - 76
        ok = bool(self.split_picks)
        cr = pygame.Rect(cx, y, cw, 36)
        panel(screen, cr, fill=ACCENT if ok else SURFACE_1, border=ACCENT if ok else LINE_SOFT,
              width=1, radius=RADIUS)
        text(screen, "CONFIRM SPLIT", f.body_bd, ACCENT_INK if ok else INK_FAINT,
             cr.center, center=True)
        self.buttons.append(("split_confirm", cr))
        y += 44
        xr = pygame.Rect(cx, y, cw, 32)
        hovx = xr.collidepoint(self.mouse)
        panel(screen, xr, fill=SURFACE_3 if hovx else SURFACE_1, border=LINE_SOFT, radius=RADIUS)
        text(screen, "cancel", f.body, INK if hovx else INK_DIM, xr.center, center=True)
        self.buttons.append(("split_cancel", xr))

    def _draw_footer(self, screen):
        f = self.fonts
        y = screen.get_height() - 52

        g = pygame.Rect(MARGIN, y, 170, 36)
        hovg = g.collidepoint(self.mouse)
        panel(screen, g, fill=ACCENT if hovg else SURFACE_3, border=ACCENT,
              width=1, radius=RADIUS)
        text(screen, "GUILD / GEAR", f.body_bd, ACCENT_INK if hovg else ACCENT,
             g.center, center=True)
        self.buttons.append(("guild", g))

        hungry = self.guild.hungry
        mt = pygame.Rect(MARGIN + 182, y, 160, 36)
        hovt = mt.collidepoint(self.mouse)
        # a stop helps only if a hungry member can reach a ration: their own pack,
        # or the shared larder of a group-mate who pools food
        reachable = any(u.rations for u in hungry) or any(
            u.share_food and u.rations for u in self.guild.roster)
        urgent = bool(hungry) and reachable
        panel(screen, mt, fill=ACCENT if hovt else SURFACE_3 if urgent else SURFACE_2,
              border=ACCENT if urgent else LINE_SOFT, width=1, radius=RADIUS)
        text(screen, "MAINTENANCE (1 h)", f.body_bd,
             ACCENT_INK if hovt else ACCENT if urgent else INK_DIM,
             mt.center, center=True)
        self.buttons.append(("maintain", mt))

        any_orders = any(g.busy for g in self.guild.groups)
        av = pygame.Rect(MARGIN + 354, y, 150, 36)
        hova = av.collidepoint(self.mouse)
        panel(screen, av, fill=ACCENT if (hova and any_orders) else SURFACE_3 if any_orders
              else SURFACE_1, border=ACCENT if any_orders else LINE_SOFT, width=1, radius=RADIUS)
        text(screen, "ADVANCE", f.body_bd,
             ACCENT_INK if (hova and any_orders) else ACCENT if any_orders else INK_FAINT,
             av.center, center=True)
        self.buttons.append(("advance", av))

        text(screen, "click a group, then a place to send it  ·  ADVANCE plays out "
             "the orders  ·  Esc for the pause menu",
             f.body_sm, INK_FAINT, (MARGIN + 520, y + 10))

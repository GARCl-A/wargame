"""World map: give orders to groups, then advance the world.

Draws `world.NODES` as a graph -- points joined by edges labelled with their
travel cost in hours. The guild is one or more **groups** (`gartok/group.py`):
each stands on its own node and carries its own squad. `self.selected` is the
group every click in this screen acts on -- pick a different row in the GROUPS
list to switch. Clicking a node issues that group a **travel order**
(`orders.travel`) instead of moving it there on the spot; the side panel's
per-node actions (fight, shop, work, ...) issue the matching order too. Nothing
actually *happens* until the clock runs, via `campaign.advance` -- it jumps the
world to the soonest order completion, resolves travel/work silently, and
hands any other kind back to `app` to play its screen. There is no manual
"advance" button: the moment every group has an order (none idle), the clock
starts chasing on its own and only stops once a group goes idle again or
something needs the player's screen -- see `_maybe_auto_advance` and
`Guild.can_auto_advance`. **MAINTENANCE** forces a short 1 h stop instead
(still through the same tick, so an order in flight stays in sync with the
clock).

A group with no order sitting on the same node as another idle group may
**SPLIT** (peel some of its members into a new group) or **MERGE** (fold a
co-located group into it) -- both physical, both instant, neither costs time.

`on_guild` opens the roster/gear screen; `on_wipe` fires if a tick starves the
guild out entirely. Leaving to the main menu is Esc -> the pause menu (`app`),
not a button here.
"""

import functools
import math
import os
import random

import pygame
from pygame import gfxdraw

from . import arena, artwork, economy, orders, world
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, MARGIN, NEUTRAL_C, OK,
                    RADIUS, SP2, SP3, SP4, WARN, blit_block, ellipsize,
                    outlined_text, panel, section, set_pointer, smooth_circle,
                    text, tracked, wrap_lines)
from .widgets import ButtonsMixin

_HERE = os.path.dirname(os.path.abspath(__file__))
_TEXTURES = os.path.join(_HERE, "assets", "textures")
PARCHMENT_FILE = os.path.join(_TEXTURES, "parchment.jpg")
DESK_FILE = os.path.join(_TEXTURES, "desk.jpg")

SIDE_W = 372
CHIP_Y = 34                                # gap from the title baseline to the stat row
CHIP_H = 40                                # label + value stack height of that row
ALERT_H = 34
FLASH_MS = 380.0                           # travel-order confirm pulse, on the destination node
GROUND_DAY = (46, 36, 25)                  # the map's own dark ground -- warm, so it reads as
GROUND_NIGHT = (23, 18, 13)                # one surface with the equally warm desk backdrop
GROUND_HI = (66, 52, 35)                   # soft relief blobs worked into that ground

# This screen's own dark palette for its chrome (sidebar, group cards) --
# deliberately not theme.SURFACE_*: that ramp is a cool blue-grey tuned for
# the app's flat UI screens, and sitting it next to a warm painted map read
# as two different apps stitched together. Same surface ROLES (well / panel
# / raised), just warmed to the map's own hue family.
PANEL_WELL   = (19, 15, 11)
PANEL_BG     = (27, 21, 15)
PANEL_RAISED = (41, 33, 23)
PANEL_LINE   = (61, 50, 36)

# Same override for running text: theme.INK/INK_DIM/INK_FAINT are stark
# white/cool-grey, tuned for the same flat SURFACE_* screens -- stark white
# read just as stitched-on as the cool button fills did. Warmed to a cream/tan
# ramp instead, so headings, group names and body copy sit in the same hue
# family as the chrome around them. Shadows the theme names on purpose --
# every plain `text()`/`tracked()` call already below reads off these.
INK       = (232, 221, 199)
INK_DIM   = (188, 174, 148)
INK_FAINT = (142, 130, 108)

# muted, painted tones for the map's own markings -- distinct hues, none of
# them a saturated UI accent, so a node reads as inked onto the map rather
# than as an app widget sitting on top of it.
KIND_COLOR = {"battle": DANGER, "market": NEUTRAL_C, "tavern": NEUTRAL_C,
              "town": NEUTRAL_C, "wilds": WARN, "prison": NEUTRAL_C}
KIND_BADGE = {"battle": "COMBAT", "market": "MARKET", "tavern": "TAVERN", "town": "STOP",
              "wilds": "WILDS", "prison": "PRISON"}
# game-icons.net silhouettes (assets/icons/, via artwork.icon) -- a real drawn
# icon per node kind reads better than the hand-drawn line glyphs it replaces.
KIND_ICON = {"battle": ("body", "sword-tie"), "market": ("gui", "wallet"),
             "tavern": ("action", "drinking"), "town": ("gui", "house"),
             "wilds": ("action", "wolf-howl"), "prison": ("body", "imprisoned")}
WORK_ICON = ("action", "stick-splitting")
HOME_ICON = ("gui", "house")
WORK_HOURS = (4, 8, 12, 16)

ROAD_SHADOW = (18, 13, 9)                  # sunk edge under a worn trail
ROAD_FILL = (196, 170, 122)                # light tan road, now the brighter mark on dark ground
PARCH_TAG = (214, 195, 152)                # a small paper tag pinned to the map
PARCH_TAG_BORDER = (120, 96, 62)
PARCH_INK = (54, 40, 26)                   # dark sepia ink -- only for text on a PARCH_TAG card
NODE_LABEL = (226, 213, 184)               # light warm ink for a name inked straight onto the ground
NODE_LABEL_OUTLINE = (14, 11, 8)
# Ink blue is a deliberate hue break from every KIND_COLOR, which all sit in
# the red/brown/green family -- lightened here so it still pops on the dark
# ground (was tuned for the old light-parchment version of this screen).
ROUTE_HL = (128, 168, 230)


@functools.lru_cache(maxsize=4)
def _load_texture(path):
    """A raw (unscaled) texture surface, or None if the file is missing --
    callers fall back to a procedural fill rather than crash."""
    try:
        surf = pygame.image.load(path)
    except (pygame.error, FileNotFoundError):
        return None
    try:
        surf = surf.convert()
    except pygame.error:                   # headless / tests, no display yet
        pass
    return surf


def _cover(surf, size):
    """Scale+crop `surf` to fill `size` exactly (CSS `background-size: cover`)."""
    sw, sh = surf.get_size()
    dw, dh = max(1, size[0]), max(1, size[1])
    scale = max(dw / sw, dh / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    scaled = pygame.transform.smoothscale(surf, (nw, nh))
    x, y = (nw - dw) // 2, (nh - dh) // 2
    return scaled.subsurface(pygame.Rect(x, y, dw, dh)).copy()


def _stable_hash(s):
    """A `hash()` that doesn't change between runs (str hashing is salted) --
    used to pick each road's bow direction so it's fixed run to run."""
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) & 0xffffffff
    return h


class MapCamera:
    """Pan/zoom over the node graph -- the continuous-plane analogue of
    `theme.BoardView`'s cell-grid camera. Nodes are authored as normalised
    (0..1) `pos` over a fixed reference canvas (`WORLD_W` x `WORLD_H`);
    `fit` finds the zoom that lays that whole canvas inside the viewport
    without stretching it (letterboxed on whichever axis is looser), and
    zooming past that lets a map too detailed to show whole be panned
    instead of everything just shrinking further. Markers, glyphs and
    labels stay a fixed screen size at any zoom -- pins on a paper map, not
    terrain -- so only spacing and roads actually grow; every node stays
    just as clickable zoomed in as zoomed out."""

    WORLD_W, WORLD_H = 1500.0, 1000.0
    PAD = 48.0                              # keep markers off the world's edge
    MIN_ZOOM_MUL, MAX_ZOOM_MUL = 1.0, 2.5   # relative to the fit zoom

    def __init__(self):
        self.rect = pygame.Rect(0, 0, 1, 1)
        self.fit_zoom = 1.0
        self.zoom = 1.0
        self.cam = [0.0, 0.0]               # world-space top-left of the viewport
        self._user_zoom = False

    def fit(self, rect):
        self.rect = rect
        self.fit_zoom = max(0.05, min(rect.w / self.WORLD_W, rect.h / self.WORLD_H))
        if not self._user_zoom:
            self.zoom = self.fit_zoom
        self._clamp()

    def _clamp(self):
        self.zoom = max(self.fit_zoom * self.MIN_ZOOM_MUL,
                        min(self.zoom, self.fit_zoom * self.MAX_ZOOM_MUL))
        for i, (view, extent) in enumerate(((self.rect.w, self.WORLD_W),
                                            (self.rect.h, self.WORLD_H))):
            span = extent * self.zoom
            if span <= view:
                self.cam[i] = -(view - span) / 2 / self.zoom      # centre a small world
            else:
                self.cam[i] = max(0.0, min(self.cam[i], extent - view / self.zoom))

    def world_to_screen(self, wx, wy):
        return (self.rect.x + (wx - self.cam[0]) * self.zoom,
                self.rect.y + (wy - self.cam[1]) * self.zoom)

    def screen_to_world(self, px):
        return ((px[0] - self.rect.x) / self.zoom + self.cam[0],
                (px[1] - self.rect.y) / self.zoom + self.cam[1])

    def node_xy(self, n):
        wx = self.PAD + n.pos[0] * (self.WORLD_W - 2 * self.PAD)
        wy = self.PAD + n.pos[1] * (self.WORLD_H - 2 * self.PAD)
        x, y = self.world_to_screen(wx, wy)
        return (int(x), int(y))

    def zoom_at(self, px, steps):
        if not self.rect.collidepoint(px):
            return
        anchor = self.screen_to_world(px)
        mul = self.zoom / self.fit_zoom + steps * 0.2
        self.zoom = self.fit_zoom * max(self.MIN_ZOOM_MUL, min(self.MAX_ZOOM_MUL, mul))
        self._user_zoom = True
        self.cam[0] = anchor[0] - (px[0] - self.rect.x) / self.zoom
        self.cam[1] = anchor[1] - (px[1] - self.rect.y) / self.zoom
        self._clamp()

    def pan_px(self, dx, dy):
        self.cam[0] -= dx / self.zoom
        self.cam[1] -= dy / self.zoom
        self._clamp()


class MapScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, on_guild, on_wipe, on_advance, on_manage_group, on_interactions):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.on_guild = on_guild
        self.on_wipe = on_wipe
        self.on_advance = on_advance
        self.on_manage_group = on_manage_group
        self.on_interactions = on_interactions
        # point at whichever group actually needs an order, not just the first
        self.selected = next((g for g in guild.groups if not g.busy and not g.empty),
                             guild.groups[0])
        self.mode = "map"                     # "map" | "split"
        self.split_picks = set()              # unit uids toggled to leave, while splitting
        self.notices = []                     # lines shown after a tick (route, meals, deaths)
        self.hits = []                        # [(rect, node)]
        self.buttons = []                     # [(key, rect)]
        self._hot = False
        self.group_rows = []                 # [(rect, group)]
        self.split_rows = []                 # [(rect, unit)]
        self._terr = None                    # cached terrain fill (key, surface)
        self._desk = None                    # cached backdrop fill (key, surface)
        self._flash = None                   # (node_id, seconds_left) -- travel-order pulse
        self._cam = MapCamera()
        self._pan = None                     # (anchor mouse pos, cam at anchor) while dragging

    def update(self, dt):
        if self._flash is not None:
            nid, t = self._flash
            t -= dt
            self._flash = (nid, t) if t > 0 else None

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self._cam.zoom_at(pygame.mouse.get_pos(), event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (2, 3):
            if self._cam.rect.collidepoint(event.pos):
                self._pan = (event.pos, list(self._cam.cam))
        elif event.type == pygame.MOUSEBUTTONUP and event.button in (2, 3):
            self._pan = None
        elif event.type == pygame.MOUSEMOTION and self._pan is not None:
            (ax, ay), cam0 = self._pan
            self._cam.cam = list(cam0)
            self._cam.pan_px(event.pos[0] - ax, event.pos[1] - ay)

    # ------------------------------------------------------------------ #
    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False,
                   danger=False, font=None):
        """Recolours every button to this screen's own warm ramp (`PANEL_*`
        fills, cream/tan ink) instead of `widgets.draw_button`'s default cool
        blue-grey/white -- that ramp is tuned for the flat UI screens and
        clashed sitting on the map's warm chrome. Accent/danger fills (gold,
        red) are shared semantics and untouched."""
        return super().add_button(surf, rect, key, label, enabled=enabled, primary=primary,
                                  danger=danger, font=font, fill_well=PANEL_WELL,
                                  fill_raised=PANEL_RAISED, fill_hover=PANEL_RAISED,
                                  line=PANEL_LINE, ink=INK, ink_dim=INK_DIM,
                                  ink_faint=INK_FAINT)

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

    def handle_escape(self):
        """Esc backs out of SPLIT mode instead of opening the pause menu."""
        if self.mode == "split":
            self.mode = "map"
            return True
        return False

    def _issue(self, order):
        if not self.selected.busy:
            self.selected.order = order
            self._maybe_auto_advance()

    def _go(self, target):
        if self.selected.busy or target.id == self.selected.node:
            return
        try:
            self.selected.order = orders.travel(self.selected, target.id)
        except ValueError:
            return
        self._flash = (target.id, FLASH_MS)
        self._maybe_auto_advance()

    def _maybe_auto_advance(self):
        """No group is left idle -- nothing else needs the player right now,
        so just run the clock (`App._advance` chases it through to the next
        real decision) instead of waiting on a click."""
        if self.guild.can_auto_advance:
            self.on_advance()

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
        elif key == "maintain":
            self.on_advance(dt=1)
        elif key == "manage_group":
            self.on_manage_group(self.selected)
        elif key == "interactions":
            self.on_interactions(self.selected)
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
    def _header_bottom(self):
        """Bottom edge of the header block (title + stat chips + the arena
        deadline card, when one is due) -- the map area starts below this,
        so the two never fight for the same rows."""
        y = MARGIN + CHIP_Y + CHIP_H
        if arena.defense_due(self.guild):
            y += SP2 + ALERT_H
        return y

    def _area(self, size):
        top = self._header_bottom() + SP3
        W, H = size
        w = W - 3 * MARGIN - SIDE_W
        return pygame.Rect(MARGIN, top, w, H - top - 64)

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "map"

    def _node_xy(self, n):
        return self._cam.node_xy(n)

    def _fallback_terrain(self, size, daylight):
        """The map's own dark ground: a flat base plus soft, low-contrast
        relief blobs (same trick as the desk backdrop's darkening) -- this is
        also the base every real `_terrain()` build starts from, so the map's
        colour never depends on how bright `parchment.jpg` happens to be."""
        w, h = size
        surf = pygame.Surface(size).convert()
        surf.fill(GROUND_DAY if daylight else GROUND_NIGHT)
        rnd = random.Random(7)
        for _ in range(70):
            r = rnd.randint(40, 160)
            blob = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            c = GROUND_HI if rnd.random() < 0.55 else (0, 0, 0)
            pygame.draw.circle(blob, (*c, 14), (r, r), r)
            surf.blit(blob, (rnd.randrange(-r, w), rnd.randrange(-r, h)))
        return surf

    def _terrain(self, size, daylight):
        """Cached fill for the map area: the dark ground above, with the
        parchment photo blitted on top at low alpha for grain only -- the
        photo used to *be* the surface (light paper, dark ink on top), which
        read brighter than the rest of the screen and made the map look
        pasted on. Now the ground's own colour is always dark and warm, and
        the texture just roughens it. Night darkens it further with a cool
        multiply tint. Rebuilt only on size/phase change."""
        key = (size, daylight)
        if self._terr and self._terr[0] == key:
            return self._terr[1]
        surf = self._fallback_terrain(size, daylight)
        parchment = _load_texture(PARCHMENT_FILE)
        if parchment is not None:
            grain = _cover(parchment, size)
            grain.set_alpha(44)
            surf.blit(grain, (0, 0))

        if not daylight:
            moon = pygame.Surface(size)
            moon.fill((132, 138, 168))
            surf.blit(moon, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        self._terr = (key, surf)
        return surf

    def _backdrop(self, size):
        """Cached fill for the whole window: the desk texture, heavily
        darkened -- the map sits lit on a dim table, not floating on flat UI
        chrome. Falls back to the map's own dark ground if the file is missing."""
        if self._desk and self._desk[0] == size:
            return self._desk[1]
        desk = _load_texture(DESK_FILE)
        if desk is None:
            surf = pygame.Surface(size)
            surf.fill(GROUND_NIGHT)
        else:
            surf = _cover(desk, size)
            dark = pygame.Surface(size, pygame.SRCALPHA)
            dark.fill((6, 6, 8, 205))
            surf.blit(dark, (0, 0))
        self._desk = (size, surf)
        return surf

    @staticmethod
    def _draw_area_shadow(screen, rect):
        """A soft dark halo behind the map rect instead of a hard-edged panel
        cut straight into the backdrop -- both surfaces are dark now, so a
        crisp 1px border alone reads as a seam between two flat shapes. A few
        expanding rounded rects at falling alpha (same trick as a node's
        danger aura) blend the two instead."""
        pad = 24
        glow = pygame.Surface((rect.w + pad * 2, rect.h + pad * 2), pygame.SRCALPHA)
        gr = glow.get_rect()
        for i, a in enumerate((30, 22, 15, 9, 4)):
            inset = i * 5
            pygame.draw.rect(glow, (0, 0, 0, a), gr.inflate(-inset * 2, -inset * 2),
                             border_radius=RADIUS + pad - inset)
        screen.blit(glow, (rect.x - pad, rect.y - pad))

    def _bow(self, a, b, pa, pb):
        """How far a road curves off the straight line between two nodes --
        a fixed direction/magnitude per node pair, so the map doesn't wobble
        between frames."""
        length = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        ka, kb = sorted((a, b))
        h = _stable_hash(f"{ka}|{kb}")
        sign = 1 if h % 2 == 0 else -1
        return sign * max(10, min(34, length * 0.10))

    @staticmethod
    def _curve_points(pa, pb, bow, n=20):
        """A quadratic bezier from `pa` to `pb`, bowed by `bow` px off the
        midpoint -- a road that isn't a ruler-straight graph edge."""
        mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
        dx, dy = pb[0] - pa[0], pb[1] - pa[1]
        length = math.hypot(dx, dy) or 1
        px, py = -dy / length, dx / length
        ctrl = (mx + px * bow, my + py * bow)
        pts = []
        for i in range(n + 1):
            t = i / n
            x = (1 - t) ** 2 * pa[0] + 2 * (1 - t) * t * ctrl[0] + t ** 2 * pb[0]
            y = (1 - t) ** 2 * pa[1] + 2 * (1 - t) * t * ctrl[1] + t ** 2 * pb[1]
            pts.append((int(x), int(y)))
        return pts

    @staticmethod
    def _thick_line(surf, color, points, width):
        """An anti-aliased thick polyline -- `pygame.draw.lines` has no
        anti-aliasing and its joints notch badly on a curve, which is what
        made the roads look sawtoothed. Each segment is a filled+AA-outlined
        quad; a filled+AA circle at every sample point rounds the joints."""
        r = max(1.0, width / 2)
        ir = max(1, round(r))
        for a, b in zip(points, points[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy) or 1
            nx, ny = -dy / length * r, dx / length * r
            poly = [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny),
                    (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]
            gfxdraw.filled_polygon(surf, poly, color)
            gfxdraw.aapolygon(surf, poly, color)
        for p in points:
            gfxdraw.filled_circle(surf, int(p[0]), int(p[1]), ir, color)
            gfxdraw.aacircle(surf, int(p[0]), int(p[1]), ir, color)

    @staticmethod
    def _ring(surf, color, center, r, width=2):
        """A smooth ring built from stacked AA circle outlines -- avoids the
        jagged core `pygame.draw.circle`'s own `width` argument draws."""
        x, y = int(center[0]), int(center[1])
        for rr in range(max(1, r - width + 1), r + 1):
            gfxdraw.aacircle(surf, x, y, rr, color)

    def _hovering(self):
        """Whether the mouse sits over anything `_click` would actually act
        on -- mirrors its own dispatch order, including the no-op cases
        (own node, a busy group) so the cursor doesn't promise a click that
        does nothing."""
        if self.mode == "split":
            return (any(r.collidepoint(self.mouse) for _, r in self.buttons)
                    or any(r.collidepoint(self.mouse) for r, _ in self.split_rows))
        if any(r.collidepoint(self.mouse) for _, r in self.buttons):
            return True
        if any(r.collidepoint(self.mouse) for r, _ in self.group_rows):
            return True
        if not self.selected.busy:
            hov = self._hovered_node()
            if hov is not None and hov.id != self.selected.node:
                return True
        return False

    def _draw_header(self, screen, size):
        """Title, then day/time · roster · score as three grouped stat
        clusters -- label above value, each pair sized to its own content
        instead of a row of identical boxes, with a divider between
        clusters. Colour stays reserved for the value, and only shows when
        a stat is actually urgent (someone hungry, an empty larder);
        everything else reads in plain ink. The arena deadline, when one is
        due, still gets an actual bordered card rather than a loose line of
        text."""
        f = self.fonts
        clock = self.guild.clock
        hungry = self.guild.hungry
        rations = self.guild.rations

        text(screen, "MAP", f.title, INK, (MARGIN, MARGIN - 2))

        pending = [u for u in self.guild.roster if u.pending_picks]

        groups = [
            [("DAY", str(clock.day), INK),
             ("TIME", f"{clock.hour_of_day:02d}:{clock.minute_of_hour:02d}", INK)],
            [("MEMBERS", f"{len(self.guild)} ({len(hungry)} hungry)" if hungry
              else str(len(self.guild)), WARN if hungry else INK),
             ("RATIONS", str(rations), DANGER if rations == 0 else INK),
             ("GOLD", str(self.guild.gold), INK)],
            [("WINS", str(self.guild.battles_won), INK),
             ("REPUTATION", str(self.guild.arena_reputation), INK)],
        ]
        if pending:
            groups.append([("LEVEL UP", f"{len(pending)} ready", ACCENT)])
        y = MARGIN + CHIP_Y
        x = MARGIN
        for gi, group in enumerate(groups):
            for label, value, color in group:
                w = max(f.label.size(label)[0], f.num.size(value)[0])
                tracked(screen, label, f.label, INK_FAINT, (x, y))
                text(screen, value, f.num, color, (x, y + 16))
                x += w + SP4
            if gi < len(groups) - 1:              # divider between clusters
                pygame.draw.line(screen, PANEL_LINE, (x - SP3, y), (x - SP3, y + CHIP_H - 4))
                x += SP2

        map_w = self._area(size).w
        if arena.defense_due(self.guild):
            champ = arena.champion_of(self.guild)
            ar = pygame.Rect(MARGIN, y + CHIP_H + SP2, map_w, ALERT_H)
            panel(screen, ar, fill=PANEL_BG, border=WARN, width=1, radius=RADIUS)
            lx = tracked(screen, "TITLE DEFENSE", f.label, WARN, (ar.x + SP3, ar.y + 10))
            msg = (f"{champ.name} must defend the Champion of the Pit at the Arena "
                   f"by day {arena.defense_deadline(self.guild)}")
            msg = ellipsize(msg, f.body_sm, ar.right - lx - 2 * SP3)
            text(screen, msg, f.body_sm, INK_DIM, (lx + SP3, ar.y + 9))

    def draw(self, screen):
        screen.blit(self._backdrop(screen.get_size()), (0, 0))
        self.hits = []
        self._reset_buttons()
        self.group_rows = []
        self.split_rows = []
        clock = self.guild.clock

        self._draw_header(screen, screen.get_size())

        area = self._area(screen.get_size())
        self._cam.fit(area)
        self._draw_area_shadow(screen, area)
        panel(screen, area, fill=GROUND_DAY if clock.is_daylight else GROUND_NIGHT,
              border=None)
        clip = screen.get_clip()
        screen.set_clip(area)
        screen.blit(self._terrain(area.size, clock.is_daylight), area.topleft)
        # hit rects go first: `_draw_edges` needs the hovered node (for the
        # route preview) before `_draw_nodes` draws the markers on top of it
        self.hits = [(self._node_hit_rect(*self._node_xy(n)), n) for n in world.NODES]
        self._draw_edges(screen)
        self._draw_nodes(screen)
        screen.set_clip(clip)

        self._draw_tooltip(screen, area)
        if self.mode == "split":
            self._draw_split_panel(screen, area)
        else:
            self._draw_side(screen, area)
        self._draw_footer(screen)
        set_pointer(self._hovering())

    # ------------------------------------------------------------------ #
    def _route_pairs(self):
        hov = self._hovered_node()
        if hov is None or hov.id == self.selected.node:
            return set()
        path, _ = world.route(self.selected.node, hov.id)
        path = path or []
        return {frozenset(p) for p in zip(path, path[1:])}

    def _draw_edges(self, screen):
        f = self.fonts
        zoom = self._cam.zoom
        route_pairs = self._route_pairs()
        segs = []
        for a, b, w in world.EDGES:
            pa = self._node_xy(world.node(a))
            pb = self._node_xy(world.node(b))
            on_route = frozenset((a, b)) in route_pairs
            pts = self._curve_points(pa, pb, self._bow(a, b, pa, pb))
            self._thick_line(screen, ROAD_SHADOW, pts, max(2.0, 7 * zoom))   # sunk trail edge
            self._thick_line(screen, ROAD_FILL, pts, max(1.0, 4 * zoom))
            if on_route:
                self._thick_line(screen, ROUTE_HL, pts, max(1.0, 3 * zoom))  # the route, inked over
            segs.append((pts[len(pts) // 2], w, on_route))

        for mid, w, on_route in segs:                               # cost tags on top
            s = f"{w} h"
            r = pygame.Rect(0, 0, f.mono_sm.size(s)[0] + 12, 16)
            r.center = mid
            panel(screen, r, fill=PARCH_TAG,
                  border=ROUTE_HL if on_route else PARCH_TAG_BORDER, radius=8)
            text(screen, s, f.mono_sm, ROUTE_HL if on_route else PARCH_INK,
                 r.center, center=True)

    @staticmethod
    def _kind_icon(screen, slug, center, color):
        """A drawn game-icons.net silhouette (see `KIND_ICON`/`WORK_ICON`/
        `HOME_ICON`) tinted to sit on the marker's own coloured disc --
        replaces the hand-drawn line glyphs this used to fall back on."""
        if slug is None:
            return
        img = artwork.icon(slug[0], slug[1], 20, color=color)
        if img is not None:
            screen.blit(img, img.get_rect(center=center))

    def _draw_marker(self, screen, x, y, n, here, hovered, others=0):
        col = KIND_COLOR[n.kind]
        sh = pygame.Surface((36, 16), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 95), sh.get_rect())
        screen.blit(sh, (x - 18, y + 5))

        if here:
            smooth_circle(screen, ACCENT, (x, y), 13)
            self._ring(screen, ACCENT_INK, (x, y), 13, 2)
            self._kind_icon(screen, HOME_ICON, (x, y), ACCENT_INK)
            pygame.draw.line(screen, ACCENT_INK, (x, y - 13), (x, y - 30), 2)
            pygame.draw.polygon(screen, ACCENT,
                                [(x + 1, y - 30), (x + 15, y - 26), (x + 1, y - 20)])
        else:
            if n.kind in ("battle", "wilds"):                       # danger aura
                aura = pygame.Surface((54, 54), pygame.SRCALPHA)
                pygame.draw.circle(aura, (*col, 24), (27, 27), 27)
                pygame.draw.circle(aura, (*col, 30), (27, 27), 18)
                screen.blit(aura, (x - 27, y - 27))
            smooth_circle(screen, col, (x, y), 13)
            self._ring(screen, tuple(c // 2 for c in col), (x, y), 13, 2)
            ink = tuple(c // 3 for c in col)
            self._kind_icon(screen, WORK_ICON if n.work else KIND_ICON.get(n.kind), (x, y), ink)
            if hovered:
                self._ring(screen, ROUTE_HL, (x, y), 17, 2)
            if self._flash is not None and self._flash[0] == n.id:
                prog = 1 - max(0.0, self._flash[1]) / FLASH_MS
                self._ring(screen, (*ROUTE_HL, int(220 * (1 - prog))),
                          (x, y), 13 + round(prog * 11), 2)

        if others:                                                 # other groups standing here
            badge = pygame.Rect(0, 0, 22, 16)
            badge.center = (x + 15, y - 15)
            panel(screen, badge, fill=PANEL_RAISED, border=ACCENT, radius=8)
            text(screen, f"+{others}", self.fonts.label, ACCENT, badge.center, center=True)

    @staticmethod
    def _node_hit_rect(x, y):
        return pygame.Rect(x - 46, y - 34, 92, 66)

    def _draw_nodes(self, screen):
        f = self.fonts
        hov = self._hovered_node()
        for n in world.NODES:
            x, y = self._node_xy(n)
            here = n.id == self.selected.node
            occupants = sum(1 for g in self.guild.groups if g.node == n.id)
            others = occupants - (1 if here else 0)
            self._draw_marker(screen, x, y, n, here, n is hov, others)

            # Direct text with an outline instead of a pill behind it -- reads
            # as inked onto the map rather than an app widget sitting on top.
            fg = ACCENT if here else ROUTE_HL if n is hov else NODE_LABEL
            outline = ACCENT_INK if here else NODE_LABEL_OUTLINE
            outlined_text(screen, n.name, f.body_bd, fg, (x, y + 27),
                          outline=outline, center=True)

    @staticmethod
    def _wilds_actions():
        """The activities on offer in the wilds -- (button key, label, one-liner).
        Just Hunt for now; foraging and the like slot in here later."""
        return [("hunt", "GO HUNTING",
                 "spend the day for meat  ·  a pack may find you first")]

    def _draw_tooltip(self, screen, area):
        """A preview of the hovered node -- name, kind and a taste of its
        blurb, plus the travel cost -- pinned near the cursor. Kind is
        legible straight off each node's own icon, so nothing here needs a
        legend to decode it. Scouting a destination no longer requires
        actually sending a group there first to see what it is."""
        hov = self._hovered_node()
        if hov is None or hov.id == self.selected.node:
            return
        f = self.fonts
        _, hours = world.route(self.selected.node, hov.id)
        busy = "  (group is busy)" if self.selected.busy else ""
        action = f"{hours} h   ·   click to send{busy}"

        w = 232
        blurb = ellipsize(hov.blurb, f.body_sm, w - 2 * SP2)
        h = 2 * SP2 + 18 + 16 + 16 + 4 + 18

        r = pygame.Rect(0, 0, w, h)
        r.topleft = (self.mouse[0] + 14, self.mouse[1] - 6)
        r.clamp_ip(area.inflate(-SP2, -SP2))
        panel(screen, r.move(0, 2), fill=ROAD_SHADOW, border=None, radius=6)
        panel(screen, r, fill=PARCH_TAG, border=ROUTE_HL, radius=6)

        x, y = r.x + SP2, r.y + SP2
        text(screen, hov.name, f.body_bd, PARCH_INK, (x, y))
        y += 18
        tracked(screen, KIND_BADGE[hov.kind], f.label, KIND_COLOR[hov.kind], (x, y))
        y += 16
        text(screen, blurb, f.body_sm, PARCH_INK, (x, y))
        y += 16 + 4
        text(screen, action, f.body_sm, ROUTE_HL, (x, y))

    # ------------------------------------------------------------------ #
    def _order_status(self, group):
        """One-line status for a group's GROUPS-list row."""
        o = group.order
        if o is None or o.kind == "idle":
            return "idle"
        if o.kind == "travel":
            dest_name = world.node(o.final_dest).name
            if o.path:                            # more waypoints still to come
                return f"→ {dest_name} via {world.node(o.dest).name} ({o.remaining:g} h)"
            return f"→ {dest_name} ({o.remaining:g} h)"
        if o.kind == "work":
            return f"working ({o.remaining:g} h left)"
        return f"heading to {o.kind} ({o.remaining:g} h)"

    def _draw_groups(self, screen, cx, y, cw, f):
        y = section(screen, "GROUPS", cx, y, cw, f, color=ACCENT)
        for g in self.guild.groups:
            sel = g is self.selected
            needs = not g.busy and not g.empty        # idle: waiting on the player
            r = pygame.Rect(cx, y, cw, 38)
            hov = r.collidepoint(self.mouse)
            border = ACCENT if sel else WARN if needs else PANEL_LINE
            panel(screen, r, fill=PANEL_RAISED if (sel or hov) else PANEL_WELL,
                  border=border, width=2 if (sel or needs) else 1, radius=8)
            name = g.name or f"Group ({len(g.members)})"
            if g.leader is not None:
                name += f"  ·  led by {g.leader.name}"
            text(screen, ellipsize(name, f.body_sm, cw - 2 * SP3),
                 f.body_sm, ACCENT if sel else INK, (r.x + SP3, r.y + 7))
            status_col = WARN if (needs and not sel) else INK_DIM
            text(screen, f"{world.node(g.node).name}  ·  {self._order_status(g)}",
                 f.label, status_col, (r.x + SP3, r.y + 22))
            if any(u.pending_picks for u in g.members):
                text(screen, "● LEVEL UP", f.label, ACCENT, (r.right - SP3, r.y + 22), right=True)
            self.group_rows.append((r, g))
            y += 42
        return y + SP2

    def _draw_group_actions(self, screen, cx, y, cw, f):
        """SPLIT (peel members off) / MERGE (fold in a co-located idle group,
        one row per such group -- there can be more than one)."""
        g = self.selected
        if g.busy:
            return y
        
        mg = pygame.Rect(cx, y, cw, 30)
        self.add_button(screen, mg, "manage_group", "MANAGE GEAR & QUESTS", font=f.body_sm)
        y += 34

        if len(g.members) > 1:
            r = pygame.Rect(cx, y, cw, 30)
            self.add_button(screen, r, "split", "SPLIT", font=f.body_sm)
            y += 34
        mates = [o for o in self.guild.groups if o is not g and o.node == g.node and not o.busy]
        for o in mates:
            mr = pygame.Rect(cx, y, cw, 30)
            name = o.name or f"Group ({len(o.members)})"
            self.add_button(screen, mr, f"merge:{o.gid}", f"MERGE WITH {name}", font=f.body_sm)
            y += 34
        return y

    def _draw_side(self, screen, area):
        f = self.fonts
        here = self._here()
        x = area.right + MARGIN
        rect = pygame.Rect(x, area.y, SIDE_W, area.h)
        panel(screen, rect, fill=PANEL_BG, border=PANEL_LINE, radius=RADIUS)

        pad = SP4
        cx = x + pad
        cw = SIDE_W - 2 * pad
        y = area.y + pad

        # --- GROUPS card: the list + its SPLIT/MERGE/MANAGE actions, boxed
        # off as one unit so it doesn't visually run into the location info
        # below it. Height is derived the same way `_draw_groups` /
        # `_draw_group_actions` lay their own rows out, so the box always
        # matches what actually gets drawn inside it.
        g = self.selected
        mates = [o for o in self.guild.groups if o is not g and o.node == g.node and not o.busy]
        actions_h = (34 + (34 if len(g.members) > 1 else 0) + 34 * len(mates)) if not g.busy else 0
        groups_h = 30 + 42 * len(self.guild.groups) + actions_h
        panel(screen, pygame.Rect(x + SP2, y - SP2, SIDE_W - 2 * SP2, groups_h + 2 * SP2),
              fill=PANEL_WELL, border=PANEL_LINE, radius=RADIUS)
        y = self._draw_groups(screen, cx, y, cw, f)
        y = self._draw_group_actions(screen, cx, y, cw, f)
        y += SP3

        # --- LOCATION card: what/where the selected group is standing on.
        blurb_lines = wrap_lines([here.blurb], f.body_sm, cw)
        loc_h = 18 + 24 + 22 + 16 * len(blurb_lines)
        panel(screen, pygame.Rect(x + SP2, y - SP2, SIDE_W - 2 * SP2, loc_h + 2 * SP2),
              fill=PANEL_WELL, border=PANEL_LINE, radius=RADIUS)
        tracked(screen, "SELECTED GROUP IS AT", f.label, ACCENT, (cx, y))
        y += 18
        text(screen, here.name, f.heading, INK, (cx, y))
        y += 24
        tracked(screen, KIND_BADGE[here.kind], f.label, KIND_COLOR[here.kind], (cx, y))
        y += 22
        for ln in blurb_lines:
            text(screen, ln, f.body_sm, INK_DIM, (cx, y))
            y += 16

        y += SP3
        y = section(screen, "HERE", cx, y, cw, f, color=ACCENT)
        if self.selected.busy:
            text(screen, f"Busy: {self._order_status(self.selected)}", f.body_sm,
                 WARN, (cx, y))
        elif here.is_battle:
            br = pygame.Rect(cx, y, cw, 38)
            defense = here.arena and arena.defense_due(self.guild)
            label = ("DEFEND YOUR TITLE" if defense
                     else "BET AT THE ARENA" if here.arena else "ATTACK")
            self.add_button(screen, br, "arena", label, primary=True)
            y += 44
            note = ("1v1 for the Champion of the Pit -- no stake, no backup" if defense
                    else "non-lethal · stake copper, win the purse" if here.arena
                    else "lethal combat · loot the bodies")
            text(screen, note, f.body_sm,
                 WARN if defense else INK_FAINT, (cx, y))
        elif here.is_market:
            mr = pygame.Rect(cx, y, cw, 38)
            self.add_button(screen, mr, "market", "ENTER THE MARKET")
        elif here.is_tavern:
            tr = pygame.Rect(cx, y, cw, 38)
            self.add_button(screen, tr, "recruit", "ENTER THE TAVERN")
            y += 44
            text(screen, "talk a stranger into signing with the guild", f.body_sm,
                 INK_FAINT, (cx, y))
        elif here.is_prison:
            pr = pygame.Rect(cx, y, cw, 38)
            self.add_button(screen, pr, "prison", "VISIT THE PRISON")
            y += 44
            text(screen, "pay a criminal's bail for a chance to recruit them", f.body_sm,
                 INK_FAINT, (cx, y))
        elif here.work:
            tracked(screen, "WORK A SHIFT", f.label, INK_DIM, (cx, y))
            y += 18
            gap = SP2
            cw4 = (cw - 3 * gap) // 4
            for i, h in enumerate(WORK_HOURS):
                r = pygame.Rect(cx + i * (cw4 + gap), y, cw4, 34)
                self.add_button(screen, r, f"work:{h}", f"{h} h", font=f.body_sm)
            y += 42
            text(screen, "trade hours of the day for copper  ·  pays little, but it's sure",
                 f.body_sm, INK_FAINT, (cx, y))
            y += 16
            for u in self.selected.members:
                level = economy.lumber_level(u)
                own_axe = level >= economy.LUMBER_LEVEL_OWN_AXE
                wage = economy.LUMBER_WAGE_OWN_AXE if own_axe else economy.LUMBER_WAGE
                status = "own Axe" if own_axe else "foreman's axe"
                text(screen, f"{u.name}: {status} -- {wage}c / "
                     f"{economy.LUMBER_BLOCK_HOURS}h block",
                     f.body_sm, OK if own_axe else INK_FAINT, (cx, y))
                y += 15
            need_axe = [u for u in self.selected.members
                       if u.work_level > 0 and economy.lumber_level(u) == 0]
            capped = [u for u in self.selected.members
                     if economy.lumber_level(u) >= economy.LUMBER_LEVEL_OWN_AXE
                     and u.work_level > economy.lumber_level(u)]
            if need_axe:
                y += 4
                names = ", ".join(u.name for u in need_axe)
                msg = f"{names}: past this job bare-handed -- bring their own Axe for a better wage and to keep banking work XP"
                wrapped = wrap_lines([msg], f.body_sm, cw)
                y = blit_block(screen, wrapped, cx, y, f.body_sm, color=WARN, lh=15)
            if capped:
                y += 4
                names = ", ".join(u.name for u in capped)
                msg = f"{names}: has outgrown this job even with their own Axe -- no more work XP here, look for tougher work"
                wrapped = wrap_lines([msg], f.body_sm, cw)
                y = blit_block(screen, wrapped, cx, y, f.body_sm, color=WARN, lh=15)
        elif here.is_wilds:
            for key, label, note in self._wilds_actions():
                r = pygame.Rect(cx, y, cw, 38)
                self.add_button(screen, r, key, label)
                y += 42
                text(screen, note, f.body_sm, INK_FAINT, (cx, y))
                y += 20
        elif here.bank:
            br = pygame.Rect(cx, y, cw, 38)
            self.add_button(screen, br, "bank", "VISIT THE BANK")
            y += 44
            chest = (f"strongbox: {self.guild.bank_load:g} / {self.guild.bank_capacity} kg"
                     if self.guild.bank_unlocked
                     else "rent a strongbox  ·  stash gear the guild isn't carrying")
            text(screen, chest, f.body_sm, INK_FAINT, (cx, y))
        else:
            text(screen, "Nothing happens here. A safe stop.", f.body_sm,
                 INK_FAINT, (cx, y))

        # A node's flags aren't mutually exclusive (the City is both a bank and
        # a tanner) -- checked after the kind-dispatch chain above, not nested
        # in one branch of it, so a future node can carry `tanner` on its own.
        # Still gated on not-busy, same as every button the chain above offers.
        interactions = []
        if here.tanner and not self.selected.busy:
            interactions.append("tanner")
        if here.trust and not self.selected.busy:
            interactions.append("trust")
            
        if here.forge and not self.selected.busy:
            y += 30
            fr = pygame.Rect(cx, y, cw, 38)
            self.add_button(screen, fr, "forge", "VISIT THE FORGE")
            y += 44
            text(screen, "craft weapons, armors and traps",
                 f.body_sm, INK_FAINT, (cx, y))

        if interactions:
            y += 30
            ir = pygame.Rect(cx, y, cw, 38)
            self.add_button(screen, ir, "interactions", "AVAILABLE INTERACTIONS")
            y += 44
            text(screen, f"{len(interactions)} mission(s) / service(s) here",
                 f.body_sm, INK_FAINT, (cx, y))
            y += 24

        has_property_business = (self.guild.property_city_unlocked or
                                 self.guild.property_city_squatting or
                                 self.guild.bankers_debt > 0)
        if here.city_property and has_property_business and not self.selected.busy:
            y += 30
            pr = pygame.Rect(cx, y, cw, 38)
            self.add_button(screen, pr, "property", "VISIT THE PROPERTY")
            y += 44
            if self.guild.property_city_repossession_due:
                note, col = "the Bankers want the house back, or the tax paid", DANGER
            elif self.guild.property_city_squatting:
                note, col = "squatting -- the guard can still come to clear it out", WARN
            elif self.guild.property_city_unlocked:
                note = (f"house: {self.guild.property_city_load:g} / "
                        f"{economy.CITY_PROPERTY_CAPACITY} kg")
                col = INK_FAINT
            elif self.guild.bankers_debt > 0:
                note, col = f"owes the Bankers {self.guild.bankers_debt} copper", DANGER
            text(screen, note, f.body_sm, col, (cx, y))

        if here.claim and not self.selected.busy:
            y += 30
            cr = pygame.Rect(cx, y, cw, 38)
            self.add_button(screen, cr, "claim", "THE WILDS CLAIM")
            y += 44
            stage = self.guild.wilds_claim_stage
            if stage == "ESTABLISHED" and self.guild.wilds_claim_owner == "seized":
                note, col = "SEIZED -- send a group to retake it", DANGER
            elif stage == "ESTABLISHED":
                note, col = "established -- the guild's own ground", OK
            elif stage == "SUSTAINING":
                note, col = f"sustaining: {self.guild.wilds_claim_sustain_days_left} day(s) left", WARN
            elif stage == "NONE":
                note, col = "unclaimed -- scout it to begin", INK_FAINT
            else:
                note, col = f"stage: {stage.title()}", INK_FAINT
            text(screen, note, f.body_sm, col, (cx, y))

        if here.ledger and not self.selected.busy:
            y += 30
            lr = pygame.Rect(cx, y, cw, 38)
            self.add_button(screen, lr, "ledger", "VISIT THE OUTPOST")
            y += 44
            text(screen, "hand over what you're carrying, if anything's owed",
                 f.body_sm, INK_FAINT, (cx, y))

        # "from here you can reach" used to be repeated here as a text list --
        # cut: the map itself already draws every edge out of your node with
        # its hour cost, so the sidebar isn't the only place carrying it.

        if self.notices:
            lines = [w for ln in self.notices for w in wrap_lines([ln], f.body_sm, cw)]
            yy = rect.bottom - pad - 13 * len(lines)
            for ln in lines:
                col = DANGER if "starved" in ln else ACCENT
                text(screen, ln, f.body_sm, col, (cx, yy))
                yy += 13

    def _draw_split_panel(self, screen, area):
        f = self.fonts
        x = area.right + MARGIN
        rect = pygame.Rect(x, area.y, SIDE_W, area.h)
        panel(screen, rect, fill=PANEL_BG, border=PANEL_LINE, radius=RADIUS)

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
            panel(screen, r, fill=PANEL_RAISED if (picked or hov) else PANEL_WELL,
                  border=ACCENT if picked else PANEL_LINE, width=2 if picked else 1, radius=8)
            text(screen, u.name, f.body_sm, ACCENT if picked else INK, (r.x + SP2, r.y + 3))
            name_w = f.body_sm.size(u.name)[0]
            tag = f"{u.race['name']} · R-Lvl {u.racial_level}"
            text(screen, tag, f.label, ACCENT if picked else INK_DIM, (r.x + SP2 + name_w + SP2, r.y + 5))
            text(screen, "leaving" if picked else "stays", f.label,
                 ACCENT if picked else INK_FAINT, (r.right - SP2, r.y + 3), right=True)
            self.split_rows.append((r, u))
            y += 34

        y = rect.bottom - pad - 76
        ok = bool(self.split_picks)
        cr = pygame.Rect(cx, y, cw, 36)
        self.add_button(screen, cr, "split_confirm", "CONFIRM SPLIT", primary=True, enabled=ok)
        y += 44
        xr = pygame.Rect(cx, y, cw, 32)
        self.add_button(screen, xr, "split_cancel", "cancel", font=f.body)

    def _draw_footer(self, screen):
        y = screen.get_height() - 52

        pending_count = sum(1 for u in self.guild.roster if u.pending_picks)
        if pending_count:
            guild_label = f"GUILD ({pending_count} LEVEL UP)"
            gw = max(195, self.fonts.body_sm.size(guild_label)[0] + 32)
        else:
            guild_label = "GUILD / GEAR"
            gw = 170

        g = pygame.Rect(MARGIN, y, gw, 36)
        self.add_button(screen, g, "guild", guild_label, primary=True)

        hungry = self.guild.hungry
        mt = pygame.Rect(g.right + SP3, y, 160, 36)
        # a stop helps only if a hungry member can reach a ration: their own pack,
        # or the shared larder of a group-mate who pools food
        reachable = any(u.rations for u in hungry) or any(
            u.share_food and u.rations for u in self.guild.roster)
        urgent = bool(hungry) and reachable
        self.add_button(screen, mt, "maintain", "MAINTENANCE (1 h)", primary=urgent)

        hint = ("give every idle group an order and the clock runs itself"
                if self.guild.needs_orders else
                "every group is underway  ·  the clock is running on its own")
        text(screen, f"{hint}  ·  Esc for the pause menu",
             self.fonts.body_sm, INK_FAINT, (mt.right + SP3, y + 10))

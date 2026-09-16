"""Manage Gear: shuffle the roster's loadouts side by side.

The guild screen is a master-detail view -- good for reading one member, poor for
the job you do most between outings: moving gear across several members at once.
This screen fixes that. Pick the members you want to work with from the strip up
top; each shows as a full column -- HANDS / OFF / BODY / PACK -- and every column
is both a source and a drop target. Move items by:

- **drag** an item onto a HAND / OFF / BODY slot, or anywhere else on a column to
  drop it in that member's pack, or onto THROW AWAY;
- **click** it to pick it up and click the destination (click it again, or click
  away, to put it back);
- **shift/ctrl-click** to gather several pack items for one move; or
- **right-click** an item for a "send to..." menu -- the fastest way to hand a
  pile to a specific member's pack.

It edits the same persistent `equipped_weapon` / `equipped_offhand` /
`equipped_armor` / `_base_inventory` the guild screen does (`LoadoutMoveMixin`),
so the next battle re-seeds every `Combatant` from the new loadout.
`native = True`. `on_back()` returns to the guild screen.
"""

import pygame

from . import chest, data, magic, missions
from .dragselect import DragSelectMixin, LoadoutMoveMixin
from .packbox import PackColumnMixin
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, RADIUS, SP1, SP2, SP3, SP4, SP5,
                    SURFACE_0, SURFACE_1, SURFACE_2, SURFACE_3, SURFACE_4, WARN,
                    ellipsize, kg, panel, set_pointer, text,
                    token_badge)
from .widgets import ButtonsMixin, footer_bar

COL_MIN, COL_MAX = 288, 380              # loadout column width clamps
MENU_HEAD = 22                           # send-to menu: header strip above the rows


class GearScreen(PackColumnMixin, DragSelectMixin, LoadoutMoveMixin, ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, on_back):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.roster = guild.roster
        self.on_back = on_back
        self.managed = list(self.roster)     # members shown as columns (clamped to fit)
        self.selected = []                   # [(unit, loc), ...]: loc is "hand"|"offhand"|"armor"|pack index
        self.menu = None                     # send-to menu: {pos, w, h, rh, rows:[(kind, arg)], picks} (+ rect/hits once drawn)
        self.notice = None                   # last chest-opening result, shown in the footer
        self.zones = []                     # [(rect, unit|None, "hand"|"offhand"|"armor"|"pack"|"discard")]
        self.sources = []                  # [(rect, unit, loc)]
        self.toggle_hits = []              # [(rect, unit)]
        self.buttons = []                  # [(key, rect)]
        self._cap = len(self.roster)         # columns that fit (recomputed each frame)
        self._hot = False

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "gear"

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
        if self._lock_at(px) is not None:
            return None
        for rect, unit, loc in self.sources:
            if rect.collidepoint(px):
                return (unit, loc)
        return None

    def _zone_at(self, px):
        for rect, unit, zone in self.zones:
            if rect.collidepoint(px):
                return (unit, zone)
        return None

    def _begin_drag(self, src):
        if src not in self.selected:
            self.selected = [src]

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.menu:
            self._menu_click(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._open_menu(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.menu = None
        super().handle_event(event)

    def _toggle(self, unit):
        self.selected = []
        if unit in self.managed:
            self.managed.remove(unit)
        elif len(self.managed) < self._cap:
            self.managed.append(unit)

    def _drop(self, px, dragging, src):
        if dragging:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            return

        lock_hit = self._lock_at(px)
        if lock_hit is not None:
            lock_hit[0].toggle_lock(lock_hit[1])
            return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "back":
                    self.on_back()
                elif key == "distribute":
                    self._distribute_load()
                return
        if not self.selected:
            for rect, unit in self.toggle_hits:
                if rect.collidepoint(px):
                    self._toggle(unit)
                    return

        mods = pygame.key.get_mods()
        if src is not None and mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL):
            if src in self.selected:
                self.selected.remove(src)
            else:
                self.selected.append(src)
            return

        if self.selected:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            elif src in self.selected:
                self.selected.remove(src)
            elif src is not None:
                self.selected = [src]
            else:
                self.selected = []
            return

        self.selected = [src] if src is not None else []

    # ------------------------------------------------------------------ #
    # send-to menu                                                        #
    # ------------------------------------------------------------------ #
    def _open_menu(self, px):
        src = self._source_at(px)
        if src is None:
            self.menu = None
            return
        picks = self.selected if src in self.selected else [src]
        picks = [p for p in picks if self._item_at(*p) is not None]
        if not picks:
            self.menu = None
            return
        self.selected = list(picks)

        # a member you'd only be handing their own pack items back to is a no-op
        owners = {id(p[0]) for p in picks}
        lift = len(owners) > 1 or any(isinstance(p[1], str) for p in picks)
        dests = [u for u in self.managed if lift or id(u) not in owners]
        rows = [("member", u) for u in dests] + [("discard", None)]
        if len(picks) == 1 and self._item_at(*picks[0]) in (data.CHEST_ITEM, data.MISSION_CHEST_ITEM):
            rows.append(("open", None))
        if len(picks) == 1:
            unit, item = picks[0][0], self._item_at(*picks[0])
            spell = magic.spell_for_scroll(item) if item else None
            if spell and unit.magic_source and spell.id not in unit.spells_known:
                rows.append(("study", spell))
            lang = magic.language_for_dictionary(item) if item else None
            if lang and lang.name not in unit.languages:
                rows.append(("study", lang))

        f = self.fonts
        w = 160
        for kind, arg in rows:
            lbl = (self._study_label(picks[0][0], arg) if kind == "study" else
                   "OPEN THE CHEST" if kind == "open" else
                   f"to {arg.name}" if kind == "member" else "throw away")
            w = max(w, f.body.size(lbl)[0] + 2 * SP4)
        self.menu = {"pos": px, "w": w, "h": MENU_HEAD + len(rows) * 24 + SP1,
                     "rh": 24, "rows": rows, "picks": list(picks)}

    def _study_label(self, unit, target):
        return "stop studying" if unit.study_target == target.id else f"study {target.name}"

    def _menu_click(self, px):
        m = self.menu
        self.menu = None
        if m is None or not m.get("rect") or not m["rect"].collidepoint(px):
            return
        for r, kind, arg in m["hits"]:
            if r.collidepoint(px):
                if kind == "open":
                    unit, loc = m["picks"][0]
                    self._open_chest(unit, self._item_at(unit, loc))
                    return
                if kind == "study":
                    unit = m["picks"][0][0]
                    unit.study_target = None if unit.study_target == arg.id else arg.id
                    self.selected = []
                    return
                self.selected = list(m["picks"])
                self._give_many(arg, "pack" if kind == "member" else "discard")
                return

    def _open_chest(self, unit, item):
        """Pick the lock right where the chest sits -- no move, no drop, just
        the roll. A miss costs nothing (the chest stays put, try again any
        time), so this never asks for confirmation. `item` is whichever chest
        was actually right-clicked (not just "does `unit` have one somewhere"
        -- a unit could carry both kinds at once, e.g. via the sandbox
        editor). The Bankers' own sealed chest (`data.MISSION_CHEST_ITEM`)
        picks the same lock but fails its mission and marks a crime on a hit
        -- `missions.open_mission_chest`, not `chest.try_open`."""
        sealed = item == data.MISSION_CHEST_ITEM
        opened, gems = (missions.open_mission_chest(self.guild, unit) if sealed
                       else chest.try_open(unit))
        if not opened:
            self.notice = f"{unit.name} can't pick the lock -- the chest is still there."
        elif sealed:
            self.notice = (f"{unit.name} breaks the Bankers' seal -- {gems} {data.GEM_ITEM} "
                           f"spill out, but the trust mission is ruined. Crime: {unit.crime}.")
        else:
            self.notice = f"{unit.name} picks the lock -- {gems} {data.GEM_ITEM} inside."
        self.selected = []

    def _draw_menu(self, screen, W, H):
        f = self.fonts
        m = self.menu
        x, y = m["pos"]
        rect = pygame.Rect(min(x, W - m["w"] - SP2), min(y, H - m["h"] - SP2),
                           m["w"], m["h"])
        panel(screen, rect, fill=SURFACE_2, border=ACCENT, width=1, radius=RADIUS)
        names = self._carried_names()
        head = names[0] if len(names) == 1 else f"{len(names)} items"
        text(screen, ellipsize(f"send {head}", f.label, m["w"] - 2 * SP3), f.label,
             INK_FAINT, (rect.x + SP3, rect.y + 4))
        m["rect"] = rect
        m["hits"] = []
        iy = rect.y + MENU_HEAD
        for kind, arg in m["rows"]:
            r = pygame.Rect(rect.x + SP1, iy, rect.w - 2 * SP1, m["rh"])
            hov = r.collidepoint(self.mouse)
            if hov:
                self._hot = True
                panel(screen, r, fill=SURFACE_4, border=LINE_SOFT, width=0, radius=4)
            lbl = (self._study_label(m["picks"][0][0], arg) if kind == "study" else
                   "OPEN THE CHEST" if kind == "open" else
                   f"to {arg.name}" if kind == "member" else "throw away")
            col = DANGER if kind == "discard" else ACCENT if hov else INK
            text(screen, lbl, f.body, col, (r.x + SP2, r.centery - 7))
            m["hits"].append((r, kind, arg))
            iy += m["rh"]

    def _distribute_load(self):
        from . import unit as unit_module
        targets = [u for u in self.managed if u in self.roster] or list(self.roster)
        if len(targets) <= 1:
            return
        unit_module.distribute_load(targets)
        self.notice = "Redistributed pack load across members."

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        screen.fill(SURFACE_0)
        self.zones = []
        self.sources = []
        self.toggle_hits = []
        self._pack_areas = []
        self._lock_hits = []
        self._reset_buttons()

        self.managed = [u for u in self.managed if u in self.roster]
        pad = MARGIN if W < 1500 else SP5

        text(screen, "MANAGE GEAR", f.title, INK, (pad, pad - 2))
        carried = self._carried_names()
        if carried:
            if len(carried) == 1:
                lead = f"moving  {carried[0]} ({kg(data.item_weight(carried[0]))})"
            else:
                tot = sum(data.item_weight(n) for n in carried)
                lead = f"moving  {len(carried)} items ({kg(tot)})"
            sub, col = (lead + "  ·  drop on a HAND / OFF / BODY, anywhere else on a "
                        "column for the pack, or THROW AWAY  ·  click outside to "
                        "cancel", ACCENT)
        else:
            sub, col = ("click a member to add or drop a column  ·  drag an item "
                        "(or click)  ·  shift+click gathers  ·  right-click for "
                        "send-to", INK_DIM)
        text(screen, ellipsize(sub, f.body, W - 2 * pad), f.body, col, (pad, pad + 30))

        top = pad + 62
        bottom = H - 56

        cols_area = W - 2 * pad
        self._cap = max(1, (cols_area + SP3) // (COL_MIN + SP3))
        strip_h = self._draw_toggle_strip(screen, pad, top, cols_area)
        ctop = top + strip_h + SP3

        shown = self.managed[:self._cap]
        n = max(1, len(shown))
        col_w = min(COL_MAX, (cols_area - (n - 1) * SP3) // n)
        for i, unit in enumerate(shown):
            r = pygame.Rect(pad + i * (col_w + SP3), ctop, col_w, bottom - ctop)
            self._draw_column(screen, r, unit, carried)

        if len(self.managed) > self._cap:
            text(screen, f"+{len(self.managed) - self._cap} selected but hidden — "
                 "widen the window or drop a column", f.label, INK_FAINT,
                 (pad, bottom + 4))

        self._draw_footer(screen, W, H, pad)

        if self._dragging and carried:
            gx, gy = self.mouse
            label = carried[0] if len(carried) == 1 else f"{len(carried)} items"
            gr = pygame.Rect(gx + 12, gy + 6, f.body_sm.size(label)[0] + 2 * SP2, 20)
            panel(screen, gr, fill=ACCENT, border=ACCENT_INK, width=1, radius=4)
            text(screen, label, f.body_sm, ACCENT_INK, gr.center, center=True)

        if self.menu is not None:
            self._draw_menu(screen, W, H)

        set_pointer(self._hot)

    # ------------------------------------------------------------------ #
    def _draw_toggle_strip(self, screen, x, y, w):
        """One row of chips -- every roster member; the managed ones lit. Wraps to
        more rows if the roster is long. Returns the strip height."""
        f = self.fonts
        cx, cy = x, y
        h = 26
        for unit in self.roster:
            on = unit in self.managed
            shown = on and self.managed.index(unit) < self._cap
            lbl = ellipsize(unit.full_name, f.body_sm, 150)
            cw = f.body_sm.size(lbl)[0] + 34
            if cx + cw > x + w:
                cx, cy = x, cy + h + SP2
            r = pygame.Rect(cx, cy, cw, h)
            if r.collidepoint(self.mouse):
                self._hot = True
            full = not on and len(self.managed) >= self._cap
            panel(screen, r, fill=SURFACE_3 if on else SURFACE_1,
                  border=ACCENT if shown else WARN if on else LINE_SOFT,
                  width=1, radius=RADIUS)
            token_badge(screen, (r.x + 12, r.centery), unit, f, r=8)
            text(screen, lbl, f.body_sm,
                 INK if on else INK_FAINT if full else INK_DIM,
                 (r.x + 24, r.centery - 6))
            self.toggle_hits.append((r, unit))
            cx += cw + SP2
        return (cy - y) + h

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen, W, H, pad):
        if self._carried_names():
            trash = pygame.Rect(0, 0, 220, 32)
            trash.center = (W // 2, H - 44 + 14)
            over = trash.collidepoint(self.mouse)
            panel(screen, trash, fill=DANGER if over else SURFACE_2, border=DANGER,
                  width=1, radius=RADIUS)
            text(screen, "THROW AWAY", self.fonts.body_bd, ACCENT_INK if over else DANGER,
                 trash.center, center=True)
            self.zones.append((trash, None, "discard"))

        footer_bar(self, screen,
                  secondary=("distribute", "DISTRIBUTE LOAD") if len(self.managed) > 1 else None,
                  primary=("back", "BACK TO GUILD"), notice=self.notice, margin=pad)

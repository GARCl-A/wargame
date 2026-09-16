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

from . import chest, data, missions
from .dragselect import DragSelectMixin, LoadoutMoveMixin
from .packbox import PackColumnMixin
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .theme import (ACCENT, ACCENT_INK, DANGER, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SP4, SP5,
                    SURFACE_0, SURFACE_1, SURFACE_2, SURFACE_3, SURFACE_4, WARN,
                    ellipsize, panel, set_pointer, text)
from .widgets import ButtonsMixin, footer_bar

COL_MIN, COL_MAX = 288, 380              # loadout column width clamps
MENU_HEAD = 22                           # send-to menu: header strip above the rows


class GroupScreen(PackColumnMixin, DragSelectMixin, LoadoutMoveMixin, ButtonsMixin, SheetModalMixin, Screen):
    native = True

    def __init__(self, fonts, guild, group, on_back):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.on_back = on_back
        self.tab = "gear"
        self.managed = list(self.group.members)     # members shown as columns (clamped to fit)
        self.selected = []                   # [(unit, loc), ...]: loc is "hand"|"offhand"|"armor"|pack index
        self.menu = None                     # send-to menu: {pos, w, h, rh, rows:[(kind, arg)], picks} (+ rect/hits once drawn)
        self.notice = None                   # last chest-opening result, shown in the footer
        self.zones = []                     # [(rect, unit|None, "hand"|"offhand"|"armor"|"pack"|"discard")]
        self.sources = []                  # [(rect, unit, loc)]
        self.tab_hits = []              # [(rect, unit)]
        self.buttons = []                  # [(key, rect)]
        self._cap = len(self.managed)
        self._hot = False         # columns that fit (recomputed each frame)

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
        if getattr(self, "editing_name", False) and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.group.name = self.name_buf.strip() or None
                self.editing_name = False
            elif event.key == pygame.K_ESCAPE:
                self.editing_name = False
            elif event.key == pygame.K_BACKSPACE:
                self.name_buf = self.name_buf[:-1]
            elif event.unicode and len(self.name_buf) < 24 and event.unicode.isprintable():
                self.name_buf += event.unicode
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.menu:
            self._menu_click(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.close_sheet_on_click():
                return
            for rect, unit in getattr(self, "sheet_hits", []):
                if rect.collidepoint(event.pos):
                    self.open_sheet(unit)
                    return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._open_menu(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.menu = None
        super().handle_event(event)

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

        for rect, tab in self.tab_hits:
            if rect.collidepoint(px):
                self.tab, self.selected = tab, []
                return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "done" or key == "back":
                    self.on_back()
                elif key == "distribute":
                    self.group.distribute_load()
                    self.notice = "Redistributed packs by carrying capacity."
                elif key == "rename":
                    self.editing_name = True
                    self.name_buf = self.group.name or ""
                return
        if not self.selected:
            pass

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

        f = self.fonts
        w = 160
        for kind, arg in rows:
            lbl = ("OPEN THE CHEST" if kind == "open" else
                   f"to {arg.name}" if kind == "member" else "throw away")
            w = max(w, f.body.size(lbl)[0] + 2 * SP4)
        self.menu = {"pos": px, "w": w, "h": MENU_HEAD + len(rows) * 24 + SP1,
                     "rh": 24, "rows": rows, "picks": list(picks)}

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
            lbl = ("OPEN THE CHEST" if kind == "open" else
                   f"to {arg.name}" if kind == "member" else "throw away")
            col = DANGER if kind == "discard" else ACCENT if hov else INK
            text(screen, lbl, f.body, col, (r.x + SP2, r.centery - 7))
            m["hits"].append((r, kind, arg))
            iy += m["rh"]

    # ------------------------------------------------------------------ #


    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        screen.fill(SURFACE_0)
        self.zones = []
        self.sources = []
        self.tab_hits = []
        self.sheet_hits = []
        self._pack_areas = []
        self._lock_hits = []
        self._reset_buttons()

        pad = MARGIN if W < 1500 else SP5
        top = pad + 62
        bottom = H - 56

        # --- header & tabs -------------------------------------------- #
        name = self.group.display_name
        text(screen, name, f.title, INK, (pad, pad - 2))
        nw = f.title.size(name)[0]
        
        sub_text = f"  ·  {len(self.group.members)} / {self.group.capacity} members"
        if self.group.overextension > 0:
            sub_text += f" (OVEREXTENDED: -{self.group.overextension} Mental Defense)"
        text(screen, sub_text, f.body_bd, DANGER if self.group.overextension > 0 else INK_DIM, (pad + nw + 40, pad + 4))
        text(screen, "Manage group gear, loadout and quests", f.body_sm, INK_FAINT, (pad, pad + 26))

        r = pygame.Rect(pad + nw + SP2, pad + 10, 24, 24)
        hov = r.collidepoint(self.mouse)
        if hov:
            self._hot = True
            panel(screen, r, fill=SURFACE_3, border=LINE_SOFT, radius=4)
        text(screen, "✎", f.body, ACCENT if hov else INK_DIM, r.center, center=True)
        self.buttons.append(("rename", r))

        if getattr(self, "editing_name", False):
            er = pygame.Rect(pad, pad - 4, max(200, nw + 50), 32)
            panel(screen, er, fill=SURFACE_1, border=ACCENT, width=2, radius=4)
            text(screen, self.name_buf + "·", f.title, INK, (pad + SP2, pad - 2))
        
        tx = pad
        ty = pad + 48
        for tab_id, label in (("gear", "GEAR"), ("quests", "QUESTS")):
            active = self.tab == tab_id
            tr = pygame.Rect(tx, ty, f.body.size(label)[0] + 2 * SP2, 22)
            hov = tr.collidepoint(self.mouse)
            if hov:
                self._hot = True
            col = ACCENT if active else INK if hov else INK_DIM
            text(screen, label, f.body, col, tr.center, center=True)
            if active:
                pygame.draw.line(screen, ACCENT, tr.bottomleft, tr.bottomright, 2)
            self.tab_hits.append((tr, tab_id))
            tx += tr.w + SP4
            
        area = pygame.Rect(pad, top, W - 2 * pad, bottom - top)

        if self.tab == "gear":
            self._draw_gear(screen, area)
        else:
            self._draw_quests(screen, area)
            
        if self._dragging and self.tab == "gear":
            carried = self._carried_names()
            if carried:
                gx, gy = self.mouse
                label = carried[0] if len(carried) == 1 else f"{len(carried)} items"
                gr = pygame.Rect(gx + 12, gy + 6, f.body_sm.size(label)[0] + 2 * SP2, 20)
                panel(screen, gr, fill=ACCENT, border=ACCENT_INK, width=1, radius=4)
                text(screen, label, f.body_sm, ACCENT_INK, gr.center, center=True)
                
        if self.menu:
            self._draw_menu(screen, W, H)

        footer_bar(self, screen,
                  secondary=("distribute", "DISTRIBUTE LOAD") if self.tab == "gear" else None,
                  primary=("done", "DONE"), notice=self.notice, notice_color=OK, margin=pad)

        self.draw_sheet_modal(screen, f)
        set_pointer("hand" if self._hot else "arrow")

    def _draw_gear(self, screen, area):
        f = self.fonts
        carried = self._carried_names()

        cols_area = area.w
        self._cap = max(1, (cols_area + SP3) // (COL_MIN + SP3))
        ctop = area.y

        shown = self.managed[:self._cap]
        n = max(1, len(shown))
        col_w = min(COL_MAX, (cols_area - (n - 1) * SP3) // n)
        for i, unit in enumerate(shown):
            r = pygame.Rect(area.x + i * (col_w + SP3), ctop, col_w, area.h)
            self._draw_column(screen, r, unit, carried)

        if len(self.managed) > self._cap:
            text(screen, f"+{len(self.managed) - self._cap} selected but hidden — "
                 "widen the window", f.label, INK_FAINT,
                 (area.x, area.bottom + 4))

    def _draw_quests(self, screen, area):
        f = self.fonts
        uids = {u.uid for u in self.group.members}
        active = [m for m in self.guild.missions if m.state == "active" and m.unit_uid in uids]
        
        y = area.y
        if not active:
            text(screen, "No active quests for this group.", f.body, INK_DIM, area.center, center=True)
            return

        for m in active:
            t = missions.template_of(m)
            r = pygame.Rect(area.x, y, min(600, area.w), 80)
            panel(screen, r, fill=SURFACE_1, border=LINE_SOFT, radius=8)
            
            text(screen, t.name, f.title, INK, (r.x + SP3, r.y + SP2))
            
            unit = next((u for u in self.group.members if u.uid == m.unit_uid), None)
            uname = unit.name if unit else "Unknown"
            text(screen, f"Accepted by {uname}", f.body_sm, INK_FAINT, (r.x + SP3, r.y + 32))
            
            days_left = m.deadline_day - self.guild.clock.day
            dcol = DANGER if days_left <= 1 else WARN if days_left <= 3 else OK
            text(screen, f"{max(0, days_left)} day(s) left", f.body, dcol, (r.right - SP3, r.y + SP2), right=True)
            
            if t.goal_qty > 0:
                prog = missions.progress(self.guild, m)
                text(screen, f"{prog} / {t.goal_qty} {t.goal_item}", f.mono, 
                     OK if prog >= t.goal_qty else INK, (r.right - SP3, r.y + 32), right=True)
            else:
                text(screen, "Delivery", f.mono, INK, (r.right - SP3, r.y + 32), right=True)
                 
            y += r.h + SP3


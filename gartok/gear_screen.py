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

from . import data
from .dragselect import DragSelectMixin, LoadoutMoveMixin
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SP4, SP5,
                    SURFACE_0, SURFACE_1, SURFACE_2, SURFACE_3, SURFACE_4, WARN,
                    ellipsize, kg, panel, section, set_pointer, text,
                    token_badge)

COL_MIN, COL_MAX = 288, 380              # loadout column width clamps
MENU_HEAD = 22                           # send-to menu: header strip above the rows


class GearScreen(DragSelectMixin, LoadoutMoveMixin, Screen):
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
        self.zones = []                     # [(rect, unit|None, "hand"|"offhand"|"armor"|"pack"|"discard")]
        self.sources = []                  # [(rect, unit, loc)]
        self.toggle_hits = []              # [(rect, unit)]
        self.buttons = []                  # [(key, rect)]
        self._cap = len(self.roster)         # columns that fit (recomputed each frame)
        self._hot = False

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
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

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "back":
                    self.on_back()
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

        f = self.fonts
        w = 160
        for kind, arg in rows:
            lbl = f"to {arg.name}" if kind == "member" else "throw away"
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
                self.selected = list(m["picks"])
                self._give_many(arg, "pack" if kind == "member" else "discard")
                return

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
            lbl = f"to {arg.name}" if kind == "member" else "throw away"
            col = DANGER if kind == "discard" else ACCENT if hov else INK
            text(screen, lbl, f.body, col, (r.x + SP2, r.centery - 7))
            m["hits"].append((r, kind, arg))
            iy += m["rh"]

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        screen.fill(SURFACE_0)
        self.zones = []
        self.sources = []
        self.toggle_hits = []
        self.buttons = []
        self._hot = False

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
            lbl = ellipsize(unit.name, f.body_sm, 150)
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
    def _slot(self, screen, r, *, sel, accepts, drop):
        panel(screen, r,
              fill=ACCENT if sel else SURFACE_3 if (drop or accepts) else SURFACE_1,
              border=ACCENT if (sel or drop) else INFO if accepts else LINE_SOFT,
              width=1, radius=4)

    def _draw_column(self, screen, rect, unit, carried):
        f = self.fonts
        mouse = self.mouse
        pad = SP3
        x = rect.x + pad
        inner = rect.w - 2 * pad

        # The whole column is a pack drop target; the hand / off / armour slots
        # below register their own zones first, so those still win on a hit.
        pack_drop = bool(carried) and rect.collidepoint(mouse)
        panel(screen, rect, fill=SURFACE_2,
              border=INFO if pack_drop else LINE_SOFT,
              width=2 if pack_drop else 1, radius=RADIUS)

        # --- header ------------------------------------------------- #
        head = pygame.Rect(rect.x, rect.y, rect.w, 52)
        pygame.draw.line(screen, LINE_SOFT, (rect.x, head.bottom),
                         (rect.right - 1, head.bottom))
        token_badge(screen, (rect.x + pad + 13, rect.y + 20), unit, f, r=13)
        nx = rect.x + pad + 32
        text(screen, ellipsize(unit.name, f.card_name, rect.right - nx - pad),
             f.card_name, INK, (nx, rect.y + 6))
        text(screen, ellipsize(f"{unit.race['name']}  ·  {unit.occupation['name']}",
                               f.body_sm, rect.right - nx - pad),
             f.body_sm, INK_FAINT, (nx, rect.y + 27))

        y = head.bottom + SP3

        # --- load bar ---------------------------------------------- #
        over_norm = unit.load > unit.carry_normal
        over_max = unit.load > unit.carry_max
        ccol = DANGER if over_max else WARN if over_norm else OK
        bar = pygame.Rect(x, y, inner, 10)
        panel(screen, bar, fill=SURFACE_1, border=LINE_SOFT, width=1, radius=4)
        span = bar.w - 2
        cap = max(1, unit.carry_max)
        fillw = int(span * min(1.0, unit.load / cap))
        if fillw > 0:
            pygame.draw.rect(screen, ccol, (bar.x + 1, bar.y + 1, fillw, bar.h - 2),
                             border_radius=3)
        mkx = bar.x + 1 + int(span * min(1.0, unit.carry_normal / cap))
        pygame.draw.line(screen, INK, (mkx, bar.y - 3), (mkx, bar.bottom + 3))
        y += 15
        text(screen, f"{kg(unit.load)}  ·  normal {kg(unit.carry_normal)}",
             f.mono_sm, ccol if (over_norm or over_max) else INK_DIM, (x, y))
        y += 16
        note = ("OVER HIGH LOAD  ·  -2 STR/DEX, -1 speed" if over_max
                else "overloaded  ·  -2 STR/DEX, -1 speed" if over_norm else "")
        if note:
            text(screen, note, f.label, ccol, (x, y))
            y += 15
        y += SP1

        two_handed = bool(unit.equipped_weapon) and \
            data.WEAPONS[unit.equipped_weapon]["hands"] >= 2

        # --- hands ------------------------------------------------- #
        y = section(screen, "HANDS", x, y, inner, f)
        for kind in ("hand", "offhand"):
            hr = pygame.Rect(x, y, inner, 32)
            held = unit.equipped_weapon if kind == "hand" else unit.equipped_offhand
            blocked = kind == "offhand" and two_handed
            sel = (unit, kind) in self.selected
            accepts = bool(carried) and not blocked and (
                (kind == "hand" and any(unit.is_weapon(n) for n in carried))
                or (kind == "offhand" and any(unit.fits_offhand(n) for n in carried)))
            drop = accepts and not sel and hr.collidepoint(mouse)
            self._slot(screen, hr, sel=sel, accepts=accepts, drop=drop)
            ink = ACCENT_INK if sel else INK
            if held:
                right = kg(data.item_weight(held))
                if kind == "hand":
                    dn, faces = data.WEAPONS[held]["damage"]
                    hit, _src = unit.attack_bonus
                    right = f"{hit:+}  ·  {dn}d{faces}  ·  " + right
                text(screen, ellipsize(held, f.body, inner - f.mono_sm.size(right)[0] - SP4),
                     f.body, ink, (hr.x + SP2, hr.y + 8))
                text(screen, right, f.mono_sm, ACCENT_INK if sel else INK_DIM,
                     (hr.right - SP2, hr.y + 9), right=True)
                self.sources.append((hr, unit, kind))
            elif blocked:
                text(screen, "off hand  ·  2-handed weapon", f.body_sm, INK_FAINT,
                     (hr.x + SP2, hr.y + 8))
            else:
                empty = "weapon: none" if kind == "hand" else "off hand: free"
                text(screen, empty, f.body_sm, ACCENT if drop else INK_FAINT,
                     (hr.x + SP2, hr.y + 8))
            if not blocked:
                self.zones.append((hr, unit, kind))
            y += 32 + SP1
        y += SP1

        # --- body ------------------------------------------------- #
        y = section(screen, "BODY", x, y, inner, f)
        ar = pygame.Rect(x, y, inner, 32)
        worn = unit.equipped_armor
        asel = (unit, "armor") in self.selected
        afit = bool(carried) and any(unit.fits_armor(n) for n in carried)
        adrop = afit and not asel and ar.collidepoint(mouse)
        self._slot(screen, ar, sel=asel, accepts=afit, drop=adrop)
        if worn:
            armor = data.ARMOR[worn]
            text(screen, ellipsize(worn, f.body, inner - 90), f.body,
                 ACCENT_INK if asel else INK, (ar.x + SP2, ar.y + 8))
            text(screen, f"+{armor['ac']} AC  ·  {kg(data.item_weight(worn))}",
                 f.mono_sm, ACCENT_INK if asel else INK_DIM, (ar.right - SP2, ar.y + 9),
                 right=True)
            self.sources.append((ar, unit, "armor"))
        else:
            text(screen, "body: no armor", f.body_sm, ACCENT if adrop else INK_FAINT,
                 (ar.x + SP2, ar.y + 8))
        self.zones.append((ar, unit, "armor"))
        y += 32 + SP2

        # --- pack ------------------------------------------------- #
        y = section(screen, f"PACK  ({len(unit._base_inventory)})", x, y, inner, f)
        if not unit._base_inventory:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (x, y + 2))
            y += 22
        for idx, item in enumerate(unit._base_inventory):
            ir = pygame.Rect(x, y, inner, 28)
            if ir.bottom > rect.bottom - pad:
                text(screen, f"+{len(unit._base_inventory) - idx} more", f.label,
                     INK_FAINT, (x, y + 4))
                break
            isel = (unit, idx) in self.selected
            ihov = not carried and ir.collidepoint(mouse)
            panel(screen, ir, fill=ACCENT if isel else SURFACE_3 if ihov else SURFACE_1,
                  border=ACCENT if isel else LINE_SOFT, width=1, radius=4)
            tag = self._item_tag(item)
            wtxt = kg(data.item_weight(item))
            rtxt = (tag + "  ·  " + wtxt) if tag else wtxt
            text(screen, ellipsize(item, f.body, inner - f.mono_sm.size(rtxt)[0] - SP4),
                 f.body, ACCENT_INK if isel else INK, (ir.x + SP2, ir.y + 6))
            text(screen, rtxt, f.mono_sm, ACCENT_INK if isel else INK_DIM,
                 (ir.right - SP2, ir.y + 7), right=True)
            self.sources.append((ir, unit, idx))
            y += 28 + SP1

        self.zones.append((rect, unit, "pack"))

    def _item_tag(self, item):
        if item in data.WEAPONS:
            return "WEAPON"
        if item in data.ARMOR:
            return "ARMOR"
        if item == data.AMMO_ITEM:
            return "AMMO"
        if item == data.FIRST_AID_ITEM:
            return "HEAL"
        if item == data.TORCH_ITEM or item in data.LIGHT_SOURCES:
            return "LIGHT"
        if item in data.FOOD_ITEMS:
            return "FOOD"
        return ""

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen, W, H, pad):
        f = self.fonts
        mouse = self.mouse
        y = H - 44

        if self._carried_names():
            trash = pygame.Rect(0, 0, 220, 32)
            trash.center = (W // 2, y + 14)
            over = trash.collidepoint(mouse)
            panel(screen, trash, fill=DANGER if over else SURFACE_2, border=DANGER,
                  width=1, radius=RADIUS)
            text(screen, "THROW AWAY", f.body_bd, ACCENT_INK if over else DANGER,
                 trash.center, center=True)
            self.zones.append((trash, None, "discard"))

        back = pygame.Rect(W - pad - 200, y, 200, 32)
        hov = back.collidepoint(mouse)
        self._hot = self._hot or hov
        panel(screen, back, fill=ACCENT if hov else SURFACE_3, border=ACCENT,
              width=1, radius=RADIUS)
        text(screen, "BACK TO GUILD", f.body_bd, ACCENT_INK if hov else ACCENT,
             back.center, center=True)
        self.buttons.append(("back", back))

        text(screen, "Esc for the pause menu", f.label, INK_FAINT, (pad, y + 10))

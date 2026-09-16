"""Shared loadout column for the gear and group management screens.

`gear_screen.GearScreen` and `group_screen.GroupScreen` show the exact same
per-member column -- header, load bar, HANDS/OFF/(TONGUE), BODY, PACK -- side
by side; only the header's info-sheet badge differs. `PackColumnMixin` owns
that column so the padlock (exempt an item from `unit.distribute_load`) and
the pack scroll (items past the fold used to be unreachable, shown as a dead
"+N more" line) are implemented once for both screens instead of twice.

Mix in before `Screen`, same convention as `dragselect.DragSelectMixin`:
``class GearScreen(DragSelectMixin, LoadoutMoveMixin, PackColumnMixin, Screen)``

Needs from the host screen: `self.fonts`, `self.mouse`, `self.selected`,
`self.zones`, `self.sources`; the mixin owns `self._pack_scroll` /
`self._pack_areas` / `self._lock_hits` and adds wheel scrolling to
`handle_event`. Screens reset `self._lock_hits = []` and `self._pack_areas = []`
at the top of `draw()` alongside their other per-frame lists, and route a click
through `self._lock_at(px)` before treating it as an item pick (see
`GearScreen._source_at`/`_drop`).
"""

import pygame

from . import data, icons
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, OK, RADIUS, SP1, SP2, SP3, SP4, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, ellipsize, kg, panel, section,
                    text, token_badge)

LOCK_W = 18                          # padlock hit-box width, left of the item name


class PackColumnMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pack_scroll = {}       # id(unit) -> pack rows scrolled past
        self._pack_areas = []        # [(rect, unit)] -- wheel hit-testing
        self._lock_hits = []         # [(rect, unit, item_name)]

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            hit = next((u for r, u in self._pack_areas if r.collidepoint(self.mouse)), None)
            if hit is not None:
                cur = self._pack_scroll.get(id(hit), 0)
                cap = max(0, len(hit._base_inventory) - 1)
                self._pack_scroll[id(hit)] = max(0, min(cap, cur - event.y))
                return
        super().handle_event(event)

    def _lock_at(self, px):
        for r, unit, name in getattr(self, "_lock_hits", []):
            if r.collidepoint(px):
                return (unit, name)
        return None

    @staticmethod
    def _item_tag(item):
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
        if item == data.CHEST_ITEM:
            return "CHEST"
        if item == data.MISSION_CHEST_ITEM:
            return "SEALED"
        return ""

    def _column_header_edge(self, screen, rect, unit, pad):
        """Right edge the header name/info must not run past -- overridden by
        a screen that draws its own badge there (see GroupScreen)."""
        return rect.right - pad

    @staticmethod
    def _slot(screen, r, *, sel, accepts, drop):
        panel(screen, r,
              fill=ACCENT if sel else SURFACE_3 if (drop or accepts) else SURFACE_1,
              border=ACCENT if (sel or drop) else INFO if accepts else LINE_SOFT,
              width=1, radius=4)

    # ------------------------------------------------------------------ #
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

        edge = self._column_header_edge(screen, rect, unit, pad)
        nx = rect.x + pad + 32
        text(screen, ellipsize(unit.full_name, f.card_name, edge - nx - pad),
             f.card_name, INK, (nx, rect.y + 6))

        info = f"{unit.race['name']}  ·  {unit.occupation['name']}"
        if getattr(unit, 'recipes', None):
            info += f"  ·  {len(unit.recipes)} recipes"
        text(screen, ellipsize(info, f.body_sm, edge - nx - pad),
             f.body_sm, INK_FAINT, (nx, rect.y + 27))

        y = head.bottom + SP3

        # --- load bar ---------------------------------------------- #
        over_norm = unit.encumbered
        over_max = unit.load > unit.carry_max
        ccol = DANGER if over_max else WARN if over_norm else OK
        carrier = f"  (carrier +{unit.carry_relief:g})" if unit.carry_relief else ""
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
        text(screen, f"{kg(unit.load)}  ·  normal {kg(unit.carry_normal)}{carrier}",
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

        # --- hands (+ the Grippli Tongue, when it has one) --------- #
        y = section(screen, "HANDS", x, y, inner, f)
        slots = ["hand", "offhand"] + (["tongue"] if unit.has_tongue else [])
        for kind in slots:
            hr = pygame.Rect(x, y, inner, 32)
            held = {"hand": unit.equipped_weapon, "offhand": unit.equipped_offhand,
                    "tongue": unit.equipped_tongue}[kind]
            blocked = kind == "offhand" and two_handed
            sel = (unit, kind) in self.selected
            fits = {"hand": unit.is_weapon, "offhand": unit.fits_offhand,
                    "tongue": unit.fits_tongue}[kind]
            accepts = bool(carried) and not blocked and any(fits(n) for n in carried)
            drop = accepts and not sel and hr.collidepoint(mouse)
            self._slot(screen, hr, sel=sel, accepts=accepts, drop=drop)
            ink = ACCENT_INK if sel else INK
            if held:
                right = kg(data.item_weight(held))
                if kind == "hand":
                    dn, faces = data.WEAPONS[held]["damage"]
                    hit, _src = unit.attack_bonus
                    right = f"{hit:+}  ·  {dn}d{faces}  ·  " + right
                elif kind == "tongue":
                    dn, faces = data.WEAPONS[held]["damage"]
                    right = f"{dn}d{faces}  ·  reach {unit.tongue_reach}  ·  " + right
                text(screen, ellipsize(held, f.body, inner - f.mono_sm.size(right)[0] - SP4),
                     f.body, ink, (hr.x + SP2, hr.y + 8))
                text(screen, right, f.mono_sm, ACCENT_INK if sel else INK_DIM,
                     (hr.right - SP2, hr.y + 9), right=True)
                self.sources.append((hr, unit, kind))
            elif blocked:
                text(screen, "off hand  ·  2-handed weapon", f.body_sm, INK_FAINT,
                     (hr.x + SP2, hr.y + 8))
            else:
                empty = {"hand": "weapon: none", "offhand": "off hand: free",
                         "tongue": "tongue: free  ·  1-handed weapon, +1 reach"}[kind]
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

        self._draw_pack_rows(screen, rect, x, y, inner, unit, carried)

    # ------------------------------------------------------------------ #
    def _draw_pack_rows(self, screen, rect, x, y, inner, unit, carried):
        """One row per physical pack item (not stacked -- each index is its own
        drag/select pick, same as before), scrolled to fit the column, with a
        padlock toggle in front of each row. The lock is tracked per item name
        (`Unit.locked_of`/`toggle_lock`): whichever physical copy shows locked
        is arbitrary among identical items, but the count always matches."""
        f = self.fonts
        mouse = self.mouse
        items = unit._base_inventory
        y = section(screen, f"PACK  ({len(items)})", x, y, inner, f)
        if not items:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (x, y + 2))
            return

        row_h = 28 + SP1
        max_bottom = rect.bottom - SP3
        area = pygame.Rect(x, y, inner, max(0, max_bottom - y))
        self._pack_areas.append((area, unit))
        visible_n = max(1, (max_bottom - y) // row_h)
        scroll = max(0, min(self._pack_scroll.get(id(unit), 0),
                            max(0, len(items) - visible_n)))
        self._pack_scroll[id(unit)] = scroll

        if scroll:
            text(screen, f"^ {scroll} more above", f.label, INK_FAINT, (x, y + 2))
            y += 14

        seen = {}
        for name in items[:scroll]:
            seen[name] = seen.get(name, 0) + 1

        shown_end = min(len(items), scroll + visible_n)
        for idx in range(scroll, shown_end):
            item = items[idx]
            seen[item] = seen.get(item, 0) + 1
            locked = seen[item] <= unit.locked_of(item)

            ir = pygame.Rect(x, y, inner, 28)
            isel = (unit, idx) in self.selected
            ihov = not carried and ir.collidepoint(mouse)
            panel(screen, ir, fill=ACCENT if isel else SURFACE_3 if ihov else SURFACE_1,
                  border=ACCENT if isel else LINE_SOFT, width=1, radius=4)

            lr = pygame.Rect(ir.x + 2, ir.y + 5, LOCK_W, 18)
            lhov = lr.collidepoint(mouse)
            icons.icon(screen, "lock" if locked else "unlock", lr,
                       ACCENT if locked else (INK if lhov else INK_FAINT))
            self._lock_hits.append((lr, unit, item))

            tag = self._item_tag(item)
            wtxt = kg(data.item_weight(item))
            rtxt = (tag + "  ·  " + wtxt) if tag else wtxt
            name_x = ir.x + LOCK_W + SP1
            text(screen, ellipsize(item, f.body, ir.right - name_x - f.mono_sm.size(rtxt)[0] - SP4),
                 f.body, ACCENT_INK if isel else INK, (name_x, ir.y + 6))
            text(screen, rtxt, f.mono_sm, ACCENT_INK if isel else INK_DIM,
                 (ir.right - SP2, ir.y + 7), right=True)
            self.sources.append((ir, unit, idx))
            y += row_h

        more_below = len(items) - shown_end
        if more_below > 0:
            text(screen, f"v {more_below} more below", f.label, INK_FAINT, (x, y + 2))

        self.zones.append((rect, unit, "pack"))

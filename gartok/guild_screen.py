"""Guild screen: the roster-and-gear view between outings.

Master-detail: a column of member cards on the left picks who you are looking
at; a wide panel on the right lays that member's loadout out with room to
breathe -- stat chips, a carry bar, and the HANDS / BODY / PACK slots.

A weapon is an item: it can sit in a member's pack or be held in a hand. Each
doll has two hand slots -- the weapon hand (a weapon, 1 or 2 handed) and the off
hand (a torch, for now) -- plus a body slot for armor. Move items by:

- **drag** an item onto a HAND / OFF HAND / BODY / PACK slot, onto another
  MEMBER in the list (drops into their pack), or onto THROW AWAY, or
- **click** it to pick it up and click the destination (click it again, or click
  away, to put it back), and
- **shift/ctrl-click** to carry several pack items at once (a multi-drop onto a
  hand/armor slot takes the first that fits and keeps the rest).

The transfer edits the persistent `equipped_weapon` / `equipped_offhand` /
`equipped_armor` / `_base_inventory`, which every battle re-seeds a `Combatant`
from -- so the next fight starts with the new loadout. `Unit.load` / `.ac` / ...
read straight off that loadout, so the cards stay truthful with no extra
bookkeeping; the full-sheet modal wraps the member in a throwaway `Combatant`.

This screen renders at the real window resolution (`native = True`): `app` hands
`draw` the window surface and un-scaled mouse coords, so the layout can use the
whole maximized screen. Reached from the map (opening it passes no time).
`on_back()` returns to the map; `on_menu()` to the slot menu.
"""

import pygame

from . import data, world
from .combatant import Combatant
from .dragselect import DragSelectMixin
from .screen import Screen
from .sheet_panel import PANEL_H, PANEL_W, draw_sheet
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SP4, SP5,
                    SURFACE_0, SURFACE_1, SURFACE_2, SURFACE_3, WARN,
                    panel, section, token_badge, text, tracked)


TABS = (("members", "MEMBERS"), ("reputations", "REPUTATIONS"))

LIST_MIN, LIST_MAX = 264, 380         # roster column width clamps
DET_MAX = 1120                        # detail panel width cap on very wide screens


def _kg(w):
    return f"{w:g} kg"


def _fit(s, font, max_px):
    """`s` clipped with an ellipsis so it fits `max_px`."""
    if max_px <= 0 or font.size(s)[0] <= max_px:
        return s
    while s and font.size(s + "…")[0] > max_px:
        s = s[:-1]
    return s + "…"


class GuildScreen(DragSelectMixin, Screen):
    native = True                        # app draws us straight to the window

    def __init__(self, fonts, guild, on_back, on_menu):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.roster = guild.roster
        self.battles_won = guild.battles_won
        self.on_back = on_back
        self.on_menu = on_menu
        self.tab = "members"                  # "members" (roster+gear) | "reputations"
        self.member = self.roster[0] if self.roster else None   # card shown on the right
        self.tab_hits = []                  # [(rect, key)]
        self.member_hits = []              # [(rect, unit)] -- list cards select the member
        self.selected = []                   # [(unit, loc), ...]: loc is "hand"|"offhand"|"armor"|pack index
        self.detail = None                   # unit whose full sheet is open (modal), or None
        self.zones = []                     # [(rect, unit, "hand"|"offhand"|"armor"|"pack"|"discard")]
        self.sources = []                  # [(rect, unit, loc)]
        self.info_hits = []                # [(rect, unit)] -- the detail header opens the sheet
        self.buttons = []                  # [(key, rect)]

    # ------------------------------------------------------------------ #
    def _recruited_by(self, unit):
        """Name of the member who recruited `unit`, or None (draft member, or the
        recruiter has since been lost)."""
        if not getattr(unit, "recruited_by", None):
            return None
        who = next((u for u in self.roster if u.uid == unit.recruited_by), None)
        return who.name if who else "someone long gone"

    @staticmethod
    def _slot_of(loc):
        return loc if isinstance(loc, str) else "pack"

    def _item_at(self, unit, loc):
        if loc == "hand":
            return unit.equipped_weapon
        if loc == "offhand":
            return unit.equipped_offhand
        if loc == "armor":
            return unit.equipped_armor
        return unit._base_inventory[loc] if loc < len(unit._base_inventory) else None

    def _carried_names(self):
        """Names of the items currently picked up (selected / being dragged)."""
        out = []
        for unit, loc in self.selected:
            name = self._item_at(unit, loc)
            if name is not None:
                out.append(name)
        return out

    # ------------------------------------------------------------------ #
    # input: click to (multi-)select, or drag an item onto a slot        #
    # (the press/drag machinery lives in DragSelectMixin)                #
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

    def _drop(self, px, dragging, src):
        if self.detail is not None:            # sheet modal: any click closes it
            self.detail = None
            return

        if dragging:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                (self.on_back if key == "back" else self.on_menu)()
                return
        for rect, key in self.tab_hits:
            if rect.collidepoint(px):
                self.tab, self.selected = key, []
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

        for rect, unit in self.member_hits:
            if rect.collidepoint(px):
                self.member, self.selected = unit, []
                return
        for rect, unit in self.info_hits:
            if rect.collidepoint(px):
                self.detail = unit
                return
        self.selected = [src] if src is not None else []

    # ------------------------------------------------------------------ #
    def _take(self, src, loc):
        if loc == "hand":
            return src.take_from_hand()
        if loc == "offhand":
            return src.take_from_offhand()
        if loc == "armor":
            return src.take_from_armor()
        return src.take_from_pack(loc)

    @staticmethod
    def _fits_slot(dst, zone, name):
        if zone == "hand":
            return dst.is_weapon(name)
        if zone == "offhand":
            return dst.fits_offhand(name)
        if zone == "armor":
            return dst.fits_armor(name)
        return True                                      # pack / discard take anything

    def _give_many(self, dst, zone):
        picks = [p for p in self.selected if self._item_at(*p) is not None]
        self.selected = []
        if not picks:
            return

        if zone == "discard":
            _, touched = self._collect(picks)
            for u in touched:
                u._derive_combat()
            return

        if zone in ("hand", "offhand", "armor"):
            fit = next((p for p in picks
                        if self._fits_slot(dst, zone, self._item_at(*p))
                        and not (p[0] is dst and self._slot_of(p[1]) == zone)), None)
            if fit is None:
                self.selected = picks                    # nothing fits: keep carrying
                return
            name = self._item_at(*fit)
            src = fit[0]
            self._take(*fit)
            {"hand": dst.give_to_hand, "offhand": dst.give_to_offhand,
             "armor": dst.give_to_armor}[zone](name)
            src._derive_combat()
            dst._derive_combat()
            return

        # pack
        if all(p[0] is dst and not isinstance(p[1], str) for p in picks):
            return                                       # same pack: nothing to do
        names, touched = self._collect(picks)
        for name in names:
            dst.give_to_pack(name)
        for u in touched:
            u._derive_combat()
        dst._derive_combat()

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        screen.fill(SURFACE_0)
        self.zones = []
        self.sources = []
        self.info_hits = []
        self.buttons = []
        self.member_hits = []
        self.tab_hits = []

        if self.member not in self.roster:
            self.member = self.roster[0] if self.roster else None

        pad = MARGIN if W < 1500 else SP5
        text(screen, "GUILD", f.title, INK, (pad, pad - 2))
        carried = self._carried_names()
        if carried:
            if len(carried) == 1:
                lead = f"moving  {carried[0]} ({_kg(data.item_weight(carried[0]))})"
            else:
                tot = sum(data.item_weight(n) for n in carried)
                lead = f"moving  {len(carried)} items ({_kg(tot)})"
            sub, col = (lead + "  ·  drop on a HAND, BODY, PACK, a MEMBER in the "
                        "list or on THROW AWAY  ·  click outside to cancel", ACCENT)
        else:
            sub, col = (f"{self.battles_won} wins  ·  {len(self.roster)} members  ·  "
                        "drag an item (or click)  ·  shift+click gathers several", INK_DIM)
        text(screen, _fit(sub, f.body, W - 2 * pad), f.body, col, (pad, pad + 30))

        if not carried:
            self._draw_tabs(screen, W, pad)

        top = pad + 62
        bottom = H - 64
        if not carried and self.tab == "reputations":
            self._draw_reputacoes(screen, W, top, pad)
        else:
            list_w = int(min(max(W * 0.24, LIST_MIN), LIST_MAX))
            det_w = min(DET_MAX, W - 2 * pad - list_w - SP4)
            packn = len(self.member._base_inventory) if self.member else 0
            det_h = max(400, min(bottom - top,
                                 340 + max(1, packn) * 34 + (34 if carried else 0)))
            list_rect = pygame.Rect(pad, top, list_w, bottom - top)
            det_rect = pygame.Rect(pad + list_w + SP4, top, det_w, det_h)
            self._draw_roster(screen, list_rect, carried)
            if self.member is not None:
                self._draw_detail(screen, det_rect, self.member, carried)

        self._draw_footer(screen, W, H, pad)

        if self._dragging and carried:
            gx, gy = self.mouse
            label = carried[0] if len(carried) == 1 else f"{len(carried)} items"
            gr = pygame.Rect(gx + 12, gy + 6, f.body_sm.size(label)[0] + 2 * SP2, 20)
            panel(screen, gr, fill=ACCENT, border=ACCENT_INK, width=1, radius=4)
            text(screen, label, f.body_sm, ACCENT_INK, gr.center, center=True)

        if self.detail is not None:
            r = pygame.Rect(0, 0, PANEL_W, PANEL_H)
            r.center = (W // 2, H // 2)
            draw_sheet(screen, r, Combatant(self.detail), f)

    # ------------------------------------------------------------------ #
    def _draw_roster(self, screen, rect, carried):
        """The left column: one compact card per member, the open one lit."""
        f = self.fonts
        n = max(1, len(self.roster))
        gap = SP2
        row_h = min(74, max(56, (rect.h - (n - 1) * gap) // n))
        mouse = self.mouse
        for i, unit in enumerate(self.roster):
            r = pygame.Rect(rect.x, rect.y + i * (row_h + gap), rect.w, row_h)
            if r.bottom > rect.bottom + 2:
                break
            sel = unit is self.member
            hov = r.collidepoint(mouse)
            drop = bool(carried) and not sel and hov
            panel(screen, r,
                  fill=SURFACE_3 if (sel or hov) else SURFACE_2,
                  border=ACCENT if sel else INFO if drop else LINE_SOFT,
                  width=2 if (sel or drop) else 1, radius=RADIUS)
            if sel:
                pygame.draw.rect(screen, ACCENT, (r.x, r.y + 4, 3, r.h - 8))

            tok = (r.x + SP3 + 12, r.y + 24)
            token_badge(screen, tok, unit.token, f)
            nx = tok[0] + 24
            text(screen, _fit(unit.name, f.card_name, r.right - nx - SP2),
                 f.card_name, INK if sel else INK_DIM if not hov else INK,
                 (nx, r.y + 6))
            text(screen, _fit(f"{unit.race['name']}  ·  {unit.occupation['name']}",
                              f.body_sm, r.right - nx - SP2),
                 f.body_sm, INK_FAINT, (nx, r.y + 27))

            over_norm = unit.load > unit.carry_normal
            over_max = unit.load > unit.carry_max
            ccol = DANGER if over_max else WARN if over_norm else INK_DIM
            text(screen, f"PV {unit.hp_max}   CA {unit.ac}   ·   {_kg(unit.load)}",
                 f.mono_sm, ccol, (r.x + SP3, r.bottom - 20))
            if unit.hunger_level:
                text(screen, "HUNGER", f.label,
                     DANGER if unit.hunger_level >= 2 else WARN,
                     (r.right - SP3, r.bottom - 19), right=True)

            self.member_hits.append((r, unit))
            if carried and not sel:
                self.zones.append((r, unit, "pack"))

    # ------------------------------------------------------------------ #
    def _chip(self, screen, r, label, val):
        f = self.fonts
        panel(screen, r, fill=SURFACE_1, border=LINE_SOFT, width=1, radius=4)
        text(screen, label, f.label, INFO, (r.centerx, r.y + 8), center=True)
        text(screen, str(val), f.num, INK, (r.centerx, r.y + 24), center=True)

    def _slot(self, screen, r, *, sel, accepts, drop):
        panel(screen, r,
              fill=ACCENT if sel else SURFACE_3 if (drop or accepts) else SURFACE_1,
              border=ACCENT if (sel or drop) else INFO if accepts else LINE_SOFT,
              width=1, radius=4)

    def _draw_detail(self, screen, rect, unit, carried):
        f = self.fonts
        mouse = self.mouse
        panel(screen, rect, fill=SURFACE_2, border=LINE_SOFT, width=2, radius=RADIUS)
        pad = SP4
        x = rect.x + pad
        inner = rect.w - 2 * pad

        # --- header ---------------------------------------------------- #
        head = pygame.Rect(rect.x, rect.y, rect.w, 60)
        head_hov = not carried and head.collidepoint(mouse)
        pygame.draw.rect(screen, SURFACE_3 if head_hov else SURFACE_2, head,
                         border_top_left_radius=RADIUS, border_top_right_radius=RADIUS)
        pygame.draw.line(screen, LINE_SOFT, (rect.x, head.bottom), (rect.right - 1, head.bottom))
        tok = (rect.x + pad + 15, rect.y + 30)
        token_badge(screen, tok, unit.token, f, r=16)
        nx = tok[0] + 28
        text(screen, unit.name, f.card_name, INK, (nx, rect.y + 10))
        origin = self._recruited_by(unit)
        sub = (f"{unit.race['name']}  ·  {unit.occupation['name']}"
               + (f"  ·  recruited by {origin}" if origin else ""))
        text(screen, _fit(sub, f.body_sm, rect.right - nx - 110), f.body_sm,
             INK_DIM, (nx, rect.y + 34))
        text(screen, "VIEW SHEET ›", f.label, ACCENT if head_hov else INK_FAINT,
             (rect.right - pad, rect.y + 12), right=True)
        if not carried:
            self.info_hits.append((head, unit))

        # Two inner columns under the header: the read-out (chips, carry, copper,
        # hunger) on the left, the gear slots -- the drop targets -- on the
        # wider right.
        top = head.bottom + SP4
        col_a = min(440, int(inner * 0.42))
        bx = x + col_a + SP5
        bw = rect.right - pad - bx

        # --- left column: stat chips ------------------------------- #
        a = top
        stats = (("PV", unit.hp_max), ("CA", unit.ac),
                 ("DM", unit.mental_defense), ("DESLOC", unit.speed))
        cw = (col_a - 3 * SP2) // 4
        for i, (lbl, val) in enumerate(stats):
            self._chip(screen, pygame.Rect(x + i * (cw + SP2), a, cw, 48), lbl, val)
        a += 48 + SP4

        # --- left column: carry bar ------------------------------- #
        over_norm = unit.load > unit.carry_normal
        over_max = unit.load > unit.carry_max
        ccol = DANGER if over_max else WARN if over_norm else OK
        tracked(screen, "LOAD", f.label, INFO, (x, a))
        a += 15
        bar = pygame.Rect(x, a, col_a, 12)
        panel(screen, bar, fill=SURFACE_1, border=LINE_SOFT, width=1, radius=4)
        span = bar.w - 2
        cap = max(1, unit.carry_max)
        fillw = int(span * min(1.0, unit.load / cap))
        if fillw > 0:
            pygame.draw.rect(screen, ccol, (bar.x + 1, bar.y + 1, fillw, bar.h - 2), border_radius=3)
        mkx = bar.x + 1 + int(span * min(1.0, unit.carry_normal / cap))
        pygame.draw.line(screen, INK, (mkx, bar.y - 3), (mkx, bar.bottom + 3))
        a += 18
        text(screen, f"{_kg(unit.load)}  ·  normal {_kg(unit.carry_normal)}  ·  "
             f"high {_kg(unit.carry_max)}", f.mono_sm, INK_DIM, (x, a))
        a += 15
        note = ("OVER HIGH LOAD  ·  -2 FOR/DES, -1 desloc" if over_max
                else "overloaded  ·  -2 FOR/DES, -1 desloc" if over_norm else "")
        if note:
            text(screen, note, f.label, ccol, (x, a))
        a += 18

        # --- left column: copper / xp / hunger -------------------- #
        xp = f"{unit.combat_xp} combat XP"
        if unit.work_xp:
            xp += f"   ·   {unit.work_xp} work XP"
        text(screen, f"{unit.gold} copper", f.mono_sm, ACCENT, (x, a))
        a += 16
        text(screen, xp, f.mono_sm, INFO, (x, a))
        a += 16
        rtag = f"  ·  {unit.rations} rations" if unit.rations else "  ·  no rations"
        if unit.ability.id == "autotroph":
            text(screen, "hunger: autotroph (doesn't eat)", f.mono_sm, INK_DIM, (x, a))
        elif unit.hunger_level:
            text(screen, f"hunger: {unit.hunger_label}  ({unit.unfed_days}d unfed){rtag}",
                 f.mono_sm, DANGER if unit.hunger_level >= 2 else WARN, (x, a))
        else:
            text(screen, f"hunger: fed{rtag}", f.mono_sm, OK, (x, a))

        # --- right column: hands --------------------------------- #
        x, inner = bx, bw
        y = section(screen, "HANDS", x, top, inner, f)
        two_handed = bool(unit.equipped_weapon) and \
            data.WEAPONS[unit.equipped_weapon]["hands"] >= 2
        for kind in ("hand", "offhand"):
            hr = pygame.Rect(x, y, inner, 34)
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
                right = ""
                if kind == "hand":
                    n, faces = data.WEAPONS[held]["damage"]
                    right = f"{n}d{faces}   ·   "
                text(screen, held, f.body, ink, (hr.x + SP3, hr.y + 9))
                text(screen, right + _kg(data.item_weight(held)), f.mono_sm,
                     ACCENT_INK if sel else INK_DIM, (hr.right - SP3, hr.y + 10), right=True)
                self.sources.append((hr, unit, kind))
            elif blocked:
                text(screen, "off hand  ·  taken by the 2-handed weapon", f.body_sm,
                     INK_FAINT, (hr.x + SP3, hr.y + 9))
            else:
                empty = ("weapon: none (fights unarmed)" if kind == "hand"
                         else "off hand: free")
                text(screen, empty, f.body_sm, ACCENT if drop else INK_FAINT,
                     (hr.x + SP3, hr.y + 9))

            if not blocked:
                self.zones.append((hr, unit, kind))
            y += 34 + SP2
        y += SP2

        # --- body: armor ----------------------------------------- #
        y = section(screen, "BODY", x, y, inner, f)
        ar = pygame.Rect(x, y, inner, 34)
        worn = unit.equipped_armor
        asel = (unit, "armor") in self.selected
        afit = bool(carried) and any(unit.fits_armor(n) for n in carried)
        adrop = afit and not asel and ar.collidepoint(mouse)
        self._slot(screen, ar, sel=asel, accepts=afit, drop=adrop)
        if worn:
            armor = data.ARMOR[worn]
            text(screen, worn, f.body, ACCENT_INK if asel else INK, (ar.x + SP3, ar.y + 9))
            text(screen, f"+{armor['ac']} CA   ·   {_kg(data.item_weight(worn))}",
                 f.mono_sm, ACCENT_INK if asel else INK_DIM, (ar.right - SP3, ar.y + 10),
                 right=True)
            self.sources.append((ar, unit, "armor"))
        else:
            text(screen, "body: no armor", f.body_sm,
                 ACCENT if adrop else INK_FAINT, (ar.x + SP3, ar.y + 9))
        self.zones.append((ar, unit, "armor"))
        y += 34 + SP4

        # --- pack ------------------------------------------------- #
        y = section(screen, "PACK", x, y, inner, f)
        if not unit._base_inventory:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (x, y + 2))
            y += 22
        for idx, item in enumerate(unit._base_inventory):
            ir = pygame.Rect(x, y, inner, 30)
            if ir.bottom > rect.bottom - SP4:
                text(screen, f"+{len(unit._base_inventory) - idx} items", f.label,
                     INK_FAINT, (x, y + 4))
                y += 20
                break
            isel = (unit, idx) in self.selected
            ihov = not carried and ir.collidepoint(mouse)
            panel(screen, ir, fill=ACCENT if isel else SURFACE_3 if ihov else SURFACE_1,
                  border=ACCENT if isel else LINE_SOFT, width=1, radius=4)
            ink = ACCENT_INK if isel else INK
            text(screen, item, f.body, ink, (ir.x + SP3, ir.y + 7))
            text(screen, _kg(data.item_weight(item)), f.mono_sm,
                 ACCENT_INK if isel else INK_DIM, (ir.right - SP3, ir.y + 8), right=True)
            tag = self._item_tag(item)
            if tag:
                text(screen, tag, f.label, ACCENT_INK if isel else INFO,
                     (ir.right - SP3 - 64, ir.y + 8), right=True)
            self.sources.append((ir, unit, idx))
            y += 30 + SP1

        if carried and y + 26 < rect.bottom - SP3:
            br = pygame.Rect(x, y + SP1, inner, 26)
            over = br.collidepoint(mouse)
            panel(screen, br, fill=SURFACE_3 if over else SURFACE_1,
                  border=ACCENT if over else INFO, width=1, radius=4)
            text(screen, "stow in pack", f.label, ACCENT if over else INK_DIM,
                 (br.centerx, br.centery - 1), center=True)
            self.zones.append((br, unit, "pack"))

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
    def _draw_tabs(self, screen, W, pad):
        """Right-aligned pill strip on the title row: MEMBERS | REPUTATIONS."""
        f = self.fonts
        x = W - pad
        for key, lbl in reversed(TABS):
            w = f.body_bd.size(lbl)[0] + 2 * SP3
            r = pygame.Rect(x - w, pad - 4, w, 28)
            x = r.x - SP2
            active = self.tab == key
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if (active or hov) else SURFACE_1,
                  border=ACCENT if active else LINE_SOFT, width=2 if active else 1,
                  radius=RADIUS)
            text(screen, lbl, f.body_bd, ACCENT if active else INK_DIM,
                 r.center, center=True)
            self.tab_hits.append((r, key))

    def _draw_reputacoes(self, screen, W, top, outer):
        """The REPUTATIONS tab: where the guild stands with each faction. Only the
        arena keeps a tally today; the panel also shows what it unlocks."""
        f = self.fonts
        rep = self.guild.arena_reputation
        r = pygame.Rect(outer, top + 8, min(W - 2 * outer, 900), 300)
        panel(screen, r, fill=SURFACE_2, border=LINE_SOFT, width=2, radius=RADIUS)
        pad = SP4
        x, y = r.x + pad, r.y + pad

        tracked(screen, "ARENA", f.label, INFO, (x, y))
        y += 18
        text(screen, str(rep), f.num_lg, ACCENT, (x, y))
        text(screen, "reputation  ·  +1 for every arena bout won",
             f.body_sm, INK_DIM, (x + 52, y + 12))
        y += 46

        y = section(screen, "WHAT IT UNLOCKS", x, y, r.w - 2 * pad, f)
        for tier in world.ARENA_TIERS:
            unlocked = rep >= tier["rep"]
            text(screen, tier["name"], f.body, INK if unlocked else INK_DIM, (x, y))
            text(screen, f"entry {tier['entry']}/head  ·  purse {tier['purse']}  ·  "
                 f"{tier['enemies']} opponent(s)", f.body_sm, INK_DIM, (x + 210, y + 2))
            mark = "unlocked" if unlocked else f"needs {tier['rep']} reputation"
            text(screen, mark, f.label, OK if unlocked else INK_FAINT,
                 (r.right - pad, y + 3), right=True)
            y += 28

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen, W, H, pad):
        f = self.fonts
        mouse = self.mouse
        y = H - 52

        if self._carried_names():
            trash = pygame.Rect(0, 0, 220, 36)
            trash.center = (W // 2, y + 18)
            over = trash.collidepoint(mouse)
            panel(screen, trash, fill=DANGER if over else SURFACE_2,
                  border=DANGER, width=1, radius=RADIUS)
            text(screen, "THROW AWAY", f.body_bd,
                 ACCENT_INK if over else DANGER, trash.center, center=True)
            self.zones.append((trash, None, "discard"))

        nxt = pygame.Rect(W - pad - 220, y, 220, 36)
        hov = nxt.collidepoint(mouse)
        panel(screen, nxt, fill=ACCENT if hov else SURFACE_3, border=ACCENT, width=1, radius=RADIUS)
        text(screen, "BACK TO MAP", f.body_bd, ACCENT_INK if hov else ACCENT,
             nxt.center, center=True)
        self.buttons.append(("back", nxt))

        menu = pygame.Rect(pad, y, 140, 36)
        hovm = menu.collidepoint(mouse)
        panel(screen, menu, fill=SURFACE_3 if hovm else SURFACE_2, border=LINE_SOFT,
              width=1, radius=RADIUS)
        text(screen, "menu", f.body, INK if hovm else INK_DIM, menu.center, center=True)
        self.buttons.append(("menu", menu))

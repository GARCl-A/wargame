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
from .dragselect import DragSelectMixin, LoadoutMoveMixin
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SP4, SP5,
                    SURFACE_0, SURFACE_1, SURFACE_2, SURFACE_3, SURFACE_4, WARN,
                    ellipsize, kg, panel, section, set_pointer, token_badge,
                    text, tracked)


TABS = (("members", "MEMBERS"), ("reputations", "REPUTATIONS"))

LIST_MIN, LIST_MAX = 264, 380         # roster column width clamps
DET_MAX = 1120                        # detail panel width cap on very wide screens


class GuildScreen(DragSelectMixin, LoadoutMoveMixin, SheetModalMixin, Screen):
    native = True                        # app draws us straight to the window

    def __init__(self, fonts, guild, on_back, on_level=None, on_manage=None):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.roster = guild.roster
        self.battles_won = guild.battles_won
        self.on_back = on_back
        self.on_level = on_level             # open the level screen for a member
        self.on_manage = on_manage           # open the Manage Gear screen (multi-member loadout)
        self.tab = "members"                  # "members" (roster+gear) | "reputations"
        self.member = self.roster[0] if self.roster else None   # card shown on the right
        self.tab_hits = []                  # [(rect, key)]
        self.member_hits = []              # [(rect, unit)] -- list cards select the member
        self.selected = []                   # [(unit, loc), ...]: loc is "hand"|"offhand"|"armor"|pack index
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
        if self.close_sheet_on_click():        # sheet modal up: any click just closes it
            return

        if dragging:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "level" and self.on_level and self.member is not None:
                    self.on_level(self.member)
                elif key == "share_food" and self.member is not None:
                    self.member.share_food = not self.member.share_food
                elif key == "manage" and self.on_manage:
                    self.on_manage()
                elif key == "back":
                    self.on_back()
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
                self.open_sheet(unit)
                return
        self.selected = [src] if src is not None else []

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
        self._hot = False

        if self.member not in self.roster:
            self.member = self.roster[0] if self.roster else None

        pad = MARGIN if W < 1500 else SP5
        text(screen, "GUILD", f.title, INK, (pad, pad - 2))
        carried = self._carried_names()
        if carried:
            if len(carried) == 1:
                lead = f"moving  {carried[0]} ({kg(data.item_weight(carried[0]))})"
            else:
                tot = sum(data.item_weight(n) for n in carried)
                lead = f"moving  {len(carried)} items ({kg(tot)})"
            sub, col = (lead + "  ·  drop on a HAND, BODY, PACK, a MEMBER in the "
                        "list or on THROW AWAY  ·  click outside to cancel", ACCENT)
        else:
            sub, col = (f"{self.battles_won} wins  ·  {len(self.roster)} members  ·  "
                        "drag an item (or click)  ·  shift+click gathers several", INK_DIM)
        text(screen, ellipsize(sub, f.body, W - 2 * pad), f.body, col, (pad, pad + 30))

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

        self.draw_sheet_modal(screen, f)

        set_pointer(self._hot)

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
            if hov and not sel:
                self._hot = True
            drop = bool(carried) and not sel and hov
            panel(screen, r,
                  fill=SURFACE_3 if (sel or hov) else SURFACE_2,
                  border=ACCENT if sel else INFO if drop else LINE_SOFT,
                  width=2 if (sel or drop) else 1, radius=RADIUS)
            if sel:
                pygame.draw.rect(screen, ACCENT, (r.x, r.y + 4, 3, r.h - 8))

            tok = (r.x + SP3 + 12, r.y + 24)
            token_badge(screen, tok, unit, f)
            nx = tok[0] + 24
            text(screen, ellipsize(unit.name, f.card_name, r.right - nx - SP2),
                 f.card_name, INK if sel else INK_DIM if not hov else INK,
                 (nx, r.y + 6))
            text(screen, ellipsize(f"{unit.race['name']}  ·  {unit.occupation['name']}",
                              f.body_sm, r.right - nx - SP2),
                 f.body_sm, INK_FAINT, (nx, r.y + 27))

            over_norm = unit.encumbered
            over_max = unit.load > unit.carry_max
            ccol = DANGER if over_max else WARN if over_norm else INK_DIM
            text(screen, f"HP {unit.hp_max}   AC {unit.ac}   ·   {kg(unit.load)}",
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

    def _pill(self, screen, r, label, *, accent=False, dot=False):
        """A small labelled button with a hover fill. Feeds `self._hot` for the
        pointer cursor."""
        hov = r.collidepoint(self.mouse)
        if hov:
            self._hot = True
        base = ACCENT if accent else INK_DIM
        fill = ACCENT if (accent and hov) else SURFACE_4 if hov else SURFACE_1
        ink = ACCENT_INK if (accent and hov) else INK if hov else base
        panel(screen, r, fill=fill, border=ACCENT if accent else LINE_SOFT,
              width=1, radius=RADIUS)
        text(screen, label, self.fonts.label, ink,
             (r.centerx + (4 if dot else 0), r.centery), center=True)
        if dot:
            pygame.draw.circle(screen, ink, (r.x + 9, r.centery), 3)

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

        # --- header: identity + two real buttons (sheet / level) ------ #
        head = pygame.Rect(rect.x, rect.y, rect.w, 60)
        pygame.draw.rect(screen, SURFACE_2, head,
                         border_top_left_radius=RADIUS, border_top_right_radius=RADIUS)
        pygame.draw.line(screen, LINE_SOFT, (rect.x, head.bottom), (rect.right - 1, head.bottom))
        tok = (rect.x + pad + 15, rect.y + 30)
        token_badge(screen, tok, unit, f, r=16)
        nx = tok[0] + 28
        origin = self._recruited_by(unit)
        sub = (f"{unit.race['name']}  ·  {unit.occupation['name']}"
               + (f"  ·  recruited by {origin}" if origin else ""))

        btn_w, btn_h = 96, 26
        bx = rect.right - pad - btn_w
        level_pend = bool(unit.pending_picks)
        if self.on_level and not carried:
            lb = pygame.Rect(bx, rect.y + 30 - btn_h // 2, btn_w, btn_h)
            self._pill(screen, lb, "LEVEL UP" if level_pend else "LEVEL",
                       accent=level_pend, dot=level_pend)
            self.buttons.append(("level", lb))
            bx -= btn_w + SP2
        if not carried:
            sb = pygame.Rect(bx, rect.y + 30 - btn_h // 2, btn_w, btn_h)
            self._pill(screen, sb, "SHEET")
            self.info_hits.append((sb, unit))

        text(screen, ellipsize(unit.name, f.card_name, bx - nx - SP2), f.card_name,
             INK, (nx, rect.y + 10))
        text(screen, ellipsize(sub, f.body_sm, bx - nx - SP2), f.body_sm,
             INK_DIM, (nx, rect.y + 34))

        # Two inner columns under the header: the read-out (chips, carry, copper,
        # hunger) on the left, the gear slots -- the drop targets -- on the
        # wider right.
        top = head.bottom + SP4
        col_a = min(440, int(inner * 0.42))
        bx = x + col_a + SP5
        bw = rect.right - pad - bx

        # --- left column: stat chips ------------------------------- #
        a = top
        stats = (("HP", unit.hp_max), ("AC", unit.ac),
                 ("MD", unit.mental_defense), ("SPD", unit.speed))
        cw = (col_a - 3 * SP2) // 4
        for i, (lbl, val) in enumerate(stats):
            self._chip(screen, pygame.Rect(x + i * (cw + SP2), a, cw, 48), lbl, val)
        a += 48 + SP4

        # --- left column: carry bar ------------------------------- #
        over_norm = unit.encumbered
        over_max = unit.load > unit.carry_max
        ccol = DANGER if over_max else WARN if over_norm else OK
        carrier = f"  (carrier +{unit.carry_relief:g})" if unit.carry_relief else ""
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
        text(screen, f"{kg(unit.load)}  ·  normal {kg(unit.carry_normal)}{carrier}  ·  "
             f"high {kg(unit.carry_max)}", f.mono_sm, INK_DIM, (x, a))
        a += 15
        note = ("OVER HIGH LOAD  ·  -2 STR/DEX, -1 speed" if over_max
                else "overloaded  ·  -2 STR/DEX, -1 speed" if over_norm else "")
        if note:
            text(screen, note, f.label, ccol, (x, a))
        a += 18

        # --- left column: copper / levels / hunger ---------------- #
        xp = f"combat N{unit.combat_level} ({unit.combat_xp} XP)"
        if unit.work_xp or unit.work_level:
            xp += f"   ·   work N{unit.work_level}"
        if unit.pending_picks:
            xp += "   ·   talent pick ready"
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
        if not carried and unit.ability.id != "autotroph":
            a += 18
            sf = pygame.Rect(x, a, 168, 22)
            self._pill(screen, sf, "SHARING FOOD" if unit.share_food else "RATIONS PRIVATE",
                       dot=unit.share_food)
            self.buttons.append(("share_food", sf))

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
                    hit, _src = unit.attack_bonus
                    right = f"{hit:+} to hit   ·   {n}d{faces}   ·   "
                text(screen, held, f.body, ink, (hr.x + SP3, hr.y + 9))
                text(screen, right + kg(data.item_weight(held)), f.mono_sm,
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
            text(screen, f"+{armor['ac']} AC   ·   {kg(data.item_weight(worn))}",
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
            text(screen, kg(data.item_weight(item)), f.mono_sm,
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
        self._hot = self._hot or hov
        panel(screen, nxt, fill=ACCENT if hov else SURFACE_3, border=ACCENT, width=1, radius=RADIUS)
        text(screen, "BACK TO MAP", f.body_bd, ACCENT_INK if hov else ACCENT,
             nxt.center, center=True)
        self.buttons.append(("back", nxt))

        if self.on_manage and not self._carried_names() and len(self.roster) > 1:
            mg = pygame.Rect(nxt.x - 220 - SP2, y, 220, 36)
            hovm = mg.collidepoint(mouse)
            self._hot = self._hot or hovm
            panel(screen, mg, fill=ACCENT if hovm else SURFACE_2, border=ACCENT,
                  width=1, radius=RADIUS)
            text(screen, "MANAGE GEAR", f.body_bd, ACCENT_INK if hovm else ACCENT,
                 mg.center, center=True)
            self.buttons.append(("manage", mg))

        text(screen, "Esc for the pause menu", f.label, INK_FAINT, (pad, y + 12))

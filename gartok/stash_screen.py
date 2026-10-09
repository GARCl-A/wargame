"""Shared body of the screens that move gear between a party and a `Stash`.

`bank_screen.BankScreen` (the strongbox) and `city_property_screen.
CityPropertyScreen` (the house) differ only in which `holdings.Stash` they
open, what they sell, and their copy -- the drag/click mechanics, the pinned
member columns and the pooled purse are all here.

Interaction: drag an item where it goes, or click to pick it up and click the
destination (shift/ctrl gathers more first). The stash's own rows carry a
`- N +` stepper for a partial move; a member's pack row always moves as a
whole stack (its ⋮ menu has "split stack" to peel off part first). The row's
⋮ button (or a right-click) opens a menu to send that stack to the stash or
another pinned member.

`self.purse` is the party's real Copper Coin stacks added up (`economy.
PartyPurse`): a rent or a debt payment comes out of the members in proportion
to what each carries, and coins move between members and the stash like any
other item.

A subclass sets the class attributes below and implements `_stash`, `_open`,
`_services` and `_run_service`. The stash is a third kind of pick owner next
to a `Unit`: the string `OWNER`.
"""

import pygame

from . import economy, items
from .constants import fmt_money
from .dragselect import DragSelectMixin, LoadoutMoveMixin
from .packbox import ItemMenuMixin
from .screen import Screen
from .ui import loadout_panel
from .ui.inspector_panel import role_for
from .ui.primitives import draw_button, header, set_pointer, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

RAIL_W = 230
COL_MIN, COL_MAX = 300, 420
STASH_W = 360


class StashScreen(economy.PartyPurse, ItemMenuMixin, DragSelectMixin, LoadoutMoveMixin, Screen):
    native = True

    OWNER = ""              # pick-owner key for the stash: "bank" / "house"
    TITLE = ""
    SUBTITLE = ""
    LABEL = ""              # panel label, e.g. "the strongbox"
    LEAVE_LABEL = ""
    CLOSED_NOTICE = ""      # shown when depositing into a stash the guild doesn't hold yet
    WHERE = ""              # "in the chest" -- completes "won't fit -- N kg free ..."
    CAN_DISTRIBUTE = False
    header_reserve = 0      # px of the header's right edge a host (a hub's tabs) has taken

    def __init__(self, fonts, guild, party, on_done):
        super().__init__()
        self.fonts = fonts                    # legacy Fonts -- unused, kept for the ctor's existing shape
        self._F = None
        self.guild = guild
        self.party = party
        self.on_done = on_done
        self.selected = []                    # [(owner, loc)] -- owner is OWNER or a Unit
        self._sel_qty = {}                    # (owner, idx) -> qty picked; member picks always move whole
        self.pinned = list(party)             # columns shown, clamped to fit at draw time
        self.notice = None
        self.buttons = []                     # [(key, rect)]
        self.sources = []                     # [(rect, owner, loc)]
        self.zones = []                       # [(rect, owner_or_OWNER, zone)]
        self._rail_hits = []
        self._rail_rect = None
        self._rail_scroll = 0
        self._rail_max_scroll = 0
        self._pack_scroll = {}                # id(unit) -> pack rows scrolled past
        self._stash_scroll = 0
        self._service_hits = []               # [(rect, key)]
        self._stash_steppers = []             # [(rect, pick, delta)]
        self._dots_hits = []                  # [(rect, unit, idx)] -- the pack row's menu button
        self._unit_by_uid = {u.uid: u for u in party}
        self.back_rect = None

    # ------------------------------------------------------------------ #
    # hooks                                                              #
    # ------------------------------------------------------------------ #
    def _stash(self):
        raise NotImplementedError

    def _open(self):
        """True once the guild actually holds the stash (rented / bought)."""
        raise NotImplementedError

    def _services(self):
        """`[(key, label, sub, enabled)]` for the panel's service buttons."""
        raise NotImplementedError

    def _run_service(self, key):
        raise NotImplementedError

    def _draw_status(self, screen, F, x, y, w):
        """Extra lines above the panel (debt, tax); returns the new `y`."""
        return y

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

    # ------------------------------------------------------------------ #
    # LoadoutMoveMixin overrides: teach it the stash as a third kind of   #
    # owner, and make pack/stash picks respect a partial-qty selection   #
    # (equip-slot picks stay whole -- you can't equip half a sword)      #
    # ------------------------------------------------------------------ #
    def _inventory(self, owner):
        return self._stash().items if owner == self.OWNER else owner._base_inventory

    def _item_at(self, owner, loc):
        if owner == self.OWNER:
            inv = self._stash().items
            return inv[loc][0] if loc < len(inv) else None
        return super()._item_at(owner, loc)

    def _qty_at(self, owner, loc):
        if isinstance(loc, str):
            return 1 if self._item_at(owner, loc) is not None else 0
        inv = self._inventory(owner)
        full = inv[loc][1] if loc < len(inv) else 0
        return min(full, self._sel_qty.get((owner, loc), full))

    def _take(self, owner, loc):
        if isinstance(loc, str):
            return super()._take(owner, loc)
        qty = self._qty_at(owner, loc)
        if owner == self.OWNER:
            return self._stash().take(loc, qty)
        return owner.take_from_pack(loc, qty), qty

    def _give_many(self, dst, zone):
        """Mirrors `LoadoutMoveMixin._give_many`, with one difference: a
        pick's owner (or the move's source) may be the stash, which has no
        `_derive_combat` to call -- guarded below instead of overridden
        piecemeal, since the parent's version isn't split into reusable
        pieces at that seam."""
        if dst == self.OWNER:
            self._deposit(list(self.selected))
            return
        picks = [p for p in self.selected if self._item_at(*p) is not None]
        self.selected = []
        if not picks:
            return

        # taking out of the stash is the one direction this screen still
        # hard-blocks over `carry_max` -- member <-> member stays the soft,
        # penalty-only overload rule `LoadoutMoveMixin` already assumes
        if any(owner == self.OWNER for owner, _ in picks):
            add = sum(items.item_weight(self._item_at(*p)) * self._qty_at(*p) for p in picks)
            if dst.load + add > dst.carry_max:
                self.notice = f"won't fit {dst.name}'s load."
                self.selected = picks
                return

        if zone in ("hand", "offhand", "tongue", "artifact", "armor"):
            fit = next((p for p in picks
                       if self._fits_slot(dst, zone, self._item_at(*p))
                       and not (p[0] is dst and self._slot_of(p[1]) == zone)), None)
            if fit is None:
                self.selected = picks
                return
            name = self._item_at(*fit)
            src = fit[0]
            taken_name, qty = self._take(*fit)
            if qty > 1:
                if src == self.OWNER:
                    self._stash().put(taken_name, qty - 1)
                else:
                    src.give_to_pack(taken_name, qty - 1)
            {"hand": dst.give_to_hand, "offhand": dst.give_to_offhand,
             "tongue": dst.give_to_tongue, "artifact": dst.give_to_artifact,
             "armor": dst.give_to_armor}[zone](name)
            if src != self.OWNER:
                src._derive_combat()
            dst._derive_combat()
            return

        # pack
        if all(p[0] is dst and not isinstance(p[1], str) for p in picks):
            return
        collected, touched = self._collect(picks)
        for name, qty in collected:
            dst.give_to_pack(name, qty)
        for u in touched:
            if u != self.OWNER:
                u._derive_combat()
        dst._derive_combat()

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
        if self._dots_at(px) is not None:
            return None
        for rect, owner, loc in self.sources:
            if rect.collidepoint(px):
                return (owner, loc)
        return None

    def _zone_at(self, px):
        for rect, owner, zone in self.zones:
            if rect.collidepoint(px):
                return (owner, zone)
        return None

    def _begin_drag(self, src):
        if src not in self.selected:
            self.selected = [src]

    def handle_event(self, event):
        if self._menu_event(event):
            return
        if event.type == pygame.MOUSEWHEEL:
            if self._rail_rect and self._rail_rect.collidepoint(self.mouse):
                self._rail_scroll = max(0, min(self._rail_max_scroll,
                                               self._rail_scroll - event.y * 40))
                return
        super().handle_event(event)

    def _drop(self, px, dragging, src):
        if dragging:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            self.selected, self._sel_qty = [], {}
            return

        pick = self._dots_at(px)
        if pick is not None:
            self._open_menu(px, self._menu_picks_for(pick))
            return

        for rect, key, delta in self._stash_steppers:
            if rect.collidepoint(px):
                self._bump_qty(key, delta)
                return

        for rect, key in self._service_hits:
            if rect.collidepoint(px):
                self._run_service(key)
                return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "done":
                    self._leave()
                elif key == "distribute":
                    self._distribute_load()
                return

        mods = pygame.key.get_mods()
        if src is not None and mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL):
            if src in self.selected:
                self.selected.remove(src)
                self._sel_qty.pop(src, None)
            else:
                self.selected.append(src)
            return

        if self.selected:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
                self.selected, self._sel_qty = [], {}
                return
            if src in self.selected:
                self.selected, self._sel_qty = [], {}
            elif src is not None:
                self.selected, self._sel_qty = [src], {}
            else:
                self.selected, self._sel_qty = [], {}
            return

        for rect, unit in self._rail_hits:
            if rect.collidepoint(px):
                if unit in self.pinned:
                    self.pinned.remove(unit)
                else:
                    self.pinned.append(unit)
                return

        self.selected = [src] if src is not None else []

    def _bump_qty(self, pick, delta):
        step = delta * (5 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1)
        owner, loc = pick
        inv = self._inventory(owner)
        full = inv[loc][1] if loc < len(inv) else 0
        cur = self._sel_qty.get(pick, full)
        new = full if delta >= 999 else max(0, min(full, cur + step))
        if new <= 0:
            self._sel_qty.pop(pick, None)
            self.selected = [p for p in self.selected if p != pick]
        else:
            self._sel_qty[pick] = new
            if pick not in self.selected:
                self.selected.append(pick)

    # ------------------------------------------------------------------ #
    # money + moving                                                     #
    # ------------------------------------------------------------------ #
    def _deposit(self, picks):
        picks = [p for p in picks if p[0] != self.OWNER and self._item_at(*p) is not None]
        if not picks:
            self.selected, self._sel_qty = [], {}
            return
        stash = self._stash()
        add = sum(items.item_weight(self._item_at(*p)) * self._qty_at(*p) for p in picks)
        if not self._open():
            self.notice = self.CLOSED_NOTICE
            self.selected = picks
            return
        if not stash.fits(add):
            self.notice = f"won't fit -- {stash.free:g} kg free {self.WHERE}."
            self.selected = picks
            return
        collected, touched = self._collect(picks)
        self._sel_qty = {}
        for name, qty in collected:
            stash.put(name, qty)
        for u in touched:
            u._derive_combat()
        total = sum(q for _, q in collected)
        one = collected[0][0] if total == 1 else f"{total} items"
        self.notice = f"stashed {one}."

    def _menu_picks_for(self, pick):
        return self.selected if pick in self.selected else [pick]

    def _menu_rows(self, picks):
        picks = [p for p in picks if self._item_at(*p) is not None]
        if not picks:
            return []
        self.selected = list(picks)
        owners = {id(p[0]) for p in picks}
        lift = len(owners) > 1 or any(isinstance(p[1], str) or p[0] == self.OWNER for p in picks)
        rows = [("member", f"to {u.name}", u) for u in self.pinned if lift or id(u) not in owners]
        if any(p[0] != self.OWNER for p in picks):
            rows.insert(0, ("stash", f"to {self.LABEL}", self.OWNER))
        return rows

    def _menu_run(self, picks, kind, arg):
        self.selected = list(picks)
        self._give_many(arg, "pack" if kind == "member" else self.OWNER)
        self.selected, self._sel_qty = [], {}

    def _distribute_load(self):
        from . import unit as unit_module
        if len(self.party) <= 1:
            return
        unit_module.distribute_load(self.party, share_coins=False)
        self.notice = "redistributed packs by carrying capacity."

    def _purse_members(self):
        return self.party

    def _leave(self):
        self.on_done()

    # ------------------------------------------------------------------ #
    # adapters: real Unit -> the plain dicts loadout_panel draws          #
    # ------------------------------------------------------------------ #
    def _hand_note(self, unit):
        name = unit.equipped_weapon
        w = items.get(name)
        if not name or not items.is_weapon(w):
            return None
        hit_bonus, _ = unit.attack_bonus
        dn, faces = w.damage
        return f"{hit_bonus:+} hit  ·  {dn}d{faces} dmg"

    @staticmethod
    def _armor_note(unit):
        name = unit.equipped_armor
        a = items.get(name)
        if not name or not items.is_armor(a):
            return None
        return items.armor_note(a)

    def _item_tag(self, name):
        return items.item_tag(name)

    def _member_dict(self, unit, carried):
        w = items.get(unit.equipped_weapon)
        two_handed = bool(w) and w.hands >= 2
        selected_locs = {loc for owner, loc in self.selected if owner is unit}

        def held(kind, name, note):
            return {"name": name, "note": note, "sel": kind in selected_locs,
                    "accepts": bool(carried) and any(self._fits_slot(unit, kind, n) for n in carried)}

        member = {
            "name": unit.name, "role": role_for(unit.occupation),
            "pending_picks": bool(unit.pending_picks),
            "kg": unit.load, "cap": unit.carry_normal,
            "hand": held("hand", unit.equipped_weapon, self._hand_note(unit)),
            "offhand": None if two_handed else held("offhand", unit.equipped_offhand, None),
            "armor": held("armor", unit.equipped_armor, self._armor_note(unit)),
            "pack": [(name, unit.pack_tag(name), items.item_weight(name), qty,
                     unit.locked_of(name) > 0, idx in selected_locs)
                    for idx, (name, qty) in enumerate(unit._base_inventory)],
        }
        if unit.has_tongue:
            member["tongue"] = held("tongue", unit.equipped_tongue, None)
        member["artifact"] = held("artifact", unit.equipped_artifact, None)
        return member

    def _stash_rows(self):
        rows = []
        sel = {loc: self._qty_at(self.OWNER, loc) for owner, loc in self.selected if owner == self.OWNER}
        for idx, (name, qty) in enumerate(self._stash().items):
            rows.append((idx, name, self._item_tag(name), items.item_weight(name), qty,
                        None, None, None, sel.get(idx, 0)))
        return rows

    # ------------------------------------------------------------------ #
    def _draw_rail(self, screen, F, rect):
        members = [{"key": u.uid, "name": u.name, "role": role_for(u.occupation),
                    "kg": u.load, "cap": u.carry_normal} for u in self.party]
        pinned_keys = {u.uid for u in self.pinned}
        hits, max_scroll = loadout_panel.rail(screen, F, rect, members, pinned_keys,
                                              bool(self.selected), self._rail_scroll, self.mouse)
        self._rail_rect = rect
        self._rail_max_scroll = max_scroll
        self._rail_scroll = max(0, min(self._rail_scroll, max_scroll))
        self._rail_hits = [(r, self._unit_by_uid[uid]) for r, uid in hits]
        for r, u in self._rail_hits:
            self.zones.append((r, u, "pack"))

    def _draw_columns(self, screen, F, area):
        gap = T.S * 2
        shown = [u for u in self.pinned if u in self.party]
        cap = max(1, (area.w + gap) // (COL_MIN + gap))
        shown = shown[:cap]
        n = max(1, len(shown))
        col_w = min(COL_MAX, max(COL_MIN, (area.w - (n - 1) * gap) // n))
        carried = self._carried_names()

        for i, u in enumerate(shown):
            r = pygame.Rect(area.x + i * (col_w + gap), area.y, col_w, area.h)
            member = self._member_dict(u, carried)
            res = loadout_panel.column(screen, F, r, member, self._pack_scroll.get(id(u), 0), self.mouse)
            self._pack_scroll[id(u)] = res["scroll"]
            for kind, slot_rect in res["slot_rects"].items():
                if slot_rect is None:
                    continue
                self.zones.append((slot_rect, u, kind))
                if member[kind]["name"]:
                    self.sources.append((slot_rect, u, kind))
            self.zones.append((res["pack_zone"], u, "pack"))
            for pr, idx in res["pack_hits"]:
                self.sources.append((pr, u, idx))
            for dr, idx in res["dots_hits"]:
                self._dots_hits.append((dr, u, idx))

        hidden = len(self.pinned) - len(shown)
        if hidden > 0:
            text(screen, F["body_sm"], f"+{hidden} pinned but hidden -- widen the window",
                (area.x, area.bottom + 4), T.TX_FAINT)
        if not shown:
            text(screen, F["body"], "Pin a member on the left to see their gear.",
                area.center, T.TX_FAINT, center=True)

    def _draw_stash(self, screen, F, rect):
        x, w = rect.x + T.S * 2, rect.w - T.S * 4
        y = self._draw_status(screen, F, x, rect.y + T.S * 2, w)
        panel_rect = pygame.Rect(rect.x, y, rect.w, rect.bottom - y)

        stash, held = self._stash(), self._open()
        data_ = {"label": self.LABEL,
                "capacity": (stash.load, stash.capacity) if held else None,
                "rows": self._stash_rows() if held else [],
                "services": self._services()}
        res = loadout_panel.container_panel(screen, F, panel_rect, data_, self._stash_scroll, self.mouse)
        self._stash_scroll = res["scroll"]
        self._service_hits += res["service_hits"]
        for r, idx in res["row_hits"]:
            self.sources.append((r, self.OWNER, idx))
        for idx, ctl in res["row_controls"].items():
            pick = (self.OWNER, idx)
            for key, delta in (("minus", -1), ("plus", 1), ("all", 999)):
                if ctl[key]:
                    self._stash_steppers.append((ctl[key], pick, delta))
        if held:
            self.zones.append((panel_rect, self.OWNER, self.OWNER))

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self._unit_by_uid = {u.uid: u for u in self.party}
        self.zones, self.sources, self.buttons, self._service_hits = [], [], [], []
        self._stash_steppers = []
        self._dots_hits = []

        head = pygame.Rect(0, 0, W, T.S * 9)
        body = pygame.Rect(0, head.bottom, W, H - head.bottom - T.S * 10)
        stash_rect = pygame.Rect(0, body.y, STASH_W, body.h)
        rail_rect = pygame.Rect(stash_rect.right, body.y, RAIL_W, body.h)
        cols = pygame.Rect(rail_rect.right, body.y, W - rail_rect.right, body.h)

        header(screen, F, head, self.TITLE, self.SUBTITLE, (), None, mpos=self.mouse)
        self.back_rect = pygame.Rect(head.x, head.y, T.S * 6, head.h)
        has_tut = self.tutorial_key() is not None
        purse_x = W - T.S * 3 - (28 + T.S if has_tut else 0) - self.header_reserve
        text(screen, F["microb"], f"purse {fmt_money(self.purse)}", (purse_x, T.S * 3), T.BRASS, right=True)

        self._draw_stash(screen, F, stash_rect)
        self._draw_rail(screen, F, rail_rect)
        self._draw_columns(screen, F, cols.inflate(-T.S * 2, -T.S * 2))

        done_r = pygame.Rect(T.S * 2, H - T.S * 8, T.S * 25, T.S * 4)
        draw_button(screen, F, done_r, self.LEAVE_LABEL, primary=True, mpos=self.mouse)
        self.buttons.append(("done", done_r))
        if self.CAN_DISTRIBUTE and len(self.party) > 1:
            dist_r = pygame.Rect(done_r.right + T.S * 2, H - T.S * 8, T.S * 22, T.S * 4)
            draw_button(screen, F, dist_r, "distribute load", mpos=self.mouse)
            self.buttons.append(("distribute", dist_r))
        if self.notice:
            text(screen, F["body_sm"], self.notice, (T.S * 2, H - T.S * 10), T.BRASS)
        self._draw_menu(screen)
        set_pointer(self._hovering())

    def _hovering(self):
        if self.menu is not None or self.split_prompt is not None:
            return self._menu_hovering()
        if any(r.collidepoint(self.mouse) for r, *_ in self._dots_hits):
            return True
        if self.back_rect is not None and self.back_rect.collidepoint(self.mouse):
            return True
        if any(r.collidepoint(self.mouse) for _, r in self.buttons):
            return True
        if any(r.collidepoint(self.mouse) for r, _ in self._rail_hits):
            return True
        if any(r.collidepoint(self.mouse) for r, *_ in self._service_hits):
            return True
        return any(r.collidepoint(self.mouse) for r, *_ in self.sources)

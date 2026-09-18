"""The bank: the guild's strongbox, rented from the Bankers.

The guild owns nothing as a body except this -- a chest at the bank in the City,
rented from the Bankers for a flat fee (`economy.BANK_CHEST_PRICE`) and holding
`guild.bank_capacity` kg. This screen rents the chest and moves gear between it
and the visiting party's packs -- and, unlike before, lets a member equip
straight out of either side: the hand/armor slots are drop zones here exactly
like on the gear screen, not a separate trip.

Money is pooled for the visit (`self.purse`, snapshotted from the party's own
coin at the door) rather than moved copper by copper -- renting the chest or
buying the house just debits the pool. Leaving settles the pool back out
proportional to what each member walked in with (`economy.settle_pooled_
purse`), so nobody's relative wealth changes just from visiting, without the
screen having to track whose copper paid for what.

Interaction: drag an item where it goes, or click to pick it up and click the
destination (shift/ctrl gathers more first). The chest's own rows carry a
`- N +` stepper for a partial move; a member's pack row always moves as a
whole stack (split it on the group screen first if you want less).
"""

import pygame

from . import data, economy
from .dragselect import DragSelectMixin, LoadoutMoveMixin
from .screen import Screen
from .theme import set_pointer
from .ui import loadout_panel
from .ui.inspector_panel import role_for
from .ui.primitives import draw_button, header, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

RAIL_W = 230
COL_MIN, COL_MAX = 300, 420
CHEST_W = 360


class BankScreen(DragSelectMixin, LoadoutMoveMixin, Screen):
    native = True

    def __init__(self, fonts, guild, party, on_done):
        super().__init__()
        self.fonts = fonts                    # legacy Fonts -- unused, kept for the ctor's existing shape
        self._F = None
        self.guild = guild
        self.party = party
        self.on_done = on_done
        self._orig_gold = {m: m.gold for m in party}
        self.purse = sum(self._orig_gold.values())
        self.selected = []                    # [(owner, loc)] -- owner is "bank" or a Unit
        self._sel_qty = {}                    # ("bank", idx) -> qty picked; member picks always move whole
        self.pinned = list(party)             # columns shown, clamped to fit at draw time
        self.notice = None
        self.buttons = []                     # [(key, rect)]
        self.sources = []                     # [(rect, owner, loc)]
        self.zones = []                       # [(rect, owner_or_"bank", zone)]
        self._rail_hits = []
        self._rail_rect = None
        self._rail_scroll = 0
        self._rail_max_scroll = 0
        self._pack_scroll = {}                # id(unit) -> pack rows scrolled past
        self._chest_scroll = 0
        self._service_hits = []               # [(rect, key)]
        self._unit_by_uid = {u.uid: u for u in party}
        self.back_rect = None

    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "bank"

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

    # ------------------------------------------------------------------ #
    # LoadoutMoveMixin overrides: teach it the chest as a third kind of   #
    # owner, and make pack/chest picks respect a partial-qty selection   #
    # (equip-slot picks stay whole -- you can't equip half a sword)      #
    # ------------------------------------------------------------------ #
    def _item_at(self, owner, loc):
        if owner == "bank":
            items = self.guild.bank_items
            return items[loc][0] if loc < len(items) else None
        return super()._item_at(owner, loc)

    def _qty_at(self, owner, loc):
        if isinstance(loc, str):
            return 1 if self._item_at(owner, loc) is not None else 0
        items = self.guild.bank_items if owner == "bank" else owner._base_inventory
        full = items[loc][1] if loc < len(items) else 0
        return min(full, self._sel_qty.get((owner, loc), full))

    def _take(self, owner, loc):
        if isinstance(loc, str):
            return super()._take(owner, loc)
        qty = self._qty_at(owner, loc)
        if owner == "bank":
            return self.guild.take_from_bank(loc, qty)
        return owner.take_from_pack(loc, qty), qty

    def _give_many(self, dst, zone):
        """Mirrors `LoadoutMoveMixin._give_many`, with one difference: a
        pick's owner (or the move's source) may be `"bank"`, which has no
        `_derive_combat` to call -- guarded below instead of overridden
        piecemeal, since the parent's version isn't split into reusable
        pieces at that seam."""
        if dst == "bank":
            self._deposit(list(self.selected))
            return
        picks = [p for p in self.selected if self._item_at(*p) is not None]
        self.selected = []
        if not picks:
            return

        # taking out of the chest is the one direction this screen still
        # hard-blocks over `carry_max` -- member <-> member stays the soft,
        # penalty-only overload rule `LoadoutMoveMixin` already assumes
        from_bank = any(owner == "bank" for owner, _ in picks)
        if from_bank:
            add = sum(data.item_weight(self._item_at(*p)) * self._qty_at(*p) for p in picks)
            if dst.load + add > dst.carry_max:
                self.notice = f"won't fit {dst.name}'s load."
                self.selected = picks
                return

        if zone in ("hand", "offhand", "tongue", "armor"):
            fit = next((p for p in picks
                       if self._fits_slot(dst, zone, self._item_at(*p))
                       and not (p[0] is dst and self._slot_of(p[1]) == zone)), None)
            if fit is None:
                self.selected = picks
                return
            name = self._item_at(*fit)
            src = fit[0]
            self._take(*fit)
            {"hand": dst.give_to_hand, "offhand": dst.give_to_offhand,
             "tongue": dst.give_to_tongue, "armor": dst.give_to_armor}[zone](name)
            if src != "bank":
                src._derive_combat()
            dst._derive_combat()
            return

        # pack
        if all(p[0] is dst and not isinstance(p[1], str) for p in picks):
            return
        items, touched = self._collect(picks)
        for name, qty in items:
            dst.give_to_pack(name, qty)
        for u in touched:
            if u != "bank":
                u._derive_combat()
        dst._derive_combat()

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
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

        for rect, key, delta in self._chest_steppers:
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
        full = self._item_full_qty(pick)
        cur = self._sel_qty.get(pick, full)
        new = full if delta >= 999 else max(0, min(full, cur + step))
        if new <= 0:
            self._sel_qty.pop(pick, None)
            self.selected = [p for p in self.selected if p != pick]
        else:
            self._sel_qty[pick] = new
            if pick not in self.selected:
                self.selected.append(pick)

    def _item_full_qty(self, pick):
        owner, loc = pick
        items = self.guild.bank_items if owner == "bank" else owner._base_inventory
        return items[loc][1] if loc < len(items) else 0

    # ------------------------------------------------------------------ #
    # money + services                                                   #
    # ------------------------------------------------------------------ #
    def _run_service(self, key):
        if key == "rent":
            if self.purse < economy.BANK_CHEST_PRICE:
                self.notice = (f"the strongbox costs {economy.BANK_CHEST_PRICE} copper -- "
                               f"the party has {self.purse}.")
                return
            self.purse -= economy.BANK_CHEST_PRICE
            self.guild.rent_bank_chest()
            self.notice = (f"rented a strongbox -- {self.guild.bank_capacity} kg of "
                           "storage at the bank.")
        elif key == "buy_property":
            if self.purse < economy.CITY_PROPERTY_PRICE:
                self.notice = (f"the Bankers want {economy.CITY_PROPERTY_PRICE} copper for "
                               f"the house -- the party has {self.purse}.")
                return
            self.purse -= economy.CITY_PROPERTY_PRICE
            self.guild.buy_city_property()
            self.notice = "bought a house in the City -- the Bankers' tax starts now."

    def _deposit(self, picks):
        picks = [p for p in picks if p[0] != "bank" and self._item_at(*p) is not None]
        if not picks:
            self.selected, self._sel_qty = [], {}
            return
        add = sum(data.item_weight(self._item_at(*p)) * self._qty_at(*p) for p in picks)
        if not self.guild.bank_unlocked:
            self.notice = "rent a strongbox first."
            self.selected = picks
            return
        if self.guild.bank_load + add > self.guild.bank_capacity:
            free = self.guild.bank_capacity - self.guild.bank_load
            self.notice = f"won't fit -- {free:g} kg free in the chest."
            self.selected = picks
            return
        items, touched = self._collect(picks)
        self._sel_qty = {}
        for name, qty in items:
            self.guild.stash_in_bank(name, qty)
        for u in touched:
            u._derive_combat()
        total = sum(q for _, q in items)
        one = items[0][0] if total == 1 else f"{total} items"
        self.notice = f"stashed {one}."

    def _distribute_load(self):
        from . import unit as unit_module
        if len(self.party) <= 1:
            return
        unit_module.distribute_load(self.party)
        self.notice = "redistributed packs by carrying capacity."

    def _leave(self):
        economy.settle_pooled_purse(self.party, self._orig_gold, self.purse)
        self.on_done()

    # ------------------------------------------------------------------ #
    # adapters: real Unit -> the plain dicts loadout_panel draws          #
    # ------------------------------------------------------------------ #
    def _hand_note(self, unit):
        name = unit.equipped_weapon
        if not name or name not in data.WEAPONS:
            return None
        wd = data.WEAPONS[name]
        hit_bonus, _ = unit.attack_bonus
        dn, faces = wd["damage"]
        return f"{hit_bonus:+} hit  ·  {dn}d{faces} dmg"

    @staticmethod
    def _armor_note(unit):
        name = unit.equipped_armor
        if not name or name not in data.ARMOR:
            return None
        ad = data.ARMOR[name]
        return f"+{ad['ac']} AC"

    def _item_tag(self, name):
        if name in data.WEAPONS:
            return "WEAPON"
        if name in data.ARMOR:
            return "ARMOR"
        return ""

    def _member_dict(self, unit, carried):
        two_handed = bool(unit.equipped_weapon) and data.WEAPONS[unit.equipped_weapon]["hands"] >= 2
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
            "pack": [(name, self._item_tag(name), data.item_weight(name), qty,
                     unit.locked_of(name) > 0, idx in selected_locs)
                    for idx, (name, qty) in enumerate(unit._base_inventory)],
        }
        if unit.has_tongue:
            member["tongue"] = held("tongue", unit.equipped_tongue, None)
        return member

    def _chest_rows(self):
        rows = []
        sel_bank = {loc: self._qty_at("bank", loc) for owner, loc in self.selected if owner == "bank"}
        for idx, (name, qty) in enumerate(self.guild.bank_items):
            rows.append((idx, name, self._item_tag(name), data.item_weight(name), qty,
                        None, None, None, sel_bank.get(idx, 0)))
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

        hidden = len(self.pinned) - len(shown)
        if hidden > 0:
            text(screen, F["body_sm"], f"+{hidden} pinned but hidden -- widen the window",
                (area.x, area.bottom + 4), T.TX_FAINT)
        if not shown:
            text(screen, F["body"], "Pin a member on the left to see their gear.",
                area.center, T.TX_FAINT, center=True)

    def _draw_chest(self, screen, F, rect):
        used, cap = self.guild.bank_load, self.guild.bank_capacity
        services = []
        if not self.guild.property_city_unlocked and not self.guild.property_city_squatting \
                and self.guild.bankers_debt <= 0:
            rep_ok = self.guild.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
            can_buy = rep_ok and not self.guild.bankers_services_blocked and self.purse >= economy.CITY_PROPERTY_PRICE
            sub = (f"{economy.CITY_PROPERTY_PRICE} c  ·  needs {economy.CITY_PROPERTY_REP_GATE} "
                  "standing with the Bankers")
            services.append(("buy_property", "BUY THE HOUSE", sub, can_buy))
        if not self.guild.bank_unlocked:
            can_rent = self.purse >= economy.BANK_CHEST_PRICE
            services.append(("rent", "RENT A STRONGBOX",
                            f"{economy.BANK_CHEST_PRICE} c  ·  {economy.BANK_CHEST_CAPACITY} kg held in the City",
                            can_rent))

        data_ = {"label": "the strongbox",
                "capacity": (used, cap) if self.guild.bank_unlocked else None,
                "rows": self._chest_rows() if self.guild.bank_unlocked else [],
                "services": services}
        res = loadout_panel.container_panel(screen, F, rect, data_, self._chest_scroll, self.mouse)
        self._chest_scroll = res["scroll"]
        self._service_hits = res["service_hits"]
        self._chest_steppers = []
        for r, idx in res["row_hits"]:
            self.sources.append((r, "bank", idx))
        for idx, ctl in res["row_controls"].items():
            if ctl["minus"]:
                self._chest_steppers.append((ctl["minus"], ("bank", idx), -1))
            if ctl["plus"]:
                self._chest_steppers.append((ctl["plus"], ("bank", idx), 1))
            if ctl["all"]:
                self._chest_steppers.append((ctl["all"], ("bank", idx), 999))
        if self.guild.bank_unlocked:
            self.zones.append((rect, "bank", "chest"))

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self._unit_by_uid = {u.uid: u for u in self.party}
        self.zones, self.sources, self.buttons = [], [], []
        self._chest_steppers = []

        head = pygame.Rect(0, 0, W, T.S * 9)
        body = pygame.Rect(0, head.bottom, W, H - head.bottom - T.S * 10)
        chest_rect = pygame.Rect(0, body.y, CHEST_W, body.h)
        rail_rect = pygame.Rect(chest_rect.right, body.y, RAIL_W, body.h)
        cols = pygame.Rect(rail_rect.right, body.y, W - rail_rect.right, body.h)

        header(screen, F, head, "The Bank",
              "the Bankers rent one strongbox  ·  a flat fee, no questions", (), None,
              mpos=self.mouse)
        self.back_rect = pygame.Rect(head.x, head.y, T.S * 6, head.h)
        text(screen, F["microb"], f"purse {self.purse} c",
            (W - T.S * 3, T.S * 3), T.BRASS, right=True)

        self._draw_chest(screen, F, chest_rect)
        self._draw_rail(screen, F, rail_rect)
        self._draw_columns(screen, F, cols.inflate(-T.S * 2, -T.S * 2))

        done_r = pygame.Rect(T.S * 2, H - T.S * 8, T.S * 25, T.S * 4)
        draw_button(screen, F, done_r, "leave the bank", primary=True, mpos=self.mouse)
        self.buttons.append(("done", done_r))
        if len(self.party) > 1:
            dist_r = pygame.Rect(done_r.right + T.S * 2, H - T.S * 8, T.S * 22, T.S * 4)
            draw_button(screen, F, dist_r, "distribute load", mpos=self.mouse)
            self.buttons.append(("distribute", dist_r))
        if self.notice:
            text(screen, F["body_sm"], self.notice, (T.S * 2, H - T.S * 10), T.BRASS)
        set_pointer(self._hovering())

    def _hovering(self):
        if self.back_rect is not None and self.back_rect.collidepoint(self.mouse):
            return True
        if any(r.collidepoint(self.mouse) for _, r in self.buttons):
            return True
        if any(r.collidepoint(self.mouse) for r, _ in self._rail_hits):
            return True
        if any(r.collidepoint(self.mouse) for r, *_ in self._service_hits):
            return True
        return any(r.collidepoint(self.mouse) for r, *_ in self.sources)

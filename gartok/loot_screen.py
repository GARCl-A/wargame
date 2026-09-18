"""Loot screen: split the spoils after a won fight.

The pile on the left is everything left on the field (see `loot.field_loot`):
the defeated enemies' gear, your own dead's gear, loose weapons and torches.
Drag items to members' packs, or straight into their hands/armor. 
"Take what fits" fills packs greedily. Whatever is still in the pile when 
you finish is left behind.
"""

import pygame

from . import data
from .dragselect import DragSelectMixin, LoadoutMoveMixin
from .packbox import PackColumnMixin
from .screen import Screen
from .theme import set_pointer
from .ui import loadout_panel
from .ui.primitives import header, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

COL_MIN, COL_MAX = 300, 420
CHEST_W = 360

class LootScreen(PackColumnMixin, DragSelectMixin, LoadoutMoveMixin, Screen):
    native = True

    def __init__(self, fonts, guild, survivors, pool, on_done):
        super().__init__()
        self.fonts = fonts
        self._F = None
        self.guild = guild
        self.survivors = survivors
        self.on_done = on_done
        
        from collections import Counter
        # Group identical items into stacks: [(name, qty)]
        self.pool = [(name, count) for name, count in Counter(pool).items()]
        
        self.selected = []                    # [(owner, loc)] -- owner is "pool" or a Unit
        self._sel_qty = {}                    # ("pool", idx) -> qty picked; member picks always move whole
        self.pinned = list(survivors)         # columns shown, clamped to fit at draw time
        self.notice = None
        self.buttons = []                     # [(key, rect)]
        self.sources = []                     # [(rect, owner, loc)]
        self.zones = []                       # [(rect, owner_or_"pool", zone)]
        self._chest_scroll = 0
        self._service_hits = []               # [(rect, key)]
        self._chest_steppers = []             # [(rect, idx, delta)]
        self.back_rect = None

    def tutorial_key(self):
        return "loot"

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

    # ------------------------------------------------------------------ #
    # LoadoutMoveMixin overrides: teach it the pool as a third kind of   #
    # owner, and make pack/pool picks respect a partial-qty selection    #
    # ------------------------------------------------------------------ #
    def _item_at(self, owner, loc):
        if owner == "pool":
            return self.pool[loc][0] if loc < len(self.pool) else None
        return super()._item_at(owner, loc)

    def _qty_at(self, owner, loc):
        if isinstance(loc, str):
            return 1 if self._item_at(owner, loc) is not None else 0
        items = self.pool if owner == "pool" else owner._base_inventory
        full = items[loc][1] if loc < len(items) else 0
        return min(full, self._sel_qty.get((owner, loc), full))

    def _take(self, owner, loc):
        if isinstance(loc, str):
            return super()._take(owner, loc)
        qty = self._qty_at(owner, loc)
        if owner == "pool":
            name, total = self.pool[loc]
            if qty >= total:
                self.pool.pop(loc)
            else:
                self.pool[loc] = (name, total - qty)
            return name, qty
        return owner.take_from_pack(loc, qty), qty
        
    def _deposit(self, picks):
        items, touched = self._collect(picks)
        for name, qty in items:
            idx = next((i for i, (n, q) in enumerate(self.pool) if n == name), None)
            if idx is not None:
                self.pool[idx] = (name, self.pool[idx][1] + qty)
            else:
                self.pool.append((name, qty))
        for u in touched:
            if u != "pool":
                u._derive_combat()

    def _give_many(self, dst, zone):
        if dst == "pool":
            self._deposit(list(self.selected))
            return
        picks = [p for p in self.selected if self._item_at(*p) is not None]
        self.selected = []
        if not picks:
            return

        from_pool = any(owner == "pool" for owner, _ in picks)
        if from_pool:
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
            if src != "pool":
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
            if u != "pool":
                u._derive_combat()
        dst._derive_combat()

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
        if self._lock_at(px) is not None:
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
        if event.type == pygame.MOUSEWHEEL:
            hit = next((u for r, u in self._pack_areas if r.collidepoint(self.mouse)), None)
            if hit is None and self._chest_area and self._chest_area.collidepoint(self.mouse):
                n = len(self.pool)
                self._chest_scroll = max(0, min(max(0, n - 1), self._chest_scroll - event.y))
                return
        super().handle_event(event)

    def _drop(self, px, dragging, src):
        if dragging:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            self.selected, self._sel_qty = [], {}
            return

        lock_hit = self._lock_at(px)
        if lock_hit is not None:
            lock_hit[0].toggle_lock(lock_hit[1])
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
                    self.on_done()
                elif key == "auto":
                    self._auto_pick()
                return

        mods = pygame.key.get_mods()
        if src is not None and mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL):
            if src in self.selected:
                self.selected.remove(src)
                if (src[0], src[1]) in self._sel_qty:
                    del self._sel_qty[(src[0], src[1])]
            else:
                self.selected.append(src)
            return

        if self.selected:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            elif src in self.selected:
                self.selected.remove(src)
                if (src[0], src[1]) in self._sel_qty:
                    del self._sel_qty[(src[0], src[1])]
            elif src is not None:
                self.selected = [src]
                self._sel_qty = {}
            else:
                self.selected = []
                self._sel_qty = {}
            return

        self.selected = [src] if src is not None else []
        self._sel_qty = {}

    def _bump_qty(self, loc, delta):
        if ("pool", loc) not in self.selected:
            self.selected.append(("pool", loc))
        name, total = self.pool[loc]
        cur = self._sel_qty.get(("pool", loc), total)
        if delta == 0:
            nxt = total
        else:
            nxt = max(1, min(total, cur + delta))
        self._sel_qty[("pool", loc)] = nxt

    def _run_service(self, key):
        if key == "auto":
            self._auto_pick()
        elif key == "done":
            self.on_done()
            
    def _auto_pick(self):
        flat_pool = []
        for name, qty in self.pool:
            flat_pool.extend([name] * qty)
            
        leftover = []
        for name in flat_pool:
            takers = sorted(self.survivors,
                            key=lambda m: m.carry_max - m.load, reverse=True)
            taken = False
            for m in takers:
                if m.load + data.item_weight(name) <= m.carry_max:
                    m.give_to_pack(name)
                    m._derive_combat()
                    taken = True
                    break
            if not taken:
                leftover.append(name)
        
        from collections import Counter
        self.pool = [(name, count) for name, count in Counter(leftover).items()]
        
        self.selected = []
        self._sel_qty = {}

    # ------------------------------------------------------------------ #
    # drawing                                                            #
    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._ui_fonts()
        screen.fill(T.TABLE)
        self.sources, self.zones, self.buttons = [], [], []
        self._chest_steppers, self._service_hits = [], []
        self._pack_areas, self._lock_hits = [], []
        self._chest_area = None

        W, H = screen.get_size()
        
        text(screen, F["titleb"], "LOOT", (T.S * 4, T.S * 4), T.BRASS)
        msg = f"{sum(qty for _, qty in self.pool)} items on the field  ·  ceiling = each one's max load  ·  drag to pack or hand"
        text(screen, F["body"], msg, (T.S * 4, T.S * 9), T.TX_FAINT)
        y = T.S * 14

        pad = T.S * 2
        chest_r = pygame.Rect(T.S * 4, y, CHEST_W, H - y - T.S * 4)
        self._draw_pool(screen, F, chest_r)

        avail_w = W - chest_r.right - pad - T.S * 4
        pinned = [u for u in self.pinned if u in self.survivors] or list(self.survivors)
        n_cols = max(1, len(pinned))
        col_w = max(COL_MIN, min(COL_MAX, (avail_w - pad * (n_cols - 1)) // n_cols))

        cx = chest_r.right + pad
        for u in pinned:
            r = pygame.Rect(cx, y, col_w, H - y - T.S * 4)
            self._draw_member(screen, F, r, u)
            cx += col_w + pad



        set_pointer(self._hovering())

    def _hovering(self):
        if any(r.collidepoint(self.mouse) for _, r in self.buttons):
            return True
        if any(r.collidepoint(self.mouse) for r, *_ in self.sources):
            return True
        if any(r.collidepoint(self.mouse) for r, *_ in self._service_hits):
            return True
        if any(r.collidepoint(self.mouse) for r, *_ in self._lock_hits):
            return True
        return False

    def _draw_pool(self, screen, F, rect):
        rows_data = []
        for i, (name, qty) in enumerate(self.pool):
            tag = self._item_tag(name)
            wt = data.item_weight(name)
            sel = ("pool", i) in self.selected
            sq = self._sel_qty.get(("pool", i), qty) if sel else 0
            rows_data.append((i, name, tag, wt, qty, None, None, None, sq))

        lbl = "DONE" if not self.pool else "LEAVE THE REST AND GO"
        data_ = {
            "label": "FIELD LOOT",
            "capacity": None,
            "rows": rows_data,
            "services": [
                ("auto", "TAKE WHAT FITS", "auto-distribute to packs", bool(self.pool)),
                ("done", lbl, "", True)
            ]
        }

        res = loadout_panel.container_panel(screen, F, rect, data_, self._chest_scroll, self.mouse)
        self._chest_scroll = res["scroll"]
        


        for r, i in res["row_hits"]:
            self.sources.append((r, "pool", i))
            
        for i, hits in res["row_controls"].items():
            for key in ("minus", "plus", "all"):
                if hits.get(key):
                    delta = -1 if key == "minus" else 1 if key == "plus" else 0
                    self._chest_steppers.append((hits[key], i, delta))

        for r, key in res["service_hits"]:
            self._service_hits.append((r, key))

        self.zones.append((rect, "pool", "pack"))
        
        self._chest_area = pygame.Rect(rect.x + T.S * 2, rect.y + T.S * 8, rect.w - T.S * 4, rect.h - T.S * 8 - T.S * 10)

    def _draw_member(self, screen, F, r, u):
        def _slot(kind):
            name = getattr(u, f"equipped_{kind}")
            if name is None:
                return {"name": "", "note": "", "accepts": True, "sel": (u, kind) in self.selected}
            sel = (u, kind) in self.selected
            return {"name": name, "note": self._item_tag(name), "accepts": True, "sel": sel}

        two_handed = bool(u.equipped_weapon) and data.WEAPONS[u.equipped_weapon]["hands"] >= 2
        member = {
            "key": u.uid,
            "name": u.name + (" (Stabilized)" if getattr(u, "hp", 1) <= 0 else ""),
            "role": getattr(u.occupation, "id", "sword"),
            "pending_picks": bool(getattr(u, "pending_picks", False)),
            "kg": u.load,
            "cap": u.carry_max,
            "slots": {
                "hand": _slot("weapon"),
                "offhand": None if two_handed else _slot("offhand"),
                "tongue": _slot("tongue") if u.has_tongue else None,
                "armor": _slot("armor")
            },
            "pack": []
        }

        for i, (name, qty) in enumerate(u._base_inventory):
            sel = (u, i) in self.selected
            locked = name in getattr(u, "locked_items", set())
            member["pack"].append((name, self._item_tag(name), data.item_weight(name), qty, locked, sel))

        res = loadout_panel.column(screen, F, r, member, self._pack_scroll.get(id(u), 0), self.mouse)
        
        if res.get("sheet_rect"):
            self.zones.append((res["sheet_rect"], u, "pack"))
        for kind, s_rect in res.get("slot_rects", {}).items():
            if s_rect:
                self.zones.append((s_rect, u, kind))
                self.sources.append((s_rect, u, kind))
        if res.get("pack_area"):
            self._pack_areas.append((res["pack_area"], u))
            self.zones.append((res["pack_area"], u, "pack"))
        for p_rect, i in res.get("pack_hits", []):
            self.sources.append((p_rect, u, i))
        for l_rect, i in res.get("lock_hits", []):
            item_name = u._base_inventory[i][0]
            self._lock_hits.append((l_rect, u, item_name))
            
        self._pack_scroll[id(u)] = res["scroll"]

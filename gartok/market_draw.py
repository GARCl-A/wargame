"""Everything the Market screen paints: the shoppers' columns, the shelf, the cargo, the status
line and the footer (`MarketDrawMixin`, mixed into `MarketScreen`)."""

import pygame

from . import economy, items, store_column, world
from .constants import fmt_money
from .ui import loadout_panel, market_panel
from .ui.primitives import draw_button, draw_tooltip, format_tooltip, set_pointer
from .ui.primitives import text as ui_text
from .ui.tokens import T
from .ui.vendor_panel import draw_vendor, draw_vendor_name

STOCK_W = 412
MARGIN = T.S * 2


class MarketDrawMixin:
    def draw(self, screen):
        F = self._ui_fonts()
        screen.fill(T.TABLE)
        self.tooltip = None
        self.lock_hits = []
        self._dots_hits = []
        self.item_rows = []
        self.cards = []
        self.buttons = []
        self.info_hits = []
        self._pack_areas = []
        self.zones = []
        W, H = screen.get_size()

        keeper = world.vendor(self.node.id, self.vendor_function)
        card = keeper.card if keeper else None
        tx = MARGIN + draw_vendor(screen, F, (MARGIN, MARGIN - 4), card)
        title = ui_text(screen, F["head"], self.node.name.upper(), (tx, MARGIN - 2), T.TX)
        draw_vendor_name(screen, F, (title.right + T.S * 2, title.y + 6), card)
        has_tut = self.tutorial_key() is not None
        purse_x = W - MARGIN - (28 + T.S if has_tut else 0) - self.header_reserve
        ui_text(screen, F["body_sm"], f"common purse: {fmt_money(self.purse)}",
                (purse_x, MARGIN + 2), T.BRASS, right=True)
        cash = self._cash()
        if cash is not None:
            ui_text(screen, F["body_sm"], f"shop can pay: {fmt_money(cash)}",
                    (purse_x, MARGIN + 24), T.TX_FAINT, right=True)
        msg, col = self._status_line()
        ui_text(screen, F["body"], msg, (tx, MARGIN + 30), col)

        top = MARGIN + 62
        cats = [(label, key) for label, key, _names in self.get_categories()]
        self.tab_hits = market_panel.category_tabs(
            screen, F, pygame.Rect(MARGIN, top, STOCK_W, 28), cats, self.tab, self.mouse)
        btn_x = W - MARGIN
        if len(self.shoppers) > 1:
            dl_btn = pygame.Rect(btn_x - 160, top, 160, 28)
            draw_button(screen, F, dl_btn, "distribute load", mpos=self.mouse)
            self.buttons.append(("distribute", dl_btn))
            btn_x = dl_btn.x - T.S
        if len(self.shoppers) + len(self.stores) > 1:
            gv_btn = pygame.Rect(btn_x - 160, top, 160, 28)
            draw_button(screen, F, gv_btn, "per member" if self.group_view else "all items", mpos=self.mouse)
            self.buttons.append(("group_view", gv_btn))

        body_top = top + 28 + T.S
        stock = pygame.Rect(MARGIN, body_top, STOCK_W, H - body_top - 72)
        hits = market_panel.stock_list(screen, F, stock, self._stock_data(), self.mouse)
        self.stock_rows = hits["rows"]
        self.qty_hits = [(r, ("stock", name), delta) for r, name, delta in hits["qty_hits"]]
        self.size_hits = hits["size_hits"]
        self.header_size_hits = hits["header_size_hits"]
        if hits["hovered"]:
            self.tooltip = self._item_tooltip(hits["hovered"], F)

        self._draw_shoppers(screen, pygame.Rect(stock.right + MARGIN, body_top,
                                                W - stock.right - 2 * MARGIN, stock.h))
        self._draw_footer(screen)

        names = self._selected_names()
        if self._dragging and names:
            market_panel.drag_ghost(screen, F, self._pick_label(names), self.mouse)

        if not self.selected:
            for r, member, loc in self.item_rows:
                if r.collidepoint(self.mouse):
                    name = self._item_at(member, loc)
                    if name:
                        self.tooltip = self._item_tooltip(name, F)
                    break

        if self.tooltip and self.menu is None:
            draw_tooltip(screen, F, self.tooltip, self.mouse)

        self._draw_menu(screen)
        self.draw_sheet_modal(screen)
        set_pointer(self._hovering())

    def _hovering(self):
        if self.menu is not None or self.split_prompt is not None:
            return self._menu_hovering()
        if any(r.collidepoint(self.mouse) for _, r in self.buttons):
            return True
        if self._col_scroll.hovering(self.mouse):
            return True
        hot = (self.tab_hits, self.qty_hits, self.size_hits, self.header_size_hits, self._dots_hits,
               self.lock_hits, self.info_hits, self.item_rows, self.stock_rows)
        return any(h[0].collidepoint(self.mouse) for group in hot for h in group)

    @staticmethod
    def _item_tooltip(name, F):
        return format_tooltip(*items.item_tooltip(name), F)

    def _pick_label(self, names):
        if self._buying:
            q = self._buy_qty(names[0])
            return names[0] if q == 1 else f"{names[0]} ×{q}"
        return names[0] if len(names) == 1 else f"{len(names)} items"

    def _status_line(self):
        """The line under the title: what the current pick will do, or the
        party and its haggling when nothing is picked up."""
        names = self._selected_names()
        if not names:
            return f"{len(self.shoppers)} shopping  ·  {self._deal_note()}", T.TX_FAINT
        if self._buying:
            name = names[0]
            q = self._buy_qty(name)
            msg = (f"buy {self._pick_label(names)} ({economy.buy_price(name, self.deal) * q})"
                   "  ·  drop on a member")
        else:
            msg = (f"moving {self._pick_label(names)}  ·  drop on another member, or on SELL "
                   f"(+{self._sell_total()})")
        return msg + "  ·  click outside to cancel", T.BRASS

    def _stock_data(self):
        """The current tab's shelf in `market_panel.stock_list`'s shape."""
        names = next((c[2] for c in self.get_categories() if c[1] == self.tab), [])
        kind = self.tab if self.tab in ("weapons", "armor") else "kit"
        rows = []
        for base_name in names:
            name = self._active_stock_name(base_name)
            price = economy.buy_price(name, self.deal)
            stock = self._stock_of(name)
            sold_out = stock is not None and stock <= 0
            rows.append({
                "name": name, "base_name": base_name,
                "spec": "" if kind == "kit" else self._stock_spec(name),
                "price": price, "base_price": economy.buy_price(name),
                "weight": items.item_weight(name),
                "stock": stock,
                "afford": self.purse >= price and not sold_out,
                "fits": any(self._fits(m, name) for m in (*self.shoppers, *self.stores)),
                "sel": ("stock", name) in self.selected,
                "tag": self._kit_tag(name) if kind == "kit" else "",
                "qty": self._buy_qty(name),
                "size": self._stock_weapon_size(base_name) if kind == "weapons" else None,
            })
        all_size = None
        if kind == "weapons":
            sizes = {self._stock_weapon_size(b) for b in names} or {"Medium"}
            all_size = sizes.pop() if len(sizes) == 1 else None
        return {"kind": kind, "all_size": all_size, "hover": not self.selected, "rows": rows}

    def _stock_spec(self, name):
        """The one-line stat blurb under a weapon / armor row."""
        w = items.get(name)
        if not w:
            return ""
        if w.type == items.ItemType.WEAPON:
            n, faces = w.damage
            hands = "2h" if w.hands >= 2 else "1h"
            rng = f"  ·  {w.range * 3 // 2}m" if w.range else ""
            return f"{n}d{faces}  ·  {hands}{rng}"
        if w.type == items.ItemType.ARMOR:
            cap = "no dex cap" if w.max_dex is None else f"dex cap {w.max_dex}"
            spd = f"  ·  -{w.speed_penalty} spd" if w.speed_penalty else ""
            return f"+{w.ac} AC  ·  {cap}{spd}"
        return ""

    @staticmethod
    def _kit_tag(name):
        return items.item_tag(name)

    def _draw_shoppers(self, screen, area):
        self._shoppers_area = area
        self._cargo_rect = None
        F = self._ui_fonts()
        gap = T.S * 2
        columns = [*self.shoppers, *self.stores]
        if self.group_view and not self._buying:
            self._draw_cargo(screen, F, area, columns)
            return

        window, card_w = self._col_scroll.fit(len(columns), area.w, gap, 300, 420)
        shown = columns[window]
        carried = self._selected_names()

        for i, m in enumerate(shown):
            r = pygame.Rect(area.x + i * (card_w + gap), area.y, card_w, area.h)
            store = store_column.is_store(m)
            if store:
                picked = {loc for o, loc in self.selected if o is m}
                member = store_column.store_dict(self.group, m, picked, carried)
            else:
                member = self._member_dict(m, carried)
            res = loadout_panel.column(screen, F, r, member, self._pack_scroll.get(id(m), 0), self.mouse)
            self._pack_scroll[id(m)] = res["scroll"]
            if not store:
                self.info_hits.append((res["sheet_rect"], m))

            for kind, slot_rect in res["slot_rects"].items():
                if slot_rect is None or store:
                    continue
                self.zones.append((slot_rect, m, kind))
                if member[kind]["name"]:
                    self.item_rows.append((slot_rect, m, kind))

            self.zones.append((res["pack_zone"], m, "pack"))
            self._pack_areas.append((res["pack_area"], m))

            for pr, idx in res["pack_hits"]:
                self.item_rows.append((pr, m, idx))
            if not store:
                for lr, idx in res["lock_hits"]:
                    self.lock_hits.append((lr, m, m._base_inventory[idx][0]))
            for dr, idx in res["dots_hits"]:
                self._dots_hits.append((dr, m, idx))

        self._col_scroll.hint(screen, F, area, self.mouse)

    def _draw_cargo(self, screen, F, area, owners):
        rows = []
        for o in owners:
            for idx, (name, qty) in enumerate(o._base_inventory):
                rows.append((o, idx, name, qty))
        rows.sort(key=lambda t: -items.item_weight(t[2]) * t[3])
        by_key = {id(o): o for o in owners}
        data = [((id(o), idx), name, self._pack_tag(o, name), items.item_weight(name), qty,
                 o.locked_of(name) > 0, (o, idx) in self.selected, o.name.split()[0][:10])
                for o, idx, name, qty in rows]
        res = loadout_panel.cargo_table(screen, F, area, data, self._cargo_scroll, self.mouse)
        self._cargo_rect = res["list_rect"]
        self._cargo_scroll = res["scroll"]
        for r, (oid, idx) in res["hits"]:
            self.item_rows.append((r, by_key[oid], idx))
        for r, (oid, idx) in res["lock_hits"]:
            o = by_key[oid]
            self.lock_hits.append((r, o, o._base_inventory[idx][0]))
        for r, (oid, idx) in res["dots_hits"]:
            self._dots_hits.append((r, by_key[oid], idx))

    def _draw_footer(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        
        done_r = pygame.Rect(T.S * 2, H - T.S * 8, T.S * 25, T.S * 4)
        draw_button(screen, F, done_r, "back to guild", primary=True, mpos=self.mouse)
        self.buttons.append(("done", done_r))

        names = self._selected_names()
        if not self._buying and any(not items.is_coin(n) for n in names):
            sell_r = pygame.Rect(0, 0, T.S * 25, T.S * 4)
            sell_r.center = (W // 2, H - T.S * 8 + T.S * 2)
            draw_button(screen, F, sell_r, f"SELL FOR {fmt_money(self._sell_total())}", mpos=self.mouse)
            self.buttons.append(("sell", sell_r))

        if not self._buying and self._marked():
            total = self._marked_total()
            marked_r = pygame.Rect(0, 0, T.S * 25, T.S * 4)
            marked_r.center = (W // 2 + T.S * 26, H - T.S * 8 + T.S * 2)
            draw_button(screen, F, marked_r, f"SELL MARKED (+{fmt_money(total)})" if total else "SELL MARKED",
                        enabled=bool(total), mpos=self.mouse)
            if total:
                self.buttons.append(("sell_marked", marked_r))

        if self.notice:
            ui_text(screen, F["body_sm"], self.notice, (T.S * 2, H - T.S * 10), T.BRASS)

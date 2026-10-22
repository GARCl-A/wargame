"""Everything the Market screen paints: the shelf and its cart, the party's cards and the cargo
table (`MarketDrawMixin`, mixed into `MarketScreen`)."""

import pygame

from . import economy, items, store_column
from .constants import fmt_money
from .ui import hub_party, loadout_panel, market_panel, shop_shelf
from .ui.hub_frame import MARGIN, button_width, hub_button
from .ui.primitives import (
    draw_tooltip,
    ellipsize,
    format_tooltip,
    set_pointer,
    small_caps,
)
from .ui.primitives import text as ui_text
from .ui.tokens import T


class MarketDrawMixin:
    """The shop tab's body inside its hub (`hub_screen.TabbedHubScreen` draws the keeper, the
    tabs and the back button): the shelf with its cart at the left, the party's cards at the
    right."""

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
        m = MARGIN
        shelf_w = round(max(T.S * 52, min(T.S * 70, W * 0.28)))
        shelf = pygame.Rect(m, 0, shelf_w, H)
        data = {**self._stock_data(), "cats": [(label.capitalize(), key) for label, key, _ in self.get_categories()],
                "cat": self.tab, "scroll": self._shelf_scroll, "foot": self._shelf_foot(),
                "drop": bool(self._goods(self.selected))}
        hits = shop_shelf.draw_shelf(screen, F, shelf, data, self.mouse)
        self._shelf_rect, self._shelf_list = hits["panel"], hits["list"]
        self._shelf_scroll = min(self._shelf_scroll, hits["max_scroll"])
        self._shelf_max = hits["max_scroll"]
        self.stock_rows = hits["rows"]
        self.qty_hits = [(r, ("stock", name), delta) for r, name, delta in hits["qty_hits"]]
        self.size_hits = hits["size_hits"]
        self.header_size_hits = hits["header_size_hits"]
        self.tab_hits = hits["cat_hits"]
        if hits["button"]:
            self.buttons.append((self._foot_action(), hits["button"]))
        if hits["hovered"]:
            self.tooltip = self._item_tooltip(hits["hovered"], F)

        party = pygame.Rect(shelf.right + T.S * 3 + 4, 0, W - m - (shelf.right + T.S * 3 + 4), H)
        self._draw_party_head(screen, F, party)
        self._draw_shoppers(screen, pygame.Rect(party.x, T.S * 8, party.w, H - T.S * 8))

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

    def _draw_party_head(self, screen, F, area):
        title = small_caps(screen, F["hub_head"], F["hub_head_sc"], "Party", (area.x, T.S + 2), T.TX)
        line, color = (self.notice, T.BRASS) if self.notice else             (f"{len(self.shoppers)} shopping  ·  drag items between packs", T.TX_MUTED)
        x = area.right
        actions = []
        if len(self.shoppers) > 1:
            actions.append(("distribute", "distribute load"))
        if len(self.shoppers) + len(self.stores) > 1:
            actions.append(("group_view", "per member" if self.group_view else "all items"))
        for key, label in actions:
            r = pygame.Rect(0, 0, button_width(F, label), T.S * 5 + 4)
            r.topright = (x, 0)
            hub_button(screen, F, r, label, mpos=self.mouse)
            self.buttons.append((key, r))
            x = r.x - T.S + 4
        ui_text(screen, F["hub_body"], ellipsize(line, F["hub_body"], x - title.right - T.S * 4),
                (title.right + T.S * 2, title.y + 6), color)

    def _shelf_foot(self):
        """The shelf's footer: the cart and BUY, the picked pack items and SELL, or the
        auto-sell when nothing is picked."""
        purse = self.purse
        if self._buying:
            cart = [(n, self._buy_qty(n)) for kind, n in self.selected if kind == "stock"]
            total = sum(economy.buy_price(n, self.deal) * q for n, q in cart)
            kg = sum(items.item_weight(n) * q for n, q in cart)
            what = ", ".join(f"{q} {n}" for n, q in cart)
            ok = purse >= total
            return {"left": f"Cart · {what} · {kg:.1f} kg", "right": ("Purse after:", fmt_money(purse - total)),
                    "right_bad": not ok, "button": f"buy for {fmt_money(total)}" if ok else "not enough copper",
                    "primary": True, "enabled": ok}
        goods = self._goods(self.selected)
        if goods:
            total = self._sell_total()
            what = ", ".join(f"{self._get_qty(p)} {self._name_of(p)}" for p in goods)
            owners = list(dict.fromkeys(p[0].name.split()[0] for p in goods))
            return {"left": f"Selling · {what} from {', '.join(owners)}",
                    "right": ("Purse after:", fmt_money(purse + total)),
                    "button": f"sell for {fmt_money(total)}", "primary": True}
        marked = sorted(self._marked())
        if not marked:
            return {"left": "Auto-sell · mark a kind from a pack's ⋮ menu", "button": "sell marked",
                    "enabled": False}
        picks, _qty = self._marked_stock()
        total = self._marked_total()
        return {"left": f"Auto-sell · {', '.join(marked)} marked",
                "right": ("", f"{len(picks)} stack{'' if len(picks) == 1 else 's'} in the packs"),
                "button": f"sell marked for {fmt_money(total)}" if total else "sell marked",
                "enabled": bool(total)}

    def _foot_action(self):
        if self._buying:
            return "buy_cart"
        return "sell" if self._goods(self.selected) else "sell_marked"

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

    def _stock_data(self):
        """The current tab's shelf in `shop_shelf.draw_shelf`'s row shape."""
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
            res = hub_party.member_card(screen, F, r, member, self._pack_scroll.get(id(m), 0), self.mouse)
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

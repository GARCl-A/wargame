"""Market: buy and sell gear for money.

The shopping party's coin counts as one **common purse** (the guild has no
treasury) and the members' packs sit side by side, so you can shift items and
spend freely without per-character fiddling. The purse is just the members' real
Copper Coin stacks added up: a purchase is paid out of them in proportion to what
each carries, and a sale pays the coin straight into the seller's own pack.
Coins move between members like any other item.

The stock is split into **category tabs** -- WEAPONS / ARMOR / CONSUMABLES & KIT
(`economy.market_categories`) -- each with a column layout tuned to what matters
for that shelf (damage and hands for weapons, AC and the Dexterity cap for armor,
a quantity stepper for the stackable kit).

Interaction (same as the guild screen): drag an item where it goes, or click to
pick it up and click the destination. Shift/ctrl-click gathers several of a
shopper's items for one move.
- a stock row  -> drop on a shopper to buy it into their pack (the kit tab buys
  the stepper's quantity in one drop); needs purse >= price and room under the
  carry max;
- a shopper's item -> drop on another shopper to hand it over, or on the SELL bar
  to sell it back (at `economy.sell_price`, always a loss) -- the market pays out of
  its own cash (`Guild.shop(node_id).cash`): what you spend goes in, what you sell comes
  out, a day refills it, and a sale above what it holds is refused;
- drop on nothing / click away to cancel.
"""

import pygame

from . import economy, items
from .constants import fmt_money
from .data import role_for
from .dragselect import DragSelectMixin
from .market_draw import MarketDrawMixin
from .packbox import ItemMenuMixin, PackColumnMixin
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .trade import Counter
from .ui.hscroll import ColumnScroll
from .ui.tokens import fonts as ui_fonts


class MarketScreen(MarketDrawMixin, ItemMenuMixin, PackColumnMixin, DragSelectMixin, SheetModalMixin, Screen,
                   Counter):
    """The window over `trade.Counter`: the rules are the counter's, this is the drawing and the mouse."""

    framed = True           # drawn for a hub's frame (`hub_screen.TabbedHubScreen`)
    native = True

    def __init__(self, fonts, guild, shoppers, node, on_done):
        super().__init__()
        Counter.__init__(self, guild, shoppers, node)     # Screen ends the cooperative chain
        self.fonts = fonts
        self.on_done = on_done
        self.tab = self.get_categories()[0][1]     # "weapons"
        self.weapon_size = "Large" if any(items.weapon_size(n) == "Large"
                                          for n in economy.targets_of(self._node_id())) else "Medium"
        self._weapon_sizes = {}              # base_name -> "Medium" | "Large"
        self.size_hits = []                  # [(rect, base_name, size)]
        self.header_size_hits = []           # [(rect, size)]
        self._F = None
        self.zones = []
        self.stock_rows = []                 # [(rect, name)]
        self.qty_hits = []                   # [(rect, name, delta)]
        self.lock_hits = []                  # [(rect, member, name)]
        self._dots_hits = []                 # [(rect, member, idx)] -- the pack row's menu button
        self.info_hits = []                  # [(rect, member)] -- the card's 'i' disc opens the sheet
        self._pack_scroll = {}               # id(member) -> stacks scrolled past in the pack list
        self._pack_areas = []                # [(rect, member)] -- pack list rects, for wheel hit-testing
        self.tab_hits = []                  # [(rect, key)]
        self.item_rows = []                  # [(rect, member, loc)]
        self.cards = []                      # [(rect, member)]
        self.buttons = []                   # [(key, rect)]
        self._col_scroll = ColumnScroll()
        self._shoppers_area = pygame.Rect(0, 0, 0, 0)
        self.group_view = False             # one table of every stack instead of a column per member
        self._cargo_scroll = 0
        self._cargo_rect = None
        self._shelf_scroll = 0                # shelf rows scrolled past
        self._shelf_max = 0
        self._shelf_rect = None              # the FOR SALE panel: drop pack items on it to sell
        self._shelf_list = None

    def _stock_weapon_size(self, base_name):
        return self._weapon_sizes.get(base_name, self.weapon_size)

    def _active_stock_name(self, base_name):
        if self.tab == "weapons" and not base_name.startswith("Large "):
            if self._stock_weapon_size(base_name) == "Large":
                large_name = f"Large {base_name}"
                if items.get(large_name):
                    return large_name
        return base_name

    def _set_weapon_size(self, base_name, size):
        self._weapon_sizes[base_name] = size
        med_name = base_name
        lrg_name = f"Large {base_name}"
        old_name = med_name if size == "Large" else lrg_name
        new_name = lrg_name if size == "Large" else med_name
        if ("stock", old_name) in self.selected:
            self.selected = [("stock", new_name) if p == ("stock", old_name) else p for p in self.selected]

    def _set_all_weapon_sizes(self, size):
        self.weapon_size = size
        cats = self.get_categories()
        wpn_names = next((names for lbl, key, names in cats if key == "weapons"), [])
        for b in wpn_names:
            self._set_weapon_size(b, size)

    # ------------------------------------------------------------------ #
    # tutorial (screen.py)                                               #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "market"

    # ------------------------------------------------------------------ #
    def _ui_fonts(self):
        if getattr(self, "_F", None) is None:
            self._F = ui_fonts()
        return self._F

    def _hand_note(self, unit):
        name = unit.equipped_weapon
        w = items.get(name)
        if not name or not items.is_weapon(w):
            return None
        hit_bonus, _ = unit.attack_bonus
        dn, faces = w.damage
        dmg = f"{dn}d{faces}"
        if (w.range == 0 or (w.has_trait("thrown") if hasattr(w, "has_trait") else getattr(w, "thrown", 0))) and unit.mod_strength:
            dmg += f"{unit.mod_strength:+}"
        return f"{hit_bonus:+}  ·  {dmg}"

    @staticmethod
    def _armor_note(unit):
        name = unit.equipped_armor
        a = items.get(name)
        if not name or not items.is_armor(a):
            return None
        return items.armor_note(a)

    def _member_dict(self, unit, carried):
        w = items.get(unit.equipped_weapon)
        two_handed = bool(w) and w.hands >= 2
        selected_locs = {loc for u, loc in self.selected if u is unit and u != "stock"}

        def held(kind, name, note):
            return {"name": name, "note": note, "sel": kind in selected_locs,
                    "accepts": bool(carried) and any(self._fits_slot(unit, kind, n) for n in carried)}

        member = {
            "name": unit.full_name, "role": role_for(unit.occupation),
            "pending_picks": bool(unit.pending_picks),
            "kg": unit.load, "normal": unit.carry_normal, "max": unit.carry_max,
            "hand": held("hand", unit.equipped_weapon, self._hand_note(unit)),
            "offhand": None if two_handed else held("offhand", unit.equipped_offhand, None),
            "armor": held("armor", unit.equipped_armor, self._armor_note(unit)),
            "pack": [(name, self._pack_tag(unit, name), items.item_weight(name), qty,
                     unit.locked_of(name) > 0, idx in selected_locs)
                    for idx, (name, qty) in enumerate(unit._base_inventory)],
        }
        if unit.has_tongue:
            member["tongue"] = held("tongue", unit.equipped_tongue, None)
        member["artifact"] = held("artifact", unit.equipped_artifact, None)
        return member

    def _pack_tag(self, owner, name):
        tag = owner.pack_tag(name)
        return f"{tag} · AUTO-SELL" if name in self._marked() else tag

    def _selected_names(self):
        return [n for n in (self._name_of(p) for p in self.selected) if n is not None]

    @property
    def _buying(self):
        return bool(self.selected) and self.selected[0][0] == "stock"

    def _select_one(self, src):
        """Replace the current selection with just `src` (a plain click) --
        a fresh pack pick starts at qty 1, matching a single click grabbing
        one item; shift/ctrl and the stepper grow it from there."""
        self.selected = [src] if src is not None else []
        self._sel_qty = {}
        if src is not None and src[0] != "stock" and not isinstance(src[1], str):
            self._sel_qty[src] = 1

    def hub_cards(self):
        """The hub header's cards for the shop: the deal, the party's purse, the till."""
        deal = self._deal_card()
        cards = [{"label": "your deal", "value": deal["headline"].capitalize(), "sub": "  ·  ".join(deal["why"]),
                  "tone": deal["tone"] if deal["tone"] != "none" else None, "warm": True},
                 {"label": "party purse", "value": fmt_money(self.purse), "tone": "money"}]
        cash = self._cash()
        if cash is not None:
            cards.append({"label": "shop can pay", "value": fmt_money(cash)})
        return cards

    # ------------------------------------------------------------------ #
    # input: click / shift-click to (multi-)select, or drag onto a card  #
    # (the press/drag machinery lives in DragSelectMixin)                #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
        if self._dots_at(px) is not None:
            return None                      # a menu button press starts no drag / select
        for rect, _name, _delta in self.qty_hits:
            if rect.collidepoint(px):
                return None                  # a stepper press starts no drag / select
        for rect, _member, _name in self.lock_hits:
            if rect.collidepoint(px):
                return None                  # a padlock press starts no drag / select
        for rect, _base_name, _size in self.size_hits:
            if rect.collidepoint(px):
                return None                  # a size toggle press starts no drag / select
        for rect, _size in self.header_size_hits:
            if rect.collidepoint(px):
                return None                  # a header size toggle starts no drag / select
        for rect, name in self.stock_rows:
            if rect.collidepoint(px):
                return ("stock", name)
        for rect, member, loc in self.item_rows:
            if rect.collidepoint(px):
                return (member, loc)
        return None

    def _begin_drag(self, src):
        mods = pygame.key.get_mods()
        if mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL):
            if src not in self.selected and src[0] != "stock":
                self.selected.append(src)
                owner, loc = src
                if not isinstance(loc, str):
                    held = owner._base_inventory[loc][1] if loc < len(owner._base_inventory) else 0
                    self._sel_qty[src] = held
            return
        if src not in self.selected:
            self.selected = [src]           # a cart row dragged takes the whole cart along

    def handle_event(self, event):
        if self._menu_event(event):
            return
        if event.type == pygame.MOUSEWHEEL:
            hy = getattr(event, 'y', 0)
            if self._col_scroll.wheel(event, over=False):
                return

            hit = next((m for r, m in self._pack_areas if r.collidepoint(self.mouse)), None)
            if hit is not None:
                n = len(self._stacks(hit._base_inventory))
                cur = self._pack_scroll.get(id(hit), 0)
                self._pack_scroll[id(hit)] = max(0, min(n - 1, cur - hy))
                return

            if self._shelf_list is not None and self._shelf_list.collidepoint(self.mouse):
                self._shelf_scroll = max(0, min(self._shelf_max, self._shelf_scroll - hy))
                return
            if self._cargo_rect is not None and self._cargo_rect.collidepoint(self.mouse):
                self._cargo_scroll = max(0, self._cargo_scroll - hy * 40)
                return
            if self._shoppers_area.collidepoint(self.mouse) and self._col_scroll.wheel(event):
                return

        super().handle_event(event)

    def _bump_qty(self, pick, delta):
        step = delta * (5 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1)
        if pick[0] == "stock":
            name = pick[1]
            self.qty[name] = max(1, self._buy_qty(name) + step)
            return

        held = self._held_qty(pick)
        new_qty = held if delta >= 999 else max(0, min(held, self._sel_qty.get(pick, 0) + step))
        if new_qty <= 0:
            self._sel_qty.pop(pick, None)
            self.selected = [p for p in self.selected if p != pick]
        else:
            self._sel_qty[pick] = new_qty
            if pick not in self.selected:
                self.selected.append(pick)

    def _menu_picks_for(self, pick):
        if pick[0] == "stock":
            return []
        if pick in self.selected and len(self.selected) > 1:
            return [p for p in self.selected if p[0] != "stock"]
        return [pick]

    def _menu_rows(self, picks):
        picks = [p for p in picks if not isinstance(p[1], str) and p[1] < len(p[0]._base_inventory)]
        if not picks:
            return []
        owners = {id(p[0]) for p in picks}
        dests = [("member", f"to {m.name}", m) for m in (*self.shoppers, *self.stores)
                 if len(owners) > 1 or id(m) not in owners]
        if len(picks) > 1:
            total = sum(economy.sell_price(self._name_of(p), self.deal) * self._get_qty(p)
                        for p in self._goods(picks))
            sell = [("sell_sel", f"sell selected  (+{fmt_money(total)})", None)] if total else []
            return sell + dests
        member, loc = picks[0]
        name, qty = member._base_inventory[loc]
        if items.is_coin(name):
            return dests
        each = economy.sell_price(name, self.deal)
        rows = [("sell", f"sell all x{qty}  (+{fmt_money(each * qty)})" if qty > 1 else f"sell  (+{fmt_money(each)})", qty)]
        if qty > 1:
            rows.insert(0, ("sell", f"sell 1  (+{fmt_money(each)})", 1))
        if self.guild is not None:
            rows.append(("mark", "unmark auto-sell" if name in self._marked() else "mark to auto-sell", name))
        return rows + dests

    def _menu_run(self, picks, kind, arg):
        if kind == "mark":
            self._toggle_marked(arg)
            return
        self.selected = list(picks)
        if kind == "sell":
            self._sel_qty = {picks[0]: arg}
        elif len(picks) == 1:
            self._sel_qty = {picks[0]: self._held_qty(picks[0])}
        if kind in ("sell", "sell_sel"):
            self._sell()
        else:
            self._drop_on_zone(arg, "pack")
            self._sel_qty = {}

    def _sell_all(self):
        """Grow every currently-picked pack stack to its full held quantity
        -- the stepper's own ALL, applied to the whole selection at once."""
        for p in list(self.selected):
            if p[0] != "stock":
                self._bump_qty(p, 999)
        self._sell()

    def _drop(self, px, dragging, src):
        if self.close_sheet_on_click():
            return

        if dragging:
            for rect, member, zone in self.zones:
                if rect.collidepoint(px):
                    self._drop_on_zone(member, zone)
                    return
            for key, rect in self.buttons:
                if key == "sell" and rect.collidepoint(px):
                    self._sell()
                    return
            if self._goods(self.selected) and self._shelf_rect is not None and self._shelf_rect.collidepoint(px):
                self._sell()
            return

        if self._col_scroll.click(px):
            return

        for rect, pick, delta in self.qty_hits:
            if rect.collidepoint(px):
                self._bump_qty(pick, delta)
                return

        pick = self._dots_at(px)
        if pick is not None:
            self._open_menu(px, self._menu_picks_for(pick))
            return

        for rect, member, name in self.lock_hits:
            if rect.collidepoint(px):
                member.toggle_lock(name)
                return

        for rect, base_name, size in self.size_hits:
            if rect.collidepoint(px):
                self._set_weapon_size(base_name, size)
                return

        for rect, size in self.header_size_hits:
            if rect.collidepoint(px):
                self._set_all_weapon_sizes(size)
                return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "done":
                    self._checkout()
                elif key == "buy_cart":
                    self._buy_cart()
                elif key == "sell":
                    self._sell()
                elif key == "sell_all":
                    self._sell_all()
                elif key == "sell_marked":
                    self._sell_marked()
                elif key == "distribute":
                    self._distribute_load()
                elif key == "group_view":
                    self.group_view = not self.group_view
                    self.selected = []
                    self._sel_qty = {}
                return

        for rect, key in self.tab_hits:
            if rect.collidepoint(px):
                self.tab, self.selected, self.notice, self._shelf_scroll = key, [], None, 0
                return

        for rect, member in self.info_hits:
            if rect.collidepoint(px):
                self.open_sheet(member)
                return

        self.notice = None
        mods = pygame.key.get_mods()
        multi = not dragging and src is not None and src[0] != "stock" \
            and mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL) \
            and (not self.selected or self.selected[0][0] != "stock")
        if multi:
            owner, loc = src
            if src in self.selected:
                self.selected = [p for p in self.selected if p != src]
                self._sel_qty.pop(src, None)
            else:
                self.selected.append(src)
                if not isinstance(loc, str):
                    held = owner._base_inventory[loc][1] if loc < len(owner._base_inventory) else 0
                    self._sel_qty[src] = held
            return

        if not dragging and src is not None and src[0] == "stock" and self._buying:
            if src in self.selected:                       # the cart: a click adds a row or takes it out
                self.selected = [p for p in self.selected if p != src]
            else:
                self.selected.append(src)
            return

        if self.selected:
            for rect, member, zone in self.zones:
                if dragging and rect.collidepoint(px):
                    self._drop_on_zone(member, zone)
                    return
            if not dragging:
                self._select_one(src)
            return
        if not dragging:
            self._select_one(src)

    def _checkout(self):
        self.on_done()

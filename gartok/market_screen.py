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
  its own cash (`Guild.market_cash`): what you spend goes in, what you sell comes
  out, a day refills it, and a sale above what it holds is refused;
- drop on nothing / click away to cancel.
"""

import pygame

from . import economy, factions, items, recorder, store_column
from .constants import fmt_money
from .dragselect import DragSelectMixin
from .packbox import ItemMenuMixin, PackColumnMixin
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .ui import loadout_panel, market_panel
from .ui.inspector_panel import role_for
from .ui.primitives import draw_button, draw_tooltip, format_tooltip, set_pointer
from .ui.primitives import text as ui_text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

STOCK_W = 412
MARGIN = T.S * 2


class MarketScreen(economy.PartyPurse, ItemMenuMixin, PackColumnMixin, DragSelectMixin, SheetModalMixin, Screen):
    native = True
    header_reserve = 0      # px of the header's right edge a host (a hub's tabs) has taken

    def __init__(self, fonts, guild, shoppers, node, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.shoppers = shoppers
        self.node = node
        self.on_done = on_done
        # haggling: language + charisma + alignment (and talents) bend the prices;
        # the shopping group's leader speaks for it when they're eligible (see
        # economy._haggle_fraction). `self.deal` is a list of economy.PriceMod,
        # fed straight to buy/sell_price.
        group = guild.group_of(shoppers[0]) if guild and shoppers else None
        self.group = group
        self.stores = [*group.herd, *group.wagons] if group else []     # wagons and animals shop along
        self.deal = economy.deal_mods(shoppers, getattr(node, "language", None),
                                      getattr(node, "alignment", None),
                                      leader=group.leader if group else None)
        self.tab = self.get_categories()[0][1]     # "weapons"
        self.weapon_size = "Medium"
        self._weapon_sizes = {}              # base_name -> "Medium" | "Large"
        self.size_hits = []                  # [(rect, base_name, size)]
        self.header_size_hits = []           # [(rect, size)]
        self.qty = {}                        # kit tab: stock name -> quantity to buy
        self.selected = []                         # [("stock", name) | (member, "hand"|"offhand"|"armor"|idx), ...]
        self._sel_qty = {}                   # (member, idx) -> how much of that pack stack is picked
        self.notice = None
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

    def tutorial_badge_rect(self, size):
        W, H = size
        return pygame.Rect(W - MARGIN - 28, MARGIN - 4, 28, 28)

    def get_categories(self):
        return economy.market_categories()

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
        if (w.range == 0 or w.thrown) and unit.mod_strength:
            dmg += f" {unit.mod_strength:+}"
        return f"{hit_bonus:+} hit  ·  {dmg} dmg"

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
        return member

    def _fits_slot(self, dst, zone, name):
        if zone == "hand":
            return dst.can_wield(name)
        if zone == "offhand":
            return dst.fits_offhand(name)
        if zone == "tongue":
            return dst.fits_tongue(name)
        if zone == "armor":
            return dst.fits_armor(name)
        return True

    @staticmethod
    def _item_at(member, loc):
        if loc == "hand":
            return member.equipped_weapon
        if loc == "offhand":
            return member.equipped_offhand
        if loc == "armor":
            return member.equipped_armor
        return items.stack_name(member._base_inventory[loc]) if loc < len(member._base_inventory) else None

    def _take(self, member, loc):
        """Lift the pick at `loc` off `member` -- `(name, qty)`. A pack pick
        takes only what `self._sel_qty` says is selected (the stepper's
        partial-stack pick), not necessarily the whole stack; an equip slot
        is always qty 1."""
        if loc == "hand":
            return member.take_from_hand(), 1
        if loc == "offhand":
            return member.take_from_offhand(), 1
        if loc == "armor":
            return member.take_from_armor(), 1
        if loc >= len(member._base_inventory):
            return None, 0
        held = member._base_inventory[loc][1]
        qty = min(held, self._sel_qty.get((member, loc), held))
        if qty <= 0:
            return None, 0
        return member.take_from_pack(loc, qty), qty

    def _name_of(self, pick):
        if pick[0] == "stock":
            return pick[1]
        return self._item_at(*pick)

    def _goods(self, picks):
        """The picks that are pack items a shop would buy -- not stock rows, not coins."""
        return [p for p in picks if p[0] != "stock"
                and self._name_of(p) is not None and not items.is_coin(self._name_of(p))]

    def _sell_total(self):
        return sum(economy.sell_price(self._name_of(p), self.deal) * self._get_qty(p)
                   for p in self._goods(self.selected))

    def _selected_names(self):
        return [n for n in (self._name_of(p) for p in self.selected) if n is not None]

    @property
    def _buying(self):
        return bool(self.selected) and self.selected[0][0] == "stock"

    def _buy_qty(self, name):
        return max(1, self.qty.get(name, 1))

    def _get_qty(self, pick):
        if pick[0] == "stock":
            return self._buy_qty(pick[1])
        return min(self._held_qty(pick), self._sel_qty.get(pick, self._held_qty(pick)))

    def _held_qty(self, pick):
        """Full quantity of the pick's stack, ignoring any partial selection
        -- what the stepper's ALL grabs."""
        owner, loc = pick
        if isinstance(loc, str):
            return 1
        return owner._base_inventory[loc][1] if loc < len(owner._base_inventory) else 0

    def _select_one(self, src):
        """Replace the current selection with just `src` (a plain click) --
        a fresh pack pick starts at qty 1, matching a single click grabbing
        one item; shift/ctrl and the stepper grow it from there."""
        self.selected = [src] if src is not None else []
        self._sel_qty = {}
        if src is not None and src[0] != "stock" and not isinstance(src[1], str):
            self._sel_qty[src] = 1

    def _fits(self, member, name):
        return member.load + items.item_weight(name) <= member.carry_max

    def _stock_of(self, name):
        """Units of `name` left to buy, or None if unlimited -- also None with
        no `guild` (a few tests build a bare screen with no campaign behind it)."""
        guild = getattr(self, "guild", None)
        return economy.stock_of(guild.market_stock, name) if guild else None

    def _cash(self):
        """What the market can still pay out today, or None with no `guild`."""
        guild, node = getattr(self, "guild", None), getattr(self, "node", None)
        return guild.market_cash_at(node.id) if guild and node else None

    def _till(self, delta):
        guild, node = getattr(self, "guild", None), getattr(self, "node", None)
        if guild and node:
            guild.move_market_cash(node.id, delta)

    def _deal_note(self):
        """One-line summary of how the party's haggling moved the prices."""
        lang = getattr(self.node, "language", None)
        general = economy.deal_value(self.deal, None, "buy")
        food = economy.deal_value(self.deal, next(iter(items.food_items())), "buy")
        food_tag = (f"  ·  food -{round(food * 100)}%"
                    if round(food, 3) != round(general, 3) else "")
        if not lang:
            return f"resale at {int(economy.SELL_FACTOR * 100)}% of price"
        pct = round(general * 100)
        speaks = any(lang in m.languages for m in self.shoppers)
        if not speaks:
            return (f"no one speaks {lang}: no haggling "
                    f"(resale at {int(economy.SELL_FACTOR * 100)}%)" + food_tag)
        how = (f"{pct}% discount" if pct > 0
               else f"{-pct}% markup" if pct < 0 else "no margin")
        return f"vendor speaks {lang} · {self.node.alignment} · {how}{food_tag}"

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
        if src not in self.selected or src[0] == "stock":
            self.selected = [src]

    def handle_event(self, event):
        if self._menu_event(event):
            return
        if event.type == pygame.MOUSEWHEEL:
            mods = pygame.key.get_mods()
            is_shift = mods & pygame.KMOD_SHIFT
            
            hx = getattr(event, 'x', 0)
            hy = getattr(event, 'y', 0)
            
            if hx != 0 or (is_shift and hy != 0):
                scroll_amt = hx if hx != 0 else -hy
                max_scroll = getattr(self, "_shoppers_max_scroll", 0)
                if max_scroll > 0:
                    cur = getattr(self, "_shoppers_scroll", 0)
                    self._shoppers_scroll = max(0, min(max_scroll, cur + scroll_amt))
                return

            hit = next((m for r, m in self._pack_areas if r.collidepoint(self.mouse)), None)
            if hit is not None:
                n = len(self._stacks(hit._base_inventory))
                cur = self._pack_scroll.get(id(hit), 0)
                self._pack_scroll[id(hit)] = max(0, min(n - 1, cur - hy))
                return
            
            if getattr(self, "_shoppers_area", pygame.Rect(0,0,0,0)).collidepoint(self.mouse):
                max_scroll = getattr(self, "_shoppers_max_scroll", 0)
                if max_scroll > 0:
                    cur = getattr(self, "_shoppers_scroll", 0)
                    self._shoppers_scroll = max(0, min(max_scroll, cur - hy))
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
        return rows + dests

    def _menu_run(self, picks, kind, arg):
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
                elif key == "sell":
                    self._sell()
                elif key == "sell_all":
                    self._sell_all()
                elif key == "distribute":
                    self._distribute_load()
                return

        for rect, key in self.tab_hits:
            if rect.collidepoint(px):
                self.tab, self.selected, self.notice = key, [], None
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


    def _drop_on_zone(self, member, zone):
        picks, self.selected = self.selected, []
        picks = [p for p in picks if self._name_of(p) is not None]
        if not picks:
            self._sel_qty = {}
            return

        if picks[0][0] == "stock":
            self._sel_qty = {}
            self._buy(member, [name for _, name in picks], zone)
            return

        picks = [p for p in picks if not (p[0] is member and p[1] == zone)]
        if not picks:
            self._sel_qty = {}
            return

        add = sum(items.item_weight(self._name_of(p)) * self._get_qty(p) for p in picks)
        if zone == "pack" and member.load + add > member.carry_max:
            self.notice = f"won't fit {member.name}'s load."
            self.selected = picks
            return

        if zone in ("hand", "offhand", "tongue", "armor"):
            fit = next((p for p in picks if self._fits_slot(member, zone, self._name_of(p))), None)
            if fit is None:
                self.selected = picks
                self.notice = f"doesn't fit in {zone}."
                return
            picks = [fit]

        collected, touched = self._collect(picks)
        self._sel_qty = {}
        for name, qty in collected:
            if zone in ("hand", "offhand", "tongue", "armor"):
                src_unit = fit[0]
                if qty > 1:
                    src_unit.give_to_pack(name, qty - 1)
                if zone == "hand":
                    member.give_to_hand(name)
                elif zone == "offhand":
                    member.give_to_offhand(name)
                elif zone == "tongue":
                    member.give_to_tongue(name)
                elif zone == "armor":
                    member.give_to_armor(name)
            else:
                member.give_to_pack(name, qty)
                
        for u in touched:
            u._derive_combat()
        member._derive_combat()
        
        if zone == "pack":
            moved = sum(qty for _, qty in collected)
            self.notice = f"{moved} item(s) -> {member.name}."
        else:
            self.notice = f"{collected[0][0]} -> {member.name}'s {zone}."

    def _node_id(self):
        return getattr(getattr(self, "node", None), "id", None)

    def _settle_market(self):

        """Bankers deeds read the guild's lifetime market tallies straight off
        `guild.total_spent`/`items_sold_kinds` (`factions.py`) -- fire this
        after any buy or sell that could have just crossed one, and append a
        DEED line to `self.notice` the same way the tanner does."""
        for d in factions.settle(self.guild, factions.Event("market", node=self.node)):
            self.notice = (self.notice or "") + "  ·  " + factions.deed_notice(d)


    def _buy(self, member, names, zone="pack"):
        if zone in ("hand", "offhand", "tongue", "armor"):
            name = names[0]
            if not self._fits_slot(member, zone, name):
                self.notice = f"{name} won't fit {member.name}'s {zone}."
                return
            stock = self._stock_of(name)
            if stock is not None and stock <= 0:
                self.notice = f"no {name} in stock."
                return
            price = economy.buy_price(name, self.deal)
            if self.purse < price:
                self.notice = "out of money."
                return
            self.purse -= price
            self._till(price)
            self.guild.total_spent += price
            if stock is not None:
                self.guild.market_stock[name] = stock - 1

            if zone == "hand":
                member.give_to_hand(name)
            elif zone == "offhand":
                member.give_to_offhand(name)
            elif zone == "tongue":
                member.give_to_tongue(name)
            elif zone == "armor":
                member.give_to_armor(name)
            member._derive_combat()
            self.qty.pop(name, None)
            recorder.emit("buy", node=self._node_id(), item=name, qty=1, price=price, zone=zone)
            self.notice = f"{member.name} bought & equipped {name}."
            self._settle_market()
            return

        bought = 0
        paid = {}

        wanted = sum(self._buy_qty(n) for n in names)
        stopped = None
        for name in names:
            for _ in range(self._buy_qty(name)):
                stock = self._stock_of(name)
                if stock is not None and stock <= 0:
                    stopped = f"no {name} in stock"
                    break
                price = economy.buy_price(name, self.deal)
                if self.purse < price:
                    stopped = "out of money"
                    break
                if not self._fits(member, name):
                    stopped = f"{name} won't fit {member.name}'s load"
                    break
                self.purse -= price
                self._till(price)
                self.guild.total_spent += price
                member.give_to_pack(name)
                if stock is not None:
                    self.guild.market_stock[name] = stock - 1
                bought += 1
                paid[name] = paid.get(name, 0) + 1
            if stopped:
                break
        member._derive_combat()
        for name, qty in paid.items():
            recorder.emit("buy", node=self._node_id(), item=name, qty=qty,
                          price=economy.buy_price(name, self.deal), zone=zone)
        for name in names:
            self.qty.pop(name, None)             # reset the steppers after a buy
        what = names[0] if len(names) == 1 else "items"
        if bought and stopped:
            self.notice = f"{member.name} bought {bought} of {wanted}  ·  {stopped}."
        elif bought:
            self.notice = f"{member.name} bought {bought}× {what}."
        elif stopped:
            self.notice = f"{stopped[0].upper()}{stopped[1:]}."
        if bought:
            self._settle_market()

    def _sell(self):
        picks = self._goods(self.selected)
        cash = self._cash()
        if picks and cash is not None and self._sell_total() > cash:
            self.notice = f"the market only has {fmt_money(cash)} to pay with  ·  sell less."
            return
        self.selected = []
        if not picks:
            self._sel_qty = {}
            return
        by_owner = {}
        for p in picks:
            by_owner.setdefault(id(p[0]), (p[0], []))[1].append(p)
        total = sold = 0
        for owner, owner_picks in by_owner.values():
            collected, _ = self._collect(owner_picks)  # _take reads self._sel_qty -- clear after
            proceeds = sum(economy.sell_price(n, self.deal) * q for n, q in collected)
            payee = owner if hasattr(owner, "money") else self.shoppers[0]    # a wagon or animal has no purse
            payee.money += proceeds
            total += proceeds
            sold += sum(q for _, q in collected)
            for n, q in collected:
                recorder.emit("sell", node=self._node_id(), item=n, qty=q,
                              price=economy.sell_price(n, self.deal))
                stock = self._stock_of(n)
                if stock is not None:
                    self.guild.market_stock[n] = stock + q
                self.guild.items_sold_kinds.add(n)
            owner._derive_combat()
        self._sel_qty = {}
        self._till(-total)
        self.notice = f"sold {sold} item(s) for {total}."
        self._settle_market()

    def _purse_members(self):
        return self.shoppers

    def _checkout(self):
        self.on_done()

    # ------------------------------------------------------------------ #

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

        ui_text(screen, F["head"], "MARKET", (MARGIN, MARGIN - 2), T.TX)
        has_tut = self.tutorial_key() is not None
        purse_x = W - MARGIN - (28 + T.S if has_tut else 0) - self.header_reserve
        ui_text(screen, F["body_sm"], f"common purse: {fmt_money(self.purse)}",
                (purse_x, MARGIN + 2), T.BRASS, right=True)
        cash = self._cash()
        if cash is not None:
            ui_text(screen, F["body_sm"], f"market can pay: {fmt_money(cash)}",
                    (purse_x, MARGIN + 24), T.TX_FAINT, right=True)
        msg, col = self._status_line()
        ui_text(screen, F["body"], msg, (MARGIN, MARGIN + 30), col)

        top = MARGIN + 62
        cats = [(label, key) for label, key, _names in self.get_categories()]
        self.tab_hits = market_panel.category_tabs(
            screen, F, pygame.Rect(MARGIN, top, STOCK_W, 28), cats, self.tab, self.mouse)
        if len(self.shoppers) > 1:
            dl_btn = pygame.Rect(W - MARGIN - 160, top, 160, 28)
            draw_button(screen, F, dl_btn, "distribute load", mpos=self.mouse)
            self.buttons.append(("distribute", dl_btn))

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
        F = self._ui_fonts()
        gap = T.S * 2
        columns = [*self.shoppers, *self.stores]

        cap = max(1, (area.w + gap) // (300 + gap))
        n_shown = min(cap, len(columns))
        card_w = min(420, max(300, (area.w - (n_shown - 1) * gap) // n_shown)) if n_shown > 0 else 300

        self._shoppers_max_scroll = max(0, len(columns) - cap)
        cur = getattr(self, "_shoppers_scroll", 0)
        self._shoppers_scroll = max(0, min(cur, self._shoppers_max_scroll))

        shown = columns[self._shoppers_scroll : self._shoppers_scroll + n_shown]
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

        if self._shoppers_max_scroll > 0:
            hr = self._shoppers_max_scroll - self._shoppers_scroll
            hl = self._shoppers_scroll
            if hr > 0:
                ui_text(screen, F["body_sm"], f"{hr} more \u2192  (scroll)", (area.right - 8, area.bottom + 8), T.TX_FAINT, right=True)
            if hl > 0:
                ui_text(screen, F["body_sm"], f"\u2190 {hl} more  (scroll)", (area.x + 8, area.bottom + 8), T.TX_FAINT)

    def _distribute_load(self):

        from . import unit as unit_module
        unit_module.distribute_load(self.shoppers, share_coins=False)
        self.selected = []
        self.notice = "redistributed packs by carrying capacity."


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

        if self.notice:
            ui_text(screen, F["body_sm"], self.notice, (T.S * 2, H - T.S * 10), T.BRASS)

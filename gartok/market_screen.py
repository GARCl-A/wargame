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
from .dragselect import DragSelectMixin
from .market_draw import MARGIN, MarketDrawMixin
from .market_trade import MarketTradeMixin
from .packbox import ItemMenuMixin, PackColumnMixin
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .ui.hscroll import ColumnScroll
from .ui.inspector_panel import role_for
from .ui.tokens import fonts as ui_fonts


class MarketScreen(MarketTradeMixin, MarketDrawMixin, economy.PartyPurse, ItemMenuMixin, PackColumnMixin,
                   DragSelectMixin, SheetModalMixin, Screen):
    native = True
    header_reserve = 0      # px of the header's right edge a host (a hub's tabs) has taken
    vendor_function = "shop"  # which of the node's functions the keeper behind this stall serves

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
        self._col_scroll = ColumnScroll()
        self._shoppers_area = pygame.Rect(0, 0, 0, 0)
        self.group_view = False             # one table of every stack instead of a column per member
        self._cargo_scroll = 0
        self._cargo_rect = None

    def sync_group(self):
        if self.group is None:
            return
        self.shoppers = list(self.group.members)
        self.stores = [*self.group.herd, *self.group.wagons]
        self.deal = economy.deal_mods(self.shoppers, getattr(self.node, "language", None),
                                      getattr(self.node, "alignment", None),
                                      leader=self.group.leader)

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
        shop = self._shop()
        return economy.market_categories(self._node_id(), shop.strays() if shop else ())

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
            "pack": [(name, self._pack_tag(unit, name), items.item_weight(name), qty,
                     unit.locked_of(name) > 0, idx in selected_locs)
                    for idx, (name, qty) in enumerate(unit._base_inventory)],
        }
        if unit.has_tongue:
            member["tongue"] = held("tongue", unit.equipped_tongue, None)
        member["artifact"] = held("artifact", unit.equipped_artifact, None)
        return member

    def _fits_slot(self, dst, zone, name):
        if zone == "hand":
            return dst.can_wield(name)
        if zone == "offhand":
            return dst.fits_offhand(name)
        if zone == "tongue":
            return dst.fits_tongue(name)
        if zone == "artifact":
            return dst.fits_artifact(name)
        if zone == "armor":
            return dst.fits_armor(name)
        return True

    @staticmethod
    def _item_at(member, loc):
        if loc == "hand":
            return member.equipped_weapon
        if loc == "offhand":
            return member.equipped_offhand
        if loc == "tongue":
            return member.equipped_tongue
        if loc == "artifact":
            return member.equipped_artifact
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
        if loc == "tongue":
            return member.take_from_tongue(), 1
        if loc == "artifact":
            return member.take_from_artifact(), 1
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

    def _marked(self):
        return getattr(self.guild, "autosell", None) or set()

    def _pack_tag(self, owner, name):
        tag = owner.pack_tag(name)
        return f"{tag} · AUTO-SELL" if name in self._marked() else tag

    def _marked_stock(self):
        """`([(member, loc)], {pick: qty})` for every marked item the shoppers carry -- all of a
        stack but the padlocked part."""
        picks, qty = [], {}
        for member in self.shoppers:
            left = {n: member.unlocked_of(n) for n in self._marked()}
            for loc, (name, held) in enumerate(member._base_inventory):
                take = min(held, left.get(name, 0))
                if take > 0:
                    left[name] -= take
                    picks.append((member, loc))
                    qty[(member, loc)] = take
        return picks, qty

    def _marked_total(self):
        picks, qty = self._marked_stock()
        return sum(economy.sell_price(self._name_of(p), self.deal) * qty[p] for p in picks)

    def _sell_marked(self):
        picks, qty = self._marked_stock()
        if not picks:
            self.notice = "nothing marked for auto-sell in the packs."
            return
        self.selected, self._sel_qty = picks, qty
        self._sell()

    def _toggle_marked(self, name):
        marked = self.guild.autosell
        marked.symmetric_difference_update({name})
        self.notice = (f"{name}: will be sold with SELL MARKED." if name in marked
                       else f"{name}: no longer marked.")

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
        """Units of `name` left to buy, or None if the shop has no count -- also None with
        no `guild` (a few tests build a bare screen with no campaign behind it)."""
        shop = self._shop()
        return economy.stock_of(shop.stock, name) if shop else None

    def _cash(self):
        """What the market can still pay out today, or None with no `guild`."""
        shop = self._shop()
        return shop.cash if shop else None

    def _till(self, delta):
        shop = self._shop()
        if shop:
            shop.move_cash(delta)

    def _shop(self):
        guild, node = getattr(self, "guild", None), getattr(self, "node", None)
        return guild.shop(node.id) if guild and node else None

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
        tongues = " or ".join(economy.vendor_tongues(lang))
        if not any(economy.speaks_with(lang, m) for m in self.shoppers):
            return (f"no one speaks {tongues}: no haggling "
                    f"(resale at {int(economy.SELL_FACTOR * 100)}%)" + food_tag)
        how = (f"{pct}% discount" if pct > 0
               else f"{-pct}% markup" if pct < 0 else "no margin")
        return f"vendor speaks {tongues} · {self.node.alignment} · {how}{food_tag}"

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
            hy = getattr(event, 'y', 0)
            if self._col_scroll.wheel(event, over=False):
                return

            hit = next((m for r, m in self._pack_areas if r.collidepoint(self.mouse)), None)
            if hit is not None:
                n = len(self._stacks(hit._base_inventory))
                cur = self._pack_scroll.get(id(hit), 0)
                self._pack_scroll[id(hit)] = max(0, min(n - 1, cur - hy))
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


    def _distribute_load(self):

        from . import unit as unit_module
        unit_module.distribute_load(self.shoppers, share_coins=False)
        self.selected = []
        self.notice = "redistributed packs by carrying capacity."


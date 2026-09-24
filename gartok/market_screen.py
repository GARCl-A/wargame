"""Market: buy and sell gear for copper.

The shopping party pools its coin into one **common purse** for the visit (the
guild has no treasury) and the members' packs sit side by side, so you can shift
items and spend freely without per-character fiddling. On the way out the purse
is split back out proportional to what each shopper walked in with
(`economy.settle_pooled_purse`, the same rule the bank/property screens use) --
so nobody's relative wealth changes just from shopping together.

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
  to sell it back (at `economy.sell_price`, always a loss);
- drop on nothing / click away to cancel.
"""

import pygame

from . import data, economy, factions, icons
from .dragselect import DragSelectMixin
from .packbox import LOCK_W, PackColumnMixin
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, SURFACE_4, WARN, ellipsize, kg,
                    panel, section, token_badge, text, tracked)
from .ui import loadout_panel
from .ui.tokens import T, mix
from .ui.tokens import fonts as ui_fonts
from .ui.inspector_panel import role_for
from .ui.primitives import draw_button, caps, text as ui_text, hline

STOCK_W = 412


class MarketScreen(PackColumnMixin, DragSelectMixin, SheetModalMixin, Screen):
    native = True

    def __init__(self, fonts, guild, shoppers, node, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.shoppers = shoppers
        self.node = node
        self.on_done = on_done
        self._orig_gold = {m: m.gold for m in shoppers}   # snapshot, for the proportional settle on leaving
        self.purse = sum(self._orig_gold.values())   # pooled for the visit
        # haggling: language + charisma + alignment (and talents) bend the prices;
        # the shopping group's leader speaks for it when they're eligible (see
        # economy._haggle_fraction). `self.deal` is a list of economy.PriceMod,
        # fed straight to buy/sell_price.
        group = guild.group_of(shoppers[0]) if guild and shoppers else None
        self.deal = economy.deal_mods(shoppers, getattr(node, "language", None),
                                      getattr(node, "alignment", None),
                                      leader=group.leader if group else None)
        self.tab = self.get_categories()[0][1]     # "weapons"
        self.qty = {}                        # kit tab: stock name -> quantity to buy
        self.sel = []                         # [("stock", name) | (member, "hand"|"offhand"|"armor"|idx), ...]
        self._sel_qty = {}                   # (member, idx) -> how much of that pack stack is picked
        self.notice = None
        self._F = None
        self.zones = []
        self.stock_rows = []                 # [(rect, name)]
        self.qty_hits = []                   # [(rect, name, delta)]
        self.lock_hits = []                  # [(rect, member, name)]
        self.info_hits = []                  # [(rect, member)] -- the card's 'i' disc opens the sheet
        self._pack_scroll = {}               # id(member) -> stacks scrolled past in the pack list
        self._pack_areas = []                # [(rect, member)] -- pack list rects, for wheel hit-testing
        self.tab_hits = []                  # [(rect, key)]
        self.item_rows = []                  # [(rect, member, loc)]
        self.cards = []                      # [(rect, member)]
        self.buttons = []                   # [(key, rect)]

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "market"

    def get_categories(self):
        return economy.market_categories()

    # ------------------------------------------------------------------ #
    def _ui_fonts(self):
        if getattr(self, "_F", None) is None:
            self._F = ui_fonts()
        return self._F

    def _hand_note(self, unit):
        name = unit.equipped_weapon
        if not name or name not in data.WEAPONS:
            return None
        wd = data.WEAPONS[name]
        hit_bonus, _ = unit.attack_bonus
        dn, faces = wd["damage"]
        dmg = f"{dn}d{faces}"
        if (wd["range"] == 0 or wd["thrown"]) and unit.mod_strength:
            dmg += f" {unit.mod_strength:+}"
        return f"{hit_bonus:+} hit  ·  {dmg} dmg"

    @staticmethod
    def _armor_note(unit):
        name = unit.equipped_armor
        if not name or name not in data.ARMOR:
            return None
        ad = data.ARMOR[name]
        return f"+{ad['ac']} AC"

    def _member_dict(self, unit, carried):
        two_handed = bool(unit.equipped_weapon) and data.WEAPONS[unit.equipped_weapon]["hands"] >= 2
        selected_locs = {loc for u, loc in self.sel if u is unit and u != "stock"}

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
            "pack": [(name, self._item_tag(name), data.item_weight(name), qty,
                     unit.locked_of(name) > 0, idx in selected_locs)
                    for idx, (name, qty) in enumerate(unit._base_inventory)],
        }
        if unit.has_tongue:
            member["tongue"] = held("tongue", unit.equipped_tongue, None)
        return member

    def _fits_slot(self, dst, zone, name):
        if zone == "hand":
            return dst.is_weapon(name)
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
        return member._base_inventory[loc][0] if loc < len(member._base_inventory) else None

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

    def _selected_names(self):
        return [n for n in (self._name_of(p) for p in self.sel) if n is not None]

    @property
    def _buying(self):
        return bool(self.sel) and self.sel[0][0] == "stock"

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
        self.sel = [src] if src is not None else []
        self._sel_qty = {}
        if src is not None and src[0] != "stock" and not isinstance(src[1], str):
            self._sel_qty[src] = 1

    def _fits(self, member, name):
        return member.load + data.item_weight(name) <= member.carry_max

    def _stock_of(self, name):
        """Units of `name` left to buy, or None if unlimited -- also None with
        no `guild` (a few tests build a bare screen with no campaign behind it)."""
        guild = getattr(self, "guild", None)
        return economy.stock_of(guild.market_stock, name) if guild else None

    def _deal_note(self):
        """One-line summary of how the party's haggling moved the prices."""
        lang = getattr(self.node, "language", None)
        general = economy.deal_value(self.deal, None, "buy")
        food = economy.deal_value(self.deal, next(iter(data.FOOD_ITEMS)), "buy")
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
        for rect, _name, _delta in self.qty_hits:
            if rect.collidepoint(px):
                return None                  # a stepper press starts no drag / select
        for rect, _member, _name in self.lock_hits:
            if rect.collidepoint(px):
                return None                  # a padlock press starts no drag / select
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
            if src not in self.sel and src[0] != "stock":
                self.sel.append(src)
                owner, loc = src
                if not isinstance(loc, str):
                    held = owner._base_inventory[loc][1] if loc < len(owner._base_inventory) else 0
                    self._sel_qty[src] = held
            return
        if src not in self.sel or src[0] == "stock":
            self.sel = [src]

    def handle_event(self, event):
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
            self.sel = [p for p in self.sel if p != pick]
        else:
            self._sel_qty[pick] = new_qty
            if pick not in self.sel:
                self.sel.append(pick)

    def _sell_all(self):
        """Grow every currently-picked pack stack to its full held quantity
        -- the stepper's own ALL, applied to the whole selection at once."""
        for p in list(self.sel):
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

        for rect, member, name in self.lock_hits:
            if rect.collidepoint(px):
                member.toggle_lock(name)
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
                self.tab, self.sel, self.notice = key, [], None
                return

        for rect, member in self.info_hits:
            if rect.collidepoint(px):
                self.open_sheet(member)
                return

        self.notice = None
        mods = pygame.key.get_mods()
        multi = not dragging and src is not None and src[0] != "stock" \
            and mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL) \
            and (not self.sel or self.sel[0][0] != "stock")
        if multi:
            owner, loc = src
            if src in self.sel:
                self.sel = [p for p in self.sel if p != src]
                self._sel_qty.pop(src, None)
            else:
                self.sel.append(src)
                if not isinstance(loc, str):
                    held = owner._base_inventory[loc][1] if loc < len(owner._base_inventory) else 0
                    self._sel_qty[src] = held
            return

        if self.sel:
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
        picks, self.sel = self.sel, []
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

        add = sum(data.item_weight(self._name_of(p)) * self._get_qty(p) for p in picks)
        if zone == "pack" and member.load + add > member.carry_max:
            self.notice = f"won't fit {member.name}'s load."
            self.sel = picks
            return

        if zone in ("hand", "offhand", "tongue", "armor"):
            fit = next((p for p in picks if self._fits_slot(member, zone, self._name_of(p))), None)
            if fit is None:
                self.sel = picks
                self.notice = f"doesn't fit in {zone}."
                return
            picks = [fit]

        items, touched = self._collect(picks)
        self._sel_qty = {}
        for name, qty in items:
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
            moved = sum(qty for _, qty in items)
            self.notice = f"{moved} item(s) -> {member.name}."
        else:
            self.notice = f"{items[0][0]} -> {member.name}'s {zone}."

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
                self.notice = "out of copper."
                return
            self.purse -= price
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
            self.notice = f"{member.name} bought & equipped {name}."
            self._settle_market()
            return

        bought = 0

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
                    stopped = "out of copper"
                    break
                if not self._fits(member, name):
                    stopped = f"{name} won't fit {member.name}'s load"
                    break
                self.purse -= price
                self.guild.total_spent += price
                member.give_to_pack(name)
                if stock is not None:
                    self.guild.market_stock[name] = stock - 1
                bought += 1
            if stopped:
                break
        member._derive_combat()
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
        picks = [p for p in self.sel
                 if p[0] != "stock" and self._name_of(p) is not None]
        self.sel = []
        if not picks:
            self._sel_qty = {}
            return
        items, touched = self._collect(picks)      # _take reads self._sel_qty -- clear after
        self._sel_qty = {}
        total = sum(economy.sell_price(n, self.deal) * q for n, q in items)
        self.purse += total
        for n, q in items:
            stock = self._stock_of(n)
            if stock is not None:
                self.guild.market_stock[n] = stock + q
            self.guild.items_sold_kinds.add(n)
        for u in touched:
            u._derive_combat()
        sold = sum(q for _, q in items)
        self.notice = f"sold {sold} item(s) for {total}."
        self._settle_market()

    def _checkout(self):
        """Settles the pooled purse back out proportional to what each
        shopper walked in with (same rule the bank/property screens use) --
        no longer an even split, so wealth doesn't quietly level out just
        from shopping together."""
        economy.settle_pooled_purse(self.shoppers, self._orig_gold, self.purse)
        self.on_done()

    # ------------------------------------------------------------------ #

    def draw(self, screen):
        f = self.fonts
        F = self._ui_fonts()
        screen.fill(T.TABLE)
        self.tooltip = None
        self.stock_rows = []
        self.qty_hits = []
        self.lock_hits = []
        self.tab_hits = []
        self.item_rows = []
        self.cards = []
        self.buttons = []
        self.info_hits = []
        self._pack_areas = []
        self.zones = []

        ui_text(screen, F["head"], "MARKET", (MARGIN, MARGIN - 2), T.TX)
        ui_text(screen, F["body_sm"], f"common purse: {self.purse} copper", 
             (screen.get_width() - MARGIN - 40, MARGIN + 2), T.BRASS, right=True)
             
        names = self._selected_names()
        if names:
            if self._buying:
                name = names[0]
                q = self._buy_qty(name)
                one = name if q == 1 else f"{name} ×{q}"
                msg = (f"buy {one} ({economy.buy_price(name, self.deal) * q})"
                       "  ·  drop on a member")
            else:
                one = names[0] if len(names) == 1 else f"{len(names)} items"
                msg = (f"moving {one}  ·  drop on another member, or on SELL "
                       f"(+{sum(economy.sell_price(n, self.deal) for n in names)})")
            ui_text(screen, F["body"], msg + "  ·  click outside to cancel", (MARGIN, MARGIN + 30), T.BRASS)
        else:
            ui_text(screen, F["body"], f"{len(self.shoppers)} shopping  ·  {self._deal_note()}", (MARGIN, MARGIN + 30), T.TX_FAINT)

        top = MARGIN + 62
        self._draw_tabs(screen, pygame.Rect(MARGIN, top, STOCK_W, 28))
        if len(self.shoppers) > 1:
            dl_btn = pygame.Rect(screen.get_width() - MARGIN - 160, top, 160, 28)
            draw_button(screen, F, dl_btn, "distribute load", mpos=self.mouse)
            self.buttons.append(("distribute", dl_btn))
            
        body_top = top + 28 + SP2
        stock = pygame.Rect(MARGIN, body_top, STOCK_W, screen.get_height() - body_top - 72)
        self._draw_stock(screen, stock)
        
        self._draw_shoppers(screen, pygame.Rect(stock.right + MARGIN, body_top,
                                                screen.get_width() - stock.right - 2 * MARGIN,
                                                stock.h))
        self._draw_footer(screen)

        if self._dragging and names:
            gx, gy = self.mouse
            if self._buying:
                q = self._buy_qty(names[0])
                label = names[0] if q == 1 else f"{names[0]} ×{q}"
            else:
                label = names[0] if len(names) == 1 else f"{len(names)} items"
            gr = pygame.Rect(gx + 12, gy + 6, F["body"].size(label)[0] + 2 * SP2, 20)
            pygame.draw.rect(screen, mix(T.BRASS, T.STEEL, .85), gr)
            pygame.draw.rect(screen, T.BRASS, gr, 1)
            ui_text(screen, F["body"], label, gr.center, T.TX, center=True)
            
        for r, member, loc in self.item_rows:
            if not self.sel and r.collidepoint(self.mouse):
                name = self._item_at(member, loc)
                if name:
                    from .theme import format_tooltip
                    t, d = data.item_tooltip(name)
                    self.tooltip = format_tooltip(t, d, f)
                break

        if getattr(self, "tooltip", None):
            from .theme import draw_tooltip
            draw_tooltip(screen, f.body_sm, self.tooltip, self.mouse)

        self.draw_sheet_modal(screen, f)

    def _draw_tabs(self, screen, rect):
        F = self._ui_fonts()
        cats = self.get_categories()
        gap = T.S
        w = (rect.w - (len(cats) - 1) * gap) // len(cats)
        for i, (label, key, _names) in enumerate(cats):
            r = pygame.Rect(rect.x + i * (w + gap), rect.y, w, rect.h)
            active = self.tab == key
            draw_button(screen, F, r, label.upper(), ghost=not active, mpos=self.mouse)
            self.tab_hits.append((r, key))

    def _draw_stock(self, screen, rect):
        F = self._ui_fonts()
        pygame.draw.rect(screen, T.STEEL, rect)
        pygame.draw.rect(screen, T.STEEL_LINE, rect, 1)
        x, w = rect.x + T.S * 2, rect.w - T.S * 4
        names = next((c[2] for c in self.get_categories() if c[1] == self.tab), [])
        kit = self.tab == "kit"

        wt_x = rect.right - T.S * 2
        price_x = wt_x - 52
        tag_x = x + 204

        caps(screen, F["micro"], "FOR SALE", (x, rect.y + T.S * 2), T.TX_FAINT)
        hline(screen, x, rect.right - T.S * 2, rect.y + T.S * 4)
        
        y = rect.y + T.S * 5
        caps(screen, F["micro"], "ITEM", (x, y), T.TX_FAINT)
        if kit:
            caps(screen, F["micro"], "QTY", (x + 152, y), T.TX_FAINT)
        caps(screen, F["micro"], "PRICE", (price_x, y), T.TX_FAINT, right=True)
        caps(screen, F["micro"], "WT", (wt_x, y), T.TX_FAINT, right=True)
        y += 17

        row_h = 30 if kit else 34
        for name in names:
            r = pygame.Rect(x, y, w, row_h)
            sel = ("stock", name) in self.sel
            hov = not self.sel and r.collidepoint(self.mouse)
            base = economy.buy_price(name)
            price = economy.buy_price(name, self.deal)
            stock = self._stock_of(name)
            out = stock is not None and stock <= 0
            afford = self.purse >= price and not out
            fits = any(self._fits(m, name) for m in self.shoppers)
            
            fill = mix(T.BRASS, T.STEEL, .85) if sel else T.STEEL_HI if hov else T.TABLE
            pygame.draw.rect(screen, fill, r)
            pygame.draw.rect(screen, T.BRASS if sel else T.STEEL_LINE, r, 1)

            ink = T.TX if sel else T.TX if afford else T.TX_FAINT
            faint = T.TX_MUTED if sel else T.TX_FAINT

            if sel:
                main_color = T.TX
            elif not afford:
                main_color = T.TX_FAINT
            elif price < base:
                main_color = T.GREEN
            elif price > base:
                main_color = T.BLOOD
            else:
                main_color = T.TX

            spec = "" if kit else self._stock_spec(name)
            name_w = 138 if kit else 148
            ui_text(screen, F["body"], ellipsize(name, F["body"], name_w), (r.x + T.S, r.y + (4 if spec else r.centery - 8 - r.y)), ink)
            if spec:
                ui_text(screen, F["micro"], spec, (r.x + T.S, r.y + 17), faint)
            if kit:
                self._draw_stepper(screen, ("stock", name), r)
                tag = self._kit_tag(name)
                if tag:
                    from .ui.loadout_panel import TAG_COLOR
                    caps(screen, F["micro"], tag, (tag_x, r.centery - 5), TAG_COLOR.get(tag, T.TX_FAINT))
            if stock is not None:
                stock_label = "SOLD OUT" if out else f"{stock} left"
                caps(screen, F["micro"], stock_label, (tag_x, r.centery + 3), T.BLOOD if out else T.TX_MUTED)

            wt = f"{data.item_weight(name):.1f} kg"
            caps(screen, F["micro"], wt, (wt_x, r.centery - 5), T.TX_FAINT if fits else T.BLOOD, right=True)
            prect_w = F["body"].size(f"{price}c")[0]
            ui_text(screen, F["body"], f"{price}c", (price_x, r.centery - 8), main_color, right=True)
            
            if base != price:
                br_w = F["micro"].size(f"{base}c")[0]
                caps(screen, F["micro"], f"{base}c", (price_x - prect_w - T.S, r.centery - 5), faint, right=True)
                line_y = r.centery - 1
                pygame.draw.line(screen, faint, (price_x - prect_w - T.S - br_w, line_y), (price_x - prect_w - T.S, line_y), 1)

            if hov:
                from .theme import format_tooltip
                t, d = data.item_tooltip(name)
                self.tooltip = format_tooltip(t, d, self.fonts)

            self.stock_rows.append((r, name))
            y += row_h + T.S

    def _stock_spec(self, name):

        """The one-line stat blurb under a weapon / armor row."""
        if name in data.WEAPONS:
            wp = data.WEAPONS[name]
            n, faces = wp["damage"]
            hands = "2h" if wp["hands"] >= 2 else "1h"
            rng = f"  ·  {wp['range'] * 3 // 2}m" if wp["range"] else ""
            return f"{n}d{faces}  ·  {hands}{rng}"
        if name in data.ARMOR:
            ar = data.ARMOR[name]
            cap = "no dex cap" if ar["max_dex"] is None else f"dex cap {ar['max_dex']}"
            spd = f"  ·  -{ar['speed']} spd" if ar["speed"] else ""
            return f"+{ar['ac']} AC  ·  {cap}{spd}"
        return ""

    @staticmethod
    def _kit_tag(name):
        if name in data.FOOD_ITEMS:
            return "FOOD"
        if name == data.FIRST_AID_ITEM:
            return "HEAL"
        if name == data.AMMO_ITEM:
            return "AMMO"
        if name == data.TORCH_ITEM or name in data.LIGHT_SOURCES:
            return "LIGHT"
        return ""


    def _draw_stepper(self, screen, pick, row):
        F = self._ui_fonts()
        q = self._get_qty(pick)
        sel = pick in self.sel if pick[0] == "stock" else q > 0
        bw, bh = 16, 18
        cy = row.centery
        minus = pygame.Rect(row.x + 138, cy - bh // 2, bw, bh)
        plus = pygame.Rect(minus.right + 26, cy - bh // 2, bw, bh)
        for r, glyph, delta in ((minus, "-", -1), (plus, "+", +1)):
            draw_button(screen, F, r, glyph, ghost=True, mpos=self.mouse)
            self.qty_hits.append((r, pick, delta))
        
        caps(screen, F["microb"], str(q), ((minus.right + plus.x) // 2, cy - 6), T.BRASS if sel else T.TX, center=True)
        if pick[0] != "stock":
            if self._held_qty(pick) > 1:
                all_btn = pygame.Rect(plus.right + 4, cy - bh // 2, 28, bh)
                draw_button(screen, F, all_btn, "ALL", ghost=True, mpos=self.mouse)
                self.qty_hits.append((all_btn, pick, 999))

    def _draw_shoppers(self, screen, area):
        self._shoppers_area = area
        F = self._ui_fonts()
        gap = T.S * 2
        
        cap = max(1, (area.w + gap) // (300 + gap))
        n_shown = min(cap, len(self.shoppers))
        card_w = min(420, max(300, (area.w - (n_shown - 1) * gap) // n_shown)) if n_shown > 0 else 300
        
        self._shoppers_max_scroll = max(0, len(self.shoppers) - cap)
        cur = getattr(self, "_shoppers_scroll", 0)
        self._shoppers_scroll = max(0, min(cur, self._shoppers_max_scroll))
        
        shown = self.shoppers[self._shoppers_scroll : self._shoppers_scroll + n_shown]
        carried = self._selected_names()
        
        for i, m in enumerate(shown):
            r = pygame.Rect(area.x + i * (card_w + gap), area.y, card_w, area.h)
            member = self._member_dict(m, carried)
            res = loadout_panel.column(screen, F, r, member, self._pack_scroll.get(id(m), 0), self.mouse)
            self._pack_scroll[id(m)] = res["scroll"]
            self.info_hits.append((res["sheet_rect"], m))
            
            for kind, slot_rect in res["slot_rects"].items():
                if slot_rect is None:
                    continue
                self.zones.append((slot_rect, m, kind))
                if member[kind]["name"]:
                    self.item_rows.append((slot_rect, m, kind))
                    
            self.zones.append((res["pack_zone"], m, "pack"))
            self._pack_areas.append((res["pack_area"], m))
            
            for pr, idx in res["pack_hits"]:
                self.item_rows.append((pr, m, idx))
            for lr, idx in res["lock_hits"]:
                self.lock_hits.append((lr, m, m._base_inventory[idx][0]))
                
        if self._shoppers_max_scroll > 0:
            from .ui.primitives import text
            hr = self._shoppers_max_scroll - self._shoppers_scroll
            hl = self._shoppers_scroll
            if hr > 0:
                text(screen, F["body_sm"], f"{hr} more \u2192  (scroll)", (area.right - 8, area.bottom + 8), T.TX_FAINT, right=True)
            if hl > 0:
                text(screen, F["body_sm"], f"\u2190 {hl} more  (scroll)", (area.x + 8, area.bottom + 8), T.TX_FAINT)

    def _distribute_load(self):

        from . import unit as unit_module
        unit_module.distribute_load(self.shoppers)
        self.sel = []
        self.notice = "redistributed packs by carrying capacity."


    def _draw_footer(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        
        done_r = pygame.Rect(T.S * 2, H - T.S * 8, T.S * 25, T.S * 4)
        draw_button(screen, F, done_r, "back to guild", primary=True, mpos=self.mouse)
        self.buttons.append(("done", done_r))

        names = self._selected_names()
        if not self._buying and names:
            sell_r = pygame.Rect(0, 0, T.S * 25, T.S * 4)
            sell_r.center = (W // 2, H - T.S * 8 + T.S * 2)
            total = sum(economy.sell_price(n, self.deal) for n in names)
            draw_button(screen, F, sell_r, f"SELL FOR {total}c", mpos=self.mouse)
            self.buttons.append(("sell", sell_r))

        if self.notice:
            ui_text(screen, F["body_sm"], self.notice, (T.S * 2, H - T.S * 10), T.BRASS)

"""The Market's trades: a drop on a member or a zone, buying, selling and the checkout through the
party purse (`MarketTradeMixin`, mixed into `MarketScreen`)."""

import pygame

from . import economy, factions, items, recorder
from .constants import fmt_money


class MarketTradeMixin:
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

        if zone in ("hand", "offhand", "tongue", "artifact", "armor"):
            fit = next((p for p in picks if self._fits_slot(member, zone, self._name_of(p))), None)
            if fit is None:
                self.selected = picks
                self.notice = f"doesn't fit in {zone}."
                return
            picks = [fit]

        collected, touched = self._collect(picks)
        self._sel_qty = {}
        for name, qty in collected:
            if zone in ("hand", "offhand", "tongue", "artifact", "armor"):
                src_unit = fit[0]
                if qty > 1:
                    src_unit.give_to_pack(name, qty - 1)
                if zone == "hand":
                    member.give_to_hand(name)
                elif zone == "offhand":
                    member.give_to_offhand(name)
                elif zone == "tongue":
                    member.give_to_tongue(name)
                elif zone == "artifact":
                    member.give_to_artifact(name)
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
        if zone in ("hand", "offhand", "tongue", "artifact", "armor"):
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
                self._shop().stock[name] = stock - 1

            if zone == "hand":
                member.give_to_hand(name)
            elif zone == "offhand":
                member.give_to_offhand(name)
            elif zone == "tongue":
                member.give_to_tongue(name)
            elif zone == "artifact":
                member.give_to_artifact(name)
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
                    self._shop().stock[name] = stock - 1
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
        shop = self._shop()
        for owner, owner_picks in by_owner.values():
            collected, _ = self._collect(owner_picks)  # _take reads self._sel_qty -- clear after
            proceeds = sum(economy.sell_price(n, self.deal) * q for n, q in collected)
            payee = owner if owner in self.shoppers else self.shoppers[0]    # a wagon or animal takes no coin
            payee.money += proceeds
            total += proceeds
            sold += sum(q for _, q in collected)
            for n, q in collected:
                recorder.emit("sell", node=self._node_id(), item=n, qty=q,
                              price=economy.sell_price(n, self.deal))
                if shop and items.get(n) and not items.is_coin(n):
                    shop.add(n, q)
                self.guild.items_sold_kinds.add(n)
            owner._derive_combat()
        self._sel_qty = {}
        self._till(-total)
        self.notice = f"sold {sold} item(s) for {total}."
        self._settle_market()

    def _purse_members(self):
        return self.shoppers

    def _purse_stores(self):
        return self.stores

    def _checkout(self):
        self.on_done()

    # ------------------------------------------------------------------ #

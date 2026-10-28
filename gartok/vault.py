"""A stash's counter, with no pygame: the Bank's strongbox (`BankVault`) and the City house
(`HouseVault`), each moving gear between a `holdings.Stash` and the visiting band's packs.

`purse` is the band's real coin (`economy.PartyPurse`): a rent, a price or a debt payment comes
out of the members in proportion to what each carries. The stash is a third kind of pick owner
next to a `Unit` and a store: the string `OWNER`. Taking out of it is the one move that
hard-blocks over `carry_max`; member to member stays the soft, penalty-only overload.

The bank is also the only place Gold Coins are minted or melted (`economy.buy_gold` /
`sell_gold`, `economy.GOLD_FEE` per coin each way), on a coin stack in a pack or the chest.
"""

from . import economy, items, store_column
from .constants import fmt_money
from .loadout_move import LoadoutMoveMixin

SLOTS = ("hand", "offhand", "tongue", "artifact", "armor")


class Vault(economy.PartyPurse, LoadoutMoveMixin):
    OWNER = ""              # pick-owner key for the stash: "bank" / "house"
    LABEL = ""              # "the strongbox"
    CLOSED_NOTICE = ""      # said when depositing into a stash the guild doesn't hold yet
    WHERE = ""              # completes "won't fit -- N kg free ..."
    CAN_DISTRIBUTE = False

    def __init__(self, guild, party):
        self.guild = guild
        self.party = party
        self.selected = []                    # [(owner, loc)] -- owner is OWNER or a pack owner
        self._sel_qty = {}                    # (owner, idx) -> qty picked
        self.notice = None
        self.group = guild.group_of(party[0]) if party else None
        self.stores = [*self.group.herd, *self.group.wagons] if self.group else []

    def _stash(self):
        raise NotImplementedError

    def _open(self):
        """True once the guild holds the stash (rented / bought)."""
        raise NotImplementedError

    def _services(self):
        """`[(key, label, sub, enabled)]`: what the place sells or settles."""
        raise NotImplementedError

    def _run_service(self, key):
        raise NotImplementedError

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
        """`LoadoutMoveMixin._give_many` with the stash as a source or the destination."""
        if dst == self.OWNER:
            self._deposit(list(self.selected))
            return
        picks = [p for p in self.selected if self._item_at(*p) is not None]
        self.selected = []
        if not picks:
            return

        if any(owner == self.OWNER for owner, _ in picks):
            add = sum(items.item_weight(self._item_at(*p)) * self._qty_at(*p) for p in picks)
            if dst.load + add > dst.carry_max:
                self.notice = f"won't fit {dst.name}'s load."
                self.selected = picks
                return

        if store_column.is_store(dst) and zone == "pack":
            moving = [p for p in picks if p[0] is not dst]
            add = sum(items.item_weight(self._item_at(*p)) * self._qty_at(*p) for p in moving)
            if not dst.stash.fits(add):
                self.notice = f"won't fit -- {dst.stash.free:g} kg free on the {dst.name.lower()}."
                self.selected = picks
                return

        if zone in SLOTS:
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

        if all(p[0] is dst and not isinstance(p[1], str) for p in picks):
            return
        collected, touched = self._collect(picks)
        for name, qty in collected:
            dst.give_to_pack(name, qty)
        for u in touched:
            if u != self.OWNER:
                u._derive_combat()
        dst._derive_combat()

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

    def _distribute_load(self):
        from . import unit as unit_module
        if len(self.party) + len(self.stores) <= 1:
            return
        unit_module.distribute_load(self.party, share_coins=True, creatures=self.stores)
        self.notice = "redistributed packs by carrying capacity."

    def _purse_members(self):
        return self.party

    def _purse_stores(self):
        return self.stores

    def hub_cards(self):
        cards = [{"label": "party purse", "value": fmt_money(self.purse), "tone": "money"}]
        if self._open():
            stash = self._stash()
            cards.insert(0, {"label": self.LABEL, "value": f"{stash.load:.1f} / {stash.capacity:.0f} kg"})
        return cards


class BankVault(Vault):
    OWNER = "bank"
    LABEL = "the strongbox"
    CLOSED_NOTICE = "rent a strongbox first."
    WHERE = "in the chest"
    CAN_DISTRIBUTE = True

    def _stash(self):
        return self.guild.bank

    def _open(self):
        return self.guild.bank.open

    def _services(self):
        g = self.guild
        services = []
        if not g.house.owned and not g.house.squatting and g.bankers_debt <= 0:
            rep_ok = g.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
            can_buy = rep_ok and not g.bankers_services_blocked and self.purse >= economy.CITY_PROPERTY_PRICE
            sub = (f"{fmt_money(economy.CITY_PROPERTY_PRICE)}  ·  needs {economy.CITY_PROPERTY_REP_GATE} "
                   "standing with the Bankers")
            services.append(("buy_property", "BUY THE HOUSE", sub, can_buy))
        if not g.bank.open:
            can_rent = self.purse >= economy.BANK_CHEST_PRICE
            services.append(("rent", "RENT A STRONGBOX",
                             f"{fmt_money(economy.BANK_CHEST_PRICE)}  ·  {economy.BANK_CHEST_CAPACITY} kg held in the City",
                             can_rent))
        return services

    def _run_service(self, key):
        if key == "rent":
            if self.purse < economy.BANK_CHEST_PRICE:
                self.notice = (f"the strongbox costs {fmt_money(economy.BANK_CHEST_PRICE)} -- "
                               f"the party has {fmt_money(self.purse)}.")
                return
            self.purse -= economy.BANK_CHEST_PRICE
            self.guild.rent_bank_chest()
            self.notice = f"rented a strongbox -- {self.guild.bank.capacity} kg of storage at the bank."
        elif key == "buy_property":
            if self.purse < economy.CITY_PROPERTY_PRICE:
                self.notice = (f"the Bankers want {fmt_money(economy.CITY_PROPERTY_PRICE)} for "
                               f"the house -- the party has {fmt_money(self.purse)}.")
                return
            self.purse -= economy.CITY_PROPERTY_PRICE
            self.guild.buy_city_property()
            self.notice = "bought a house in the City -- the Bankers' tax starts now."

    def _holder_of(self, owner):
        return self._stash() if owner == self.OWNER else owner

    def _exchange(self, holder, mode, n):
        """Mint (`buy_gold`) or melt (`sell_gold`) `n` Gold Coins out of `holder`. False if it cannot."""
        if mode == "buy_gold":
            if not economy.buy_gold(holder, n):
                return False
            self.notice = f"minted {n} gold coins for {fmt_money(economy.gold_price(n))}."
        else:
            if not economy.sell_gold(holder, n):
                return False
            self.notice = f"melted {n} gold coins into {fmt_money(economy.gold_payout(n))}."
        if hasattr(holder, "_derive_combat"):
            holder._derive_combat()
        return True


class HouseVault(Vault):
    OWNER = "house"
    LABEL = "the house"
    CLOSED_NOTICE = "buy the house first."
    WHERE = "at the property"

    def _stash(self):
        return self.guild.house.stash

    def _open(self):
        return self.guild.house.owned

    def _services(self):
        g = self.guild
        rows = []
        if g.bankers_debt > 0:
            rows.append(("pay_debt", "PAY TOWARD THE DEBT", "the Bankers' other services are shut until it is paid",
                         self.purse > 0))
        if g.house.owned:
            if not g.house.oven:
                rows.append(("oven", "BUY AN OVEN", f"{fmt_money(economy.OVEN_PRICE)}  ·  unlocks cooking at the house",
                             self.purse >= economy.OVEN_PRICE))
            return rows
        if g.house.squatting:
            return rows
        rep_ok = g.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
        can_buy = rep_ok and not g.bankers_services_blocked and self.purse >= economy.CITY_PROPERTY_PRICE
        sub = (f"{fmt_money(economy.CITY_PROPERTY_PRICE)}  ·  needs {economy.CITY_PROPERTY_REP_GATE} "
               f"standing with the Bankers (have {g.reputation.get('bankers', 0)})")
        return [*rows, ("buy", "BUY THE HOUSE", sub, can_buy)]

    def _run_service(self, key):
        if key == "buy":
            rep_ok = self.guild.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
            if not rep_ok or self.guild.bankers_services_blocked:
                return
            if self.purse < economy.CITY_PROPERTY_PRICE:
                self.notice = (f"the Bankers want {fmt_money(economy.CITY_PROPERTY_PRICE)} for "
                               f"the house -- the party has {fmt_money(self.purse)}.")
                return
            self.purse -= economy.CITY_PROPERTY_PRICE
            self.guild.buy_city_property()
            self.notice = "bought a house in the City -- the Bankers' tax starts now."
        elif key == "oven":
            if self.purse < economy.OVEN_PRICE:
                self.notice = f"an oven costs {fmt_money(economy.OVEN_PRICE)} -- the party has {fmt_money(self.purse)}."
                return
            self.purse -= economy.OVEN_PRICE
            self.guild.buy_oven()
            self.notice = "the oven is installed -- the house can cook now."
        elif key == "pay_debt":
            amount = min(self.purse, self.guild.bankers_debt)
            if amount <= 0:
                self.notice = "the party has no money to pay with."
                return
            self.purse -= amount
            self.guild.pay_bankers_debt(amount)
            self.notice = (f"paid {fmt_money(amount)} toward the debt." if self.guild.bankers_debt > 0
                           else "debt cleared -- the Bankers deal with the guild again.")

    def hub_cards(self):
        g, house = self.guild, self.guild.house
        cards = super().hub_cards()
        if house.squatting:
            cards.insert(0, {"label": "squatting", "value": "no tax", "sub": "the guard raids this place",
                             "tone": "bad"})
        elif house.owned:
            left = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT - house.missed_payments
            sub = (f"{house.missed_payments} missed  ·  {max(0, left)} more before the Bankers act"
                   if house.missed_payments else f"{fmt_money(economy.CITY_PROPERTY_TAX)} a cycle")
            cards.insert(0, {"label": "next tax", "value": f"day {house.tax_due_day}", "sub": sub,
                             "tone": "bad" if house.missed_payments else None})
        if g.bankers_debt > 0:
            cards.insert(0, {"label": "owed to the bankers", "value": fmt_money(g.bankers_debt), "tone": "bad"})
        return cards

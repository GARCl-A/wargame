"""A stash's counter, with no pygame: the Bank's strongbox (`BankVault`) and the City house
(`HouseVault`), each moving gear between a `holdings.Stash` and the visiting band's packs.

`purse` is the band's real coin (`economy.PartyPurse`): a rent, a price or a debt payment comes
out of the members in proportion to what each carries. The stash is a third kind of pick owner
next to a `Unit` and a store: the string `OWNER`. Taking out of it is the one move that
hard-blocks over `carry_max`; member to member stays the soft, penalty-only overload.

The bank is also the only place Gold Coins are minted or melted (`economy.buy_gold` /
`sell_gold`, `economy.GOLD_FEE` per coin each way), on a coin stack in a pack or the chest.
"""

from . import economy, i18n, items, store_column
from .constants import fmt_money
from .loadout_move import LoadoutMoveMixin

SLOTS = ("hand", "offhand", "tongue", "artifact", "armor")


class Vault(economy.PartyPurse, LoadoutMoveMixin):
    OWNER = ""              # pick-owner key for the stash: "bank" / "house"
    LABEL = ""              # catalog key of the stash's card label
    CLOSED_NOTICE = ""      # catalog key, said when depositing into a stash the guild doesn't hold yet
    NO_ROOM = ""            # catalog key of "won't fit -- N kg free ..." in this stash
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
                self.notice = i18n.t("vault.won_t_fit_s_load", name=dst.name)
                self.selected = picks
                return

        if store_column.is_store(dst) and zone == "pack":
            moving = [p for p in picks if p[0] is not dst]
            add = sum(items.item_weight(self._item_at(*p)) * self._qty_at(*p) for p in moving)
            if not dst.stash.fits(add):
                self.notice = i18n.t("vault.won_t_fit_kg_free", free=dst.stash.free, lower=dst.name.lower())
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
            self.notice = i18n.t(self.CLOSED_NOTICE)
            self.selected = picks
            return
        if not stash.fits(add):
            self.notice = i18n.t(self.NO_ROOM, free=f"{stash.free:g}")
            self.selected = picks
            return
        collected, touched = self._collect(picks)
        self._sel_qty = {}
        for name, qty in collected:
            stash.put(name, qty)
        for u in touched:
            u._derive_combat()
        total = sum(q for _, q in collected)
        one = collected[0][0] if total == 1 else i18n.plural("vault.items", total)
        self.notice = i18n.t("vault.stashed", one=one)

    def _distribute_load(self):
        from . import unit as unit_module
        if len(self.party) + len(self.stores) <= 1:
            return
        unit_module.distribute_load(self.party, share_coins=True, creatures=self.stores)
        self.notice = i18n.t("vault.redistributed_packs_by_carrying_capacity")

    def _purse_members(self):
        return self.party

    def _purse_stores(self):
        return self.stores

    def hub_cards(self):
        cards = [{"label": i18n.t("vault.party_purse"), "value": fmt_money(self.purse), "tone": "money"}]
        if self._open():
            stash = self._stash()
            cards.insert(0, {"label": i18n.t(self.LABEL), "value": i18n.t("vault.kg", load=stash.load, capacity=stash.capacity)})
        return cards


class BankVault(Vault):
    OWNER = "bank"
    LABEL = "vault.label_bank"
    CLOSED_NOTICE = "vault.closed_bank"
    NO_ROOM = "vault.no_room_bank"
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
            sub = (i18n.t("vault.needs_standing_with_bankers", fmt_money=fmt_money(economy.CITY_PROPERTY_PRICE), city_property_rep_gate=economy.CITY_PROPERTY_REP_GATE))
            services.append(("buy_property", i18n.t("vault.buy_house"), sub, can_buy))
        if not g.bank.open:
            can_rent = self.purse >= economy.BANK_CHEST_PRICE
            services.append(("rent", "RENT A STRONGBOX",
                             i18n.t("vault.kg_held_in_city", fmt_money=fmt_money(economy.BANK_CHEST_PRICE), bank_chest_capacity=economy.BANK_CHEST_CAPACITY),
                             can_rent))
        return services

    def _run_service(self, key):
        if key == "rent":
            if self.purse < economy.BANK_CHEST_PRICE:
                self.notice = (i18n.t("vault.strongbox_costs_party_has", cost=fmt_money(economy.BANK_CHEST_PRICE), wealth=fmt_money(self.purse)))
                return
            self.purse -= economy.BANK_CHEST_PRICE
            self.guild.rent_bank_chest()
            self.notice = i18n.t("vault.rented_strongbox_kg_of_storage", capacity=self.guild.bank.capacity)
        elif key == "buy_property":
            if self.purse < economy.CITY_PROPERTY_PRICE:
                self.notice = (i18n.t("vault.bankers_want_for_house_party", cost=fmt_money(economy.CITY_PROPERTY_PRICE), wealth=fmt_money(self.purse)))
                return
            self.purse -= economy.CITY_PROPERTY_PRICE
            self.guild.buy_city_property()
            self.notice = i18n.t("vault.bought_house_in_city_bankers")

    def _holder_of(self, owner):
        return self._stash() if owner == self.OWNER else owner

    def _exchange(self, holder, mode, n):
        """Mint (`buy_gold`) or melt (`sell_gold`) `n` Gold Coins out of `holder`. False if it cannot."""
        if mode == "buy_gold":
            if not economy.buy_gold(holder, n):
                return False
            self.notice = i18n.t("vault.minted_gold_coins_for", n=n, fmt_money=fmt_money(economy.gold_price(n)))
        else:
            if not economy.sell_gold(holder, n):
                return False
            self.notice = i18n.t("vault.melted_gold_coins_into", n=n, fmt_money=fmt_money(economy.gold_payout(n)))
        if hasattr(holder, "_derive_combat"):
            holder._derive_combat()
        return True


class HouseVault(Vault):
    OWNER = "house"
    LABEL = "vault.label_house"
    CLOSED_NOTICE = "vault.closed_house"
    NO_ROOM = "vault.no_room_house"

    def _stash(self):
        return self.guild.house.stash

    def _open(self):
        return self.guild.house.owned

    def _services(self):
        g = self.guild
        rows = []
        if g.bankers_debt > 0:
            rows.append(("pay_debt", i18n.t("vault.pay_toward_debt"), i18n.t("vault.bankers_other_services_are_shut"),
                         self.purse > 0))
        if g.house.owned:
            if not g.house.oven:
                rows.append(("oven", i18n.t("vault.buy_oven"), i18n.t("vault.unlocks_cooking_at_house", fmt_money=fmt_money(economy.OVEN_PRICE)),
                             self.purse >= economy.OVEN_PRICE))
            return rows
        if g.house.squatting:
            return rows
        rep_ok = g.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
        can_buy = rep_ok and not g.bankers_services_blocked and self.purse >= economy.CITY_PROPERTY_PRICE
        sub = (i18n.t("vault.needs_standing_with_bankers_have", fmt_money=fmt_money(economy.CITY_PROPERTY_PRICE), city_property_rep_gate=economy.CITY_PROPERTY_REP_GATE, get=g.reputation.get('bankers', 0)))
        return [*rows, ("buy", i18n.t("vault.buy_house"), sub, can_buy)]

    def _run_service(self, key):
        if key == "buy":
            rep_ok = self.guild.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
            if not rep_ok or self.guild.bankers_services_blocked:
                return
            if self.purse < economy.CITY_PROPERTY_PRICE:
                self.notice = (i18n.t("vault.bankers_want_for_house_party", cost=fmt_money(economy.CITY_PROPERTY_PRICE), wealth=fmt_money(self.purse)))
                return
            self.purse -= economy.CITY_PROPERTY_PRICE
            self.guild.buy_city_property()
            self.notice = i18n.t("vault.bought_house_in_city_bankers")
        elif key == "oven":
            if self.purse < economy.OVEN_PRICE:
                self.notice = i18n.t("vault.oven_costs_party_has", cost=fmt_money(economy.OVEN_PRICE), wealth=fmt_money(self.purse))
                return
            self.purse -= economy.OVEN_PRICE
            self.guild.buy_oven()
            self.notice = i18n.t("vault.oven_is_installed_house_can")
        elif key == "pay_debt":
            amount = min(self.purse, self.guild.bankers_debt)
            if amount <= 0:
                self.notice = i18n.t("vault.party_has_no_money_to")
                return
            self.purse -= amount
            self.guild.pay_bankers_debt(amount)
            self.notice = (i18n.t("vault.paid_toward_debt", fmt_money=fmt_money(amount)) if self.guild.bankers_debt > 0
                           else i18n.t("vault.debt_cleared_bankers_deal_with"))

    def hub_cards(self):
        g, house = self.guild, self.guild.house
        cards = super().hub_cards()
        if house.squatting:
            cards.insert(0, {"label": "squatting", "value": i18n.t("vault.no_tax"), "sub": i18n.t("vault.guard_raids_this_place"),
                             "tone": "bad"})
        elif house.owned:
            left = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT - house.missed_payments
            sub = (i18n.t("vault.missed_more_before_bankers_act", missed_payments=house.missed_payments, max=max(0, left))
                   if house.missed_payments else f"{fmt_money(economy.CITY_PROPERTY_TAX)} a cycle")
            cards.insert(0, {"label": i18n.t("vault.next_tax"), "value": i18n.t("vault.day", tax_due_day=house.tax_due_day), "sub": sub,
                             "tone": "bad" if house.missed_payments else None})
        if g.bankers_debt > 0:
            cards.insert(0, {"label": i18n.t("vault.owed_to_bankers"), "value": fmt_money(g.bankers_debt), "tone": "bad"})
        return cards

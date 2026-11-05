"""A shop's counter: what a band can buy, sell and move between its packs at a node's shop.

The rules only, with no window: the shelf (`economy.market_categories`, the Library's own), the
haggled deal, the party purse (the members' coin, `economy.PartyPurse`), the till and the stock
(`Guild.shop(node_id)`), the auto-sell marks, the moves between packs and slots and the deeds and
objectives a trade can meet. `web/shop_tab.py` draws it, setting `selected` / `_sel_qty` / `qty` the
way a pick would and calling its methods.

A pick is `("stock", name)` for a shelf row, or `(owner, loc)` with `loc` a pack index or a slot
(`"hand"`, `"offhand"`, `"tongue"`, `"artifact"`, `"armor"`).
"""

import random

from . import data, economy, factions, i18n, items, recorder
from .constants import fmt_money

SLOTS = ("hand", "offhand", "tongue", "artifact", "armor")

# how far the voice's alignment sits from the vendor's (`data.alignment_distance`)
BENT_WORDS = {n: f"trade.bent.{n}" for n in range(5)}


def collect(picks, take):
    """Pull every `(owner, loc)` pick off its owner through `take(owner, loc) -> (name, qty)` --
    `[(name, qty)]` moved plus the owners touched. Pack rows come off highest index first so an
    earlier removal doesn't shift the ones still to come."""
    by_owner = {}
    for owner, loc in picks:
        by_owner.setdefault(id(owner), (owner, []))[1].append(loc)
    moved, touched = [], []
    for owner, locs in by_owner.values():
        touched.append(owner)
        ordered = [loc for loc in locs if isinstance(loc, str)]
        ordered += sorted((loc for loc in locs if not isinstance(loc, str)), reverse=True)
        for loc in ordered:
            name, qty = take(owner, loc)
            if name is not None:
                moved.append((name, qty))
    return moved, touched


def library_stock_dictionaries(guild):
    """Dictionaries the Library sells today: none until the `library_initiate` deed (rep >= 1),
    then one language per point of reputation, drawn afresh each day."""
    rep = guild.reputation.get("library", 0)
    if rep <= 0:
        return []
    rng = random.Random(guild.clock.day)
    return [f"Dictionary of {lang}" for lang in rng.sample(data.LANGUAGES, min(rep, len(data.LANGUAGES)))]


class Counter(economy.PartyPurse):
    def __init__(self, guild, shoppers, node):
        self.guild = guild
        self.shoppers = shoppers
        self.node = node
        group = guild.group_of(shoppers[0]) if guild and shoppers else None
        self.group = group
        self.stores = [*group.herd, *group.wagons] if group else []     # wagons and animals shop along
        # haggling: language + charisma + alignment (and talents) bend the prices; the group's
        # leader speaks for it when eligible (`economy._haggle_fraction`)
        self.deal = economy.deal_mods(shoppers, getattr(node, "language", None),
                                      getattr(node, "alignment", None),
                                      leader=group.leader if group else None)
        self.qty = {}                        # stock name -> quantity to buy
        self.selected = []
        self._sel_qty = {}                   # (owner, idx) -> how much of that pack stack is picked
        self.notice = None

    def sync_group(self):
        if self.group is None:
            return
        self.shoppers = list(self.group.members)
        self.stores = [*self.group.herd, *self.group.wagons]
        self.deal = economy.deal_mods(self.shoppers, getattr(self.node, "language", None),
                                      getattr(self.node, "alignment", None),
                                      leader=self.group.leader)

    def get_categories(self):
        shop = self._shop()
        cats = economy.market_categories(self._node_id(), shop.strays() if shop else ())

        def base_names(names):     # a weapon row is its Medium name; the size toggle picks the Large one
            return list(dict.fromkeys(n.removeprefix("Large ") for n in names))
        return [(lbl, key, base_names(names) if key == "weapons" else names) for lbl, key, names in cats]

    def _node_id(self):
        return getattr(getattr(self, "node", None), "id", None)

    def _shop(self):
        guild, node = getattr(self, "guild", None), getattr(self, "node", None)
        return guild.shop(node.id) if guild and node else None

    def _stock_of(self, name):
        """Units of `name` left to buy, or None if the shop has no count -- also None with
        no `guild` (a few tests build a bare counter with no campaign behind it). A weapon the
        shelf does not keep is 0: the size toggle can name one."""
        shop = self._shop()
        if shop and name not in shop.stock and items.is_weapon(name):
            return 0
        return economy.stock_of(shop.stock, name) if shop else None

    def _cash(self):
        """What the shop can still pay out today, or None with no `guild`."""
        shop = self._shop()
        return shop.cash if shop else None

    def _till(self, delta):
        shop = self._shop()
        if shop:
            shop.move_cash(delta)

    def _purse_members(self):
        return self.shoppers

    def _purse_stores(self):
        return self.stores

    @staticmethod
    def _stock_spec(name):
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
            cap = i18n.t("trade.no_dex_cap") if w.max_dex is None else i18n.t("trade.dex_cap", max_dex=w.max_dex)
            spd = i18n.t("trade.spd", speed_penalty=w.speed_penalty) if w.speed_penalty else ""
            return i18n.t("trade.ac", ac=w.ac, cap=cap, spd=spd)
        return ""

    def _deal_card(self):
        """How the party's haggling moved the prices: a headline, its tone and the reasons."""
        lang = getattr(self.node, "language", None)
        alignment = getattr(self.node, "alignment", None)
        sell = i18n.t("trade.you_sell_at_of_price", int=int(economy.SELL_FACTOR * 100))
        if not lang or not alignment:
            return {"headline": i18n.t("trade.fixed_prices"), "tone": "none", "why": [sell]}
        voice, dist = economy.haggle_voice(self.shoppers, lang, alignment,
                                           self.group.leader if self.group else None)
        if voice is None:
            tongues = " or ".join(economy.vendor_tongues(lang))
            return {"headline": i18n.t("trade.no_haggling"), "tone": "none", "why": [i18n.t("trade.no_one_speaks", tongues=tongues), sell]}
        general = economy.deal_value(self.deal, None, "buy")
        food = economy.deal_value(self.deal, next(iter(items.food_items())), "buy")
        pct = round(general * 100)
        headline = i18n.t("trade.pct_off", pct=pct) if pct > 0 else i18n.t("trade.pct_markup", pct=-pct) if pct < 0 else i18n.t("trade.list_price")
        tone = "good" if pct > 0 else "bad" if pct < 0 else "none"
        cha = voice.haggle_charisma_mod
        why = [i18n.t("trade.speaks_for_group", name=voice.name),
               i18n.t("trade.charisma", cha=cha, bent_words=i18n.t(BENT_WORDS[dist]))]
        if round(food, 3) != round(general, 3):
            why.append(i18n.t("trade.food_off", round=round(food * 100)))
        return {"headline": headline, "tone": tone, "why": why}

    # ------------------------------------------------------------------ #
    # picks                                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _fits_slot(dst, zone, name):
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
        """Lift the pick at `loc` off `member` -- `(name, qty)`. A pack pick takes only what
        `self._sel_qty` says is picked, not necessarily the whole stack; a slot is always qty 1."""
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

    def _collect(self, picks):
        return collect(picks, self._take)

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

    def _buy_qty(self, name):
        return max(1, self.qty.get(name, 1))

    def _get_qty(self, pick):
        if pick[0] == "stock":
            return self._buy_qty(pick[1])
        return min(self._held_qty(pick), self._sel_qty.get(pick, self._held_qty(pick)))

    def _held_qty(self, pick):
        """Full quantity of the pick's stack, ignoring any partial pick."""
        owner, loc = pick
        if isinstance(loc, str):
            return 1
        return owner._base_inventory[loc][1] if loc < len(owner._base_inventory) else 0

    @staticmethod
    def _fits(member, name):
        return member.load + items.item_weight(name) <= member.carry_max

    # ------------------------------------------------------------------ #
    # auto-sell                                                           #
    # ------------------------------------------------------------------ #
    def _marked(self):
        return getattr(self.guild, "autosell", None) or set()

    def _marked_stock(self, names=None):
        """`([(member, loc)], {pick: qty})` for every marked item (or every one of `names`) the shoppers and
        stores carry -- all of a stack but the padlocked part."""
        names = self._marked() if names is None else names
        picks, qty = [], {}
        for member in (*self.shoppers, *self.stores):
            left = {n: member.unlocked_of(n) for n in names}
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

    def _sell_marked(self, names=None):
        picks, qty = self._marked_stock(names)
        if not picks:
            self.notice = i18n.t("trade.nothing_marked_for_auto_sell") if names is None else i18n.t("trade.nothing_to_sell")
            return
        self.selected, self._sel_qty = picks, qty
        self._sell()

    def sell_named(self, names):
        """SELL MARKED for these items instead of the marks: what a routine's trade does at the counter."""
        self._sell_marked(names)

    def buy_named(self, wants):
        """BUY with a cart of `{name: count}`, each into whoever has the most room: what a routine's trade
        does at the counter."""
        wants = {name: count for name, count in wants.items() if count > 0}
        self.selected = [("stock", name) for name in wants]
        self.qty = dict(wants)
        self._buy_cart()

    def _toggle_marked(self, name):
        marked = self.guild.autosell
        marked.symmetric_difference_update({name})
        self.notice = (i18n.t("trade.will_be_sold_with_sell", name=name) if name in marked
                       else i18n.t("trade.no_longer_marked", name=name))

    def _distribute_load(self):
        from . import unit as unit_module
        unit_module.distribute_load(self.shoppers, share_coins=True, creatures=self.stores)
        self.selected = []
        self.notice = i18n.t("trade.redistributed_packs_by_carrying_capacity")

    # ------------------------------------------------------------------ #
    # trades                                                              #
    # ------------------------------------------------------------------ #
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
            self.notice = i18n.t("trade.won_t_fit_s_load", name=member.name)
            self.selected = picks
            return

        if zone in SLOTS:
            fit = next((p for p in picks if self._fits_slot(member, zone, self._name_of(p))), None)
            if fit is None:
                self.selected = picks
                self.notice = i18n.t("trade.doesn_t_fit_in", zone=zone)
                return
            picks = [fit]

        collected, touched = self._collect(picks)
        self._sel_qty = {}
        for name, qty in collected:
            if zone in SLOTS:
                if qty > 1:
                    fit[0].give_to_pack(name, qty - 1)
                self._equip(member, zone, name)
            else:
                member.give_to_pack(name, qty)

        for u in touched:
            u._derive_combat()
        member._derive_combat()

        if zone == "pack":
            moved = sum(qty for _, qty in collected)
            self.notice = i18n.t("trade.item_s", moved=moved, name=member.name)
        else:
            self.notice = f"{collected[0][0]} -> {member.name}'s {zone}."

    @staticmethod
    def _equip(member, zone, name):
        {"hand": member.give_to_hand, "offhand": member.give_to_offhand, "tongue": member.give_to_tongue,
         "artifact": member.give_to_artifact, "armor": member.give_to_armor}[zone](name)

    def _settle_market(self):
        """Bankers deeds read the guild's lifetime market tallies straight off
        `guild.total_spent`/`items_sold_kinds` (`factions.py`) -- fire this
        after any buy or sell that could have just crossed one, and append a
        DEED line to `self.notice` the same way the tanner does."""
        from . import objectives
        objectives.check_and_bank(self.guild)
        for d in factions.settle(self.guild, factions.Event("market", node=self.node)):
            self.notice = (self.notice or "") + "  ·  " + factions.deed_notice(d)

    def _buy(self, member, names, zone="pack"):
        if zone in SLOTS:
            name = names[0]
            if not self._fits_slot(member, zone, name):
                self.notice = i18n.t("trade.won_t_fit_s", name=name, owner=member.name, zone=zone)
                return
            stock = self._stock_of(name)
            if stock is not None and stock <= 0:
                self.notice = i18n.t("trade.no_in_stock", name=name)
                return
            price = economy.buy_price(name, self.deal)
            if self.purse < price:
                self.notice = i18n.t("trade.out_of_money")
                return
            self.purse -= price
            self._till(price)
            self.guild.total_spent += price
            if stock is not None:
                self._shop().stock[name] = stock - 1
            self._equip(member, zone, name)
            member._derive_combat()
            self.qty.pop(name, None)
            recorder.emit("buy", node=self._node_id(), item=name, qty=1, price=price, zone=zone)
            self.notice = i18n.t("trade.bought_equipped", name=member.name, item=name)
            self._opening_goals(name)
            self._settle_market()
            return

        paid, wanted, stopped = {}, sum(self._buy_qty(n) for n in names), None
        for name in names:
            for _ in range(self._buy_qty(name)):
                stopped = self._buy_one(member, name)
                if stopped:
                    break
                paid[name] = paid.get(name, 0) + 1
            if stopped:
                break
        member._derive_combat()
        self._bought(paid, names, zone)
        bought = sum(paid.values())
        what = names[0] if len(names) == 1 else i18n.t("trade.items")
        if bought and stopped:
            self.notice = i18n.t("trade.bought_of", name=member.name, bought=bought, wanted=wanted, stopped=stopped)
        elif bought:
            self.notice = i18n.t("trade.bought", name=member.name, bought=bought, what=what)
        elif stopped:
            self.notice = i18n.t("trade.stopped", reason=i18n.sentence(stopped))

    def _opening_goals(self, name):
        from . import objectives
        if items.is_food(name):
            objectives.complete(self.guild, "obj_buy_food")
        if name in ("Torch", "Lantern"):
            objectives.complete(self.guild, "obj_buy_torch")

    def _buy_one(self, member, name):
        """Buy one `name` into `member`'s pack; the reason it can't, or None."""
        stock = self._stock_of(name)
        if stock is not None and stock <= 0:
            return i18n.t("trade.no_in_stock_2", name=name)
        price = economy.buy_price(name, self.deal)
        if self.purse < price:
            return i18n.t("trade.out_of_money_2")
        if not self._fits(member, name):
            return i18n.t("trade.won_t_fit_s_load_2", name=name, owner=member.name)
        self.purse -= price
        self._till(price)
        self.guild.total_spent += price
        member.give_to_pack(name)
        if stock is not None:
            self._shop().stock[name] = stock - 1
        return None

    def _bought(self, paid, names, zone="pack"):
        """After a buy: log it, tick the opening goals, reset the steppers, settle the till."""
        for name, qty in paid.items():
            recorder.emit("buy", node=self._node_id(), item=name, qty=qty,
                          price=economy.buy_price(name, self.deal), zone=zone)
            self._opening_goals(name)
        for name in names:
            self.qty.pop(name, None)
        if paid:
            self._settle_market()

    def _buy_cart(self):
        """BUY: every row in the cart, each one into whoever has the most room for it."""
        names = [n for kind, n in self.selected if kind == "stock"]
        buyers = [*self.shoppers, *self.stores]
        paid, touched, stopped = {}, set(), None
        wanted = sum(self._buy_qty(n) for n in names)
        for name in names:
            for _ in range(self._buy_qty(name)):
                room = [m for m in buyers if self._fits(m, name)]
                if not room:
                    stopped = i18n.t("trade.no_one_has_room_for", name=name)
                    break
                member = max(room, key=lambda m: m.carry_max - m.load)
                stopped = self._buy_one(member, name)
                if stopped:
                    break
                paid[name] = paid.get(name, 0) + 1
                touched.add(member)
            if stopped:
                break
        for member in touched:
            if hasattr(member, "_derive_combat"):
                member._derive_combat()
        self._bought(paid, names)
        bought = sum(paid.values())
        if bought == wanted:
            self.selected = []
            self.notice = i18n.plural("trade.bought_shared", bought)
        elif bought:
            self.notice = i18n.t("trade.bought_of_2", bought=bought, wanted=wanted, stopped=stopped)
        else:
            self.notice = i18n.t("trade.stopped", reason=i18n.sentence(stopped))

    def _sell(self):
        picks = self._goods(self.selected)
        cash = self._cash()
        if picks and cash is not None and self._sell_total() > cash:
            self.notice = i18n.t("trade.market_only_has_to_pay", fmt_money=fmt_money(cash))
            return
        self.selected = []
        if not picks:
            self._sel_qty = {}
            return
        by_owner = {}
        for p in picks:
            by_owner.setdefault(id(p[0]), (p[0], []))[1].append(p)
        total = sold = binned = 0
        shop = self._shop()
        for owner, owner_picks in by_owner.values():
            collected, _ = self._collect(owner_picks)  # _take reads self._sel_qty -- clear after
            proceeds = sum(economy.sell_price(n, self.deal) * q for n, q in collected)
            payee = owner if owner in self.shoppers else self.shoppers[0]    # a wagon or animal takes no coin
            payee.money += proceeds
            total += proceeds
            for n, q in collected:
                price = economy.sell_price(n, self.deal)
                recorder.emit("sell", node=self._node_id(), item=n, qty=q, price=price)
                if price == 0:
                    binned += q
                    continue
                sold += q
                if shop and items.get(n) and not items.is_coin(n):
                    shop.add(n, q)
                self.guild.items_sold_kinds.add(n)
            owner._derive_combat()
        self._sel_qty = {}
        self._till(-total)
        parts = [i18n.t("trade.sold_item_s_for", sold=sold, total=total)] if sold else []
        if binned:
            parts.append(i18n.t("trade.keeper_threw_away_worthless_item", binned=binned))
        self.notice = "  ·  ".join(parts) + "."
        self._settle_market()


class LibraryCounter(Counter):
    """The Library's counter: its supplies, the day's dictionaries once the guild is known there,
    and what the shelf bought back."""

    def _build_categories(self):
        dictionaries = library_stock_dictionaries(self.guild)
        cats = [("SUPPLIES", "supplies", list(economy.LIBRARY_SUPPLIES))]
        if dictionaries:
            cats.append(("DICTIONARIES", "dictionaries", dictionaries))
        return cats

    def get_categories(self):
        cats = list(getattr(self, "_custom_categories", None) or self._build_categories())
        shop = self._shop()
        if shop and shop.strays():
            cats.append(("RESALE", "resale", shop.strays()))
        return cats

    def sync_group(self):
        super().sync_group()
        self._custom_categories = self._build_categories()


def counter_for(guild, shoppers, node):
    """The counter a node's shop keeps: the Library's own, or the town's."""
    return (LibraryCounter if node.id == "library" else Counter)(guild, shoppers, node)

"""A stash tab in the browser: the Bank's VAULT (the strongbox, the Bankers' services, the gold exchange on
a coin stack) and the City house's THE HOUSE (its stash, the tax, the oven, the debt), each on paper with
every pack of the band beside it.

The moves are `vault.BankVault` / `HouseVault`'s: a verb sets the vault's pick and calls its move, so
the stash's weight cap, the load limit on what comes out, the slots, the fee and the purse are the
vault's.
"""

from .. import economy, i18n, item_icon, items, store_column
from ..vault import BankVault, HouseVault
from .shop_tab import SLOTS, _portrait, _tip

# what each stash says of itself: where it is held, and what stands in for it before the guild has one
COPY = {owner: {field: f"vault_tab.{owner}.{field}" for field in ("title", "where", "closed", "closed_line")}
        for owner in (BankVault.OWNER, HouseVault.OWNER)}


class VaultTab:
    def __init__(self, guild, group, node, desk=BankVault):
        self.s = desk(guild, list(group.members))
        self.chest = self.s.OWNER
        self.exchanges = isinstance(self.s, BankVault)
        self.guild, self.group, self.node = guild, group, node

    # ------------------------------------------------------------------ #
    # the tab                                                             #
    # ------------------------------------------------------------------ #
    def state(self):
        s = self.s
        notice, s.notice = s.notice, None
        stash = s._stash()
        return {
            "cards": s.hub_cards(),
            "purse": s.purse,
            "chest": {"owner": self.chest, "label": i18n.t(s.LABEL), **{k: i18n.t(v) for k, v in COPY[self.chest].items()}, "open": s._open(),
                      "load": round(stash.load, 2), "capacity": stash.capacity,
                      "rows": [self._row(self.chest, i, items.stack_name(e), e[1], items.stack_note(e))
                                 for i, e in enumerate(stash.items)]},
            "services": [{"key": k, "label": label, "sub": sub, "on": on} for k, label, sub, on in s._services()],
            "packs": [self._store(o) if store_column.is_store(o) else self._member(o) for o in (*s.party, *s.stores)],
            "gold": {"price": economy.gold_price(1), "payout": economy.gold_payout(1), "fee": economy.GOLD_FEE}
                    if self.exchanges else None,
            "distribute": s.CAN_DISTRIBUTE,
            "notice": notice,
        }

    def _row(self, owner, loc, name, qty, note=""):
        row = {"loc": loc, "name": name, "qty": qty, "glyph": item_icon.glyph(name), "kg": items.item_weight(name),
               "coin": items.is_coin(name), "tip": _tip(name), "note": note}
        if not self.exchanges:
            return row
        holder = self.s._holder_of(owner)
        if name == items.COIN_ITEM:
            row["mint"] = economy.max_gold_buyable(holder)
        elif name == items.GOLD_ITEM:
            row["melt"] = economy.max_gold_sellable(holder)
        return row

    def _pack(self, owner):
        return [self._row(owner, idx, items.stack_name(e), e[1], items.stack_note(e))
                for idx, e in enumerate(owner._base_inventory)]

    def _member(self, u):
        w = items.get(u.equipped_weapon)
        worn = []
        for zone, label in SLOTS:
            if (zone == "offhand" and w and w.hands >= 2) or (zone == "tongue" and not u.has_tongue):
                continue
            name = self.s._item_at(u, zone)
            worn.append({"zone": zone, "label": label, "name": name,
                         "glyph": item_icon.glyph(name) if name else None,
                         "kg": items.item_weight(name) if name else 0, "tip": _tip(name) if name else ""})
        return {"id": u.uid, "name": u.name, "portrait": _portrait(u), "store": False,
                "sub": u.race['name'],
                "hurt": u.hp < u.hp_max, "money": u.money,
                "kg": round(u.load, 2), "normal": u.carry_normal, "max": u.carry_max,
                "worn": worn, "pack": self._pack(u)}

    def _store(self, c):
        d = store_column.store_dict(self.group, c, set(), [])
        return {"id": c.uid, "name": d["name"], "portrait": None, "store": True,
                "glyph": "item/saddle" if d.get("tack") is not None else "item/locked-chest",
                "sub": d.get("status", {}).get("text", ""), "hurt": False, "money": c.money,
                "kg": round(d["kg"], 2), "normal": d["normal"], "max": d["max"], "worn": [], "pack": self._pack(c)}

    # ------------------------------------------------------------------ #
    # what the person does                                                #
    # ------------------------------------------------------------------ #
    def _owner(self, oid):
        if oid == self.chest:
            return self.chest
        o = next((o for o in (*self.s.party, *self.s.stores) if o.uid == oid), None)
        if o is None:
            raise ValueError(i18n.t("vault_tab.no_such_pack"))
        return o

    def _pick(self, b):
        """`(owner, loc)` of a chest or pack row (`loc` its index) or a worn slot (`loc` its zone)."""
        owner, loc = self._owner(b["from"]), b["loc"]
        if isinstance(loc, str):
            if owner == self.chest or loc not in dict(SLOTS) or self.s._item_at(owner, loc) is None:
                raise ValueError(i18n.t("vault_tab.nothing_in_that_slot", loc=loc))
        elif not 0 <= loc < len(self.s._inventory(owner)):
            raise ValueError(i18n.t("vault_tab.no_such_stack"))
        return owner, loc

    def move(self, picks, to, zone="pack"):
        """Hand the picks to `to`: the stash (`self.chest`), a pack, or a member's worn slot."""
        s = self.s
        dest = self._owner(to)
        if dest == self.chest:
            zone = self.chest
        elif zone not in ("pack", *dict(SLOTS)):
            raise ValueError(i18n.t("vault_tab.no_such_slot", zone=zone))
        s.selected, s._sel_qty = [], {}
        for b in picks:
            pick = self._pick(b)
            s.selected.append(pick)
            if not isinstance(pick[1], str) and b.get("qty"):
                held = s._inventory(pick[0])[pick[1]][1]
                s._sel_qty[pick] = max(1, min(held, int(b["qty"])))
        s._give_many(dest, zone)
        s.selected, s._sel_qty = [], {}

    def service(self, key):
        offer = next((x for x in self.s._services() if x[0] == key), None)
        if offer is None or not offer[3]:
            raise ValueError(i18n.t("vault_tab.that_is_not_on_offer"))
        self.s._run_service(key)

    def exchange(self, oid, n, melt=False):
        if not self.exchanges:
            raise ValueError(i18n.t("vault_tab.gold_is_minted_and_melted"))
        holder = self.s._holder_of(self._owner(oid))
        if not self.s._exchange(holder, "sell_gold" if melt else "buy_gold", int(n)):
            raise ValueError(i18n.t("vault_tab.cannot_melt" if melt else "vault_tab.cannot_mint", n=n))

    def distribute(self):
        if not self.s.CAN_DISTRIBUTE:
            raise ValueError(i18n.t("vault_tab.load_is_not_shared_out"))
        self.s._distribute_load()

"""A hub's shop tab in the browser: the shelf, every shopper's whole kit, the purse and the till.

The trades are `trade.Counter`'s: a verb sets the
counter's pick the way a drop would and calls the same method, so the prices, the stock, the till,
the purse and the deeds stay one source.
"""

from .. import artwork, economy, item_icon, items, store_column, trade
from ..data import role_for
from .session import asset_url

SLOTS = (("hand", "Hand"), ("offhand", "Hand"), ("tongue", "Tongue"), ("armor", "Armour"), ("artifact", "Artifact"))


def _portrait(u):
    return asset_url(artwork.portrait_path(u.race["name"], getattr(u, "portrait_id", None)))


def _tip(name):
    return "\n".join(items.item_tooltip(name))


def _first_line(name):
    body = items.item_tooltip(name)[1]
    return body.split(". ")[0].removesuffix(".")


class ShopTab:
    def __init__(self, guild, group, node):
        self.m = trade.counter_for(guild, list(group.members), node)
        self.guild, self.group, self.node = guild, group, node

    # ------------------------------------------------------------------ #
    # the tab                                                             #
    # ------------------------------------------------------------------ #
    def state(self):
        m = self.m
        m.sync_group()
        notice, m.notice = m.notice, None
        owners = [*m.shoppers, *m.stores]
        voice, dist = self._voice()
        return {
            "deal": self._deal(voice, dist),
            "till": m._cash(),
            "purse": m.purse,
            "shelf": self._shelf(),
            "packs": [self._store(o) if store_column.is_store(o) else self._member(o, o is voice) for o in owners],
            "marked": sorted(m._marked()),
            "marked_total": m._marked_total(),
            "notice": notice,
        }

    def _voice(self):
        """Who haggles for the band and how far their bent is from the keeper's."""
        lang, bent = getattr(self.node, "language", None), getattr(self.node, "alignment", None)
        if not lang or not bent:
            return None, None
        return economy.haggle_voice(self.m.shoppers, lang, bent, self.group.leader)

    def _deal(self, voice, dist):
        m = self.m
        card = m._deal_card()
        lang = getattr(self.node, "language", None)
        out = {"headline": card["headline"], "tone": card["tone"], "why": card["why"],
               "pay": round((1 - economy.deal_value(m.deal, None, "buy")) * 100),
               "get": round((economy.SELL_FACTOR + 0.4 * economy.deal_value(m.deal, None, "sell")) * 100),
               "voice": None, "marks": []}
        if voice is not None:
            out["voice"] = {"uid": voice.uid, "name": voice.name, "portrait": _portrait(voice)}
            cha = voice.haggle_charisma_mod
            out["marks"] = [{"text": f"Speaks {lang}", "good": True},
                            {"text": f"Cha {cha:+d}", "good": cha > 0},
                            {"text": trade.BENT_WORDS[dist].capitalize(), "good": dist <= 1}]
        elif lang:
            out["marks"] = [{"text": f"No one speaks {' or '.join(economy.vendor_tongues(lang))}", "good": False}]
        return out

    def _shelf(self):
        m = self.m
        shop = m._shop()
        targets = shop.targets if shop else {}
        cats = []
        for label, key, names in m.get_categories():
            if key == "weapons":       # a Large weapon is a row of its own beside its Medium one
                names = [n for b in names for n in (b, f"Large {b}")
                         if items.get(n) and (n == b or (shop and n in shop.stock))]
            cats.append({"key": key, "label": label.title().replace(" And ", " & "),
                         "rows": [self._ware(n, key, targets) for n in names]})
        return cats

    def _ware(self, name, cat, targets):
        m = self.m
        stock = m._stock_of(name)
        spec = m._stock_spec(name) if cat in ("weapons", "armor") else ""
        return {"name": name, "glyph": item_icon.glyph(name), "use": spec or _first_line(name),
                "tip": _tip(name), "weight": items.item_weight(name),
                "stock": stock, "target": targets.get(name, (None, 0))[0],
                "price": economy.buy_price(name, m.deal), "list": economy.buy_price(name),
                "sell": economy.sell_price(name, m.deal)}

    def _row(self, owner, loc, name, qty):
        m = self.m
        return {"loc": loc, "name": name, "qty": qty, "glyph": item_icon.glyph(name),
                "kg": items.item_weight(name), "coin": items.is_coin(name),
                "sell": None if items.is_coin(name) else economy.sell_price(name, m.deal),
                "locked": owner.locked_of(name) > 0, "marked": name in m._marked(),
                "tip": _tip(name)}

    def _pack(self, owner):
        return [self._row(owner, idx, items.stack_name(e), e[1]) for idx, e in enumerate(owner._base_inventory)]

    def _member(self, u, voice):
        w = items.get(u.equipped_weapon)
        worn = []
        for zone, label in SLOTS:
            if zone == "offhand" and w and w.hands >= 2:
                continue
            if zone == "tongue" and not u.has_tongue:
                continue
            name = self.m._item_at(u, zone)
            worn.append({"zone": zone, "label": label, "name": name,
                         "glyph": item_icon.glyph(name) if name else None,
                         "kg": items.item_weight(name) if name else 0,
                         "sell": economy.sell_price(name, self.m.deal) if name else None,
                         "tip": _tip(name) if name else ""})
        return {"id": u.uid, "name": u.name, "portrait": _portrait(u), "store": False,
                "sub": f"{u.race['name']} · {u.occupation['name']}", "role": role_for(u.occupation),
                "voice": voice, "hurt": u.hp < u.hp_max,
                "money": u.money, "kg": round(u.load, 2), "normal": u.carry_normal, "max": u.carry_max,
                "worn": worn, "pack": self._pack(u)}

    def _store(self, s):
        d = store_column.store_dict(self.group, s, set(), [])
        return {"id": s.uid, "name": d["name"], "portrait": None, "store": True,
                "glyph": "item/saddle" if d.get("tack") is not None else "item/locked-chest",
                "sub": d.get("status", {}).get("text", ""), "voice": False, "hurt": False,
                "money": s.money, "kg": round(d["kg"], 2), "normal": d["normal"], "max": d["max"],
                "worn": ([{"zone": "tack", "label": "Tack", "name": d["tack"]["name"], "fixed": True,
                           "glyph": item_icon.glyph(d["tack"]["name"]) if d["tack"]["name"] else None,
                           "kg": items.item_weight(d["tack"]["name"]) if d["tack"]["name"] else 0}]
                         if d.get("tack") is not None else []),
                "pack": self._pack(s)}

    # ------------------------------------------------------------------ #
    # what the person does                                                #
    # ------------------------------------------------------------------ #
    def _owner(self, oid):
        o = next((o for o in (*self.m.shoppers, *self.m.stores) if o.uid == oid), None)
        if o is None:
            raise ValueError("no such pack")
        return o

    def _pick(self, b):
        """`(owner, loc)` of a pack row (`loc` its index) or a worn slot (`loc` its zone)."""
        owner, loc = self._owner(b["from"]), b["loc"]
        if isinstance(loc, str):
            if loc not in dict(SLOTS) or self.m._item_at(owner, loc) is None:
                raise ValueError(f"nothing in that {loc} slot")
        elif not 0 <= loc < len(owner._base_inventory):
            raise ValueError("no such stack")
        return owner, loc

    def _qty(self, pick, qty):
        if isinstance(pick[1], str):
            return
        held = pick[0]._base_inventory[pick[1]][1]
        self.m._sel_qty[pick] = max(1, min(held, int(qty or held)))

    def buy(self, name, qty=1, to=None, zone="pack"):
        m = self.m
        if not any(r["name"] == name for c in self._shelf() for r in c["rows"]):
            raise ValueError(f"{name} is not on this shelf")
        m.qty[name] = max(1, int(qty))
        if to is None:
            m.selected = [("stock", name)]
            m._buy_cart()
        else:
            m.selected = []
            m._buy(self._owner(to), [name], zone)

    def _select(self, picks):
        m = self.m
        m.selected, m._sel_qty = [], {}
        for b in picks:
            pick = self._pick(b)
            m.selected.append(pick)
            self._qty(pick, b.get("qty"))

    def move(self, picks, to, zone="pack"):
        if zone not in ("pack", *dict(SLOTS)):
            raise ValueError(f"no such slot: {zone}")
        dest = self._owner(to)
        self._select(picks)
        self.m._drop_on_zone(dest, zone)
        self.m.selected, self.m._sel_qty = [], {}

    def sell(self, picks):
        m = self.m
        self._select(picks)
        if not m._goods(m.selected):
            m.selected, m._sel_qty = [], {}
            raise ValueError("nothing there the shop would buy")
        m._sell()
        m.selected, m._sel_qty = [], {}

    def lock(self, oid, name):
        self._owner(oid).toggle_lock(name)

    def mark(self, name):
        self.m._toggle_marked(name)

    def sell_marked(self):
        self.m._sell_marked()
        self.m.selected, self.m._sel_qty = [], {}

    def distribute(self):
        self.m._distribute_load()

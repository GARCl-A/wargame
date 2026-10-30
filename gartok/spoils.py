"""The field's loot split among the survivors, with no pygame: the pile (`loot.field_loot`) as
stacks, a pick of part of a stack, the moves onto a member's pack or worn slot and back to the
field under each one's `carry_max`, "take what fits" and sharing the packs out by what each can
carry. Whatever is still in the pile when the report moves on is left behind.
`web/report_session.py` holds one."""

from collections import Counter

from . import items
from .loadout_move import LoadoutMoveMixin
from .unit_loadout import distribute_load

WORN = ("hand", "offhand", "tongue", "artifact", "armor")


class Spoils(LoadoutMoveMixin):
    """The pile is a third kind of owner beside the members: a pick is `("pool", idx)` or
    `(unit, loc)`, and `_sel_qty` narrows a stack pick to part of it."""

    def __init__(self, survivors, pool):
        self.survivors = survivors
        self.pool = list(Counter(pool).items())
        self.selected = []
        self._sel_qty = {}
        self.notice = None

    def _item_at(self, owner, loc):
        if owner == "pool":
            return self.pool[loc][0] if loc < len(self.pool) else None
        return super()._item_at(owner, loc)

    def _qty_at(self, owner, loc):
        if isinstance(loc, str):
            return 1 if self._item_at(owner, loc) is not None else 0
        inv = self.pool if owner == "pool" else owner._base_inventory
        full = inv[loc][1] if loc < len(inv) else 0
        return min(full, self._sel_qty.get((owner, loc), full))

    def _take(self, owner, loc):
        if isinstance(loc, str):
            return super()._take(owner, loc)
        qty = self._qty_at(owner, loc)
        if owner == "pool":
            name, total = self.pool[loc]
            if qty >= total:
                self.pool.pop(loc)
            else:
                self.pool[loc] = (name, total - qty)
            return name, qty
        return owner.take_from_pack(loc, qty), qty

    def _to_pool(self, name, qty):
        idx = next((i for i, (n, _) in enumerate(self.pool) if n == name), None)
        if idx is not None:
            self.pool[idx] = (name, self.pool[idx][1] + qty)
        else:
            self.pool.append((name, qty))

    def _deposit(self, picks):
        collected, touched = self._collect(picks)
        for name, qty in collected:
            self._to_pool(name, qty)
        for u in touched:
            if u != "pool":
                u._derive_combat()

    def _give_many(self, dst, zone):
        """Drop `self.selected` on `dst` ("pool" or a member) at `zone`; a load past the
        member's `carry_max`, or nothing that fits the slot, keeps the picks selected."""
        if dst == "pool":
            self._deposit(list(self.selected))
            return
        picks = [p for p in self.selected if self._item_at(*p) is not None]
        self.selected = []
        if not picks:
            return

        if any(owner == "pool" for owner, _ in picks):
            add = sum(items.item_weight(self._item_at(*p)) * self._qty_at(*p) for p in picks)
            if dst.load + add > dst.carry_max:
                self.notice = f"won't fit {dst.name}'s load."
                self.selected = picks
                return

        if zone in WORN:
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
                if src == "pool":
                    self._to_pool(taken_name, qty - 1)
                else:
                    src.give_to_pack(taken_name, qty - 1)
            {"hand": dst.give_to_hand, "offhand": dst.give_to_offhand,
             "tongue": dst.give_to_tongue, "artifact": dst.give_to_artifact,
             "armor": dst.give_to_armor}[zone](name)
            if src != "pool":
                src._derive_combat()
            dst._derive_combat()
            return

        if all(p[0] is dst and not isinstance(p[1], str) for p in picks):
            return
        collected, touched = self._collect(picks)
        for name, qty in collected:
            dst.give_to_pack(name, qty)
        for u in touched:
            if u != "pool":
                u._derive_combat()
        dst._derive_combat()

    def _auto_pick(self):
        """Each thing on the field to the member with the most room left that can still carry it."""
        leftover = []
        for name, qty in self.pool:
            for _ in range(qty):
                taker = next((m for m in sorted(self.survivors, key=lambda m: m.carry_max - m.load, reverse=True)
                              if m.load + items.item_weight(name) <= m.carry_max), None)
                if taker is None:
                    leftover.append(name)
                    continue
                taker.give_to_pack(name)
                taker._derive_combat()
        self.pool = list(Counter(leftover).items())
        self.selected = []
        self._sel_qty = {}

    def distribute(self):
        """Even the survivors' packs out by free carrying capacity, coins too; the field stays put."""
        if len(self.survivors) < 2:
            raise ValueError("nobody to share the load with")
        distribute_load(self.survivors)
        self.selected = []
        self._sel_qty = {}

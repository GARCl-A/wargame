"""The member-loadout moves, with no pygame: ``_item_at`` / ``_take`` / ``_give_many``
over a member's hand / off-hand / tongue / artifact / armour / pack, shared by the
guild's pack screens and the stashes (`vault.Vault`)."""

from .trade import collect


class LoadoutMoveMixin:
    """The member-loadout half shared by the guild and gear screens: read or lift
    the item at a member's slot -- ``"hand"`` / ``"offhand"`` / ``"armor"`` or a
    pack index -- and drop a batch of picks (`self.selected`) onto a slot, a pack
    or the discard, taking the first that fits a hand/armour slot and keeping the
    rest. Needs `self.selected`; the shop's counter (`trade.Counter`) tracks buy/sell
    as well and keeps its own copy.
    """

    def _collect(self, picks):
        return collect(picks, self._take)

    @staticmethod
    def _slot_of(loc):
        return loc if isinstance(loc, str) else "pack"

    def _item_at(self, unit, loc):
        if loc == "hand":
            return unit.equipped_weapon
        if loc == "offhand":
            return unit.equipped_offhand
        if loc == "tongue":
            return unit.equipped_tongue
        if loc == "artifact":
            return unit.equipped_artifact
        if loc == "armor":
            return unit.equipped_armor
        return unit._base_inventory[loc][0] if loc < len(unit._base_inventory) else None

    def _qty_at(self, unit, loc):
        """How many a pick at `loc` represents -- 1 for an equip slot, the
        whole stack's quantity for a pack pick."""
        if isinstance(loc, str):
            return 1 if self._item_at(unit, loc) is not None else 0
        return unit._base_inventory[loc][1] if loc < len(unit._base_inventory) else 0

    def _carried_names(self):
        """Names of the items currently picked up (selected / being dragged)."""
        return [n for n in (self._item_at(*p) for p in self.selected) if n is not None]

    def _take(self, src, loc):
        """Lift the pick at `loc` off `src` -- `(name, qty)`. A pack pick
        always takes its whole stack (`idx` addresses the stack, not a
        physical item); an equip slot is always qty 1."""
        if loc == "hand":
            return src.take_from_hand(), 1
        if loc == "offhand":
            return src.take_from_offhand(), 1
        if loc == "tongue":
            return src.take_from_tongue(), 1
        if loc == "artifact":
            return src.take_from_artifact(), 1
        if loc == "armor":
            return src.take_from_armor(), 1
        if loc >= len(src._base_inventory):
            return None, 0
        qty = src._base_inventory[loc][1]
        return src.take_from_pack(loc, qty), qty

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
        return True                                      # pack / discard take anything

    def _give_many(self, dst, zone):
        picks = [p for p in self.selected if self._item_at(*p) is not None]
        self.selected = []
        if not picks:
            return

        if zone == "discard":
            _, touched = self._collect(picks)
            for u in touched:
                u._derive_combat()
            return

        if zone in ("hand", "offhand", "tongue", "artifact", "armor"):
            fit = next((p for p in picks
                        if self._fits_slot(dst, zone, self._item_at(*p))
                        and not (p[0] is dst and self._slot_of(p[1]) == zone)), None)
            if fit is None:
                self.selected = picks                    # nothing fits: keep carrying
                return
            name = self._item_at(*fit)
            src = fit[0]
            taken_name, qty = self._take(*fit)
            
            # Put the rest of the stack back if we took multiple
            if qty > 1:
                src.give_to_pack(taken_name, qty - 1)
                
            {"hand": dst.give_to_hand, "offhand": dst.give_to_offhand,
             "tongue": dst.give_to_tongue, "artifact": dst.give_to_artifact,
             "armor": dst.give_to_armor}[zone](name)
            src._derive_combat()
            dst._derive_combat()
            return

        # pack
        if all(p[0] is dst and not isinstance(p[1], str) for p in picks):
            return                                       # same pack: nothing to do
        items, touched = self._collect(picks)
        for name, qty in items:
            dst.give_to_pack(name, qty)
        for u in touched:
            u._derive_combat()
        dst._derive_combat()

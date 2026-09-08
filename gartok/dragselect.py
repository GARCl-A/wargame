"""Shared press / drag / drop plumbing for the item screens.

The guild and market screens both let you click an item to pick it up (click
again to drop it) or drag it straight onto a target, with shift/ctrl to gather
several first. This mixin owns the mechanical half -- telling a click from a
drag past a few pixels of slop, and pulling a batch of picks off their owners --
and calls back into the screen for the layout-specific parts:

- `_source_at(pos)` -> the pick under the cursor, or None
- `_begin_drag(src)` -> a press just became a drag (optional; default no-op)
- `_drop(pos, dragging, src)` -> resolve the release (the click / drop logic)

`_collect(picks)` pulls every ``(owner, loc)`` pick off its owner and returns
``(names, owners touched)``; pack rows come off highest index first so an earlier
removal doesn't shift the ones still to come. It needs ``self._take(owner, loc)``.

Mix in before `Screen` so this `handle_event` wins:
``class GuildScreen(DragSelectMixin, Screen)``.

`LoadoutMoveMixin` (below) adds the member-loadout move logic the guild and gear
screens share -- ``_item_at`` / ``_take`` / ``_give_many`` over a member's
hand / off-hand / armour / pack.
"""

import pygame


class DragSelectMixin:
    DRAG_SLOP = 5                             # pixels of travel that turn a click into a drag

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._press = None                   # window pos of the current left-button press
        self._press_src = None               # the pick that press landed on, or None
        self._dragging = False               # promoted from a press once the mouse travels

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._press = event.pos
            self._press_src = self._source_at(event.pos)
            self._dragging = False
        elif (event.type == pygame.MOUSEMOTION and self._press is not None
              and self._press_src is not None and not self._dragging):
            if (abs(event.pos[0] - self._press[0])
                    + abs(event.pos[1] - self._press[1]) > self.DRAG_SLOP):
                self._dragging = True
                self._begin_drag(self._press_src)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._press is None:
                return                       # release of a press we never saw
            dragging, src = self._dragging, self._press_src
            self._press = self._press_src = None
            self._dragging = False
            self._drop(event.pos, dragging, src)

    def _begin_drag(self, src):
        """A press just crossed the slop and became a drag. Screens override to
        narrow the selection to what's under the cursor."""

    def _collect(self, picks):
        by_owner = {}
        for owner, loc in picks:
            by_owner.setdefault(id(owner), (owner, []))[1].append(loc)
        names, touched = [], []
        for owner, locs in by_owner.values():
            touched.append(owner)
            ordered = [l for l in locs if isinstance(l, str)]
            ordered += sorted((l for l in locs if not isinstance(l, str)), reverse=True)
            for loc in ordered:
                got = self._take(owner, loc)
                if got is not None:
                    names.append(got)
        return names, touched


class LoadoutMoveMixin:
    """The member-loadout half shared by the guild and gear screens: read or lift
    the item at a member's slot -- ``"hand"`` / ``"offhand"`` / ``"armor"`` or a
    pack index -- and drop a batch of picks (`self.selected`) onto a slot, a pack
    or the discard, taking the first that fits a hand/armour slot and keeping the
    rest. Needs `self.selected` and `DragSelectMixin._collect`; the market screen
    tracks buy/sell as well and keeps its own copy.
    """

    @staticmethod
    def _slot_of(loc):
        return loc if isinstance(loc, str) else "pack"

    def _item_at(self, unit, loc):
        if loc == "hand":
            return unit.equipped_weapon
        if loc == "offhand":
            return unit.equipped_offhand
        if loc == "armor":
            return unit.equipped_armor
        return unit._base_inventory[loc] if loc < len(unit._base_inventory) else None

    def _carried_names(self):
        """Names of the items currently picked up (selected / being dragged)."""
        return [n for n in (self._item_at(*p) for p in self.selected) if n is not None]

    def _take(self, src, loc):
        if loc == "hand":
            return src.take_from_hand()
        if loc == "offhand":
            return src.take_from_offhand()
        if loc == "armor":
            return src.take_from_armor()
        return src.take_from_pack(loc)

    @staticmethod
    def _fits_slot(dst, zone, name):
        if zone == "hand":
            return dst.is_weapon(name)
        if zone == "offhand":
            return dst.fits_offhand(name)
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

        if zone in ("hand", "offhand", "armor"):
            fit = next((p for p in picks
                        if self._fits_slot(dst, zone, self._item_at(*p))
                        and not (p[0] is dst and self._slot_of(p[1]) == zone)), None)
            if fit is None:
                self.selected = picks                    # nothing fits: keep carrying
                return
            name = self._item_at(*fit)
            src = fit[0]
            self._take(*fit)
            {"hand": dst.give_to_hand, "offhand": dst.give_to_offhand,
             "armor": dst.give_to_armor}[zone](name)
            src._derive_combat()
            dst._derive_combat()
            return

        # pack
        if all(p[0] is dst and not isinstance(p[1], str) for p in picks):
            return                                       # same pack: nothing to do
        names, touched = self._collect(picks)
        for name in names:
            dst.give_to_pack(name)
        for u in touched:
            u._derive_combat()
        dst._derive_combat()

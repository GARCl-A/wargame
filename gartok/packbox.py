"""Shared drag bookkeeping for the gear and group management screens.

`gear_screen.GearScreen` and `group_screen.GroupScreen` both show a per-member
loadout column (header, load bar, HANDS/OFF/(TONGUE), BODY, PACK) via
`gartok.ui.loadout_panel.column()` now, but still share the padlock hit-testing
(exempt an item from `unit.distribute_load`), the item-tag lookup `column()`'s
`pack` rows want, and the pack-column mouse-wheel scroll `column()` itself
doesn't own (it just draws whatever `scroll` offset it's handed back).
`PackColumnMixin` is what's left of the column that used to render both
screens by hand, before they moved onto `gartok/ui/`: just that bookkeeping,
no drawing of its own left.

Mix in before `Screen`, same convention as `dragselect.DragSelectMixin`:
``class GearScreen(PackColumnMixin, DragSelectMixin, LoadoutMoveMixin, Screen)``

Needs from the host screen: `self.mouse`. Screens reset `self._lock_hits = []`
and `self._pack_areas = []` at the top of `draw()` alongside their other
per-frame lists, append to `self._pack_areas` as they draw each column (see
`GearScreen._draw_columns`), and route a click through `self._lock_at(px)`
before treating it as an item pick (see `GearScreen._source_at`/`_drop`).

`bank_screen.py`/`city_property_screen.py` don't mix this in -- they keep
their own smaller `_item_tag` copy since they don't need the rest of this
contract (no lock toggling, no per-column wheel scroll on a shopping visit).
"""

import pygame

from . import data

LOCK_W = 18                          # padlock hit-box width, left of the item name -- market_screen.py still draws its own row by hand and reuses this


class PackColumnMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pack_scroll = {}       # id(unit) -> pack rows scrolled past
        self._pack_areas = []        # [(rect, unit)] -- wheel hit-testing
        self._lock_hits = []         # [(rect, unit, item_name)]

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            hit = next((u for r, u in self._pack_areas if r.collidepoint(self.mouse)), None)
            if hit is not None:
                cur = self._pack_scroll.get(id(hit), 0)
                cap = max(0, len(hit._base_inventory) - 1)
                self._pack_scroll[id(hit)] = max(0, min(cap, cur - event.y))
                return
        super().handle_event(event)

    def _lock_at(self, px):
        for r, unit, name in getattr(self, "_lock_hits", []):
            if r.collidepoint(px):
                return (unit, name)
        return None

    @staticmethod
    def _item_tag(item):
        if item in data.WEAPONS:
            return "WEAPON"
        if item in data.ARMOR:
            return "ARMOR"
        if item == data.AMMO_ITEM:
            return "AMMO"
        if item == data.FIRST_AID_ITEM:
            return "HEAL"
        if item == data.TORCH_ITEM or item in data.LIGHT_SOURCES:
            return "LIGHT"
        if item in data.FOOD_ITEMS:
            return "FOOD"
        if item == data.CHEST_ITEM:
            return "CHEST"
        if item == data.MISSION_CHEST_ITEM:
            return "SEALED"
        return ""

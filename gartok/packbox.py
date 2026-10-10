"""Shared drag bookkeeping for the pack screens.

`group_screen.GroupScreen` and `market_screen.MarketScreen` both show a per-member
loadout column (header, load bar, HANDS/OFF/(TONGUE), BODY, PACK) via
`gartok.ui.loadout_panel.column()` now, but still share the padlock hit-testing
(exempt an item from `unit.distribute_load`), the item-tag lookup `column()`'s
`pack` rows want, and the pack-column mouse-wheel scroll `column()` itself
doesn't own (it just draws whatever `scroll` offset it's handed back).
`PackColumnMixin` is what's left of the column that used to render both
screens by hand, before they moved onto `gartok/ui/`: just that bookkeeping,
no drawing of its own left.

Mix in before `Screen`, same convention as `dragselect.DragSelectMixin`:
``class GroupScreen(PackColumnMixin, DragSelectMixin, LoadoutMoveMixin, Screen)``

Needs from the host screen: `self.mouse`. Screens reset `self._lock_hits = []`
and `self._pack_areas = []` at the top of `draw()` alongside their other
per-frame lists, append to `self._pack_areas` as they draw each column (see
`GroupScreen._draw_bags`), and route a click through `self._lock_at(px)`
before treating it as an item pick (see `GroupScreen._source_at`/`_drop`).

`stash_screen.py` (the bank and the house) doesn't mix this in -- it keeps
its own smaller `_item_tag` since it doesn't need the rest of this contract
(no lock toggling, no per-column wheel scroll on a shopping visit).
"""

import pygame

from . import items

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
        return items.item_tag(item)


class SplitStackMixin:
    """The "split stack" quantity picker: peel part of a pack stack (a purse of
    coins, a bundle of rations) into its own stack so that part can be moved,
    sold or locked on its own. Needs `self.selected`, `self.menu` and
    `self.notice` from the host; `ItemMenuMixin` pulls it into every screen
    that has the ⋮ menu."""

    split_prompt = None              # {"unit","idx","name","held","amount"} while picking a quantity

    @staticmethod
    def _splittable(pick):
        """`(unit, idx)` when `pick` is a pack stack of two or more that a Unit
        owns -- a stash row is moved with its own stepper, an equip slot holds one."""
        owner, loc = pick
        if not isinstance(loc, int) or not hasattr(owner, "split_pack"):
            return None
        inv = owner._base_inventory
        return (owner, loc) if loc < len(inv) and inv[loc][1] > 1 else None

    def _can_split(self):
        return len(self.selected) == 1 and self._splittable(self.selected[0]) is not None

    def _open_split_prompt(self, picks=None):
        picks = self.selected if picks is None else picks
        target = self._splittable(picks[0]) if len(picks) == 1 else None
        self.menu = None
        if target is None:
            return
        unit, idx = target
        name, held = unit._base_inventory[idx]
        self.selected = [target]
        self.split_prompt = {"unit": unit, "idx": idx, "name": name, "held": held,
                             "amount": max(1, held // 2)}

    def _split_prompt_click(self, px):
        p = self.split_prompt
        if p is None or not p.get("rect") or not p["rect"].collidepoint(px):
            self.split_prompt = None
            return
        for r, key in p["hits"]:
            if r.collidepoint(px):
                if key == "minus":
                    p["amount"] = max(1, p["amount"] - 1)
                elif key == "plus":
                    p["amount"] = min(p["held"] - 1, p["amount"] + 1)
                elif key == "confirm":
                    p["unit"].split_pack(p["idx"], p["amount"])
                    self.notice = f"Split {p['amount']} {p['name']} into its own stack."
                    self.selected = []
                    if hasattr(self, "_sel_qty"):
                        self._sel_qty = {}
                    self.split_prompt = None
                return

    def _draw_split_prompt(self, screen, F):
        from .ui import loadout_panel
        p = self.split_prompt
        W, H = screen.get_size()
        res = loadout_panel.quantity_prompt(screen, F, (W // 2, H // 2), f"split {p['name']}",
                                            p["amount"], p["held"], "SPLIT INTO TWO STACKS",
                                            self.mouse)
        p["rect"], p["hits"] = res["rect"], res["hits"]

    def _split_hovering(self):
        return any(r.collidepoint(self.mouse) for r, _ in self.split_prompt.get("hits", ()))


class ItemMenuMixin(SplitStackMixin):
    """The popup behind a pack row's ⋮ button (and right-click): the host says
    what the rows are and what each does, this owns opening, drawing,
    hit-testing and dismissing -- and the "split stack" row and its quantity
    prompt, so every host gets them. A pick is `(owner, loc)`; the menu acts on a
    list of them.

    Host contract: `_ui_fonts()`, `self.mouse`, `self.selected`, `self.notice`,
    `_source_at(px)`, a
    `self._dots_hits = [(rect, owner, loc)]` it refills each frame,
    `_menu_rows(picks)` -> `[(kind, label, arg)]` (empty = no menu) and
    `_menu_run(picks, kind, arg)`. `_menu_picks_for(pick)` is what the menu acts
    on when opened from that row (just the row by default; a host with a
    selection widens it). Call `_menu_event(event)`
    in `handle_event` (first -- it owns the split prompt's clicks), `_dots_at(px)` before a click
    counts as a selection, `_open_menu(px, self._menu_picks_for(pick))` on a dots hit, and
    `_draw_menu(screen)` while drawing."""

    menu = None
    _dots_hits = ()

    def _dots_at(self, px):
        return next(((owner, loc) for r, owner, loc in self._dots_hits
                     if r.collidepoint(px)), None)

    def _menu_picks_for(self, pick):
        return [pick]

    def _menu_picks_at(self, px):
        src = self._source_at(px)
        return self._menu_picks_for(src) if src is not None else []

    def _open_menu(self, anchor, picks=None):
        if picks is None:
            picks = self._menu_picks_at(anchor)
        rows = self._menu_rows(picks) if picks else []
        if rows and len(picks) == 1 and self._splittable(picks[0]):
            rows = [("split", "split stack", None)] + [r for r in rows if r[0] != "split"]
        self.menu = {"anchor": anchor, "rows": rows, "picks": list(picks)} if rows else None

    def _menu_event(self, event):
        """True when the event was the menu's (a pick, a dismiss, a right-click)."""
        if event.type != pygame.MOUSEBUTTONDOWN:
            return False
        if self.split_prompt is not None:
            if event.button == 1:
                self._split_prompt_click(event.pos)
                return True
            self.split_prompt = None
        if self.menu is not None and event.button == 1:
            m, self.menu = self.menu, None
            hit = next(((kind, arg) for r, kind, arg in m.get("hits", ())
                        if r.collidepoint(event.pos)), None)
            if hit and hit[0] == "split":
                self._open_split_prompt(m["picks"])
            elif hit:
                self._menu_run(m["picks"], *hit)
            return True
        if event.button == 3:
            self._open_menu(event.pos)
            return True
        self.menu = None
        return False

    def _draw_menu(self, screen):
        from .ui import loadout_panel
        if self.menu is not None:
            res = loadout_panel.send_menu(screen, self._ui_fonts(), self.menu["anchor"],
                                          self.menu["rows"], self.mouse)
            self.menu["rect"], self.menu["hits"] = res["rect"], res["hits"]
        if self.split_prompt is not None:
            self._draw_split_prompt(screen, self._ui_fonts())

    def _menu_hovering(self):
        if self.split_prompt is not None:
            return self._split_hovering()
        return self.menu is not None and any(
            r.collidepoint(self.mouse) for r, *_ in self.menu.get("hits", ()))

"""The bank: the guild's strongbox, rented from the Bankers.

The guild owns nothing as a body except this -- a chest at the bank in the City,
rented from the Bankers for a flat fee (`economy.BANK_CHEST_PRICE`) and holding
`guild.bank_capacity` kg. This screen rents the chest and moves gear between it
and the visiting party's packs.

The visiting party's packs sit beside the chest. Only **pack** items move here --
spares in and out of storage; wielding a weapon or wearing armor still happens on
the gear screen. Stashing is free; the one cost is the strongbox rent, charged
across the party (poorest first) -- so members keep their own coin and there is
nothing to settle on the way out.

Interaction (same as the market): drag an item where it goes, or click to pick it
up and click the destination. Shift/ctrl-click gathers several items -- from the
chest, a pack, or both at once -- for one move; the per-stack stepper (`- N +` /
`ALL`) does the same without a mouse-drag. A padlock on a pack item (not the
chest -- it's shared storage) exempts it from DISTRIBUTE LOAD.
- a party member's pack item -> drop on the CHEST to stash it (needs room under
  `bank_capacity`), or on another member to hand it over;
- a chest item -> drop on a member to take it into their pack (needs room under
  their carry max);
- drop on nothing / click away to cancel.
"""

import pygame

from . import data, economy, icons
from .dragselect import DragSelectMixin
from .packbox import LOCK_W
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, SURFACE_4, WARN, ellipsize, kg, panel,
                    section, text, token_badge)
from .widgets import ButtonsMixin, footer_bar

CHEST_W = 340
WT_COL = 60                          # reserved width for the trailing weight text


class BankScreen(DragSelectMixin, ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, party, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.party = party
        self.on_done = on_done
        self.sel = []                                # [(who, idx), ...] -- who is "bank" or a Unit
        self._sel_qty = {}                           # (unit, idx) -> qty picked; bank picks are always 1
        self.notice = None
        self.chest_rows = []                         # [(rect, idx)]
        self.item_rows = []                          # [(rect, member, idx)]
        self.qty_hits = []                           # [(rect, pick, delta)]
        self.lock_hits = []                          # [(rect, member, name)]
        self.cards = []                              # [(rect, member)]
        self.buttons = []                            # [(key, rect)]
        self._pack_scroll = {}                       # "bank" | id(member) -> stacks scrolled past
        self._pack_areas = []                        # [(rect, who)] -- wheel hit-testing
        self._hot = False

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "bank"

    # ------------------------------------------------------------------ #
    def _items_of(self, who):
        return self.guild.bank_items if who == "bank" else who._base_inventory

    def _name_of(self, pick):
        who, idx = pick
        items = self._items_of(who)
        if not (0 <= idx < len(items)):
            return None
        return items[idx] if who == "bank" else items[idx][0]

    def _held_qty(self, pick):
        """Full stack quantity for a Unit pick -- meaningless for a bank pick
        (the chest is still a flat, unstacked `list[str]`; see `_get_qty`)."""
        who, idx = pick
        items = self._items_of(who)
        return items[idx][1] if 0 <= idx < len(items) else 0

    def _selected_names(self):
        return [n for n in (self._name_of(p) for p in self.sel) if n is not None]

    def _display_stacks(self, who):
        """`[(name, idx, qty)]` rows to show for `who`. A Unit's pack already
        keeps real quantities (one row per stack, `dragselect._stacks`); the
        bank chest is still a flat, unstacked `list[str]` (Decision B), so its
        rows are a physical-index group instead -- `idx` there is one
        representative index among several equal picks, same as before this
        migration."""
        items = self._items_of(who)
        if who != "bank":
            return self._stacks(items)
        groups, order = {}, []
        for i, name in enumerate(items):
            if name not in groups:
                groups[name] = []
                order.append(name)
            groups[name].append(i)
        return [(name, groups[name][-1], len(groups[name])) for name in order]

    def _get_qty(self, pick):
        who, _idx = pick
        if who == "bank":
            name = self._name_of(pick)
            if name is None:
                return 0
            all_locs = [i for i, n in enumerate(self.guild.bank_items) if n == name]
            return len([p for p in self.sel if p[0] == "bank" and p[1] in all_locs])
        held = self._held_qty(pick)
        return min(held, self._sel_qty.get(pick, held))

    @property
    def purse(self):
        """The visiting party's coin, live -- the only thing it ever spends here
        is the strongbox rent. Stashing gear is free, so members keep their own
        money; nothing is pooled and redivided on the way out."""
        return sum(m.gold for m in self.party)

    def _charge(self, amount):
        economy.charge_evenly(self.party, amount)

    def _chest_room(self, weight):
        return self.guild.bank_load + weight <= self.guild.bank_capacity

    def _fits(self, member, weight):
        return member.load + weight <= member.carry_max

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
        for rect, _pick, _delta in self.qty_hits:
            if rect.collidepoint(px):
                return None                  # a stepper press starts no drag / select
        for rect, _member, _name in self.lock_hits:
            if rect.collidepoint(px):
                return None                  # a padlock press starts no drag / select
        for rect, idx in self.chest_rows:
            if rect.collidepoint(px):
                return ("bank", idx)
        for rect, member, idx in self.item_rows:
            if rect.collidepoint(px):
                return (member, idx)
        return None

    def _begin_drag(self, src):
        if src not in self.sel:
            self.sel = [src]

    def _expand_stack(self, src):
        """Bank picks: `src` plus every other physical index carrying the same
        name (the chest is still flat/unstacked). Unit picks: `src` alone --
        `idx` already addresses the whole stack; the caller grows its qty to
        the full stack separately (see `_drop`)."""
        who, _idx = src
        if who != "bank":
            return [src]
        name = self._name_of(src)
        if name is None:
            return [src]
        return [(who, i) for i, n in enumerate(self.guild.bank_items) if n == name]

    def _collect(self, picks):
        """Pull every `(who, idx)` pick off its owner -- highest index first so
        an earlier removal doesn't shift the ones still to come. Returns
        `([(name, qty)], touched)`, `touched` being the Unit owners to
        re-derive (the chest isn't one). A Unit pick takes whatever
        `self._sel_qty` says is selected; a bank pick is always qty 1 (one
        physical index)."""
        by_owner = {}
        for who, idx in picks:
            key = "bank" if who == "bank" else id(who)
            by_owner.setdefault(key, (who, []))[1].append(idx)
        items, touched = [], []
        for who, idxs in by_owner.values():
            for idx in sorted(idxs, reverse=True):
                if who == "bank":
                    items.append((self.guild.bank_items.pop(idx), 1))
                    continue
                held = who._base_inventory[idx][1] if idx < len(who._base_inventory) else 0
                qty = min(held, self._sel_qty.get((who, idx), held))
                if qty > 0:
                    items.append((who.take_from_pack(idx, qty), qty))
            if who != "bank":
                touched.append(who)
        return items, touched

    def _bump_qty(self, pick, delta):
        step = delta * (5 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1)
        who, _idx = pick
        if who == "bank":
            name = self._name_of(pick)
            all_locs = [i for i, n in enumerate(self.guild.bank_items) if n == name]
            sel_locs = [p[1] for p in self.sel if p[0] == "bank" and p[1] in all_locs]
            if delta >= 999:
                self.sel = [p for p in self.sel if not (p[0] == "bank" and p[1] in all_locs)]
                self.sel.extend([("bank", l) for l in all_locs])
                return
            if delta > 0:
                to_add = [l for l in all_locs if l not in sel_locs][:step]
                self.sel.extend([("bank", l) for l in to_add])
            else:
                to_remove = sel_locs[-abs(step):]
                self.sel = [p for p in self.sel if not (p[0] == "bank" and p[1] in to_remove)]
            return

        held = self._held_qty(pick)
        new_qty = held if delta >= 999 else max(0, min(held, self._sel_qty.get(pick, 0) + step))
        if new_qty <= 0:
            self._sel_qty.pop(pick, None)
            self.sel = [p for p in self.sel if p != pick]
        else:
            self._sel_qty[pick] = new_qty
            if pick not in self.sel:
                self.sel.append(pick)

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            hit = next((w for r, w in self._pack_areas if r.collidepoint(self.mouse)), None)
            if hit is not None:
                n = len(self._display_stacks(hit))
                key = "bank" if hit == "bank" else id(hit)
                cur = self._pack_scroll.get(key, 0)
                self._pack_scroll[key] = max(0, min(max(0, n - 1), cur - event.y))
                return
        super().handle_event(event)

    def _drop(self, px, dragging, src):
        for key, rect in self.buttons:
            if key in ("done", "rent", "buy_property") and rect.collidepoint(px):
                if key == "done":
                    self._leave()
                elif key == "rent":
                    self._rent()
                elif key == "buy_property":
                    self._buy_property()
                return

        if dragging:
            self._resolve(px)
            self.sel = []
            self._sel_qty = {}
            return

        for rect, pick, delta in self.qty_hits:
            if rect.collidepoint(px):
                self._bump_qty(pick, delta)
                return

        for rect, member, name in self.lock_hits:
            if rect.collidepoint(px):
                member.toggle_lock(name)
                return

        for key, rect in self.buttons:
            if key == "distribute" and rect.collidepoint(px):
                self._distribute_load()
                return

        mods = pygame.key.get_mods()
        if src is not None and mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL):
            who, _idx = src
            if who == "bank":
                group = self._expand_stack(src)
                if src in self.sel:
                    self.sel = [p for p in self.sel if p not in group]
                else:
                    self.sel += [p for p in group if p not in self.sel]
            elif src in self.sel:
                self.sel = [p for p in self.sel if p != src]
                self._sel_qty.pop(src, None)
            else:
                self.sel.append(src)
                self._sel_qty[src] = self._held_qty(src)
            return

        if self.sel:
            if self._resolve(px):
                return
            self._select_one(src)
            return
        self._select_one(src)

    def _select_one(self, src):
        """Replace the current selection with just `src` (a plain click) -- a
        fresh Unit pack pick starts at qty 1; shift/ctrl and the stepper grow
        it from there. Bank picks don't track a qty (the chest is flat)."""
        self.sel = [src] if src is not None else []
        self._sel_qty = {}
        if src is not None and src[0] != "bank":
            self._sel_qty[src] = 1

    def _resolve(self, px):
        """Land the carried picks on whatever is under `px`. Returns True if the
        release was spent (moved, or bounced off a full target)."""
        picks = [p for p in self.sel if self._name_of(p) is not None]
        if not picks:
            return False

        for rect, member in self.cards:
            if rect.collidepoint(px):
                self._drop_on_member(member, picks)
                return True

        for key, rect in self.buttons:
            if key == "chest" and rect.collidepoint(px):
                self._drop_on_chest(picks)
                return True
        return False

    # ------------------------------------------------------------------ #
    def _rent(self):
        if self.guild.bank_unlocked:
            return
        if self.purse < economy.BANK_CHEST_PRICE:
            self.notice = (f"the strongbox costs {economy.BANK_CHEST_PRICE} copper — "
                           f"the party has {self.purse}.")
            return
        self._charge(economy.BANK_CHEST_PRICE)
        self.guild.rent_bank_chest()
        self.notice = (f"rented a strongbox — {self.guild.bank_capacity} kg of "
                       "storage at the bank.")

    def _buy_property(self):
        if self.guild.property_city_unlocked or self.guild.bankers_services_blocked:
            return
        if self.guild.reputation.get("bankers", 0) < economy.CITY_PROPERTY_REP_GATE:
            return
        if self.purse < economy.CITY_PROPERTY_PRICE:
            self.notice = (f"the Bankers want {economy.CITY_PROPERTY_PRICE} copper for the "
                           f"house — the party has {self.purse}.")
            return
        self._charge(economy.CITY_PROPERTY_PRICE)
        self.guild.buy_city_property()
        self.notice = "bought a house in the City — the Bankers' tax starts now."

    def _drop_on_chest(self, picks):
        if not self.guild.bank_unlocked:
            self.notice = "rent a strongbox first."
            self.sel = picks
            return
        picks = [p for p in picks if p[0] != "bank"]         # already in the chest: no-op
        if not picks:
            self.sel = []
            self._sel_qty = {}
            return
        add = sum(data.item_weight(self._name_of(p)) * self._get_qty(p) for p in picks)
        if not self._chest_room(add):
            free = self.guild.bank_capacity - self.guild.bank_load
            self.notice = f"won't fit — {free:g} kg free in the chest."
            self.sel = picks
            return
        items, touched = self._collect(picks)   # _collect reads self._sel_qty -- clear after
        self._sel_qty = {}
        for name, qty in items:
            self.guild.bank_items.extend([name] * qty)
        for u in touched:
            u._derive_combat()
        self.sel = []
        total = sum(qty for _, qty in items)
        one = items[0][0] if total == 1 else f"{total} items"
        self.notice = f"stashed {one}."

    def _drop_on_member(self, member, picks):
        picks = [p for p in picks if p[0] is not member]     # dropped back home: skip
        if not picks:
            self.sel = []
            self._sel_qty = {}
            return
        add = sum(data.item_weight(self._name_of(p)) * self._get_qty(p) for p in picks)
        if not self._fits(member, add):
            self.notice = f"won't fit {member.name}'s load."
            self.sel = picks
            return
        from_chest = all(p[0] == "bank" for p in picks)
        items, touched = self._collect(picks)   # _collect reads self._sel_qty -- clear after
        self._sel_qty = {}
        for name, qty in items:
            member.give_to_pack(name, qty)
        for u in touched:
            u._derive_combat()
        member._derive_combat()
        self.sel = []
        total = sum(qty for _, qty in items)
        one = items[0][0] if total == 1 else f"{total} items"
        self.notice = (f"{member.name} took {one}." if from_chest
                       else f"{one} → {member.name}.")

    def _distribute_load(self):
        from . import unit as unit_module
        if len(self.party) <= 1:
            return
        unit_module.distribute_load(self.party)
        self.notice = "redistributed packs by carrying capacity."

    def _leave(self):
        self.on_done()               # members kept their own coin -- nothing to settle

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self.chest_rows = []
        self.item_rows = []
        self.qty_hits = []
        self.lock_hits = []
        self.cards = []
        self._pack_areas = []
        self._reset_buttons()

        text(screen, "THE BANK", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, f"common purse: {self.purse} copper", f.body_bd, ACCENT,
             (screen.get_width() - MARGIN, MARGIN + 2), right=True)

        names = self._selected_names()
        if names:
            one = names[0] if len(names) == 1 else f"{len(names)} items"
            text(screen, f"moving {one}  ·  drop on the chest or a member  ·  "
                 "click outside to cancel", f.body, ACCENT, (MARGIN, MARGIN + 30))
        else:
            text(screen, f"{len(self.party)} at the bank  ·  the Bankers rent one "
                 "strongbox — a flat fee, no questions", f.body, INK_DIM,
                 (MARGIN, MARGIN + 30))

        top = MARGIN + 62
        chest = pygame.Rect(MARGIN, top, CHEST_W, screen.get_height() - top - 72)
        self._draw_chest(screen, chest)
        self._draw_party(screen, pygame.Rect(chest.right + MARGIN, top,
                                             screen.get_width() - chest.right - 2 * MARGIN,
                                             chest.h))
        self._draw_footer(screen)

        if self._dragging and names:
            gx, gy = self.mouse
            label = names[0] if len(names) == 1 else f"{len(names)} items"
            gr = pygame.Rect(gx + 12, gy + 6, f.body_sm.size(label)[0] + 2 * SP2, 20)
            panel(screen, gr, fill=ACCENT, border=ACCENT_INK, width=1, radius=4)
            text(screen, label, f.body_sm, ACCENT_INK, gr.center, center=True)

    # ------------------------------------------------------------------ #
    def _draw_chest(self, screen, rect):
        f = self.fonts
        names = self._selected_names()
        depositing = bool(names) and any(p[0] != "bank" for p in self.sel)
        hov = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_2,
              border=INFO if (depositing and hov) else LINE_SOFT,
              width=2 if (depositing and hov) else 1, radius=RADIUS)
        self.buttons.append(("chest", rect))

        x, w = rect.x + SP3, rect.w - 2 * SP3
        y = rect.y + SP3

        if not self.guild.property_city_unlocked and not self.guild.property_city_squatting and self.guild.bankers_debt <= 0:
            y = section(screen, "CITY PROPERTY", x, y, w, f)
            for ln in ("The Bankers sell a house inside the walls for ",
                       f"{economy.CITY_PROPERTY_PRICE} copper, taxed {economy.CITY_PROPERTY_TAX}",
                       f"copper every {economy.CITY_PROPERTY_TAX_PERIOD_DAYS} days."):
                text(screen, ln, f.body_sm, INK_DIM, (x, y))
                y += 17

            rep_ok = self.guild.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
            if not rep_ok:
                text(screen, f"needs {economy.CITY_PROPERTY_REP_GATE} reputation with the ",
                     f.body_sm, WARN, (x, y))
                y += 17
                text(screen, f"Bankers (have {self.guild.reputation.get('bankers', 0)})",
                     f.body_sm, WARN, (x, y))
                y += 17
            y += SP2
            pr = pygame.Rect(x, y, w, 38)
            can_buy = rep_ok and not self.guild.bankers_services_blocked and self.purse >= economy.CITY_PROPERTY_PRICE
            self.add_button(screen, pr, "buy_property",
                            f"BUY THE HOUSE — {economy.CITY_PROPERTY_PRICE} COPPER",
                            enabled=can_buy, primary=can_buy)
            y += 60

        y = section(screen, "THE STRONGBOX", x, y, w, f)

        if not self.guild.bank_unlocked:
            for ln in ("The guild has no strongbox yet.",
                       f"The Bankers rent one for {economy.BANK_CHEST_PRICE} copper:",
                       f"{economy.BANK_CHEST_CAPACITY} kg of storage, held safe in "
                       "the City."):
                text(screen, ln, f.body_sm, INK_DIM, (x, y))
                y += 17
            y += SP2
            r = pygame.Rect(x, y, w, 38)
            can = self.purse >= economy.BANK_CHEST_PRICE
            self.add_button(screen, r, "rent",
                            f"RENT A STRONGBOX — {economy.BANK_CHEST_PRICE} COPPER",
                            enabled=can, primary=can)
            return

        # capacity bar
        used, cap = self.guild.bank_load, self.guild.bank_capacity
        over = used > cap
        bar = pygame.Rect(x, y, w, 10)
        panel(screen, bar, fill=SURFACE_1, border=LINE_SOFT, width=1, radius=4)
        span = bar.w - 2
        fillw = int(span * min(1.0, used / max(1, cap)))
        if fillw > 0:
            pygame.draw.rect(screen, DANGER if over else OK,
                             (bar.x + 1, bar.y + 1, fillw, bar.h - 2), border_radius=3)
        y += 15
        text(screen, f"{kg(used)}  /  {kg(cap)}", f.mono_sm,
             DANGER if over else INK_DIM, (x, y))
        y += 18

        y = self._draw_stack_list(screen, "bank", x, y, w, rect.bottom - SP3,
                                  header=f"STASHED  ({len(self.guild.bank_items)})",
                                  show_lock=False)

    # ------------------------------------------------------------------ #
    def _draw_party(self, screen, area):
        n = max(1, len(self.party))
        gap = SP3
        card_w = min(300, (area.w - (n - 1) * gap) // n)
        for i, m in enumerate(self.party):
            rect = pygame.Rect(area.x + i * (card_w + gap), area.y, card_w, area.h)
            self._draw_card(screen, rect, m)
            self.cards.append((rect, m))

    def _draw_card(self, screen, rect, m):
        f = self.fonts
        pad = SP3
        names = self._selected_names()
        add = sum(data.item_weight(self._name_of(p)) * self._get_qty(p) for p in self.sel)
        incoming = bool(names) and any(p[0] is not m for p in self.sel)
        take_ok = incoming and self._fits(m, add)
        hov = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_2,
              border=OK if (take_ok and hov) else DANGER if (incoming and hov and not take_ok)
              else LINE_SOFT, width=2 if hov else 1, radius=RADIUS)

        tok = (rect.x + pad + 12, rect.y + pad + 12)
        token_badge(screen, tok, m, f)
        text(screen, m.name, f.card_name, INK, (tok[0] + 24, rect.y + pad))
        text(screen, f"{m.race['name']}  ·  {m.occupation['name']}", f.body_sm,
             INK_DIM, (tok[0] + 24, rect.y + pad + 20))

        y = rect.y + pad + 48
        over = m.load > m.carry_max
        ccol = DANGER if over else WARN if m.encumbered else OK
        text(screen, f"Load {kg(m.load)} / {kg(m.carry_normal)}", f.mono_sm, ccol,
             (rect.x + pad, y))
        y += 18

        self._draw_stack_list(screen, m, rect.x + pad, y, rect.w - 2 * pad,
                              rect.bottom - pad, header=f"PACK  ({len(m._base_inventory)})",
                              show_lock=True)

    # ------------------------------------------------------------------ #
    def _draw_stack_list(self, screen, who, x, y, w, bottom, *, header, show_lock):
        """Stacked, scrollable rows for `who`'s items (`who` is `"bank"` or a
        Unit) -- the chest and every party pack are drawn through this one path
        so the multi-select stepper, the wheel scroll and the padlock (pack
        only) all behave the same everywhere."""
        f = self.fonts
        items = self._items_of(who)
        y = section(screen, header, x, y, w, f)
        if not items:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (x, y + 2))
            return y + 22

        row_h = 24 + SP1
        area = pygame.Rect(x, y, w, max(0, bottom - y))
        self._pack_areas.append((area, who))
        stacks = self._display_stacks(who)
        visible_n = max(1, (bottom - y) // row_h)
        key = "bank" if who == "bank" else id(who)
        scroll = max(0, min(self._pack_scroll.get(key, 0), max(0, len(stacks) - visible_n)))
        self._pack_scroll[key] = scroll

        if scroll:
            text(screen, f"^ {scroll} more above", f.label, INK_FAINT, (x, y + 2))
            y += 14
        shown = stacks[scroll:scroll + visible_n]
        for name, idx, count in shown:
            r = pygame.Rect(x, y, w, 24)
            self._draw_row(screen, r, who, idx, name, count, show_lock=show_lock)
            y += row_h
        more_below = len(stacks) - scroll - len(shown)
        if more_below > 0:
            text(screen, f"v {more_below} more below", f.label, INK_FAINT, (x, y + 2))
            y += 14
        return y

    def _draw_row(self, screen, r, who, idx, name, count, *, show_lock):
        f = self.fonts
        pick = (who, idx)
        q = self._get_qty(pick)
        sel = q > 0
        hov = not self.sel and r.collidepoint(self.mouse)
        panel(screen, r, fill=ACCENT if sel else SURFACE_3 if hov else SURFACE_1,
              border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
        ink = ACCENT_INK if sel else INK

        name_x = r.x + SP2
        if show_lock:
            locked = who.locked_of(name) >= count
            lr = pygame.Rect(r.x + 2, r.y + 3, LOCK_W, 18)
            lhov = lr.collidepoint(self.mouse)
            icons.icon(screen, "lock" if locked else "unlock", lr,
                       ACCENT_INK if sel else ACCENT if locked else (INK if lhov else INK_FAINT))
            self.lock_hits.append((lr, who, name))
            name_x += LOCK_W

        bw, bh = 16, 18
        cy = r.centery
        cursor = r.right - SP2 - WT_COL
        if count > 1:
            all_btn = pygame.Rect(cursor - 28, cy - bh // 2, 28, bh)
            hov_all = all_btn.collidepoint(self.mouse)
            panel(screen, all_btn, fill=SURFACE_4 if hov_all else SURFACE_1,
                  border=ACCENT if hov_all else LINE_SOFT, width=1, radius=3)
            text(screen, "ALL", f.label, ACCENT if hov_all else INK_DIM, all_btn.center, center=True)
            self.qty_hits.append((all_btn, pick, 999))
            cursor = all_btn.x - 4

        plus = pygame.Rect(cursor - bw, cy - bh // 2, bw, bh)
        minus = pygame.Rect(plus.x - 26 - bw, cy - bh // 2, bw, bh)
        for br, glyph, delta in ((minus, "-", -1), (plus, "+", +1)):
            hov_b = br.collidepoint(self.mouse)
            panel(screen, br, fill=SURFACE_4 if hov_b else SURFACE_1,
                  border=ACCENT if hov_b else LINE_SOFT, width=1, radius=3)
            text(screen, glyph, f.body_bd, ACCENT if hov_b else INK_DIM, br.center, center=True)
            self.qty_hits.append((br, pick, delta))
        if q:
            text(screen, str(q), f.mono, ACCENT, ((minus.right + plus.x) // 2, cy - 1), center=True)

        label = name if count == 1 else f"{name}  ×{count}"
        text(screen, ellipsize(label, f.body_sm, minus.x - name_x - SP2), f.body_sm,
             ACCENT_INK if sel else ink, (name_x, r.y + 5))
        text(screen, kg(data.item_weight(name) * count), f.mono_sm,
             ACCENT_INK if sel else INK_DIM, (r.right - SP2, r.y + 6), right=True)

        if who == "bank":
            self.chest_rows.append((r, idx))
        else:
            self.item_rows.append((r, who, idx))

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen):
        secondary = ("distribute", "DISTRIBUTE LOAD") if len(self.party) > 1 else None
        footer_bar(self, screen, primary=("done", "LEAVE THE BANK"), secondary=secondary,
                  notice=self.notice)

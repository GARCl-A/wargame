"""The City property: bought from the Bankers, taxed on a cycle.

[[gartok-property-two-paths]]'s "City" path -- the counterpart to a Wilds
claim, subordinate to the Bankers rather than sovereign. `CityPropertyScreen`
is the day-to-day screen (buy it, stash gear in it, pay off any debt) --
the same shape as `bank_screen.BankScreen`'s strongbox (equip slots live on
every member column here too, and money is pooled for the visit the same
way), just with a recurring tax instead of a one-off fee, and no equivalent
of the strongbox's second "rent" step. `RepossessionScreen` is the choice
forced once too many tax cycles are missed (`guild.property_city_repossession_due`):
return the property (and owe the Bankers), or keep it and become an illegal
occupier -- same three-way modal shape `justice_screen.GuardScreen` uses for
the guard's catch, just two options instead of three (there is no "fight" here,
only later, if the guild squats and the guard actually comes -- `campaign.py`'s
"eviction" pause).
"""

import pygame

from . import data, economy
from .dragselect import DragSelectMixin, LoadoutMoveMixin
from .screen import Screen
from .theme import (DANGER, INFO, INK, INK_DIM, MARGIN, SP2, SP3,
                    SURFACE_2, SURFACE_3, panel, set_pointer, text, wrap_lines)
from .ui import loadout_panel
from .ui.inspector_panel import role_for
from .ui.primitives import draw_button, header
from .ui.primitives import text as ui_text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .widgets import ModalScreen

RAIL_W = 230
COL_MIN, COL_MAX = 300, 420
HOUSE_W = 360


class CityPropertyScreen(DragSelectMixin, LoadoutMoveMixin, Screen):
    native = True

    def __init__(self, fonts, guild, party, on_done):
        super().__init__()
        self.fonts = fonts
        self._F = None
        self.guild = guild
        self.party = party
        self.on_done = on_done
        self._orig_gold = {m: m.gold for m in party}
        self.purse = sum(self._orig_gold.values())
        self.selected = []
        self._sel_qty = {}
        self.pinned = list(party)
        self.notice = None
        self.buttons = []
        self.sources = []
        self.zones = []
        self._rail_hits = []
        self._rail_rect = None
        self._rail_scroll = 0
        self._rail_max_scroll = 0
        self._pack_scroll = {}
        self._house_scroll = 0
        self._service_hits = []
        self._unit_by_uid = {u.uid: u for u in party}
        self.back_rect = None

    def tutorial_key(self):
        return None

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

    # ------------------------------------------------------------------ #
    # LoadoutMoveMixin overrides -- see bank_screen.py's twin methods for  #
    # why these exist (a "house" owner with no `_derive_combat`, and a     #
    # stepper-adjustable partial qty for house/pack picks alike)          #
    # ------------------------------------------------------------------ #
    def _item_at(self, owner, loc):
        if owner == "house":
            items = self.guild.property_city_items
            return items[loc][0] if loc < len(items) else None
        return super()._item_at(owner, loc)

    def _qty_at(self, owner, loc):
        if isinstance(loc, str):
            return 1 if self._item_at(owner, loc) is not None else 0
        items = self.guild.property_city_items if owner == "house" else owner._base_inventory
        full = items[loc][1] if loc < len(items) else 0
        return min(full, self._sel_qty.get((owner, loc), full))

    def _take(self, owner, loc):
        if isinstance(loc, str):
            return super()._take(owner, loc)
        qty = self._qty_at(owner, loc)
        if owner == "house":
            return self.guild.take_from_property(loc, qty)
        return owner.take_from_pack(loc, qty), qty

    def _give_many(self, dst, zone):
        if dst == "house":
            self._deposit(list(self.selected))
            return
        picks = [p for p in self.selected if self._item_at(*p) is not None]
        self.selected = []
        if not picks:
            return

        from_house = any(owner == "house" for owner, _ in picks)
        if from_house:
            add = sum(data.item_weight(self._item_at(*p)) * self._qty_at(*p) for p in picks)
            if dst.load + add > dst.carry_max:
                self.notice = f"won't fit {dst.name}'s load."
                self.selected = picks
                return

        if zone in ("hand", "offhand", "tongue", "armor"):
            fit = next((p for p in picks
                       if self._fits_slot(dst, zone, self._item_at(*p))
                       and not (p[0] is dst and self._slot_of(p[1]) == zone)), None)
            if fit is None:
                self.selected = picks
                return
            name = self._item_at(*fit)
            src = fit[0]
            self._take(*fit)
            {"hand": dst.give_to_hand, "offhand": dst.give_to_offhand,
             "tongue": dst.give_to_tongue, "armor": dst.give_to_armor}[zone](name)
            if src != "house":
                src._derive_combat()
            dst._derive_combat()
            return

        if all(p[0] is dst and not isinstance(p[1], str) for p in picks):
            return
        items, touched = self._collect(picks)
        for name, qty in items:
            dst.give_to_pack(name, qty)
        for u in touched:
            if u != "house":
                u._derive_combat()
        dst._derive_combat()

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
        for rect, owner, loc in self.sources:
            if rect.collidepoint(px):
                return (owner, loc)
        return None

    def _zone_at(self, px):
        for rect, owner, zone in self.zones:
            if rect.collidepoint(px):
                return (owner, zone)
        return None

    def _begin_drag(self, src):
        if src not in self.selected:
            self.selected = [src]

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            if self._rail_rect and self._rail_rect.collidepoint(self.mouse):
                self._rail_scroll = max(0, min(self._rail_max_scroll,
                                               self._rail_scroll - event.y * 40))
                return
        super().handle_event(event)

    def _drop(self, px, dragging, src):
        if dragging:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            self.selected, self._sel_qty = [], {}
            return

        for rect, key, delta in self._house_steppers:
            if rect.collidepoint(px):
                self._bump_qty(key, delta)
                return

        for rect, key in self._service_hits:
            if rect.collidepoint(px):
                self._run_service(key)
                return

        for key, rect in self.buttons:
            if rect.collidepoint(px) and key == "done":
                self._leave()
                return

        mods = pygame.key.get_mods()
        if src is not None and mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL):
            if src in self.selected:
                self.selected.remove(src)
                self._sel_qty.pop(src, None)
            else:
                self.selected.append(src)
            return

        if self.selected:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
                self.selected, self._sel_qty = [], {}
                return
            if src in self.selected:
                self.selected, self._sel_qty = [], {}
            elif src is not None:
                self.selected, self._sel_qty = [src], {}
            else:
                self.selected, self._sel_qty = [], {}
            return

        for rect, unit in self._rail_hits:
            if rect.collidepoint(px):
                if unit in self.pinned:
                    self.pinned.remove(unit)
                else:
                    self.pinned.append(unit)
                return

        self.selected = [src] if src is not None else []

    def _bump_qty(self, pick, delta):
        step = delta * (5 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1)
        owner, loc = pick
        items = self.guild.property_city_items if owner == "house" else owner._base_inventory
        full = items[loc][1] if loc < len(items) else 0
        cur = self._sel_qty.get(pick, full)
        new = full if delta >= 999 else max(0, min(full, cur + step))
        if new <= 0:
            self._sel_qty.pop(pick, None)
            self.selected = [p for p in self.selected if p != pick]
        else:
            self._sel_qty[pick] = new
            if pick not in self.selected:
                self.selected.append(pick)

    # ------------------------------------------------------------------ #
    # money + services                                                   #
    # ------------------------------------------------------------------ #
    def _run_service(self, key):
        if key == "buy":
            rep_ok = self.guild.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
            if not rep_ok or self.guild.bankers_services_blocked:
                return
            if self.purse < economy.CITY_PROPERTY_PRICE:
                self.notice = (f"the Bankers want {economy.CITY_PROPERTY_PRICE} copper for "
                               f"the house -- the party has {self.purse}.")
                return
            self.purse -= economy.CITY_PROPERTY_PRICE
            self.guild.buy_city_property()
            self.notice = "bought a house in the City -- the Bankers' tax starts now."
        elif key == "pay_debt":
            amount = min(self.purse, self.guild.bankers_debt)
            if amount <= 0:
                self.notice = "the party has no copper to pay with."
                return
            self.purse -= amount
            self.guild.pay_bankers_debt(amount)
            self.notice = (f"paid {amount} copper toward the debt." if self.guild.bankers_debt > 0
                           else "debt cleared -- the Bankers deal with the guild again.")

    def _leave(self):
        economy.settle_pooled_purse(self.party, self._orig_gold, self.purse)
        self.on_done()

    def _deposit(self, picks):
        picks = [p for p in picks if p[0] != "house" and self._item_at(*p) is not None]
        if not picks:
            self.selected, self._sel_qty = [], {}
            return
        add = sum(data.item_weight(self._item_at(*p)) * self._qty_at(*p) for p in picks)
        if not self.guild.property_city_unlocked:
            self.notice = "buy the house first."
            self.selected = picks
            return
        if self.guild.property_city_load + add > economy.CITY_PROPERTY_CAPACITY:
            free = economy.CITY_PROPERTY_CAPACITY - self.guild.property_city_load
            self.notice = f"won't fit -- {free:g} kg free at the property."
            self.selected = picks
            return
        items, touched = self._collect(picks)
        self._sel_qty = {}
        for name, qty in items:
            self.guild.stash_in_property(name, qty)
        for u in touched:
            u._derive_combat()
        total = sum(q for _, q in items)
        one = items[0][0] if total == 1 else f"{total} items"
        self.notice = f"stashed {one}."

    # ------------------------------------------------------------------ #
    # adapters: real Unit -> the plain dicts loadout_panel draws          #
    # ------------------------------------------------------------------ #
    def _item_tag(self, name):
        if name in data.WEAPONS:
            return "WEAPON"
        if name in data.ARMOR:
            return "ARMOR"
        return ""

    def _hand_note(self, unit):
        name = unit.equipped_weapon
        if not name or name not in data.WEAPONS:
            return None
        hit_bonus, _ = unit.attack_bonus
        dn, faces = data.WEAPONS[name]["damage"]
        return f"{hit_bonus:+} hit  ·  {dn}d{faces} dmg"

    @staticmethod
    def _armor_note(unit):
        name = unit.equipped_armor
        if not name or name not in data.ARMOR:
            return None
        return f"+{data.ARMOR[name]['ac']} AC"

    def _member_dict(self, unit, carried):
        two_handed = bool(unit.equipped_weapon) and data.WEAPONS[unit.equipped_weapon]["hands"] >= 2
        selected_locs = {loc for owner, loc in self.selected if owner is unit}

        def held(kind, name, note):
            return {"name": name, "note": note, "sel": kind in selected_locs,
                    "accepts": bool(carried) and any(self._fits_slot(unit, kind, n) for n in carried)}

        member = {
            "name": unit.name, "role": role_for(unit.occupation),
            "pending_picks": bool(unit.pending_picks),
            "kg": unit.load, "cap": unit.carry_normal,
            "hand": held("hand", unit.equipped_weapon, self._hand_note(unit)),
            "offhand": None if two_handed else held("offhand", unit.equipped_offhand, None),
            "armor": held("armor", unit.equipped_armor, self._armor_note(unit)),
            "pack": [(name, self._item_tag(name), data.item_weight(name), qty,
                     unit.locked_of(name) > 0, idx in selected_locs)
                    for idx, (name, qty) in enumerate(unit._base_inventory)],
        }
        if unit.has_tongue:
            member["tongue"] = held("tongue", unit.equipped_tongue, None)
        return member

    def _house_rows(self):
        rows = []
        sel_house = {loc: self._qty_at("house", loc) for owner, loc in self.selected if owner == "house"}
        for idx, (name, qty) in enumerate(self.guild.property_city_items):
            rows.append((idx, name, self._item_tag(name), data.item_weight(name), qty,
                        None, None, None, sel_house.get(idx, 0)))
        return rows

    # ------------------------------------------------------------------ #
    def _draw_rail(self, screen, F, rect):
        members = [{"key": u.uid, "name": u.name, "role": role_for(u.occupation),
                    "kg": u.load, "cap": u.carry_normal} for u in self.party]
        pinned_keys = {u.uid for u in self.pinned}
        hits, max_scroll = loadout_panel.rail(screen, F, rect, members, pinned_keys,
                                              bool(self.selected), self._rail_scroll, self.mouse)
        self._rail_rect = rect
        self._rail_max_scroll = max_scroll
        self._rail_scroll = max(0, min(self._rail_scroll, max_scroll))
        self._rail_hits = [(r, self._unit_by_uid[uid]) for r, uid in hits]
        for r, u in self._rail_hits:
            self.zones.append((r, u, "pack"))

    def _draw_columns(self, screen, F, area):
        gap = T.S * 2
        shown = [u for u in self.pinned if u in self.party]
        cap = max(1, (area.w + gap) // (COL_MIN + gap))
        shown = shown[:cap]
        n = max(1, len(shown))
        col_w = min(COL_MAX, max(COL_MIN, (area.w - (n - 1) * gap) // n))
        carried = self._carried_names()

        for i, u in enumerate(shown):
            r = pygame.Rect(area.x + i * (col_w + gap), area.y, col_w, area.h)
            member = self._member_dict(u, carried)
            res = loadout_panel.column(screen, F, r, member, self._pack_scroll.get(id(u), 0), self.mouse)
            self._pack_scroll[id(u)] = res["scroll"]
            for kind, slot_rect in res["slot_rects"].items():
                if slot_rect is None:
                    continue
                self.zones.append((slot_rect, u, kind))
                if member[kind]["name"]:
                    self.sources.append((slot_rect, u, kind))
            self.zones.append((res["pack_zone"], u, "pack"))
            for pr, idx in res["pack_hits"]:
                self.sources.append((pr, u, idx))

        hidden = len(self.pinned) - len(shown)
        if hidden > 0:
            ui_text(screen, F["body_sm"], f"+{hidden} pinned but hidden -- widen the window",
                (area.x, area.bottom + 4), T.TX_FAINT)
        if not shown:
            ui_text(screen, F["body"], "Pin a member on the left to see their gear.",
                area.center, T.TX_FAINT, center=True)

    def _draw_house(self, screen, F, rect):
        x, w = rect.x + T.S * 2, rect.w - T.S * 4
        y = rect.y + T.S * 2

        if self.guild.bankers_debt > 0:
            for ln in (f"owed to the Bankers: {self.guild.bankers_debt} copper",
                      "their other services are shut until it's paid"):
                ui_text(screen, F["body_sm"], ln, (x, y), T.BLOOD)
                y += 16
            y += T.S
            can_pay = self.purse > 0
            r = pygame.Rect(x, y, w, T.S * 4)
            draw_button(screen, F, r, "PAY TOWARD THE DEBT", primary=can_pay,
                       ghost=not can_pay, mpos=self.mouse)
            if can_pay:
                self._service_hits.append((r, "pay_debt"))
            y = r.bottom + T.S * 2

        if self.guild.property_city_squatting:
            for ln in ("squatting -- no tax, but the guard raids this place",):
                ui_text(screen, F["body_sm"], ln, (x, y), T.BLOOD)
                y += 16
            y += T.S
        elif self.guild.property_city_unlocked:
            due = self.guild.property_city_tax_due_day
            ui_text(screen, F["body_sm"], f"next tax due day {due}: {economy.CITY_PROPERTY_TAX} c",
                (x, y), T.TX_FAINT)
            y += 16
            if self.guild.property_city_missed_payments:
                left = (economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT
                       - self.guild.property_city_missed_payments)
                ui_text(screen, F["body_sm"],
                    f"{self.guild.property_city_missed_payments} cycle(s) missed -- "
                    f"{max(0, left)} more before the Bankers act", (x, y), T.BRASS)
                y += 16
            y += T.S

        services = []
        if not self.guild.property_city_unlocked and not self.guild.property_city_squatting:
            rep_ok = self.guild.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
            can_buy = rep_ok and not self.guild.bankers_services_blocked and self.purse >= economy.CITY_PROPERTY_PRICE
            sub = (f"{economy.CITY_PROPERTY_PRICE} c  ·  needs {economy.CITY_PROPERTY_REP_GATE} "
                  f"standing with the Bankers (have {self.guild.reputation.get('bankers', 0)})")
            services.append(("buy", "BUY THE HOUSE", sub, can_buy))

        panel_rect = pygame.Rect(rect.x, y, rect.w, rect.bottom - y)
        data_ = {"label": "the house",
                "capacity": (self.guild.property_city_load, economy.CITY_PROPERTY_CAPACITY)
                           if self.guild.property_city_unlocked else None,
                "rows": self._house_rows() if self.guild.property_city_unlocked else [],
                "services": services}
        res = loadout_panel.container_panel(screen, F, panel_rect, data_, self._house_scroll, self.mouse)
        self._house_scroll = res["scroll"]
        self._service_hits += res["service_hits"]
        self._house_steppers = []
        for r, idx in res["row_hits"]:
            self.sources.append((r, "house", idx))
        for idx, ctl in res["row_controls"].items():
            if ctl["minus"]:
                self._house_steppers.append((ctl["minus"], ("house", idx), -1))
            if ctl["plus"]:
                self._house_steppers.append((ctl["plus"], ("house", idx), 1))
            if ctl["all"]:
                self._house_steppers.append((ctl["all"], ("house", idx), 999))
        if self.guild.property_city_unlocked:
            self.zones.append((panel_rect, "house", "house"))

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self._unit_by_uid = {u.uid: u for u in self.party}
        self.zones, self.sources, self.buttons, self._service_hits = [], [], [], []
        self._house_steppers = []

        head = pygame.Rect(0, 0, W, T.S * 9)
        body = pygame.Rect(0, head.bottom, W, H - head.bottom - T.S * 10)
        house_rect = pygame.Rect(0, body.y, HOUSE_W, body.h)
        rail_rect = pygame.Rect(house_rect.right, body.y, RAIL_W, body.h)
        cols = pygame.Rect(rail_rect.right, body.y, W - rail_rect.right, body.h)

        header(screen, F, head, "The City Property",
              "a house inside the walls, bought from the Bankers -- taxed on a cycle",
              (), None, mpos=self.mouse)
        self.back_rect = pygame.Rect(head.x, head.y, T.S * 6, head.h)
        ui_text(screen, F["microb"], f"purse {self.purse} c", (W - T.S * 3, T.S * 3), T.BRASS, right=True)

        self._draw_house(screen, F, house_rect)
        self._draw_rail(screen, F, rail_rect)
        self._draw_columns(screen, F, cols.inflate(-T.S * 2, -T.S * 2))

        done_r = pygame.Rect(T.S * 2, H - T.S * 8, T.S * 28, T.S * 4)
        draw_button(screen, F, done_r, "leave the property", primary=True, mpos=self.mouse)
        self.buttons.append(("done", done_r))
        if self.notice:
            ui_text(screen, F["body_sm"], self.notice, (done_r.right + T.S * 2, H - T.S * 8 + 10), T.BRASS)
        set_pointer(self._hovering())

    def _hovering(self):
        if self.back_rect is not None and self.back_rect.collidepoint(self.mouse):
            return True
        if any(r.collidepoint(self.mouse) for _, r in self.buttons):
            return True
        if any(r.collidepoint(self.mouse) for r, _ in self._rail_hits):
            return True
        if any(r.collidepoint(self.mouse) for r, *_ in self._service_hits):
            return True
        return any(r.collidepoint(self.mouse) for r, *_ in self.sources)


class RepossessionScreen(ModalScreen, Screen):
    """Forced open instead of `CityPropertyScreen` once
    `guild.property_city_repossession_due` -- the Bankers want their house
    back, or their tax paid; there is no third option here (unlike
    `justice_screen.GuardScreen`'s FIGHT, squatting is not a fight, it's a
    standing risk played out later, in `campaign.py`'s "eviction" pause).
    No `resume_to` -- there is no screen underneath to freeze, so the shared
    modal frame falls back to a flat backdrop (`draw_scene_behind`'s except
    branch). Untouched by the container-transfer rework above -- a binary
    choice modal, no gear moves here at all."""

    native = True

    def __init__(self, fonts, guild, on_return, on_squat):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.on_return = on_return
        self.on_squat = on_squat
        self.buttons = []

    def tutorial_key(self):
        return None

    def on_button(self, key):
        if key == "return":
            self.on_return()
        elif key == "squat":
            self.on_squat()

    def _lines(self, w):
        f = self.fonts
        missed = self.guild.property_city_missed_payments
        owed = missed * economy.CITY_PROPERTY_TAX
        warn = wrap_lines([(f"{missed} tax cycles missed -- {owed} copper behind. "
                           "The Bankers want the house back, or the debt paid.")],
                          f.body, w)
        return owed, warn

    def card_rect(self, size):
        W, H = size
        f = self.fonts
        w = min(560, W - 2 * MARGIN) + 2 * SP3
        _, warn = self._lines(w - 2 * SP3)
        h = (SP3 + f.title.get_height() + SP2 + len(warn) * (f.body.get_height() + 2)
             + SP2 + 56 + SP2 + 56 + SP3)
        r = pygame.Rect(0, 0, w, h)
        r.center = (W // 2, H // 2)
        return r

    def draw_body(self, screen, card):
        f = self.fonts
        text(screen, "THE BANKERS", f.title, INK, (card.x + SP3, card.y + SP3))
        owed, warn = self._lines(card.w - 2 * SP3)
        y = card.y + SP3 + f.title.get_height() + SP2
        for ln in warn:
            text(screen, ln, f.body, DANGER, (card.x + SP3, y))
            y += f.body.get_height() + 2
        y += SP2

        y = self._option(screen, card, "return", "RETURN THE PROPERTY",
                         f"Hand it back. The guild owes {owed} copper -- the "
                         "Bankers' other services are shut until it's paid.",
                         y, INFO)
        self._option(screen, card, "squat", "REFUSE -- SQUAT",
                     "Keep the house without paying. No more tax, but the guard "
                     "will come to clear it out, sooner or later.",
                     y, DANGER)

    def _option(self, screen, card, key, label, sub, top, col):
        f = self.fonts
        r = pygame.Rect(card.x + SP3, top, card.w - 2 * SP3, 56)
        hov = r.collidepoint(self.mouse)
        panel(screen, r, fill=SURFACE_3 if hov else SURFACE_2, border=col,
              width=2 if hov else 1, radius=8)
        text(screen, label, f.body_bd, col, (r.x + SP3, r.y + 8))
        text(screen, sub, f.body_sm, INK_DIM, (r.x + SP3, r.y + 30))
        self.buttons.append((key, r))
        return r.bottom + SP2

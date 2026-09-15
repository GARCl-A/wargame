"""The City property: bought from the Bankers, taxed on a cycle.

[[gartok-property-two-paths]]'s "City" path -- the counterpart to a Wilds
claim, subordinate to the Bankers rather than sovereign. `CityPropertyScreen`
is the day-to-day screen (buy it, stash gear in it, pay off any debt) --
almost the same shape as `bank_screen.BankScreen`'s strongbox, just with a
recurring tax instead of a one-off fee. `RepossessionScreen` is the choice
forced once too many tax cycles are missed (`guild.property_city_repossession_due`):
return the property (and owe the Bankers), or keep it and become an illegal
occupier -- same three-way modal shape `justice_screen.GuardScreen` uses for
the guard's catch, just two options instead of three (there is no "fight" here,
only later, if the guild squats and the guard actually comes -- `campaign.py`'s
"eviction" pause).
"""

import pygame

from . import data, economy
from .dragselect import DragSelectMixin
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, WARN, ellipsize, kg, panel, section,
                    text, token_badge, wrap_lines)
from .widgets import ButtonsMixin, ModalScreen, footer_bar

HOUSE_W = 392
PACK_ROWS_SHOWN = 10


class CityPropertyScreen(DragSelectMixin, ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, party, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.party = party
        self.on_done = on_done
        self.sel = None
        self.notice = None
        self.house_rows = []
        self.item_rows = []
        self.cards = []
        self.buttons = []
        self._hot = False

    def tutorial_key(self):
        return None

    # ------------------------------------------------------------------ #
    def _name_of(self, pick):
        if pick is None:
            return None
        who, idx = pick
        if who == "house":
            return (self.guild.property_city_items[idx]
                    if idx < len(self.guild.property_city_items) else None)
        return who._base_inventory[idx] if idx < len(who._base_inventory) else None

    @property
    def purse(self):
        return sum(m.gold for m in self.party)

    def _charge(self, amount):
        economy.charge_evenly(self.party, amount)

    @property
    def _from_house(self):
        return self.sel is not None and self.sel[0] == "house"

    def _house_room(self, name):
        return self.guild.property_city_load + data.item_weight(name) <= economy.CITY_PROPERTY_CAPACITY

    def _fits(self, member, name):
        return member.load + data.item_weight(name) <= member.carry_max

    @property
    def _rep_ok(self):
        return self.guild.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
        for rect, idx in self.house_rows:
            if rect.collidepoint(px):
                return ("house", idx)
        for rect, member, idx in self.item_rows:
            if rect.collidepoint(px):
                return (member, idx)
        return None

    def _begin_drag(self, src):
        self.sel = src

    def _drop(self, px, dragging, src):
        for key, rect in self.buttons:
            if key in ("done", "buy", "pay_debt") and rect.collidepoint(px):
                {"done": self._leave, "buy": self._buy,
                 "pay_debt": self._pay_debt}[key]()
                return

        if dragging:
            self._resolve(px)
            self.sel = None
            return

        if self.sel is not None:
            if self._resolve(px):
                self.sel = None
                return
            self.sel = None if src == self.sel else src
            return
        self.sel = src

    def _resolve(self, px):
        if self.sel is None or self._name_of(self.sel) is None:
            return False
        name = self._name_of(self.sel)

        for rect, member in self.cards:
            if rect.collidepoint(px):
                if self._from_house:
                    self._withdraw(member)
                elif self.sel[0] is not member:
                    self._hand_over(member)
                return True

        for key, rect in self.buttons:
            if key == "house" and rect.collidepoint(px) and not self._from_house:
                self._deposit()
                return True
        return False

    # ------------------------------------------------------------------ #
    def _buy(self):
        if self.guild.property_city_unlocked or self.guild.bankers_services_blocked:
            return
        if not self._rep_ok:
            return
        if self.purse < economy.CITY_PROPERTY_PRICE:
            self.notice = (f"the Bankers want {economy.CITY_PROPERTY_PRICE} copper for the "
                           f"house -- the party has {self.purse}.")
            return
        self._charge(economy.CITY_PROPERTY_PRICE)
        self.guild.buy_city_property()
        self.notice = "bought a house in the City -- the Bankers' tax starts now."

    def _pay_debt(self):
        if self.guild.bankers_debt <= 0:
            return
        amount = min(self.purse, self.guild.bankers_debt)
        if amount <= 0:
            self.notice = "the party has no copper to pay with."
            return
        self._charge(amount)
        self.guild.pay_bankers_debt(amount)
        self.notice = (f"paid {amount} copper toward the debt."
                       if self.guild.bankers_debt > 0
                       else "debt cleared -- the Bankers deal with the guild again.")

    def _deposit(self):
        name = self._name_of(self.sel)
        member = self.sel[0]
        if not self._house_room(name):
            free = economy.CITY_PROPERTY_CAPACITY - self.guild.property_city_load
            self.notice = f"{name} won't fit -- {free:g} kg free at the property."
            return
        member.take_from_pack(self.sel[1])
        self.guild.property_city_items.append(name)
        member._derive_combat()
        self.notice = f"stashed {name}."

    def _withdraw(self, member):
        name = self._name_of(self.sel)
        if not self._fits(member, name):
            self.notice = f"{name} won't fit {member.name}'s load."
            return
        self.guild.property_city_items.pop(self.sel[1])
        member.give_to_pack(name)
        member._derive_combat()
        self.notice = f"{member.name} took {name}."

    def _hand_over(self, member):
        name = self._name_of(self.sel)
        src = self.sel[0]
        if not self._fits(member, name):
            self.notice = f"{name} won't fit {member.name}'s load."
            return
        src.take_from_pack(self.sel[1])
        member.give_to_pack(name)
        src._derive_combat()
        member._derive_combat()
        self.notice = f"{name} -> {member.name}."

    def _leave(self):
        self.on_done()

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self.house_rows = []
        self.item_rows = []
        self.cards = []
        self._reset_buttons()

        text(screen, "THE CITY PROPERTY", f.title, INK, (MARGIN, MARGIN - 2))
        text(screen, f"common purse: {self.purse} copper", f.body_bd, ACCENT,
             (screen.get_width() - MARGIN, MARGIN + 2), right=True)

        name = self._name_of(self.sel)
        if name:
            where = "the house" if self._from_house else self.sel[0].name + "'s pack"
            text(screen, f"moving {name} from {where}  ·  drop on the house or a "
                 "member  ·  click outside to cancel", f.body, ACCENT,
                 (MARGIN, MARGIN + 30))
        else:
            text(screen, "a house inside the walls, bought from the Bankers -- taxed "
                 "on a cycle", f.body, INK_DIM, (MARGIN, MARGIN + 30))

        top = MARGIN + 62
        house = pygame.Rect(MARGIN, top, HOUSE_W, screen.get_height() - top - 72)
        self._draw_house(screen, house)
        self._draw_party(screen, pygame.Rect(house.right + MARGIN, top,
                                             screen.get_width() - house.right - 2 * MARGIN,
                                             house.h))
        self._draw_footer(screen)

        if self._dragging and name:
            gx, gy = self.mouse
            gr = pygame.Rect(gx + 12, gy + 6, f.body_sm.size(name)[0] + 2 * SP2, 20)
            panel(screen, gr, fill=ACCENT, border=ACCENT_INK, width=1, radius=4)
            text(screen, name, f.body_sm, ACCENT_INK, gr.center, center=True)

    # ------------------------------------------------------------------ #
    def _draw_house(self, screen, rect):
        f = self.fonts
        carried = self._name_of(self.sel)
        depositing = bool(carried) and not self._from_house
        hov = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_2,
              border=INFO if (depositing and hov) else LINE_SOFT,
              width=2 if (depositing and hov) else 1, radius=RADIUS)
        if self.guild.property_city_unlocked:
            self.buttons.append(("house", rect))

        x, w = rect.x + SP3, rect.w - 2 * SP3
        y = section(screen, "THE HOUSE", x, rect.y + SP3, w, f)

        if self.guild.bankers_debt > 0:
            y = self._draw_debt(screen, x, y, w)

        if not self.guild.property_city_unlocked:
            y = self._draw_buy_offer(screen, x, y, w)
            return

        used, cap = self.guild.property_city_load, economy.CITY_PROPERTY_CAPACITY
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

        if self.guild.property_city_squatting:
            text(screen, "SQUATTING -- no tax, but the guard raids this place",
                 f.body_sm, DANGER, (x, y))
            y += 17
        else:
            due = self.guild.property_city_tax_due_day
            text(screen, f"next tax due day {due}: {economy.CITY_PROPERTY_TAX} copper",
                 f.body_sm, INK_FAINT, (x, y))
            y += 17
            if self.guild.property_city_missed_payments:
                left = (economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT
                        - self.guild.property_city_missed_payments)
                text(screen, f"{self.guild.property_city_missed_payments} cycle(s) missed -- "
                     f"{max(0, left)} more before the Bankers act", f.body_sm, WARN, (x, y))
                y += 17
        y += 4

        y = section(screen, f"STASHED  ({len(self.guild.property_city_items)})", x, y, w, f)
        if not self.guild.property_city_items:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (x, y + 2))
        for idx, item in enumerate(self.guild.property_city_items):
            r = pygame.Rect(x, y, w, 28)
            if r.bottom > rect.bottom - SP3:
                text(screen, f"+{len(self.guild.property_city_items) - idx} more", f.label,
                     INK_FAINT, (x, y + 4))
                break
            sel = self.sel == ("house", idx)
            ihov = not self.sel and r.collidepoint(self.mouse)
            panel(screen, r, fill=ACCENT if sel else SURFACE_3 if ihov else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
            text(screen, ellipsize(item, f.body, w - 70), f.body,
                 ACCENT_INK if sel else INK, (r.x + SP2, r.y + 6))
            text(screen, kg(data.item_weight(item)), f.mono_sm,
                 ACCENT_INK if sel else INK_DIM, (r.right - SP2, r.y + 7), right=True)
            self.house_rows.append((r, idx))
            y += 28 + SP1

    def _draw_debt(self, screen, x, y, w):
        f = self.fonts
        text(screen, f"owed to the Bankers: {self.guild.bankers_debt} copper -- their "
             "other services are shut until it's paid", f.body_sm, DANGER, (x, y))
        y += 20
        r = pygame.Rect(x, y, w, 34)
        can = self.purse > 0
        self.add_button(screen, r, "pay_debt", "PAY TOWARD THE DEBT", enabled=can, primary=can)
        return r.bottom + SP2

    def _draw_buy_offer(self, screen, x, y, w):
        f = self.fonts
        if self.guild.property_city_squatting:
            for ln in ("The guild squats a house it no longer owns.",
                       "The guard can still come to clear it out."):
                text(screen, ln, f.body_sm, DANGER, (x, y))
                y += 17
            return y
        for ln in (f"The Bankers sell a house inside the walls for "
                   f"{economy.CITY_PROPERTY_PRICE} copper,",
                   f"taxed {economy.CITY_PROPERTY_TAX} copper every "
                   f"{economy.CITY_PROPERTY_TAX_PERIOD_DAYS} days,",
                   f"{economy.CITY_PROPERTY_CAPACITY} kg of storage inside the walls."):
            text(screen, ln, f.body_sm, INK_DIM, (x, y))
            y += 17
        if not self._rep_ok:
            text(screen, f"needs {economy.CITY_PROPERTY_REP_GATE} reputation with the "
                 f"Bankers (have {self.guild.reputation.get('bankers', 0)})",
                 f.body_sm, WARN, (x, y))
            y += 17
        y += SP2
        r = pygame.Rect(x, y, w, 38)
        can = self._rep_ok and not self.guild.bankers_services_blocked and self.purse >= economy.CITY_PROPERTY_PRICE
        self.add_button(screen, r, "buy", f"BUY THE HOUSE -- {economy.CITY_PROPERTY_PRICE} COPPER",
                        enabled=can, primary=can)
        return r.bottom + SP2

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
        name = self._name_of(self.sel)
        incoming = bool(name) and not (self.sel[0] is m)
        take_ok = incoming and self._fits(m, name)
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

        y = section(screen, f"PACK  ({len(m._base_inventory)})", rect.x + pad, y,
                    rect.w - 2 * pad, f)
        if not m._base_inventory:
            text(screen, "(empty)", f.body_sm, INK_FAINT, (rect.x + pad, y + 2))
        shown = m._base_inventory[:PACK_ROWS_SHOWN]
        for idx, item in enumerate(shown):
            r = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, 24)
            sel = self.sel == (m, idx)
            ihov = not self.sel and r.collidepoint(self.mouse)
            panel(screen, r, fill=ACCENT if sel else SURFACE_3 if ihov else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=1, radius=4)
            text(screen, ellipsize(item, f.body_sm, rect.w - 2 * pad - 60), f.body_sm,
                 ACCENT_INK if sel else INK, (r.x + SP2, r.y + 5))
            text(screen, kg(data.item_weight(item)), f.mono_sm,
                 ACCENT_INK if sel else INK_DIM, (r.right - SP2, r.y + 6), right=True)
            self.item_rows.append((r, m, idx))
            y += 24 + SP1
        extra = len(m._base_inventory) - len(shown)
        if extra > 0:
            text(screen, f"+{extra} more", f.label, INK_FAINT,
                 (rect.x + pad, y + 2))

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen):
        footer_bar(self, screen, primary=("done", "LEAVE THE PROPERTY"), notice=self.notice)


class RepossessionScreen(ModalScreen, Screen):
    """Forced open instead of `CityPropertyScreen` once
    `guild.property_city_repossession_due` -- the Bankers want their house
    back, or their tax paid; there is no third option here (unlike
    `justice_screen.GuardScreen`'s FIGHT, squatting is not a fight, it's a
    standing risk played out later, in `campaign.py`'s "eviction" pause).
    No `resume_to` -- there is no screen underneath to freeze, so the shared
    modal frame falls back to a flat backdrop (`draw_scene_behind`'s except
    branch)."""

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
              width=2 if hov else 1, radius=RADIUS)
        text(screen, label, f.body_bd, col, (r.x + SP3, r.y + 8))
        text(screen, sub, f.body_sm, INK_DIM, (r.x + SP3, r.y + 30))
        self.buttons.append((key, r))
        return r.bottom + SP2

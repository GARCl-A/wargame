"""The City property: bought from the Bankers, taxed on a cycle.

[[gartok-property-two-paths]]'s "City" path -- the counterpart to a Wilds
claim, subordinate to the Bankers rather than sovereign. `CityPropertyScreen`
is the day-to-day screen (buy it, stash gear in it, pay off any debt) --
the same shape as `bank_screen.BankScreen`'s strongbox (both are a
`stash_screen.StashScreen`), just with a recurring tax instead of a one-off
fee, and no equivalent of the strongbox's second "rent" step.
`RepossessionScreen` is the choice forced once too many tax cycles are missed
(`guild.house.repossession_due`): return the property (and owe the Bankers),
or keep it and become an illegal occupier -- same three-way modal shape
`justice_screen.GuardScreen` uses for the guard's catch, just two options
instead of three (there is no "fight" here, only later, if the guild squats
and the guard actually comes -- `campaign.py`'s "eviction" pause).
"""

import pygame

from . import economy
from .screen import Screen
from .stash_screen import StashScreen
from .ui.primitives import draw_button
from .ui.primitives import text as ui_text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class CityPropertyScreen(StashScreen):
    OWNER = "house"
    TITLE = "The City Property"
    SUBTITLE = "a house inside the walls, bought from the Bankers -- taxed on a cycle"
    LABEL = "the house"
    LEAVE_LABEL = "leave the property"
    CLOSED_NOTICE = "buy the house first."
    WHERE = "at the property"

    def __init__(self, fonts, guild, party, on_done, on_cook=None, on_garage=None):
        super().__init__(fonts, guild, party, on_done)
        self.on_cook = on_cook
        self.on_garage = on_garage

    def tutorial_key(self):
        return "property"

    def _stash(self):
        return self.guild.house.stash

    def _open(self):
        return self.guild.house.owned

    def _services(self):
        g = self.guild
        if g.house.owned:
            rows = []
            if not g.house.oven:
                rows.append(("oven", "BUY AN OVEN", f"{economy.OVEN_PRICE} c  ·  unlocks cooking at the house",
                             self.purse >= economy.OVEN_PRICE))
            elif self.on_cook:
                rows.append(("cook", "COOK", "turn Meat and Salt into Jerky, which keeps for 20 days", True))
            if self.on_garage:
                garage = g.house.garage
                sub = (f"{len(garage.wagons)} / {garage.tier} wagons  ·  {len(garage.herd)} / {garage.tier} animals"
                       if garage.open else f"{economy.GARAGE_PRICE} c  ·  keeps a wagon and an animal at the house")
                rows.append(("garage", "GARAGE", sub, True))
            return rows
        if g.house.squatting:
            return []
        rep_ok = g.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
        can_buy = rep_ok and not g.bankers_services_blocked and self.purse >= economy.CITY_PROPERTY_PRICE
        sub = (f"{economy.CITY_PROPERTY_PRICE} c  ·  needs {economy.CITY_PROPERTY_REP_GATE} "
              f"standing with the Bankers (have {g.reputation.get('bankers', 0)})")
        return [("buy", "BUY THE HOUSE", sub, can_buy)]

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
        elif key == "oven":
            if self.purse < economy.OVEN_PRICE:
                self.notice = f"an oven costs {economy.OVEN_PRICE} copper -- the party has {self.purse}."
                return
            self.purse -= economy.OVEN_PRICE
            self.guild.buy_oven()
            self.notice = "the oven is installed -- the house can cook now."
        elif key == "cook":
            self.on_cook()
        elif key == "garage":
            self.on_garage()
        elif key == "pay_debt":
            amount = min(self.purse, self.guild.bankers_debt)
            if amount <= 0:
                self.notice = "the party has no copper to pay with."
                return
            self.purse -= amount
            self.guild.pay_bankers_debt(amount)
            self.notice = (f"paid {amount} copper toward the debt." if self.guild.bankers_debt > 0
                           else "debt cleared -- the Bankers deal with the guild again.")

    def _draw_status(self, screen, F, x, y, w):
        g, house = self.guild, self.guild.house
        if g.bankers_debt > 0:
            for ln in (f"owed to the Bankers: {g.bankers_debt} copper",
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

        if house.squatting:
            ui_text(screen, F["body_sm"], "squatting -- no tax, but the guard raids this place",
                (x, y), T.BLOOD)
            y += 16 + T.S
        elif house.owned:
            ui_text(screen, F["body_sm"],
                f"next tax due day {house.tax_due_day}: {economy.CITY_PROPERTY_TAX} c",
                (x, y), T.TX_FAINT)
            y += 16
            if house.missed_payments:
                left = economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT - house.missed_payments
                ui_text(screen, F["body_sm"],
                    f"{house.missed_payments} cycle(s) missed -- "
                    f"{max(0, left)} more before the Bankers act", (x, y), T.BRASS)
                y += 16
            y += T.S
        return y


class RepossessionScreen(Screen):
    """Forced open instead of `CityPropertyScreen` once
    `guild.house.repossession_due` -- the Bankers want their house
    back, or their tax paid; there is no third option here (unlike
    `justice_screen.GuardScreen`'s FIGHT, squatting is not a fight, it's a
    standing risk played out later, in `campaign.py`'s "eviction" pause).
    Modernized to the `gartok/ui/` design system using `modal_card`."""

    native = True

    def __init__(self, fonts, guild, on_return, on_squat):
        super().__init__()
        self.fonts = fonts
        self._F = fonts if (isinstance(fonts, dict) and "body" in fonts) else ui_fonts()
        self.guild = guild
        self.on_return = on_return
        self.on_squat = on_squat
        self.buttons = []
        self._hot = False

    def tutorial_key(self):
        return None

    def on_button(self, key):
        if key == "return":
            self.on_return()
        elif key == "squat":
            self.on_squat()

    def _click(self, pos):
        for key, rect in self.buttons:
            if rect.collidepoint(pos):
                self.on_button(key)
                return

    def card_rect(self, size):
        W, H = size
        w = min(580, W - 48)
        box_h = 280
        r = pygame.Rect(0, 0, w, box_h)
        r.center = (W // 2, H // 2)
        return r

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)

    def draw(self, screen):
        F = self._F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.buttons.clear()
        self._hot = False

        missed = self.guild.house.missed_payments
        owed = missed * economy.CITY_PROPERTY_TAX
        warn_msg = (f"{missed} tax cycles missed -- {owed} copper behind. "
                    "The Bankers want the house back, or the debt paid.")

        box_w = min(580, W - 48)
        inner_w = box_w - 48
        from .ui.primitives import caps as p_caps
        from .ui.primitives import hline, modal_card, wrap
        from .ui.primitives import text as p_text
        lines = wrap(F["body"], warn_msg, inner_w)
        box_h = 24 + 18 + 28 + 14 + len(lines) * 24 + 18 + 58 + 12 + 58 + 20

        card = modal_card(screen, (box_w, box_h), veil=True)
        pygame.draw.rect(screen, T.BLOOD, card, 2, border_radius=4)

        cx = card.x + 24
        cy = card.y + 20
        p_caps(screen, F["microb"], "TAX DEFAULT NOTICE", (cx, cy), T.BLOOD)
        cy += 18
        p_text(screen, F["head"], "THE BANKERS — REPOSSESSION DUE", (cx, cy), T.TX)
        cy += 30
        hline(screen, card.x + 20, card.right - 20, cy)
        cy += 14

        for ln in lines:
            p_text(screen, F["body"], ln, (cx, cy), T.BLOOD)
            cy += 24
        cy += 14

        # Option 1: Return property
        r1 = pygame.Rect(cx, cy, inner_w, 58)
        hov1 = r1.collidepoint(self.mouse)
        if hov1: self._hot = True
        pygame.draw.rect(screen, T.STEEL if hov1 else T.TABLE, r1, border_radius=4)
        pygame.draw.rect(screen, T.BRASS if hov1 else T.STEEL_LINE, r1, 2 if hov1 else 1, border_radius=4)
        p_text(screen, F["bodyb"], "RETURN THE PROPERTY", (r1.x + 14, r1.y + 10), T.TX)
        p_text(screen, F["body_sm"], f"Hand it back. The guild owes {owed} copper -- Bankers shut until paid.", (r1.x + 14, r1.y + 32), T.TX_MUTED)
        self.buttons.append(("return", r1))

        # Option 2: Squat
        cy = r1.bottom + 12
        r2 = pygame.Rect(cx, cy, inner_w, 58)
        hov2 = r2.collidepoint(self.mouse)
        if hov2: self._hot = True
        pygame.draw.rect(screen, T.STEEL if hov2 else T.TABLE, r2, border_radius=4)
        pygame.draw.rect(screen, T.BLOOD if hov2 else T.STEEL_LINE, r2, 2 if hov2 else 1, border_radius=4)
        p_text(screen, F["bodyb"], "REFUSE -- SQUAT", (r2.x + 14, r2.y + 10), T.BLOOD)
        p_text(screen, F["body_sm"], "Keep the house without paying. The City Guard will come to clear it out.", (r2.x + 14, r2.y + 32), T.TX_MUTED)
        self.buttons.append(("squat", r2))

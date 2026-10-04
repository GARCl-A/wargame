"""The bank: the guild's strongbox, rented from the Bankers.

The guild owns nothing as a body except this -- a chest at the bank in the City,
rented from the Bankers for a flat fee (`economy.BANK_CHEST_PRICE`) and holding
`guild.bank.capacity` kg. This screen rents the chest and moves gear between it
and the visiting party's packs (the mechanics live in `stash_screen.StashScreen`)
-- and lets a member equip straight out of either side: the hand/armor slots are
drop zones here exactly like on the gear screen, not a separate trip. The Bankers
also sell the City house from here (`city_property_screen.py` is where it's used).
"""

import pygame

from . import economy
from .stash_screen import StashScreen
from .ui.tokens import T


class BankScreen(StashScreen):
    OWNER = "bank"
    TITLE = "The Bank"
    SUBTITLE = "the Bankers rent one strongbox  ·  a flat fee, no questions"
    LABEL = "the strongbox"
    LEAVE_LABEL = "leave the bank"
    CLOSED_NOTICE = "rent a strongbox first."
    WHERE = "in the chest"
    CAN_DISTRIBUTE = True

    def tutorial_key(self):
        return "bank"

    def tutorial_badge_rect(self, size):
        W, H = size
        return pygame.Rect(W - T.S * 3 - 28, T.S * 2, 28, 28)

    def tutorial_anchor(self, size):
        W, H = size
        return (W - T.S * 3 - 340, T.S * 9 + T.S, 340, "down")

    def _stash(self):
        return self.guild.bank

    def _open(self):
        return self.guild.bank.open

    def _services(self):
        g = self.guild
        services = []
        if not g.house.owned and not g.house.squatting and g.bankers_debt <= 0:
            rep_ok = g.reputation.get("bankers", 0) >= economy.CITY_PROPERTY_REP_GATE
            can_buy = rep_ok and not g.bankers_services_blocked and self.purse >= economy.CITY_PROPERTY_PRICE
            sub = (f"{economy.CITY_PROPERTY_PRICE} c  ·  needs {economy.CITY_PROPERTY_REP_GATE} "
                  "standing with the Bankers")
            services.append(("buy_property", "BUY THE HOUSE", sub, can_buy))
        if not g.bank.open:
            can_rent = self.purse >= economy.BANK_CHEST_PRICE
            services.append(("rent", "RENT A STRONGBOX",
                            f"{economy.BANK_CHEST_PRICE} c  ·  {economy.BANK_CHEST_CAPACITY} kg held in the City",
                            can_rent))
        return services

    def _run_service(self, key):
        if key == "rent":
            if self.purse < economy.BANK_CHEST_PRICE:
                self.notice = (f"the strongbox costs {economy.BANK_CHEST_PRICE} copper -- "
                               f"the party has {self.purse}.")
                return
            self.purse -= economy.BANK_CHEST_PRICE
            self.guild.rent_bank_chest()
            self.notice = (f"rented a strongbox -- {self.guild.bank.capacity} kg of "
                           "storage at the bank.")
        elif key == "buy_property":
            if self.purse < economy.CITY_PROPERTY_PRICE:
                self.notice = (f"the Bankers want {economy.CITY_PROPERTY_PRICE} copper for "
                               f"the house -- the party has {self.purse}.")
                return
            self.purse -= economy.CITY_PROPERTY_PRICE
            self.guild.buy_city_property()
            self.notice = "bought a house in the City -- the Bankers' tax starts now."

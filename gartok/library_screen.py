"""The Library shop: buy dictionaries."""

import random

from . import data
from .market_screen import MarketScreen


def library_stock_dictionaries(guild):
    """Dictionaries currently sold by the Library today.
    Locked until `library_initiate` deed is completed (rep >= 1)."""
    rep = guild.reputation.get("library", 0)
    if rep <= 0:
        return []
    count = rep
    rng = random.Random(guild.clock.day)
    langs = rng.sample(data.LANGUAGES, min(count, len(data.LANGUAGES)))
    return [f"Dictionary of {lang}" for lang in langs]


class LibraryScreen(MarketScreen):
    def __init__(self, fonts, guild, shoppers, node, on_done):
        # We need to set the categories first, or super().__init__ will call it
        self._guild_ref = guild
        self._custom_categories = self._build_categories()
        super().__init__(fonts, guild, shoppers, node, on_done)
        self.tab = "supplies"

    def _build_categories(self):
        dictionaries = library_stock_dictionaries(self._guild_ref)
        cats = [("SUPPLIES", "supplies", ["Paper", "Ink"])]
        if dictionaries:
            cats.append(("DICTIONARIES", "dictionaries", dictionaries))
        return cats

    def get_categories(self):
        return getattr(self, "_custom_categories", self._build_categories())

    def tutorial_key(self):
        return "library"

"""The Library shop: buy dictionaries."""

import random
from . import data
from .market_screen import MarketScreen


class LibraryScreen(MarketScreen):
    def __init__(self, fonts, guild, shoppers, node, on_done):
        # We need to set the categories first, or super().__init__ will call it
        self._guild_ref = guild
        self._custom_categories = self._build_categories()
        super().__init__(fonts, guild, shoppers, node, on_done)
        self.tab = "kit"

    def _build_categories(self):
        rep = self._guild_ref.reputation.get("library", 0)
        count = 1 + rep * 2
        
        rng = random.Random(self._guild_ref.clock.day)
        langs = rng.sample(data.LANGUAGES, min(count, len(data.LANGUAGES)))
        
        dictionaries = [f"Dictionary of {lang}" for lang in langs]
        return [("DICTIONARIES", "kit", dictionaries)]

    def get_categories(self):
        return getattr(self, "_custom_categories", self._build_categories())

"""The Library shop: buy dictionaries (the rules are `trade.LibraryCounter`'s)."""

from .market_screen import MarketScreen
from .trade import LibraryCounter


class LibraryScreen(LibraryCounter, MarketScreen):

    def __init__(self, fonts, guild, shoppers, node, on_done):
        super().__init__(fonts, guild, shoppers, node, on_done)
        self.tab = "supplies"

    def tutorial_key(self):
        return "library"

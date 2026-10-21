"""The Bank Hub: the strongbox and the Bankers' jobs behind one row of tabs."""

from . import world
from .bank_screen import BankScreen
from .hub_screen import TabbedHubScreen
from .trust_screen import TrustScreen
from .ui.tokens import fonts as ui_fonts


class BankHubScreen(TabbedHubScreen):
    def __init__(self, fonts, guild, group, on_done):
        self.guild, self.group = guild, group
        self.vault_screen = BankScreen(fonts, guild, list(group.members), on_done)
        self.jobs_screen = TrustScreen(ui_fonts(), guild, group, on_done)
        super().__init__(fonts, [("vault", "VAULT", self.vault_screen), ("jobs", "JOBS", self.jobs_screen)],
                         node=world.node("city"), on_done=on_done)

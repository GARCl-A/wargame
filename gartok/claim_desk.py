"""The Wilds Claim's work with no window: scouting, the Lumber hauled for the fences and the fences raised, the
garrison, and the hearth (campfire or oven). Gathering Lumber is the Gathering tab's (`gather.py`). The two fights (CLEAR,
SWEEP) are the front-end's to play (`guild_claim` says what they are). pygame's `WildsClaimScreen` and
`web/claim_tab.py` are the windows over `ClaimDesk`.
"""

from . import economy, orders, stints


class ClaimDesk:
    def __init__(self, guild, group):
        self.guild, self.group = guild, group
        self.notice = None

    def _carriers(self):
        return self.group.carriers

    def _party_lumber(self):
        return sum(m.count_of("Lumber") for m in self._carriers())

    def _deposit_lumber(self):
        total = 0
        for m in self._carriers():
            n = m.count_of("Lumber")
            if n:
                m.remove_named("Lumber", n)
                total += n
                m._derive_combat()
        if total:
            self.guild.wilds_claim_deposit_lumber(total)
            self.notice = f"deposited {total} Lumber toward the fences."
        else:
            self.notice = "nobody here is carrying Lumber."

    # the claim's work with hours to it: each returns its stint for the band, or None (the notice says why)
    def _scout(self):
        return stints.order("claim_scout", economy.WILDS_CLAIM_SCOUT_HOURS, self.group.members)

    def _build_fences(self):
        if self.guild.wilds_claim_fence_lumber < economy.WILDS_CLAIM_FENCE_LUMBER:
            return None
        return stints.order("claim_fences", economy.WILDS_CLAIM_FENCE_HOURS, self.group.members)

    def _light_campfire(self):
        if not self.guild.claim_fire_fuel(self._carriers()):
            self.notice = f"nobody has {economy.CAMPFIRE_FUEL} to burn."
            return None
        self._lightened()
        return stints.order("claim_fire", economy.CAMPFIRE_HOURS, self.group.members)

    def _build_oven(self):
        short = self.guild.claim_oven_short(self._carriers())
        if short:
            self.notice = short
            return None
        self.guild.claim_oven_bricks(self._carriers())
        self._lightened()
        return stints.order("claim_oven", economy.CLAIM_OVEN_HOURS, self.group.members)

    def _lightened(self):
        for m in self.group.members:
            m._derive_combat()

    def _start_garrison(self):
        self.group.order = orders.garrison("hold")
        self.guild.wilds_claim_start_sustaining()

    def _leave_garrison(self):
        if self.group.order is not None and self.group.order.kind == "garrison":
            self.group.order = orders.idle()
        self.notice = "the garrison stands down -- sustaining the claim starts over."

"""The Wilds claim campaign: scout, clear, fence, sweep, then hold a garrison.

Mixed into `guild.Guild`; see `economy.WILDS_CLAIM_*` and
`wilds_claim_screen.WildsClaimScreen`.
"""

from . import economy, world

# The Wilds claim's own stage machine (see economy.WILDS_CLAIM_*).
WILDS_CLAIM_STAGES = ("NONE", "SCOUTED", "CLEARED", "FENCED", "SWEPT", "SUSTAINING", "ESTABLISHED")


class WildsClaimMixin:
    # ------------------------------------------------------------------ #
    # the Wilds claim campaign (see the class docstring, economy.WILDS_CLAIM_*) #
    # ------------------------------------------------------------------ #
    def wilds_claim_scout(self):
        self.wilds_claim_stage = "SCOUTED"

    def wilds_claim_mark_cleared(self):
        self.wilds_claim_stage = "CLEARED"

    def wilds_claim_deposit_lumber(self, n):
        self.wilds_claim_fence_lumber += n

    def wilds_claim_build_fences(self):
        self.wilds_claim_fence_lumber -= economy.WILDS_CLAIM_FENCE_LUMBER
        self.wilds_claim_stage = "FENCED"

    def wilds_claim_mark_swept(self):
        self.wilds_claim_stage = "SWEPT"

    def wilds_claim_start_sustaining(self):
        self.wilds_claim_stage = "SUSTAINING"
        self.wilds_claim_sustain_days_left = economy.WILDS_CLAIM_SUSTAIN_DAYS

    def _wilds_claim_garrisoned(self):
        """True while some living group is actually parked, garrisoning, at
        the claim node right now."""
        return any(g.order is not None and g.order.kind == "garrison"
                   and g.node == world.WILDS_TERRITORY_NODE and not g.empty
                   for g in self.groups)

    def _wilds_claim_sustain_tick(self):
        """Once a day, while `SUSTAINING`: the countdown only advances for a
        day the claim was actually garrisoned the whole time through -- no
        partial credit, same "start the clock over" rule
        `campaign.resolve_wilds_raid` applies to a raid the garrison loses.
        Pulling the garrison out early (a fresh order, not a lost fight) has
        the same effect -- sustaining only counts while someone is there."""
        if self.wilds_claim_stage != "SUSTAINING":
            return []
        if not self._wilds_claim_garrisoned():
            if self.wilds_claim_sustain_days_left != economy.WILDS_CLAIM_SUSTAIN_DAYS:
                self.wilds_claim_sustain_days_left = economy.WILDS_CLAIM_SUSTAIN_DAYS
                return ["The Wilds claim sits unguarded -- sustaining it starts over."]
            return []
        self.wilds_claim_sustain_days_left -= 1
        if self.wilds_claim_sustain_days_left <= 0:
            self.wilds_claim_stage = "ESTABLISHED"
            self.wilds_claim_sustain_days_left = None
            self.wilds_claim_owner = "guild"   # Sistema 4: what a seizure/retake actually flips
            return ["The Wilds claim is ESTABLISHED -- the land is the guild's."]
        return []

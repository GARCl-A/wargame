"""The Wilds claim campaign: scout, clear, fence, sweep, then hold a garrison.

Mixed into `guild.Guild`; see `economy.WILDS_CLAIM_*` and
`wilds_claim_screen.WildsClaimScreen`.
"""

import random

from . import data, economy, wagon_watch, world

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

    @property
    def wilds_claim_can_cook(self):
        return self.wilds_claim_campfire and self.wilds_claim_owner != "seized"

    def wilds_claim_light_campfire(self, crew):
        """Build a fire at the claim: one unit of fuel from someone's pack, an hour
        of the clock, and a WIS check by the best of `crew`. The fuel is gone
        whether or not the fire catches. Returns `(lit, events, casualties)`."""
        fuel = next((u for u in crew if u.count_of(economy.CAMPFIRE_FUEL)), None)
        if fuel is None:
            return False, [f"nobody has {economy.CAMPFIRE_FUEL} to burn."], []
        fuel.remove_named(economy.CAMPFIRE_FUEL)
        events, casualties = self.pass_time(economy.CAMPFIRE_HOURS, busy=crew)
        best = max(crew, key=lambda u: u.mod_wisdom)
        if data.roll(1, 20) + best.mod_wisdom >= economy.CAMPFIRE_DC:
            self.wilds_claim_campfire = True
            return True, ["the fire catches -- the claim has a hearth now."] + events, casualties
        return False, ["the wood won't catch -- the fuel is wasted."] + events, casualties

    def claim_garrison(self):
        """The living group parked, garrisoning, at the claim node right now, or None."""
        return next((g for g in self.groups
                     if g.order is not None and g.order.kind == "garrison"
                     and g.node == world.WILDS_TERRITORY_NODE and not g.empty), None)

    @property
    def claim_garage_open(self):
        """Open the moment the garrison opens (the 10 days to hold), until it is seized."""
        return self.wilds_claim_stage in ("SUSTAINING", "ESTABLISHED") and self.wilds_claim_owner != "seized"

    def wilds_claim_seize(self):
        """The occupiers take the ground, and whatever was parked there."""
        self.wilds_claim_owner = "seized"
        self.claim_garage.clear()

    def _garaged_food(self):
        return self.house.garage.food_stores() + self.claim_garage.food_stores()

    def _claim_garage_feed(self):
        """The garrison's food, and the animals' own load, feed what is parked at the claim."""
        garrison = self.claim_garrison()
        if garrison is None:
            return self.claim_garage.feed()
        return self.claim_garage.feed(*garrison.food_stores(), *(u._base_inventory for u in garrison.members))

    def _claim_garage_tick(self):
        """Once a day, with nobody at the claim: one roll for what is parked there, the
        flightiest animal's chance, and a hit loses all of it silently. Left long
        enough, it always goes. A wagon with no animal has nothing to bolt."""
        garage = self.claim_garage
        if garage.empty or self.claim_garrison() is not None:
            return
        if random.random() < wagon_watch.flight_chance(garage):
            garage.clear()

    def _wilds_claim_sustain_tick(self):
        """Once a day, while `SUSTAINING`: the countdown only advances for a
        day the claim was actually garrisoned the whole time through -- no
        partial credit, same "start the clock over" rule
        `campaign.resolve_wilds_raid` applies to a raid the garrison loses.
        Pulling the garrison out early (a fresh order, not a lost fight) has
        the same effect -- sustaining only counts while someone is there."""
        if self.wilds_claim_stage != "SUSTAINING":
            return []
        if self.claim_garrison() is None:
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

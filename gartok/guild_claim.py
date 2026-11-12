"""The Wilds claim campaign: scout, clear, fence, sweep, then hold a garrison.

Mixed into `guild.Guild`; see `economy.WILDS_CLAIM_*` and
`wilds_claim_screen.WildsClaimScreen`.
"""

import random

from . import data, economy, i18n, orders, recorder, wagon_watch, world

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
        return (self.wilds_claim_campfire or self.claim_oven) and self.wilds_claim_owner != "seized"

    def claim_build_oven(self, crew):
        """Build the oven: Stone Brick pooled from `crew`'s packs and a stretch of the clock.
        Unlike the campfire it never goes out, and it stays standing if the claim is seized.
        The headless shortcut of a `claim_oven` stint. Returns `(built, events, casualties)`."""
        short = self.claim_oven_short(crew)
        if short:
            return False, [short], []
        self.claim_oven_bricks(crew)
        events, casualties = self.tick(economy.CLAIM_OVEN_HOURS, busy=crew)
        return True, self.claim_oven_built() + events, casualties

    def claim_oven_short(self, crew):
        """Why `crew` cannot build the claim's oven now, or None."""
        if self.claim_oven:
            return i18n.t("guild_claim.claim_already_has_oven")
        have = sum(u.count_of(economy.CLAIM_OVEN_BRICK) for u in crew)
        if have < economy.CLAIM_OVEN_BRICKS:
            return i18n.t("guild_claim.oven_needs_group_carries", claim_oven_bricks=economy.CLAIM_OVEN_BRICKS, claim_oven_brick=economy.CLAIM_OVEN_BRICK, have=have)
        return None

    def claim_oven_bricks(self, crew):
        """The oven's Stone Brick, out of `crew`'s packs as the work starts."""
        left = economy.CLAIM_OVEN_BRICKS
        for u in crew:
            left -= u.remove_named(economy.CLAIM_OVEN_BRICK, left)

    def claim_oven_built(self):
        self.claim_oven = True
        recorder.emit("asset", what="claim_oven")
        return [i18n.t("guild_claim.oven_is_built_claim_can")]

    def wilds_claim_light_campfire(self, crew):
        """Build a fire at the claim: one unit of fuel from someone's pack, an hour
        of the clock, and a WIS check by the best of `crew`. The fuel is gone
        whether or not the fire catches. The headless shortcut of a `claim_fire` stint.
        Returns `(lit, events, casualties)`."""
        if not self.claim_fire_fuel(crew):
            return False, [i18n.t("guild_claim.nobody_has_to_burn", campfire_fuel=economy.CAMPFIRE_FUEL)], []
        events, casualties = self.tick(economy.CAMPFIRE_HOURS, busy=crew)
        lit, lines = self.claim_fire_catch(crew)
        return lit, lines + events, casualties

    def claim_fire_fuel(self, crew):
        """The fuel out of someone's pack as the work starts; False when nobody has any."""
        fuel = next((u for u in crew if u.count_of(economy.CAMPFIRE_FUEL) >= economy.CAMPFIRE_FUEL_UNITS), None)
        if fuel is None:
            return False
        fuel.remove_named(economy.CAMPFIRE_FUEL, economy.CAMPFIRE_FUEL_UNITS)
        return True

    def claim_fire_catch(self, crew):
        """The hour is up: a WIS check by the best of `crew` says whether the fire caught.
        -> `(lit, lines)`."""
        best = max(crew, key=lambda u: u.mod_wisdom)
        if data.roll(1, 20) + best.mod_wisdom >= economy.CAMPFIRE_DC:
            self.wilds_claim_campfire = True
            return True, [i18n.t("guild_claim.fire_catches_claim_has_hearth")]
        return False, [i18n.t("guild_claim.wood_won_t_catch_fuel")]

    def claim_garrison(self):
        """The living group parked, garrisoning, at the claim node right now, or None."""
        return next((g for g in self.groups
                     if orders.holds_post(g.order)
                     and g.node == world.WILDS_TERRITORY_NODE and not g.empty), None)

    @property
    def claim_held(self):
        """The garrison has opened (the 10 days to hold) and the claim is not seized: its garage and its
        gathering are open."""
        return self.wilds_claim_stage in ("SUSTAINING", "ESTABLISHED") and self.wilds_claim_owner != "seized"

    claim_garage_open = claim_held

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

    def _campfire_tick(self):
        """The fire burns for free while a garrison stands at the claim and dies the day nobody does."""
        if self.wilds_claim_campfire and self.claim_garrison() is None:
            self.wilds_claim_campfire = False

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
        `forced.resolve_wilds_raid` applies to a raid the garrison loses.
        Pulling the garrison out early (a fresh order, not a lost fight) has
        the same effect -- sustaining only counts while someone is there."""
        if self.wilds_claim_stage != "SUSTAINING":
            return []
        if self.claim_garrison() is None:
            if self.wilds_claim_sustain_days_left != economy.WILDS_CLAIM_SUSTAIN_DAYS:
                self.wilds_claim_sustain_days_left = economy.WILDS_CLAIM_SUSTAIN_DAYS
                return [i18n.t("guild_claim.wilds_claim_sits_unguarded_sustaining")]
            return []
        self.wilds_claim_sustain_days_left -= 1
        if self.wilds_claim_sustain_days_left <= 0:
            self.wilds_claim_stage = "ESTABLISHED"
            self.wilds_claim_sustain_days_left = None
            self.wilds_claim_owner = "guild"   # Sistema 4: what a seizure/retake actually flips
            return [i18n.t("guild_claim.wilds_claim_is_established_land")]
        return []

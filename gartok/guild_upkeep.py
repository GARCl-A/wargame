"""Time and daily upkeep: the clock, meals, rotting food, resting and the
once-a-day sweep over everything the guild owes.

Mixed into `guild.Guild`. `pass_time` is the only path that moves the clock
by hours; battle time (`clock.advance_rounds`) is seconds and skips upkeep.
"""

from . import cohesion, data, economy, items, justice, missions, orders, recorder, world

HOURS_PER_HEAL = 8


def rest_heal(unit):
    """HP one full stretch of rest (`HOURS_PER_HEAL` hours) gives back."""
    return max(1, unit.racial_level * unit.mod_constitution)


class UpkeepMixin:
    @property
    def hungry(self):
        return [u for u in self.roster if u.hunger_level > 0]

    @property
    def rations(self):
        """Meals in the packs across the whole roster, and on the wagons and animals."""
        return sum(u.rations for u in self.roster) + sum(g.carried_rations for g in self.groups)

    # ------------------------------------------------------------------ #
    # time + daily upkeep                                                #
    # ------------------------------------------------------------------ #
    def pass_time(self, hours, busy=()):
        """Advance the campaign clock and run daily upkeep for every day it
        crosses. Returns a list of events (missed meals, deaths) for the caller
        to show. This is the only path that moves the clock by hours -- battle
        time (`clock.advance_rounds`) is seconds and skips upkeep.

        `busy` are units doing something that spends the hours without a group
        order carrying it (a hunt, a crafting shift, scouting the claim): they
        do not rest meanwhile, same as a group on an order.

        The `(hours, busy=()) -> (events, casualties)` shape is a contract: the
        app's `_tick_outside_map` stands in for this call on screens that spend
        an hour (`repair_wagon`), and a test pins the two together."""
        start_day = self.clock.day
        self.clock.advance_hours(hours)
        events = []
        all_casualties = []
        for u in self.roster:
            events += u.tick_poison(hours)
        for _ in range(self.clock.day - start_day):
            e, c = self._daily_upkeep()
            events += e
            all_casualties += c
        
        # Passive healing: every 8h of continuous rest (not busy) heals the unit.
        # Steady Pace lets a group that is working where it stands rest on the job.
        for g in self.groups:
            working = g.busy and g.order.kind in orders.WORK_KINDS
            resting = g.busy and g.order.kind == "rest"
            for u in g.members:
                on_the_job = working or u in busy
                if ((g.busy and not resting) or u in busy) and not (on_the_job and u.talent_bonus("work_rest")):
                    u.consecutive_rest_hours = 0
                    continue
                if not (u.hp < u.hp_max or getattr(u, "sick", False)):
                    continue
                u.consecutive_rest_hours += hours
                while u.consecutive_rest_hours >= HOURS_PER_HEAL:
                    u.consecutive_rest_hours -= HOURS_PER_HEAL
                    if getattr(u, "sick", False):
                        if getattr(u, "treated", False):
                            cured = True
                            events.append(f"{u.name} rests and recovers from their sickness (treated).")
                        else:
                            cured = data.d20() <= 5
                            if cured:
                                events.append(f"{u.name} rests and recovers from their sickness naturally.")

                        if cured:
                            u.sick = False
                            u.treated = False
                            u._derive_combat()
                        else:
                            u.treated = False

                    if u.hp < u.hp_max and u.unfed_days == 0:
                        heal = rest_heal(u)
                        u.hp = min(u.hp_max, u.hp + heal)
                        events.append(f"{u.name} rests and recovers {heal} HP.")

                    if u.hp == u.hp_max and not getattr(u, "sick", False):
                        u.consecutive_rest_hours = 0
                        break

        recorder.day_tick(self)
        return events, all_casualties

    def _shared_larder(self, eater):
        """The packs `eater` may draw a ration from -- every group-mate
        (physically together, so the only ones who could actually hand over
        food) whose `share_food` is on. Own pack is handled first by the unit
        itself. What the group itself carries (wagon, animals) is always open."""
        group = self.group_of(eater)
        mates = group.members if group is not None else self.roster
        larder = [u._base_inventory for u in mates if u is not eater and u.share_food]
        if group is not None:
            larder += group.food_stores()
            if group is self.claim_garrison():
                larder += self.claim_garage.food_stores()
        return larder

    def _rot_food(self, inventory):
        """Age every food entry a day in place. `inventory` is a Unit's pack
        or a `Stash`'s items (a stack ages as one unit)."""
        rotten = 0
        new_inv = []
        for it in inventory:
            if it.defn.food and it.defn.lifespan is not None:
                it.days_old += 1
                if it.is_rotten():
                    rotten += it.qty
                    new_inv.append(items.create_instance("Rotten Food", qty=it.qty))
                else:
                    new_inv.append(it)
            else:
                new_inv.append(it)
        inventory[:] = new_inv
        return rotten


    def _daily_upkeep(self):
        events, casualties, ate = [], [], []
        
        # 1) rot food in everyone's inventory, the bank chest and the house
        total_rotten = 0
        for u in self.roster:
            total_rotten += self._rot_food(u._base_inventory)
        total_rotten += self._rot_food(self.bank.items)
        total_rotten += self._rot_food(self.house.stash.items)
        for pack in [p for g in self.groups for p in g.food_stores()] + self._garaged_food():
            total_rotten += self._rot_food(pack)
        if total_rotten:
            events.append(f"{total_rotten} portions of food rotted away.")

        for u in self.roster:
            u.medicine_attempted_today = False
            if u.has_talent("fruitful"):
                u.give_to_pack("Fruit")
                events.append(f"{u.name} blooms at dawn and yields a fresh Fruit.")
            if u.ability.id == "innocent_face" and u.crime > 0 and self.clock.day > 0 and self.clock.day % 7 == 0:
                u.crime -= 1
                events.append(f"{u.name}'s criminal record fades by 1 (Innocent Face).")
        # Units studying at the tavern pay for a room that includes a meal.
        # Check their funds directly since the rent isn't deducted until _garrison_upkeep.
        studying_fed = {
            u for g in self.groups
            if g.order and g.order.kind == "garrison" and g.order.job == "study"
            and world.node(g.node).garrison_job == "study"
            for u in g.members
            if u.study_target and u.money >= economy.TAVERN_STUDY_COST_PER_DAY
        }

        # Everyone eats from their own pack first (a full pass), so a hungry mate
        # drawing on the shared larder next can't take a ration its owner still
        # needs. Only then does the still-unfed hit the larder / the hunger step.
        for u, outcome in self._meal_pass(self.roster, self._shared_larder, studying_fed).items():
            if outcome == "dead":
                casualties.append(u)
                recorder.death(u, "starvation", unfed_days=u.unfed_days)
                events.append(f"{u.name} starved to death.")
            elif outcome == "hungry":
                events.append(f"{u.name} did not eat today: {u.hunger_label}.")
            elif outcome == "ate" and u.ability.id != "autotroph":
                ate.append(u)
        if ate:
            who = "1 member ate" if len(ate) == 1 else f"{len(ate)} members ate"
            events.append(f"{who} ({self.rations} rations left).")
        if casualties:
            self.remove_members(casualties)
        for g in self.groups:
            events += g.feed_animals()
        events += self.house.garage.feed(self.house.stash.items)
        events += self._claim_garage_feed()
        for m in missions.expire_overdue(self):
            events.append(f"{missions.template_of(m).name}: the deadline passed.")
        for u in justice.release_due(self):
            events.append(f"{u.name} finishes their time and is released in the City.")
        events += self._city_property_upkeep()
        events += self._garrison_upkeep()
        for n in world.NODES:
            if n.is_market:
                self.market_cash[n.id] = economy.regen_market_cash(self.market_cash_at(n.id))
        events += self._wilds_claim_sustain_tick()
        self._claim_garage_tick()
        self._campfire_tick()
        events += cohesion.daily(self)
        return events, casualties

    @staticmethod
    def _meal_pass(units, larder_of, free=()):
        """One day's meal for `units`: everyone eats from their own pack first (a
        full pass), so a hungry mate drawing on the larder next can't take a
        ration its owner still needs; only then does the still-unfed hit
        `larder_of(unit)` / the hunger step. `free` are fed without a ration.
        Returns `{unit: "ate" | "hungry" | "dead"}`. Touches only the units and
        packs it is handed, so `rest.py` runs it on copies to plan a rest."""
        ate_own = {u for u in units
                   if u not in free and u.ability.id != "autotroph" and u._take_ration()}
        outcomes = {}
        for u in units:
            if u in free or u in ate_own:
                u.unfed_days, outcomes[u] = 0, "ate"
            else:
                outcomes[u] = u.consume_daily_food(larder_of(u))
            u._derive_combat()                 # refresh mods / hp_max for the new hunger
        return outcomes

    @staticmethod
    def _eat_now(units, larder_of):
        """The hungry among `units` eat right now (own pack first); returns who."""
        fed = [u for u in units if u.eat_now()]
        for u in units:
            if u.hunger_level and u not in fed and u.eat_now(larder_of(u)):
                fed.append(u)
        for u in fed:
            u._derive_combat()
        return fed

    def eat_now_pass(self, members=None):
        """Anyone still hungry eats right now -- own pack, then the group
        larder -- without waiting for the next daily meal. No clock advance
        (the caller runs `pass_time` itself, or is mid-tick already).
        `members` narrows it to one group (a rest order's); the default is
        everyone."""
        fed = self._eat_now(self.roster if members is None else list(members), self._shared_larder)
        if not fed:
            return []
        names = ", ".join(u.name for u in fed)
        return [f"Stopped to eat: {names} ({self.rations} rations left)."]

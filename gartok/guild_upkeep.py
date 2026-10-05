"""Time and daily upkeep: the clock, meals, rotting food, resting and the
once-a-day sweep over everything the guild owes.

Mixed into `guild.Guild`. `pass_time` is the only path that moves the clock
by hours; battle time (`clock.advance_rounds`) is seconds and skips upkeep.
"""

from . import cohesion, data, economy, items, justice, missions, world


class UpkeepMixin:
    @property
    def hungry(self):
        return [u for u in self.roster if u.hunger_level > 0]

    @property
    def rations(self):
        """Meals in the packs across the whole roster."""
        return sum(u.rations for u in self.roster)

    # ------------------------------------------------------------------ #
    # time + daily upkeep                                                #
    # ------------------------------------------------------------------ #
    def pass_time(self, hours):
        """Advance the campaign clock and run daily upkeep for every day it
        crosses. Returns a list of events (missed meals, deaths) for the caller
        to show. This is the only path that moves the clock by hours -- battle
        time (`clock.advance_rounds`) is seconds and skips upkeep."""
        start_day = self.clock.day
        self.clock.advance_hours(hours)
        events = []
        all_casualties = []
        for _ in range(self.clock.day - start_day):
            e, c = self._daily_upkeep()
            events += e
            all_casualties += c
        
        # Passive healing: every 8h of continuous rest (not busy) heals the unit
        for g in self.groups:
            if not g.busy:
                for u in g.members:
                    if u.hp < u.hp_max or getattr(u, "sick", False):
                        u.consecutive_rest_hours += hours
                        while u.consecutive_rest_hours >= 8:
                            u.consecutive_rest_hours -= 8
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
                                heal = max(1, u.racial_level * u.mod_constitution)
                                u.hp = min(u.hp_max, u.hp + heal)
                                events.append(f"{u.name} rests and recovers {heal} HP.")
                                
                            if u.hp == u.hp_max and not getattr(u, "sick", False):
                                u.consecutive_rest_hours = 0
                                break
            else:
                for u in g.members:
                    u.consecutive_rest_hours = 0

        return events, all_casualties

    def _shared_larder(self, eater):
        """The packs `eater` may draw a ration from -- every group-mate
        (physically together, so the only ones who could actually hand over
        food) whose `share_food` is on. Own pack is handled first by the unit
        itself."""
        group = self.group_of(eater)
        mates = group.members if group is not None else self.roster
        return [u._base_inventory for u in mates
                if u is not eater and u.share_food]

    @staticmethod
    def _age_food_name(name):
        """One day of aging for a single food name -- `(new_name, rotted)`.
        Anything without a `lifespan` entry passes through unchanged."""
        base = name.split(" (")[0]
        it = items.get(base)
        if it is None or it.lifespan is None:
            return name, False
        age = int(name.split(" (")[1].replace("d)", "")) + 1 if " (" in name else 1
        if age >= it.lifespan:
            return "Rotten Food", True
        return f"{base} ({age}d)", False

    def _rot_food(self, inventory):
        """Age every food entry a day in place. `inventory` is either a
        Unit's pack (`list[(name,qty)]` -- a stack ages as one unit, since
        aging changes the name and same-name is exactly what stacks
        together) or a `Stash`'s items; rotted portions
        merge into any Rotten Food already held instead of duplicating it."""
        rotten = 0
        new_inv = []
        for it in inventory:
            if isinstance(it, items.ItemInstance):
                if it.defn.food and it.defn.lifespan is not None:
                    it.days_old += 1
                    if it.is_rotten():
                        rotten += it.qty
                        rotten_inst = items.create_instance("Rotten Food", qty=it.qty)
                        new_inv.append(rotten_inst)
                    else:
                        new_inv.append(it)
                else:
                    new_inv.append(it)
            elif isinstance(it, tuple):
                name, qty = it
                new_name, rotted = self._age_food_name(name)
                if rotted:
                    rotten += qty
                existing = next((i for i, (n, _) in enumerate(new_inv) if n == new_name), None)
                if existing is not None:
                    new_inv[existing] = (new_name, new_inv[existing][1] + qty)
                else:
                    new_inv.append((new_name, qty))
            else:
                new_name, rotted = self._age_food_name(it)
                rotten += rotted
                new_inv.append(new_name)
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
            if u.study_target and u.gold >= economy.TAVERN_STUDY_COST_PER_DAY
        }

        # Everyone eats from their own pack first (a full pass), so a hungry mate
        # drawing on the shared larder next can't take a ration its owner still
        # needs. Only then does the still-unfed hit the larder / the hunger step.
        ate_own = {u for u in self.roster
                   if u not in studying_fed and u.ability.id != "autotroph" and u._take_ration()}
        for u in self.roster:
            if u in studying_fed or u in ate_own:
                u.unfed_days, outcome = 0, "ate"
            else:
                outcome = u.consume_daily_food(self._shared_larder(u))
            if outcome == "dead":
                casualties.append(u)
                events.append(f"{u.name} starved to death.")
            elif outcome == "hungry":
                events.append(f"{u.name} did not eat today: {u.hunger_label}.")
            elif outcome == "ate" and u.ability.id != "autotroph":
                ate.append(u)
            u._derive_combat()                 # refresh mods / hp_max for the new hunger
        if ate:
            who = "1 member ate" if len(ate) == 1 else f"{len(ate)} members ate"
            events.append(f"{who} ({self.rations} rations left).")
        if casualties:
            self.remove_members(casualties)
        for m in missions.expire_overdue(self):
            events.append(f"{missions.template_of(m).name}: the deadline passed.")
        for u in justice.release_due(self):
            events.append(f"{u.name} finishes their time and is released in the City.")
        events += self._city_property_upkeep()
        events += self._garrison_upkeep()
        events += self._wilds_claim_sustain_tick()
        events += cohesion.daily(self)
        return events, casualties

    def eat_now_pass(self):
        """Anyone still hungry eats right now -- own pack, then the group
        larder -- without waiting for the next daily meal. No clock advance
        (the caller runs `pass_time` itself, or is mid-tick already)."""
        fed = [u for u in self.roster if u.eat_now()]          # own packs first
        for u in self.roster:
            if u.hunger_level and u not in fed and u.eat_now(self._shared_larder(u)):
                fed.append(u)
        for u in fed:
            u._derive_combat()
        if not fed:
            return []
        names = ", ".join(u.name for u in fed)
        return [f"Stopped to eat: {names} ({self.rations} rations left)."]

    def do_maintenance(self, hours=1):
        """A camp stop: the guild takes `hours` to see to itself. Advances the
        clock (so a stop that crosses midnight still runs the daily meal) and
        then lets anyone still hungry eat from their pack right now. Returns the
        events to show. Eating is the only chore today; rest / gear repair hang
        off here later."""
        events, casualties = self.pass_time(hours)
        events += self.eat_now_pass()
        if not events:
            events.append("A quiet stop. No one needed to eat.")
        return events, casualties

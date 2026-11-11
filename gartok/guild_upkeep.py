"""Time and daily upkeep: the clock, meals, rotting food, resting and the
once-a-day sweep over everything the guild owes.

Mixed into `guild.Guild`. `pass_time` is the only path that moves the clock
by hours; battle time (`clock.advance_rounds`) is seconds and skips upkeep.
"""

from . import (
    aftermath,
    captives,
    cohesion,
    cult_site,
    data,
    i18n,
    items,
    justice,
    magic,
    missions,
    orders,
    recorder,
    rite,
    vocations,
    wildfire,
    world,
)
from .clock import SECONDS_PER_DAY

HOURS_PER_HEAL = 8
HOURS_PER_NONLETHAL_CLEAR = 24
HARDENED_NONLETHAL_CLEAR = 16              # two heal stretches: the clock checks every HOURS_PER_HEAL


def rest_heal(unit, triage=False):
    """HP one full stretch of rest (`HOURS_PER_HEAL` hours) gives back; `triage` is a
    Triage talent anywhere in the unit's group."""
    return (max(1, unit.racial_level * unit.mod_constitution)
            + int(unit.talent_bonus("rest_heal_bonus")) + triage)


def nonlethal_clear_hours(unit):
    """Unbroken rest that wipes `unit`'s non-lethal damage."""
    return HARDENED_NONLETHAL_CLEAR if unit.has_talent("hardened") else HOURS_PER_NONLETHAL_CLEAR


class UpkeepMixin:
    @property
    def hungry(self):
        return [u for u in self.roster if u.hunger_level > 0]

    @property
    def rations(self):
        """Meals in the packs across the whole roster, and on the wagons and animals."""
        return sum(u.rations for u in self.roster) + sum(g.carried_rations for g in self.groups)

    @property
    def rotten_rations(self):
        return sum(u.rotten_rations for u in self.roster) + sum(g.carried_rotten for g in self.groups)

    def food_alert(self):
        """`(level, text, title)` for the map's food card, or None: "critical" with no food left,
        "warning" with about a day of it. Meals count rations across the whole guild. `title`
        is the card's few words, `text` the full line its tooltip shows."""
        mouths, rations = len(self.roster), self.rations
        if not mouths or rations > mouths:
            return None
        if rations > 0:
            return ("warning", (i18n.t("guild_upkeep.only_meal_left_for_member", meals=i18n.count("meal", rations), members=i18n.count("member", mouths))),
                    i18n.t("guild_upkeep.low_on_food"))
        rot = self.rotten_rations
        rot_note = (i18n.plural("guild_upkeep.only_portion_of_rotten_food", rot) if rot else "")
        hungry = self.hungry
        if not hungry:
            return ("critical", (i18n.t("guild_upkeep.no_food_left_whole_guild")
                                 + rot_note), i18n.t("guild_upkeep.no_food_left"))
        days = max(1, data.STARVATION_DEATH_DAYS - max(u.unfed_days for u in hungry))
        return ("critical", (i18n.t("guild_upkeep.starving_member_hungry_and_no", members=i18n.count("member", len(hungry)), days=i18n.count("day", days)) + rot_note),
                "STARVING")

    # ------------------------------------------------------------------ #
    # time + daily upkeep                                                #
    # ------------------------------------------------------------------ #
    def tick(self, hours, busy=()):
        """Hours spent with no map to run them (the sims, a test's shortcut): through
        `campaign.advance`, so every band's order keeps in step. The game never calls it: an hour a
        band spends there is an order (`stints.py`). -> `(events, casualties)`."""
        from . import campaign
        result = campaign.advance(self, dt=hours, busy=busy)
        return result.events, result.casualties

    def pass_time(self, hours, busy=()):
        """Advance the campaign clock and run daily upkeep for every day it
        crosses. Returns a list of events (missed meals, deaths) for the caller
        to show. This is the only path that moves the clock by hours -- battle
        time (`clock.advance_rounds`) is seconds and skips upkeep. It leaves the
        bands' orders alone, so only `campaign._advance` calls it (a test checks it).

        `busy` are units spending the hours without a group order carrying them
        (a headless shortcut's crew, `tick`): they do not rest meanwhile, same as
        a group on an order."""
        start_day = self.clock.day
        self.clock.advance_hours(hours)
        events = []
        all_casualties = []
        for u in self.roster:
            events += u.tick_poison(hours)
        self.log.record(events, self.clock.seconds, "day")
        for i in range(self.clock.day - start_day):
            # each crossed day's upkeep is written at its own midnight, not at the jump's end
            e, c = self._daily_upkeep((start_day + i) * SECONDS_PER_DAY)
            events += e
            all_casualties += c
        e, c = self.reap_collapsed()
        self.log.record(e, self.clock.seconds, "day")
        events += e
        all_casualties += c

        # Passive healing: every 8h of continuous rest (not busy) heals the unit.
        # Steady Pace lets a group that is working where it stands rest on the job.
        for g in self.groups:
            logged = len(events)
            resting = g.busy and orders.is_resting(g.order)
            working = g.busy and g.order.kind in orders.WORK_KINDS and not resting
            for u in g.members:
                on_the_job = working or u in busy
                waiting = g.busy and ((g.order.kind == "solo" and u.uid != g.order.who)
                                      or (g.order.kind == "hunting" and u.uid not in g.order.crew))
                if ((g.busy and not resting and not waiting) or u in busy) and not (on_the_job and u.talent_bonus("work_rest")):
                    u.consecutive_rest_hours = 0
                    u.unbroken_rest_hours = 0
                    continue
                if not (u.hp < u.hp_max or getattr(u, "sick", False)):
                    continue
                u.consecutive_rest_hours += hours
                u.unbroken_rest_hours = getattr(u, "unbroken_rest_hours", 0) + hours
                while u.consecutive_rest_hours >= HOURS_PER_HEAL:
                    u.consecutive_rest_hours -= HOURS_PER_HEAL
                    if getattr(u, "sick", False):
                        if getattr(u, "treated", False):
                            cured = True
                            events.append(i18n.t("guild_upkeep.rests_and_recovers_from_their", name=u.name))
                        else:
                            cured = data.d20() <= 5
                            if cured:
                                events.append(i18n.t("guild_upkeep.rests_and_recovers_from_their_2", name=u.name))

                        if cured:
                            u.sick = False
                            u.treated = False
                            u._apply_attributes()
                            u._derive_combat()
                        else:
                            u.treated = False

                    if u.hp < u.hp_max and u.unfed_days == 0:
                        grp = self.group_of(u)
                        heal = rest_heal(u, triage=bool(grp and grp.has_talent("triage")))
                        u.hp = min(u.hp_max, u.hp + heal)
                        events.append(i18n.t("guild_upkeep.rests_and_recovers_hp", name=u.name, heal=heal))

                    rested_ticks = u.unbroken_rest_hours - u.consecutive_rest_hours
                    if (rested_ticks >= nonlethal_clear_hours(u) - 1e-9
                            and getattr(u, "non_lethal_damage", 0) > 0 and u.unfed_days == 0):
                        cleared = u.non_lethal_damage
                        u.hp = min(u.hp_max, u.hp + cleared)
                        u.non_lethal_damage = 0
                        events.append(i18n.t("guild_upkeep.shakes_off_non_lethal_damage", name=u.name, cleared=cleared))

                    if u.hp == u.hp_max and not getattr(u, "sick", False):
                        u.consecutive_rest_hours = 0
                        u.unbroken_rest_hours = 0
                        break
            self.log.record(events[logged:], self.clock.seconds, "rest", g.display_name)

        recorder.day_tick(self)
        return events, all_casualties

    def reap_collapsed(self):
        """Whoever has a physical score (Str / Dex / Con) at zero or below dies where they stand: the
        world half of `Combatant.check_collapse`. Poison, sickness and hunger all get here the same way.
        -> `(events, dead)`, the dead already off the roster."""
        events, dead = [], []
        for u in self.roster:
            attribute = u.zeroed_attribute
            if attribute is None:
                continue
            g = self.group_of(u)
            place = world.node(g.node).name if g is not None and g.node else None
            u.memorial = aftermath.collapsed(u, attribute, day=self.clock.day, place=place)
            recorder.death(u, "collapse", attribute=attribute)
            events.append(i18n.t("guild_upkeep.died", name=u.name, cause=u.memorial.cause))
            dead.append(u)
        if dead:
            self.remove_members(dead)
        return events, dead

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

    def _rot_food(self, inventory, spoiled=None):
        """Age every perishable entry a day in place. `inventory` is a Unit's pack
        or a `Stash`'s items (a stack ages as one unit). Food past its days turns to
        Rotten Food; anything else perishable (a body) is gone, its name added to `spoiled`."""
        rotten = 0
        new_inv = []
        for it in inventory:
            if it.defn.lifespan is None:
                new_inv.append(it)
                continue
            it.days_old += 1
            if not it.is_rotten():
                new_inv.append(it)
            elif it.defn.food:
                rotten += it.qty
                new_inv.append(items.create_instance("Rotten Food", qty=it.qty))
            elif spoiled is not None:
                spoiled.append(it.name)
        inventory[:] = new_inv
        return rotten


    def _daily_upkeep(self, at=None):
        """One day's sweep. `at` is the clock second the day began, where its lines go in the log."""
        events, casualties, ate = [], [], []
        at = self.clock.seconds if at is None else at
        logged = 0

        def flush(kind):
            nonlocal logged
            self.log.record(events[logged:], at, kind)
            logged = len(events)

        # 1) rot food in everyone's inventory, the bank chest and the house
        total_rotten = 0
        spoiled = []
        if not vocations.food_pauses(self):
            for u in self.roster:
                total_rotten += self._rot_food(u._base_inventory, spoiled)
            total_rotten += self._rot_food(self.bank.items, spoiled)
            total_rotten += self._rot_food(self.house.stash.items, spoiled)
            for pack in [p for g in self.groups for p in g.food_stores()] + self._garaged_food():
                total_rotten += self._rot_food(pack, spoiled)
        if total_rotten:
            events.append(i18n.t("guild_upkeep.portions_of_food_rotted_away", total_rotten=total_rotten))
        events += [i18n.t("guild_upkeep.rotted_away", name=name) for name in spoiled]
        flush("food")
        events += captives.daily(self)
        flush("guild")

        for u in self.roster:
            u.medicine_attempted_today = False
            if u.has_talent("fruitful"):
                fruit, n = u.dawn_bloom()
                u.give_to_pack(fruit, n)
                events.append(i18n.t("guild_upkeep.blooms_at_dawn_and_yields", name=u.name, n=n, fruit=fruit))
            if u.ability.id == "innocent_face" and u.crime > 0 and self.clock.day > 0 and self.clock.day % 7 == 0:
                u.crime -= 1
                events.append(i18n.t("guild_upkeep.s_criminal_record_fades_by", name=u.name))
        flush("day")
        # Units studying at the tavern pay for a room that includes a meal.
        # The rent isn't deducted until _garrison_upkeep, so check the group's funds here.
        # A rite's boarder with an empty pack is fed (and charged) by `rite.board`.
        board_fed = {
            u for g in self.groups
            if g.order and g.order.kind == "garrison" and g.order.job == "study"
            and world.node(g.node).garrison_job == "study"
            for u in magic.rent_covered(g)
        } | rite.board(self)

        # Everyone eats fresh food from their own pack first (a full pass), so a hungry
        # mate drawing on the shared larder next can't take a ration its owner still
        # needs. Only then does the still-unfed hit the larder / the hunger step.
        was_sick = {u for u in self.roster if u.sick}
        gut_rot = {u: u.poisons.get("gut_rot", {}).get("level", 0) for u in self.roster}
        for u, outcome in self._meal_pass(self.roster, self._shared_larder, board_fed).items():
            if outcome == "dead":
                casualties.append(u)
                recorder.death(u, "starvation", unfed_days=u.unfed_days)
                g = self.group_of(u)
                u.memorial = aftermath.starved(u, day=self.clock.day,
                                               place=world.node(g.node).name if g is not None and g.node else None)
                events.append(i18n.t("guild_upkeep.starved_to_death", name=u.name))
            elif outcome == "hungry":
                events.append(i18n.t("guild_upkeep.did_not_eat_today", name=u.name, hunger_label=u.hunger_label))
            elif outcome == "ate" and u.ability.id != "autotroph":
                ate.append(u)
                if u.sick and u not in was_sick:
                    events.append(i18n.t("guild_upkeep.ate_rotten_food_and_fell", name=u.name))
                elif u.poisons.get("gut_rot", {}).get("level", 0) > gut_rot[u]:
                    events.append(i18n.t("guild_upkeep.ate_rotten_food_again_gut", name=u.name, poisons=u.poisons['gut_rot']['level']))
        if ate:
            who = i18n.plural("guild_upkeep.members_ate", len(ate))
            events.append(i18n.t("guild_upkeep.rations_left", who=who, rations=self.rations))
        if casualties:
            self.remove_members(casualties)
        for g in self.groups:
            events += g.feed_animals()
        events += self.house.garage.feed(self.house.stash.items)
        events += self._claim_garage_feed()
        flush("food")
        events += wildfire.daily(self)
        for m in missions.expire_overdue(self):
            events.append(i18n.t("guild_upkeep.deadline_passed", name=missions.template_of(m).name))
        events += cult_site.daily(self)
        for u in justice.release_due(self):
            events.append(i18n.t("guild_upkeep.finishes_their_time_and_is", name=u.name))
        events += self._city_property_upkeep()
        flush("guild")
        events += self._garrison_upkeep()
        flush("work")
        for n in world.NODES:
            if n.has("shop"):
                self.shop(n.id).refill()
        events += self._wilds_claim_sustain_tick()
        self._claim_garage_tick()
        self._campfire_tick()
        events += cohesion.daily(self)
        flush("day")
        return events, casualties

    @staticmethod
    def _meal_pass(units, larder_of, free=()):
        """One day's meal for `units`: everyone eats fresh food from their own pack
        first (a full pass), so a hungry mate drawing on the larder next can't take a
        ration its owner still needs; only then does the still-unfed hit
        `larder_of(unit)` / the hunger step. `free` are fed without a ration.
        Returns `{unit: "ate" | "hungry" | "dead"}`. Touches only the units and
        packs it is handed, so `rest.py` runs it on copies to plan a rest."""
        ate_own = {u for u in units
                   if u not in free and u.ability.id != "autotroph" and u._take_ration(allow_rotten=False)}
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
        """The hungry among `units` eat right now (own fresh food first); returns who."""
        fed = [u for u in units if u.eat_now(allow_rotten=False)]
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
        members = self.roster if members is None else list(members)
        fed = self._eat_now(members, self._shared_larder)
        beasts = [a for g in self.groups if any(m in g.members for m in members)
                  for a in g.feed_hungry_animals()]
        if not fed and not beasts:
            return []
        names = ", ".join([u.name for u in fed] + [a.species for a in beasts])
        return [i18n.t("guild_upkeep.stopped_to_eat_rations_left", names=names, rations=self.rations)]

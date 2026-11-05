"""What the guild owns as a body: the bank chest, the City property, the
Bankers' debt and the garrison's stockpile.

Mixed into `guild.Guild`; the stores themselves live in `holdings.py`.
"""

from . import data, economy, i18n, magic, recorder, rite, world
from . import wagon as wagons
from .constants import fmt_money


class HoldingsMixin:
    def rent_bank_chest(self):
        """Take up the Bankers' offer: the guild's first strongbox. The caller
        collects the fee first -- this only flips the capacity on."""
        self.bank.capacity = economy.BANK_CHEST_CAPACITY
        recorder.emit("asset", what="bank_chest")

    @property
    def bankers_services_blocked(self):
        """Outstanding debt shuts the Bankers' doors -- no new strongbox, no
        buying the property (back) -- until it's paid off."""
        return self.bankers_debt > 0

    def buy_city_property(self):
        self.house.buy(self.clock.day)
        recorder.emit("asset", what="house")

    def buy_oven(self):
        """The caller collects `economy.OVEN_PRICE` first."""
        self.house.oven = True
        recorder.emit("asset", what="oven")

    def buy_garage_tier(self):
        """The caller collects `economy.GARAGE_PRICE` first."""
        self.house.garage.tier += 1
        recorder.emit("asset", what="garage")

    def park_wagon(self, group, wagon, garage=None):
        """Move one of `group`'s wagons into a garage (the house's unless given); False if
        there is no room."""
        garage = garage or self.house.garage
        if wagon not in group.wagons or garage.wagon_room <= 0:
            return False
        group.remove_wagon(wagon)
        garage.wagons.append(wagon)
        return True

    def repair_wagon(self, crew, wagon):
        """Mend `wagon` where the group stands: the Lumber out of someone's pack, an hour
        of the clock and an INT check by the best of `crew`. The Lumber and the hour are
        spent whether or not it holds. The headless shortcut of a `repair` stint.
        Returns `(ok, events, casualties)`; whoever starved meanwhile is in both."""
        short = self.repair_short(crew, wagon)
        if short:
            return False, [short], []
        self.repair_lumber(crew, wagon)
        events, casualties = self.tick(wagons.REPAIR_HOURS, busy=crew)
        events = [*events, *(i18n.t("guild_holdings.starved_to_death", name=u.name) for u in casualties)]
        ok, lines = self.repair_roll(crew, wagon)
        return ok, [*lines, *events], casualties

    def repair_short(self, crew, wagon):
        """Why `crew` cannot mend `wagon` now, or None."""
        name = wagon.kind.lower()
        if not wagon.needs_repair:
            return i18n.t("guild_holdings.needs_no_repair", name=name)
        cost = wagon.repair_cost
        if sum(u.count_of(wagons.REPAIR_ITEM) for u in crew) < cost:
            return i18n.t("guild_holdings.it_takes_to_mend", cost=cost, repair_item=i18n.name("item", wagons.REPAIR_ITEM), name=name)
        return None

    def repair_lumber(self, crew, wagon):
        """The repair's Lumber, out of `crew`'s packs as the work starts."""
        left = wagon.repair_cost
        for u in crew:
            left -= u.remove_named(wagons.REPAIR_ITEM, left)

    def repair_roll(self, crew, wagon):
        """The hour is up: an INT check by the best of `crew` says whether `wagon` holds.
        -> `(ok, lines)`."""
        name = wagon.kind.lower()
        smith = wagons.repairer(crew)
        total = data.d20() + smith.mod_intelligence
        if total < wagons.REPAIR_DC:
            return False, [i18n.t("guild_holdings.fails_to_mend_vs_dc", name=smith.name, item=name, total=total, repair_dc=wagons.REPAIR_DC, repair_item=i18n.name("item", wagons.REPAIR_ITEM))]
        mult = 2 if any(u.has_talent('wheelwright') for u in crew) else 1
        gained = wagon.repair(mult=mult)
        return True, [i18n.t("guild_holdings.mends_hp", name=smith.name, item=name, gained=gained, hp=wagon.hp, hp_max=wagon.hp_max)]

    def abandon_wagon(self, group, wagon):
        """Leave a wagon behind for good, cargo and all (the caller let the player unload
        it first). Its animals stay in the group."""
        if wagon not in group.wagons:
            return False
        group.remove_wagon(wagon)
        return True

    def park_animal(self, group, animal, garage=None):
        garage = garage or self.house.garage
        if animal not in group.herd or garage.animal_room <= 0:
            return False
        group.herd.remove(animal)
        animal.hitch = None
        garage.herd.append(animal)
        return True

    def take_wagon(self, group, wagon, garage=None):
        garage = garage or self.house.garage
        if wagon not in garage.wagons:
            return False
        garage.wagons.remove(wagon)
        group.add_wagon(wagon)
        group.hitch_idle()
        return True

    def take_animal(self, group, animal, garage=None):
        """False if the group cannot control another animal (`Group.can_take`)."""
        garage = garage or self.house.garage
        if animal not in garage.herd or not group.can_take(animal):
            return False
        garage.herd.remove(animal)
        group.herd.append(animal)
        group.hitch_idle()
        return True

    def repossess_city_property(self):
        """ACCEPT: hand the property back, bank the missed rent as debt owed
        to the Bankers -- their services stay shut until it's paid."""
        self.bankers_debt += self.house.repossess()
        self.bankers_debt_since = self.clock.day

    # ------------------------------------------------------------------ #
    # the garrison: a Group parked on a "garrison" order, working a job    #
    # ------------------------------------------------------------------ #
    def _garrison_upkeep(self):
        """Once a day: every group parked on a `"garrison"` order works its job (a study, a rite).
        A node whose `garrison_job` doesn't match the order's own `job` produces nothing; the group
        still sits there, fed by the normal per-group upkeep, just not working."""
        events = []
        for g in self.groups:
            if g.empty or g.order is None or g.order.kind != "garrison":
                continue
            node = world.node(g.node)
            if node.garrison_job != g.order.job:
                continue

            if g.order.job == rite.JOB:
                events += rite.daily(g)
                continue

            if g.order.job == "study":
                for u in g.members:
                    event = magic.progress_study(u, group=g)
                    if event:
                        events.append(event)
                if not any(u.study_target for u in g.members):
                    g.order = None
                    events.append(i18n.t("guild_holdings.studies_are_over_rooms_released", name=node.name))
                elif not magic.rent_covered(g):
                    g.order = None
                    events.append(i18n.t("guild_holdings.no_one_can_pay_for", name=node.name))
                continue
        return events

    def pay_bankers_debt(self, amount):
        """Apply `amount` (already collected by the caller) to `bankers_debt`,
        never past zero. Returns how much was actually owed (<= amount)."""
        paid = min(amount, self.bankers_debt)
        self.bankers_debt -= paid
        if self.bankers_debt == 0:
            self.bankers_debt_since = None
        return paid

    def _charge_roster(self, amount):
        """Take `amount` copper off the whole roster -- `economy.charge_evenly`
        over everyone rather than one screen's visiting guests."""
        economy.charge_evenly(self.roster, amount)

    def _city_property_upkeep(self):
        """Run once a day (from `_daily_upkeep`): collect the property tax
        when it falls due, and escalate long-ignored Bankers debt to the
        guard -- same crime/guard pipeline `justice.py` already runs, so a
        deadbeat guild eventually gets caught the normal way, not a bespoke
        one. No-op with no property and no debt (the common case)."""
        events = []
        house = self.house
        if house.owned and not house.squatting and self.clock.day >= (house.tax_due_day or 0):
            house.tax_due_day = self.clock.day + economy.CITY_PROPERTY_TAX_PERIOD_DAYS
            if self.money >= economy.CITY_PROPERTY_TAX:
                self._charge_roster(economy.CITY_PROPERTY_TAX)
                events.append(i18n.t("guild_holdings.bankers_collect_in_property_tax", fmt_money=fmt_money(economy.CITY_PROPERTY_TAX)))
            else:
                house.missed_payments += 1
                events.append(i18n.t("guild_holdings.guild_can_t_cover_property"))
        if (self.bankers_debt > 0 and self.bankers_debt_since is not None
                and self.clock.day - self.bankers_debt_since >= economy.CITY_PROPERTY_DEBT_GRACE_DAYS):
            self.bankers_debt_since = self.clock.day     # resets the grace window
            if self.leader is not None:
                self.leader.crime += 1
                events.append(i18n.t("guild_holdings.s_unpaid_debt_to_bankers", name=self.leader.name))
        return events

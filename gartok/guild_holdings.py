"""What the guild owns as a body: the bank chest, the City property, the
Bankers' debt and the garrison's stockpile.

Mixed into `guild.Guild`; the stores themselves live in `holdings.py`.
"""

from . import economy, magic, world


class HoldingsMixin:
    def rent_bank_chest(self):
        """Take up the Bankers' offer: the guild's first strongbox. The caller
        collects the fee first -- this only flips the capacity on."""
        self.bank.capacity = economy.BANK_CHEST_CAPACITY

    @property
    def bankers_services_blocked(self):
        """Outstanding debt shuts the Bankers' doors -- no new strongbox, no
        buying the property (back) -- until it's paid off."""
        return self.bankers_debt > 0

    def buy_city_property(self):
        self.house.buy(self.clock.day)

    def buy_oven(self):
        """The caller collects `economy.OVEN_PRICE` first."""
        self.house.oven = True

    def repossess_city_property(self):
        """ACCEPT: hand the property back, bank the missed rent as debt owed
        to the Bankers -- their services stay shut until it's paid."""
        self.bankers_debt += self.house.repossess()
        self.bankers_debt_since = self.clock.day

    # ------------------------------------------------------------------ #
    # the garrison: a Group parked on a "garrison" order, working a job    #
    # ------------------------------------------------------------------ #
    def garrison_stock_at(self, node_id):
        return self.garrison_stock.get(node_id, [])

    def _garrison_upkeep(self):
        """Once a day: every group parked on a `"garrison"` order banks its
        job's output into `garrison_stock`, keyed by the node it's standing
        on. A node whose `garrison_job` doesn't match the order's own `job`
        (or offers none at all -- true of every node today, see
        `world.Node.garrison_job`) produces nothing; the group still sits
        there, fed by the normal per-group upkeep, just not working."""
        events = []
        for g in self.groups:
            if g.empty or g.order is None or g.order.kind != "garrison":
                continue
            node = world.node(g.node)
            if node.garrison_job != g.order.job:
                continue

            if g.order.job == "study":
                for u in g.members:
                    event = magic.progress_study(u, group=g)
                    if event:
                        events.append(event)
                if not any(u.study_target for u in g.members):
                    g.order = None
                    events.append(f"{node.name}: studies are over -- rooms released.")
                elif not any(u.study_target and u.gold >= economy.TAVERN_STUDY_COST_PER_DAY
                             for u in g.members):
                    g.order = None
                    events.append(f"{node.name}: no one can pay for another night -- rooms released.")
                continue

            item = economy.GARRISON_JOBS.get(g.order.job)
            if item is None:
                continue
            count = economy.GARRISON_YIELD_PER_MEMBER_PER_DAY * len(g.members)
            self.garrison_stock.setdefault(g.node, []).extend([item] * count)
            events.append(f"{node.name}: the garrison gathers {count} {item}.")
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
            if self.gold >= economy.CITY_PROPERTY_TAX:
                self._charge_roster(economy.CITY_PROPERTY_TAX)
                events.append(f"The Bankers collect {economy.CITY_PROPERTY_TAX} copper in property tax.")
            else:
                house.missed_payments += 1
                events.append("The guild can't cover the property tax -- the Bankers note it.")
        if self.bankers_debt > 0 and self.bankers_debt_since is not None:
            if self.clock.day - self.bankers_debt_since >= economy.CITY_PROPERTY_DEBT_GRACE_DAYS:
                self.bankers_debt_since = self.clock.day     # resets the grace window
                if self.leader is not None:
                    self.leader.crime += 1
                    events.append(f"{self.leader.name}'s unpaid debt to the Bankers "
                                  "reaches the guard's ears.")
        return events

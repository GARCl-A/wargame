"""Field Command's desk, with no window: the Bankers' fortified outpost where the trust mission's sealed chest
(`data.MISSION_CHEST_ITEM`) is traded, intact, for a letter of receipt (`data.LETTER_ITEM`) -- the thing
`missions.turn_in` actually counts back at the City (`trust_screen.py`). No progress bar, no goal_qty --
either someone in the group is carrying the chest, or there is nothing to hand over. Once the Bankers vouch
for the guild, Commander Varkas's mentorship and the frontier supply run.

The desk's panels are data (`panels`), drawn by pygame's `LedgerScreen` and the browser's THE DESK
(`web/ledger_tab.py`).
"""

from . import data, economy, i18n, orders
from .constants import fmt_money


class LedgerDesk:
    def __init__(self, guild, group, on_done):
        self.guild, self.group = guild, group
        self.on_done = on_done          # the supply run leaves the desk
        self.notice = None

    def _carrier(self):
        return next((u for u in self.group.members
                    if u.has_item(data.MISSION_CHEST_ITEM)), None)

    def _act(self, key):
        if key == "exchange":
            carrier = self._carrier()
            if carrier is not None:
                carrier.remove_named(data.MISSION_CHEST_ITEM)
                carrier.give_to_pack(data.LETTER_ITEM)
                self.notice = (i18n.t("ledger.hands_over_sealed_chest_outpost", name=carrier.name))
        elif key == "accept_mentorship":
            from . import missions
            recruit = missions.make_treefolk_recruit()
            self.guild.add_member(recruit, self.group)
            signer = self.group.leader or self.group.members[0]
            missions.accept_treefolk_mentorship(self.guild, signer, recruit)
            self.notice = i18n.t("ledger.treefolk_joins_your_group_for", name=recruit.name)
        elif key == "deliver_recruit":
            from . import missions
            m_tree = next((m for m in self.guild.missions if m.template_id == "ledger_treefolk"), None)
            if m_tree is not None:
                recruit = next((u for u in self.guild.roster if u.uid == m_tree.recruit_uid), None)
                if recruit is not None:
                    missions.deliver_treefolk_recruit(self.guild, self.group, m_tree, recruit)
                    self.notice = i18n.t("ledger.steps_into_garrison_reward_received", name=recruit.name)
        elif key == "supply_run":
            try:
                self.group.order = orders.supply_run(self.guild, self.group)
                self.on_done()
            except ValueError as err:
                self.notice = str(err)

    def hub_cards(self):
        cards = [{"label": i18n.t("ledger.party_purse"), "value": fmt_money(sum(u.money for u in self.group.members)),
                  "tone": "money"}]
        if "bankers_trust" in self.guild.deeds_done:
            done = "ledger_hold_supply_run" in self.guild.deeds_done
            cards.insert(0, {"label": i18n.t("ledger.supply_runs"), "value": f"{self.guild.supply_runs_completed} / 10",
                             "tone": "good" if done else None})
        return cards

    def panels(self):
        """The chest while someone carries it, the mentorship and the supply run once the Bankers vouch
        for the guild, else the gate; each `{key, title, aside, rows, lines, button, warn}`, `rows` as
        `(label, value, tone)` and `button` as `(key, label, enabled)`."""
        out = []
        if self._carrier() is not None:
            out.append(self._chest())
        if "bankers_trust" in self.guild.deeds_done:
            out += [self._mentorship(), self._supply_run()]
        return out or [self._gate()]

    @staticmethod
    def _panel(key, title, aside=None, rows=(), lines=(), button=None, warn=None):
        return {"key": key, "title": title, "aside": aside, "rows": list(rows), "lines": list(lines),
                "button": button, "warn": warn}

    def _chest(self):
        return self._panel("chest", i18n.t("ledger.sealed_chest"), i18n.t("ledger.bankers_trust"), rows=[
            ("Carrier", self._carrier().name, None),
            (i18n.t("ledger.in_return"), i18n.t("ledger.letter_of_receipt_to_take"), "muted")],
            button=("exchange", i18n.t("ledger.hand_over_chest"), True))

    def _mentorship(self):
        from . import missions
        m_tree = next((m for m in self.guild.missions if m.template_id == "ledger_treefolk"), None)
        button = None
        if m_tree is None:
            rows = [("Offer", i18n.t("ledger.green_treefolk_recruit_racial_level"), None),
                    ("Task", i18n.t("ledger.train_them_to_racial_level"), "muted")]
            button = ("accept_mentorship", i18n.t("ledger.accept_recruit"), True)
        elif m_tree.state == "active":
            recruit = next((u for u in self.guild.roster if u.uid == m_tree.recruit_uid), None)
            if recruit is None:
                m_tree.state = "failed"
                rows = [("Status", i18n.t("ledger.treefolk_recruit_fell_in_battle"), "bad")]
            elif recruit in self.group.members:
                lvl = recruit.racial_level
                ready = lvl >= 2
                rows = [("Recruit", recruit.name, None),
                        ("Training", i18n.t("ledger.racial_level", lvl=lvl), "good" if ready else "muted"),
                        ("Reward", i18n.t("ledger.recruit_leaves_guild", fmt_money=fmt_money(missions.LEDGER_TREEFOLK.reward)),
                         "money")]
                button = ("deliver_recruit", i18n.t("ledger.deliver_recruit"), ready)
            else:
                rows = [("Recruit", i18n.t("ledger.is_in_another_group_bring", name=recruit.name), "muted")]
        else:
            rows = [("Status", i18n.t("ledger.treefolk_soldier_serves_with_honour"), "good"),
                    ("Gates", i18n.t("ledger.ledger_hold_stands_open_to"), "muted")]
        return self._panel("mentorship", i18n.t("ledger.garrison_mentorship"), i18n.t("ledger.commander_varkas"), rows=rows, button=button)

    def _supply_run(self):
        trip = orders.supply_hours(self.guild, self.group)
        cargo = self.group.free_cargo_capacity
        need = economy.SUPPLY_RUN_CARGO_KG
        can_run = cargo >= need
        return self._panel("supply_run", i18n.t("ledger.frontier_supply_run"), i18n.t("ledger.to_frontier_outpost_and_back"), rows=[
            ("Trip", i18n.t("ledger.hours_walking_kg_of_supplies", trip=trip, need=need), None),
            ("Pay", i18n.t("ledger.each_work_level", fmt_money=fmt_money(economy.SUPPLY_RUN_PAY), supply_run_level=economy.SUPPLY_RUN_LEVEL), "money"),
            ("Cargo", i18n.t("ledger.kg_free", cargo=cargo, need=need) if can_run
             else i18n.t("ledger.kg_free_bring_pack_animals", cargo=cargo, need=need),
             "good" if can_run else "bad")],
            button=("supply_run", i18n.t("ledger.depart_with_caravan"), can_run),
            warn=i18n.t("ledger.enemy_soldiers_may_ambush_each"))

    def _gate(self):
        return self._panel("gate", i18n.t("ledger.gatehouse"), lines=(
            i18n.t("ledger.sentries_look_band_over_from"),
            (i18n.t("ledger.commander_varkas_only_receives_couriers"))))

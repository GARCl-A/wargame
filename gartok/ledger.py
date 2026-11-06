"""Field Command's desk, with no window: the Bankers' fortified outpost where the trust mission's sealed chest
(`data.MISSION_CHEST_ITEM`) is traded, intact, for a letter of receipt (`data.LETTER_ITEM`) -- the thing
`missions.turn_in` actually counts back at the City (`trust_screen.py`). No progress bar, no goal_qty --
either someone in the group is carrying the chest, or there is nothing to hand over. Once the Bankers vouch
for the guild, the frontier supply run (Commander Varkas's mentorship is the Jobs tab's `job_board.LedgerBoard`).

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
        """The chest while someone carries it, the supply run once the Bankers vouch
        for the guild, else the gate; each `{key, title, aside, rows, lines, button, warn}`, `rows` as
        `(label, value, tone)` and `button` as `(key, label, enabled)`."""
        out = []
        if self._carrier() is not None:
            out.append(self._chest())
        if "bankers_trust" in self.guild.deeds_done:
            out.append(self._supply_run())
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

"""Ledger Hold's desk, with no window: the Bankers' fortified outpost where the trust mission's sealed chest
(`data.MISSION_CHEST_ITEM`) is traded, intact, for a letter of receipt (`data.LETTER_ITEM`) -- the thing
`missions.turn_in` actually counts back at the City (`trust_screen.py`). No progress bar, no goal_qty --
either someone in the group is carrying the chest, or there is nothing to hand over. Once the Bankers vouch
for the guild, Commander Varkas's mentorship and the frontier supply run.

The desk's panels are data (`panels`), drawn by pygame's `LedgerScreen` and the browser's THE DESK
(`web/ledger_tab.py`).
"""

from . import data, economy, orders
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
                self.notice = (f"{carrier.name} hands over the sealed chest -- the "
                               "outpost gives a letter of receipt in return.")
        elif key == "accept_mentorship":
            from . import missions
            recruit = missions.make_treefolk_recruit()
            self.guild.add_member(recruit, self.group)
            signer = self.group.leader or self.group.members[0]
            missions.accept_treefolk_mentorship(self.guild, signer, recruit)
            self.notice = f"{recruit.name} (Treefolk) joins your group for mentorship."
        elif key == "deliver_recruit":
            from . import missions
            m_tree = next((m for m in self.guild.missions if m.template_id == "ledger_treefolk"), None)
            if m_tree is not None:
                recruit = next((u for u in self.guild.roster if u.uid == m_tree.recruit_uid), None)
                if recruit is not None:
                    missions.deliver_treefolk_recruit(self.guild, self.group, m_tree, recruit)
                    self.notice = f"{recruit.name} steps into the garrison. $230 reward received!"
        elif key == "supply_run":
            try:
                self.group.order = orders.supply_run(self.guild, self.group)
                self.on_done()
            except ValueError as err:
                self.notice = str(err)

    def hub_cards(self):
        cards = [{"label": "party purse", "value": fmt_money(sum(u.money for u in self.group.members)),
                  "tone": "money"}]
        if "bankers_trust" in self.guild.deeds_done:
            done = "ledger_hold_supply_run" in self.guild.deeds_done
            cards.insert(0, {"label": "supply runs", "value": f"{self.guild.supply_runs_completed} / 10",
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
        return self._panel("chest", "The Sealed Chest", "the Bankers' trust", rows=[
            ("Carrier", self._carrier().name, None),
            ("In return", "a letter of receipt, to take back to the City", "muted")],
            button=("exchange", "Hand over the chest", True))

    def _mentorship(self):
        from . import missions
        m_tree = next((m for m in self.guild.missions if m.template_id == "ledger_treefolk"), None)
        button = None
        if m_tree is None:
            rows = [("Offer", "a green Treefolk recruit (racial level 0) joins the group", None),
                    ("Task", "train them to racial level 2, then bring them back", "muted")]
            button = ("accept_mentorship", "Accept the recruit", True)
        elif m_tree.state == "active":
            recruit = next((u for u in self.guild.roster if u.uid == m_tree.recruit_uid), None)
            if recruit is None:
                m_tree.state = "failed"
                rows = [("Status", "the Treefolk recruit fell in battle: the mentorship has failed", "bad")]
            elif recruit in self.group.members:
                lvl = recruit.racial_level
                ready = lvl >= 2
                rows = [("Recruit", recruit.name, None),
                        ("Training", f"racial level {lvl} / 2", "good" if ready else "muted"),
                        ("Reward", f"{fmt_money(missions.LEDGER_TREEFOLK.reward)}  ·  the recruit leaves the guild",
                         "money")]
                button = ("deliver_recruit", "Deliver the recruit", ready)
            else:
                rows = [("Recruit", f"{recruit.name} is in another group: bring them here to hand over", "muted")]
        else:
            rows = [("Status", "the Treefolk soldier serves with honour", "good"),
                    ("Gates", "Ledger Hold stands open to the guild", "muted")]
        return self._panel("mentorship", "Garrison Mentorship", "Commander Varkas", rows=rows, button=button)

    def _supply_run(self):
        trip = orders.supply_hours(self.guild, self.group)
        cargo = self.group.free_cargo_capacity
        need = economy.SUPPLY_RUN_CARGO_KG
        can_run = cargo >= need
        return self._panel("supply_run", "Frontier Supply Run", "to the Frontier Outpost and back", rows=[
            ("Trip", f"{trip:.1f} hours, walking {need:.0f} kg of supplies", None),
            ("Pay", f"{fmt_money(economy.SUPPLY_RUN_PAY)} each  ·  work level {economy.SUPPLY_RUN_LEVEL}", "money"),
            ("Cargo", f"{cargo:.1f} / {need:.0f} kg free" if can_run
             else f"{cargo:.1f} / {need:.0f} kg free: bring pack animals or lighten the load",
             "good" if can_run else "bad")],
            button=("supply_run", "Depart with the caravan", can_run),
            warn="Enemy soldiers may ambush each leg.")

    def _gate(self):
        return self._panel("gate", "The Gatehouse", lines=(
            "The sentries look the band over from the gatehouse.",
            ("Commander Varkas only receives couriers bearing the counting-house seal, "
             "or bands the Bankers vouch for.")))

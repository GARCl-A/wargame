"""A work node's two desks (the Lumber Yard, the Mine), with no window: WORK, the paid shifts with each
worker's tool and wage, and GATHERING, the licence and what a shift of keeping the finds is worth.

`WorkScreen` / `GatherScreen` are the pygame windows over them and `web/work_tab.py` the browser's.
"""

from . import economy, gather
from .constants import fmt_money

SHIFTS = (4, 8, 12, 16)


class WorkDesk:
    def __init__(self, guild, group, node):
        self.guild, self.group, self.node = guild, group, node
        self.report = []                # what the last shift paid

    def _wage(self, hours):
        return sum(economy.work_pay(self.node.id, hours, economy.work_level(u, self.node.id))
                   for u in self.group.members)

    def hub_cards(self):
        return [{"label": f"wage for {SHIFTS[-1]} h", "value": fmt_money(self._wage(SHIFTS[-1])), "tone": "money"},
                {"label": "party purse", "value": fmt_money(sum(u.money for u in self.group.members)),
                 "tone": "money"},
                {"label": "rations", "value": f"{self.group.rations}  ·  {self.group.rations_days} d",
                 "tone": "bad" if self.group.rations_days < 1 else None}]

    def _crew_note(self, u, tool):
        level = economy.work_level(u, self.node.id)
        own = level >= economy.LUMBER_LEVEL_OWN_AXE
        if own and u.work_level > level:
            return f"has outgrown this job even with their own {tool}: no more work XP here", "money"
        if not own and u.work_level > 0:
            return f"past this job bare-handed: their own {tool} pays more and keeps the work XP", "money"
        return None


class GatherDesk:
    def __init__(self, guild, group, node):
        self.guild, self.group, self.node = guild, group, node
        self.notice = None

    def buy_licence(self):
        if self.guild.buy_licence(self.node.id, self.group):
            self.notice = f"{self.node.name}: the gathering licence is the guild's."
        else:
            self.notice = "not enough coin for the licence"

    def _payback_line(self, price):
        """A full day's haul against the wage for this group, and the days a licence takes to pay."""
        haul, wage, risk = self.guild.shift_worth(self.group, self.node.id, gather.DAY_HOURS)
        line = (f"{gather.DAY_HOURS} h for this group: haul ~{fmt_money(round(haul))} sold, "
                f"wage {fmt_money(round(wage))}, {risk * 100:.0f}% ambush")
        if self.guild.has_licence(self.node.id):
            return line
        if haul <= wage:
            return line + " · the licence never pays back"
        return line + f" · licence pays back in ~{price / (haul - wage):.0f} days"

    def hub_cards(self):
        price = gather.licence_price(self.node.id)
        held = self.guild.has_licence(self.node.id)
        purse = sum(u.money for u in self.group.members)
        return [{"label": "licence", "value": "held" if held else fmt_money(price),
                 "tone": "good" if held else None},
                {"label": "party purse", "value": fmt_money(purse), "tone": "money"}]

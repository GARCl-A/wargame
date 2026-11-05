"""A work node's two desks (the Lumber Yard, the Mine), with no window: WORK, the paid shifts with each
worker's tool and wage, and GATHERING, the licence and what a shift of keeping the finds is worth.
`web/work_tab.py` draws them.
"""

from . import economy, gather, i18n
from .constants import fmt_money

SHIFTS = (4, 8, 12, 16)


class WorkDesk:
    def __init__(self, guild, group, node):
        self.guild, self.group, self.node = guild, group, node
        self.report = []                # what the last shift paid

    def _rations_card(self):
        g = self.group
        if not g.rations and g.rotten_rations:
            return {"label": i18n.lab("rations"), "value": i18n.t("work_desk.all_rotten", rotten_rations=g.rotten_rations), "tone": "bad"}
        return {"label": i18n.lab("rations"), "value": f"{g.rations}  ·  {g.rations_days} d",
                "tone": "bad" if g.rations_days < 1 else None}

    def _wage(self, hours):
        return sum(economy.work_pay(self.node.id, hours, economy.work_level(u, self.node.id))
                   for u in self.group.members)

    def hub_cards(self):
        return [{"label": i18n.t("work_desk.wage_for_h", shifts=SHIFTS[-1]), "value": fmt_money(self._wage(SHIFTS[-1])), "tone": "money"},
                {"label": i18n.t("work_desk.party_purse"), "value": fmt_money(sum(u.money for u in self.group.members)),
                 "tone": "money"},
                self._rations_card()]

    def _crew_note(self, u, tool):
        tool = i18n.Ref("item", tool)
        level = economy.work_level(u, self.node.id)
        own = level >= economy.LUMBER_LEVEL_OWN_AXE
        if own and u.work_level > level:
            return i18n.t("work_desk.has_outgrown_this_job_even", tool=tool), "money"
        if not own and u.work_level > 0:
            return i18n.t("work_desk.past_this_job_bare_handed", tool=tool), "money"
        return None


class GatherDesk:
    def __init__(self, guild, group, node):
        self.guild, self.group, self.node = guild, group, node
        self.notice = None
        self.report = []                # what the last shift found

    def buy_licence(self):
        if self.guild.buy_licence(self.node.id, self.group):
            self.notice = i18n.t("work_desk.gathering_licence_is_guild_s", name=self.node.name)
        else:
            self.notice = i18n.t("work_desk.not_enough_coin_for_licence")

    def _gather_note(self, u, tool):
        """What a shift of gathering does for `u`: their haul and work XP, or that they only stand guard."""
        tool = i18n.Ref("item", tool)
        if not economy.owns_tool(u, self.node.id):
            return i18n.t("work_desk.no_stands_guard_no_haul", tool=tool)
        level = gather.LEVEL[self.node.id]
        if u.work_level > level:
            return i18n.t("work_desk.own_gathers_but_has_outgrown", tool=tool, work_level=u.work_level)
        return i18n.t("work_desk.own_gathers_work_xp_x", tool=tool, value=level - u.work_level + 1)

    def _payback_line(self, price):
        """A full day's haul for this group and, before the licence is bought, the days of it the
        licence takes to pay for itself."""
        haul, risk = self.guild.shift_worth(self.group, self.node.id, gather.DAY_HOURS)
        line = i18n.t("work_desk.h_for_this_group_haul", day_hours=gather.DAY_HOURS, fmt_money=fmt_money(round(haul)), value=risk * 100)
        if self.guild.has_licence(self.node.id) or not haul:
            return line
        return line + i18n.t("work_desk.licence_pays_for_itself_in", value=price / haul)

    def hub_cards(self):
        purse = {"label": i18n.t("work_desk.party_purse"), "value": fmt_money(sum(u.money for u in self.group.members)), "tone": "money"}
        if not gather.needs_licence(self.node.id):
            return [purse]
        held = self.guild.has_licence(self.node.id)
        return [{"label": i18n.t("work_desk.licence"), "value": i18n.t("work_desk.licence_held") if held else fmt_money(gather.licence_price(self.node.id)),
                 "tone": "good" if held else None}, purse]

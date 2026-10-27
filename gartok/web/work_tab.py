"""A work node's two tabs in the browser (the Lumber Yard, the Mine): WORK, the paid shifts with each
worker's tool and wage, and GATHERING, the licence and the shifts that keep what the crew finds.

The reads are pygame's own (`WorkScreen`, `GatherScreen`), borrowed as the map borrows `MapScreen`'s,
until step 10 of `docs/plans/web_frontend.md` moves them here. The verbs that run the clock live on
`HubSession`, which holds the map.
"""

from .. import economy, gather, item_icon
from ..gather_screen import GatherScreen
from ..work_screen import SHIFTS, WorkScreen
from .shop_tab import _portrait


class WorkTab:
    _wage = WorkScreen._wage
    _crew_note = WorkScreen._crew_note
    hub_cards = WorkScreen.hub_cards

    def __init__(self, guild, group, node):
        self.guild, self.group, self.node = guild, group, node
        self.report = []                # what the last shift paid

    def state(self):
        tool = economy.WORK_TOOLS[self.node.id]
        crew = []
        for u in self.group.members:
            level = economy.work_level(u, self.node.id)
            own = level >= economy.LUMBER_LEVEL_OWN_AXE
            note = self._crew_note(u, tool)
            crew.append({"name": u.name, "portrait": _portrait(u), "own": own,
                         "sub": f"own {tool.lower()}" if own else f"the foreman's {tool.lower()}",
                         "pay": economy.work_pay(self.node.id, SHIFTS[-1], level),
                         "note": note[0] if note else None})
        return {"cards": self.hub_cards(), "tool": tool, "glyph": item_icon.glyph(tool), "day": SHIFTS[-1],
                "crew": crew, "shifts": [{"hours": h, "wage": self._wage(h)} for h in SHIFTS],
                "report": self.report}


class GatherTab:
    hub_cards = GatherScreen.hub_cards
    _payback_line = GatherScreen._payback_line

    def __init__(self, guild, group, node):
        self.guild, self.group, self.node = guild, group, node
        self.notice = None

    def buy_licence(self):
        if self.guild.buy_licence(self.node.id, self.group):
            self.notice = f"{self.node.name}: the gathering licence is the guild's."
        else:
            self.notice = "not enough coin for the licence"

    def state(self):
        node = self.node.id
        price = gather.licence_price(node)
        main = gather.drops(node)[0][0]
        shifts = []
        for h in SHIFTS:
            haul, wage, risk = self.guild.shift_worth(self.group, node, h)
            shifts.append({"hours": h, "haul": round(haul), "wage": round(wage), "risk": round(risk * 100),
                           "good": haul > wage})
        crew = []
        for u in self.group.members:
            haul, wage = self.guild.worker_worth(u, node, gather.DAY_HOURS)
            crew.append({"name": u.name, "portrait": _portrait(u), "sub": f"{u.race['name']} · {u.occupation['name']}",
                         "haul": round(haul), "wage": round(wage), "good": haul > wage})
        notice, self.notice = self.notice, None
        return {"cards": self.hub_cards(), "held": self.guild.has_licence(node), "price": price,
                "short": self.guild.licence_shortfall(node, self.group),
                "rolls": f"{gather.rolls(gather.DAY_HOURS):.1f} rolls a worker in {gather.DAY_HOURS} h",
                "drops": [{"name": n, "glyph": item_icon.glyph(n), "pct": pct, "sell": economy.sell_price(n)}
                          for n, pct in gather.drops(node)],
                "glyph": item_icon.glyph(main), "shifts": shifts, "crew": crew, "day": gather.DAY_HOURS,
                "payback": self._payback_line(price), "notice": notice}

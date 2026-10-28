"""Ledger Hold's THE DESK in the browser: on leather the band here (who carries the Bankers' sealed chest),
on paper the desk's panels as `ledger.LedgerDesk.panels` lays them out: the chest to hand over, Commander
Varkas's mentorship, the frontier supply run, or the gatehouse that turns the band away.

The rules are `ledger.LedgerDesk`'s, which pygame's `LedgerScreen` reads too. The supply run leaves
the desk: `HubSession` sends the band back to the map, where the clock runs.
"""

from .. import data
from ..ledger import LedgerDesk
from .shop_tab import _portrait


class LedgerTab:
    def __init__(self, guild, group, node):
        self.s = LedgerDesk(guild, group, lambda: None)
        self.guild, self.group, self.node = guild, group, node

    def act(self, key):
        """Press the desk's button `key`; one the desk does not offer now is refused."""
        offered = {p["button"][0]: p["button"][2] for p in self.s.panels() if p["button"]}
        if key not in offered:
            raise ValueError("the desk offers no such thing now")
        if not offered[key]:
            raise ValueError("the desk cannot do that yet")
        self.s.notice = None
        self.s._act(key)

    @staticmethod
    def _panel(p):
        button = p["button"]
        return {"key": p["key"], "title": p["title"], "aside": p["aside"], "lines": p["lines"], "warn": p["warn"],
                "rows": [{"label": lbl, "value": v, "tone": tone} for lbl, v, tone in p["rows"]],
                "button": {"key": button[0], "label": button[1], "can": button[2]} if button else None}

    def state(self):
        s = self.s
        members = [{"uid": u.uid, "name": u.name, "portrait": _portrait(u),
                    "sub": f"{u.race['name']} {u.occupation['name']}",
                    "chest": u.has_item(data.MISSION_CHEST_ITEM), "letter": u.has_item(data.LETTER_ITEM)}
                   for u in self.group.members]
        notice, s.notice = s.notice, None
        return {"cards": s.hub_cards(), "members": members, "panels": [self._panel(p) for p in s.panels()],
                "notice": notice}

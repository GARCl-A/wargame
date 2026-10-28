"""The Apothecary's MEDIC tab in the browser: the ward on leather (who is hurt, sick or poisoned, and
what each one costs), the bill on paper (the picked patients, the total, who waits) and the button that
treats them, or admits the one picked for a hospital stay.

The reads and the pick rule are `medic.Ward`'s, which pygame's tab reads too. The verb that may hand the band
to the clock lives on `HubSession`, which holds the map.
"""

from .. import economy, medic
from .shop_tab import _portrait


class MedicTab(medic.Ward):
    pick = medic.Ward._toggle

    def __init__(self, guild, group, node):
        super().__init__(guild, group)
        self.node = node
        self.report = []                # what the last treatment said

    def treat(self):
        ok, lines = self._treat()
        self.report = lines if ok else []
        return ok

    def state(self):
        by_uid = {u.uid: u for u in self.group.members}
        ward = []
        for q in self._quotes():
            u = by_uid[q.uid]
            ward.append({"uid": q.uid, "name": q.name, "portrait": _portrait(u),
                         "sub": f"{u.race['name']} {u.occupation['name'].lower()} · HP {u.hp} / {u.hp_max}",
                         "parts": [{"label": lbl, "cost": c, "hours": h} for lbl, c, h in q.parts],
                         "cost": q.cost, "hours": q.hours, "stay": not q.offered, "picked": q.uid in self.picked})
        picked = self._picked_quotes()
        cost, hours = medic.total(picked)
        purse = sum(u.money for u in (*self.group.members, *getattr(self.group, "stores", ())))
        stay = self._stay()
        notice, self.notice = self.notice, None
        ill = {u["uid"] for u in ward}
        return {"cards": self.hub_cards(), "ward": ward, "cost": cost, "hours": hours, "purse": purse,
                "can_pay": purse >= cost, "stay": self._stay_where() if stay else None,
                "fine": [u.name for u in self.group.members if u.uid not in ill],
                "max_hours": economy.MEDIC_MAX_HOURS, "report": self.report, "notice": None if self.report else notice}

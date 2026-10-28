"""A sanctuary's INITIATION tab in the browser: the band on leather (who may stay to board for the
school's rite, where each one stands in it, or why they cannot), the school's terms on paper and the
button that leaves the picked one boarding.

The rules are `rite.Initiation`'s, which pygame's `InitiationScreen` reads too: the terms, the blockers,
the pick and the begin. The verb that may hand the band to the clock (`begin`) lives on `HubSession`, which holds the map.
"""

from .. import factions, rite
from .shop_tab import _portrait


class InitiationTab:
    def __init__(self, guild, group, node):
        self.s = rite.Initiation(guild, group)
        self.guild, self.group, self.node = guild, group, node
        self.report = []                    # what the last begin said

    def pick(self, uid):
        if self.s._member(uid) is None:
            raise ValueError("no such member in the band")
        self.report = []
        self.s._pick(uid)

    def begin(self):
        """Leave the picked one boarding. True when the rite began."""
        if self.s._action() is None:
            raise ValueError("nobody picked can begin the rite")
        ok, lines = self.s._begin()
        self.report = lines if ok else []
        return ok

    def state(self):
        s, school = self.s, self.s.school
        rows = {r["key"]: r for r in s._rows()}
        members = []
        for u in self.group.members:
            r = rows[u.uid]
            label, done, total = rite.stage(u, school)
            members.append({"uid": u.uid, "name": u.name, "portrait": _portrait(u), "sub": r["sub"],
                            "status": s._status(u), "stage": label, "done": done, "total": total,
                            "initiated": school in u.magic_sources, "started": rite.paid(u, school),
                            "note": r["note"], "on": r["enabled"], "picked": r["picked"]})
        picked = s._member(s.picked)
        notice, s.notice = s.notice, None
        return {"cards": s.hub_cards(), "school": school.title(),
                "faction": factions.FACTIONS[rite.FACTION[school]].name,
                "terms": [{"label": lbl, "value": val, "ok": ok} for lbl, val, ok in s._terms()],
                "members": members, "picked": picked.name if picked else None, "action": s._action(),
                "report": self.report, "notice": None if self.report else notice}

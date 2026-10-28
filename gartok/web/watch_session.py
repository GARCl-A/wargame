"""Who minds the wagon at a place it cannot enter, as pygame's `WatchScreen`: everyone goes in until a
click leaves them outside; one guard keeps it safe (`wagon_watch`). GO IN hands the party to the place."""

from typing import ClassVar

from .. import wagon_watch, world
from ..map_screen import node_icon
from .map_session import _portrait, _when
from .session import Session


def watch_state(group, goes):
    """The watch's page and its cards: who goes in and what the wagon risks; the hunt's watch reads it too."""
    node = world.node(group.node)
    guards = [u for u in group.members if u not in goes]
    return {"members": [{"uid": u.uid, "name": u.name, "portrait": _portrait(u),
                         "what": f"{u.race['name']} {u.occupation['name'].lower()}",
                         "level": f"level {u.combat_level}", "goes": u in goes} for u in group.members],
            "going": len(goes), "outside": len(guards), "guarded": bool(guards),
            "risk": wagon_watch.risk(group, node), "place_risk": node.wagon_risk,
            "flight": wagon_watch.flight_chance(group)}


def toggle(group, goes, uid):
    """`goes` with the member `uid` moved in or out; the last one in cannot stay out."""
    u = next((m for m in group.members if m.uid == uid), None)
    if u is None:
        raise ValueError("no such member in the band")
    if u not in goes:
        return [m for m in group.members if m in goes or m is u]
    if len(goes) == 1:
        raise ValueError("someone has to go in")
    return [m for m in goes if m is not u]


class WatchSession(Session):
    screen = "watch"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "watch": lambda s, b: s.toggle(b["uid"]),
        "go": lambda s, b: s.go(),
        "leave": lambda s, b: s.leave(),
    }

    def __init__(self, map_session, group, label, lead, go):
        """`label` is the seal's (ENTER THE RUINS), `lead` what waits inside, `go(party, guarded)` what
        GO IN opens."""
        self.map = map_session
        self.group = group
        self.label = label
        self.lead = lead
        self._go = go
        self.goes = list(group.members)

    def toggle(self, uid):
        self.goes = toggle(self.group, self.goes, uid)
        return self.state()

    def go(self):
        return self._go(list(self.goes), len(self.goes) < len(self.group.members))

    def leave(self):
        from .dialogue_session import _to_map
        return _to_map(self.map, self.group)

    def state(self):
        g, n = self.group, world.node(self.group.node)
        day, at = _when(self.map.guild, 0)
        return {"band": g.display_name, "day": day, "at": at, "title": n.name,
                "icon": "/".join(node_icon(n.id) or ("map", "signpost")), "label": self.label.capitalize(),
                "lead": self.lead, "watch": watch_state(g, self.goes)}

"""A screen the map opens that the browser does not draw yet (a hub, the guild, a fight): it says
where the band went and what pygame plays there until its own step of
`docs/plans/web_frontend.md` lands, then goes back to the map."""

from typing import ClassVar

from .. import forced, node_functions, world
from ..map_screen import node_icon
from .session import Session

STEP_HUBS = "the hubs and the other screens come in step 9"
STEP_FIGHT = "a campaign fight joins the browser in step 10"


def _label(order, here):
    """The node button's label for an interactive order, as the map's inspector shows it."""
    if order.kind == "arena":
        return "Enter the arena"
    fn = next((f for f in node_functions.FUNCTIONS.values() if f.order_kind == order.kind and f.label), None)
    if fn is None:
        return order.kind.replace("_", " ").capitalize()
    return (here.shop_label if fn.id == "shop" and here.shop_label else fn.label).capitalize()


class AwaySession(Session):
    screen = "away"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {"back": lambda s, b: s.resume() if s.resume else s.map.back()}

    def __init__(self, map_session, group, order, fight=False, title=None, what=None, resume=None):
        self.map = map_session
        self.resume = resume              # the screen that sent it, when it is not the map
        self.group = group
        self.order = order
        self.fight = fight
        self.title = title
        self.what = what

    def state(self):
        g, here = self.group, world.node(self.group.node)
        if self.fight and self.order is None:
            title = self.title
            line = (f"{self.what.capitalize()} is played in pygame for now: {STEP_FIGHT}. "
                    f"{g.display_name} goes back to the map, and nothing has changed.")
        elif self.fight:
            title = forced.EVENTS[self.order.kind].label or "A fight"
            line = (f"{len(self.order.pack)} foes stand before {g.display_name}. The fight is played in "
                    f"pygame for now: {STEP_FIGHT}. The band waits on the map with its fight due, and the save keeps it.")
        elif self.order is not None:
            title = _label(self.order, here)
            line = (f"{g.display_name} goes in at {here.name}. Its screen is played in pygame for now: "
                    f"{STEP_HUBS}.")
        else:
            title = self.title
            line = f"{self.what.capitalize()} is played in pygame for now: {STEP_HUBS}."
        return {"title": title.capitalize() if title.isupper() else title, "place": here.name,
                "icon": "/".join(node_icon(here.id) or ("map", "signpost")), "band": g.display_name,
                "line": line, "fight": self.fight}

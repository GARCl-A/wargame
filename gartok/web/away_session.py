"""A place the map opens that the browser does not play yet (the searches' finds and the errands'
fights): it says where the band went and that pygame plays it until its part of step 10 of
`docs/plans/web_frontend.md` lands, then goes back to the map."""

from typing import ClassVar

from .. import node_functions, world
from ..map_screen import node_icon
from .session import Session

STEP_FIGHT = "the rest of the campaign's fights join the browser in step 10"


def _label(order, here):
    """The node button's label for an interactive order, as the map's inspector shows it."""
    fn = next((f for f in node_functions.FUNCTIONS.values() if f.order_kind == order.kind and f.label), None)
    if fn is None:
        return order.kind.replace("_", " ").capitalize()
    return (here.shop_label if fn.id == "shop" and here.shop_label else fn.label).capitalize()


class AwaySession(Session):
    screen = "away"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {"back": lambda s, b: s.map.back()}

    def __init__(self, map_session, group, order):
        self.map = map_session
        self.group = group
        self.order = order

    def state(self):
        g, here = self.group, world.node(self.group.node)
        title = _label(self.order, here)
        return {"title": title.capitalize() if title.isupper() else title, "place": here.name,
                "icon": "/".join(node_icon(here.id) or ("map", "signpost")), "band": g.display_name,
                "line": f"{g.display_name} goes in at {here.name}. It is played in pygame for now: {STEP_FIGHT}.",
                "fight": True}

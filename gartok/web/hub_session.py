"""A node's screens behind one row of tabs, in the browser: the keeper's strip, the tabs, the way back
to the map. The shop is the first tab (`shop_tab.ShopTab`); a tab the browser does not draw yet says
so inside the frame, and its screen is played in pygame until its part of step 9 of
`docs/plans/web_frontend.md` lands.

The tabs follow the hub pygame opens for the same order (`app_nodes`, `hub_screen.TabbedHubScreen`).
"""

from typing import ClassVar

from .. import artwork, world
from ..hub_screen import TabbedHubScreen
from ..map_screen import node_icon
from .session import Session, asset_url
from .shop_tab import ShopTab

# order kind -> its hub's tabs, where it is not the node's own list (`_node_tabs`)
HUBS = {
    "forge": (("shop", "Shop"), ("craft", "Forge")),
    "tanner": (("shop", "Shop"), ("jobs", "Jobs")),
    "apothecary": (("shop", "Shop"), ("medic", "Medic"), ("craft", "Craft"), ("jobs", "Jobs")),
    "library": (("shop", "Shop"), ("craft", "Write"), ("jobs", "Jobs")),
}
HUB_KINDS = {"market", "carpenter", "stable", "shrine", *HUBS}
LIVE = {"shop"}                        # the tabs the browser draws so far
# what a tab not drawn yet is, for its note
WHAT = {"recruits": "the recruits", "rooms": "the study rooms", "perform": "the stage", "tavern": "the tavern",
        "stable": "the stables", "forge": "the forge", "craft": "the workbench", "carpenter": "the carpentry",
        "wagons": "the wagon yard", "jobs": "the jobs board", "medic": "the Medic", "study": "the study desk",
        "initiation": "the initiation", "work": "the paid shifts", "gather": "the gathering"}


def _node_tabs(node):
    """The tabs `TabbedHubScreen.for_node` builds for `node`, in its order."""
    tabs = []
    if node.has("shop"):
        tabs.append(("shop", "Food & Drink" if node.id == "tavern" else "Farm" if node.id == "farm" else "Shop"))
    if node.has("recruit"):
        tabs += ((("recruits", "Recruit"), ("rooms", "Study"), ("perform", "Perform")) if node.id == "tavern"
                 else (("tavern", "Tavern"),))
    if node.has("stable"):
        tabs.append(("stable", "Stables"))
    if node.has("forge"):
        tabs.append(("forge", "Forge"))
    if node.has("carpenter"):
        tabs += (("carpenter", "Carpentry"), ("wagons", "Wagons"))
    if node.has("tanner"):
        tabs.append(("jobs", "Jobs"))
    if node.has("apothecary"):
        tabs += (("medic", "Medic"), ("jobs", "Jobs"))
    if node.has("library"):
        tabs += (("study", "Study"), ("jobs", "Jobs"))
    if node.has("shrine"):
        tabs += (("jobs", "Jobs"), ("initiation", "Initiation"))
    if node.has("work"):
        tabs.append(("work", "Work"))
        from .. import gather
        if gather.can_gather(node.id):
            tabs.append(("gather", "Gathering"))
    return tabs or [("shop", "Shop")]


def tabs_for(kind, node):
    return list(HUBS.get(kind) or _node_tabs(node))


def opens_hub(order, node):
    """True when the browser plays `order` at `node` in a hub (the Farm's stables only beside its shop,
    as `App._open_stables` does)."""
    return order.kind in HUB_KINDS and (order.kind != "stable" or node.has("shop"))


def _shop(verb):
    """A shop verb: it acts on the shop tab and answers the whole hub."""
    def run(s, b):
        verb(s.shop, b)
        return s.state()
    return run


class HubSession(Session):
    screen = "hub"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "tab": lambda s, b: s.pick_tab(b["key"]),
        "back": lambda s, b: s.map.back(),
        "buy": _shop(lambda t, b: t.buy(b["name"], b.get("qty", 1), b.get("to"), b.get("zone", "pack"))),
        "move": _shop(lambda t, b: t.move(b["picks"], b["to"], b.get("zone", "pack"))),
        "sell": _shop(lambda t, b: t.sell(b["picks"])),
        "lock": _shop(lambda t, b: t.lock(b["owner"], b["name"])),
        "mark": _shop(lambda t, b: t.mark(b["name"])),
        "sell_marked": _shop(lambda t, b: t.sell_marked()),
        "distribute": _shop(lambda t, b: t.distribute()),
    }

    keeper = TabbedHubScreen.keeper         # reads `node` and `tab`

    def __init__(self, map_session, group, order):
        self.map = map_session
        self.guild = map_session.guild
        self.group = group
        self.order = order
        self.node = world.node(group.node)
        self.tabs = tabs_for(order.kind, self.node)
        first = "shop" if order.kind in ("market", "stable") else {"forge": "craft"}.get(order.kind, order.kind)
        self.tab = first if any(k == first for k, _ in self.tabs) else self.tabs[0][0]
        self._shop = None

    @property
    def shop(self):
        if not any(k == "shop" for k, _ in self.tabs):
            raise ValueError("this place has no shop")
        if self._shop is None:
            self._shop = ShopTab(self.guild, self.group, self.node)
        return self._shop

    def pick_tab(self, key):
        if not any(k == key for k, _ in self.tabs):
            raise ValueError(f"no {key} tab here")
        self.tab = key
        return self.state()

    def state(self):
        c, n = self.guild.clock, self.node
        k = self.keeper()
        part = "night" if not c.is_daylight else "morning" if c.hour_of_day < 12 else "afternoon" if c.hour_of_day < 15 else "evening"
        keeper = {"name": k.get("name"), "caption": k.get("caption", ""), "bent": k.get("bent", ""),
                  "line": k.get("line", ""),
                  "portrait": asset_url(artwork.portrait_path(None, k["portrait"])) if k.get("portrait") else None}
        tongue = f" · the traders speak {n.language}" if getattr(n, "language", None) else ""
        out = {"place": n.name, "sub": f"Day {c.day}, {part}{tongue}", "band": self.group.display_name,
               "icon": "/".join(node_icon(n.id) or ("map", "signpost")), "keeper": keeper,
               "tabs": [{"key": key, "label": label, "live": key in LIVE} for key, label in self.tabs],
               "tab": self.tab}
        if self.tab == "shop":
            out["shop"] = self.shop.state()
        else:
            label = next(lbl for key, lbl in self.tabs if key == self.tab)
            out["away"] = {"title": label, "line": (f"{WHAT.get(self.tab, label).capitalize()} at {n.name} is played "
                                                    "in pygame for now: the hub's other tabs follow the shop in "
                                                    "step 9.")}
        return out

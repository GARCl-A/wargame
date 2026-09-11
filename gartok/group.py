"""A group: a subset of the guild's roster that is always in one place.

Every unit belongs to exactly one group, even if that group has just the one
member (a "solo group"). Groups own **position** (the world node they're
standing on) and **squad composition**; everything shared -- the bank chest,
faction reputation, the campaign clock, the taverna pool -- stays on `Guild`
(see `guild.py`).

Two groups standing on the same node may be merged; a group may be split by
peeling members off into a new one at the same node -- see
`Guild.split_group`/`Guild.merge_groups`. `order` is the seam for the
tick/orders map loop (travel / work / hunt / ... in flight for this group);
unused until that lands.
"""

from uuid import uuid4


class Group:
    def __init__(self, members, node=None, name=None, gid=None):
        self.gid = gid or uuid4().hex     # stable id: save refs, map selection
        self.members = list(members)      # list[Unit]
        self.node = node                  # world node id
        self.name = name                  # optional label ("Water Team"), or None
        self.order = None                 # in-flight Order, or None (idle) -- later

    def __len__(self):
        return len(self.members)

    @property
    def empty(self):
        return not self.members

    @property
    def busy(self):
        """True while an order is actually in flight -- `order is None` and an
        explicit `orders.idle()` both mean idle."""
        return self.order is not None and self.order.kind != "idle"

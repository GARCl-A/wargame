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

Every group also has a **leader** -- who speaks for it (haggling, see
`economy._haggle_fraction`) and what it holds together: `capacity` is how many
members the leader's Charisma can hold in one coalition; past that,
`overextension` counts the excess and `Guild._sync_leadership` folds it into
every member's Mental Defense (`Unit._derive_ac`) -- an overstretched group is
individually easier to rattle. The leader can be swapped for any other member
of the group at any time, free (`set_leader`); it only auto-succeeds
(`ensure_leader`, by Charisma) when the current leader stops being a member at
all (death, or peeled into a different group by a split).
"""

from uuid import uuid4

BASE_CAPACITY = 3   # + the leader's Charisma modifier -- see `capacity`/`overextension`


class Group:
    def __init__(self, members, node=None, name=None, gid=None, leader=None):
        self.gid = gid or uuid4().hex     # stable id: save refs, map selection
        self.members = list(members)      # list[Unit]
        self.node = node                  # world node id
        self.name = name                  # optional label ("Water Team"), or None
        self.order = None                 # in-flight Order, or None (idle) -- later
        self.leader = leader              # Unit; None resolves via ensure_leader below
        self.ensure_leader()

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

    # ------------------------------------------------------------------ #
    # leadership                                                         #
    # ------------------------------------------------------------------ #
    def ensure_leader(self):
        """Auto-succession: if the current leader isn't a member any more (died,
        never set, split off elsewhere), the highest-Charisma member left takes
        over. A no-op otherwise -- this never overrides a deliberate choice."""
        if self.members and self.leader not in self.members:
            self.leader = max(self.members, key=lambda u: u.mod_charisma)

    def set_leader(self, unit):
        """Hand leadership to `unit` -- free, any time, as long as they're
        already a member (a group is a physical thing; leading it from
        elsewhere makes no sense)."""
        if unit not in self.members:
            raise ValueError("leader must be a member of the group")
        self.leader = unit

    @property
    def capacity(self):
        """Members this group's leader can hold as one coalition before
        cohesion starts to suffer -- `BASE_CAPACITY` + the leader's Charisma
        modifier. Retune `BASE_CAPACITY` freely, like `progression`'s
        thresholds."""
        return BASE_CAPACITY + (self.leader.mod_charisma if self.leader else 0)

    @property
    def overextension(self):
        """How far past `capacity` this group is right now. Costs every
        member Mental Defense (see `Unit._derive_ac`) rather than blocking
        recruitment/merges outright -- the guild can still grow, it just gets
        easier to rattle."""
        return max(0, len(self.members) - self.capacity)

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

from . import items
from .animals import feed_herd
from .data import METERS_PER_SQUARE

BASE_CAPACITY = 3   # + the leader's Charisma modifier -- see `capacity`/`overextension`
HERD_BASE = 3       # + the leader's Wisdom modifier -- see `herd_capacity`
BASE_SLOTS = 2      # groups an unknown guild may run: one to study, one in the field
FAME_PER_SLOT = 3   # total reputation that buys the guild one more group


def _food_in(pack):
    return sum(qty for name, qty in pack if items.is_food(name.split(" (")[0]))


class Group:
    def __init__(self, members, node=None, name=None, gid=None, leader=None, wagons=None, herd=None):
        self.gid = gid or uuid4().hex     # stable id: save refs, map selection
        self.members = list(members)      # list[Unit]
        self.node = node                  # world node id
        self.name = name                  # optional label ("Water Team"), or None
        self.order = None                 # in-flight Order, or None (idle) -- later
        self.pending = None               # a forced Order (orders.FORCED_KINDS) that came due and awaits its fight
        self.leader = leader              # Unit; None resolves via ensure_leader below
        self.herd = list(herd or [])      # animals.Animal -- lost with the group
        self.wagons = []                  # wagon.Wagon -- lost with the group
        for wagon in wagons or []:
            self.add_wagon(wagon)
        self.herd_notice = None           # day an overextended herd starts to stray -- see cohesion.py
        self.ensure_leader()

    def __len__(self):
        return len(self.members)

    def add_wagon(self, wagon):
        self.wagons.append(wagon)
        wagon._group = self

    def remove_wagon(self, wagon):
        self.wagons.remove(wagon)
        wagon._group = None
        for animal in self.herd:
            if animal.hitch == wagon.uid:
                animal.hitch = None

    def pulling(self, animal):
        """The wagon of this group `animal` is hitched to, or None."""
        return next((w for w in self.wagons
                     if w.uid == animal.hitch and animal.role == "draft" and not w.broken), None)

    def wear_wagons(self, distance):
        """The road wears every wagon (`Wagon.wear`); one that breaks lets its animals go
        -- they stay in the herd. Returns the log lines."""
        events = []
        for wagon in self.wagons:
            if wagon.wear(distance) and wagon.broken:
                for animal in self.herd:
                    if animal.hitch == wagon.uid:
                        animal.hitch = None
                events.append(f"the {wagon.kind.lower()} of {self.display_name} breaks down on the road.")
        return events

    def hitch(self, animal, wagon, *, swap=False):
        """Harness `animal` to `wagon` (None unhitches). False if the animal wears no
        Harness, the wagon is not this group's, or its slots are full -- unless
        `swap`, when a full wagon gives up one animal, which takes the place `animal`
        leaves (its old wagon, or none)."""
        if wagon is None:
            animal.hitch = None
            return True
        if animal.role != "draft" or wagon not in self.wagons:
            return False
        old = self.pulling(animal)
        if old is not wagon and not wagon.free_slots:
            if not swap:
                return False
            wagon.draft[0].hitch = old.uid if old else None
        animal.hitch = wagon.uid
        return True

    def hitch_idle(self):
        """Every harnessed animal pulling nothing takes the first wagon with a
        free slot."""
        for animal in self.herd:
            if animal.role == "draft" and self.pulling(animal) is None:
                wagon = next((w for w in self.wagons if w.free_slots), None)
                if wagon is not None:
                    animal.hitch = wagon.uid

    def next_hitch(self, animal):
        """Cycle `animal`: the next wagon with room, then unhitched, then round."""
        current = self.pulling(animal)
        order = [*self.wagons, None]
        start = order.index(current) + 1 if current in order else 0
        for wagon in order[start:] + order[:start]:
            if wagon is not current and (wagon is None or wagon.free_slots):
                self.hitch(animal, wagon)
                return

    @property
    def carried_rations(self):
        """Meals on the wagons and on the animals' backs."""
        return sum(_food_in(pack) for pack in self.food_stores())

    def food_stores(self):
        """Packs of food that belong to the group itself rather than a member:
        the wagons' cargo, then each animal's load."""
        return [*(w.stash.items for w in self.wagons), *(a.stash.items for a in self.herd)]

    def feed_animals(self):
        """One day's feeding: each animal eats from its own load, then the rest of
        the group's stores, then any member's pack. They starve and die after
        `animals.STARVE_DAYS` unfed days. Returns the log lines."""
        def packs_for(animal):
            own = animal.stash.items
            return [own, *(p for p in self.food_stores() if p is not own),
                    *(u._base_inventory for u in self.members)]

        return feed_herd(self.herd, packs_for)

    @property
    def display_name(self):
        if self.name:
            return self.name
        if self.leader:
            return f"{self.leader.name}'s Band"
        return f"Group ({len(self.members)})"

    @property
    def empty(self):
        return not self.members

    @property
    def busy(self):
        """True while an order is actually in flight -- `order is None` and an
        explicit `orders.idle()` both mean idle."""
        return self.order is not None and self.order.kind != "idle"

    @property
    def fight_due(self):
        """A forced order came due and is waiting for its fight (`pending`)."""
        return self.pending is not None

    @property
    def locked(self):
        """True while an order actually blocks splitting this group or merging
        another into it -- same as `busy` except a standing `"garrison"` order
        doesn't count: those members aren't going anywhere, so peeling some
        off or folding another group in is still physically fine. See
        `Guild.split_group`/`merge_groups`, [[gartok-property-two-paths]].

        A forced order waiting in `pending` locks too, though `order` is already
        None by then (so `busy` and `advance` leave the group alone): the squad
        is about to fight and must stay as it is."""
        if self.fight_due:
            return True
        return self.order is not None and self.order.kind not in ("idle", "garrison")

    def has_talent(self, talent_id):
        return any(u.has_talent(talent_id) for u in self.members)

    # ------------------------------------------------------------------ #
    # leadership                                                         #
    # ------------------------------------------------------------------ #
    def ensure_leader(self):
        """Auto-succession: if the current leader isn't a member any more (died,
        never set, split off elsewhere), the highest-Charisma member left takes
        over, and returns True; otherwise a no-op that returns False -- this never
        overrides a deliberate choice."""
        if self.members and self.leader not in self.members:
            self.leader = max(self.members, key=lambda u: u.mod_charisma)
            return True
        return False

    def set_leader(self, unit):
        """Hand leadership to `unit` -- free, any time, as long as they're
        already a member (a group is a physical thing; leading it from
        elsewhere makes no sense)."""
        if unit not in self.members:
            raise ValueError("leader must be a member of the group")
        if self.fight_due:
            raise ValueError("can't change leaders with a fight about to start")
        self.leader = unit

    @property
    def capacity(self):
        """Members this group's leader can hold as one coalition before
        cohesion starts to suffer -- `BASE_CAPACITY` + the leader's Charisma
        modifier + half their racial level."""
        if not self.leader:
            return BASE_CAPACITY
        return BASE_CAPACITY + self.leader.mod_charisma + (self.leader.racial_level // 2)

    @property
    def herd_capacity(self):
        """How much herd the leader can control -- `HERD_BASE` + their Wisdom
        modifier. Each animal costs its species' `herd_weight`."""
        if not self.leader:
            return HERD_BASE
        return max(1, HERD_BASE + self.leader.mod_wisdom)

    @property
    def herd_load(self):
        return sum(a.herd_weight for a in self.herd)

    def can_take(self, animal):
        return self.herd_load + animal.herd_weight <= self.herd_capacity

    def boarding(self):
        """Who rides which wagon, `{wagon uid: [unit]}`. A wagon seats people by
        weight: each one counts as their body plus everything they carry, against
        what the wagon draws less its own cargo. The slowest are seated first, onto
        the wagon with the most room left; whoever does not fit walks."""
        room = {w.uid: w.budget - w.stash.load for w in self.wagons}
        seats = {w.uid: [] for w in self.wagons}
        for unit in sorted(self.members, key=lambda u: u.speed):
            weight = unit.ride_weight
            uid = max(room, key=room.get, default=None)
            if uid is not None and room[uid] >= weight:
                seats[uid].append(unit)
                room[uid] -= weight
        return seats

    @property
    def riders(self):
        return [u for seated in self.boarding().values() for u in seated]

    @property
    def speed(self):
        """Meters the group covers in one move: the slowest walker (their combat
        speed, armor and load included) or animal, harnessed or not. Whoever rides
        a wagon goes at the pace of the animals pulling it."""
        riding = self.riders
        return min([u.speed * METERS_PER_SQUARE for u in self.members if u not in riding]
                   + [a.speed for a in self.herd], default=0)

    @property
    def overextension(self):
        """How far past `capacity` this group is right now. Costs every
        member Mental Defense (see `Unit._derive_ac`) rather than blocking
        recruitment/merges outright -- the guild can still grow, it just gets
        easier to rattle."""
        return max(0, len(self.members) - self.capacity)

    def distribute_load(self, share_coins=True):
        """Rebalances the unlocked pack items of the members, the pack animals and
        the wagons by free carrying capacity -- see `unit.distribute_load`."""
        from . import unit
        unit.distribute_load(self.members, share_coins, creatures=[*self.herd, *self.wagons])

    # ------------------------------------------------------------------ #
    # logistics: the band's answer to "can we move" / "are we fed" --   #
    # each member already tracks its own `load`/`rations` (unit.py);    #
    # these just total them for a band-wide readout.                    #
    # ------------------------------------------------------------------ #
    @property
    def total_load(self):
        """Combined carry weight across every member."""
        return sum(u.load for u in self.members)

    @property
    def total_carry_normal(self):
        """Combined normal-carry threshold across every member -- pairs with
        `total_load` for a band-wide load bar (`carry_max` is the harder,
        soft-blocked ceiling per member; summing it too would flatter an
        unevenly-loaded group, so it's left per-member)."""
        return sum(u.carry_normal for u in self.members)

    @property
    def rations(self):
        """Meals sitting in the group's packs -- the shared larder every
        member here can draw from (see `Guild._shared_larder`)."""
        return sum(u.rations for u in self.members) + self.carried_rations

    @property
    def rations_days(self):
        """Whole days this larder covers if every member here eats once a
        day. Rounds down: 0 means someone goes hungry today without a
        resupply, even if the group is carrying a few spare meals."""
        if not self.members:
            return 0
        return self.rations // len(self.members)


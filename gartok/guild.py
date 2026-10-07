"""The guild: the player's organisation.

The guild is the **shared** state across every member -- the campaign tallies
(`battles_won`), standing with each faction, the campaign clock, the bank chest,
the taverna pool -- plus the full membership. Physical state (who is where, who
is travelling together) belongs to `Group` (see `group.py`): `Guild.groups` is a
list of `Group`, and every member is in exactly one of them, even if that group
has just the one member. `Guild.roster` is a read view flattened across every
group; `Guild.node` is a single-group convenience over the first group (see the
property below) and stops making sense once a second group exists.

The guild also has one **leader** -- "who am I" (chosen at the draft; see
`draft_screen.py`), the identity the player answers to before anyone else. It
is a *run-unique* title, not scoped to a group. It auto-succeeds by Charisma
the instant it stops being a living roster member (`_sync_leadership`), same as
a `Group`'s own leader (`group.py`) -- but a *deliberate* swap
(`Guild.set_leader`) only works once per run (`leader_swaps_used`); after that,
only death reshuffles it. Every mutation that can change who leads what
(`add_member`, `remove_members`, `split_group`, `merge_groups`, and `__init__`
itself) ends by calling `_sync_leadership`, which also folds each group's
`overextension` into its members' Mental Defense.

The guild also has a chosen **identity** -- `name`, `banner_color`, `banner_icon`
-- set at the draft (`draft_screen.py`'s "identity" phase) purely for flavour:
`app.py` feeds `banner_color` to `ui.banner.set_player_color` so every unit token
in the game renders in it. A guild from before this existed falls back to
`DEFAULT_BANNER_COLOR`/`DEFAULT_BANNER_ICON` below.

What the guild owns as a body lives in `holdings.py`: the **bank chest**
(`bank`, a `Stash` rented from the Bankers in the City -- capacity 0 means no
chest yet; `bank_screen` rents it and moves gear in and out) and the **City
property** (`house`, a `CityProperty` bought from the Bankers; see
[[gartok-property-two-paths]] and `city_property_screen.py`), taxed on a cycle
(`_city_property_upkeep`, called from `_daily_upkeep` below). Missing enough
cycles (`house.missed_payments`) offers a choice next visit: return it
(`repossess_city_property`, banking `bankers_debt`) or squat
(`house.squat`, drawing periodic guard raids -- `campaign.py`'s "eviction"
pause). Outstanding debt escalates to the guard the same way an ignored rap
sheet does (`justice.py`) once `CITY_PROPERTY_DEBT_GRACE_DAYS` passes with
nothing paid.

A **garrison** is a `Group` parked on a standing `"garrison"` order
(`orders.py`) instead of asking for fresh ones -- `_garrison_upkeep` (also
called from `_daily_upkeep`) banks its job's daily output into
`garrison_stock`, keyed by node id, generic across any future property.

The **Wilds claim** (`wilds_claim_stage`, one of `WILDS_CLAIM_STAGES`, at
`world.WILDS_TERRITORY_NODE`) is the guild's own territory, worked toward
through `wilds_claim_screen.WildsClaimScreen`: scout, clear the land (a real
fight), raise fences (consumes `wilds_claim_fence_lumber`, hauled in by hand),
sweep the region (a second fight), then hold a garrison there for
`economy.WILDS_CLAIM_SUSTAIN_DAYS` (`_wilds_claim_sustain_tick`, called from
`_daily_upkeep`) -- interrupted by a raid (`campaign.resolve_wilds_raid`) or
just pulling the garrison out early, either of which resets the countdown,
never the stages already done.

Once `ESTABLISHED`, `wilds_claim_owner` ("guild" | "seized") is Sistema 4's
own ownership flag: the same periodic roll that raided a `SUSTAINING`
garrison can now seize the claim outright instead (`campaign.
_wilds_claim_seizure_check` -- ungarrisoned, no fight at all; garrisoned, a
real one, `campaign.resolve_wilds_seizure`), and a seized claim is won back
by simply travelling there and beating the occupiers
(`campaign.resolve_wilds_claim_retake`) -- never a redo of the stages above.

`reputation` is `{faction_id: score}` and moves only when a `factions.Deed` is
completed (banked in `deeds_done`); there is no per-win grind. `arena_reputation`
is a shortcut for `reputation["arena"]` -- `world.arena_offers` reads it to
decide which (non-lethal, paid) fights the guild may take on.

The guild also carries the taverna's current crop of strangers (`taverna_pool`)
so they stay the same face-to-face across visits; `recruit.refresh_pool` swaps
them for a new set once a week.

`jailed` is the same trick applied to anyone serving time with the City guard
(`justice.py`): a `[(Unit, released_day), ...]` list, off every `Group` but
still on the roster's books, so upkeep and saves keep seeing it. Freed by
`justice.release_due`, called once a day from `_daily_upkeep` below.
"""

from . import cohesion, economy
from .clock import Clock
from .group import BASE_SLOTS, FAME_PER_SLOT, Group
from .guild_claim import (
    WILDS_CLAIM_STAGES,  # noqa: F401 -- re-exported
    WildsClaimMixin,
)
from .guild_holdings import HoldingsMixin
from .guild_labor import LaborMixin
from .guild_upkeep import UpkeepMixin
from .holdings import CityProperty, Garage, Stash
from .tutorial import TutorialState

# Fallbacks for a guild with no chosen identity (old saves, from before the
# draft's naming/banner step existed). Plain data, not `artwork`
# imports -- this module stays pygame-free; the presentation layer resolves
# these slugs/colours (`ui.banner.BANNER_COLORS`, `artwork.BANNER_ICONS`).
DEFAULT_BANNER_COLOR = (94, 156, 214)   # same value as ui.banner.DEFAULT_COLOR
DEFAULT_BANNER_ICON = "shield-bash"     # artwork.BANNER_ICONS[0]


class Guild(HoldingsMixin, WildsClaimMixin, UpkeepMixin, LaborMixin):
    def __init__(self, roster, battles_won=0, reputation=None, deeds_done=None,
                 arena_challenge_day=None, clock=None, node=None,
                 taverna_week=None, taverna_pool=None, taverna_blocked=None,
                 bank=None, groups=None,
                 leader=None, leader_swaps_used=0,
                 name="", banner_color=None, banner_icon=None, tutorial=None,
                 market_stock=None, market_cash=None, missions=None,
                 total_spent=0, items_sold_kinds=None, jailed=None,
                 prison_week=None, prison_pool=None, prison_blocked=None,
                 house=None, bankers_debt=0,
                 bankers_debt_since=None, garrison_stock=None,
                 wilds_claim_stage="NONE", wilds_claim_fence_lumber=0,
                 wilds_claim_sustain_days_left=None, wilds_claim_owner=None,
                 wilds_claim_campfire=False, claim_garage=None,
                 ancient_ruins_discovered=False, leaving=None):
        # `groups` (a list[Group]) wins when given (persist's new save shape);
        # else `roster`/`node` build the one starting group (draft, old saves,
        # every existing test call site) -- the guild leader, if given, also
        # leads that first group (the draft's founding leader is naturally in
        # charge of the one group there is to lead).
        self.groups = groups if groups is not None else [Group(roster, node=node, leader=leader)]
        self.battles_won = battles_won
        self.reputation = dict(reputation or {})   # {faction_id: score}, moved by deeds only
        self.deeds_done = list(deeds_done or [])   # ids of completed factions.Deed
        self.arena_challenge_day = arena_challenge_day  # day a title defense falls due, or None (arena.py)
        self.clock = clock or Clock()
        self.bank = bank if bank is not None else Stash()   # the rented strongbox; capacity 0 = none rented
        # live market stock (economy.STOCK) -- a name absent here restocks freely
        self.market_stock = dict(economy.STOCK) if market_stock is None else dict(market_stock)
        # what each market can still pay for goods, keyed by node id; a node absent here
        # holds `economy.MARKET_CASH_START`
        self.market_cash = dict(market_cash or {})
        self.missions = list(missions or [])  # active/finished missions.Mission, see missions.py
        # lifetime market tallies the Bankers' deeds read straight off the guild
        # (`factions.py`), rather than off a single "market" event's payload
        self.total_spent = total_spent               # copper ever paid to the market
        self.items_sold_kinds = set(items_sold_kinds or ())  # distinct item names ever sold
        # the taverna's strangers, re-rolled weekly by `recruit.refresh_pool`
        self.taverna_week = taverna_week      # week index the pool was rolled for, or None
        self.taverna_pool = taverna_pool      # list[Unit] on offer, or None (roll on first visit)
        self.taverna_blocked = taverna_blocked if taverna_blocked is not None else []
        #   ^ [[candidate_uid, recruiter_uid], ...] pitches already failed this week
        
        # the prison's strangers (bail & recruit), re-rolled weekly by `recruit.refresh_prison_pool`
        self.prison_week = prison_week
        self.prison_pool = prison_pool
        self.prison_blocked = prison_blocked if prison_blocked is not None else []
        
        self.jailed = list(jailed or [])      # [(Unit, released_day), ...] -- see the docstring above
        # the City property -- see the docstring above and economy.CITY_PROPERTY_*
        self.house = house if house is not None else CityProperty()
        self.bankers_debt = bankers_debt                 # copper owed after a repossession
        self.bankers_debt_since = bankers_debt_since     # clock.day the debt started (grace window)
        # a garrisoned group's job output, keyed by the node it's parked on --
        # generic across any future property (economy.GARRISON_JOBS, world.Node.garrison_job)
        self.garrison_stock = {k: list(v) for k, v in (garrison_stock or {}).items()}
        # the Wilds claim campaign -- see the class docstring and WILDS_CLAIM_STAGES above
        self.wilds_claim_stage = wilds_claim_stage
        self.wilds_claim_fence_lumber = wilds_claim_fence_lumber
        self.wilds_claim_sustain_days_left = wilds_claim_sustain_days_left   # only meaningful while SUSTAINING
        self.wilds_claim_owner = wilds_claim_owner   # None before ESTABLISHED, else "guild" | "seized" (Sistema 4)
        self.wilds_claim_campfire = wilds_claim_campfire   # a fire is built at the claim: cooking is unlocked there
        self.claim_garage = claim_garage or Garage(unlimited=True)   # wagons and animals parked at the claim
        self.leaving = dict(leaving or {})    # {uid: day the notice lapses} -- see cohesion.py
        self.leader = leader                  # the guild's "who am I" -- None resolves below
        self.leader_swaps_used = leader_swaps_used   # 0 or 1: the one free deliberate change
        self.name = name or ""                # chosen at the draft; "" shows as "The Guild"
        self.banner_color = tuple(banner_color) if banner_color else DEFAULT_BANNER_COLOR
        self.banner_icon = banner_icon or DEFAULT_BANNER_ICON
        # the tutorial's dismissed/enabled state (tutorial.py) -- carried on
        # the guild so it saves and loads by slot, like everything else here;
        # the draft (before a Guild exists) keeps its own until `app._draft_done`
        # hands it in
        self.ancient_ruins_discovered = ancient_ruins_discovered
        self.tutorial = tutorial if tutorial is not None else TutorialState()
        self._sync_leadership()

    def market_cash_at(self, node_id):
        return self.market_cash.get(node_id, economy.MARKET_CASH_START)

    def move_market_cash(self, node_id, delta):
        self.market_cash[node_id] = max(0, self.market_cash_at(node_id) + delta)

    # ------------------------------------------------------------------ #
    # the roster: a flattened read view across every group                #
    # ------------------------------------------------------------------ #
    @property
    def roster(self):
        return [u for g in self.groups for u in g.members]

    def group_of(self, unit):
        """The `Group` holding `unit`, or None if it isn't on the roster."""
        for g in self.groups:
            if unit in g.members:
                return g
        return None

    # ------------------------------------------------------------------ #
    # leadership: the guild's "who am I", and each group's own leader     #
    # ------------------------------------------------------------------ #
    def set_leader(self, unit):
        """A deliberate change of who the guild answers to -- unlike a
        `Group`'s leader, this costs the run's one free swap
        (`leader_swaps_used`); once spent, only death reshuffles it."""
        if unit not in self.roster:
            raise ValueError("guild leader must be a roster member")
        if unit is self.leader:
            return
        if self.leader_swaps_used >= 1:
            raise ValueError("no free guild leader change left")
        self.leader = unit
        self.leader_swaps_used += 1

    def set_group_leader(self, group, unit):
        """`Group.set_leader` plus what a new leader changes at once: a herd they
        cannot control starts its notice now. Returns the events."""
        group.set_leader(unit)
        events = cohesion.herd_notices(self)
        self._sync_leadership()
        return events

    def _sync_leadership(self):
        """Re-run after anything that can change who leads what: auto-succeeds
        the guild leader (by Charisma) if they're no longer on the roster,
        does the same per group (`Group.ensure_leader`), then folds each
        group's `overextension` into its members' Mental Defense
        (`Unit._derive_ac` reads `unit.group_overextension`)."""
        if self.roster and self.leader not in self.roster:
            self.leader = max(self.roster, key=lambda u: u.mod_charisma)
        changed = [g.ensure_leader() for g in self.groups]     # every group, so no short-circuit
        if any(changed):
            cohesion.herd_notices(self)
        for g in self.groups:
            n = g.overextension
            for u in g.members:
                if u.group_overextension != n:
                    u.group_overextension = n
                    u._derive_combat()

    # ------------------------------------------------------------------ #
    # fame -> how many groups the guild can run at once                   #
    # ------------------------------------------------------------------ #
    @property
    def fame(self):
        """How widely known the guild is: every faction's reputation, summed."""
        return sum(max(0, r) for r in self.reputation.values())

    @property
    def group_slots(self):
        return BASE_SLOTS + self.fame // FAME_PER_SLOT

    @property
    def free_slots(self):
        return max(0, self.group_slots - len(self.groups))

    @property
    def fame_to_next_slot(self):
        return FAME_PER_SLOT - self.fame % FAME_PER_SLOT

    def can_absorb(self, group):
        """True if one more member in `group` would not leave it overextended
        with nowhere to split them to."""
        if group is None:
            return True
        return len(group.members) < group.capacity or self.free_slots > 0

    def add_member(self, unit, group):
        group.members.append(unit)
        self._sync_leadership()

    def remove_members(self, units):
        """Drop each of `units` from whichever group holds it (permadeath /
        starvation), pruning any group this empties out entirely (no ghost
        tokens left standing on the map). A unit not found on any group is
        silently skipped."""
        dead = set(units)
        for g in list(self.groups):
            if any(u in dead for u in g.members):
                g.members = [u for u in g.members if u not in dead]
                if g.empty:
                    self.groups.remove(g)
        self._sync_leadership()

    def split_group(self, group, members, *, name=None, wagons=(), herd=()):
        """Peel `members` (a subset of `group.members`) off into a brand new
        `Group` at the same node -- physically valid because they haven't gone
        anywhere yet. `group` keeps whoever is left; it is pruned if that leaves
        it empty (everyone moved to the new group). Refuses to empty `group`
        entirely if that would leave the new group as EVERYONE (nothing to
        split) or to peel off a group mid-order (its members aren't all in one
        place right now conceptually until the order resolves) -- except a
        standing `"garrison"` order (`Group.locked`), which never resolves by
        design and doesn't move anyone. `wagons` and `herd` (a subset of the
        group's own) go with the new group; a moved animal stays hitched only if
        its wagon came too."""
        peel = [u for u in group.members if u in set(members)]
        if not peel or len(peel) == len(group.members):
            raise ValueError("split needs a non-empty, proper subset of the group")
        if group.locked:
            raise ValueError("can't split a group with an order in flight")
        if not self.free_slots:
            raise ValueError("no free group slot -- the guild is not famous enough to run another")
        new_group = Group(peel, node=group.node, name=name)
        moved_herd = [a for a in group.herd if a in herd]
        if sum(a.herd_weight for a in moved_herd) > new_group.herd_capacity:
            raise ValueError(f"the herd would outgrow what {new_group.leader.name} can control "
                             f"({new_group.herd_capacity})")
        group.members = [u for u in group.members if u not in peel]
        for wagon in [w for w in group.wagons if w in wagons]:
            group.wagons.remove(wagon)
            new_group.add_wagon(wagon)
        for animal in moved_herd:
            group.herd.remove(animal)
            new_group.herd.append(animal)
            if new_group.pulling(animal) is None:
                animal.hitch = None
        group.hitch_idle()
        new_group.hitch_idle()
        self.groups.append(new_group)
        self._sync_leadership()
        return new_group

    def merge_groups(self, a, b):
        """Fold `b` into `a` -- only valid when they're standing on the same
        node (a group is a physical thing; merging elsewhere would teleport
        someone). Removes `b` from the guild. Returns `a`. A standing
        `"garrison"` order on either side is not a blocker (`Group.locked`) --
        only an order that actually moves or occupies someone is."""
        if a.node != b.node:
            raise ValueError("can only merge groups standing on the same node")
        if a.locked or b.locked:
            raise ValueError("can't merge a group with an order in flight")
        if a.herd_load + b.herd_load > a.herd_capacity:
            raise ValueError(f"the herd would outgrow what {a.leader.name} can control ({a.herd_capacity})")
        for wagon in list(b.wagons):
            b.remove_wagon(wagon)
            a.add_wagon(wagon)
        a.herd += b.herd
        a.hitch_idle()
        a.members += b.members
        self.groups.remove(b)
        self._sync_leadership()
        return a

    def __len__(self):
        return len(self.roster)

    @property
    def empty(self):
        return not self.roster

    @property
    def needs_orders(self):
        """True while some group is idle and waiting on the player to send it
        somewhere -- the map should stop there instead of running the clock."""
        return any(not g.busy for g in self.groups if not g.empty)

    @property
    def can_auto_advance(self):
        """Nothing needs the player right now, but at least one group still
        has an order in flight -- keep the clock running on its own instead
        of waiting on a click."""
        return not self.needs_orders and any(g.busy and g.order.kind != "garrison" for g in self.groups)

    @property
    def arena_reputation(self):
        """Standing with the Pits -- what `world.arena_offers` gates the stake
        tiers on. Rises only when an arena `factions.Deed` is completed."""
        return self.reputation.get("arena", 0)

    @property
    def money(self):
        """Total $ across the roster (the guild has no purse of its own)."""
        return sum(u.money for u in self.roster)

    def record_victory(self):
        self.battles_won += 1

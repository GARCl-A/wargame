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
`app.py` feeds `banner_color` to `theme.set_player_color` so every unit token
in the game renders in it. A guild from before this existed falls back to
`DEFAULT_BANNER_COLOR`/`DEFAULT_BANNER_ICON` below.

The one thing the guild owns as a body is the **bank chest** -- a strongbox
rented from the Bankers in the City (`bank_capacity` kg, `bank_items` the names
stashed). `bank_capacity == 0` means no chest yet; `bank_screen` rents it and
moves gear in and out.

The guild may also own a **City property** -- a house bought from the Bankers
(`property_city_unlocked`, `property_city_items`; see [[gartok-property-two-paths]]
and `city_property_screen.py`), taxed on a cycle (`_city_property_upkeep`,
called from `_daily_upkeep` below). Missing enough cycles
(`property_city_missed_payments`) offers a choice next visit: return it
(`repossess_city_property`, banking `bankers_debt`) or squat
(`squat_city_property`, drawing periodic guard raids -- `campaign.py`'s
"eviction" pause). Outstanding debt escalates to the guard the same way an
ignored rap sheet does (`justice.py`) once `CITY_PROPERTY_DEBT_GRACE_DAYS`
passes with nothing paid.

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

from . import data, economy, justice, magic, missions, progression, world
from .clock import Clock
from .group import Group
from .tutorial import TutorialState

# Fallbacks for a guild with no chosen identity (old saves, from before the
# draft's naming/banner step existed). Plain data, not `theme`/`artwork`
# imports -- this module stays pygame-free; the presentation layer resolves
# these slugs/colours (`theme.BANNER_COLORS`, `artwork.BANNER_ICONS`).
DEFAULT_BANNER_COLOR = (94, 156, 214)   # same value as theme.PLAYER_C's own default
DEFAULT_BANNER_ICON = "shield-bash"     # artwork.BANNER_ICONS[0]

# The Wilds claim's own stage machine (see the class docstring, economy.WILDS_CLAIM_*).
WILDS_CLAIM_STAGES = ("NONE", "SCOUTED", "CLEARED", "FENCED", "SWEPT", "SUSTAINING", "ESTABLISHED")


class Guild:
    def __init__(self, roster, battles_won=0, reputation=None, deeds_done=None,
                 arena_challenge_day=None, clock=None, node=None,
                 taverna_week=None, taverna_pool=None, taverna_blocked=None,
                 bank_capacity=0, bank_items=None, groups=None,
                 leader=None, leader_swaps_used=0,
                 name="", banner_color=None, banner_icon=None, tutorial=None,
                 market_stock=None, missions=None,
                 total_spent=0, items_sold_kinds=None, jailed=None,
                 prison_week=None, prison_pool=None, prison_blocked=None,
                 property_city_unlocked=False, property_city_items=None,
                 property_city_tax_due_day=None, property_city_missed_payments=0,
                 property_city_squatting=False, bankers_debt=0,
                 property_city_debt_since=None, garrison_stock=None,
                 wilds_claim_stage="NONE", wilds_claim_fence_lumber=0,
                 wilds_claim_sustain_days_left=None, wilds_claim_owner=None):
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
        self.bank_capacity = bank_capacity    # kg the rented strongbox holds (0 = none rented)
        self.bank_items = list(bank_items or [])   # item names stashed in the chest
        # live market stock (economy.STOCK) -- a name absent here restocks freely
        self.market_stock = dict(economy.STOCK) if market_stock is None else dict(market_stock)
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
        self.property_city_unlocked = property_city_unlocked
        self.property_city_items = list(property_city_items or [])
        self.property_city_tax_due_day = property_city_tax_due_day   # clock.day the next tax is due, or None
        self.property_city_missed_payments = property_city_missed_payments
        self.property_city_squatting = property_city_squatting       # illegal occupier, after refusing repossession
        self.bankers_debt = bankers_debt                              # copper owed after a repossession
        self.property_city_debt_since = property_city_debt_since     # clock.day the debt started (grace window)
        # a garrisoned group's job output, keyed by the node it's parked on --
        # generic across any future property (economy.GARRISON_JOBS, world.Node.garrison_job)
        self.garrison_stock = {k: list(v) for k, v in (garrison_stock or {}).items()}
        # the Wilds claim campaign -- see the class docstring and WILDS_CLAIM_STAGES above
        self.wilds_claim_stage = wilds_claim_stage
        self.wilds_claim_fence_lumber = wilds_claim_fence_lumber
        self.wilds_claim_sustain_days_left = wilds_claim_sustain_days_left   # only meaningful while SUSTAINING
        self.wilds_claim_owner = wilds_claim_owner   # None before ESTABLISHED, else "guild" | "seized" (Sistema 4)
        self.leader = leader                  # the guild's "who am I" -- None resolves below
        self.leader_swaps_used = leader_swaps_used   # 0 or 1: the one free deliberate change
        self.name = name or ""                # chosen at the draft; "" shows as "The Guild"
        self.banner_color = tuple(banner_color) if banner_color else DEFAULT_BANNER_COLOR
        self.banner_icon = banner_icon or DEFAULT_BANNER_ICON
        # the soft tutorial's dismissed/enabled state (tutorial.py) -- carried on
        # the guild so it saves and loads by slot, like everything else here;
        # the draft (before a Guild exists) keeps its own until `app._draft_done`
        # hands it in
        self.tutorial = tutorial if tutorial is not None else TutorialState()
        self._sync_leadership()

    # ------------------------------------------------------------------ #
    # the roster: a flattened read view across every group                #
    # ------------------------------------------------------------------ #
    @property
    def roster(self):
        return [u for g in self.groups for u in g.members]

    @roster.setter
    def roster(self, units):
        """Single-group convenience: valid only with exactly one group
        (replaces its whole membership wholesale) -- every real mutation
        should go through `add_member`/`remove_members` instead, which stay
        correct once a second group exists."""
        if len(self.groups) != 1:
            raise NotImplementedError(
                "guild.roster assignment needs exactly one group; "
                "use add_member/remove_members instead")
        self.groups[0].members = list(units)

    @property
    def node(self):
        """Single-group convenience over the first group's position. Ambiguous
        (and unused) once a second group exists -- read `group.node` instead."""
        return self.groups[0].node

    @node.setter
    def node(self, value):
        self.groups[0].node = value

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

    def _sync_leadership(self):
        """Re-run after anything that can change who leads what: auto-succeeds
        the guild leader (by Charisma) if they're no longer on the roster,
        does the same per group (`Group.ensure_leader`), then folds each
        group's `overextension` into its members' Mental Defense
        (`Unit._derive_ac` reads `unit.group_overextension`)."""
        if self.roster and self.leader not in self.roster:
            self.leader = max(self.roster, key=lambda u: u.mod_charisma)
        for g in self.groups:
            g.ensure_leader()
        for g in self.groups:
            n = g.overextension
            for u in g.members:
                if u.group_overextension != n:
                    u.group_overextension = n
                    u._derive_combat()

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

    def split_group(self, group, members, *, name=None):
        """Peel `members` (a subset of `group.members`) off into a brand new
        `Group` at the same node -- physically valid because they haven't gone
        anywhere yet. `group` keeps whoever is left; it is pruned if that leaves
        it empty (everyone moved to the new group). Refuses to empty `group`
        entirely if that would leave the new group as EVERYONE (nothing to
        split) or to peel off a group mid-order (its members aren't all in one
        place right now conceptually until the order resolves) -- except a
        standing `"garrison"` order (`Group.locked`), which never resolves by
        design and doesn't move anyone."""
        peel = [u for u in group.members if u in set(members)]
        if not peel or len(peel) == len(group.members):
            raise ValueError("split needs a non-empty, proper subset of the group")
        if group.locked:
            raise ValueError("can't split a group with an order in flight")
        group.members = [u for u in group.members if u not in peel]
        new_group = Group(peel, node=group.node, name=name)
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
        return not self.needs_orders and any(g.busy for g in self.groups)

    @property
    def arena_reputation(self):
        """Standing with the Pits -- what `world.arena_offers` gates the stake
        tiers on. Rises only when an arena `factions.Deed` is completed."""
        return self.reputation.get("arena", 0)

    @property
    def bank_unlocked(self):
        """True once the guild has rented a strongbox from the Bankers."""
        return self.bank_capacity > 0

    @property
    def bank_load(self):
        """Weight of everything stashed in the bank chest."""
        return sum(data.item_weight(it) for it in self.bank_items)

    def rent_bank_chest(self):
        """Take up the Bankers' offer: the guild's first strongbox. The caller
        collects the fee first -- this only flips the capacity on."""
        self.bank_capacity = economy.BANK_CHEST_CAPACITY

    # ------------------------------------------------------------------ #
    # the City property (see the class docstring, economy.CITY_PROPERTY_*) #
    # ------------------------------------------------------------------ #
    @property
    def property_city_load(self):
        return sum(data.item_weight(it) for it in self.property_city_items)

    @property
    def bankers_services_blocked(self):
        """Outstanding debt shuts the Bankers' doors -- no new strongbox, no
        buying the property (back) -- until it's paid off."""
        return self.bankers_debt > 0

    def buy_city_property(self):
        """Take up the Bankers' offer on a house. The caller collects the
        price first -- this only flips ownership on and starts the tax clock."""
        self.property_city_unlocked = True
        self.property_city_missed_payments = 0
        self.property_city_tax_due_day = self.clock.day + economy.CITY_PROPERTY_TAX_PERIOD_DAYS

    @property
    def property_city_repossession_due(self):
        """True once missed cycles hit the limit -- `app` shows the choice
        screen instead of the normal property screen on the next visit."""
        return (self.property_city_unlocked
                and self.property_city_missed_payments >= economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT)

    def repossess_city_property(self):
        """ACCEPT: hand the property back, bank the missed rent as debt owed
        to the Bankers -- their services stay shut until it's paid."""
        owed = self.property_city_missed_payments * economy.CITY_PROPERTY_TAX
        self.property_city_unlocked = False
        self.property_city_items = []
        self.property_city_missed_payments = 0
        self.property_city_tax_due_day = None
        self.bankers_debt += owed
        self.property_city_debt_since = self.clock.day

    def squat_city_property(self):
        """REFUSE: the guild keeps the house as an illegal occupier -- no more
        tax to pay, but the guard now raids it periodically
        (`campaign._property_raid_catch`) until it wins or the guild gives up
        (`abandon_city_squat`)."""
        self.property_city_squatting = True
        self.property_city_missed_payments = 0
        self.property_city_tax_due_day = None

    def abandon_city_squat(self):
        """Give up a squat before the guard forces the issue -- the property
        is simply gone, no debt (nothing was ever paid back on it)."""
        self.property_city_squatting = False
        self.property_city_unlocked = False
        self.property_city_items = []

    # ------------------------------------------------------------------ #
    # the garrison: a Group parked on a "garrison" order, working a job    #
    # ------------------------------------------------------------------ #
    def garrison_stock_at(self, node_id):
        return self.garrison_stock.get(node_id, [])

    def _garrison_upkeep(self):
        """Once a day: every group parked on a `"garrison"` order banks its
        job's output into `garrison_stock`, keyed by the node it's standing
        on. A node whose `garrison_job` doesn't match the order's own `job`
        (or offers none at all -- true of every node today, see
        `world.Node.garrison_job`) produces nothing; the group still sits
        there, fed by the normal per-group upkeep, just not working."""
        events = []
        for g in self.groups:
            if g.empty or g.order is None or g.order.kind != "garrison":
                continue
            node = world.node(g.node)
            if node.garrison_job != g.order.job:
                continue

            if g.order.job == "study":
                for u in g.members:
                    event = magic.progress_study(u)
                    if event:
                        events.append(event)
                continue

            item = economy.GARRISON_JOBS.get(g.order.job)
            if item is None:
                continue
            count = economy.GARRISON_YIELD_PER_MEMBER_PER_DAY * len(g.members)
            self.garrison_stock.setdefault(g.node, []).extend([item] * count)
            events.append(f"{node.name}: the garrison gathers {count} {item}.")
        return events

    # ------------------------------------------------------------------ #
    # the Wilds claim campaign (see the class docstring, economy.WILDS_CLAIM_*) #
    # ------------------------------------------------------------------ #
    def wilds_claim_scout(self):
        self.wilds_claim_stage = "SCOUTED"

    def wilds_claim_mark_cleared(self):
        self.wilds_claim_stage = "CLEARED"

    def wilds_claim_deposit_lumber(self, n):
        self.wilds_claim_fence_lumber += n

    def wilds_claim_build_fences(self):
        self.wilds_claim_fence_lumber -= economy.WILDS_CLAIM_FENCE_LUMBER
        self.wilds_claim_stage = "FENCED"

    def wilds_claim_mark_swept(self):
        self.wilds_claim_stage = "SWEPT"

    def wilds_claim_start_sustaining(self):
        self.wilds_claim_stage = "SUSTAINING"
        self.wilds_claim_sustain_days_left = economy.WILDS_CLAIM_SUSTAIN_DAYS

    def _wilds_claim_garrisoned(self):
        """True while some living group is actually parked, garrisoning, at
        the claim node right now."""
        return any(g.order is not None and g.order.kind == "garrison"
                   and g.node == world.WILDS_TERRITORY_NODE and not g.empty
                   for g in self.groups)

    def _wilds_claim_sustain_tick(self):
        """Once a day, while `SUSTAINING`: the countdown only advances for a
        day the claim was actually garrisoned the whole time through -- no
        partial credit, same "start the clock over" rule
        `campaign.resolve_wilds_raid` applies to a raid the garrison loses.
        Pulling the garrison out early (a fresh order, not a lost fight) has
        the same effect -- sustaining only counts while someone is there."""
        if self.wilds_claim_stage != "SUSTAINING":
            return []
        if not self._wilds_claim_garrisoned():
            if self.wilds_claim_sustain_days_left != economy.WILDS_CLAIM_SUSTAIN_DAYS:
                self.wilds_claim_sustain_days_left = economy.WILDS_CLAIM_SUSTAIN_DAYS
                return ["The Wilds claim sits unguarded -- sustaining it starts over."]
            return []
        self.wilds_claim_sustain_days_left -= 1
        if self.wilds_claim_sustain_days_left <= 0:
            self.wilds_claim_stage = "ESTABLISHED"
            self.wilds_claim_sustain_days_left = None
            self.wilds_claim_owner = "guild"   # Sistema 4: what a seizure/retake actually flips
            return ["The Wilds claim is ESTABLISHED -- the land is the guild's."]
        return []

    def pay_bankers_debt(self, amount):
        """Apply `amount` (already collected by the caller) to `bankers_debt`,
        never past zero. Returns how much was actually owed (<= amount)."""
        paid = min(amount, self.bankers_debt)
        self.bankers_debt -= paid
        if self.bankers_debt == 0:
            self.property_city_debt_since = None
        return paid

    @property
    def hungry(self):
        return [u for u in self.roster if u.hunger_level > 0]

    @property
    def rations(self):
        """Meals in the packs across the whole roster."""
        return sum(u.rations for u in self.roster)

    # ------------------------------------------------------------------ #
    # time + daily upkeep                                                #
    # ------------------------------------------------------------------ #
    def pass_time(self, hours):
        """Advance the campaign clock and run daily upkeep for every day it
        crosses. Returns a list of events (missed meals, deaths) for the caller
        to show. This is the only path that moves the clock by hours -- battle
        time (`clock.advance_rounds`) is seconds and skips upkeep."""
        start_day = self.clock.day
        self.clock.advance_hours(hours)
        events = []
        all_casualties = []
        for _ in range(self.clock.day - start_day):
            e, c = self._daily_upkeep()
            events += e
            all_casualties += c
        
        # Passive healing: every 8h of continuous rest (not busy) heals the unit
        for g in self.groups:
            if not g.busy:
                for u in g.members:
                    if u.hp < u.hp_max or getattr(u, "sick", False):
                        u.consecutive_rest_hours += hours
                        while u.consecutive_rest_hours >= 8:
                            u.consecutive_rest_hours -= 8
                            if getattr(u, "sick", False):
                                u.sick = False
                                events.append(f"{u.name} rests and recovers from their sickness.")
                                u._derive_combat()
                            
                            if u.hp < u.hp_max:
                                heal = max(1, u.racial_level + u.mod_constitution)
                                u.hp = min(u.hp_max, u.hp + heal)
                                events.append(f"{u.name} rests and recovers {heal} HP.")
                                
                            if u.hp == u.hp_max and not getattr(u, "sick", False):
                                u.consecutive_rest_hours = 0
                                break
            else:
                for u in g.members:
                    u.consecutive_rest_hours = 0

        return events, all_casualties

    def _shared_larder(self, eater):
        """The packs `eater` may draw a ration from -- every group-mate
        (physically together, so the only ones who could actually hand over
        food) whose `share_food` is on. Own pack is handled first by the unit
        itself."""
        group = self.group_of(eater)
        mates = group.members if group is not None else self.roster
        return [u._base_inventory for u in mates
                if u is not eater and u.share_food]

    def _rot_food(self, inventory):
        rotten = 0
        new_inv = []
        for item in inventory:
            base_item = item.split(" (")[0]
            if base_item in data.FOOD_LIFESPAN:
                if " (" in item:
                    age = int(item.split(" (")[1].replace("d)", "")) + 1
                else:
                    age = 1
                if age >= data.FOOD_LIFESPAN[base_item]:
                    new_inv.append("Rotten Food")
                    rotten += 1
                else:
                    new_inv.append(f"{base_item} ({age}d)")
            else:
                new_inv.append(item)
        inventory[:] = new_inv
        return rotten

    def _daily_upkeep(self):
        events, casualties, ate = [], [], []
        
        # 1) rot food in everyone's inventory (and the bank chest)
        total_rotten = 0
        for u in self.roster:
            total_rotten += self._rot_food(u._base_inventory)
        total_rotten += self._rot_food(self.bank_items)
        if total_rotten:
            events.append(f"{total_rotten} portions of food rotted away.")

        for u in self.roster:
            if u.has_talent("fruitful"):
                u.give_to_pack("Fruit")
                events.append(f"{u.name} blooms at dawn and yields a fresh Fruit.")
        # Everyone eats from their own pack first (a full pass), so a hungry mate
        # drawing on the shared larder next can't take a ration its owner still
        # needs. Only then does the still-unfed hit the larder / the hunger step.
        ate_own = {u for u in self.roster
                   if u.ability.id != "autotroph" and u._take_ration()}
        for u in self.roster:
            if u in ate_own:
                u.unfed_days, outcome = 0, "ate"
            else:
                outcome = u.consume_daily_food(self._shared_larder(u))
            if outcome == "dead":
                casualties.append(u)
                events.append(f"{u.name} starved to death.")
            elif outcome == "hungry":
                events.append(f"{u.name} did not eat today: {u.hunger_label}.")
            elif outcome == "ate" and u.ability.id != "autotroph":
                ate.append(u)
            u._derive_combat()                 # refresh mods / hp_max for the new hunger
        if ate:
            who = "1 member ate" if len(ate) == 1 else f"{len(ate)} members ate"
            events.append(f"{who} ({self.rations} rations left).")
        if casualties:
            self.remove_members(casualties)
        for m in missions.expire_overdue(self):
            events.append(f"{missions.template_of(m).name}: the deadline passed.")
        for u in justice.release_due(self):
            events.append(f"{u.name} finishes their time and is released in the City.")
        events += self._city_property_upkeep()
        events += self._garrison_upkeep()
        events += self._wilds_claim_sustain_tick()
        return events, casualties

    def _charge_roster(self, amount):
        """Take `amount` copper off the whole roster -- `economy.charge_evenly`
        over everyone rather than one screen's visiting guests."""
        economy.charge_evenly(self.roster, amount)

    def _city_property_upkeep(self):
        """Run once a day (from `_daily_upkeep`): collect the property tax
        when it falls due, and escalate long-ignored Bankers debt to the
        guard -- same crime/guard pipeline `justice.py` already runs, so a
        deadbeat guild eventually gets caught the normal way, not a bespoke
        one. No-op with no property and no debt (the common case)."""
        events = []
        if self.property_city_unlocked and self.clock.day >= (self.property_city_tax_due_day or 0):
            self.property_city_tax_due_day = self.clock.day + economy.CITY_PROPERTY_TAX_PERIOD_DAYS
            if self.gold >= economy.CITY_PROPERTY_TAX:
                self._charge_roster(economy.CITY_PROPERTY_TAX)
                events.append(f"The Bankers collect {economy.CITY_PROPERTY_TAX} copper in property tax.")
            else:
                self.property_city_missed_payments += 1
                events.append("The guild can't cover the property tax -- the Bankers note it.")
        if self.bankers_debt > 0 and self.property_city_debt_since is not None:
            if self.clock.day - self.property_city_debt_since >= economy.CITY_PROPERTY_DEBT_GRACE_DAYS:
                self.property_city_debt_since = self.clock.day     # resets the grace window
                if self.leader is not None:
                    self.leader.crime += 1
                    events.append(f"{self.leader.name}'s unpaid debt to the Bankers "
                                  "reaches the guard's ears.")
        return events

    def eat_now_pass(self):
        """Anyone still hungry eats right now -- own pack, then the group
        larder -- without waiting for the next daily meal. No clock advance
        (the caller runs `pass_time` itself, or is mid-tick already)."""
        fed = [u for u in self.roster if u.eat_now()]          # own packs first
        for u in self.roster:
            if u.hunger_level and u not in fed and u.eat_now(self._shared_larder(u)):
                fed.append(u)
        for u in fed:
            u._derive_combat()
        if not fed:
            return []
        names = ", ".join(u.name for u in fed)
        return [f"Stopped to eat: {names} ({self.rations} rations left)."]

    def do_maintenance(self, hours=1):
        """A camp stop: the guild takes `hours` to see to itself. Advances the
        clock (so a stop that crosses midnight still runs the daily meal) and
        then lets anyone still hungry eat from their pack right now. Returns the
        events to show. Eating is the only chore today; rest / gear repair hang
        off here later."""
        events, casualties = self.pass_time(hours)
        events += self.eat_now_pass()
        if not events:
            events.append("A quiet stop. No one needed to eat.")
        return events, casualties

    def work_speedup(self, crew):
        """The clock-time multiplier a work shift actually takes: 1.0 unless
        someone on `crew` has Brisk Hands, in which case the whole guild moves
        on only once the SLOWEST worker is done -- so the saving lands only
        when nobody on the crew is dragging."""
        if not crew:
            return 1.0
        goblins = sum(1 for u in crew if u.race["name"] == "Goblin")
        mults = []
        for u in crew:
            speed = u.talent_bonus("activity_speed")
            if u.has_talent("swarm_logic"):
                speed += 0.10 * max(0, goblins - 1)
            mults.append(1 - speed)
        return max(mults)

    def work_shift(self, workers, hours):
        """A stint at the lumber yard outside the walls, done right now:
        advances the campaign clock through `pass_time` (a long shift can cross
        midnight and run the daily meal -- a starving worker may not live to be
        paid) and then pays the crew. See `_pay_shift` for the pay/XP step alone
        (used by the tick/orders engine, which advances the clock itself)."""
        hours = int(hours)
        crew = [u for u in workers if u in self.roster]
        clock_hours = hours * self.work_speedup(crew)
        events, casualties = self.pass_time(clock_hours)
        events += self._pay_shift(workers, hours, clock_hours)
        return events, casualties

    def work_property(self, clock_hours, max_charges, work_minutes):
        """Work a city property (forge / tanner / ledger) for `max_charges` or
        until the clock jumps `clock_hours`, whichever hits first. Returns a
        tuple (finished_charges: int, events, casualties). This deliberately
        advances the campaign clock through `pass_time` (a long shift can cross
        midnight and trigger the daily upkeep)."""
        if max_charges <= 0:
            return 0, [], []
        shift_minutes = clock_hours * 60
        charges = min(max_charges, shift_minutes // work_minutes)
        events, casualties = self.pass_time(clock_hours)
        return charges, events, casualties

    def work_wilds_claim(self, clock_hours):
        """Work on the Wilds claim for `clock_hours`. Advances the campaign clock
        through `pass_time`. Returns `(events, casualties)`."""
        events, casualties = self.pass_time(clock_hours)
        return events, casualties

    def _pay_shift(self, workers, hours, clock_hours):
        """Pay + bank work-XP for a completed shift -- no clock advance, the
        caller already ran `pass_time`. `hours` is the nominal shift length
        (what pay/XP are based on); `clock_hours` is how long it actually took
        (Brisk Hands can shrink it), used only for the "done early" note."""
        earners = [u for u in workers if u in self.roster]   # a long shift can starve one
        paid = []
        events = []
        for u in earners:
            old_work_lvl = u.work_level
            level = economy.lumber_level(u)
            pay = economy.lumber_pay(hours, level)
            gain = round(pay * (1 + u.talent_bonus("coin_gain")))
            u.gold += gain
            u.work_hours += progression.work_xp_hours(hours, level, u.work_level)
            u.collect_levels()                 # more work marks can lift the mean level
            paid.append(gain)
            if u.work_level > old_work_lvl:
                events.append(f"{u.name} reached work level {u.work_level}!")
        if earners:
            names = ", ".join(u.name for u in earners)
            wage = (f"+{paid[0]} copper each" if len(set(paid)) == 1
                    else f"+{sum(paid)} copper total")
            note = f"Lumber yard: {names} worked {hours} h ({wage})."
            if clock_hours < hours:
                note += f"  Brisk Hands: crew done in {clock_hours:g} h."
            events.append(note)
        return events

    def crafting_shift(self, unit, recipe, hours):
        """A stint at the forge/workbench, done right now:
        advances the campaign clock through `pass_time` and rolls progress."""
        hours = int(hours)
        if unit.crafting_target != recipe:
            recipe_data = data.CRAFTING_RECIPES.get(recipe)
            if not recipe_data:
                return [f"Unknown recipe {recipe}."], []
            
            # Verify materials
            inv = list(unit._base_inventory)
            missing = False
            for mat in recipe_data["materials"]:
                if mat in inv:
                    inv.remove(mat)
                else:
                    missing = True
                    break
            
            if missing:
                return [f"{unit.name} can't craft {recipe} -- missing materials."], []
                
            # Consume materials
            for mat in recipe_data["materials"]:
                unit._base_inventory.remove(mat)
                
            unit.crafting_target = recipe
            unit.crafting_progress = 0

        clock_hours = hours * self.work_speedup([unit])
        events, casualties = self.pass_time(clock_hours)
        
        progress_total = 0
        done = False
        # One roll per hour
        for _ in range(hours):
            p, done = unit.progress_crafting()
            progress_total += p
            if done:
                break
                
        if done:
            events.append(f"{unit.name} finished crafting: {recipe}!")
        else:
            events.append(f"{unit.name} worked on {recipe} for {hours}h (+{progress_total} progress).")
            
        return events, casualties

    @property
    def gold(self):
        """Total copper across the roster (the guild has no purse of its own)."""
        return sum(u.gold for u in self.roster)

    def record_victory(self):
        self.battles_won += 1

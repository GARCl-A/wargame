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

`reputation` is `{faction_id: score}` and moves only when a `factions.Deed` is
completed (banked in `deeds_done`); there is no per-win grind. `arena_reputation`
is a shortcut for `reputation["arena"]` -- `world.arena_offers` reads it to
decide which (non-lethal, paid) fights the guild may take on.

The guild also carries the taverna's current crop of strangers (`taverna_pool`)
so they stay the same face-to-face across visits; `recruit.refresh_pool` swaps
them for a new set once a week.
"""

from . import data, economy, progression
from .clock import Clock
from .group import Group
from .tutorial import TutorialState

# Fallbacks for a guild with no chosen identity (old saves, from before the
# draft's naming/banner step existed). Plain data, not `theme`/`artwork`
# imports -- this module stays pygame-free; the presentation layer resolves
# these slugs/colours (`theme.BANNER_COLORS`, `artwork.BANNER_ICONS`).
DEFAULT_BANNER_COLOR = (94, 156, 214)   # same value as theme.PLAYER_C's own default
DEFAULT_BANNER_ICON = "shield-bash"     # artwork.BANNER_ICONS[0]


class Guild:
    def __init__(self, roster, battles_won=0, reputation=None, deeds_done=None,
                 arena_challenge_day=None, clock=None, node=None,
                 taverna_week=None, taverna_pool=None, taverna_blocked=None,
                 bank_capacity=0, bank_items=None, groups=None,
                 leader=None, leader_swaps_used=0,
                 name="", banner_color=None, banner_icon=None, tutorial=None):
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
        # the taverna's strangers, re-rolled weekly by `recruit.refresh_pool`
        self.taverna_week = taverna_week      # week index the pool was rolled for, or None
        self.taverna_pool = taverna_pool      # list[Unit] on offer, or None (roll on first visit)
        self.taverna_blocked = taverna_blocked if taverna_blocked is not None else []
        #   ^ [[candidate_uid, recruiter_uid], ...] pitches already failed this week
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
        place right now conceptually until the order resolves)."""
        peel = [u for u in group.members if u in set(members)]
        if not peel or len(peel) == len(group.members):
            raise ValueError("split needs a non-empty, proper subset of the group")
        if group.busy:
            raise ValueError("can't split a group with an order in flight")
        group.members = [u for u in group.members if u not in peel]
        new_group = Group(peel, node=group.node, name=name)
        self.groups.append(new_group)
        self._sync_leadership()
        return new_group

    def merge_groups(self, a, b):
        """Fold `b` into `a` -- only valid when they're standing on the same
        node (a group is a physical thing; merging elsewhere would teleport
        someone). Removes `b` from the guild. Returns `a`."""
        if a.node != b.node:
            raise ValueError("can only merge groups standing on the same node")
        if a.busy or b.busy:
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
        for _ in range(self.clock.day - start_day):
            events += self._daily_upkeep()
        return events

    def _shared_larder(self, eater):
        """The packs `eater` may draw a ration from -- every group-mate
        (physically together, so the only ones who could actually hand over
        food) whose `share_food` is on. Own pack is handled first by the unit
        itself."""
        group = self.group_of(eater)
        mates = group.members if group is not None else self.roster
        return [u._base_inventory for u in mates
                if u is not eater and u.share_food]

    def _daily_upkeep(self):
        events, casualties, ate = [], [], []
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
        events = self.pass_time(hours)
        events += self.eat_now_pass()
        if not events:
            events.append("A quiet stop. No one needed to eat.")
        return events

    def work_speedup(self, crew):
        """The clock-time multiplier a work shift actually takes: 1.0 unless
        someone on `crew` has Brisk Hands, in which case the whole guild moves
        on only once the SLOWEST worker is done -- so the saving lands only
        when nobody on the crew is dragging."""
        return max((1 - u.talent_bonus("activity_speed") for u in crew), default=1.0)

    def work_shift(self, workers, hours):
        """A stint at the lumber yard outside the walls, done right now:
        advances the campaign clock through `pass_time` (a long shift can cross
        midnight and run the daily meal -- a starving worker may not live to be
        paid) and then pays the crew. See `_pay_shift` for the pay/XP step alone
        (used by the tick/orders engine, which advances the clock itself)."""
        hours = int(hours)
        crew = [u for u in workers if u in self.roster]
        clock_hours = hours * self.work_speedup(crew)
        events = self.pass_time(clock_hours)
        events += self._pay_shift(workers, hours, clock_hours)
        return events

    def _pay_shift(self, workers, hours, clock_hours):
        """Pay + bank work-XP for a completed shift -- no clock advance, the
        caller already ran `pass_time`. `hours` is the nominal shift length
        (what pay/XP are based on); `clock_hours` is how long it actually took
        (Brisk Hands can shrink it), used only for the "done early" note."""
        earners = [u for u in workers if u in self.roster]   # a long shift can starve one
        paid = []
        for u in earners:
            level = economy.lumber_level(u)
            pay = economy.lumber_pay(hours, level)
            gain = round(pay * (1 + u.talent_bonus("coin_gain")))
            u.gold += gain
            u.work_hours += progression.work_xp_hours(hours, level, u.work_level)
            u.collect_levels()                 # more work marks can lift the mean level
            paid.append(gain)

        events = []
        if earners:
            names = ", ".join(u.name for u in earners)
            wage = (f"+{paid[0]} copper each" if len(set(paid)) == 1
                    else f"+{sum(paid)} copper total")
            note = f"Lumber yard: {names} worked {hours} h ({wage})."
            if clock_hours < hours:
                note += f"  Brisk Hands: crew done in {clock_hours:g} h."
            events.append(note)
        return events

    @property
    def gold(self):
        """Total copper across the roster (the guild has no purse of its own)."""
        return sum(u.gold for u in self.roster)

    def record_victory(self):
        self.battles_won += 1

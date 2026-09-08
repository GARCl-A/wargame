"""The guild: the player's organisation.

The guild *is* its roster -- there is no hall, no vault, no treasury; gold and
items live on the individual characters. `Guild` is the set of members, the
campaign tallies (`battles_won`, `arena_reputation`), and the campaign clock,
plus where the guild currently sits on the world map (`node`). It is the seam
hired hands and a bank hang off later.

`arena_reputation` rises one point per won arena bout; `world.arena_offers`
reads it to decide which (non-lethal, paid) fights the guild may take on.

The guild also carries the taverna's current crop of strangers (`taverna_pool`)
so they stay the same face-to-face across visits; `recruit.refresh_pool` swaps
them for a new set once a week.
"""

from .clock import Clock


class Guild:
    def __init__(self, roster, battles_won=0, arena_reputation=0, clock=None, node=None,
                 taverna_week=None, taverna_pool=None, taverna_blocked=None):
        self.roster = roster                  # list[Unit] -- the members
        self.battles_won = battles_won
        self.arena_reputation = arena_reputation
        self.clock = clock or Clock()
        self.node = node                      # current world-map node id (set on entry)
        # the taverna's strangers, re-rolled weekly by `recruit.refresh_pool`
        self.taverna_week = taverna_week      # week index the pool was rolled for, or None
        self.taverna_pool = taverna_pool      # list[Unit] on offer, or None (roll on first visit)
        self.taverna_blocked = taverna_blocked if taverna_blocked is not None else []
        #   ^ [[candidate_uid, recruiter_uid], ...] pitches already failed this week

    def __len__(self):
        return len(self.roster)

    @property
    def empty(self):
        return not self.roster

    @property
    def hungry(self):
        return [u for u in self.roster if u.hunger_level > 0]

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

    def _daily_upkeep(self):
        events, casualties = [], []
        for u in self.roster:
            outcome = u.consume_daily_food()
            if outcome == "dead":
                casualties.append(u)
                events.append(f"{u.name} morreu de fome.")
            elif outcome == "hungry":
                events.append(f"{u.name} nao comeu hoje: {u.hunger_label}.")
            u._derive_combat()                 # refresh mods / hp_max for the new hunger
        if casualties:
            self.roster = [u for u in self.roster if u not in casualties]
        return events

    @property
    def gold(self):
        """Total copper across the roster (the guild has no purse of its own)."""
        return sum(u.gold for u in self.roster)

    def record_victory(self):
        self.battles_won += 1

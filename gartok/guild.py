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

from . import economy
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

    def _daily_upkeep(self):
        events, casualties, ate = [], [], []
        for u in self.roster:
            outcome = u.consume_daily_food()
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
            self.roster = [u for u in self.roster if u not in casualties]
        return events

    def do_maintenance(self, hours=1):
        """A camp stop: the guild takes `hours` to see to itself. Advances the
        clock (so a stop that crosses midnight still runs the daily meal) and
        then lets anyone still hungry eat from their pack right now. Returns the
        events to show. Eating is the only chore today; rest / gear repair hang
        off here later."""
        events = self.pass_time(hours)
        fed = []
        for u in self.roster:
            if u.eat_now():
                fed.append(u)
                u._derive_combat()
        if fed:
            names = ", ".join(u.name for u in fed)
            events.append(f"Stopped to eat: {names} ({self.rations} rations left).")
        elif not events:
            events.append("A quiet stop. No one needed to eat.")
        return events

    def work_shift(self, workers, hours):
        """A stint at the lumber yard outside the walls: `workers` trade `hours`
        of the day for copper. Pays `economy.lumber_pay(hours)` (lifted by the
        Piecework talent) straight into each worker's purse and banks the full
        `hours` toward their work-XP. Brisk Hands is each worker's own -- a Brisk
        worker finishes their share early, but the guild moves on as one token
        only once the SLOWEST worker is done, so the clock saving lands only when
        nobody on the crew is dragging. Advances the campaign clock through
        `pass_time` (a long shift can cross midnight and run the daily meal), so a
        starving worker may not live to be paid. Returns the events to show."""
        hours = int(hours)
        pay = economy.lumber_pay(hours)
        crew = [u for u in workers if u in self.roster]
        slowest = max((1 - u._talent_sum("activity_speed") for u in crew), default=1.0)
        clock_hours = hours * slowest
        events = self.pass_time(clock_hours)
        earners = [u for u in workers if u in self.roster]   # a long shift can starve one
        paid = []
        for u in earners:
            gain = round(pay * (1 + u._talent_sum("coin_gain")))
            u.gold += gain
            u.work_hours += hours
            u.collect_levels()                 # more work marks can lift the mean level
            paid.append(gain)

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

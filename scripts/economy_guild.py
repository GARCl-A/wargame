"""Economy sim v2, layer 2: a whole guild lives N days under a policy.

Plan: docs/plans/economy_sim_v2.md. The real `Guild` lives the days: the real order engine
(`orders` + `campaign.advance`) walks it between places and ticks the clock, the real daily
upkeep feeds it, rots its food and heals it, and the market is the real `MarketScreen`, so
prices, haggling, finite stock and the market's cash (`Guild.shop(node_id).cash`) all bite. Work and
tavern shifts, hunts and rests go through the same calls the game makes.

The one stand-in is the fight. A policy only decides *what* to do; fights are drawn from a
library of real battles (`Battle` + `ai`, folded in by `campaign.absorb_battle`) played ahead
of time for each (kind, level, party size). `--skill` replaces the AI's win rate with a
player's, drawing a won or a lost sample, because the AI plays much worse than a person.

A policy is a class with `step(sim)`; each step spends time. Policies:

  lumber    the floor: work the yard 16 h, rest 8 h, eat
  cautious  lumber, plus the Scrapper bout until everyone is combat 1; hunts only at mean
            level 3 and full health
  balanced  Scrapper to combat 1, lumber to build a buffer, buys Studded Leather, a weapon
            and the strongbox in turn, hunts from mean level 2
  greedy    Scrapper and the Wilds from day one, buys food only when the packs are empty
  maxev     each cycle picks the activity with the best expected copper per day
  human     balanced, playing by thresholds measured from recorded play (--profile)
  rush      the recorded line: Axes, the Champion at level 0, one hunt for a Hide, the Dictionary mission
  crafter   a specialist guild: the best crafter buys inputs and crafts on a solo order
            while the rest work the yard, then sells at the market (the experiment for
            the restock limiter; needs `--recipes`)

    python scripts/economy_guild.py                         # every policy, 7 and 30 days
    python scripts/economy_guild.py --policies lumber,balanced --guilds 60 --skill 0.8
    python scripts/economy_guild.py --policies crafter --recipes "Bear Trap" --restock 4:1
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import ClassVar

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(SCRIPTS))

import economy_activities as act

from gartok import (
    animals,
    arena,
    campaign,
    craft_level,
    data,
    economy,
    encounters,
    hunt,
    items,
    matchup,
    medic,
    missions,
    orders,
    recorder,
    recruit,
    rest,
    solo,
    wagon,
    world,
)
from gartok.clock import SECONDS_PER_DAY
from gartok.guild import Guild
from gartok.market_screen import MarketScreen
from gartok.prison_screen import BAIL_BONUS
from gartok.scenario import ErmosScenario

SHIFT_HOURS = 16                     # a work shift; the other 8 h of the day are sleep
SLEEP_HOURS = 24 - SHIFT_HOURS
FOOD_LOW_DAYS = 2                    # shop when the packs hold less than this many days
FOOD_TARGET_DAYS = 6                 # ...and buy up to this many (a Potato keeps 7)
MILESTONE_WEAPON = "Axe"             # the weapon the day-30 milestone prices
MILESTONE_ARMOR = "Studded Leather"
MILESTONE_FOOD_DAYS = 7
CURVE_DAYS = (1, 3, 7, 14, 21, 30)
STEP_LIMIT = 4000
CREW_FOOD_DAYS = 6                   # rations the crew is kept stocked with at each shop visit
CREW_CHUNK_HOURS = 4                 # the crew's orders are checked this often while the squad is busy
# what a member spends talent picks on, in order: the work track pays (Piecework +20% coin,
# Brisk Hands, Steady Pace heals on the job), the combat track keeps the squad alive
TALENT_PLAN = {
    "work": ("carrier", "piecework", "brisk_hands", "steady_pace"),
    "combat": ("tough", "hardy", "bulwark", "recovery"),
}
AXE_BUFFER_DAYS = 3                  # days of food kept in hand when buying an Axe
MIXED_DAYS = 14                      # most days a mixed guild works its wounds off before giving up


def spend_picks(unit):
    """Spend the talent picks the unit's levels earned, on `TALENT_PLAN` in order. A library
    squad does it too, so a level-3 fight is fought by a level-3 character with its talents."""
    for track, plan in TALENT_PLAN.items():
        for talent_id in plan:
            if unit.picks_available(track) <= 0:
                break
            unit.choose_talent(track, talent_id)


class Wiped(Exception):
    """The whole guild is dead."""


# --------------------------------------------------------------------------- #
# fights: a library of real battles, drawn from by outcome                    #
# --------------------------------------------------------------------------- #
@dataclass
class Sample:
    won: bool
    rounds: int
    members: list                     # per party slot: (hp lost, died, combat xp)
    loot: list                        # item names the winners pick up
    purse: int                        # arena purse, 0 elsewhere


CLAIM_NODE = world.WILDS_TERRITORY_NODE
CLAIM_FOOD_DAYS = 12                 # rations bought for a Claim expedition: the walk and a stay
CLAIM_RESOLVERS = {
    "wilds_raid": campaign.resolve_wilds_raid,
    "wilds_seizure": campaign.resolve_wilds_seizure,
    "wilds_retake": campaign.resolve_wilds_claim_retake,
}
# the Claim's fights: (enemy level, enemy count)
CLAIM_FIGHTS = {
    "claim_clear": (economy.WILDS_CLAIM_CLEAR_LEVEL, economy.WILDS_CLAIM_CLEAR_SIZE),
    "claim_sweep": (economy.WILDS_CLAIM_SWEEP_LEVEL, economy.WILDS_CLAIM_SWEEP_SIZE),
    "raid": (economy.WILDS_RAID_LEVEL, economy.WILDS_RAID_SIZE),
}


def as_levels(level):
    """A library key: `(combat, work)`. The racial level, and with it the hit dice, is the two
    added, so a combat-only squad and a squad that also works are not the same fighters."""
    return level if isinstance(level, tuple) else (level, level)


class FightLibrary:
    """Real battles for each (kind, levels, size), played once and cached. Kinds: the arena's
    bouts (`arena` the Scrapper, `champion`, `brawl`, `ctf`; non-lethal), `wilds` (a hunt's
    ambush), `road` (the Old Road), and the Claim's `claim_clear`, `claim_sweep` and `raid`."""

    def __init__(self, samples=40):
        self.samples = samples
        self.cache = {}

    def pool(self, kind, level, size):
        key = (kind, as_levels(level), size)
        if key not in self.cache:
            self.cache[key] = [self._play(kind, key[1], size) for _ in range(self.samples)]
        return self.cache[key]

    @staticmethod
    def _play(kind, level, size):
        squad = act.make_squad(size, level)
        for u in squad:
            spend_picks(u)
        guild = Guild(squad, node="city")
        before = [(u.hp, u.combat_xp) for u in squad]
        if kind in act.BOUTS:
            node, bout = world.node("arena"), act.BOUTS[kind]()
            foes, scenario = matchup.build(node, bout, squad_size=size, guild=guild)
            battle = act.play(squad, foes, scenario, lethal=False)
            outcome = campaign.absorb_battle(guild, squad, battle, node=node, arena_offer=bout)
        elif kind in CLAIM_FIGHTS:
            node, (foe_level, count) = world.node(CLAIM_NODE), CLAIM_FIGHTS[kind]
            foes = [encounters.build_enemy(foe_level) for _ in range(count)]
            battle = act.play(squad, foes, node.scenario(), lethal=True)
            outcome = campaign.absorb_battle(guild, squad, battle, node=node)
        else:
            if kind == "wilds":
                node, foes, scenario = world.node("wilds"), hunt.wilds_pack(), ErmosScenario()
            else:
                node = world.node("road")
                foes = encounters.roll_encounter(node.encounter_table)
                scenario = ErmosScenario()
            battle = act.play(squad, foes, scenario, lethal=True)
            outcome = campaign.absorb_battle(guild, squad, battle, node=node)
        members = []
        for u, (hp, xp) in zip(squad, before):
            members.append((max(0, hp - u.hp), u not in guild.roster, u.combat_xp - xp))
        return Sample(outcome.won, battle.round_no, members, list(outcome.loot_pool),
                      outcome.arena_reward or 0)

    def draw(self, kind, level, size, rng, skill=None):
        """One sample: the AI's own mix, or a won / lost one with a player's win chance."""
        pool = self.pool(kind, level, size)
        if skill is None:
            return rng.choice(pool)
        wins = [s for s in pool if s.won]
        losses = [s for s in pool if not s.won]
        want_win = rng.random() < skill
        chosen = (wins if want_win else losses) or pool
        return rng.choice(chosen)

    def relief(self, kind, level, size, skill=None):
        """How much of the AI's casualties in won fights a better player still takes: 1 at the
        AI's own win rate, 0 at a perfect record (an assumption, as in layer 1's hunts)."""
        if skill is None:
            return 1.0
        pool = self.pool(kind, level, size)
        ai = sum(s.won for s in pool) / len(pool)
        return 1.0 if ai >= 1 else min(1.0, (1 - skill) / (1 - ai))

    def stats(self, kind, level, size, skill=None):
        """(win chance, mean loot value, mean deaths) of a fight, for a policy to weigh."""
        pool = self.pool(kind, level, size)
        wins = [s for s in pool if s.won]
        p = (len(wins) / len(pool)) if skill is None else skill
        value = statistics.mean(act.loot_value(s.loot) for s in wins) if wins else 0.0
        deaths = statistics.mean(sum(m[1] for m in s.members) for s in pool)
        return p, value, deaths


# --------------------------------------------------------------------------- #
# the restock limiter under test                                              #
# --------------------------------------------------------------------------- #
@dataclass
class Restock:
    """Every freely bought market item gets a finite shelf: `target` units, refilled by
    `per_day` each morning (selling back tops a shelf up, as the real finite stock does)."""
    target: int
    per_day: int

    @classmethod
    def parse(cls, text):
        target, per_day = text.split(":")
        return cls(int(target), int(per_day))


# --------------------------------------------------------------------------- #
# one simulated guild                                                         #
# --------------------------------------------------------------------------- #
@dataclass
class Snapshot:
    day: float
    money: int
    alive: int
    combat: float
    work: float
    rations: int
    gear_cost: int
    armored: int = 0                  # members in Studded Leather or better
    chest: bool = False


class Sim:
    def __init__(self, policy, *, size=3, level=0, skill=None, seed=0, library=None,
                 restock=None, recipes=(), capital=0, assets=(), medic=False, horizon=None, mixed=False, talents=True):
        random.seed(seed)
        self.rng = random.Random(seed)
        squad = act.make_squad(size, level)
        for u in squad:
            u.recipes.extend(r for r in recipes if r not in u.recipes)
        if capital:
            squad[0].give_to_pack(items.COIN_ITEM, capital)
        self.guild = Guild(squad, node="city")
        self.main = self.guild.groups[0]
        self.crew = None                      # the group that works the yard while the squad is out
        self._crew_works = False
        self.recruited = 0                    # strangers who signed on
        self.pitches = 0                      # pitches made
        self.bail_spent = 0                   # copper paid in bail
        for asset in assets:
            self.own(asset)
        self.policy = policy
        self.skill = skill
        self.library = library or FightLibrary()
        self.restock = restock
        self.medic = medic
        self.mixed = mixed
        self.talents = talents
        self.horizon = horizon if horizon is not None else float("inf")
        self.champion_beaten = False
        self.claim_day = None                 # the day the Claim became the guild's
        self.claim_lumber = 0                 # Lumber the garrison gathered and brought home
        self.treated = 0                      # copper paid to the Medic
        self.bouts = 0                        # staked arena bouts fought
        self.start_xp = sum(u.combat_xp for u in squad)
        self.start_members = size
        self.start_money = self.money
        self.sellable = Counter()
        self.sold_total = 0                   # copper the market paid for the guild's goods
        self.input_spend = 0                  # copper the crafter paid for inputs
        self.snapshots = []
        self.starved = 0
        self.milestone_day = None
        self._stock_day = 0
        if restock:
            for name in dict.fromkeys(economy.MARKET_STOCK):
                if economy.freely_buyable(name):
                    self.guild.shop("market").stock[name] = restock.target
        self.snap()

    def own(self, asset):
        """Start with something the guild has to keep: `house` (taxed every week), an animal
        (`Donkey`, `Ox`, `Horse`: a mouth to feed) or a `Cart` (worn by the road)."""
        if asset == "house":
            self.guild.buy_city_property()
        elif asset in animals.PRICE:
            self.group.herd.append(animals.Animal(asset))
        elif asset in wagon.VEHICLES:
            self.group.add_wagon(wagon.Wagon(asset))
            self.group.hitch_idle()
        else:
            raise ValueError(f"unknown asset {asset!r}")

    # -- state ------------------------------------------------------------- #
    @property
    def group(self):
        if self.main not in self.guild.groups:
            raise Wiped
        return self.main

    @property
    def members(self):
        return list(self.group.members)

    @property
    def money(self):
        return sum(u.money for u in self.guild.roster)

    @property
    def elapsed(self):
        return self.guild.clock.seconds / SECONDS_PER_DAY

    @property
    def rations(self):
        return self.group.rations

    @property
    def mouths(self):
        """Whoever eats a ration a day: the members and the animals of the herd."""
        return len(self.members) + len(self.group.herd)

    @property
    def food_days(self):
        return self.rations / max(1, self.mouths)

    @property
    def crew_food_days(self):
        if self.crew is None:
            return float("inf")
        return self.crew.rations / max(1, len(self.crew.members))

    @property
    def mean_combat(self):
        return statistics.mean(u.combat_level for u in self.members)

    @property
    def fight_level(self):
        """(combat, work) the fight library plays this squad at: both tracks matter, since the
        racial level (hit dice) is their sum."""
        return (round(self.mean_combat),
                round(statistics.mean(u.work_level for u in self.members)))

    @property
    def min_combat(self):
        return min(u.combat_level for u in self.members)

    @property
    def hurt(self):
        return any(u.hp < u.hp_max for u in self.members)

    @property
    def badly_hurt(self):
        return any(u.hp * 2 < u.hp_max for u in self.members)

    def spend_picks(self):
        for u in self.guild.roster:
            spend_picks(u)

    def snap(self):
        roster = self.guild.roster
        if not roster:
            return
        if self.talents:
            self.spend_picks()
        cost = milestone_cost(self)
        self.snapshots.append(Snapshot(
            self.elapsed, self.money, len(roster),
            statistics.mean(u.combat_level for u in roster),
            statistics.mean(u.work_level for u in roster), self.rations, cost,
            sum(_owns_at_least(u, MILESTONE_ARMOR, u.equipped_armor or "") for u in roster),
            bool(self.guild.bank.capacity)))
        if self.milestone_day is None and self.money >= cost:
            self.milestone_day = self.elapsed
        self.starved += sum(1 for u in roster if u.unfed_days > 0) and 1
        if self.claim_day is None and self.guild.wilds_claim_stage == "ESTABLISHED":
            self.claim_day = self.elapsed

    def _refill_shelves(self):
        if not self.restock:
            return
        today = int(self.elapsed)
        days, self._stock_day = today - self._stock_day, today
        if days <= 0:
            return
        shelves = self.guild.shop("market").stock
        for name, count in shelves.items():
            if economy.freely_buyable(name):
                shelves[name] = min(self.restock.target, count + self.restock.per_day * days)

    # -- the order engine -------------------------------------------------- #
    def run_order(self, order):
        """Issue `order` to the guild's group and tick the real engine until it resolves.
        Returns the interactive order it arrived with, or None for an auto order. A road
        ambush on the way is fought and the walk resumed."""
        group = self.group
        group.order = order
        self.tend_crew()
        for _ in range(STEP_LIMIT):
            result = campaign.advance(self.guild)
            self._refill_shelves()
            if result.wiped or self.guild.empty:
                raise Wiped
            self.tend_crew()
            arrived = None
            for grp, pend in result.pending:
                if grp is not group and pend.kind not in CLAIM_RESOLVERS and pend.kind != "ambush":
                    continue
                if pend.kind == "ambush":
                    self._road_fight(grp, pend)
                elif pend.kind in CLAIM_RESOLVERS:
                    self._claim_fight(grp, pend)
                elif pend.kind in orders.FORCED_KINDS:
                    raise RuntimeError(f"unexpected forced order {pend.kind!r}")
                else:
                    arrived = pend
            if arrived is not None:
                group.order = None
                self.snap()
                return arrived
            if not group.busy:
                self.snap()
                return None
        raise RuntimeError("order did not resolve")

    def goto(self, node_id):
        if self.group.node != node_id:
            self.run_order(orders.travel(self.group, node_id))

    def arrive(self, kind, node_id):
        self.goto(node_id)
        self.run_order(orders.interactive(kind))

    def sleep(self, hours=SLEEP_HOURS):
        self.run_order(orders.rest(hours))

    def pass_hours(self, hours, busy=None):
        busy = busy if busy is not None else self.members
        if self.crew is None:
            events, _ = self.guild.pass_time(hours, busy=busy)
        else:
            events = []
            while hours > 1e-9:
                chunk = min(hours, CREW_CHUNK_HOURS)
                events += campaign.advance(self.guild, dt=chunk, busy=busy).events
                hours -= chunk
                self.tend_crew()
        self._refill_shelves()
        if self.guild.empty:
            raise Wiped
        self.snap()
        return events

    # -- a growing guild --------------------------------------------------- #
    def recruit(self, node="tavern", reserve=0):
        """A visit to the tavern (free; the Charisma contest decides) or the prison (the bail is
        paid first, +2 to the contest, and lost if the pitch fails). The best talker with a free
        sponsor slot and a shared language pitches each stranger. -> how many signed on."""
        prison = node == "prison"
        self.arrive("prison" if prison else "recruit", node)
        guild = self.guild
        pool = recruit.refresh_prison_pool(guild) if prison else recruit.refresh_pool(guild)
        barred = recruit.prison_barred if prison else recruit.barred
        bar = recruit.prison_bar if prison else recruit.bar
        hired = 0
        for cand in list(pool):
            talkers = [m for m in self.members if recruit.slots_free(guild, m) > 0
                       and recruit.can_pitch(m, cand) and not barred(guild, cand, m)]
            if not talkers:
                continue
            bail = recruit.bail_cost(cand) if prison else 0
            if bail and self.money < bail + reserve:
                continue
            talker = max(talkers, key=lambda m: m.mod_charisma)
            if bail:
                economy.charge_richest_first(self.members, bail)
                self.bail_spent += bail
            self.pitches += 1
            pitch = recruit.convince(talker, cand, len(guild.roster), day=guild.clock.day,
                                     extra_mods=[BAIL_BONUS] if prison else None)
            if pitch.ok:
                recruit.enlist(guild, cand, talker)
                hired += 1
                self.recruited += 1
            else:
                bar(guild, cand, talker)
        self.snap()
        return hired

    def seat_extras(self, fighters):
        """Everyone past the first `fighters` of the squad goes to the crew that works the yard.
        The first time that is a split of the squad's group; later arrivals are added to the
        crew directly (they walk to the yard unseen). Needs a free group slot for the first split."""
        extras = self.main.members[fighters:]
        if not extras:
            return
        if self.crew is None or self.crew not in self.guild.groups:
            try:
                self.crew = self.guild.split_group(self.main, extras, name="Crew")
            except ValueError:
                return
            self.crew.order = None
        else:
            for u in extras:
                self.main.members.remove(u)
                self.crew.members.append(u)
            self.guild._sync_leadership()
        self.tend_crew()

    def tend_crew(self):
        """Give the crew its next order when it is idle: walk to the yard, work 16 h, rest 8 h."""
        crew = self.crew
        if crew is None:
            return
        if crew not in self.guild.groups or crew.empty:
            self.crew = None
            return
        if crew.busy:
            return
        if crew.node != "lumber_yard":
            crew.order = orders.travel(crew, "lumber_yard")
            return
        self._crew_works = not self._crew_works
        crew.order = (orders.work(self.guild, crew, SHIFT_HOURS) if self._crew_works
                      else orders.rest(SLEEP_HOURS))

    def crew_pay_in(self):
        """The crew hands its wages to the squad at a shop visit (no treasury: the coins are
        theirs, and they meet the squad at the market in this model)."""
        if self.crew is None:
            return
        total = sum(u.money for u in self.crew.members)
        if not total:
            return
        for u in self.crew.members:
            u.money = 0
        self.members[0].money += total

    # -- fights ------------------------------------------------------------ #
    def apply(self, sample, party, relief=1.0, kind=None):
        """Fold a drawn fight into the real guild: hurt, kill, level, then hand out the loot.
        `relief` thins the deaths of a won fight (see `FightLibrary.relief`)."""
        dead = []
        slots = list(sample.members)
        self.rng.shuffle(slots)           # a library squad's slots are exchangeable: no member is always the one who kills
        for unit, (lost, died, xp) in zip(party, slots):
            if died and sample.won and self.rng.random() >= relief:
                died, lost = False, unit.hp
            if died:
                dead.append(unit)
                recorder.death(unit, "combat", kind=kind, won=sample.won, rounds=sample.rounds,
                               hp_frac=round(max(0, unit.hp) / unit.hp_max, 2), squad=len(party),
                               unfed_days=unit.unfed_days)
                continue
            unit.hp = max(1, unit.hp - lost)
            if xp:
                unit.combat_xp += xp
                unit.collect_levels()
        self.guild.clock.advance_rounds(sample.rounds)
        if dead:
            self.guild.remove_members(dead)
        survivors = [u for u in party if u not in dead]
        if not survivors:
            raise Wiped
        if sample.won:
            self.hand_out(sample.loot, survivors)
        return survivors

    def hand_out(self, loot, members):
        for i, name in enumerate(loot):
            for k in range(len(members)):
                u = members[(i + k) % len(members)]
                if u.load + items.item_weight(name) <= u.carry_max:
                    u.give_to_pack(name)
                    if not items.is_coin(name):
                        self.sellable[name] += 1
                    break

    def fight(self, kind, party):
        level = (round(statistics.mean(u.combat_level for u in party)),
                 round(statistics.mean(u.work_level for u in party)))
        sample = self.library.draw(kind, level, len(party), self.rng, self.skill)
        relief = self.library.relief(kind, level, len(party), self.skill)
        return sample, self.apply(sample, party, relief, kind)

    def _road_fight(self, group, pend):
        self.fight("road", list(group.members))
        campaign.resolve_road_ambush(self.guild, group, pend)

    def _claim_fight(self, group, pend):
        """A raid on the garrison, a seizure attempt or the fight to retake a seized claim."""
        sample, _ = self.fight("raid", list(group.members))
        CLAIM_RESOLVERS[pend.kind](self.guild, group, pend, SimpleNamespace(won=sample.won))

    # -- places ------------------------------------------------------------ #
    def work_shift(self, hours=SHIFT_HOURS):
        self.goto("lumber_yard")
        self.run_order(orders.work(self.guild, self.group, hours))

    def heal(self):
        if self.medic and self.treat():
            return
        if self.mixed:
            for _ in range(MIXED_DAYS):
                if not self.hurt or self.food_days < 1:
                    break
                self.work_shift()
                self.sleep()
            return
        plan = rest.until_full(self.guild, self.group)
        self.run_order(orders.rest(plan.hours if plan.available else SLEEP_HOURS))

    def treat(self):
        """The Medic's quick treatment (`medic.py`): every hurt, sick or poisoned member is
        cured at the City for the potions and doses it would take at a discount, in the
        longest treatment's hours. False when the guild cannot pay it and still eat tomorrow."""
        quotes = [q for q in medic.quotes(self.members) if q.needs_care and q.offered]
        patients = {q.uid for q in quotes}
        cost, hours = medic.total(quotes)
        if not quotes or self.money < cost + self.mouths * cheapest_food_price():
            return False
        self.goto("city")
        economy.charge_richest_first(self.members, cost)
        for u in self.members:
            if u.uid in patients:
                medic.cure(u)
        self.treated += cost
        self.pass_hours(hours)
        return True

    def stage_show(self, hours=4):
        crew = [u for u in self.members if economy.can_perform(u)]
        if not crew:
            return False
        self.goto("tavern")
        self.guild.perform_shift(crew, hours)
        self.snap()
        return True

    def bout(self, kind="arena"):
        """One staked bout (`act.BOUTS`: the Scrapper by default): stake, fight, and the purse to
        whoever the player picks. Beating the champion opens the Games."""
        bout = act.BOUTS[kind]()
        party = self.members
        stake = bout.entry * len(party)
        if self.money < stake:
            return None
        self.arrive("arena", "arena")
        economy.charge_richest_first(party, stake)
        self.bouts += 1
        sample, survivors = self.fight(kind, party)
        if sample.won and survivors:
            survivors[0].money += sample.purse
            if kind == "champion":
                self.champion_beaten = True
        return sample

    def hunt(self, hours=SHIFT_HOURS):
        """A day in the Wilds: walk there, hunt, an ambush now and then, walk back later."""
        self.arrive("hunt", "wilds")
        state = hunt.HuntState(party=self.members, node=world.node("wilds"), hours_left=hours)
        while state.hours_left > 0 and state.party:
            elapsed, ambushed = hunt.hunt_stretch(state, self.rng)
            self.pass_hours(elapsed, busy=state.party)
            if not ambushed:
                continue
            state.fights += 1
            sample, survivors = self.fight("wilds", state.party)
            state.party = survivors
            if not sample.won:
                break
        hunt.grant_haul(state)
        return state

    # -- the Wilds claim --------------------------------------------------- #
    def claim_cost(self):
        """Copper an expedition needs beyond the usual buffer: food for the stay and, until the
        fences are up, the Lumber for them."""
        food = max(0, CLAIM_FOOD_DAYS * self.mouths - self.rations) * cheapest_food_price()
        return food + self._fence_lumber_short() * economy.LUMBER_PRICE

    def _fence_lumber_short(self):
        g = self.guild
        if g.wilds_claim_stage not in ("NONE", "SCOUTED", "CLEARED"):
            return 0
        carried = sum(u.count_of("Lumber") for u in self.members)
        return max(0, economy.WILDS_CLAIM_FENCE_LUMBER - g.wilds_claim_fence_lumber - carried)

    def claim_run(self):
        """One expedition to the Claim: stock up, walk there, and push the campaign (scout, clear,
        fence, sweep, garrison) as far as the squad's health allows. A lost fight ends the run."""
        g = self.guild
        if self.food_days < CLAIM_FOOD_DAYS * 0.6 or self._fence_lumber_short():
            with self.market() as shop:
                shop.sell_loot()
                shop.buy_food(CLAIM_FOOD_DAYS)
                for _ in range(self._fence_lumber_short()):
                    roomy = max(self.members, key=lambda u: u.carry_max - u.load)
                    if not shop.buy(roomy, "Lumber"):
                        break
        self.goto(CLAIM_NODE)
        if g.wilds_claim_owner == "seized":
            return
        if g.wilds_claim_stage == "NONE":
            self.pass_hours(economy.WILDS_CLAIM_SCOUT_HOURS)
            g.wilds_claim_scout()
        if g.wilds_claim_stage == "SCOUTED":
            if not self.fight("claim_clear", self.members)[0].won:
                return
            g.wilds_claim_mark_cleared()
        if g.wilds_claim_stage == "CLEARED":
            total = 0
            for u in self.members:
                if n := u.count_of("Lumber"):
                    u.remove_named("Lumber", n)
                    total += n
            if total:
                g.wilds_claim_deposit_lumber(total)
            if g.wilds_claim_fence_lumber < economy.WILDS_CLAIM_FENCE_LUMBER:
                return
            self.pass_hours(economy.WILDS_CLAIM_FENCE_HOURS)
            g.wilds_claim_build_fences()
        if g.wilds_claim_stage == "FENCED":
            if not self.fight("claim_sweep", self.members)[0].won:
                return
            g.wilds_claim_mark_swept()
        self.hold_claim()

    def hold_claim(self):
        """Garrison the Claim a day at a time (the map's ADVANCE 24 h), fighting the raids that
        come, until the food runs low, someone is near death, the claim is seized or the run ends."""
        g = self.guild
        if g.wilds_claim_stage == "SWEPT":
            g.wilds_claim_start_sustaining()
        self.group.order = orders.garrison("lumber")
        while (self.elapsed < self.horizon and self.food_days >= 1 and g.wilds_claim_owner != "seized"
               and not any(u.hp * 4 < u.hp_max for u in self.members)):
            result = campaign.advance(g, dt=24)
            self._refill_shelves()
            if result.wiped or g.empty:
                raise Wiped
            for grp, pend in result.pending:
                self._claim_fight(grp, pend)
            if self.group.order is None:
                self.group.order = orders.garrison("lumber")
            self.snap()
        self.group.order = None
        stock = g.garrison_stock.setdefault(CLAIM_NODE, [])
        for u in self.members:
            while stock and u.load + items.item_weight("Lumber") <= u.carry_max:
                stock.pop()
                u.give_to_pack("Lumber")
                self.sellable["Lumber"] += 1
                self.claim_lumber += 1

    # -- the market -------------------------------------------------------- #
    def market(self):
        self.arrive("market", "market")
        return MarketVisit(self)

    def keep_fed(self, low=FOOD_LOW_DAYS, target=FOOD_TARGET_DAYS, at_low=False):
        """Shop when the food in hand is under `low` days, or at it with `at_low`: a person who
        shops the day the larder is empty is recorded as a threshold of 0."""
        def stocked(days):
            return days > low if at_low else days >= low
        if (stocked(self.food_days) and stocked(self.crew_food_days)) or self.money < cheapest_food_price():
            return False
        with self.market() as shop:
            shop.sell_loot()
            shop.buy_food(target)
        return True


class MarketVisit:
    """One stop at the market, through the real `MarketScreen`."""

    def __init__(self, sim):
        self.sim = sim
        self.node = world.node("market")
        sim.crew_pay_in()
        crew = list(sim.crew.members) if sim.crew is not None else []
        self.screen = MarketScreen(None, sim.guild, sim.members + crew, self.node, lambda: None)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if exc[0] is None:
            self.feed_crew()
        self.sim.snap()
        return False

    def feed_crew(self):
        """Keep the crew stocked with food from the squad's purse (the crew's rations come
        out of the same market stall, as if the squad had carried them over)."""
        sim = self.sim
        if sim.crew is None or sim.money < cheapest_food_price():
            return
        name = cheapest_food()
        need = int(CREW_FOOD_DAYS * len(sim.crew.members)) - sim.crew.rations
        for _ in range(max(0, need)):
            roomy = max(sim.crew.members, key=lambda u: u.carry_max - u.load)
            if sim.money < economy.buy_price(name, self.screen.deal) or not self.buy(roomy, name):
                break

    def _price(self, name):
        return economy.sell_price(name, self.screen.deal)

    def sell_loot(self):
        """Sell what the guild picked up, as much as the market's cash can pay for."""
        screen, sim = self.screen, self.sim
        cash = sim.guild.shop(self.node.id).cash
        picks, total = [], 0
        stacks = [(u, i, n, q) for u in sim.members for i, (n, q) in enumerate(u._base_inventory)
                  if sim.sellable[n] > 0 and not items.is_coin(n)]
        for u, i, name, qty in sorted(stacks, key=lambda s: -self._price(s[2])):
            take = min(qty, sim.sellable[name])
            unit_price = self._price(name)
            take = min(take, int((cash - total) // unit_price))
            if take <= 0:
                continue
            picks.append(((u, i), name, take))
            total += take * unit_price
        if not picks:
            return 0
        screen.selected = [p for p, _, _ in picks]
        screen._sel_qty = {p: take for p, _, take in picks}
        before = sim.money
        screen._sell()
        for _, name, take in picks:
            sim.sellable[name] = max(0, sim.sellable[name] - take)
        sim.sold_total += sim.money - before
        return sim.money - before

    def buy(self, member, name, qty=1, zone="pack"):
        screen = self.screen
        screen.qty[name] = qty
        screen.selected = [("stock", name)]
        before = sum(u.money for u in self.sim.members)
        screen._buy(member, [name], zone=zone)
        return before - sum(u.money for u in self.sim.members)

    def buy_food(self, target_days):
        """Buy the cheapest food up to `target_days` of rations, each unit into whichever
        pack has the most room, until the money, the shelf or the room runs out."""
        sim, name = self.sim, cheapest_food()
        need = int(target_days * sim.mouths) - sim.rations
        for _ in range(max(0, need)):
            roomy = sorted(sim.members, key=lambda u: u.carry_max - u.load, reverse=True)
            if sim.money < economy.buy_price(name, self.screen.deal) or not self.buy(roomy[0], name):
                break


def cheapest_food():
    return min((n for n in data.FOOD_ITEMS if n != "Rotten Food"), key=lambda n: items.get(n).price)


def cheapest_food_price():
    return items.get(cheapest_food()).price


# --------------------------------------------------------------------------- #
# the day-30 milestone: food for 7 days, a weapon and Studded Leather each,    #
# and the bank's strongbox                                                     #
# --------------------------------------------------------------------------- #
def _owns_at_least(member, want, current):
    cur, goal = items.get(current), items.get(want)
    return cur is not None and goal is not None and cur.price >= goal.price


def milestone_cost(sim):
    """Copper still missing for the milestone: whatever the guild has not already got."""
    guild, cost = sim.guild, 0
    for u in guild.roster:
        if not _owns_at_least(u, MILESTONE_ARMOR, getattr(u, "equipped_armor", None) or ""):
            cost += items.get(MILESTONE_ARMOR).price
        if not _owns_at_least(u, MILESTONE_WEAPON, u.equipped_weapon or ""):
            cost += items.get(MILESTONE_WEAPON).price
    if not guild.bank.capacity:
        cost += economy.BANK_CHEST_PRICE
    need_rations = MILESTONE_FOOD_DAYS * len(guild.roster) - guild.rations
    cost += max(0, need_rations) * cheapest_food_price()
    return cost


# --------------------------------------------------------------------------- #
# policies                                                                    #
# --------------------------------------------------------------------------- #
class Policy:
    name = "policy"
    HURT = "badly_hurt"            # how hurt the guild may be and still go about its day

    def upkeep(self, sim):
        sim.keep_fed()
        self.buy_axes(sim)
        if getattr(sim, self.HURT):
            sim.heal()

    def buy_axes(self, sim):
        """The yard pays 4/3 to anyone carrying an Axe, so the first thing a poor squad buys is
        an Axe for whoever lacks one, as soon as it can pay it and still eat for BUFFER_DAYS."""
        axe = items.get(MILESTONE_WEAPON).price
        lacking = [u for u in sim.members if economy.lumber_level(u) == 0]
        reserve = AXE_BUFFER_DAYS * sim.mouths * cheapest_food_price()
        if not lacking or sim.money < axe + reserve:
            return
        with sim.market() as shop:
            for u in lacking:
                if sim.money < axe + reserve:
                    break
                shop.buy(u, MILESTONE_WEAPON)

    def lumber_day(self, sim):
        sim.work_shift()
        sim.sleep()

    def stake(self, sim):
        return arena.scrapper_bout().entry * len(sim.members)

    def level_up_bout(self, sim, spare):
        """A Scrapper bout in the evening, while someone is still combat 0 and the stake and
        `spare` copper (the next meals) are covered."""
        if sim.min_combat < 1 and not sim.hurt and sim.money >= self.stake(sim) + spare:
            sim.bout()
            return True
        return False

    def step(self, sim):
        raise NotImplementedError


class Lumber(Policy):
    name = "lumber"

    def step(self, sim):
        self.upkeep(sim)
        self.lumber_day(sim)


class Cautious(Policy):
    name = "cautious"

    def step(self, sim):
        self.upkeep(sim)
        if sim.mean_combat >= 3 and not sim.hurt and sim.food_days >= 3:
            sim.hunt()
            sim.heal()
            return
        self.level_up_bout(sim, 3 * len(sim.members))
        self.lumber_day(sim)


class Balanced(Policy):
    name = "balanced"
    BUFFER_DAYS = 3

    def buffer(self, sim):
        return self.stake(sim) + self.BUFFER_DAYS * len(sim.members) * cheapest_food_price()

    def gear(self, sim):
        """Armor first, then a weapon, then the strongbox, whenever the buffer survives it."""
        wants = []
        for u in sim.members:
            if not _owns_at_least(u, MILESTONE_ARMOR, getattr(u, "equipped_armor", None) or ""):
                wants.append((u, MILESTONE_ARMOR, "armor"))
        for u in sim.members:
            if not _owns_at_least(u, MILESTONE_WEAPON, u.equipped_weapon or ""):
                wants.append((u, MILESTONE_WEAPON, "hand"))
        wants = [w for w in wants if sim.money >= self.buffer(sim) + items.get(w[1]).price]
        chest = not sim.guild.bank.capacity and sim.money >= self.buffer(sim) + economy.BANK_CHEST_PRICE
        if not wants and not chest:
            return
        if wants:
            with sim.market() as shop:
                shop.sell_loot()
                for member, name, zone in wants:
                    if sim.money >= self.buffer(sim) + items.get(name).price:
                        shop.buy(member, name, zone=zone)
        if chest and sim.money >= self.buffer(sim) + economy.BANK_CHEST_PRICE:
            sim.arrive("bank", "city")
            economy.charge_richest_first(sim.members, economy.BANK_CHEST_PRICE)
            sim.guild.rent_bank_chest()

    def ready(self, sim):
        """Healthy, fed and with the buffer to spare: the squad may leave the yard for a risk."""
        return (sim.mean_combat >= 2 and not sim.hurt and sim.food_days >= 3
                and sim.money >= self.buffer(sim))

    def adventure(self, sim):
        """The risky day this policy prefers once the squad is ready; False if it did none."""
        if not self.ready(sim):
            return False
        sim.hunt()
        sim.heal()
        return True

    def step(self, sim):
        self.upkeep(sim)
        self.gear(sim)
        if self.adventure(sim):
            return
        self.level_up_bout(sim, self.BUFFER_DAYS * len(sim.members) * cheapest_food_price())
        if self.show_pays(sim):
            for _ in range(SHIFT_HOURS // 4):
                sim.stage_show(4)
            sim.sleep()
        else:
            self.lumber_day(sim)

    @staticmethod
    def show_pays(sim):
        """A day of shows replaces the squad's shift at the yard, so it has to pay more than it."""
        singers = [u for u in sim.members if economy.can_perform(u)]
        tips = sum(economy.perform_expected(1, u.mod_charisma) for u in singers)
        wages = sum(economy.lumber_pay(SHIFT_HOURS, economy.lumber_level(u)) for u in sim.members)
        return tips * SHIFT_HOURS > wages


class Grower(Balanced):
    """Balanced, but it recruits once a week until the guild has `TARGET` members, and everyone
    past the three fighters works the yard as a crew while the squad is out. Strangers come
    from the tavern (free) and, when the purse allows, the prison (bail)."""
    name = "grower"
    TARGET = 6
    FIGHTERS = 3

    def __init__(self):
        self.visited = -1

    def step(self, sim):
        self.upkeep(sim)
        week = recruit.current_week(sim.guild.clock)
        if len(sim.guild.roster) < self.TARGET and week != self.visited and sim.food_days >= 2:
            self.visited = week
            reserve = self.buffer(sim)
            sim.recruit("tavern")
            if len(sim.guild.roster) < self.TARGET:
                sim.recruit("prison", reserve=reserve)
            sim.seat_extras(self.FIGHTERS)
        super().step(sim)


class Games(Balanced):
    """Balanced, but its adventure is the arena's ladder instead of the Wilds: the champion
    first (it opens the Games), then whichever Games bout pays best."""
    name = "games"

    def adventure(self, sim):
        if not self.ready(sim):
            return False
        size, level = len(sim.members), sim.fight_level
        options = {}
        spare = self.BUFFER_DAYS * size * cheapest_food_price()
        for kind in ("brawl", "ctf") if sim.champion_beaten else ("champion",):
            bout = act.BOUTS[kind]()
            if sim.money < bout.entry * size + spare:
                continue
            p, _, _ = sim.library.stats(kind, level, size, sim.skill)
            options[kind] = p * bout.purse / size - bout.entry
        if not options:
            return False
        kind = max(options, key=options.get)
        if options[kind] <= 0 and kind != "champion":
            return False
        if sim.bout(kind) is None:
            return False
        sim.heal()
        return True


class Climber(Games):
    """Follows the XP: each day it does the rung that still teaches. The yard until it stops
    (work 1, or 2 with an Axe), the Scrapper until combat 1, then the Games (the champion first)
    from combat 1, and the Wilds hunt once the squad is combat 3; the yard pays in between.
    The talents it picks (Piecework, Hardy ...) come from `TALENT_PLAN`."""
    name = "climber"
    GAMES_LEVEL = 0.6                 # two of three at combat 1: the slowest member catches up in the Games
    WILDS_LEVEL = 3

    def ready(self, sim):
        return (sim.mean_combat >= self.GAMES_LEVEL and not sim.hurt and sim.food_days >= 3
                and sim.money >= self.buffer(sim))

    def adventure(self, sim):
        if sim.mean_combat >= self.WILDS_LEVEL and self.ready(sim):
            sim.hunt()
            sim.heal()
            return True
        return super().adventure(sim)


class Claimer(Balanced):
    """Balanced, but its adventure is the Wilds claim: scout, clear, fence, sweep, then hold it.
    Starts once the squad is combat 2 and can pay for the trip."""
    name = "claimer"

    def buffer(self, sim):
        """The gear waits for the trip's food and fence Lumber to be set aside first."""
        return super().buffer(sim) + sim.claim_cost()

    def adventure(self, sim):
        if sim.guild.wilds_claim_stage == "ESTABLISHED" and sim.guild.wilds_claim_owner == "guild":
            if not (sim.food_days >= 3 and not sim.hurt):
                return False
        elif not self.ready(sim):
            return False
        sim.claim_run()
        sim.heal()
        return True


class Human(Balanced):
    """`balanced`, but every decision threshold is the one measured from recorded play
    (`scripts/play_analysis.py --out`, loaded with `--profile`): the cash held when the Axe was
    bought, the days of food shopped at and up to, the HP and level before a bout or a hunt, the
    day the yard was left. A threshold the recordings never showed keeps `balanced`'s rule."""
    name = "human"
    profile: ClassVar[dict] = {}

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            cls.profile = json.load(f)

    def want(self, key, default):
        return self.profile.get(key, default)

    @staticmethod
    def hp_frac(sim):
        return statistics.mean(max(0, u.hp) / u.hp_max for u in sim.members)

    def upkeep(self, sim):
        sim.keep_fed(self.want("food_low_days", FOOD_LOW_DAYS),
                     self.want("food_target_days", FOOD_TARGET_DAYS), at_low=True)
        self.buy_axes(sim)
        if sim.badly_hurt:
            sim.heal()

    def buy_axes(self, sim):
        axe = items.get(MILESTONE_WEAPON).price
        lacking = [u for u in sim.members if economy.lumber_level(u) == 0]
        if not lacking or sim.food_days < self.want("axe_food_days", AXE_BUFFER_DAYS):
            return
        if sim.money / len(sim.members) < self.want("axe_cash_per_member", axe):
            return
        with sim.market() as shop:
            for u in lacking:
                if sim.money < axe:
                    break
                shop.buy(u, MILESTONE_WEAPON)

    def level_up_bout(self, sim, spare):
        if (sim.min_combat >= 1 or self.hp_frac(sim) < self.want("bout_min_hp", 1.0)
                or sim.money < self.stake(sim)
                or sim.money / len(sim.members) < self.want("bout_cash_per_member", 0)):
            return False
        sim.bout()
        return True

    def ready(self, sim):
        return (sim.mean_combat >= self.want("hunt_min_level", 2)
                and self.hp_frac(sim) >= self.want("hunt_min_hp", 1.0)
                and sim.food_days >= 3 and sim.money >= self.buffer(sim))

    def step(self, sim):
        if sim.elapsed < self.want("yard_leave_day", 0) - 1:
            self.upkeep(sim)
            self.lumber_day(sim)
            return
        super().step(sim)


class Rush(Human):
    """The line two recorded runs took to the day-30 milestone in 11-14 days: sell the starting
    kit and buy Axes, work the yard until the Champion's stake is in hand (level does not
    matter), beat him, wear armor, hunt the Wilds once for a Hide, buy Paper and Ink at the
    Library, craft the Dictionary the Library's one-off mission wants, and only then the rest of
    the gear and the strongbox. Thresholds come from `--profile` like `human`'s."""
    name = "rush"
    HIDE = "1sqm Hide"
    DICTIONARY = "Dictionary of Ankarin"
    HUNT_HOURS = 6
    CRAFT_CHUNK = 4
    CRAFT_CHUNKS = 8

    def __init__(self):
        self.opened = False
        self.dictionary_done = False
        self.mission = None

    def open(self, sim):
        """Day 0: the starting kit that is not food goes to the market, then Axes."""
        for u in sim.members:
            for name, qty in u._base_inventory:
                if not items.is_coin(name) and not items.is_food(name):
                    sim.sellable[name] += qty
        with sim.market() as shop:
            shop.sell_loot()
        self.buy_axes(sim)

    def buffer(self, sim):
        return self.BUFFER_DAYS * len(sim.members) * cheapest_food_price()

    def gear(self, sim):
        if self.dictionary_done:
            return super().gear(sim)
        wants = [u for u in sim.members
                 if not _owns_at_least(u, MILESTONE_ARMOR, getattr(u, "equipped_armor", None) or "")]
        price = items.get(MILESTONE_ARMOR).price
        wants = [u for u in wants if sim.money >= self.buffer(sim) + price]
        if not wants:
            return
        with sim.market() as shop:
            for u in wants:
                if sim.money >= self.buffer(sim) + price:
                    shop.buy(u, MILESTONE_ARMOR, zone="armor")

    def has_hide(self, sim):
        return any(u.count_of(self.HIDE) for u in sim.members)

    def hunt_ready(self, sim):
        return (sim.mean_combat >= self.want("hunt_min_level", 0)
                and self.hp_frac(sim) >= self.want("hunt_min_hp", 0.9)
                and sim.food_days >= 2 and sim.money >= self.buffer(sim))

    def dictionary_cost(self):
        return sum(items.get(n).price for n in economy.LIBRARY_SUPPLIES)

    def make_dictionary(self, sim):
        """Paper and Ink at the Library, the Hide to the crafter, accept the mission, craft, hand in."""
        guild = sim.guild
        crafter = max(sim.members, key=lambda u: u.mod_intelligence)
        holder = next(u for u in sim.members if u.count_of(self.HIDE))
        sim.goto("library")
        shop = MarketScreen(None, guild, sim.members, world.node("library"), lambda: None)
        for name in economy.LIBRARY_SUPPLIES:
            if not crafter.count_of(name):
                shop.qty[name] = 1
                shop.selected = [("stock", name)]
                shop._buy(crafter, [name])
        if holder is not crafter:
            holder.remove_named(self.HIDE, 1)
            crafter.give_to_pack(self.HIDE)
        if self.mission is None:
            self.mission = missions.accept(guild, crafter, missions.LIBRARY_DICTIONARY)
        mission = self.mission
        for _ in range(self.CRAFT_CHUNKS):
            guild.crafting_shift(crafter, self.DICTIONARY, self.CRAFT_CHUNK)
            if crafter.count_of(self.DICTIONARY):
                break
        if missions.can_turn_in(guild, mission):
            missions.turn_in(guild, mission)
            self.dictionary_done = True
        sim.snap()

    def step(self, sim):
        if not self.opened:
            self.opened = True
            self.open(sim)
        self.upkeep(sim)
        if not sim.champion_beaten:
            stake = act.BOUTS["champion"]().entry * len(sim.members)
            if sim.money >= stake and sim.bout("champion") is not None:
                sim.heal()
                return
        elif not self.has_hide(sim):
            self.gear(sim)
        if sim.champion_beaten and not self.dictionary_done:
            if not self.has_hide(sim):
                if self.hunt_ready(sim):
                    sim.hunt(self.HUNT_HOURS)
                    sim.sellable[self.HIDE] = 0
                    sim.heal()
                    return
            elif sim.money >= self.buffer(sim) + self.dictionary_cost():
                self.make_dictionary(sim)
                return
        if self.dictionary_done:
            Balanced.step(self, sim)
            return
        self.lumber_day(sim)


class Greedy(Policy):
    name = "greedy"

    def upkeep(self, sim):
        sim.keep_fed(low=0.5)
        if sim.hurt:
            sim.heal()

    def step(self, sim):
        self.upkeep(sim)
        if sim.min_combat < 1 and sim.money >= self.stake(sim):
            sim.bout()
            sim.heal()
        elif sim.food_days >= 1:
            sim.hunt()
            sim.heal()
        else:
            self.lumber_day(sim)


class MaxEV(Policy):
    name = "maxev"

    def step(self, sim):
        self.upkeep(sim)
        size, level = len(sim.members), sim.fight_level
        options = {"lumber": self.lumber_ev(sim)}
        bout = arena.scrapper_bout()
        if sim.money >= bout.entry * size and not sim.hurt:
            p, _, _ = sim.library.stats("arena", level, size, sim.skill)
            options["arena"] = p * bout.purse / size - bout.entry
        if not sim.hurt and sim.food_days >= 2:
            p, value, deaths = sim.library.stats("wilds", level, size, sim.skill)
            options["hunt"] = (p * value / size) / 2.0 - deaths * 4
        choice = max(options, key=options.get)
        if choice == "arena":
            sim.bout()
            sim.heal()
        elif choice == "hunt":
            sim.hunt()
            sim.heal()
        else:
            self.lumber_day(sim)

    @staticmethod
    def lumber_ev(sim):
        return statistics.mean(economy.lumber_pay(SHIFT_HOURS, economy.lumber_level(u))
                               for u in sim.members)


class Crafter(Policy):
    """The guild's best crafter buys inputs for a few batches, works a shift at the forge on a
    solo order (`solo.craft`) and sells the product at the market. The rest of the guild works
    the yard as a crew meanwhile; its wages pay for the next batches."""
    name = "crafter"
    BATCHES = 6

    def step(self, sim):
        self.seat(sim)
        sim.keep_fed()
        crafter = max(sim.members, key=lambda u: u.mod_intelligence)
        recipe = self.pick(sim, crafter)
        if recipe is None:
            self.lumber_day(sim)
            return
        with sim.market() as shop:
            shop.sell_loot()
            self.stock_up(sim, shop, crafter, recipe)
        need = items.CRAFTING_RECIPES[recipe].materials
        if crafter.crafting_target != recipe and not all(crafter.count_of(m) for m in need):
            self.lumber_day(sim)                    # too poor for a batch: the floor job
            return
        sim.goto("city")
        ok, _ = solo.craft(sim.guild, sim.group, crafter, recipe, SHIFT_HOURS)
        if not ok:
            self.lumber_day(sim)
            return
        sim.run_order(sim.group.order)
        target = items.CRAFTING_RECIPES[recipe].target
        sim.sellable[target] = max(sim.sellable[target], crafter.count_of(target))
        sim.snap()
        sim.sleep()

    @staticmethod
    def seat(sim):
        """The best crafter stays with the main group; everyone else becomes the yard crew."""
        if sim.crew is not None or len(sim.members) < 2:
            return
        members = sim.main.members
        members.insert(0, members.pop(members.index(max(members, key=lambda u: u.mod_intelligence))))
        sim.seat_extras(1)

    @staticmethod
    def pick(sim, crafter):
        """The known recipe that sells best per hour of work, or None if none sells at a profit."""
        best, best_rate = None, 0.0
        deal = MarketScreen(None, sim.guild, sim.members, world.node("market"), lambda: None).deal
        for name in crafter.known_recipes:
            recipe = items.CRAFTING_RECIPES.get(name)
            if recipe is None or not all(economy.freely_buyable(m) for m in recipe.materials):
                continue
            margin = (recipe.yield_qty * economy.sell_price(recipe.target, deal)
                      - sum(economy.buy_price(m, deal) for m in recipe.materials))
            rate = margin / (items.recipe_goal(recipe) / craft_level.AVG_ROLL)
            if rate > best_rate:
                best, best_rate = name, rate
        return best

    @classmethod
    def stock_up(cls, sim, shop, unit, recipe):
        need = Counter(items.CRAFTING_RECIPES[recipe].materials)
        reserve = FOOD_LOW_DAYS * len(sim.guild.roster) * cheapest_food_price()
        for _ in range(cls.BATCHES - min(unit.count_of(m) // q for m, q in need.items())):
            if any(sim.guild.shop("market").stock.get(m, 1) < q for m, q in need.items()):
                break
            cost = sum(economy.buy_price(m, shop.screen.deal) * q for m, q in need.items())
            if sim.money < cost + reserve:
                break
            spent = [shop.buy(unit, m, q) for m, q in need.items()]
            sim.input_spend += sum(spent)
            if not all(spent):
                break


POLICIES = {cls.name: cls for cls in (Lumber, Cautious, Balanced, Games, Climber, Claimer, Grower, Human, Rush, Greedy, MaxEV, Crafter)}


# --------------------------------------------------------------------------- #
# running guilds and reporting                                                #
# --------------------------------------------------------------------------- #
@dataclass
class Result:
    policy: str
    seed: int
    wiped: bool
    members_start: int
    members_end: int
    money: dict = field(default_factory=dict)      # day -> total copper
    combat: dict = field(default_factory=dict)
    work: dict = field(default_factory=dict)
    milestone_day: float | None = None
    starved: int = 0
    crashed: str = ""
    start_money: int = 0
    milestone_met: bool = False                    # at the last mark: alive and able to afford it all
    sold: int = 0
    input_spend: int = 0
    armor: dict = field(default_factory=dict)      # day -> share of members in Studded Leather or better
    chest: dict = field(default_factory=dict)      # day -> the strongbox is rented
    curve: dict = field(default_factory=dict)      # day -> copper per member
    traits: list = field(default_factory=list)     # per starting member: see `member_traits`
    claim_day: float | None = None                 # the day the Claim became the guild's
    claim_stage: str = "NONE"                      # how far the Claim campaign got
    claim_owner: str = ""
    claim_lumber: int = 0                          # Lumber the garrison gathered and brought home
    treated: int = 0                               # copper paid to the Medic
    champion: bool = False                         # the Pit's champion was beaten (the Games open)
    bouts: int = 0                                 # staked arena bouts fought
    recruited: int = 0                             # strangers who signed on
    pitches: int = 0
    bail: int = 0                                  # copper paid in bail
    alive: dict = field(default_factory=dict)      # day -> roster size, for a guild that grew
    xp: int = 0                                    # combat XP the survivors gained


def at_day(snaps, day):
    """The first snapshot at or after `day`, else the last one."""
    for s in snaps:
        if s.day >= day:
            return s
    return snaps[-1]


def run_guild(policy_name, *, days=30, seed=0, size=3, level=0, skill=None, library=None,
              restock=None, recipes=(), marks=(7, 30), capital=0, assets=(), medic=False, mixed=False, talents=True):
    sim = Sim(POLICIES[policy_name](), size=size, level=level, skill=skill, seed=seed,
              library=library, restock=restock, recipes=recipes, capital=capital, assets=assets,
              medic=medic, horizon=days, mixed=mixed, talents=talents)
    traits = [member_traits(u) for u in sim.members]
    wiped, crashed, wiped_at = False, "", None
    try:
        for _ in range(STEP_LIMIT):
            if sim.elapsed >= days:
                break
            sim.policy.step(sim)
    except Wiped:
        wiped, wiped_at = True, sim.elapsed
    except RuntimeError as exc:
        crashed = str(exc)
    res = Result(policy_name, seed, wiped, size, len(sim.guild.roster),
                 milestone_day=sim.milestone_day, starved=sim.starved, crashed=crashed,
                 start_money=sim.start_money, sold=sim.sold_total,
                 input_spend=sim.input_spend, traits=traits, claim_day=sim.claim_day,
                 claim_stage=sim.guild.wilds_claim_stage, claim_owner=sim.guild.wilds_claim_owner,
                 claim_lumber=sim.claim_lumber, treated=sim.treated,
                 champion=sim.champion_beaten, bouts=sim.bouts, recruited=sim.recruited,
                 pitches=sim.pitches, bail=sim.bail_spent,
                 xp=sum(u.combat_xp for u in sim.guild.roster) - sim.start_xp)
    def dead_by(day):
        return wiped_at is not None and wiped_at <= day

    for d in marks:
        if dead_by(d):
            res.money[d] = res.combat[d] = res.work[d] = res.armor[d] = 0
            res.chest[d] = False
        elif sim.snapshots:
            s = at_day(sim.snapshots, d)
            res.money[d], res.combat[d], res.work[d] = s.money, s.combat, s.work
            res.armor[d], res.chest[d] = s.armored / max(1, s.alive), s.chest
            if sim.recruited:
                res.alive[d] = s.alive
    for d in CURVE_DAYS:
        if d <= days:
            snap = at_day(sim.snapshots, d)
            res.curve[d] = 0 if dead_by(d) else snap.money / (snap.alive if sim.recruited else size)
    if sim.snapshots and not dead_by(marks[-1]):
        last = at_day(sim.snapshots, marks[-1])
        res.milestone_met = last.money >= last.gear_cost
    return res


def summarize(results, marks=(7, 30)):
    """One policy's guilds -> the numbers the report prints."""
    n = len(results)
    out = {"guilds": n, "wiped": sum(r.wiped for r in results) / n,
           "lost": statistics.mean(r.members_start - r.members_end for r in results),
           "hungry": sum(r.starved > 0 for r in results) / n,
           "crashed": sum(bool(r.crashed) for r in results)}
    for d in marks:
        money = [r.money[d] / r.alive.get(d, r.members_start) for r in results if d in r.money]
        out[f"money{d}"] = statistics.median(money) if money else 0.0
        out[f"combat{d}"] = statistics.mean(r.combat[d] for r in results if d in r.combat) if money else 0.0
    out["armor"] = statistics.mean(r.armor.get(marks[-1], 0.0) for r in results)
    out["chest"] = sum(bool(r.chest.get(marks[-1])) for r in results) / n
    out["curve"] = {d: statistics.median(r.curve[d] for r in results if d in r.curve)
                    for d in CURVE_DAYS if any(d in r.curve for r in results)}
    done = [r.milestone_day for r in results if r.milestone_day is not None]
    out["milestone"] = sum(r.milestone_met for r in results) / n
    out["milestone_day"] = statistics.median(done) if done else None
    claimed = [r.claim_day for r in results if r.claim_day is not None]
    out["claim"] = len(claimed) / n
    out["claim_day"] = statistics.median(claimed) if claimed else None
    out["seized"] = sum(r.claim_owner == "seized" for r in results) / n
    out["claim_lumber"] = statistics.mean(r.claim_lumber for r in results)
    out["champion"] = sum(r.champion for r in results) / n
    out["treated"] = statistics.mean(r.treated for r in results)
    out["bouts"] = statistics.mean(r.bouts for r in results)
    out["recruited"] = statistics.mean(r.recruited for r in results)
    out["bail"] = statistics.mean(r.bail for r in results)
    out["xp"] = statistics.mean(r.xp for r in results) / results[0].members_start
    return out


def adventure_report(table, label):
    """What a squad past its first week does with the arena's ladder, the Claim and the Medic."""
    lines = [f"== {label}",
             f"{'policy':<10}{'champion':>9}{'bouts':>7}{'cXP/mbr':>9}{'claim':>7}{'on day':>8}{'seized':>8}{'lumber':>8}{'medic $':>9}{'recruits':>9}{'bail $':>8}"]
    for name, s in table.items():
        day = f"{s['claim_day']:.0f}" if s["claim_day"] is not None else "-"
        lines.append(f"{name:<10}{s['champion'] * 100:>8.0f}%{s['bouts']:>7.1f}{s['xp']:>9.1f}"
                     f"{s['claim'] * 100:>6.0f}%{day:>8}{s['seized'] * 100:>7.0f}%"
                     f"{s['claim_lumber']:>8.1f}{s['treated']:>9.0f}{s['recruited']:>9.1f}{s['bail']:>8.0f}")
    lines.append("   (champion: guilds that beat the champion; bouts / cXP: arena bouts fought and "
                 "combat XP gained per member; claim: guilds that made the Claim theirs, on the "
                 "median day; seized: lost it after; lumber: gathered by the garrison; medic $: "
                 "paid per guild; recruits: strangers who signed on; bail: paid at the prison)")
    return chr(10).join(lines)


def report(table, marks, label):
    head = (f"{'policy':<10}{'wiped':>7}{'hungry':>8}{'lost':>6}"
            + "".join(f"{f'$/mbr d{d}':>10}{f'cmb d{d}':>8}" for d in marks)
            + f"{'armor':>7}{'chest':>7}{'milestone':>11}{'first day':>10}")
    lines = [f"== {label}", head]
    for name, s in table.items():
        first = f"{s['milestone_day']:.0f}" if s["milestone_day"] is not None else "-"
        lines.append(f"{name:<10}{s['wiped'] * 100:>6.0f}%{s['hungry'] * 100:>7.0f}%{s['lost']:>6.1f}"
                     + "".join(f"{s[f'money{d}']:>10.0f}{s[f'combat{d}']:>8.1f}" for d in marks)
                     + f"{s['armor'] * 100:>6.0f}%{s['chest'] * 100:>6.0f}%"
                     + f"{s['milestone'] * 100:>10.0f}%{first:>10}")
    return "\n".join(lines)


def member_traits(unit):
    """What a ranking groups a member by: race, occupation, languages known, an attribute's
    modifier (`STR mod` ...) and whether they start with an Axe (the yard pays 4/3 for it)."""
    traits = {"race": unit.race["name"], "occupation": unit.occupation["name"],
              "languages": len(unit.languages), "own Axe": economy.lumber_level(unit) > 0}
    for attribute in data.ATTRIBUTES:
        traits[f"{attribute[:3].upper()} mod"] = data.mod(getattr(unit, attribute))
    return traits


def rank_traits(results, day):
    """Net copper per member and survival, averaged by each trait the starting members had.
    A guild's outcome is shared by its members, so a trait shows only on average, over many
    guilds. -> {trait name: {value: (net per member, survival, samples)}}"""
    groups = {}
    for r in results:
        if day not in r.money:
            continue
        net = (r.money[day] - r.start_money) / r.members_start
        alive = r.members_end / r.members_start
        for traits in r.traits:
            for trait, value in traits.items():
                groups.setdefault(trait, {}).setdefault(value, []).append((net, alive))
    return {trait: {value: (statistics.mean(n for n, _ in rows),
                            statistics.mean(a for _, a in rows), len(rows))
                    for value, rows in table.items()}
            for trait, table in groups.items()}


def ranking_report(ranked, label, top=5):
    lines = [f"== ranking: {label} (net copper per member, survival, members sampled)"]
    for trait, table in ranked.items():
        order = sorted(table.items(), key=lambda kv: kv[1][0], reverse=True)
        spread = order[0][1][0] - order[-1][1][0]
        lines.append(f"  by {trait}: best-to-worst spread ${spread:.0f}")
        shown = order if len(order) <= 2 * top else order[:top] + [None] + order[-top:]
        for entry in shown:
            if entry is None:
                lines.append("      ...")
                continue
            value, (net, alive, n) = entry
            lines.append(f"      {value!s:<14}{net:>8.1f}{alive * 100:>7.0f}%{n:>6}")
    return "\n".join(lines)


def apply_overrides(sets, prices):
    """What-if knobs: `--set economy.LUMBER_WAGE=2` and `--price "Studded Leather=40"`."""
    import importlib
    from dataclasses import replace
    for text in sets:
        path, value = text.split("=")
        module, attr = path.rsplit(".", 1)
        setattr(importlib.import_module(f"gartok.{module}"), attr, int(value) if value.lstrip("-").isdigit() else float(value))
    for text in prices:
        name, value = text.split("=")
        item = items.get(name)
        new = replace(item, price=int(value))
        items._REGISTRY[item.id] = new
        for key, held in list(items._LOOKUP.items()):
            if held.id == item.id:
                items._LOOKUP[key] = new


def restock_sweep(settings, *, policy, guilds, days, skill, recipes, size, level, seed, capital):
    """One policy under each shelf setting (`inf` = infinite stock, today's rule): how much a
    specialist guild pulls out of the market a day, net of the inputs it buys, against what the
    same guild would earn at the lumber yard. The table that sizes the restock limiter."""
    library = FightLibrary()
    squad_lumber = size * economy.LUMBER_WAGE * (SHIFT_HOURS // economy.LUMBER_BLOCK_HOURS)
    lines = [(f"== restock sweep: {policy}, {guilds} guilds of {size}, {days} days, "
              f"{capital} copper to start"),
             f"   a squad at the lumber yard earns ${squad_lumber}/day",
             f"{'shelves':<10}{'sales':>8}{'inputs':>8}{'profit/d':>10}{'x lumber':>10}{'wiped':>7}"]
    for setting in settings:
        restock = Restock.parse(setting) if setting != "inf" else None
        runs = [run_guild(policy, days=days, seed=seed + i, size=size, level=level, skill=skill,
                          library=library, restock=restock, recipes=recipes, marks=(days,),
                          capital=capital)
                for i in range(guilds)]
        sold = statistics.mean(r.sold for r in runs) / days
        spent = statistics.mean(r.input_spend for r in runs) / days
        profit = sold - spent
        lines.append(f"{setting:<10}{sold:>8.1f}{spent:>8.1f}{profit:>10.1f}"
                     f"{profit / squad_lumber:>10.2f}{sum(r.wiped for r in runs) / len(runs) * 100:>6.0f}%")
    return chr(10).join(lines)


def curve_report(table):
    days = sorted({d for s in table.values() for d in s["curve"]})
    lines = ["== sustain curve: median copper per member, by day",
             f"{'policy':<10}" + "".join(f"{f'd{d}':>7}" for d in days)]
    for name, s in table.items():
        lines.append(f"{name:<10}" + "".join(f"{s['curve'].get(d, float('nan')):>7.0f}" for d in days))
    return chr(10).join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--policies", default="lumber,cautious,balanced,greedy,maxev")
    ap.add_argument("--guilds", type=int, default=40)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--size", type=int, default=3)
    ap.add_argument("--level", type=int, default=0)
    ap.add_argument("--skill", type=float, default=None,
                    help="a player's win chance in every fight (default: the AI's own)")
    ap.add_argument("--restock", default=None, metavar="TARGET:PER_DAY",
                    help="finite shelves: every free market item holds TARGET, refills PER_DAY")
    ap.add_argument("--recipes", default="", help="comma list given to every member (crafter)")
    ap.add_argument("--assets", default="",
                    help="comma list the guild starts with and must keep: house, Donkey, Ox, Horse, Cart")
    ap.add_argument("--medic", action="store_true",
                    help="a Medic at the City heals for potions at a discount, in an hour")
    ap.add_argument("--mixed", action="store_true",
                    help="hurt members work the yard while they heal (1 HP a night) instead of resting")
    ap.add_argument("--medic-factor", type=float, default=None, metavar="F",
                    help=f"the Medic's price as a share of the potions ({act.MEDIC_PRICE_FACTOR})")
    ap.add_argument("--capital", type=int, default=0,
                    help="extra copper at the start, for a guild past its first week")
    ap.add_argument("--profile", default=None, metavar="JSON",
                    help="thresholds measured from recorded play (play_analysis.py --out) for the human policy")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--restock-sweep", default=None, metavar="inf,TARGET:PER_DAY,...",
                    help="run the first policy under each shelf setting and compare")
    ap.add_argument("--curve", action="store_true",
                    help="also print each policy's copper per member by day")
    ap.add_argument("--ranking", action="store_true",
                    help="rank races, occupations, CHA and languages by what the guilds earned")
    ap.add_argument("--set", action="append", default=[], metavar="MODULE.NAME=VALUE",
                    help="what-if: override a gartok constant, e.g. economy.LUMBER_WAGE=2")
    ap.add_argument("--price", action="append", default=[], metavar="ITEM=VALUE",
                    help="what-if: override an item's price, e.g. \"Studded Leather=40\"")
    args = ap.parse_args()
    apply_overrides(args.set, args.price)
    if args.profile:
        Human.load(args.profile)
    if args.medic_factor is not None:
        act.MEDIC_PRICE_FACTOR = args.medic_factor
    marks = tuple(d for d in (7, 30) if d <= args.days) or (args.days,)
    recipes = [r for r in args.recipes.split(",") if r]
    assets = [a for a in args.assets.split(",") if a]
    if args.restock_sweep:
        print(restock_sweep(args.restock_sweep.split(","), policy=args.policies.split(",")[0],
                            guilds=args.guilds, days=args.days, skill=args.skill, recipes=recipes,
                            size=args.size, level=args.level, seed=args.seed,
                            capital=args.capital))
        return
    restock = Restock.parse(args.restock) if args.restock else None
    library = FightLibrary()
    table, ranked = {}, []
    for name in args.policies.split(","):
        results = [run_guild(name, days=args.days, seed=args.seed + i, size=args.size,
                             level=args.level, skill=args.skill, library=library,
                             restock=restock, recipes=recipes, marks=marks, capital=args.capital,
                             assets=assets, medic=args.medic, mixed=args.mixed)
                   for i in range(args.guilds)]
        table[name] = summarize(results, marks)
        if args.ranking:
            ranked.append(ranking_report(rank_traits(results, marks[-1]),
                                         f"{name}, day {marks[-1]}"))
    skill = "the AI plays" if args.skill is None else f"a player wins {args.skill * 100:.0f}%"
    print(report(table, marks, f"{args.guilds} guilds of {args.size}, level {args.level}, "
                               f"{skill}" + (f", shelves {args.restock}" if restock else "")))
    if args.curve:
        print("\n" + curve_report(table))
    if any(s["claim"] or s["champion"] or s["treated"] or s["recruited"] for s in table.values()):
        print("\n" + adventure_report(table, "the arena's ladder, the Claim and the Medic"))
    for text in ranked:
        print("\n" + text)


if __name__ == "__main__":
    main()

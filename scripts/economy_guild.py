"""Economy sim v2, layer 2: a whole guild lives N days under a policy.

Plan: docs/plans/economy_sim_v2.md. The real `Guild` lives the days: the real order engine
(`orders` + `campaign.advance`) walks it between places and ticks the clock, the real daily
upkeep feeds it, rots its food and heals it, and the market is the real `MarketScreen`, so
prices, haggling, finite stock and the market's cash (`Guild.shop(node_id).cash`) all bite. Work and
tavern shifts, hunts and rests go through the same calls the game makes.

The one stand-in is the fight. A policy only decides *what* to do; fights are drawn from a
library of real battles (`Battle` + `ai`, folded in by `campaign.absorb_battle`) played ahead
of time for each (kind, level, party size). `--skill` lifts the AI's win rate to a player's
(`economy_activities.player_odds`: they turn that share of the AI's losses into wins), drawing a
won or a lost sample, because the AI plays worse than a person.

A policy is a class with `step(sim)`; each step spends time. The game has no fatigue, so a
shift follows a shift and only the wounded rest. Policies:

  lumber    the floor: the yard's wage, shift after shift, and food
  balanced  the game played as the author plays it (see the class): the sprint to the day-30
            milestone, then the Pit, a recruit and the Wilds hunt as the income

The gathering probes (`gatherer`, `miner`, `miner_wage`) do not play the game: they measure a
licence against its wage for the report's GATHERING section (`gather_payback`).

    python scripts/economy_guild.py                         # lumber and balanced, 7 and 30 days
    python scripts/economy_guild.py --guilds 60 --skill 0.5 --ranking
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(SCRIPTS))

import economy_activities as act

from gartok import (
    animals,
    campaign,
    data,
    dialogue,
    economy,
    encounters,
    factions,
    forced,
    gather,
    hunt,
    items,
    library_screen,
    magic,
    matchup,
    medic,
    missions,
    names,
    orders,
    recorder,
    recruit,
    rest,
    rite,
    vocations,
    wagon,
    world,
)
from gartok.clock import SECONDS_PER_DAY
from gartok.group import NORMAL
from gartok.guild import Guild
from gartok.market_screen import MarketScreen
from gartok.prison_screen import BAIL_BONUS
from gartok.scenario import ErmosScenario, Scenario

SHIFT_HOURS = 16                     # a work shift; the other 8 h of the day are sleep
SLEEP_HOURS = 24 - SHIFT_HOURS        # a night's rest, for the wounded: the game has no fatigue
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
# Brisk Hands, Steady Pace heals on the job), then hauls, rests, travels and performs better;
# the combat track keeps the squad alive
TALENT_PLAN = {
    "work": ("carrier", "piecework", "brisk_hands", "steady_pace", "heavy_haul",
             "sturdy", "restful_sleep", "deep_reserves", "observant", "beast_whisperer",
             "pathfinder", "field_medic", "triage", "charismatic", "fixer", "troubadour"),
    "combat": ("tough", "hardy", "bulwark", "recovery"),
}
PIT_MIN_HP = 0.8                     # the mean HP the author's recorded bouts started at
PIT_REST_HOURS = 24                  # unbroken rest after a bout: it wipes the Pit's non-lethal damage
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
CLAIM_KINDS = frozenset({"wilds_raid", "wilds_seizure", "wilds_retake"})
# the Claim's fights: (enemy level, enemy count)
CLAIM_FIGHTS = {
    "claim_clear": (economy.WILDS_CLAIM_CLEAR_LEVEL, economy.WILDS_CLAIM_CLEAR_SIZE),
    "claim_sweep": (economy.WILDS_CLAIM_SWEEP_LEVEL, economy.WILDS_CLAIM_SWEEP_SIZE),
    "raid": (economy.WILDS_RAID_LEVEL, economy.WILDS_RAID_SIZE),
}


NAKED = (None, None)                 # a library squad's kit: no armor, each its own starting weapon


def kit_of(party):
    """`(armor, weapon)` the fight library dresses a squad in for `party`: the armor most of them
    wear, and a weapon only when two in three hold the same one (else each keeps their own)."""
    armor, _ = Counter(getattr(u, "equipped_armor", None) for u in party).most_common(1)[0]
    weapon, held = Counter(u.equipped_weapon for u in party).most_common(1)[0]
    return armor, (weapon if held * 3 >= 2 * len(party) else None)


def as_levels(level):
    """A library key: `(combat, work)`. The racial level, and with it the hit dice, is the two
    added, so a combat-only squad and a squad that also works are not the same fighters."""
    return level if isinstance(level, tuple) else (level, level)


class FightLibrary:
    """Real battles for each (kind, levels, size), played once and cached. Kinds: the arena's
    bouts (`arena` the Scrapper, `champion`, `brawl`, `ctf`; non-lethal), `wilds` (a hunt's
    ambush), `road` (the Old Road), `gather:<node>` (a pack finding a crew gathering), and the Claim's `claim_clear`, `claim_sweep` and `raid`."""

    def __init__(self, samples=40):
        self.samples = samples
        self.cache = {}

    def pool(self, kind, level, size, kit=NAKED):
        key = (kind, as_levels(level), size) + ((kit,) if kit != NAKED else ())
        if key not in self.cache:
            state, names_state = random.getstate(), names._rng.getstate()
            random.seed(repr(key))      # the same fights for a key whatever ran first
            names._rng.seed(repr(key))  # names seed the foes' intel read (intel.py), so they change the fight
            try:
                self.cache[key] = [self._play(kind, key[1], size, kit) for _ in range(self.samples)]
            finally:
                random.setstate(state)
                names._rng.setstate(names_state)
        return self.cache[key]

    @staticmethod
    def _play(kind, level, size, kit=NAKED):
        squad = act.make_squad(size, level)
        armor, weapon = kit
        for u in squad:
            spend_picks(u)
            if armor:
                u.give_to_armor(armor)
            if weapon:
                u.give_to_hand(weapon)
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
            if kind.startswith("gather:"):
                node_id = kind.split(":", 1)[1]
                node, foes, scenario = world.node(node_id), gather.ambush_pack(node_id), Scenario()
            elif kind == "wilds":
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

    def draw(self, kind, level, size, rng, skill=None, kit=NAKED):
        """One sample: the AI's own mix, or a won / lost one at a player's odds
        (`act.player_odds`: a squad the AI wins more with, the player does too)."""
        pool = self.pool(kind, level, size, kit)
        if skill is None:
            return rng.choice(pool)
        wins = [s for s in pool if s.won]
        losses = [s for s in pool if not s.won]
        want_win = rng.random() < act.player_odds(len(wins) / len(pool), skill)
        chosen = (wins if want_win else losses) or pool
        return rng.choice(chosen)

    def relief(self, kind, level, size, skill=None, kit=NAKED):
        """How much of the AI's casualties in won fights a better player still takes (`act.relief`)."""
        pool = self.pool(kind, level, size, kit)
        return act.relief(sum(s.won for s in pool) / len(pool), skill)

    def stats(self, kind, level, size, skill=None, kit=NAKED):
        """(win chance, mean loot value, mean deaths) of a fight, for a policy to weigh."""
        pool = self.pool(kind, level, size, kit)
        wins = [s for s in pool if s.won]
        p = act.player_odds(len(wins) / len(pool), skill)
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
                 restock=None, recipes=(), capital=0, assets=(), medic=False, horizon=None, mixed=False, talents=True,
                 vocation=None):
        random.seed(seed)
        self.rng = random.Random(seed)
        squad = act.make_squad(size, level)
        for u in squad:
            u.recipes.extend(r for r in recipes if r not in u.recipes)
        if capital:
            squad[0].give_to_pack(items.COIN_ITEM, capital)
        self.guild = Guild(squad, node="city", vocation=vocation, leader=squad[0])
        self.main = self.guild.groups[0]
        self.main.stance = policy.stance
        self.crew = None                      # the group that works the yard while the squad is out
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
        self.languages_learned = 0
        self.mages_trained = 0
        self._stock_day = 0
        if restock:
            for name in dict.fromkeys(economy.MARKET_STOCK):
                if economy.freely_buyable(name):
                    self.guild.shop(economy.shop_of(name)).stock[name] = restock.target
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
        for node_id in economy.TOWN_SHOPS:
            shelves = self.guild.shop(node_id).stock
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
                if grp is not group and pend.kind not in CLAIM_KINDS and pend.kind != "ambush":
                    continue
                if pend.kind == "ambush":
                    self._road_fight(grp, pend)
                elif pend.kind == "gather_ambush":
                    self._gather_fight(grp, pend)
                elif pend.kind in CLAIM_KINDS:
                    self._claim_fight(grp, pend)
                elif pend.kind in forced.EVENTS:
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
            self.run_order(orders.travel(self.group, node_id, vocations.travel_mult(self.guild, self.group)))

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
    def recruit(self, node="tavern", reserve=0, limit=None):
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
            if limit is not None and len(guild.roster) >= limit:
                break
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
            crew.order = orders.travel(crew, "lumber_yard", vocations.travel_mult(self.guild, crew))
            return
        hurt = any(u.hp < u.hp_max for u in crew.members)
        crew.order = orders.rest(SLEEP_HOURS) if hurt else orders.work(self.guild, crew, SHIFT_HOURS)

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

    # -- advancement & education ------------------------------------------- #
    def study_language(self, language, student=None):
        """Put a student on a study order with a Dictionary of `language` until learned.
        Returns True if learned, False otherwise."""
        dict_name = f"Dictionary of {language}"
        holders = (*self.members, *getattr(self.group, "stores", ()))
        has_dict = any(u.has_item(dict_name) for u in holders)

        if not has_dict:
            if dict_name in library_screen.library_stock_dictionaries(self.guild):
                cost = items.get(dict_name).price
                if self.money >= cost + 20:
                    with self.market("library") as mkt:
                        mkt.buy(self.members[0], dict_name)
                    has_dict = any(u.has_item(dict_name) for u in self.members)

        if not has_dict:
            speakers = [u for u in self.guild.roster if language in u.languages]
            if speakers:
                crafter = max(speakers, key=lambda u: u.mod_intelligence)
                supplies = ("Paper", "Ink", "1sqm Hide")
                supplies_cost = sum(items.get(n).price for n in supplies if not crafter.count_of(n))
                if self.money >= supplies_cost + 20:
                    with self.market() as mkt:
                        for n in supplies:
                            if not crafter.count_of(n):
                                mkt.buy(crafter, n)
                    for _ in range(3):
                        self.guild.crafting_shift(crafter, dict_name, 4)
                        if crafter.count_of(dict_name):
                            break
                    has_dict = any(u.has_item(dict_name) for u in self.members)

        if not has_dict:
            return False

        candidates = [u for u in self.members if language not in u.languages]
        if not candidates:
            return False
        student = student or max(candidates, key=lambda u: u.mod_intelligence)

        self.keep_fed(target=16)
        magic.begin_study(student, language, (*self.members, *getattr(self.group, "stores", ())))
        self.goto("tavern")
        self.group.order = orders.garrison("study")

        for _ in range(16):
            if language in student.languages:
                break
            if self.food_days < 1 and self.money < economy.TAVERN_STUDY_COST_PER_DAY * self.mouths:
                break
            result = campaign.advance(self.guild, dt=24)
            self._refill_shelves()
            if result.wiped or self.guild.empty:
                raise Wiped
            self.snap()

        self.group.order = None
        magic.end_study(student)
        learned = language in student.languages
        if learned:
            self.languages_learned += 1
        return learned

    def initiate_mage(self, school, student=None):
        """Board a member at the sanctuary for `school` until initiated."""
        sanctuary_node = next((n for n, s in rite.SANCTUARY.items() if s == school), None)
        if not sanctuary_node:
            return False
        faction_id = rite.FACTION.get(school)
        if self.guild.reputation.get(faction_id, 0) < rite.REP_NEEDED:
            return False

        candidates = [u for u in self.members if school not in u.magic_sources]
        if not candidates:
            return False
        student = student or max(candidates, key=lambda u: u.mod_intelligence)

        if school == "faith" and not rite.paid(student, school):
            if not any(u.has_item(rite.HOLY_SYMBOL) for u in self.members):
                symbol_cost = items.get(rite.HOLY_SYMBOL).price
                if self.money >= symbol_cost:
                    with self.market() as mkt:
                        mkt.buy(student, rite.HOLY_SYMBOL)
                if not any(u.has_item(rite.HOLY_SYMBOL) for u in self.members):
                    return False

        self.keep_fed(target=25)
        self.goto(sanctuary_node)

        ok, _ = rite.begin(self.guild, self.group, student, school)
        if not ok:
            return False

        for _ in range(25):
            if school in student.magic_sources:
                break
            if self.food_days < 1 and self.money < rite.BOARD_PER_DAY * self.mouths:
                break
            result = campaign.advance(self.guild, dt=24)
            self._refill_shelves()
            if result.wiped or self.guild.empty:
                raise Wiped
            self.snap()

        student_group = self.guild.group_of(student)
        if student_group is not None and student_group is not self.group:
            self.guild.merge_groups(self.group, student_group)
        self.group.order = None
        done = school in student.magic_sources
        if done:
            self.mages_trained += 1
            spend_picks(student)
        return done

    # -- fights ------------------------------------------------------------ #
    def apply(self, sample, party, relief=1.0, kind=None):
        """Fold a drawn fight into the real guild: hurt, kill, level, then hand out the loot.
        `relief` thins the deaths of a won fight (see `FightLibrary.relief`). An arena bout's
        damage is non-lethal, as the game marks it (`campaign.absorb_battle`): a day's unbroken
        rest wipes it."""
        lethal = kind not in act.BOUTS
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
            before = unit.hp
            unit.hp = max(1, unit.hp - lost)
            if not lethal:
                unit.non_lethal_damage = min(unit.hp_max - unit.hp,
                                             unit.non_lethal_damage + before - unit.hp)
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

    @staticmethod
    def _levels(party):
        return (round(statistics.mean(u.combat_level for u in party)),
                round(statistics.mean(u.work_level for u in party)))

    def fight(self, kind, party):
        level = self._levels(party)
        kit = kit_of(party)
        sample = self.library.draw(kind, level, len(party), self.rng, self.skill, kit)
        relief = self.library.relief(kind, level, len(party), self.skill, kit)
        return sample, self.apply(sample, party, relief, kind)

    def talked_down(self, kind, group, pend):
        """The squad's AI talks first (`dialogue.ai_play`, weighing its odds in the fight):
        True when the talk settled the ambush without one."""
        enc = forced.encounter(self.guild, group, pend)
        if enc is None:
            return False
        party = list(group.members)
        odds, _, _ = self.library.stats(kind, self._levels(party), len(party), self.skill, kit_of(party))
        if dialogue.ai_play(enc, party, odds, self.rng).kind != "peace":
            return False
        forced.settle_talk(self.guild, group, pend)
        return True

    def _road_fight(self, group, pend):
        if self.talked_down("road", group, pend):
            return
        self.fight("road", list(group.members))
        forced.resolve_road_ambush(self.guild, group, pend)

    def _gather_fight(self, group, pend):
        if self.talked_down(f"gather:{group.node}", group, pend):
            return
        sample, survivors = self.fight(f"gather:{group.node}", list(group.members))
        forced.resolve_gather_ambush(self.guild, group, pend,
                                     SimpleNamespace(won=sample.won, survivors=survivors))

    def _claim_fight(self, group, pend):
        """A raid on the garrison, a seizure attempt or the fight to retake a seized claim."""
        sample, _ = self.fight("raid", list(group.members))
        forced.resolve(self.guild, group, pend, SimpleNamespace(won=sample.won))

    # -- places ------------------------------------------------------------ #
    def work_shift(self, hours=SHIFT_HOURS, node="lumber_yard"):
        self.goto(node)
        self.run_order(orders.work(self.guild, self.group, hours))

    def gather_shift(self, hours=SHIFT_HOURS, node="lumber_yard"):
        """A gathering shift (the guild must hold the node's licence); what the crew picks up is
        loot to sell."""
        self.goto(node)
        names = [name for name, _ in gather.TABLES[node]]
        held = {name: sum(u.count_of(name) for u in self.members) for name in names}
        self.run_order(orders.work(self.guild, self.group, hours, gather=True))
        for name in names:
            self.sellable[name] += max(0, sum(u.count_of(name) for u in self.members) - held[name])

    def buy_licence(self, node):
        self.goto(node)
        return self.guild.buy_licence(node, self.members)

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

    def bout_stake(self, kind="arena"):
        """What a bout costs to enter: the entry for each fighter fielded (`Bout.player_cap`)."""
        bout = act.BOUTS[kind]()
        return bout.entry * min(len(self.members), bout.player_cap)

    def bout(self, kind="arena"):
        """One staked bout (`act.BOUTS`: the Scrapper by default): stake, fight, and the purse to
        whoever the player picks. Beating the champion opens the Games."""
        bout = act.BOUTS[kind]()
        party = sorted(self.members, key=lambda u: (u.combat_level, u.hp / u.hp_max, u.hp_max),
                       reverse=True)[:bout.player_cap]
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
            outcome = SimpleNamespace(won=sample.won, arena_tier=bout, squad_size=len(party),
                                      player_kos=len(party) - len(survivors))
            factions.settle(self.guild, factions.Event("battle", node=world.node("arena"), outcome=outcome))
        return sample

    def hunt(self, hours=SHIFT_HOURS):
        """A day in the Wilds: walk there, hunt, an ambush now and then, walk back later."""
        self.arrive("hunt", "wilds")
        state = hunt.begin(self.guild, self.members, world.node("wilds"), self.main.stance,
                           hours_left=hours)
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
    def market(self, node_id=None):
        """A shopping stop. With no node the guild walks to whichever shop sells what it asks
        for first (`MarketVisit.buy`), or to the Market to sell."""
        return MarketVisit(self, node_id)

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
    """A round of the shops, through the real `MarketScreen`: it stands at one shop at a time
    and walks to the next when an item is not on the shelf it is at."""

    def __init__(self, sim, node_id=None):
        self.sim = sim
        self.node = None
        self._screen = None
        if node_id:
            self.go(node_id)

    def go(self, node_id):
        sim = self.sim
        sim.arrive("market", node_id)
        sim.crew_pay_in()
        crew = list(sim.crew.members) if sim.crew is not None else []
        self.node = world.node(node_id)
        self._screen = MarketScreen(None, sim.guild, sim.members + crew, self.node, lambda: None)

    @property
    def screen(self):
        if self._screen is None:
            self.go("market")
        return self._screen

    def stand_at(self, name):
        """Walk to the shop that sells `name`, unless the one we are at has it."""
        shop = self._screen._shop() if self.node is not None else None
        if shop is not None and name in shop.stock:
            return
        node_id = economy.shop_of(name)
        if node_id and (self.node is None or node_id != self.node.id):
            self.go(node_id)

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
            if sim.crew is None:                 # the crew was called in while the guild walked
                break
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

    def sell_round(self, nodes=economy.TOWN_SHOPS):
        """Sell the loot shop by shop through `nodes` until it is gone: one till refills only
        `MARKET_CASH_REGEN` a day, less than a crew's haul."""
        for node_id in nodes:
            if not any(self.sim.sellable.values()):
                break
            self.go(node_id)
            self.sell_loot()

    def buy(self, member, name, qty=1, zone="pack"):
        self.stand_at(name)
        screen = self.screen
        screen.qty[name] = qty
        screen.selected = [("stock", name)]
        before = sum(u.money for u in self.sim.members)
        screen._buy(member, [name], zone=zone)
        return before - sum(u.money for u in self.sim.members)

    def buy_food(self, target_days):
        """Buy the cheapest food up to `target_days` of rations, each unit into whichever
        pack has the most room, until the money, the shelf or the room runs out. A food covers
        only the days before it spoils (the meals nearest to spoiling are eaten first), so a
        long trip takes the cheap food for its first days and what keeps for the rest, never dearer
        than `TRIP_FOOD_PRICE`; what the shelves leave uncovered is the cheapest food, eaten stale."""
        sim = self.sim
        covered = sim.rations
        need = int(target_days * sim.mouths) - covered
        passes = [(n, int(min(target_days, items.get(n).lifespan or target_days) * sim.mouths))
                  for n in foods_by_price() if items.get(n).price <= TRIP_FOOD_PRICE]
        for name, keeps in passes + [(cheapest_food(), None)]:
            while need > 0 and (keeps is None or covered < keeps):
                roomy = sorted(sim.members, key=lambda u: u.carry_max - u.load, reverse=True)
                if sim.money < economy.buy_price(name, self.screen.deal) or not self.buy(roomy[0], name):
                    break
                need -= 1
                covered += 1


TRIP_FOOD_PRICE = items.get("Jerky").price   # the dearest ration bought for a trip; Compote is a cook's


def foods_by_price():
    return sorted((n for n in data.FOOD_ITEMS if n != "Rotten Food"), key=lambda n: items.get(n).price)


def cheapest_food():
    return foods_by_price()[0]


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
    stance = NORMAL                # the travel stance the group keeps for the whole run
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

    def work_node_shift(self, sim, node):
        """A day's shift at `node`: gathered once the guild holds the licence, bought when the
        cash covers it and the next meals, else the wage."""
        reserve = 3 * sim.mouths * cheapest_food_price()
        if (gather.can_gather(node) and not sim.guild.has_licence(node)
                and sim.money >= gather.licence_price(node) + reserve):
            sim.buy_licence(node)
        if sim.guild.has_licence(node):
            sim.gather_shift(node=node)
        else:
            sim.work_shift(node=node)

    def stake(self, sim):
        return sim.bout_stake()

    def step(self, sim):
        raise NotImplementedError


class Lumber(Policy):
    name = "lumber"

    def step(self, sim):
        self.upkeep(sim)
        self.lumber_day(sim)


class Gatherer(Policy):
    """The yard's day labour, but gathering once the licence is bought: Lumber and Fruit go to
    the Yard's own till every couple of days."""
    name = "gatherer"
    SELL_EVERY = 2

    def step(self, sim):
        self.upkeep(sim)
        self.work_node_shift(sim, "lumber_yard")
        day = sim.mouths * gather.rolls(SHIFT_HOURS)
        if sum(sim.sellable.values()) >= self.SELL_EVERY * day:
            with sim.market("lumber_yard") as shop:
                shop.sell_loot()
        if sum(sim.sellable.values()) >= 2 * self.SELL_EVERY * day:
            with sim.market() as shop:
                shop.sell_round()


class Miner(Policy):
    """Day labour at the Mine, a long walk past the Old Road: stock up in the City (a Pick each
    and food for the whole stay), walk there, work `STAY_DAYS` shifts, walk back. A guild that
    cannot afford the trip works the yard that day. The point is the break-even: the Mine pays
    more a day, the trip costs two days of walking and two rolls on the road."""
    name = "miner"
    STAY_DAYS = 6

    def __init__(self):
        self.left = 0

    def step(self, sim):
        if self.left > 0:
            if sim.food_days < 1:
                self.left = 0
                sim.goto("market")
                return
            self.work_node_shift(sim, "mine")
            if any(sim.sellable.values()):
                with sim.market("mine") as shop:
                    shop.sell_loot()
            self.left -= 1
            if self.left == 0:
                sim.goto("market")
            return
        if getattr(sim, self.HURT):
            sim.heal()
        if not self.provision(sim):
            self.lumber_day(sim)
            return
        self.left = self.STAY_DAYS
        sim.goto("mine")

    def provision(self, sim):
        """Sell the loot, buy a Pick for whoever lacks one while the trip's food stays covered,
        then the food. True when the stay is fed."""
        trip_food = (self.STAY_DAYS + 1) * sim.mouths * cheapest_food_price()
        pick = items.get(economy.WORK_TOOLS["mine"]).price
        with sim.market() as shop:
            shop.sell_round()
            for u in sim.members:
                if economy.work_level(u, "mine") == 0 and sim.money >= pick + trip_food:
                    shop.buy(u, economy.WORK_TOOLS["mine"])
            shop.buy_food(self.STAY_DAYS + 1)
        return sim.food_days >= self.STAY_DAYS


class MinerWage(Miner):
    """The Miner's trip with the wage only, never the licence: what gathering there is measured against."""
    name = "miner_wage"

    def work_node_shift(self, sim, node):
        sim.work_shift(node=node)


class Balanced(Policy):
    """The line the author plays. First the sprint to the day-30 milestone (the author's 14-day
    run): Axes on day one, the yard to work 2 (racial 1, a hit die), the Champion at combat 0, armor,
    the strongbox. Then the long game: the Pit until the squad can hunt, a recruit, the Wilds hunt
    as the income (its Hide makes the Library's Dictionary), the yard only while it heals."""
    name = "balanced"
    BUFFER_DAYS = 1
    WORK_GOAL = 2                        # work 2 with an Axe: racial level 1 in about five days
    HUNT_LEVEL = 0.33                    # one of three at combat 1: where the author's recorded runs
                                         # took the Champion and their first hunts (median)
    HUNT_HP = 0.8                        # the most wounded member, before a hunt or the Champion
    PIT_READY = 2                        # members at `WORK_GOAL` before the Pit: the author's runs went in
                                         # at work [2, 2, 1]
    OPENING_FOOD_DAYS = 1                # food kept back when the Axes are bought on day one
    FOOD_LOW_DAYS = 2                    # shop at two days left: a step (a walk and a shift) runs past one
    HUNT_SQUAD = 4                       # the author's runs signed a fourth before the first hunt; the
                                         # one that hunted with three lost it
    TRIO_LEVEL = 0.67                    # three hunt once two of them are combat 1 (the Pit, while no one signs)
    SELL_AT = 15                         # loot worth a day's wages for three is carried to the market
    HIDE = "1sqm Hide"
    DICTIONARY = "Dictionary of Ankarin"

    def __init__(self):
        super().__init__()
        self.opened = False
        self.dictionary_done = False
        self.mission = None
        self.pitched_week = -1

    def buffer(self, sim):
        return self.BUFFER_DAYS * len(sim.members) * cheapest_food_price()

    def sign_on(self, sim):
        """A free pitch at the tavern once a week, once the milestone is met (a recruit raises it),
        until the squad can hunt at `HUNT_SQUAD`."""
        week = recruit.current_week(sim.guild.clock)
        if (self.sprinting(sim) or len(sim.guild.roster) >= self.HUNT_SQUAD
                or week == self.pitched_week or sim.food_days < 1):
            return
        self.pitched_week = week
        sim.recruit("tavern", limit=self.HUNT_SQUAD)

    def hp_frac(self, sim):
        return min(max(0, u.hp) / max(1, u.hp_max) for u in sim.members)

    def has_hide(self, sim):
        return any(u.count_of(self.HIDE) for u in sim.members)

    def upkeep(self, sim):
        self.buy_axes(sim)
        sim.keep_fed(low=self.FOOD_LOW_DAYS, target=7.0, at_low=True)
        if not self.dictionary_done:
            sim.sellable[self.HIDE] = 0
        if sim.badly_hurt:
            sim.heal()

    def hunt_level(self):
        return self.HUNT_LEVEL

    @staticmethod
    def sprinting(sim):
        return sim.milestone_day is None

    def hunt_ready(self, sim):
        """Armored, healed, fed and with the buffer: the squad may leave the yard for the Wilds."""
        squad = len(sim.members) >= self.HUNT_SQUAD or sim.mean_combat >= self.TRIO_LEVEL
        return (squad and kit_of(sim.members)[0] is not None
                and sim.mean_combat >= self.hunt_level()
                and self.hp_frac(sim) >= self.HUNT_HP and sim.food_days >= 2
                and sim.money >= self.buffer(sim))

    def open(self, sim):
        for u in sim.members:
            for item in getattr(u, "_base_inventory", ()):
                if not items.is_coin(item.name) and not items.is_food(item.name):
                    sim.sellable[item.name] += item.qty
        with sim.market() as shop:
            shop.sell_loot()
            axe = items.get(MILESTONE_WEAPON).price
            reserve = self.OPENING_FOOD_DAYS * sim.mouths * cheapest_food_price()
            for u in sim.members:
                if economy.lumber_level(u) == 0 and sim.money >= axe + reserve:
                    shop.buy(u, MILESTONE_WEAPON)

    def make_dictionary(self, sim):
        crafter = max(sim.members, key=lambda u: u.mod_intelligence)
        holders = [u for u in sim.members if u.count_of(self.HIDE)]
        if not holders:
            return False
        holder = holders[0]
        sim.goto("library")
        shop = MarketScreen(None, sim.guild, sim.members, world.node("library"), lambda: None)
        for name in economy.LIBRARY_SUPPLIES:
            if not crafter.count_of(name):
                shop.qty[name] = 1
                shop.selected = [("stock", name)]
                shop._buy(crafter, [name])
        if holder is not crafter:
            holder.remove_named(self.HIDE, 1)
            crafter.give_to_pack(self.HIDE)
        if self.mission is None:
            self.mission = missions.accept(sim.guild, crafter, missions.LIBRARY_DICTIONARY)
        mission = self.mission
        for _ in range(8):
            sim.guild.crafting_shift(crafter, self.DICTIONARY, 4)
            if crafter.count_of(self.DICTIONARY):
                break
        if missions.can_turn_in(sim.guild, mission):
            missions.turn_in(sim.guild, mission)
            self.dictionary_done = True
        sim.snap()
        return True

    def gear(self, sim):
        """Armor first, then a weapon (the Axe in the pack is wielded, not bought twice), then the
        strongbox, whenever the buffer survives it."""
        for u in sim.members:
            if u.equipped_weapon != MILESTONE_WEAPON and u.count_of(MILESTONE_WEAPON):
                u.remove_named(MILESTONE_WEAPON, 1)
                u.give_to_hand(MILESTONE_WEAPON)
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

    def adventure(self, sim):
        """The risky day this policy prefers once the squad is ready; False if it did none."""
        if self.sprinting(sim) or not self.hunt_ready(sim):
            return False
        sim.hunt()
        if not self.dictionary_done:
            sim.sellable[self.HIDE] = 0
        if sum(economy.sell_price(n) * q for n, q in sim.sellable.items()) >= self.SELL_AT:
            with sim.market() as shop:
                shop.sell_loot()
        if sim.hurt:
            sim.heal()
        return True

    def pit_bout(self, sim):
        """A Scrapper bout on the way up. The Pit does not kill, so the squad goes in wounded (the
        mean HP the author bouts at, `PIT_MIN_HP`) and rests a day after, as the author did."""
        if (sim.min_combat >= 1 or sim.money < self.stake(sim) + self.buffer(sim)
                or statistics.mean(u.hp / u.hp_max for u in sim.members) < PIT_MIN_HP):
            return False
        sim.bout()
        if sim.hurt:
            sim.sleep(PIT_REST_HOURS)
        return True

    def climb(self, sim):
        """The way to the Champion: the yard to `WORK_GOAL`, the Pit to `hunt_level` (not while
        sprinting: work 2 beats him at combat 0), then the Champion himself. True when it spent
        the day."""
        if sum(u.work_level >= self.WORK_GOAL for u in sim.members) < self.PIT_READY:
            self.lumber_day(sim)
            return True
        if not self.sprinting(sim) and sim.mean_combat < self.hunt_level():
            if not self.pit_bout(sim):
                self.lumber_day(sim)
            return True
        if sim.champion_beaten:
            return (not self.sprinting(sim) and len(sim.members) < self.HUNT_SQUAD
                    and sim.mean_combat < self.TRIO_LEVEL and self.pit_bout(sim))
        stake = sim.bout_stake("champion")
        if self.hp_frac(sim) >= self.HUNT_HP and sim.money >= stake + self.buffer(sim):
            if sim.bout("champion") is not None:
                if sim.hurt:
                    sim.heal()
                return True
        self.lumber_day(sim)
        return True

    def step(self, sim):
        if not self.opened:
            self.opened = True
            self.open(sim)
        self.upkeep(sim)
        self.sign_on(sim)
        if not self.dictionary_done and self.has_hide(sim):
            dict_cost = sum(items.get(n).price for n in economy.LIBRARY_SUPPLIES)
            if sim.money >= self.buffer(sim) + dict_cost:
                if self.make_dictionary(sim):
                    return
        if self.climb(sim):
            return
        self.gear(sim)
        for school, faction in rite.FACTION.items():
            if (sim.guild.reputation.get(faction, 0) >= rite.REP_NEEDED
                    and not any(school in u.magic_sources for u in sim.members)
                    and sim.money >= self.buffer(sim) + 80):
                if sim.initiate_mage(school):
                    return
        if self.adventure(sim):
            return
        if self.show_pays(sim):
            for _ in range(SHIFT_HOURS // 4):
                sim.stage_show(4)
        else:
            self.lumber_day(sim)

    @staticmethod
    def show_pays(sim):
        """A day of shows replaces the squad's shift at the yard, so it has to pay more than it."""
        singers = [u for u in sim.members if economy.can_perform(u)]
        tips = sum(economy.perform_expected(1, u.mod_charisma) for u in singers)
        wages = sum(economy.lumber_pay(SHIFT_HOURS, economy.lumber_level(u)) for u in sim.members)
        return tips * SHIFT_HOURS > wages


POLICIES = {cls.name: cls for cls in (Lumber, Balanced, Gatherer, Miner, MinerWage)}


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
    milestone_met: bool = False                    # it could afford it all on some day by the last mark
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
    deeds: list = field(default_factory=list)      # faction deeds completed
    languages: int = 0                             # foreign languages learned through study
    mages: int = 0                                 # members initiated into magic


def at_day(snaps, day):
    """The first snapshot at or after `day`, else the last one."""
    for s in snaps:
        if s.day >= day:
            return s
    return snaps[-1]


def run_guild(policy_name, *, days=30, seed=0, size=3, level=0, skill=None, library=None,
              restock=None, recipes=(), marks=(7, 30), capital=0, assets=(), medic=False, mixed=False, talents=True,
              vocation=None):
    sim = Sim(POLICIES[policy_name](), size=size, level=level, skill=skill, seed=seed,
              library=library, restock=restock, recipes=recipes, capital=capital, assets=assets,
              medic=medic, horizon=days, mixed=mixed, talents=talents, vocation=vocation)
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
                 xp=sum(u.combat_xp for u in sim.guild.roster) - sim.start_xp,
                 deeds=list(sim.guild.deeds_done),
                 languages=sim.languages_learned,
                 mages=sim.mages_trained)
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
    res.milestone_met = sim.milestone_day is not None and sim.milestone_day <= marks[-1]
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
    out["deeds"] = statistics.mean(len(r.deeds) for r in results)
    out["deeds_set"] = sorted(set(d for r in results for d in r.deeds))
    out["languages"] = statistics.mean(r.languages for r in results)
    out["mages"] = statistics.mean(r.mages for r in results)
    return out


def deeds_report(table, label="FACTION DEEDS"):
    """Summary of deeds banked, languages learned, and mages trained across policies."""
    lines = [f"== {label} (28 deeds total in world)",
             f"{'policy':<10}{'deeds':>7}{'langs':>7}{'mages':>7}  {'deeds completed'}"]
    for name, s in table.items():
        deeds_count = f"{s.get('deeds', 0):.1f}"
        langs = f"{s.get('languages', 0):.1f}"
        mages = f"{s.get('mages', 0):.1f}"
        deeds_list = ", ".join(s.get("deeds_set", [])) or "none"
        lines.append(f"{name:<10}{deeds_count:>7}{langs:>7}{mages:>7}  {deeds_list}")
    return "\n".join(lines)


def adventure_report(table, label):
    """What a squad past its first week does with the arena's ladder, the Claim and the Medic."""
    lines = [f"== {label}",
             f"{'policy':<10}{'champion':>9}{'bouts':>7}{'cXP/mbr':>9}{'claim':>7}{'on day':>8}{'seized':>8}{'lumber':>8}{'medic $':>9}{'recruits':>9}{'bail $':>8}{'deeds':>7}"]
    for name, s in table.items():
        day = f"{s['claim_day']:.0f}" if s["claim_day"] is not None else "-"
        deeds = f"{s.get('deeds', 0):.1f}"
        lines.append(f"{name:<10}{s['champion'] * 100:>8.0f}%{s['bouts']:>7.1f}{s['xp']:>9.1f}"
                     f"{s['claim'] * 100:>6.0f}%{day:>8}{s['seized'] * 100:>7.0f}%"
                     f"{s['claim_lumber']:>8.1f}{s['treated']:>9.0f}{s['recruited']:>9.1f}{s['bail']:>8.0f}{deeds:>7}")
    lines.append("   (champion: guilds that beat the champion; bouts / cXP: arena bouts fought and "
                 "combat XP gained per member; claim: guilds that made the Claim theirs, on the "
                 "median day; seized: lost it after; lumber: gathered by the garrison; medic $: "
                 "paid per guild; recruits: strangers who signed on; bail: paid at the prison; "
                 "deeds: faction deeds banked)")
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



def curve_report(table):
    days = sorted({d for s in table.values() for d in s["curve"]})
    lines = ["== sustain curve: median copper per member, by day",
             f"{'policy':<10}" + "".join(f"{f'd{d}':>7}" for d in days)]
    for name, s in table.items():
        lines.append(f"{name:<10}" + "".join(f"{s['curve'].get(d, float('nan')):>7.0f}" for d in days))
    return chr(10).join(lines)


# --------------------------------------------------------------------------- #
# gathering: the licence's payback in the engine against the table's promise  #
# --------------------------------------------------------------------------- #
GATHER_PAIRS = {"lumber_yard": ("gatherer", "lumber"), "mine": ("miner", "miner_wage")}
GATHER_DAYS = 60
GATHER_CREWS = (3, 7)                # a small crew, and the full group a good leader keeps there
GATHER_LEVEL = 3                     # the licence is bought once a squad has climbed out of the Scrapper
GATHER_SPARE = 150                   # copper on top of the licence: food and tools for both sides


def gather_payback(node, *, guilds, seed, library, skill, level=0, size=3, days=GATHER_DAYS):
    """The same guilds gathering at `node` (the licence bought on day one) and working its wage.
    -> dict: the copper edge a day gathering adds over the wage, the days that edge takes to pay
    the licence, the share of each side wiped, and what the table alone promises."""
    price = gather.licence_price(node)
    capital = price + GATHER_SPARE * size // 3
    out = {}
    for side, policy in zip(("gather", "wage"), GATHER_PAIRS[node]):
        runs = [run_guild(policy, days=days, seed=seed + i, capital=capital, library=library,
                          skill=skill, level=level, size=size, marks=(days,)) for i in range(guilds)]
        alive = [r for r in runs if not r.wiped] or runs
        out[side] = {"gain": statistics.mean(r.money[days] - r.start_money for r in runs),
                     "alive_gain": statistics.mean(r.money[days] - r.start_money for r in alive),
                     "wiped": sum(r.wiped for r in runs) / len(runs)}
    edge = (out["gather"]["gain"] + price - out["wage"]["gain"]) / days
    alive_edge = (out["gather"]["alive_gain"] + price - out["wage"]["alive_gain"]) / days
    promise = size * (gather.expected_value(node, gather.DAY_HOURS)
                      - economy.work_pay(node, gather.DAY_HOURS, economy.LUMBER_LEVEL_OWN_AXE))
    return {"node": node, "level": level, "size": size, "price": price, "edge": edge,
            "alive_edge": alive_edge, "promise": promise,
            "payback": price / edge if edge > 0 else None,
            "alive_payback": price / alive_edge if alive_edge > 0 else None,
            "wiped": out["gather"]["wiped"], "wage_wiped": out["wage"]["wiped"]}


def gather_report(rows, label):
    def days(x):
        return f"{x:.0f}" if x else "never"
    lines = [f"== the gathering licence, measured ({label})",
             (f"   each node gathered from day one against its wage, {GATHER_DAYS} days; edge = copper a day "
              f"gathering adds for the guild"),
             (f"{'node':<13}{'lvl':>4}{'crew':>5}{'licence':>8}{'promised':>10}{'edge':>7}{'payback':>9}"
              f"{'alive edge':>12}{'payback':>9}{'wiped':>7}{'wage wiped':>12}")]
    for r in rows:
        lines.append(f"{r['node']:<13}{r['level']:>4}{r['size']:>5}{r['price']:>8}{r['promise']:>9.1f}/d"
                     f"{r['edge']:>7.1f}{days(r['payback']):>9}{r['alive_edge']:>12.1f}{days(r['alive_payback']):>9}"
                     f"{r['wiped'] * 100:>6.0f}%{r['wage_wiped'] * 100:>11.0f}%")
    lines.append(f"   promised: the crew's table value over an Axe-armed wage ({gather.PAYBACK_CREW} workers "
                 f"pay the licence in {gather.PAYBACK_DAYS} days on the table); alive: wiped guilds left out")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--policies", default="lumber,balanced")
    ap.add_argument("--guilds", type=int, default=40)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--size", type=int, default=3)
    ap.add_argument("--level", type=int, default=0)
    ap.add_argument("--skill", type=float, default=None,
                    help="the share of the AI's losses a player turns into wins (default: the AI's own)")
    ap.add_argument("--restock", default=None, metavar="TARGET:PER_DAY",
                    help="finite shelves: every free market item holds TARGET, refills PER_DAY")
    ap.add_argument("--recipes", default="", help="comma list of recipes every member knows")
    ap.add_argument("--assets", default="",
                    help="comma list the guild starts with and must keep: house, Donkey, Ox, Horse, Cart")
    ap.add_argument("--medic", action="store_true",
                    help="a Medic at the City heals for potions at a discount, in an hour")
    ap.add_argument("--vocation", default=None, choices=sorted(vocations.VOCATIONS),
                    help="the guild's founding trade (its perk is live in the sim)")
    ap.add_argument("--mixed", action="store_true",
                    help="hurt members work the yard while they heal (1 HP a night) instead of resting")
    ap.add_argument("--medic-factor", type=float, default=None, metavar="F",
                    help=f"the Medic's price as a share of the potions ({act.MEDIC_PRICE_FACTOR})")
    ap.add_argument("--capital", type=int, default=0,
                    help="extra copper at the start, for a guild past its first week")
    ap.add_argument("--seed", type=int, default=0)
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
    if args.medic_factor is not None:
        act.MEDIC_PRICE_FACTOR = args.medic_factor
    marks = tuple(d for d in (7, 30) if d <= args.days) or (args.days,)
    recipes = [r for r in args.recipes.split(",") if r]
    assets = [a for a in args.assets.split(",") if a]
    restock = Restock.parse(args.restock) if args.restock else None
    library = FightLibrary()
    table, ranked = {}, []
    for name in args.policies.split(","):
        results = [run_guild(name, days=args.days, seed=args.seed + i, size=args.size,
                             level=args.level, skill=args.skill, library=library,
                             restock=restock, recipes=recipes, marks=marks, capital=args.capital,
                             assets=assets, medic=args.medic, mixed=args.mixed,
                             vocation=args.vocation)
                   for i in range(args.guilds)]
        table[name] = summarize(results, marks)
        if args.ranking:
            ranked.append(ranking_report(rank_traits(results, marks[-1]),
                                         f"{name}, day {marks[-1]}"))
    skill = "the AI plays" if args.skill is None else f"a player wins {args.skill * 100:.0f}% of the AI's losses"
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

"""Forced events: what the world does to a group that nobody ordered.

The guard, the road and fortress ambushes, the eviction of a squatted property, the raids and
seizures of the Wilds claim, the fight to retake it, and the packs that find a gathering crew or
a supply caravan. Each is one `ForcedEvent` in `EVENTS`, keyed by its order kind:

- **where it is caught.** `arrival` catchers run when a group reaches a node
  (`arrival_pause`, called by `campaign.advance`); a `daily` check runs once per tick for the
  days crossed (`daily_checks`); an event with neither is raised by the work that triggers it
  (`Guild.gather_shift`; a supply run's leg stopping at its ambush, `Guild.supply_leg`).
- **how it is played** (`play`): "battle" goes straight into the fight against `order.pack`,
  "map" lands on the map with a red CTA to start it, "talk" opens the dialogue before it
  (`encounter`, `dialogue.py`; a pack nobody in talks goes straight to the fight). The road
  ambush's CTA opens the dialogue too. `app.FORCED_PLAYERS` maps each to its screen.
- **what kind of fight it is** (`nature`, `fight_nature`): only an opportunist pack weighs the odds
  (`encounters.would_attack`, asked where each ambush is caught; a pack that would not come is dropped).
- **how it is settled** (`resolve`), after the fight: `resolve(guild, group, order, outcome)`;
  a talk that ends without one is settled by `settle_talk`.

A caught event comes back from `campaign.advance` as a `(group, Order)` pending pair with
`group.order` already None and `group.pending` set, so the group is locked until it is fought.
`EVENTS` order is the order the arrival catchers are tried in: the guard is a legal consequence
of who you are and goes first, the rest each fire at one kind of node only.

Adding a threat = its catch and resolve functions here and one `ForcedEvent` line.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace

from . import (
    constants,
    cult_site,
    dialogue,
    economy,
    encounters,
    factions,
    fight_nature,
    i18n,
    justice,
    missions,
    orders,
    vocations,
    world,
)

FORTRESS_AMBUSH_LEVEL = constants.FORTRESS_AMBUSH_LEVEL
FORTRESS_AMBUSH_SIZE = constants.FORTRESS_AMBUSH_SIZE
CITY_RAID_CHANCE = constants.CITY_RAID_CHANCE    # per arrival at a squatted City property
CITY_RAID_LEVEL = constants.CITY_RAID_LEVEL
CITY_RAID_SIZE = 3
CLAIM_ATTACKS = ("wilds_raid", "wilds_seizure")
SOUGHT, OPPORTUNIST, DETERMINED = fight_nature.SOUGHT, fight_nature.OPPORTUNIST, fight_nature.DETERMINED


@dataclass(frozen=True)
class ForcedEvent:
    kind: str
    play: str                       # "battle" | "map" | "talk"
    nature: str                     # fight_nature: whether the power check (encounters.would_attack) applies
    resolve: Callable               # (guild, group, order, outcome) -> events
    arrival: tuple = ()             # catch(guild, group, prev_node, resume_path) -> Order | None
    daily: Callable | None = None   # (guild, days) -> (events, [(group, Order)])

    @property
    def label(self):
        """The group hand-over card's headline."""
        key = f"forced.label.{self.kind}"
        return i18n.t(key) if i18n.has(key) else ""


# --------------------------------------------------------------------------- #
# arrival                                                                     #
# --------------------------------------------------------------------------- #
def arrival_notices(guild, node_id):
    """What arriving at `node_id` tells the player: a faction met for the first time, then
    the deeds the arrival completed."""
    events = [i18n.t("forced.found_faction", faction=f.name) for f in guild.meet_factions_at(node_id)]
    events += [factions.deed_notice(d)
               for d in factions.settle(guild, factions.Event("travel", node=world.node(node_id)))]
    return events


def arrival_pause(guild, group, prev_node, resume_path):
    """The forced `Order` that pauses `group` on arriving at `group.node`, or None to let the
    arrival complete."""
    for event in EVENTS.values():
        for catch in event.arrival:
            order = catch(guild, group, prev_node, resume_path)
            if order is not None:
                return order
    return None


def guard_catch(guild, group, prev_node, resume_path):
    """A jurisdiction node rolls the guard test (`justice.catch`) on the members carrying crime."""
    if not world.node(group.node).jurisdiction:
        return None
    caught = justice.catch(group)
    if not caught:
        return None
    return orders.Order("guard", caught=tuple(u.uid for u in caught),
                        prev_node=prev_node, resume_path=tuple(resume_path))


def road_ambush_catch(guild, group, prev_node, resume_path):
    """An unsafe node rolls `world.ROAD_AMBUSH_CHANCE` once per leg against its own
    `encounter_table`; a pack the group would sweep (`encounters.would_attack`) lets it be."""
    node = world.node(group.node)
    if not node.unsafe:
        return None
    chance = world.ROAD_AMBUSH_CHANCE * vocations.ambush_mult(
        guild, group.stance, scout=group.has_talent("woodland_scout"),
        prowler=group.has_talent("night_prowler"))
    if random.random() >= chance:
        return None
    pack = encounters.roll_encounter(node.encounter_table)
    if not encounters.would_attack(pack, group.members):
        return None
    return orders.Order("ambush", pack=tuple(pack), resume_path=tuple(resume_path))


def demon_ambush_catch(guild, group, prev_node, resume_path):
    """While the Demon of the Cult lives it can fall on a band arriving at the Country Roads or the Farm
    (`cult_site.ambush`); killing it there ends it as the lair would."""
    pack = cult_site.ambush(guild, group.node)
    if pack is None:
        return None
    return orders.Order("ambush", pack=pack, resume_path=tuple(resume_path))


def fortress_ambush_catch(guild, group, prev_node, resume_path):
    """The trust mission's one-off ambush at Field Command (`missions.pending_fortress_ambush`):
    bandits after the sealed chest. Marked done the moment it fires, win or lose, so it never
    springs twice on the same shipment."""
    if not world.node(group.node).has("ledger"):
        return None
    mission = missions.pending_fortress_ambush(guild, group)
    if mission is None:
        return None
    mission.ambush_done = True
    pack = tuple(encounters.build_enemy(FORTRESS_AMBUSH_LEVEL)
                 for _ in range(FORTRESS_AMBUSH_SIZE))
    return orders.Order("fortress_ambush", pack=pack, resume_path=tuple(resume_path))


def property_raid_catch(guild, group, prev_node, resume_path):
    """The City guard coming to clear a squatted property (`guild.house.squatting`), rolled once
    per arrival at the `property` node."""
    if not (guild.house.squatting and world.node(group.node).has("property")):
        return None
    if random.random() >= CITY_RAID_CHANCE:
        return None
    pack = tuple(encounters.build_enemy(CITY_RAID_LEVEL) for _ in range(CITY_RAID_SIZE))
    return orders.Order("eviction", pack=pack, resume_path=tuple(resume_path))


def wilds_claim_retake_catch(guild, group, prev_node, resume_path):
    """Arriving at a seized Wilds claim: the occupiers are still holding it."""
    if not (world.node(group.node).has("claim") and guild.wilds_claim_owner == "seized"):
        return None
    return orders.Order("wilds_retake", pack=_claim_raiders(), resume_path=tuple(resume_path))


# --------------------------------------------------------------------------- #
# daily                                                                       #
# --------------------------------------------------------------------------- #
def daily_checks(guild, days):
    """`(events, pending)` from every event with a `daily` check, for `days` calendar days crossed."""
    events, pending = [], []
    for event in EVENTS.values():
        if event.daily is not None:
            ev, pend = event.daily(guild, days)
            events += ev
            pending += pend
    return events, pending


def claim_attack_rolls(days):
    """Whether a claim attack lands over `days` calendar days crossed: `WILDS_RAID_CHANCE` is a
    per-day chance, so a jump of several days gets the odds of at least one hit and a call that
    crosses no midnight (a 1 h rest) never rolls."""
    return days > 0 and random.random() < 1 - (1 - economy.WILDS_RAID_CHANCE) ** days


def _claim_raiders():
    return tuple(encounters.build_enemy(economy.WILDS_RAID_LEVEL)
                 for _ in range(economy.WILDS_RAID_SIZE))


def _claim_garrisons(guild):
    return [g for g in guild.groups if not g.empty and orders.holds_post(g.order)
            and g.node == world.WILDS_TERRITORY_NODE]


def claim_crew(guild):
    """Every band physically at the claim, whatever it is doing there: the garrison, the gatherers,
    one that stopped by. A band on the road or out hunting is not there."""
    return [g for g in guild.groups
            if not g.empty and g.node == world.WILDS_TERRITORY_NODE and not g.fight_due
            and (g.order is None or g.order.kind not in ("travel", "hunting"))]


def _claim_attack(guild, days, kind, crew):
    """The one fight a claim attack is, when the day's roll lands and the raiders would take the crew
    on (`encounters.would_attack`): the crew's biggest garrison fronts it (`kind`), every other band
    there is called to arms (`"wilds_aid"`), and each carries what it was doing in `prior`."""
    if not claim_attack_rolls(days):
        return []
    pack = _claim_raiders()
    if not encounters.would_attack(pack, [u for g in crew for u in g.members]):
        return []
    lead = max(crew, key=lambda g: (orders.holds_post(g.order), len(g.members)))
    called = []
    for g in crew:
        prior, g.order = g.order, None
        called.append((g, orders.Order(kind if g is lead else "wilds_aid", pack=pack, prior=prior)))
    return called


def wilds_claim_raid_check(guild, days):
    """Raiders test the crew while a garrison sustains the claim (`"SUSTAINING"`). Daily rather than
    on arrival because a garrison never arrives again once posted."""
    if guild.wilds_claim_stage != "SUSTAINING" or not _claim_garrisons(guild):
        return [], []
    return [], _claim_attack(guild, days, "wilds_raid", claim_crew(guild))


def wilds_claim_seizure_check(guild, days):
    """Once `"ESTABLISHED"` and held, the same roll decides whether raiders test the claim.
    With nobody there they take it without a fight; otherwise it is a `"wilds_seizure"` fight."""
    if guild.wilds_claim_stage != "ESTABLISHED" or guild.wilds_claim_owner != "guild":
        return [], []
    crew = claim_crew(guild)
    if not crew:
        if not claim_attack_rolls(days):
            return [], []
        guild.wilds_claim_seize()
        return [i18n.t("forced.claim.unguarded")], []
    return [], _claim_attack(guild, days, "wilds_seizure", crew)


def fight_squad(guild, group, order):
    """Who fights `order` for `group`: the band itself, and for a claim attack every band called
    to arms beside it."""
    squad = list(group.members)
    if order.kind in CLAIM_ATTACKS:
        for g in guild.groups:
            if g is not group and g.pending is not None and g.pending.kind == "wilds_aid":
                squad += g.members
    return squad


def fight_lead(guild, group):
    """The band whose order is the fight `group` is called to: itself, or for a band called to arms
    the one fronting the claim attack."""
    if group.pending is None or group.pending.kind != "wilds_aid":
        return group
    return next((g for g in guild.groups if g.pending is not None and g.pending.kind in CLAIM_ATTACKS), group)


# --------------------------------------------------------------------------- #
# settling                                                                    #
# --------------------------------------------------------------------------- #
def resolve(guild, group, order, outcome):
    """Settle the forced fight `order` after `app` ran it through `campaign.absorb_battle`."""
    return EVENTS[order.kind].resolve(guild, group, order, outcome)


def resume_arrival(guild, group, order):
    """Hand `group` back the order a pause interrupted: the rest of a multi-leg route if any is
    owed, or idle, firing the arrival notices withheld while it was unresolved."""
    group.pending = None
    if group.empty:
        return []
    if order.resume_path:
        group.order = orders.next_leg(group.node, list(order.resume_path), group.speed,
                                      vocations.travel_mult(guild, group))
        return []
    events = arrival_notices(guild, group.node)
    group.order = orders.idle()
    return events


def resolve_guard_prison(guild, group, order):
    """'Accept prison': jail every caught unit (its own days, off its own crime), then resume
    whatever the arrest interrupted."""
    events = []
    for u in list(group.members):
        if u.uid in order.caught:
            days = justice.jail(guild, u)
            events.append(i18n.plural("forced.arrest", days, who=u.name))
    events += resume_arrival(guild, group, order)
    return events


def resolve_guard_flee(guild, group, order):
    """'Run': the group falls back to `order.prev_node`, which gets the same arrival check as any
    other. A re-catch there carries `prev_node=None`, so the patrol's dialogue offers no RUN.

    Returns `(events, pause)`: `pause` is the new forced `Order` for the caller to resolve next,
    or None if the group is simply idle now."""
    group.pending = None
    if order.prev_node is None:
        return [], None
    caught = [u for u in group.members if u.uid in order.caught]
    names = ", ".join(u.name for u in caught) if caught else i18n.t("forced.the_group")
    events = [i18n.t("forced.fall_back", who=names, place=world.node(order.prev_node).name)]
    group.node = order.prev_node
    pause = arrival_pause(guild, group, None, ())
    if pause is not None:
        group.order = None
        group.pending = pause
        return events, pause
    group.order = orders.idle()
    return events, None


def resolve_guard_fight_aftermath(guild, group, order, outcome):
    """Every caught unit that survived the patrol fight banks the crime the brawl adds, then the
    group's order resumes."""
    events = []
    for u in outcome.survivors:
        if u.uid in order.caught:
            justice.resolve_fight_crime(u, outcome)
            events.append(i18n.t("forced.guard_survivor", who=u.name, crime=u.crime))
    events += resume_arrival(guild, group, order)
    return events


def resolve_road_ambush(guild, group, order, outcome=None):
    """No choice to make: whoever is left resumes whatever the ambush interrupted."""
    if outcome is not None and outcome.won and any(getattr(u, "bio_slug", None) == cult_site.DEMON for u in order.pack):
        cult_site.demon_slain(guild)
    return resume_arrival(guild, group, order)


def resolve_gather_ambush(guild, group, order, outcome):
    """A win banks the shift's haul for whoever is left; a loss sends them away with nothing."""
    group.pending = None
    if group.empty:
        return []
    group.order = orders.idle()
    if not outcome.won:
        return [i18n.t("forced.gather.lost")]
    if order.job is not None:
        group.order = orders.garrison(order.job)
    survivors = [u for u in group.members if u in outcome.survivors]
    return [i18n.t("forced.gather.won")] + guild.bank_haul(survivors, order.hours, group.node)


def resolve_supply_ambush(guild, group, order, outcome):
    """A win walks the caravan on from where it stopped (the pay waits for Field Command); a loss or
    a flight leaves the group where the leg began -- Field Command on the way out, the Outpost on the
    way back -- with the cargo lost."""
    group.pending = None
    if group.empty:
        return []
    if not outcome.won:
        group.order = orders.idle()
        return [i18n.t("forced.supply.lost", place=world.node(group.node).name)]
    group.order = orders.Order("travel", eta=order.eta, remaining=order.owed, dest=order.dest,
                               path=order.resume_path, task="supply_run")
    return [i18n.t("forced.supply.won")]


def resolve_property_raid(guild, group, order, outcome):
    """Losing the eviction fight clears the squat for good; winning drives the patrol off until
    the next roll."""
    events = resume_arrival(guild, group, order)
    if outcome.won:
        events.insert(0, i18n.t("forced.raid.won"))
    else:
        guild.house.abandon()
        events.insert(0, i18n.t("forced.raid.lost"))
    return events


def _stand_down_crew(guild, group, order, won):
    """The claim attack is over: every band that fought it (`group` and the ones called to arms) goes
    back to what it was doing on a win, and to no orders on a loss. The dead are already gone."""
    for g, prior in [(group, order.prior)] + [(g, g.pending.prior) for g in guild.groups
                                              if g.pending is not None and g.pending.kind == "wilds_aid"]:
        g.pending = None
        if not g.empty:
            g.order = prior if won else orders.idle()


def resolve_wilds_raid(guild, group, order, outcome):
    """Winning sends every band back to its work; losing restarts the sustain countdown and leaves
    the survivors idle."""
    _stand_down_crew(guild, group, order, outcome.won)
    if outcome.won:
        return [i18n.t("forced.claim.raid_won")]
    guild.wilds_claim_sustain_days_left = economy.WILDS_CLAIM_SUSTAIN_DAYS
    return [i18n.t("forced.claim.raid_lost")]


def resolve_wilds_seizure(guild, group, order, outcome):
    """Winning sends every band back to its work; losing hands the claim to the occupiers until a retake."""
    _stand_down_crew(guild, group, order, outcome.won)
    if outcome.won:
        return [i18n.t("forced.claim.seizure_won")]
    guild.wilds_claim_seize()
    return [i18n.t("forced.claim.seizure_lost")]


def resolve_wilds_aid(guild, group, order, outcome):
    """A band called to arms is settled with the fight it joined (`_stand_down_crew`)."""
    return []


def resolve_wilds_claim_retake(guild, group, order, outcome):
    """Winning hands the claim back (the structure was never touched); losing resumes the
    arrival and the claim stays seized."""
    events = resume_arrival(guild, group, order)
    if outcome.won:
        guild.wilds_claim_owner = "guild"
        events.insert(0, i18n.t("forced.claim.retaken"))
    else:
        events.insert(0, i18n.t("forced.claim.retake_failed"))
    return events


# --------------------------------------------------------------------------- #
# the talk before the fight                                                   #
# --------------------------------------------------------------------------- #
TALKS = {"guard", "ambush", "fortress_ambush", "gather_ambush", "supply_ambush"}


def encounter(guild, group, order):
    """The dialogue `order` opens before its fight (`dialogue.py`), or None for straight to it:
    a kind with no talk, or a pack with nobody who speaks. The guard's patrol is built here, on
    the order, so the one who talks is the one who fights."""
    if order.kind not in TALKS:
        return None
    if order.kind == "guard":
        caught = [u for u in group.members if u.uid in order.caught]
        if not order.pack:
            crime = max((u.crime for u in caught), default=0)
            order.pack = tuple(justice.patrol_pack(crime))
        return dialogue.Patrol(order.pack, caught, can_run=order.prev_node is not None)
    if not dialogue.can_talk(order.pack):
        return None
    enc = dialogue.Ambush(order.pack, title=i18n.t(f"forced.title.{order.kind}"))
    enc.set_odds(group.members)
    return enc


def settle_talk(guild, group, order):
    """The talk ended with no fight (a bluff, a bribe, a rout): settle `order` as a fight won
    without a blow -- the road goes on, the haul or the cargo is banked, the guard lets them go
    with the rap sheet as it was."""
    if order.kind == "guard":
        return resume_arrival(guild, group, order)
    calm = SimpleNamespace(won=True, survivors=list(group.members), fallen=[], player_kos=0)
    return EVENTS[order.kind].resolve(guild, group, order, calm)


EVENTS = {e.kind: e for e in (
    ForcedEvent("guard", "talk", DETERMINED, resolve_guard_fight_aftermath, arrival=(guard_catch,)),
    ForcedEvent("ambush", "map", OPPORTUNIST, resolve_road_ambush, arrival=(demon_ambush_catch, road_ambush_catch)),
    ForcedEvent("fortress_ambush", "map", DETERMINED, resolve_road_ambush, arrival=(fortress_ambush_catch,)),
    ForcedEvent("eviction", "battle", DETERMINED, resolve_property_raid, arrival=(property_raid_catch,)),
    ForcedEvent("wilds_retake", "battle", SOUGHT, resolve_wilds_claim_retake,
                arrival=(wilds_claim_retake_catch,)),
    ForcedEvent("wilds_raid", "battle", OPPORTUNIST, resolve_wilds_raid, daily=wilds_claim_raid_check),
    ForcedEvent("wilds_seizure", "battle", OPPORTUNIST, resolve_wilds_seizure, daily=wilds_claim_seizure_check),
    ForcedEvent("wilds_aid", "battle", OPPORTUNIST, resolve_wilds_aid),
    ForcedEvent("gather_ambush", "talk", OPPORTUNIST, resolve_gather_ambush),
    ForcedEvent("supply_ambush", "talk", OPPORTUNIST, resolve_supply_ambush),
)}

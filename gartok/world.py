"""The world map: a small graph of places the guild's groups travel between.

Nodes are places; edges carry a travel cost in whole hours. Each `Group`
(`gartok/group.py`) sits on one node; ordering it elsewhere (`orders.travel`)
uses `route` (Dijkstra over `EDGES`) to price the trip in hours, and
`campaign.advance` is what actually moves it there and advances the clock.
`MapScreen` draws the graph; `app` turns the node a group's order resolves at
into the activity screen there.

Node kinds:
- "town":    a safe stop, nothing to do but pass through (and manage gear).
             A town with `work=True` is a lumber yard: put members to a shift
             there to trade hours of the day for copper (`Guild.work_shift`);
             a town with `bank=True` has the Bankers -- rent a strongbox and
             stash gear the guild isn't carrying (`bank_screen`);
- "battle":  the chosen squad drops into a tactical fight on `scenario`;
- "market":  a shop -- buy and sell gear for copper.
- "tavern": strangers looking for work -- talk one into the guild (`recruit`).
- "wilds":  open country with its own activities -- Hunt for meat (`hunt`), at
            the risk of an ambush by a scaled pack (`encounters`).

A battle node is lethal by default (permadeath, loot the corpses). The Arena is
the exception: `lethal=False`, `arena=True` -- a paid, non-lethal bout. The squad
stakes copper to enter -- `entry` per fighter, from the tier `world.arena_offers`
picks for the guild's `arena_reputation`; winning pays the flat purse, losing
forfeits the stake. Nobody dies either way. Reputation with the Pits comes from
completing arena deeds (`factions`), not from the win itself.

`pos` is normalised (0..1, 0..1) inside the map area; `MapScreen` scales it.

`jurisdiction` (e.g. `"the_city"`) marks a node the guard patrols: `campaign.advance`
tests every crime-carrying member of a group that arrives there -- waypoint or
final stop alike -- and can pause the group on the outcome (`justice.py`).
Outside jurisdiction (`road`, `wilds`, the lumber yard) a rap sheet never comes up.

`unsafe` marks a node with its own standing danger: every arrival there rolls
`ROAD_AMBUSH_CHANCE` (once per leg, not per hour like `hunt.py`'s wilds
ambush) against `encounter_table` (an `encounters.EncounterEntry` tuple) --
`campaign.advance` pauses the group on a lethal fight if it hits, same seam
as `jurisdiction`. Only the Old Road (`road`) carries it for now.

`trust`/`ledger` are one-mission flags for the Bankers' trust run
(`missions.TRUST_CHEST`): `trust` (the City) offers/turns in the mission
(`trust_screen.py`); `ledger` (Ledger Hold) trades the sealed chest for a
letter (`ledger_screen.py`). The fortress ambush that can hit Ledger Hold
along the way is mission-conditional, not a standing risk like `unsafe` --
see `missions.pending_fortress_ambush` / `campaign._fortress_ambush_catch`.

`city_property` marks where the Bankers sell the guild a house
(`city_property_screen.py`, [[gartok-property-two-paths]]'s "City" path) --
today only the City itself, same node as `bank`/`trust` but its own flag since
a node can carry more than one Bankers service at once.

`garrison_job` names the job a `"garrison"` order (`orders.py`) can work while
parked at this node, or None for a node with none -- `Guild._garrison_upkeep`
checks it against the order's own `job` before banking any output
(`economy.GARRISON_JOBS`).

`claim` marks the Wilds claim campaign's own node (`WILDS_TERRITORY_NODE`,
`wilds_claim_screen.py`, [[gartok-property-two-paths]]'s "Wilds" path) --
distinct from `wilds` (Hunt) on purpose, the fantasy being the guild holding
ground of its own rather than a plot of the same hunting grounds everyone
else uses. It is the first (and, for now, only) node carrying `garrison_job`
-- Sistema 1's engine sat dormant until this gave it somewhere real to work.
"""

import heapq
import os
from dataclasses import dataclass

from . import encounters
from .scenario import ArenaScenario, CustomScenario, ErmosScenario

ROAD_AMBUSH_CHANCE = 0.35   # per travel-leg arrival at an `unsafe` node, not per hour (unlike hunt.py)

# The trust mission's fortress ambush battlefield -- painted in the map editor
# once it exists (map_editor_screen.py); checking the file directly (rather
# than a fixed reference that would crash `map_lib.load_map`) means dropping
# a map under this exact slug is the only thing needed to switch over, no
# code change here. `ErmosScenario` (open country) stands in until then.
FORTRESS_AMBUSH_MAP_SLUG = "ledger-hold-ambush"


def fortress_scenario():
    from . import map_lib   # lazy: map_lib -> npc_lib -> persist pulls in half the package,
                             # which would cycle straight back to world.py at import time
    if os.path.exists(map_lib.map_path(FORTRESS_AMBUSH_MAP_SLUG)):
        return CustomScenario(map_lib.load_map(FORTRESS_AMBUSH_MAP_SLUG))
    return ErmosScenario()


class Node:
    def __init__(self, id, name, kind, pos, blurb, scenario=None,
                 lethal=True, arena=False, language=None, alignment=None, work=False,
                 bank=False, tanner=False, jurisdiction=None,
                 unsafe=False, encounter_table=None, trust=False, ledger=False,
                 city_property=False, garrison_job=None, claim=False, forge=False,
                 prison=False, apothecary=False):
        self.id = id
        self.name = name
        self.kind = kind
        self.pos = pos
        self.blurb = blurb
        self.scenario = scenario             # a Scenario subclass, for "battle"
        self.lethal = lethal                 # False -> 0 HP knocks out, no permadeath
        self.arena = arena                   # True -> staked, non-lethal, pays a purse
        self.language = language             # market: the tongue the vendor haggles in
        self.alignment = alignment           # market: the vendor's bent (price sympathy)
        self.work = work                     # town: a lumber yard -- trade hours for copper
        self.bank = bank                     # town: the Bankers -- rent a strongbox (bank_screen)
        self.tanner = tanner                 # town: a mission board -- missions.TANNER_HIDES (tanner_screen)
        self.jurisdiction = jurisdiction     # e.g. "the_city" -- the guard tests every arrival (justice.py)
        self.unsafe = unsafe                 # True -> ROAD_AMBUSH_CHANCE per arrival (campaign.py)
        self.encounter_table = encounter_table   # encounters.EncounterEntry tuple an unsafe node's ambush rolls off
        self.trust = trust                   # town: the Bankers' trust mission (trust_screen)
        self.ledger = ledger                 # town: trade the sealed chest for a letter (ledger_screen)
        self.city_property = city_property   # town: buy a house from the Bankers (city_property_screen)
        self.garrison_job = garrison_job     # the job a "garrison" order can work here, or None
        self.claim = claim                   # the Wilds claim campaign's node (wilds_claim_screen)
        self.forge = forge                   # town: crafting forge/workbench (crafting_screen)
        self.apothecary = apothecary         # town: brewing potions (crafting_screen)

    @property
    def is_battle(self):
        return self.kind == "battle"

    @property
    def is_market(self):
        return self.kind == "market"

    @property
    def is_tavern(self):
        return self.kind == "tavern"

    @property
    def is_prison(self):
        return self.kind == "prison"

    @property
    def is_wilds(self):
        return self.kind == "wilds"


@dataclass(frozen=True)
class Bout:
    """One arena match-up: stake `entry` copper per fighter, face `enemies`
    opponents, win the flat `purse`. `ARENA_TIERS` are the staked ladder;
    `arena.py` builds the one-off bouts (champion, title defense, the Games) to
    the same shape so `SquadScreen` and `campaign` read them all the same way.

    `rep` gates a ladder tier (None on the one-offs). `level` is the mean level
    the opponents are built to (`encounters.build_enemy`); the staked ladder
    scales on it, the one-off bouts field their own hand-built opponents and
    leave it 0. The bool flags tag a bout for its consumer: `champion`/`defense`
    for `campaign`, `stage2`/`ctf`/`boss` for the Games (`ctf` fights on a
    `FlagScenario`; `boss` fields the map's authored NPC team plus scaled goons).
    `map_slug` swaps the node's procedural scenario for an authored map
    (`map_lib`). `squad_max` caps how many fighters the player may send -- 0 means
    "match the opponent count" (`enemies`), which every arena bout but the boss
    does. `matchup.build` reads all of this.
    """
    name: str
    entry: int
    purse: int
    enemies: int
    level: int = 0
    rep: int | None = None
    champion: bool = False
    defense: bool = False
    stage2: bool = False
    ctf: bool = False
    boss: bool = False
    map_slug: str | None = None
    squad_max: int = 0

    @property
    def player_cap(self):
        """Fighters the player may field: `squad_max`, or the opponent count."""
        return self.squad_max or self.enemies


# The arena bouts are now directly managed by the narrative progression
# in app.py (using the scrapper/champion bouts before The Games).


NODES = [
    Node("city", "Ankareth", "town", (0.30, 0.50),
         "The walled burg. Where the guild sets out from -- and where the "
         "Bankers keep their strongboxes.", bank=True, tanner=True, trust=True,
         city_property=True, jurisdiction="the_city", forge=True, apothecary=True),
    Node("lumber_yard", "Lumber Yard", "town", (0.22, 0.64),
         "A sawmill just outside the walls. The foreman lends the axe -- you fell "
         "a tree that isn't yours and take only the wage for the hours.",
         work=True),
    Node("arena", "Arena", "battle", (0.405, 0.32),
         "Staked bouts in the pits under the city. Nobody dies -- you lose the purse.",
         ArenaScenario, lethal=False, arena=True, jurisdiction="the_city"),
    Node("market", "Market", "market", (0.38, 0.64),
         "Buy and sell gear for copper. The traders speak Ankarin.",
         language="Ankarin", alignment="Lawful and Neutral", jurisdiction="the_city"),
    Node("tavern", "Tavern", "tavern", (0.135, 0.50),
         "Smoke, warm beer and folk with no contract. Talk someone into joining the guild.",
         jurisdiction="the_city", garrison_job="study"),
    Node("prison", "Prison", "prison", (0.22, 0.36),
         "The City's holding cells for minor criminals. Pay someone's bail for a chance to recruit them.",
         jurisdiction="the_city"),
    Node("road", "Old Road", "town", (0.60, 0.50),
         "A dirt track cutting across the open country to the east.",
         unsafe=True, encounter_table=encounters.OLD_ROAD_TABLE),
    Node("wilds", "The Wilds", "wilds", (0.91, 0.37),
         "Open ground under the sky, outside the walls. Hunt it for meat -- and "
         "risk what else hunts here.", ErmosScenario),
    Node("ledger_hold", "Ledger Hold", "town", (0.76, 0.73),
         "A fortified counting-house the Bankers keep well outside the walls -- "
         "armed, and used to precious cargo.", fortress_scenario, ledger=True),
    Node("wilds_territory", "The Claim", "town", (0.97, 0.31),
         "A stretch of the Wilds the guild means to make its own -- if it can "
         "clear it, fence it, and hold it.", ErmosScenario,
         claim=True, garrison_job="lumber"),
]

WILDS_TERRITORY_NODE = "wilds_territory"

EDGES = [
    ("city", "arena", 2),
    ("city", "lumber_yard", 1),
    ("city", "market", 1),
    ("city", "tavern", 1),
    ("city", "prison", 1),
    ("city", "road", 4),
    ("arena", "road", 3),
    ("road", "wilds", 6),
    ("road", "ledger_hold", 5),
    ("wilds", "wilds_territory", 2),
]

START_NODE = "city"

_BY_ID = {n.id: n for n in NODES}

_ADJ = {n.id: [] for n in NODES}
for _a, _b, _w in EDGES:
    _ADJ[_a].append((_b, _w))
    _ADJ[_b].append((_a, _w))


def node(id):
    return _BY_ID[id]


def neighbors(id):
    """[(node_id, hours), ...] directly connected to `id`."""
    return _ADJ[id]


def route(src, dst):
    """Cheapest path as ([node ids incl. both ends], total_hours).

    ([src], 0) when src == dst; (None, inf) when unreachable.
    """
    if src == dst:
        return [src], 0
    dist = {src: 0}
    prev = {}
    pq = [(0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == dst:
            break
        if d > dist.get(u, float("inf")):
            continue
        for v, w in _ADJ[u]:
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    if dst not in dist:
        return None, float("inf")
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    return path[::-1], dist[dst]

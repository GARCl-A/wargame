"""The world map: a small graph of places the guild's groups travel between.

Nodes are places; edges carry a distance, in the hours a person walking at
`WALK_SPEED` covers. Each `Group` (`gartok/group.py`) sits on one node; ordering
it elsewhere (`orders.travel`) uses `route` (Dijkstra over `EDGES`) to find the
shortest way, `hours` turns a distance into time at the group's speed, and
`campaign.advance` is what actually moves it there and advances the clock.
`MapScreen` draws the graph; `app` turns the node a group's order resolves at
into the activity screen there.

Node kinds (the place's nature -- its terrain, glyph and scenario):
- "town":    a safe stop.
- "battle":  the chosen squad drops into a tactical fight on `scenario`;
- "market":  a stall-keeper's place;
- "tavern":  strangers looking for work;
- "wilds":   open country at the risk of an ambush by a scaled pack (`encounters`).

What a node *offers* is `functions` (ids from `node_functions.FUNCTIONS`): a
lumber yard has "work", the City "bank", "tanner", "forge"..., the Library
"library" and "shop". A node may carry any mix. "shop" is the one that owns a
till and a shelf (`shop.Shop`, `Guild.shop(node_id)`): it is refilled every day
and a screen that hosts it (the Library's tabs) shows the stall inside.

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

`garrison_job` names the job a `"garrison"` order (`orders.py`) can work while
parked at this node, or None for a node with none -- `Guild._garrison_upkeep`
checks it against the order's own `job` before banking any output
(`economy.GARRISON_JOBS`).
"""

import heapq
import os
from dataclasses import dataclass

from . import encounters
from .ox_fields import OxFieldsScenario
from .scenario import ArenaScenario, CustomScenario, ErmosScenario

WALK_SPEED = 9.0           # meters per move of the walker one distance unit is measured by
ROAD_AMBUSH_CHANCE = 0.2    # per travel-leg arrival at an `unsafe` node, not per hour (unlike hunt.py)

# The trust mission's fortress ambush battlefield -- painted in the map editor
# once it exists (map_editor_screen.py); checking the file directly (rather
# than a fixed reference that would crash `map_lib.load_map`) means dropping
# a map under this exact slug is the only thing needed to switch over, no
# code change here. `ErmosScenario` (open country) stands in until then.
FORTRESS_AMBUSH_MAP_SLUG = "ledger-hold-ambush"


def fortress_scenario():
    from . import (
        map_lib,  # lazy: map_lib -> npc_lib -> persist pulls in half the package,
    )
                             # which would cycle straight back to world.py at import time
    if os.path.exists(map_lib.map_path(FORTRESS_AMBUSH_MAP_SLUG)):
        return CustomScenario(map_lib.load_map(FORTRESS_AMBUSH_MAP_SLUG))
    return ErmosScenario()


class Node:
    def __init__(self, id, name, kind, pos, blurb, scenario=None,
                 lethal=True, arena=False, language=None, alignment=None, functions=(),
                 jurisdiction=None, unsafe=False, encounter_table=None,
                 garrison_job=None, wagon_risk=0.0):
        self.id = id
        self.name = name
        self.kind = kind
        self.pos = pos
        self.blurb = blurb
        self.scenario = scenario             # a Scenario subclass, for "battle"
        self.lethal = lethal                 # False -> 0 HP knocks out, no permadeath
        self.arena = arena                   # True -> staked, non-lethal, pays a purse
        self.language = language             # shop: the tongue the vendor haggles in
        self.alignment = alignment           # shop: the vendor's bent (price sympathy)
        self.functions = tuple(functions)    # what the node offers (node_functions.FUNCTIONS)
        self.jurisdiction = jurisdiction     # e.g. "the_city" -- the guard tests every arrival (justice.py)
        self.unsafe = unsafe                 # True -> ROAD_AMBUSH_CHANCE per arrival (campaign.py)
        self.encounter_table = encounter_table   # encounters.EncounterEntry tuple an unsafe node's ambush rolls off
        self.garrison_job = garrison_job     # the job a "garrison" order can work here, or None
        self.wagon_risk = wagon_risk         # chance a wagon left unguarded here is lost (wagon_watch.py)

    def has(self, function):
        return function in self.functions

    @property
    def is_battle(self):
        return self.kind == "battle"


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
         "Bankers keep their strongboxes.", jurisdiction="the_city",
         functions=("bank", "tanner", "trust", "forge", "apothecary", "property")),
    Node("lumber_yard", "Lumber Yard", "town", (0.22, 0.64),
         "A sawmill just outside the walls. The foreman lends the axe -- you fell "
         "a tree that isn't yours and take only the wage for the hours.",
         functions=("work",)),
    Node("mine", "The Mine", "town", (0.78, 0.54),
         "A working quarry past the Old Road. The foreman lends the pick, and the only stone, ore and coal "
         "for sale are sold here.", functions=("work", "shop")),
    Node("arena", "Arena", "battle", (0.405, 0.32),
         "Staked bouts in the pits under the city. Nobody dies -- you lose the purse.",
         ArenaScenario, lethal=False, arena=True, jurisdiction="the_city"),
    Node("market", "Market", "market", (0.38, 0.64),
         "Buy and sell gear for copper. The traders speak Ankarin.",
         language="Ankarin", alignment="Lawful and Neutral", jurisdiction="the_city",
         functions=("shop",)),
    Node("tavern", "Tavern", "tavern", (0.135, 0.50),
         "Smoke, warm beer and folk with no contract. Talk someone into joining the guild.",
         jurisdiction="the_city", garrison_job="study", functions=("recruit",)),
    Node("prison", "Prison", "prison", (0.22, 0.36),
         "The City's holding cells for minor criminals. Pay someone's bail for a chance to recruit them.",
         jurisdiction="the_city", functions=("prison",)),
    Node("road", "Old Road", "town", (0.60, 0.50),
         "A dirt track cutting across the open country to the east.",
         unsafe=True, encounter_table=encounters.OLD_ROAD_TABLE),
    Node("wilds", "The Wilds", "wilds", (0.91, 0.37),
         "Open ground under the sky, outside the walls. Hunt it for meat -- and "
         "risk what else hunts here.", ErmosScenario, functions=("hunt",)),
    Node("ledger_hold", "Ledger Hold", "town", (0.76, 0.73),
         "A fortified counting-house the Bankers keep well outside the walls -- "
         "armed, and used to precious cargo.", fortress_scenario, functions=("ledger",)),
    Node("wilds_territory", "The Claim", "town", (0.97, 0.31),
         "A stretch of the Wilds the guild means to make its own -- if it can "
         "clear it, fence it, and hold it.", ErmosScenario,
         garrison_job="lumber", functions=("claim",)),
    Node("library", "The Library", "town", (0.12, 0.32),
         "A quiet place of study just outside the city. Sells dictionaries and seeks lost knowledge.",
         jurisdiction="the_city", functions=("library", "shop")),
    Node("farm", "The Farm", "town", (0.30, 0.84),
         "A farmstead beyond the walls. For now it keeps the stables: wagons and the animals that pull them.",
         functions=("stable",)),
    Node("ancient_ruins", "Ancient Ruins", "town", (0.52, 0.22),
         "Crumbling stone spires buried in the wild scrub. The lost library vaults lie beneath.",
         functions=("ancient_ruins",), wagon_risk=ROAD_AMBUSH_CHANCE),
    Node("country_roads", "Country Roads", "town", (0.44, 0.92),
         "Dirt lanes between the farmsteads south of the city. Quiet, and wide open."),
    Node("ox_fields", "Legendary Ox Fields", "town", (0.62, 0.88),
         "Fertile grazing land where something very old and very large has outlived every hunter sent after it.",
         OxFieldsScenario, functions=("ox_hunt",)),
]

HIDDEN_NODES = {"ancient_ruins": "ancient_ruins_discovered", "ox_fields": "ox_fields_discovered"}

WILDS_TERRITORY_NODE = "wilds_territory"

EDGES = [
    ("city", "arena", 2),
    ("city", "lumber_yard", 1),
    ("city", "market", 1),
    ("city", "tavern", 1),
    ("city", "prison", 1),
    ("city", "library", 1),
    ("city", "farm", 2),
    ("city", "road", 4),
    ("arena", "road", 3),
    ("road", "wilds", 6),
    ("road", "ledger_hold", 5),
    ("road", "ancient_ruins", 2),
    ("farm", "country_roads", 1),
    ("country_roads", "ox_fields", 1),
    ("wilds", "wilds_territory", 2),
    ("road", "mine", 6),
    ("mine", "wilds_territory", 2),
]

START_NODE = "city"

_BY_ID = {n.id: n for n in NODES}

_ADJ = {n.id: [] for n in NODES}
for _a, _b, _w in EDGES:
    _ADJ[_a].append((_b, _w))
    _ADJ[_b].append((_a, _w))


def node(id):
    return _BY_ID[id]


def known(guild):
    """The nodes the guild can see: everything but the places still to be found."""
    return [n for n in NODES if n.id not in HIDDEN_NODES or getattr(guild, HIDDEN_NODES[n.id])]


def hours(distance, speed):
    """Time to cover `distance` at `speed` (meters per move)."""
    return distance * WALK_SPEED / max(speed, 1)


def neighbors(id):
    """[(node_id, distance), ...] directly connected to `id`."""
    return _ADJ[id]


def route(src, dst):
    """Shortest path as ([node ids incl. both ends], total distance).

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

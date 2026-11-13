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

`pos` is in map units: a small map fills (0..1, 0..1), a bigger one runs past 1 (never squeezed,
so nodes keep their spacing) and the map camera pans over it.

`jurisdiction` (e.g. `"ankareth"`) marks a node the guard patrols: `campaign.advance`
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
import math
import os
import random
from dataclasses import dataclass

from . import encounters, i18n
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


@dataclass(frozen=True)
class Vendor:
    """The face and name behind one of a node's functions: shown in that screen's
    header so the player learns who they deal with. `portrait` is a file in
    `assets/portraits/npc/`."""
    name: str
    race: str
    role: str
    portrait: str
    line: str = ""          # what they say when the guild walks in, for a vendor made in play; else `desc.vendor.<id>`
    female: bool = False    # picks the feminine form of the role where the language has one

    @property
    def key(self):
        return self.name.lower().replace(" ", "_")

    @property
    def shown(self):
        shown = i18n.name("vendor", self.key)
        return self.name if shown == self.key else shown

    def said(self):
        return i18n.desc("vendor", self.key) or self.line

    @property
    def caption(self):
        return i18n.t("world.vendor_caption", race=i18n.name("race", self.race), role=i18n.role(self.role, self.female))

    @property
    def card(self):
        return {"name": self.shown, "caption": self.caption, "portrait": self.portrait, "line": self.said()}


class Node:
    def __init__(self, id, name, kind, pos, scenario=None,
                 lethal=True, arena=False, language=None, alignment=None, functions=(),
                 jurisdiction=None, unsafe=False, encounter_table=None,
                 garrison_job=None, wagon_risk=0.0, vendors=None,
                 hidden=False, floor=None, blurb=""):
        self.id = id
        self._name = name                    # the English default; the catalog's `name.node.<id>` wins
        self.kind = kind
        self.pos = pos
        self._blurb = blurb                  # for a node made in play; a static node's is `desc.node.<id>`
        self.scenario = scenario             # a Scenario subclass, for "battle"
        self.lethal = lethal                 # False -> 0 HP knocks out, no permadeath
        self.arena = arena                   # True -> staked, non-lethal, pays a purse
        self.language = language             # shop: the tongue (or a tuple of them) the vendor haggles in
        self.alignment = alignment           # shop: the vendor's bent (price sympathy)
        self.functions = tuple(functions)    # what the node offers (node_functions.FUNCTIONS)
        self.jurisdiction = jurisdiction     # e.g. "ankareth" -- the guard tests every arrival (justice.py); the map washes the nodes that share it
        self.unsafe = unsafe                 # True -> ROAD_AMBUSH_CHANCE per arrival (campaign.py)
        self.encounter_table = encounter_table   # encounters.EncounterEntry tuple an unsafe node's ambush rolls off
        self.garrison_job = garrison_job     # the job a "garrison" order can work here, or None
        self.wagon_risk = wagon_risk         # chance a wagon left unguarded here is lost (wagon_watch.py)
        self.vendors = dict(vendors or {})   # function id -> the Vendor behind it
        self.hidden = hidden
        self.floor = floor                   # its fights' floor (`ui/floors.py`) over the scenario's own

    @property
    def name(self):
        shown = i18n.name("node", self.id)
        return self._name if shown == self.id else shown

    @property
    def blurb(self):
        return i18n.desc("node", self.id) or self._blurb

    @property
    def shop_label(self):
        """The map button's text for the `shop` function, or None for the function's own."""
        key = f"world.shop_label.{self.id}"
        return i18n.t(key) if i18n.has(key) else None

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


_ELYSIA = Vendor("Elysia", "Sprite", "banker", "banker.png", female=True)
_ROWAN = Vendor("Rowan", "Treefolk", "carpenter", "carpenter.png", female=True)
_THALASHGROK = Vendor("Thalashgrok", "Dwarf", "blacksmith", "blacksmith.png")
_DUNGORM = Vendor("Dungorm", "Gnoll", "tanner", "tanner.png")

NODES = [
    Node("city", "The Bank", "town", (0.30, 0.50), jurisdiction="ankareth",
         functions=("bank", "trust", "property"),
         vendors={"bank": _ELYSIA, "trust": _ELYSIA, "property": _ELYSIA}),
    Node("lumber_yard", "Lumber Yard", "town", (0.22, 0.64),
         language="Orcish", alignment="Chaotic and Neutral",
         functions=("work", "shop"),
         vendors={"shop": Vendor("Grashnak", "Orc", "foreman", "lumberjack.png")}),
    Node("carpenter", "The Carpenter", "town", (0.26, 0.57),
         jurisdiction="ankareth", language="Verdant", alignment="Neutral and Good",
         functions=("carpenter", "shop"),
         vendors={"carpenter": _ROWAN, "shop": _ROWAN}),

    Node("mine", "The Mine", "town", (0.78, 0.54), language="Goblin", alignment="Neutral and Evil",
         functions=("work", "shop"),
         vendors={"shop": Vendor("Nikkit", "Goblin", "foreman", "miner.png")}),
    Node("arena", "Arena", "battle", (0.405, 0.32),
         ArenaScenario, lethal=False, arena=True, jurisdiction="ankareth",
         vendors={"arena": Vendor("Gorrum Sandfist", "Goliath", "pit master", "arena_master.png")}),
    Node("market", "Market", "market", (0.38, 0.64),
         language="Ankarin", alignment="Lawful and Neutral", jurisdiction="ankareth",
         functions=("shop",), vendors={"shop": Vendor("Surmanyx", "Automaton", "merchant", "merchant.png")}),
    Node("smith", "The Smithy", "town", (0.47, 0.57),
         jurisdiction="ankareth", language="Dwarvish", alignment="Lawful and Neutral", functions=("forge", "shop"),
         vendors={"forge": _THALASHGROK, "shop": _THALASHGROK}),
    Node("tanner", "The Tannery", "town", (0.10, 0.72),
         jurisdiction="ankareth", language="Orcish", alignment="Chaotic and Neutral", functions=("tanner", "shop"),
         vendors={"tanner": _DUNGORM, "shop": _DUNGORM}),
    Node("apothecary", "The Apothecary", "town", (0.29, 0.20),
         jurisdiction="ankareth", language="Gnomish", alignment="Chaotic and Good", functions=("apothecary", "shop"),
         vendors={"shop": Vendor("Pimbletwig", "Gnome", "apothecary", "apothecary.png")}),
    Node("tavern", "Tavern", "tavern", (0.135, 0.50),
         jurisdiction="ankareth", garrison_job="study",
         language="Halfling", alignment="Neutral and Good", functions=("recruit", "shop", "innkeeper"),
         vendors={"shop": Vendor("Tobbin Hearthcup", "Halfling", "innkeeper", "innkeeper.png", female=True)}),
    Node("prison", "Prison", "prison", (0.22, 0.36),
         jurisdiction="ankareth", functions=("prison",),
         vendors={"prison": Vendor("Captain Caelen", "Elf", "warden", "prison_guard.png")}),
    Node("road", "Old Road", "town", (0.60, 0.50),
         unsafe=True, encounter_table=encounters.OLD_ROAD_TABLE, floor="earth"),
    Node("wilds", "The Wilds", "wilds", (0.91, 0.37),
         ErmosScenario, functions=("hunt",)),
    Node("ledger_hold", "Field Command", "town", (0.76, 0.73),
         fortress_scenario, functions=("ledger",),
         vendors={"ledger": Vendor("Commander Varkas", "Hobgoblin", "officer", "ledger_hold_officer.png")}),
    Node("frontier_outpost", "Frontier Outpost", "town", (0.90, 0.64)),
    Node("battlefield", "The Battlefield", "town", (0.99, 0.58), functions=("skirmish",)),
    Node("wilds_territory", "The Claim", "town", (0.97, 0.31),
         ErmosScenario,
         garrison_job="hold", functions=("claim",)),
    Node("library", "The Library", "town", (0.12, 0.32),
         jurisdiction="ankareth", language="Draconic", alignment="Lawful and Evil", functions=("library", "shop"),
         vendors={"library": Vendor("Thalfel", "Kobold", "librarian", "librarian.png", female=True)}),
    Node("farm", "The Farm", "town", (0.30, 0.84),
         language=("Ankarin", "Sylvan"), alignment="Lawful and Good", functions=("stable", "shop", "farmer"),
         vendors={"shop": Vendor("Edric Ashvale", "Human", "farmer", "farmer.png")}),
    Node("ancient_ruins", "Ancient Ruins", "town", (0.52, 0.22),
         functions=("ancient_ruins",), wagon_risk=ROAD_AMBUSH_CHANCE, hidden=True),
    Node("blood_sanctuary", "Blood Sanctuary", "town", (0.66, 0.10),
         alignment="Chaotic and Evil", functions=("shrine",), garrison_job="rite", hidden=True,
         vendors={"shrine": Vendor("Ssareth Coldvein", "Lizardfolk", "blood keeper", "blood_keeper.png", female=True)}),
    Node("nature_grove", "Nature Grove", "town", (0.95, 0.20),
         alignment="Neutral and Good", functions=("shrine",), garrison_job="rite", hidden=True,
         vendors={"shrine": Vendor("Thorne Mossmane", "Centaur", "grove keeper", "grove_keeper.png")}),
    Node("faith_cathedral", "Faith Cathedral", "town", (0.88, 0.85),
         alignment="Lawful and Good", functions=("shrine",), garrison_job="rite", hidden=True,
         vendors={"shrine": Vendor("Brother Quillon", "Kenku", "cathedral keeper", "cathedral_keeper.png")}),
    Node("serpents_nest", "Serpent's Nest", "town", (0.10, 0.74),
         functions=("serpents_nest",), wagon_risk=ROAD_AMBUSH_CHANCE, hidden=True),
    Node("dragon_lair", "The Dragon's Lair", "town", (0.86, 0.62),
         functions=("dragon_lair",), hidden=True),
    Node("country_roads", "Country Roads", "town", (0.44, 0.92), floor="earth"),
    Node("ox_fields", "Legendary Ox Fields", "town", (0.62, 0.88),
         OxFieldsScenario, functions=("ox_hunt",), hidden=True),
]

WILDS_TERRITORY_NODE = "wilds_territory"

EDGES = [
    ("city", "arena", 2),
    ("city", "lumber_yard", 1),
    ("city", "carpenter", 0.5),
    ("lumber_yard", "carpenter", 0.5),
    ("city", "market", 1),
    ("city", "tavern", 1),
    ("city", "prison", 1),
    ("city", "library", 1),
    ("city", "farm", 2),
    ("city", "smith", 0.5),
    ("city", "tanner", 0.5),
    ("city", "apothecary", 0.5),
    ("smith", "tanner", 0.3),
    ("smith", "apothecary", 0.3),
    ("tanner", "apothecary", 0.3),
    ("city", "road", 4),
    ("arena", "road", 3),
    ("road", "wilds", 6),
    ("road", "ledger_hold", 5),
    ("road", "ancient_ruins", 2),
    ("ancient_ruins", "blood_sanctuary", 2),
    ("wilds", "nature_grove", 3),
    ("ledger_hold", "faith_cathedral", 3),
    ("ledger_hold", "frontier_outpost", 5),
    ("frontier_outpost", "battlefield", 2),
    ("farm", "country_roads", 1),
    ("country_roads", "ox_fields", 1),
    ("lumber_yard", "serpents_nest", 1),
    ("mine", "dragon_lair", 2),
    ("wilds", "wilds_territory", 2),
    ("road", "mine", 6),
    ("mine", "wilds_territory", 2),
]

START_NODE = "tavern"              # where a new guild stands on day one
JAIL_RELEASE_NODE = "city"        # where a sentence served lets the freed walk out

_BY_ID = {n.id: n for n in NODES}

_ADJ = {n.id: [] for n in NODES}
for _a, _b, _w in EDGES:
    _ADJ[_a].append((_b, _w))
    _ADJ[_b].append((_a, _w))


# Ethereal nodes: places an event puts on the map for a while and takes off again (`wildfire.py`).
# They live in the guild's save; `clear_runtime` + `add_node` rebuild them on load. `VERSION`
# moves on every change, so a map on screen knows to refresh.
_RUNTIME = set()
VERSION = 0


def add_node(n, links):
    """Put `n` on the map, joined to each `(node_id, distance)` in `links`."""
    global VERSION
    NODES.append(n)
    _BY_ID[n.id] = n
    _ADJ[n.id] = []
    _RUNTIME.add(n.id)
    for other, w in links:
        EDGES.append((n.id, other, w))
        _ADJ[n.id].append((other, w))
        _ADJ[other].append((n.id, w))
    VERSION += 1


def remove_node(node_id):
    """Take an ethereal node off the map, with every edge into it."""
    global VERSION
    if node_id not in _RUNTIME:
        return
    _RUNTIME.discard(node_id)
    NODES[:] = [n for n in NODES if n.id != node_id]
    del _BY_ID[node_id]
    for other, _w in _ADJ.pop(node_id):
        _ADJ[other] = [(v, w) for v, w in _ADJ[other] if v != node_id]
    EDGES[:] = [e for e in EDGES if node_id not in e[:2]]
    VERSION += 1


def clear_runtime():
    for node_id in list(_RUNTIME):
        remove_node(node_id)


def exists(node_id):
    return node_id in _BY_ID


def is_ethereal(node_id):
    return node_id in _RUNTIME


def free_spot(near, away=None, radius=0.12, min_sep=0.09, seed=0):
    """A map position about `radius` from `near` (a position) that keeps `min_sep` from every
    node, leaning away from the position `away` when given."""
    rng = random.Random(seed)
    taken = [n.pos for n in NODES]
    best, best_score = None, -1.0
    for i in range(48):
        angle = 2 * math.pi * i / 48 + rng.uniform(-0.05, 0.05)
        for r in (radius, radius * 1.4, radius * 1.9):
            p = (near[0] + r * math.cos(angle), near[1] + r * math.sin(angle))
            if p[0] < 0.02 or p[1] < 0.02:
                continue
            gap = min((math.dist(p, q) for q in taken), default=1.0)
            lean = 0.0 if away is None else math.dist(p, away) * 0.05
            score = min(gap, min_sep) + lean
            if score > best_score:
                best, best_score = p, score
            if gap >= min_sep:
                break
    return (round(best[0], 3), round(best[1], 3))


def node(id):
    return _BY_ID[id]


def vendor(node_id, function):
    """The `Vendor` behind `function` at the node, or None when it has no face."""
    return _BY_ID[node_id].vendors.get(function)


def known(guild):
    """The nodes the guild can see: public nodes plus any revealed hidden nodes."""
    res = []
    for n in NODES:
        if not n.hidden or (guild is not None and guild.is_node_revealed(n.id)):
            res.append(n)
    return res


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


_BASE_POS = {n.id: n.pos for n in NODES}


def compute_layout(nodes=None, edges=None, seed=42, iterations=500, margin=0.08):
    """Computes a 2D distance-proportional layout using Kamada-Kawai spring embedding.

    Spring rest lengths are scaled to guarantee comfortable visual clearance around
    town nodes while maintaining geographic proportionality with travel hours across
    the world map.
    """
    if nodes is None:
        nodes = NODES
    if edges is None:
        edges = EDGES
    node_ids = [n.id if hasattr(n, "id") else n for n in nodes]
    N = len(node_ids)

    adj = {u: {} for u in node_ids}
    for u, v, w in edges:
        if u in adj and v in adj:
            adj[u][v] = min(adj[u].get(v, w), w)
            adj[v][u] = min(adj[v].get(u, w), w)

    dist = {u: {v: float("inf") for v in node_ids} for u in node_ids}
    for u in node_ids:
        dist[u][u] = 0.0
        for v, w in adj[u].items():
            dist[u][v] = w

    for k in node_ids:
        for i in node_ids:
            for j in node_ids:
                dist[i][j] = min(dist[i][j], dist[i][k] + dist[k][j])

    rng = random.Random(seed)
    pos = {}
    for n in nodes:
        nid = n.id if hasattr(n, "id") else n
        if nid in _BASE_POS:
            pos[nid] = list(_BASE_POS[nid])
        elif hasattr(n, "pos") and n.pos:
            pos[nid] = list(n.pos)
        else:
            pos[nid] = [rng.uniform(0.2, 0.8), rng.uniform(0.2, 0.8)]

    pairs = [
        (node_ids[i], node_ids[j])
        for i in range(N)
        for j in range(i + 1, N)
        if dist[node_ids[i]][node_ids[j]] < float("inf")
    ]
    L0 = 0.075
    K = 1.0
    step_size = 0.08
    min_sep = 0.09

    for step in range(iterations):
        temp = 1.0 - (step / iterations)
        forces = {u: [0.0, 0.0] for u in node_ids}

        for u, v in pairs:
            d_raw = dist[u][v]
            d_eff = (d_raw ** 0.6) + 1.5
            d_ideal = d_eff * L0
            if d_ideal <= 0:
                continue
            k_uv = K / (d_eff ** 1.8)

            dx = pos[u][0] - pos[v][0]
            dy = pos[u][1] - pos[v][1]
            d_actual = math.hypot(dx, dy)
            if d_actual < 1e-5:
                continue

            f = k_uv * (d_actual - d_ideal)
            fx = f * (dx / d_actual)
            fy = f * (dy / d_actual)

            forces[u][0] -= fx
            forces[u][1] -= fy
            forces[v][0] += fx
            forces[v][1] += fy

        for u, v in pairs:
            dx = pos[u][0] - pos[v][0]
            dy = pos[u][1] - pos[v][1]
            d_actual = math.hypot(dx, dy)
            if 1e-5 < d_actual < min_sep:
                rep_f = 0.7 * (min_sep - d_actual) / d_actual
                forces[u][0] += rep_f * dx
                forces[u][1] += rep_f * dy
                forces[v][0] -= rep_f * dx
                forces[v][1] -= rep_f * dy

        cur_step = step_size * temp
        for u in node_ids:
            f_norm = math.hypot(forces[u][0], forces[u][1])
            if f_norm > 1.0:
                forces[u][0] /= f_norm
                forces[u][1] /= f_norm
            pos[u][0] += forces[u][0] * cur_step
            pos[u][1] += forces[u][1] * cur_step

    min_x = min(pos[u][0] for u in node_ids)
    max_x = max(pos[u][0] for u in node_ids)
    min_y = min(pos[u][1] for u in node_ids)
    max_y = max(pos[u][1] for u in node_ids)
    span_x = max(max_x - min_x, 1e-5)
    span_y = max(max_y - min_y, 1e-5)
    max_span = max(span_x, span_y)

    # A small map is stretched to fill the unit box; a big one is never squeezed into it (that
    # would pull nodes under `min_sep`): it grows past 1 and the map camera pans over it.
    avail = 1.0 - 2 * margin
    scale = max(1.0, avail / max_span)
    offset_x = margin + max(0.0, (avail - span_x * scale) / 2.0)
    offset_y = margin + max(0.0, (avail - span_y * scale) / 2.0)

    out = {u: [offset_x + (pos[u][0] - min_x) * scale, offset_y + (pos[u][1] - min_y) * scale]
           for u in node_ids}
    _spread(out, min_sep + 0.001, margin)     # + what the rounding below can eat
    return {u: (round(x, 3), round(y, 3)) for u, (x, y) in out.items()}


def _spread(pos, min_sep, margin, rounds=300):
    """Push apart every pair closer than `min_sep` (springs alone do not guarantee it on a
    crowded map), then shift the whole map back inside `margin`."""
    ids = list(pos)
    for _ in range(rounds):
        moved = False
        for i, u in enumerate(ids):
            for v in ids[i + 1:]:
                dx, dy = pos[u][0] - pos[v][0], pos[u][1] - pos[v][1]
                d = math.hypot(dx, dy)
                if d >= min_sep:
                    continue
                ux, uy = (dx / d, dy / d) if d > 1e-9 else (1.0, 0.0)
                push = (min_sep - d) / 2 + 1e-4
                pos[u][0] += ux * push
                pos[u][1] += uy * push
                pos[v][0] -= ux * push
                pos[v][1] -= uy * push
                moved = True
        if not moved:
            break
    shift_x = margin - min(p[0] for p in pos.values())
    shift_y = margin - min(p[1] for p in pos.values())
    for p in pos.values():
        p[0] += max(0.0, shift_x)
        p[1] += max(0.0, shift_y)


def apply_layout(nodes=None, edges=None, seed=42):
    """Assigns computed layout coordinates to Node.pos."""
    ns = nodes if nodes is not None else NODES
    es = edges if edges is not None else EDGES
    layout = compute_layout(ns, es, seed=seed)
    for n in ns:
        if n.id in layout:
            n.pos = layout[n.id]
    return layout


apply_layout()



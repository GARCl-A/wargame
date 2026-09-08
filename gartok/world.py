"""The world map: a small graph of places the guild travels between.

Nodes are places; edges carry a travel cost in whole hours. The guild sits on
one node (`guild.node`); moving to another runs `route` (Dijkstra over `EDGES`)
and the caller advances the clock by the summed hours. `MapScreen` draws the
graph; `app` turns the node the guild is on into the activity there.

Node kinds:
- "town":    a safe stop, nothing to do but pass through (and manage gear).
             A town with `work=True` is a lumber yard: put members to a shift
             there to trade hours of the day for copper (`Guild.work_shift`);
- "battle":  the chosen squad drops into a tactical fight on `scenario`;
- "market":  a shop -- buy and sell gear for copper.
- "taverna": strangers looking for work -- talk one into the guild (`recruit`).

A battle node is lethal by default (permadeath, loot the corpses). The Arena is
the exception: `lethal=False`, `arena=True` -- a paid, non-lethal bout. The squad
stakes copper to enter -- `entry` per fighter, from the tier `world.arena_offers`
picks for the guild's `arena_reputation`; winning pays the flat purse and raises
the reputation, losing just forfeits the stake. Nobody dies either way.

`pos` is normalised (0..1, 0..1) inside the map area; `MapScreen` scales it.
"""

import heapq

from .scenario import ArenaScenario, ErmosScenario


class Node:
    def __init__(self, id, name, kind, pos, blurb, scenario=None,
                 lethal=True, arena=False, language=None, alignment=None, work=False):
        self.id = id
        self.name = name
        self.kind = kind
        self.pos = pos
        self.blurb = blurb
        self.scenario = scenario             # a Scenario subclass, for "battle"
        self.lethal = lethal                 # False -> 0 PV knocks out, no permadeath
        self.arena = arena                   # True -> staked, non-lethal, pays a purse
        self.language = language             # market: the tongue the vendor haggles in
        self.alignment = alignment           # market: the vendor's bent (price sympathy)
        self.work = work                     # town: a lumber yard -- trade hours for copper

    @property
    def is_battle(self):
        return self.kind == "battle"

    @property
    def is_market(self):
        return self.kind == "market"

    @property
    def is_taverna(self):
        return self.kind == "taverna"


# Arena bouts unlocked by reputation: stake `entry` copper PER FIGHTER sent in,
# field `enemies` opponents, win the flat `purse` and +1 reputation. The purse
# does not grow with the squad, so piling bodies onto a weak tier just eats the
# take -- a lean squad of strong dolls keeps the most. Ordered cheapest first.
ARENA_TIERS = [
    {"rep": 0,  "name": "Fossa dos novatos", "entry": 4,   "purse": 15,  "enemies": 1},
    {"rep": 2,  "name": "Ringue de bronze",  "entry": 15,  "purse": 55,  "enemies": 2},
    {"rep": 5,  "name": "Grade de ferro",    "entry": 40,  "purse": 150, "enemies": 3},
    {"rep": 10, "name": "Arena de prata",    "entry": 100, "purse": 380, "enemies": 3},
]


def arena_offers(reputation):
    """The bouts the guild may take on at its current `reputation` (>= 1 always)."""
    return [t for t in ARENA_TIERS if reputation >= t["rep"]]


NODES = [
    Node("cidade", "Cidade", "town", (0.16, 0.58),
         "O burgo murado. De onde a guilda parte."),
    Node("madeireira", "Madeireira", "town", (0.05, 0.80),
         "Serraria logo fora dos muros. O feitor empresta o machado -- voce "
         "derruba arvore que nao e sua e leva so o pagamento pelas horas.",
         work=True),
    Node("arena", "Arena", "battle", (0.33, 0.30),
         "Lutas de aposta nos fossos sob a cidade. Ninguem morre -- perde-se a bolsa.",
         ArenaScenario, lethal=False, arena=True),
    Node("mercado", "Mercado", "market", (0.28, 0.84),
         "Comprar e vender equipamento por cobre. Os mercadores falam Ankarin.",
         language="Ankarin", alignment="Leal e Neutro"),
    Node("taverna", "Taverna", "taverna", (0.07, 0.30),
         "Fumaca, cerveja morna e gente sem contrato. Convenca alguem a se juntar a guilda."),
    Node("estrada", "Estrada Velha", "town", (0.55, 0.52),
         "Trilha de terra que corta o descampado a leste."),
    Node("ermos", "Ermos", "battle", (0.83, 0.40),
         "Campo aberto sob o ceu, fora das muralhas.", ErmosScenario),
    Node("ruinas", "Ruinas", "battle", (0.78, 0.80),
         "Pedras tombadas de algo antigo. Escuro la dentro.", ArenaScenario),
]

EDGES = [
    ("cidade", "arena", 2),
    ("cidade", "madeireira", 1),
    ("cidade", "mercado", 1),
    ("cidade", "taverna", 1),
    ("cidade", "estrada", 4),
    ("arena", "estrada", 3),
    ("estrada", "ermos", 6),
    ("estrada", "ruinas", 7),
    ("ermos", "ruinas", 4),
]

START_NODE = "cidade"

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

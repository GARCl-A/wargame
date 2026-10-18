"""The Serpent's Nest: the den of the Snake Dragon, off the Lumber Yard.

Two steps, each its own rule here:

- the nest is a secret node (`world.Node.hidden`): with a Snake Dragon job out
  (`missions.pending_snake`), a group at the Lumber Yard searches for it (`search`, a
  Wisdom check); once found it stays on the map;
- inside, one dark map of five chambers (`NestScenario`): packs of snakes, scaled to the
  squad, sleep in the first four until a foe comes near; the fifth is the lair, a pool of
  shallow and deep water, and the Snake Dragon in it. The fight is won the moment the
  Snake Dragon is down for good -- dead, or bound (`actions.Capture`).

The Snake Dragon is authored (`npcs/snake_dragon.json`): a `["Snake", "Dragon"]` hybrid with
the Dragon racial talents (`dragon`, `dragon_breath`).
"""

import random

from . import data, encounters, missions, npc_lib
from .board import Board, grid_distance
from .ground import GroundObject
from .scenario import Scenario

NODE = "serpents_nest"
SEARCH_HOURS = 2
SEARCH_DC = 10
DRAGON_SLUG = missions.SNAKE_SLUG

COLS, ROWS = 40, 18
ENTRANCE = ((0, 8), (0, 9))
DEPLOY = (1, 7, 4, 10)                 # the mouth of the den, where the squad comes in
ROOMS = (                              # (x0, y0, x1, y1), inclusive
    (5, 4, 12, 13),                    # 1: the hall of skins
    (15, 2, 21, 6),                    # 2: the upper den
    (15, 11, 21, 15),                  # 3: the lower den
    (25, 4, 30, 13),                   # 4: the egg chamber
    (33, 2, 38, 15),                   # 5: the lair
)
PASSAGES = (
    (13, 8, 14, 9),                    # hall -> crossing
    (15, 8, 21, 9),                    # the crossing between the two dens
    (18, 7, 18, 7), (18, 10, 18, 10),  # doors into the dens
    (22, 8, 24, 9),                    # crossing -> egg chamber
    (31, 8, 32, 9),                    # egg chamber -> lair
)
POOL_SHALLOW = (34, 5, 37, 12)
POOL_DEEP = (35, 7, 36, 10)
DRAGON_CELL = (37, 3)
PACKS = (                              # (room index, snakes, spiders)
    (0, 2, 0),
    (1, 2, 0),
    (2, 1, 1),
    (3, 3, 0),
    (4, 1, 0),
)
AWARENESS = 5
TORCHES = ((2, 7), (2, 10))


def _cells(x0, y0, x1, y1):
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


def _scout(party):
    return max(party, key=lambda u: u.mod_wisdom) if party else None


def search(guild, group):
    """Spend `SEARCH_HOURS` searching the woods round the yard for the den. Only finds it
    while a Snake Dragon job is out. -> (found, message)."""
    guild.clock.advance_hours(SEARCH_HOURS)
    scout = _scout(group.members)
    who = scout.name if scout else "The squad"
    if missions.pending_snake(guild) is None:
        return False, f"{who} beats the brush round the yard for {SEARCH_HOURS} hours: stumps and sawdust."
    nat = data.d20()
    wis = scout.mod_wisdom if scout else 0
    total = nat + wis
    if total >= SEARCH_DC:
        guild.reveal_node(NODE)
        return True, (f"{who} follows the shed skins to a split in the rock below the yard. "
                      "The Serpent's Nest is found.")
    return False, (f"{who} searches for {SEARCH_HOURS} hours and finds no den "
                   f"(d20({nat}) {wis:+}(WIS) = {total} vs DC {SEARCH_DC}).")


def _sleeper(unit, cell):
    unit.dormant = True
    unit.awareness_radius = AWARENESS
    unit.map_cell = cell
    return unit


def build_enemies(level, rng=random, dragon=True):
    """The nest's packs at `level` (the squad's mean level), placed in their chambers,
    and the Snake Dragon in its lair (unless `dragon` is False: it was delivered). Every
    one sleeps until a foe comes near."""
    out = []
    lair_spot = _cells(DRAGON_CELL[0], DRAGON_CELL[1], DRAGON_CELL[0] + 1, DRAGON_CELL[1] + 1)
    for room, snakes, spiders in PACKS:
        free = sorted(c for c in _cells(*ROOMS[room]) - _cells(*POOL_SHALLOW) - lair_spot
                      if min(grid_distance(c, d) for d in _cells(*DEPLOY)) > AWARENESS)
        cells = rng.sample(free, snakes + spiders)
        for i, cell in enumerate(cells):
            pool = data.SPIDER_POOL if i >= snakes else data.SNAKE_POOL
            out.append(_sleeper(encounters.build_enemy(level, rng, race_pool=pool), cell))
    if dragon:
        out.append(_sleeper(npc_lib.load_npc(DRAGON_SLUG), DRAGON_CELL))
    return out


def dragon_home(guild):
    """The Snake Dragon is still in its lair: no school has had it yet."""
    return not any(m.state == "done" and m.template_id in {t.id for t in missions.SNAKE_HUNTS}
                   for m in guild.missions)


def dragon_of(battle):
    return next((u for u in battle.enemy_units
                 if getattr(getattr(u, "char", None), "npc_slug", None) == DRAGON_SLUG), None)


class NestScenario(Scenario):
    ambient_light = False
    outdoor = False
    torch_count = 0

    def __init__(self, level=1, rng=random, dragon=True):
        self._cols, self._rows = COLS, ROWS
        self.enemies = build_enemies(level, rng, dragon)

    def _make_board(self):
        floor = set().union(*(_cells(*r) for r in (DEPLOY, *ROOMS, *PASSAGES))) | set(ENTRANCE)
        walls = _cells(0, 0, COLS - 1, ROWS - 1) - floor
        water = _cells(*POOL_SHALLOW)
        elevation = {c: -1 for c in _cells(*POOL_DEEP)}
        return Board(walls=walls, water=water, elevation=elevation, cols=COLS, rows=ROWS)

    def _deploy_cells(self, u):
        if u.team == "player":
            return sorted(_cells(*DEPLOY))
        cell = getattr(u, "map_cell", None)
        return [cell] if cell else sorted(_cells(*ROOMS[4]) - _cells(*POOL_SHALLOW))

    def build(self, battle):
        super().build(battle)
        battle.escape_cells = set(ENTRANCE)
        for p in TORCHES:
            battle.ground.append(GroundObject.torch(p))

    def win_check(self, battle):
        dragon = dragon_of(battle)
        if dragon is not None and (dragon.dead or dragon.captured):
            return "player"
        return None

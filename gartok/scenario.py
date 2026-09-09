"""Building the map for one battle: terrain, deployment and scatter.

Kept apart from `Battle` (which owns turn flow and state) so a real scenario
system later -- objectives, prebuilt maps, deployment zones -- has a seam to slot
into instead of unpicking `Battle.setup`. A scenario's `build` receives the
battle and populates its `board`, `units[*].pos`, `creatures`, `ground` and the
`ambient_light` flag.

`Scenario` is the shared machinery (side deployment, the unit's own creatures,
torch scatter). A concrete location on the world map picks a subclass:
- `ArenaScenario` -- the dungeon pit fight: cluttered, always dark, torches around;
- `ErmosScenario` -- open country: `outdoor`, so ambient light follows the
  campaign clock (`battle.daylight`) -- lit by day, pitch dark by night (bring
  your own torch; nothing scattered).
- `CustomScenario` -- a map hand-laid in the editor (`map_lib` dict): fixed
  walls, torches and deployment zones, no random scatter.
"""

import random

from .board import COLS, ROWS, Board, cells, neighbors
from .ground import Creature, GroundObject
from . import data


class Scenario:
    """Base scenario: side deployment + the unit's own creatures. Subclasses set
    the terrain (`_make_board`) and the lighting (`ambient_light` / `torch_count`)."""

    ambient_light = False    # indoor default: seen only by torchlight / darkvision
    outdoor = False          # outdoor: ambient light tracks the clock (battle.daylight)
    torch_count = 6

    def build(self, battle):
        battle.board = self._make_board()
        battle.ambient_light = battle.daylight if self.outdoor else self.ambient_light
        self._deploy(battle)
        self._place_creatures(battle)
        self._scatter_torches(battle)

    def _make_board(self):
        return Board()

    # ------------------------------------------------------------------ #
    def _spawn_cells(self, team):
        """Candidate deployment cells for a side -- the base is the three columns
        on that side's edge. `CustomScenario` overrides this with the zone the
        map author painted."""
        cols = (0, 1, 2) if team == "player" else (COLS - 3, COLS - 2, COLS - 1)
        return [(x, y) for x in cols for y in range(ROWS)]

    def _deploy(self, battle):
        taken = set(battle.board.walls)
        for u in battle.units:
            self._place_unit(u, self._spawn_cells(u.team), taken)

    @staticmethod
    def _place_unit(u, spawn, taken):
        options = list(spawn)
        random.shuffle(options)
        for p in options:
            shape = cells(p, u.footprint)
            if all(0 <= cx < COLS and 0 <= cy < ROWS for cx, cy in shape) \
                    and not (taken & set(shape)):
                u.pos = p
                taken.update(shape)
                return
        u.pos = spawn[0] if spawn else (0, 0)    # fallback: crowded map

    def _place_creatures(self, battle):
        """Neutral creatures that come with a unit (e.g. the Shepherd's sheep)."""
        taken = battle.occupied() | battle.board.walls
        for u in battle.units:
            name = getattr(u, "starting_creature", None)
            if not name:
                continue
            base = data.CREATURE_ITEMS[name]
            candidates = [p for c in battle.cells_of(u) for p in neighbors(c)
                          if p not in taken and battle.board.in_bounds(p)]
            pos = random.choice(candidates) if candidates else u.pos
            taken.add(pos)
            battle.creatures.append(Creature(name, base["token"], pos, base["footprint"]))

    def _scatter_torches(self, battle):
        if not self.torch_count or battle.ambient_light:
            return
        taken = (battle.occupied() | battle.board.walls | battle.creature_cells()
                 | {o.pos for o in battle.ground})
        free = [(x, y) for x in range(COLS) for y in range(ROWS)
                if (x, y) not in taken]
        random.shuffle(free)
        for p in free[:self.torch_count]:
            battle.ground.append(GroundObject.torch(p))


class ArenaScenario(Scenario):
    """The dungeon pit fight the game has shipped with: cluttered wall segments,
    no ambient light, torches scattered anywhere on the floor to fight over."""


class ErmosScenario(Scenario):
    """Open country: sparse walls, `outdoor` -- lit by day, pitch dark by night.
    Nothing lying around: bring your own torch."""

    outdoor = True
    torch_count = 0

    def _make_board(self):
        return Board(min_seg=1, max_seg=2)


class CustomScenario(Scenario):
    """A battle built from a map laid out in the editor (`map_lib`): fixed walls,
    fixed torches, and the deployment cells the author painted. Falls back to the
    base side-column deployment for a side the map leaves blank. What the author
    did not light stays dark -- no torch scatter."""

    def __init__(self, data):
        self.ambient_light = bool(data.get("ambient_light"))
        self.outdoor = bool(data.get("outdoor"))
        self._walls = [tuple(c) for c in data.get("walls", [])]
        self._torches = [tuple(c) for c in data.get("torches", [])]
        self._zones = {"player": [tuple(c) for c in data.get("deploy_player", [])],
                       "enemy": [tuple(c) for c in data.get("deploy_enemy", [])]}

    def _make_board(self):
        return Board(walls=self._walls)

    def _spawn_cells(self, team):
        return self._zones[team] or super()._spawn_cells(team)

    def _scatter_torches(self, battle):
        if battle.ambient_light:
            return
        taken = battle.occupied() | battle.board.walls | battle.creature_cells()
        for p in self._torches:
            if p not in taken and battle.board.in_bounds(p):
                battle.ground.append(GroundObject.torch(p))

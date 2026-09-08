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
    def _deploy(self, battle):
        taken = set(battle.board.walls)
        cols_p = (0, 1, 2)
        cols_e = (COLS - 3, COLS - 2, COLS - 1)

        def place(u, columns):
            options = [(x, y) for x in columns for y in range(ROWS)]
            random.shuffle(options)
            for p in options:
                shape = cells(p, u.footprint)
                if all(0 <= cx < COLS and 0 <= cy < ROWS for cx, cy in shape) \
                        and not (taken & set(shape)):
                    u.pos = p
                    taken.update(shape)
                    return
            u.pos = (columns[0], 0)              # fallback: crowded map

        for u in battle.units:
            place(u, cols_p if u.team == "player" else cols_e)

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

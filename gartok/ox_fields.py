"""The Legendary Ox Fields: a big open field and the beast that is hunted across it.

Daylight, no torches: the tracks that led the party here were read by day, and the
fight starts the moment they are found. Terrain is what the hunt is played on --
groves (walls that block sight), mud (difficult ground) and two box canyons
opening west, the only places the Aurochs can be pinned (`ai.py` makes it run
from anyone near, so a straight chase never lands a blow).

Pressure is the herd: every `CALL_EVERY` rounds Aurochs bellows and an ox joins the
fight from a map edge (at most `CALL_MAX`), scaled to the party's mean level.
The fight is won the moment Aurochs falls, whatever is still standing.
"""

import math
import random

from . import data, encounters
from .board import Board, grid_distance
from .scenario import Scenario

AUROCHS_SLUG = "aurochs"
COLS, ROWS = 48, 30
GROVES = 16
MUD_PATCHES = 4
CALL_EVERY = 5
CALL_MAX = 4
CALL_LEVEL_MAX = 3      # the herd is a nuisance, not the boss: two levels under the party, up to this
_COMPASS = ("east", "south-east", "south", "south-west", "west", "north-west", "north", "north-east")


def _blob(rng, start, size, cols, rows):
    """A connected scatter of `size` cells grown from `start`."""
    out = {start}
    frontier = [start]
    for _ in range(size - 1):
        x, y = rng.choice(frontier)
        nx, ny = x + rng.choice((-1, 0, 1)), y + rng.choice((-1, 0, 1))
        if 0 <= nx < cols and 0 <= ny < rows:
            out.add((nx, ny))
            frontier.append((nx, ny))
    return out


def _canyon(x, y):
    """Walls of a box canyon opening west: top, bottom and back, a 5x5 yard inside."""
    walls = {(x + dx, y) for dx in range(7)} | {(x + dx, y + 6) for dx in range(7)}
    walls |= {(x + 6, y + dy) for dy in range(7)}
    return walls


def _connected(walls, cols, rows, a, b):
    seen, todo = {a}, [a]
    while todo:
        x, y = todo.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if (n not in seen and 0 <= n[0] < cols and 0 <= n[1] < rows
                        and n not in walls):
                    seen.add(n)
                    todo.append(n)
    return b in seen


def layout(rng=random):
    """-> (walls, mud): groves, two canyons and mud flats, with the west edge kept
    clear for the party and a walkable way from there to the far side."""
    for _ in range(20):
        walls = set()
        for _ in range(GROVES):
            walls |= _blob(rng, (rng.randint(8, COLS - 4), rng.randint(2, ROWS - 3)),
                           rng.randint(4, 9), COLS, ROWS)
        for cx, cy in ((COLS - 14, 2), (COLS - 14, ROWS - 9)):
            walls = {w for w in walls if not (cx - 2 <= w[0] <= cx + 8 and cy - 2 <= w[1] <= cy + 8)}
            walls |= _canyon(cx, cy)
        walls = {w for w in walls if w[0] >= 5}
        mud = set()
        for _ in range(MUD_PATCHES):
            mud |= _blob(rng, (rng.randint(6, COLS - 6), rng.randint(2, ROWS - 3)),
                         rng.randint(8, 14), COLS, ROWS)
        mud -= walls
        if _connected(walls, COLS, ROWS, (1, ROWS // 2), (COLS - 2, ROWS // 2)):
            return walls, mud
    return set(), set()


def direction_name(src, dst):
    """The compass word for the way from `src` to `dst`."""
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    if not (dx or dy):
        return "right here"
    ang = math.degrees(math.atan2(dy, dx)) % 360
    return _COMPASS[int((ang + 22.5) // 45) % 8]


class OxFieldsScenario(Scenario):
    """The hunt for Aurochs. See the module docstring."""

    ambient_light = True
    outdoor = False
    torch_count = 0

    def __init__(self):
        self.calls = 0

    def _make_board(self):
        walls, mud = layout()
        return Board(walls=walls, water=mud, cols=COLS, rows=ROWS)

    def _deploy_cells(self, u):
        if u.team == "player":
            return super()._deploy_cells(u)
        east = [(x, y) for x in range(COLS * 2 // 3, COLS - 2) for y in range(ROWS - 1)]
        random.shuffle(east)
        return east

    def build(self, battle):
        self.calls = 0
        super().build(battle)

    @staticmethod
    def _aurochs(battle):
        return [u for u in battle.enemy_units
                if getattr(getattr(u, "char", None), "npc_slug", None) == AUROCHS_SLUG]

    def win_check(self, battle):
        beasts = self._aurochs(battle)
        if beasts and not any(b.alive for b in beasts):
            return "player"
        return None

    def on_round(self, battle):
        """A new round: a hint where the beast is while it is out of sight, and the herd's call."""
        beasts = [b for b in self._aurochs(battle) if b.alive]
        party = [u for u in battle.player_units if u.alive]
        if not beasts or not party:
            return
        if not any(battle.can_see_unit(p, beasts[0]) for p in party):
            mid = (sum(p.pos[0] for p in party) // len(party),
                   sum(p.pos[1] for p in party) // len(party))
            battle.log(f"Hooves drum somewhere to the {direction_name(mid, beasts[0].pos)}.")
        if battle.round_no % CALL_EVERY or self.calls >= CALL_MAX:
            return
        level = max(1, min(CALL_LEVEL_MAX, round(sum(u.combat_level for u in party) / len(party)) - 2))
        calf = encounters.build_enemy(level, race_pool=data.OX_POOL)
        far = sorted(((x, y) for x in (0, COLS - 2) for y in range(0, ROWS - 1, 2)),
                     key=lambda c: -min(grid_distance(c, p.pos) for p in party))
        placed = battle.reinforce(calf, far)
        if placed is not None:
            self.calls += 1
            battle.log("Aurochs bellows -- an answering call rolls across the fields, "
                       "and an ox charges in!")


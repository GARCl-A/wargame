"""Board: grid geometry, walls, pathfinding and line of sight.

The `Board` only knows the terrain. Who stands where (units, ground objects) is
passed in as a set of blocked cells to the pathfinding calls, so the board never
depends on battle state.
"""

import random
from collections import deque

COLS, ROWS = 16, 12


def chebyshev(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def cells(pos, footprint=1):
    """Cells a `footprint`x`footprint` shape covers with its anchor (top-left) at `pos`."""
    x, y = pos
    return [(x + dx, y + dy) for dx in range(footprint) for dy in range(footprint)]


def cells_distance(cells_a, cells_b):
    """Smallest Chebyshev distance between two sets of cells."""
    return min(chebyshev(p, q) for p in cells_a for q in cells_b)


def fits(pos, footprint, blocked):
    """Is the footprint anchored at `pos` fully inside the grid and free of `blocked`?"""
    x, y = pos
    if not (0 <= x <= COLS - footprint and 0 <= y <= ROWS - footprint):
        return False
    return not any(c in blocked for c in cells(pos, footprint))


def neighbors(pos):
    """The 8 adjacent cells inside the grid."""
    x, y = pos
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                nx, ny = x + dx, y + dy
                if 0 <= nx < COLS and 0 <= ny < ROWS:
                    yield (nx, ny)


class Board:
    def __init__(self, min_seg=3, max_seg=6):
        # `min_seg`/`max_seg` bound how many short wall segments get scattered in
        # the middle: the default is the cluttered arena; an open field passes
        # something small (e.g. 1..2).
        self.min_seg = min_seg
        self.max_seg = max_seg
        self.walls = self._generate_walls()

    def in_bounds(self, pos):
        return 0 <= pos[0] < COLS and 0 <= pos[1] < ROWS

    # ------------------------------------------------------------------ #
    # wall generation                                                    #
    # ------------------------------------------------------------------ #
    def _generate_walls(self):
        """Short wall segments in the middle of the map, without splitting the sides."""
        goals = [(x, y) for x in (COLS - 1, COLS - 2, COLS - 3) for y in range(ROWS)]
        for _ in range(40):
            walls = set()
            for _ in range(random.randint(self.min_seg, self.max_seg)):
                horiz = random.random() < 0.5
                length = random.randint(2, 4)
                cx = random.randint(4, COLS - 5)
                cy = random.randint(1, ROWS - 2)
                for i in range(length):
                    p = (cx + i, cy) if horiz else (cx, cy + i)
                    if self.in_bounds(p):
                        walls.add(p)
            if self._sides_connected(walls, (0, 0), goals):
                return walls
        return set()

    @staticmethod
    def _sides_connected(walls, origin, goals):
        seen = {origin}
        q = deque([origin])
        while q:
            x, y = q.popleft()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (x + dx, y + dy)
                    if (dx or dy) and 0 <= nb[0] < COLS and 0 <= nb[1] < ROWS \
                            and nb not in seen and nb not in walls:
                        seen.add(nb)
                        q.append(nb)
        return all(g in seen for g in goals)

    def diagonal_corner_blocked(self, a, b):
        """Is `a`->`b` a diagonal step squeezed between TWO walls at the corner?

        On a square grid, the diagonal step between (ax,ay) and (bx,by) grazes the
        two orthogonal corner cells, (bx,ay) and (ax,by). If both are walls you
        can neither move nor see through there. A single wall does not block it.
        """
        (ax, ay), (bx, by) = a, b
        if ax == bx or ay == by:
            return False
        return (bx, ay) in self.walls and (ax, by) in self.walls

    # ------------------------------------------------------------------ #
    # line of sight                                                      #
    # ------------------------------------------------------------------ #
    def los_clear(self, a, b):
        """Line of sight (Bresenham). Blocked by a wall on an intermediate cell,
        or by two walls closing a corner the line crosses diagonally."""
        (x0, y0), (x1, y1) = a, b
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while (x, y) != (x1, y1):
            e2 = 2 * err
            px, py = x, y
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
            if x != px and y != py \
                    and (x, py) in self.walls and (px, y) in self.walls:
                return False
            if (x, y) != (x1, y1) and (x, y) in self.walls:
                return False
        return True

    # ------------------------------------------------------------------ #
    # pathfinding (8 directions, cost 1 per step)                         #
    # ------------------------------------------------------------------ #
    def reachable(self, start, budget, blocked=frozenset(), footprint=1,
                  passable=frozenset()):
        """BFS of anchors -> {anchor: cost}. A `footprint`x`footprint` shape only
        lands where it fits whole (inside the grid, not touching `blocked`). Cells
        in `passable` (e.g. allies) can be crossed but not ended on."""
        dist = {start: 0}
        q = deque([start])
        while q:
            cur = q.popleft()
            if dist[cur] >= budget:
                continue
            for nb in neighbors(cur):
                if nb in dist or not fits(nb, footprint, blocked) \
                        or self.diagonal_corner_blocked(cur, nb):
                    continue
                dist[nb] = dist[cur] + 1
                q.append(nb)
        dist.pop(start, None)
        if passable:
            dist = {p: c for p, c in dist.items()
                    if not passable.intersection(cells(p, footprint))}
        return dist

    def path_to(self, start, goal, blocked=frozenset(), footprint=1):
        """Shortest anchor path ``[start, ..., goal]`` (8 directions, cost 1 per
        step). Returns ``[]`` if `goal` cannot be reached. Allies are not passed
        in `blocked` here: a path may cross an ally's cell, it just cannot end on
        one (the caller only ever asks for a `goal` that is a valid landing)."""
        if start == goal:
            return [start]
        prev = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            for nb in neighbors(cur):
                if nb not in prev and fits(nb, footprint, blocked) \
                        and not self.diagonal_corner_blocked(cur, nb):
                    prev[nb] = cur
                    q.append(nb)
        if goal not in prev:
            return []
        path = []
        c = goal
        while c is not None:
            path.append(c)
            c = prev[c]
        path.reverse()
        return path

    def path_step_toward(self, start, goal, budget, blocked=frozenset(),
                         footprint=1, target_cells=None, passable=frozenset()):
        """Anchor `budget` steps from `start` along the shortest path to touching
        `target_cells` (by default the `goal` cell itself). Cells in `passable`
        (allies) can be crossed but not stopped on: step back."""
        target_cells = target_cells or [goal]

        def touching(cur):
            return cells_distance(cells(cur, footprint), target_cells) <= 1

        prev = {start: None}
        q = deque([start])
        dest = None
        while q:
            cur = q.popleft()
            if touching(cur):
                dest = cur
                break
            for nb in neighbors(cur):
                if nb not in prev and fits(nb, footprint, blocked) \
                        and not self.diagonal_corner_blocked(cur, nb):
                    prev[nb] = cur
                    q.append(nb)

        if dest is None:
            dest = min(prev, key=lambda p: cells_distance(cells(p, footprint), target_cells))
        path = []
        c = dest
        while c is not None:
            path.append(c)
            c = prev[c]
        path.reverse()                          # [start, ..., dest]
        idx = min(budget, len(path) - 1)
        while idx > 0 and passable.intersection(cells(path[idx], footprint)):
            idx -= 1                             # do not stop on top of an ally
        return path[idx]

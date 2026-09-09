"""Board: grid geometry, walls, pathfinding and line of sight.

The `Board` only knows the terrain. Who stands where (units, ground objects) is
passed in as a set of blocked cells to the pathfinding calls, so the board never
depends on battle state.
"""

import heapq
import random
from collections import deque

COLS, ROWS = 16, 12


def chebyshev(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def grid_distance(a, b):
    """Diagonal-aware grid distance (D&D 3.5 / Pathfinder "every other diagonal
    costs 2"). Along the shortest route, `min(dx, dy)` steps are diagonal and cost
    1, 2, 1, 2, ...; the rest are straight and cost 1 each. Turns a range from a
    square into an octagon."""
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    lo, hi = min(dx, dy), max(dx, dy)
    return hi + lo // 2


def _is_diag(a, b):
    return a[0] != b[0] and a[1] != b[1]


def _step_cost(a, b, diags):
    """(cost, diagonals-so-far) of one 8-direction step. Straight = 1. Diagonals
    alternate 1, 2, 1, 2, ... over the move; `diags` counts how many have been
    taken before this step."""
    if not _is_diag(a, b):
        return 1, diags
    return (1, diags + 1) if diags % 2 == 0 else (2, diags + 1)


def route_cost(path, diags=0):
    """(total cost, diagonals taken) of walking `path` = [c0, c1, ...], starting
    from `diags` diagonals already spent this move."""
    cost = 0
    for a, b in zip(path, path[1:]):
        step, diags = _step_cost(a, b, diags)
        cost += step
    return cost, diags


def cells(pos, footprint=1):
    """Cells a `footprint`x`footprint` shape covers with its anchor (top-left) at `pos`."""
    x, y = pos
    return [(x + dx, y + dy) for dx in range(footprint) for dy in range(footprint)]


def cells_distance(cells_a, cells_b):
    """Smallest diagonal-aware distance between two sets of cells."""
    return min(grid_distance(p, q) for p in cells_a for q in cells_b)


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
    def __init__(self, min_seg=3, max_seg=6, walls=None):
        # `min_seg`/`max_seg` bound how many short wall segments get scattered in
        # the middle: the default is the cluttered arena; an open field passes
        # something small (e.g. 1..2). `walls` (a hand-authored layout from the
        # map editor) skips generation entirely and takes the given cells as-is.
        self.min_seg = min_seg
        self.max_seg = max_seg
        self.walls = ({tuple(w) for w in walls} if walls is not None
                      else self._generate_walls())

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
    # pathfinding (8 directions; diagonals alternate cost 1, 2, 1, 2 ...) #
    # ------------------------------------------------------------------ #
    def _dijkstra(self, start, blocked, footprint, diags=0, budget=None, goal=None):
        """Dijkstra over ``(anchor, diagonal parity)`` under the diagonal
        alternation rule (see `route_cost`). Returns ``(dist, prev)``:
        ``dist`` maps every anchor reachable within `budget` to its least cost;
        ``prev`` holds back-pointers for a least-cost route to each. `diags` is
        how many diagonals were already spent on the move before `start`."""
        start_state = (start, diags % 2)
        best = {start_state: 0}
        dist = {start: 0}
        prev = {start: None}
        pq = [(0, start, diags)]
        while pq:
            cost, cur, cd = heapq.heappop(pq)
            if cost > best.get((cur, cd % 2), cost):
                continue
            if goal is not None and cur == goal:
                break
            for nb in neighbors(cur):
                if not fits(nb, footprint, blocked) \
                        or self.diagonal_corner_blocked(cur, nb):
                    continue
                step, ncd = _step_cost(cur, nb, cd)
                nc = cost + step
                if budget is not None and nc > budget:
                    continue
                if nc < best.get((nb, ncd % 2), float("inf")):
                    best[(nb, ncd % 2)] = nc
                    heapq.heappush(pq, (nc, nb, ncd))
                    if nc < dist.get(nb, float("inf")):
                        dist[nb] = nc
                        prev[nb] = cur
        return dist, prev

    @staticmethod
    def _trace(prev, dest):
        path = []
        c = dest
        while c is not None:
            path.append(c)
            c = prev[c]
        path.reverse()
        return path

    def reachable(self, start, budget, blocked=frozenset(), footprint=1,
                  passable=frozenset(), diags=0):
        """Anchors -> {anchor: cost} within `budget`. A `footprint`x`footprint`
        shape only lands where it fits whole (inside the grid, not touching
        `blocked`). Cells in `passable` (e.g. allies) can be crossed but not ended
        on. `diags` = diagonals already spent this move (the alternation carries
        over across the clicks of one Move action)."""
        dist, _ = self._dijkstra(start, blocked, footprint, diags, budget)
        dist.pop(start, None)
        if passable:
            dist = {p: c for p, c in dist.items()
                    if not passable.intersection(cells(p, footprint))}
        return dist

    def path_to(self, start, goal, blocked=frozenset(), footprint=1, diags=0):
        """Least-cost anchor path ``[start, ..., goal]``. Returns ``[]`` if `goal`
        cannot be reached. Allies are not passed in `blocked` here: a path may
        cross an ally's cell, it just cannot end on one (the caller only ever asks
        for a `goal` that is a valid landing)."""
        if start == goal:
            return [start]
        _, prev = self._dijkstra(start, blocked, footprint, diags, goal=goal)
        if goal not in prev:
            return []
        return self._trace(prev, goal)

    def path_step_toward(self, start, goal, budget, blocked=frozenset(),
                         footprint=1, target_cells=None, passable=frozenset(),
                         diags=0):
        """Anchor as far as `budget` (in movement cost) from `start` along the
        least-cost path to touching `target_cells` (by default the `goal` cell).
        Cells in `passable` (allies) can be crossed but not stopped on: step back.

        Only the `budget` disc is explored -- a cell the unit cannot reach this
        turn can never be the pick, so a far-off target costs the same as a near
        one. This runs once per acting unit each turn."""
        target_cells = target_cells or [goal]
        dist, prev = self._dijkstra(start, blocked, footprint, diags, budget=budget)

        def touch(p):
            return cells_distance(cells(p, footprint), target_cells)

        reached = list(dist)
        touching = [p for p in reached if touch(p) <= 1]
        if touching:
            dest = min(touching, key=lambda p: dist[p])
        else:
            dest = min(reached, key=lambda p: (touch(p), dist[p]))

        path = self._trace(prev, dest)          # [start, ..., dest]
        cd, spent, idx = diags, 0, 0
        for i in range(1, len(path)):
            step, cd = _step_cost(path[i - 1], path[i], cd)
            if spent + step > budget:
                break
            spent, idx = spent + step, i
        while idx > 0 and passable.intersection(cells(path[idx], footprint)):
            idx -= 1                             # do not stop on top of an ally
        return path[idx]

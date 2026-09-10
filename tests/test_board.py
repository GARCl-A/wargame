"""Board geometry: pathfinding, line of sight, the diagonal rule."""

import random

from tests.helpers import abilities, Battle, Board, grid_distance, ROWS, Unit


def test_los_blocked_by_wall():
    b = Board()
    b.walls = {(5, 5)}
    assert b.los_clear((4, 5), (6, 5)) is False
    assert b.los_clear((4, 4), (4, 8)) is True


def test_two_walls_at_corner_block_diagonal_and_sight():
    b = Board()
    b.walls = {(4, 4), (5, 5)}
    reach = b.reachable((4, 5), 1)
    assert (5, 4) not in reach
    assert b.los_clear((4, 5), (5, 4)) is False
    assert b.los_clear((4, 5), (7, 2)) is False


def test_single_wall_at_corner_does_not_block_diagonal():
    b = Board()
    b.walls = {(5, 5)}
    reach = b.reachable((4, 5), 1)
    assert (5, 4) in reach
    assert b.los_clear((4, 5), (5, 4)) is True


def test_ally_lets_pass_but_not_stop_enemy_blocks():
    random.seed(0)
    batt = Battle([Unit("player"), Unit("player")], [Unit("enemy")])
    # wall on column 6 with a single door at (6,5): only way through
    batt.board.walls = {(6, y) for y in range(12) if y != 5}
    a, ally, foe = batt.units
    for u in batt.units:
        u.footprint = 1
    a.pos, a.ap, a.walking = (5, 5), 2, False
    ally.pos, foe.pos = (6, 5), (12, 9)
    reach = batt.reachable(a)
    assert (6, 5) not in reach                 # does not end on top of the ally
    assert (7, 5) in reach                     # but crosses through to the other side

    ally.pos, foe.pos = (12, 9), (6, 5)        # enemy in the chokepoint
    reach = batt.reachable(a)
    assert (6, 5) not in reach and (7, 5) not in reach   # enemy blocks completely


def test_path_to_returns_full_route():
    b = Board()
    b.walls = set()
    path = b.path_to((2, 2), (5, 2))
    assert path[0] == (2, 2) and path[-1] == (5, 2)
    assert len(path) == 4                              # 3 steps, cost 1 each
    assert b.path_to((0, 0), (0, 0)) == [(0, 0)]


def test_move_records_walked_path():
    random.seed(0)
    batt = Battle([Unit("player")], [Unit("enemy")])
    batt.board.walls = set()
    u = batt.units[0]
    u.pos, u.ap, u.walking = (3, 3), 2, False
    u.path = [u.pos]
    batt.move_unit(u, (5, 3))
    assert u.path[0] == (3, 3) and u.path[-1] == (5, 3)
    batt.move_unit(u, (5, 5))                          # second step, same turn
    assert u.path[0] == (3, 3) and u.path[-1] == (5, 5)


def test_reachable_respects_budget():
    b = Board()
    b.walls = set()
    reach = b.reachable((8, 6), 2)
    assert all(v <= 2 for v in reach.values())
    assert (10, 6) in reach and (11, 6) not in reach


def test_path_step_toward_stops_within_budget_for_a_far_goal():
    b = Board()
    b.walls = set()
    # goal well out of reach: still steps toward it, never past `budget`
    dest = b.path_step_toward((2, 6), (14, 6), budget=3)
    assert b.reachable((2, 6), 3).get(dest, 99) <= 3
    assert dest[0] > 2                                  # moved toward the goal
    # goal in reach: lands adjacent, not on top of it
    adj = b.path_step_toward((2, 6), (6, 6), budget=6)
    assert max(abs(adj[0] - 6), abs(adj[1] - 6)) == 1


def test_grid_distance_alternates_diagonals():
    # every other diagonal costs 2: N diagonals = N + N // 2
    assert grid_distance((0, 0), (1, 1)) == 1
    assert grid_distance((0, 0), (2, 2)) == 3
    assert grid_distance((0, 0), (3, 3)) == 4
    assert grid_distance((0, 0), (4, 4)) == 6
    # straight is untouched; adjacency (<= 1) matches Chebyshev
    assert grid_distance((0, 0), (5, 0)) == 5
    assert grid_distance((2, 2), (4, 2)) == 2
    # a mix: 2 straight + 3 diagonal
    assert grid_distance((0, 0), (5, 3)) == 5 + 1


def test_diagonal_move_costs_more_than_straight():
    b = Board()
    b.walls = set()
    reach = b.reachable((8, 6), 6)
    assert reach[(14, 6)] == 6                          # 6 straight
    assert reach[(12, 10)] == 6                         # 4 diagonal: 1+2+1+2
    assert (13, 11) not in reach                        # 5 diagonal would cost 7


def test_fractioned_walk_carries_the_diagonal_alternation():
    random.seed(0)
    batt = Battle([Unit("player")], [Unit("enemy")])
    batt.board.walls = set()
    u = batt.units[0]
    u.pos, u.ap, u.walking = (1, 1), 2, False
    u.path = [u.pos]
    batt.move_unit(u, (2, 2))                           # 1st diagonal: cost 1
    assert (u.moved, u.diag_steps) == (1, 1)
    batt.move_unit(u, (3, 3))                           # 2nd diagonal: cost 2
    assert (u.moved, u.diag_steps) == (3, 2)
    assert u.ap == 1                                    # still one Move action
    batt.move_unit(u, (4, 4))                           # 3rd diagonal: cost 1 again
    assert u.moved == 4


def test_dark_map_only_sees_own_cell():
    random.seed(1)
    batt = Battle([Unit("player")], [Unit("enemy")])
    batt.ground = []                                  # no torches on the ground
    for u in batt.units:                              # no light source, no darkvision
        u.weapon_hand = u.torch_hand = False
        u.inventory, u._ability = ["Sack"], abilities.get("none")
    p, e = batt.units
    p.pos, e.pos = (2, 2), (12, 9)
    assert batt.can_see(p, p.pos) is True
    assert batt.can_see(p, (5, 2)) is False


def test_a_non_flier_cannot_path_across_an_elevation_change():
    b = Board(walls=[], elevation={(4, y): -2 for y in range(ROWS)})
    reach = b.reachable((3, 5), budget=8)
    assert (5, 5) not in reach                     # the pit wall at column 4 blocks it
    assert b.reachable((3, 5), budget=8, vertical=True).get((5, 5))  # a flier crosses


def test_path_step_toward_commits_to_the_long_way_around_a_wall():
    """The route is planned over the whole board: a unit boxed against a wall
    takes the detour instead of standing at the dead end."""
    b = Board(walls=[(8, y) for y in range(11)])   # seals column 8, one gap at row 11
    step = b.path_step_toward((7, 3), (9, 3), budget=6, blocked=b.walls)
    assert step != (7, 3)                            # it moves toward the row-11 gap...
    assert step[1] > 3                               # ...downward, not stuck at the wall

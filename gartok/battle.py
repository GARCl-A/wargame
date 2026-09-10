"""Battle state: board, units, ground objects, initiative order and turn flow.

Resolving each action (attack, throw, ...) lives in `actions.py`; geometry and
pathfinding in `board.py`; vision and light in `vision.py`. `Battle` only holds
the state and coordinates the turn, exposing helpers the actions query.

Battle owns its *combatants*: it wraps every character it is given in a
`combatant.Combatant` (see there), so the fight never touches the persistent
roster and a rematch could reuse the same picks.
"""

from . import data, vision
from .board import COLS, ROWS, cells, chebyshev, cells_distance, route_cost
from .combatant import Combatant
from .data import d20
from .scenario import ArenaScenario

__all__ = ["Battle", "COLS", "ROWS", "chebyshev"]


class Battle:
    def __init__(self, player_units, enemy_units, scenario=None, daylight=True,
                 lethal=True, arena=False):
        self.log_lines = []
        self.daylight = daylight              # outdoor scenarios read this for ambient light
        self.lethal = lethal                 # False = arena bout: 0 HP knocks out, no permadeath
        self.arena = arena                   # True = fought in the pits: the Champion of the Pit title bites here
        self.scenario = scenario or ArenaScenario()
        self.player_units = [Combatant(u, "player") for u in player_units]
        self.enemy_units = [Combatant(u, "enemy") for u in enemy_units]
        self.setup()

    # ------------------------------------------------------------------ #
    def log(self, msg):
        self.log_lines.append(msg)
        del self.log_lines[:-200]

    def setup(self):
        self.log_lines.clear()
        self.ambient_light = False           # scenario.build sets the real value
        self.ground = []                     # GroundObject list (dropped weapons, torches)
        self.units = list(self.player_units) + list(self.enemy_units)
        for u in self.units:
            u.reset_battle_state()           # fresh state (also full heal on a rematch)
            u.nonlethal = not self.lethal    # 0 HP -> knocked out instead of dying

        self.creatures = []                  # neutral bodies (e.g. the Shepherd's sheep)
        self._pf_cache = {}                   # per-turn Dijkstra field cache (see _pf_field)
        # capture-the-flag: {"player": cell|None, "enemy": cell|None}, else None.
        # the player's flag is planted by `battle_screen`; the scenario drops the
        # enemy's during `build`.
        self.flags = ({"player": None, "enemy": None}
                      if getattr(self.scenario, "is_ctf", False) else None)
        self.scenario.build(self)            # board + deployment + scatter
        self.round_no = 1
        self.winner = None
        self._mopup_open = False              # enemies down, allies still bleeding out
        if self.is_ctf:
            self._assign_flag_runners()
        self._roll_initiative()
        self.log("--- Round 1 ---")
        self._announce_turn()

    def creature_cells(self):
        return {c for cr in self.creatures for c in cells(cr.pos, cr.footprint)}

    # ------------------------------------------------------------------ #
    # capture the flag                                                   #
    # ------------------------------------------------------------------ #
    @property
    def is_ctf(self):
        return self.flags is not None

    @property
    def awaiting_flag(self):
        """The player still has to plant their flag before the fight can start."""
        return self.is_ctf and self.flags["player"] is None

    def _assign_flag_runners(self):
        """Tag the fastest half of the enemy side as flag runners -- the AI sends
        them for the player's flag while the rest hold and fight."""
        ranked = sorted(self.enemy_units, key=lambda c: c.speed, reverse=True)
        cut = max(1, (len(ranked) + 1) // 2)      # ceil(half) -- a 3v3 sends 2 runners
        for i, c in enumerate(ranked):
            c.ctf_runner = i < cut

    def check_objective(self):
        """Let a caller (the screen, mid-turn) settle a scenario objective the
        instant it is met, instead of waiting for the turn to end."""
        if self.winner is None and self._check_winner():
            self.log(f"*** Victory: {self.winner} ***")

    def _roll_initiative(self):
        for u in self.units:
            u.initiative = d20() + u.initiative_bonus()
        self.order = sorted(self.units, key=lambda u: u.initiative, reverse=True)
        self.turn_idx = 0
        self.active.start_turn(self.log)

    # ------------------------------------------------------------------ #
    # state queries (used by actions, AI and UI)                         #
    # ------------------------------------------------------------------ #
    @property
    def active(self):
        return self.order[self.turn_idx]

    @property
    def mopping_up(self):
        """Enemies are down; the fight runs on only so standing allies can
        stabilize the dying (and the dying finish their death saves)."""
        return self._mopup_open and self.winner is None

    def cells_of(self, unit, pos=None):
        return cells(pos or unit.pos, unit.footprint)

    def elevation(self, unit, pos=None):
        """The floor height the unit stands on (its anchor cell)."""
        return self.board.elevation_at(pos or unit.pos)

    def unit_at(self, pos, include_downed=False):
        for u in self.units:
            if (u.alive or (include_downed and u.downed)) and pos in self.cells_of(u):
                return u
        return None

    def occupied(self, exclude=None):
        result = set()
        for u in self.units:
            if u.alive and u is not exclude:
                result.update(self.cells_of(u))
        return result

    def cells_by_side(self, unit):
        """({ally cells}, {enemy cells}) of living units, excluding `unit`.

        An enemy blocks passage and stopping; an ally can be crossed, just not
        ended on.
        """
        allies, enemies = set(), set()
        for u in self.units:
            if not u.alive or u is unit:
                continue
            dest = allies if u.team == unit.team else enemies
            dest.update(self.cells_of(u))
        return allies, enemies

    def units_distance(self, a, b):
        return cells_distance(self.cells_of(a), self.cells_of(b))

    def los_between(self, a, b):
        """Clear LOS between some cell of `a` and some cell of `b`."""
        return any(self.board.los_clear(ca, cb)
                   for ca in self.cells_of(a) for cb in self.cells_of(b))

    def ground_at(self, pos):
        for o in self.ground:
            if o.pos == pos:
                return o
        return None

    def ground_in_reach(self, unit):
        """Ground objects on the footprint or adjacent to it (for the PickUp action)."""
        ucells = self.cells_of(unit)
        return [o for o in self.ground
                if min(chebyshev(o.pos, c) for c in ucells) <= 1]

    # vision (delegates to vision.py) --------------------------------- #
    def can_see(self, observer, target_pos):
        return vision.can_see(self, observer, target_pos)

    def can_see_unit(self, observer, target):
        return vision.can_see_unit(self, observer, target)

    # ------------------------------------------------------------------ #
    # movement  (Move action: 1 point; 2 points per turn)                #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _walk_diags(unit):
        """Diagonals already spent in the walk `unit` is in the middle of (0 when
        no Move action is open -- a fresh walk starts the 1, 2, 1, 2 ... over)."""
        return unit.diag_steps if unit.walking else 0

    def _pf_field(self, start, footprint, diags, vertical, blocked):
        """A full-board Dijkstra scan ``(dist, prev)`` from `start`, memoised for
        this turn. `reachable` / `path_to` / `path_step_toward` each ask for the
        same scan several times per acting unit. The key is every input the scan
        depends on -- including the whole `blocked` set (walls + creatures + enemy
        cells), rebuilt by the caller every time -- so a hit is provably the
        identical computation: if anything moved, the key differs and it recomputes.

        The cache holds only plain int/tuple dicts (no unit or board references,
        nothing to keep alive for the GC) and is cleared at the top of every turn
        in `_advance_turn`, so it never holds more than a handful of entries."""
        key = (start, footprint, diags % 2, vertical, blocked)  # blocked (a frozenset) is part of the key
        field = self._pf_cache.get(key)
        if field is None:
            field = self.board._dijkstra(start, blocked, footprint, diags,
                                         vertical=vertical)
            self._pf_cache[key] = field
        return field

    def reachable(self, unit, budget=None):
        """Reachable anchors -> {pos: cost}. Straight steps cost 1; the diagonals
        along a route alternate 1, 2, 1, 2 ... (`board.route_cost`)."""
        if budget is None:
            if unit.walking:
                budget = unit.speed - unit.moved
            elif unit.ap >= 1:
                budget = unit.speed
            else:
                return {}
        allies, enemies = self.cells_by_side(unit)
        blocked = frozenset(enemies | self.board.walls | self.creature_cells())
        diags = self._walk_diags(unit)
        field = self._pf_field(unit.pos, unit.footprint, diags,
                               unit.can_move_vertically, blocked)
        return self.board.reachable(unit.pos, budget, blocked, unit.footprint,
                                    allies, diags,
                                    vertical=unit.can_move_vertically, field=field)

    def reachable_cells(self, unit):
        """Union of the cells the footprint would cover at each reachable anchor (UI highlight)."""
        result = set()
        for anchor in self.reachable(unit):
            result.update(cells(anchor, unit.footprint))
        return result

    def path_to(self, unit, dest):
        """The cells `unit` would walk through to reach the anchor `dest`,
        ``[unit.pos, ..., dest]`` (``[]`` if unreachable)."""
        _, enemies = self.cells_by_side(unit)
        blocked = frozenset(enemies | self.board.walls | self.creature_cells())
        diags = self._walk_diags(unit)
        field = self._pf_field(unit.pos, unit.footprint, diags,
                               unit.can_move_vertically, blocked)
        return self.board.path_to(unit.pos, dest, blocked, unit.footprint, diags,
                                  vertical=unit.can_move_vertically, field=field)

    def path_step_toward(self, unit, goal, budget):
        allies, enemies = self.cells_by_side(unit)
        blocked = frozenset(enemies | self.board.walls | self.creature_cells())
        target = self.unit_at(goal)
        target_cells = self.cells_of(target) if target else None
        diags = self._walk_diags(unit)
        field = self._pf_field(unit.pos, unit.footprint, diags,
                               unit.can_move_vertically, blocked)
        return self.board.path_step_toward(unit.pos, goal, budget, blocked, unit.footprint,
                                           target_cells, allies, diags,
                                           vertical=unit.can_move_vertically, field=field)

    def move_unit(self, unit, dest):
        reach = self.reachable(unit)
        if dest not in reach:
            return False
        if not unit.walking:                 # start the Move action (1 point)
            if unit.ap < 1:
                return False
            unit.ap -= 1
            unit.walking = True
            unit.moved = 0
            unit.diag_steps = 0              # a fresh walk restarts the diagonal alternation
            self.log(f"{unit.name} moves (1 action point).")
        segment = self.path_to(unit, dest) or [unit.pos, dest]
        step_cost, unit.diag_steps = route_cost(segment, unit.diag_steps)
        unit.moved += step_cost
        unit.path.extend(segment[1:])         # the cells walked this turn so far
        unit.pos = dest
        if unit.moved >= unit.speed:          # walk exhausted; next step = new action
            unit.walking = False
        return True

    # ------------------------------------------------------------------ #
    # turn flow                                                          #
    # ------------------------------------------------------------------ #
    def _living_side(self, team):
        return [u for u in self.units if u.alive and u.team == team]

    def _check_winner(self):
        if self.winner:
            return self.winner

        forced = self.scenario.win_check(self)
        if forced:
            # the scenario's own objective settled the fight before either side
            # was wiped -- honour it, then tidy up like a normal finish.
            self.winner = forced
            if forced == "enemy" and self.lethal:
                self._wipe_side("player")
            self._resolve_dangling_dying()
            return self.winner

        players_up = self._living_side("player")
        enemies_up = self._living_side("enemy")
        if players_up and enemies_up:
            return None

        if not players_up and enemies_up:
            # squad wiped while the enemy still stands.
            self.winner = "enemy"
            if self.lethal:
                # a lost lethal battle is total -- everyone on the ground goes with it.
                self._wipe_side("player")
                self._resolve_dangling_dying()
            # a lost arena bout: the knocked-out squad just loses the match.
            return self.winner

        # The enemy side is gone. If allies are still bleeding out and someone is
        # standing to help, let the fight run on: the standing allies get their
        # turns to stabilize the dying, and the dying keep rolling death saves,
        # before the battle is finally called.
        dying_allies = [u for u in self.units
                        if u.team == "player" and u.status == "dying"]
        if players_up and dying_allies:
            if not self._mopup_open:
                self._mopup_open = True
                self.log("Enemies down -- stabilize the downed allies before "
                         "the fight ends.")
            return None

        self.winner = "player"
        self._resolve_dangling_dying()
        return self.winner

    # ------------------------------------------------------------------ #
    # falling, stabilizing and death                                     #
    # ------------------------------------------------------------------ #
    def apply_fall(self, unit, drop, log):
        """Resolve a drop of `drop` floor levels: the first level is free, every
        level after that is 1d6. A flier floats down and takes nothing."""
        if drop <= 1 or unit.flies:
            return
        dmg = data.roll(drop - 1, 6)
        log(f"{unit.name} falls {drop} levels -> {dmg} damage ({drop - 1}d6).")
        unit.take_damage(dmg, log)

    def _death_save(self, unit):
        """d20 >= DEATH_SAVE_MIN -> stable; otherwise dead. Logs and returns the
        new status."""
        roll = d20()
        if roll >= data.DEATH_SAVE_MIN:
            unit.status = "stable"
            self.log(f"{unit.name}: death save d20({roll}) -> survives, "
                     f"unconscious at 0 HP.")
        else:
            unit.status = "dead"
            self.log(f"{unit.name}: death save d20({roll}) -> dies.")
        return unit.status

    def stabilize(self, unit):
        """Bring a dying unit to `stable` (from a successful Stabilize / FirstAid)."""
        unit.status = "stable"
        self.log(f"{unit.name} was stabilized (unconscious at 0 HP until the end of the fight).")

    def repair(self, unit):
        """Bring a broken automaton back into the fight at 1 HP (successful ally
        Stabilize). No death clock was ever running -- there is no time limit."""
        unit.status = "up"
        unit.hp = 1
        unit.death_clock = 0
        self.log(f"{unit.name} is back online (1 HP).")

    def _resolve_dying_turn(self, unit):
        """The dying unit's turn: tick the counter, roll the death save on the DYING_TURNS-th."""
        unit.death_clock += 1
        if unit.death_clock >= data.DYING_TURNS:
            self._death_save(unit)
        else:
            self.log(f"{unit.name} is dying ({unit.death_clock}/{data.DYING_TURNS}).")

    def _resolve_dangling_dying(self):
        """Battle over: every unit still dying makes one last death save."""
        for u in self.units:
            if u.status == "dying":
                self._death_save(u)

    def _wipe_side(self, team):
        """A lost battle is total: everyone on this side still on the ground
        (dying, stabilized or broken) is lost with the defeat."""
        for u in self.units:
            if u.team == team and u.status in ("dying", "stable", "broken"):
                u.status = "dead"
                self.log(f"{u.name} doesn't survive their wounds after the defeat.")

    def _announce_turn(self):
        u = self.active
        self.log(f"{u.name}'s turn ({u.team}).")

    def end_turn(self):
        if self.winner:
            return
        self.active.end_turn(self.log)       # demoralized expires at the end of the sufferer's turn
        self._advance_turn()

    def _advance_turn(self):
        """Advance to the next standing unit. A dying unit gets a turn on the way
        (its death counter ticks / it rolls the save); stable and dead are skipped."""
        self._pf_cache.clear()               # the Dijkstra field cache is per-turn
        for _ in range(len(self.order) + 1):
            self.turn_idx += 1
            if self.turn_idx >= len(self.order):
                self.turn_idx = 0
                self.round_no += 1
                self.log(f"--- Round {self.round_no} ---")
            u = self.active
            if u.status == "dying":
                self._resolve_dying_turn(u)
                if self._check_winner():
                    self.log(f"*** Victory: {self.winner} ***")
                    return
                continue
            if u.alive:
                break
        if self._check_winner():
            self.log(f"*** Victory: {self.winner} ***")
            return
        self.active.start_turn(self.log)
        self._announce_turn()

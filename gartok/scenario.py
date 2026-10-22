"""Building the map for one battle: terrain, deployment and scatter.

Kept apart from `Battle` (which owns turn flow and state) so a real scenario
system later -- objectives, prebuilt maps, deployment zones -- has a seam to slot
into instead of unpicking `Battle.setup`. A scenario's `build` receives the
battle and populates its `board`, `units[*].pos`, `creatures`, `ground` and the
`ambient_light` flag.

`Scenario` is the shared machinery (side deployment, the unit's own creatures,
torch scatter). A concrete location on the world map picks a subclass:
- `ArenaScenario` -- the dungeon pit fight: cluttered, always dark, torches around;
- `WildsScenario` (or `ErmosScenario`) -- open country: `outdoor`, so ambient light follows the
  campaign clock (`battle.daylight`) -- lit by day, pitch dark by night (bring
  your own torch; nothing scattered).
- `CustomScenario` -- a map hand-laid in the editor (`map_lib` dict): fixed
  walls, torches and deployment zones (player / generic enemy / named NPC), no
  random scatter.
- `FlagScenario` / `CustomFlagScenario` -- capture the flag (the `_FlagObjective`
  mixin) on the procedural pit / on an authored map.
"""

import functools
import random

from . import data, encounters
from .board import COLS, ROWS, Board, cells
from .ground import Creature, GroundObject


class Scenario:
    """Base scenario: side deployment + the unit's own creatures. Subclasses set
    the terrain (`_make_board`) and the lighting (`ambient_light` / `torch_count`)."""

    floor = "stone"          # the board's look (`ui/floors.py`); presentation only
    ambient_light = False    # indoor default: seen only by torchlight / darkvision
    outdoor = False          # outdoor: ambient light tracks the clock (battle.daylight)
    torch_count = 6
    strips_the_dead = False  # the loot takes what every body wore, not only what it carried (loot.field_loot)

    def build(self, battle):
        battle.board = self._make_board()
        battle.ambient_light = battle.daylight if self.outdoor else self.ambient_light
        self._deploy(battle)
        self._place_creatures(battle)
        self._scatter_torches(battle)
        self._place_ai_traps(battle)

    def on_round(self, battle):
        """A new round begins -- a scenario with a clock of its own (reinforcements,
        a hint) hooks here. The base scenario has none."""

    def on_turn_start(self, battle, unit):
        """`unit`'s turn begins (after its own start-of-turn effects)."""

    def on_turn_end(self, battle, unit):
        """`unit` ends its turn, before its end-of-turn effects."""

    def on_pick_up(self, battle, unit, obj):
        """`unit` just picked `obj` (a `GroundObject`) up."""

    def _place_ai_traps(self, battle):
        """The AI automatically places one trap from its inventory, if it has any,
        near its starting position before the battle starts."""
        for u in battle.enemy_units:
            trap_to_place = None
            if "Bear Trap" in u.inventory:
                trap_to_place = "Bear Trap"
            elif "Alarm Trap" in u.inventory:
                trap_to_place = "Alarm Trap"
                
            if trap_to_place:
                taken = battle.occupied() | battle.board.walls | battle.creature_cells() | {o.pos for o in battle.ground}
                candidates = [p for c in battle.cells_of(u) for p in battle.board.neighbors(c)
                              if p not in taken and battle.board.in_bounds(p)]
                if candidates:
                    pos = random.choice(candidates)
                    battle.ground.append(GroundObject.trap(pos, trap_to_place.lower(), u.team))
                    u.inventory.remove(trap_to_place)
                    # For now, AI places just one trap per unit.

    def _make_board(self):
        return Board()

    def can_withdraw(self, battle):
        """May the player's side leave the field now as winners (`Battle.withdraw`)? Only
        a scenario whose objective can be met before every foe is down says yes."""
        return False

    held_note = "The last foe is down."

    def holds_field(self, battle):
        """Does the fight run on once every foe is down (`Battle._check_winner`)? A place the
        squad has to walk out of says yes; `held_note` is the log line when it starts."""
        return False

    def after_battle(self, guild, battle):
        """What the fight leaves in the world once it is over (`campaign.absorb_battle`).
        The base scenario leaves nothing."""

    def win_check(self, battle):
        """Force a winner on a non-elimination objective: return "player" or
        "enemy" to end the fight now, or None to fall through to the default
        rule (a side loses when every member is down). `battle._check_winner`
        consults this first, every turn. The base scenario has no objective
        beyond wiping the other side, so it always returns None."""
        return

    # ------------------------------------------------------------------ #
    def _spawn_cells(self, team):
        """A side's edge columns -- the base deployment area."""
        cols, rows = self._cols, self._rows
        xs = (0, 1, 2) if team == "player" else (cols - 3, cols - 2, cols - 1)
        return [(x, y) for x in xs for y in range(rows)]

    def _deploy_cells(self, u):
        """Ordered candidate cells for `u` (the first that fits wins). Base: that
        side's edge columns in random order. `CustomScenario` puts the authored
        zones in front."""
        area = list(self._spawn_cells(u.team))
        random.shuffle(area)
        return area

    def _deploy(self, battle):
        self._cols, self._rows = battle.board.cols, battle.board.rows
        taken = set(battle.board.walls)
        for u in battle.units:
            self._place(u, self._deploy_cells(u), taken, battle.board)

    @staticmethod
    def _place(u, candidates, taken, board):
        for p in candidates:
            shape = cells(p, u.footprint)
            if all(board.in_bounds(c) for c in shape) and not (taken & set(shape)):
                u.pos = p
                taken.update(shape)
                return
        u.pos = candidates[0] if candidates else (0, 0)    # fallback: crowded map

    def _place_creatures(self, battle):
        """Neutral creatures that come with a unit (e.g. the Shepherd's sheep)."""
        taken = battle.occupied() | battle.board.walls
        for u in battle.units:
            name = getattr(u, "starting_creature", None)
            if not name:
                continue
            base = data.CREATURE_ITEMS[name]
            candidates = [p for c in battle.cells_of(u) for p in battle.board.neighbors(c)
                          if p not in taken and battle.board.in_bounds(p)]
            pos = random.choice(candidates) if candidates else u.pos
            taken.add(pos)
            battle.creatures.append(Creature(name, base["token"], pos, base["footprint"]))

    def _scatter_torches(self, battle):
        if not self.torch_count or battle.ambient_light:
            return
        taken = (battle.occupied() | battle.board.walls | battle.creature_cells()
                 | {o.pos for o in battle.ground})
        free = [(x, y) for x in range(battle.board.cols)
                for y in range(battle.board.rows) if (x, y) not in taken]
        random.shuffle(free)
        for p in free[:self.torch_count]:
            battle.ground.append(GroundObject.torch(p))


class ArenaScenario(Scenario):
    """The dungeon pit fight the game has shipped with: cluttered wall segments,
    no ambient light, torches scattered anywhere on the floor to fight over."""

    floor = "arena"


def own_half(team, cols=COLS):
    """The columns a side may keep its flag in: the player's is the left half of
    the board, the enemy's the right."""
    mid = cols // 2
    return range(mid) if team == "player" else range(mid, cols)


class _FlagObjective:
    """Capture the flag: each side has a flag, and a bout is won by carrying
    the *other* side's flag back to your own -- KO everyone and walk it home,
    or just run it past them. Stepping onto an unclaimed flag scoops it up
    (no action spent); it then rides along at the carrier's position until
    they either plant it back on their own flag's cell (a capture) or go
    down, dropping it right where they fell for anyone to pick up again. The
    player plants theirs anywhere in the left half at the start
    (`battle.flags["player"]`, set by `battle_screen`); the enemy's is dropped
    in the right half by `auto_place_enemy_flag`, which the concrete
    scenario's `build` must call after `super().build`.

    Mixed in front of a terrain scenario: `FlagScenario` (the procedural pit),
    `CustomFlagScenario` (a map hand-laid in the editor)."""

    is_ctf = True

    def build(self, battle):
        super().build(battle)
        self.auto_place_enemy_flag(battle)

    def auto_place_enemy_flag(self, battle, rng=random):
        """Drop the enemy flag on a random free cell of the right half (not a
        wall, not under a unit). Falls back to any free cell if the half is
        somehow full."""
        cols, rows = battle.board.cols, battle.board.rows
        taken = battle.occupied() | battle.board.walls
        free = [(x, y) for x in own_half("enemy", cols) for y in range(rows)
                if (x, y) not in taken]
        if not free:
            free = [(x, y) for x in range(cols) for y in range(rows)
                    if (x, y) not in taken]
        battle.flags["enemy"] = rng.choice(free) if free else (cols - 1, rows // 2)

    def _update_carriers(self, battle):
        """Drop anything its carrier can no longer hold (downed), then let a
        standing fighter scoop up whichever flag they are standing on -- only
        the *other* team may carry a given flag."""
        for team, carrier in battle.flag_carrier.items():
            if carrier is not None and not carrier.alive:
                battle.flags[team] = carrier.pos
                battle.flag_carrier[team] = None

        for team, pos in battle.flags.items():
            if battle.flag_carrier[team] is not None or pos is None:
                continue                          # already held, or still being planted
            holder = next((u for u in battle.units
                          if u.alive and u.team != team and pos in battle.cells_of(u)), None)
            if holder is not None:
                battle.flag_carrier[team] = holder

    def win_check(self, battle):
        if battle.flags["player"] is None or battle.flags["enemy"] is None:
            return None                       # still planting -- no objective yet
        self._update_carriers(battle)
        for carrier in battle.flag_carrier.values():
            if carrier is None or not carrier.alive:
                continue
            home = battle.flags[carrier.team]     # the carrier's own side's flag
            if home is not None and home in battle.cells_of(carrier):
                return carrier.team
        return None


class FlagScenario(_FlagObjective, ArenaScenario):
    """Capture the flag in the pits (the arena's second stage): the cluttered
    `ArenaScenario` floor and torch scatter, plus the flag objective."""


class WildsScenario(Scenario):
    """Open country: sparse walls, `outdoor` -- lit by day, pitch dark by night.
    Nothing lying around: bring your own torch."""

    floor = "grass"
    outdoor = True
    torch_count = 0

    def _make_board(self):
        return Board(min_seg=1, max_seg=2)


ErmosScenario = WildsScenario


class StreetScenario(Scenario):
    """City streets: `outdoor` -- lit by day, lit around street torches by night."""

    floor = "cobble"
    outdoor = True
    torch_count = 6


def scenario_for(node):
    """A node's fight scenario: its own `node.scenario()`, `StreetScenario` inside the
    City's jurisdiction (daylight by day, street torches at night), or `WildsScenario`
    out in the open -- on the node's own floor when it names one (a road's packed earth)."""
    if node.scenario is not None:
        scen = node.scenario()
    elif getattr(node, "jurisdiction", None) == "the_city":
        scen = StreetScenario()
    else:
        scen = WildsScenario()
    if getattr(node, "floor", None):
        scen.floor = node.floor
    return scen


class ReplayScenario(Scenario):
    """A fight put back at the opening row of a combat log (`combat_log.rebuild`): its board, the
    cells each unit stood on and the light, with nothing rolled. Only the base rule (a side loses
    when it is all down) carries over."""

    def __init__(self, start):
        self.start = start
        self.floor = start["board"].get("floor", Scenario.floor)

    def _make_board(self):
        b = self.start["board"]
        return Board(walls=b["walls"], elevation=b["elevation"], ropes=b["ropes"],
                     water=b["water"], cols=b["cols"], rows=b["rows"])

    def build(self, battle):
        battle.board = self._make_board()
        battle.ambient_light = self.start["ambient_light"]
        for u, vals in zip(battle.units, self.start["state"]["units"]):
            u.pos = (vals[0], vals[1])
        for kind, x, y, name in self.start["state"]["world"]["ground"]:
            if kind == GroundObject.TORCH:
                battle.ground.append(GroundObject.torch((x, y)))
            elif kind == GroundObject.WEAPON:
                battle.ground.append(GroundObject.weapon((x, y), name))


class ReplayFlagScenario(_FlagObjective, ReplayScenario):
    """A capture-the-flag fight put back at its opening: the replay's board and cells, and both
    flags where the log has them once the player's was planted (`planted`)."""

    def __init__(self, start, planted):
        super().__init__(start)
        self.planted = {team: tuple(cell) for team, cell in planted.items()}

    def auto_place_enemy_flag(self, battle, rng=random):
        battle.flags.update(self.planted)


class CustomScenario(Scenario):
    """A battle built from a map laid out in the editor (`map_lib`): fixed walls,
    fixed torches, and the deployment cells the author painted -- a player zone, a
    generic enemy zone, and an NPC zone for a named opponent (Adelio and the
    like). Falls back to the base edge columns for whatever the map leaves blank.
    What the author did not light stays dark -- no torch scatter."""

    def __init__(self, data):
        self.ambient_light = bool(data.get("ambient_light"))
        self.outdoor = bool(data.get("outdoor"))
        self.floor = data.get("floor") or ("grass" if self.outdoor else Scenario.floor)
        self._cols = int(data.get("cols") or COLS)
        self._rows = int(data.get("rows") or ROWS)
        self._walls = [tuple(c) for c in data.get("walls", [])]
        self._torches = [tuple(c) for c in data.get("torches", [])]
        self._elevation = {(e[0], e[1]): e[2] for e in data.get("elevation", [])
                           if len(e) >= 3}
        self._ropes = [tuple(c) for c in data.get("ropes", [])]
        self._water = [tuple(c) for c in data.get("water", [])]
        self._traps = [tuple(c) for c in data.get("traps", []) if len(c) >= 3]
        self._relics = [list(c) for c in data.get("relics", []) if len(c) >= 3]
        self._chests = [list(c) for c in data.get("chests", []) if len(c) >= 3]
        self.secret_walls = {tuple(c) for c in data.get("secret_walls", [])}
        self.escape_cells = {tuple(c) for c in data.get("escape_cells", [])}
        self._zones = {"player": [tuple(c) for c in data.get("deploy_player", [])],
                       "enemy": [tuple(c) for c in data.get("deploy_enemy", [])],
                       "npc": [(e[0], e[1]) for e in data.get("deploy_npc", [])]}

    def _make_board(self):
        return Board(walls=self._walls, elevation=self._elevation, ropes=self._ropes,
                     water=self._water, cols=self._cols, rows=self._rows)

    def build(self, battle):
        super().build(battle)
        battle.secret_walls = set(getattr(self, "secret_walls", set()))
        battle.escape_cells = set(getattr(self, "escape_cells", set()))
        for tr in getattr(self, "_traps", []):
            if len(tr) >= 3 and battle.board.in_bounds((tr[0], tr[1])):
                battle.ground.append(GroundObject.trap((tr[0], tr[1]), str(tr[2]).lower(), "enemy"))
        for rel in getattr(self, "_relics", []):
            if len(rel) >= 3 and battle.board.in_bounds((rel[0], rel[1])):
                battle.ground.append(GroundObject.relic((rel[0], rel[1]), rel[2]))
        for ch in getattr(self, "_chests", []):
            if len(ch) >= 3 and battle.board.in_bounds((ch[0], ch[1])):
                battle.ground.append(GroundObject.chest((ch[0], ch[1]), list(ch[2])))

    @staticmethod
    def _is_npc(u):
        """A named library character (Adelio, a hand-built champion), not a
        generated `Unit("enemy")`."""
        return bool(getattr(u, "arena_role", None)) or not getattr(u, "_auto_name", True)

    def _deploy_cells(self, u):
        if u.team == "player":
            order = [self._zones["player"]]
        else:
            slot = getattr(u, "map_cell", None)   # `map_lib.npc_units` pins each NPC to its cell
            npc, enemy = self._zones["npc"], self._zones["enemy"]
            if slot is not None:
                order = [[slot], npc, enemy]
            elif self._is_npc(u):
                order = [npc, enemy]
            else:
                order = [enemy, npc]
        cells_ = []
        for zone in order + [self._spawn_cells(u.team)]:
            for c in zone:
                if c not in cells_:
                    cells_.append(c)
        return cells_

    def _scatter_torches(self, battle):
        if battle.ambient_light:
            return
        taken = battle.occupied() | battle.board.walls | battle.creature_cells()
        for p in self._torches:
            if p not in taken and battle.board.in_bounds(p):
                battle.ground.append(GroundObject.torch(p))


class CustomFlagScenario(_FlagObjective, CustomScenario):
    """Capture the flag on a map hand-laid in the editor: the authored board,
    walls, torches and deploy zones (`CustomScenario`), plus the flag objective
    (`_FlagObjective`) -- same rules as the pit `FlagScenario`, only the terrain
    is authored. The Games' boss bout fights here (`arena.boss_bout`); the map's
    `deploy_npc` places the Ribbit brothers, both sides race, the symmetric map
    is the fairness."""


class AncientRuinsScenario(Scenario):
    """The game's first true dungeon: Ruins of the Ancient Library.

    A 30x18 continuous subterranean complex of 5 interconnected chambers:
    - Chamber 1 (Guardian Room): Sentry constructs guarding the entrance hall.
    - Chamber 2 (Trap Gauntlet): A corridor rigged with Bear Traps and an Alarm Trap.
    - Chamber 3 & 4 (Secret Vault): Behind a concealed wall mechanism; contains an ancient chest with loot.
    - Chamber 5 (Boss Sanctum): 'The Ancient Archivist' guarding the stone pedestal with the Ancient Codex.
    """

    ambient_light = False
    outdoor = False
    torch_count = 0

    def __init__(self, cleared=None):
        """`cleared` is `Guild.ruins_cleared`: the foes slain and the things taken on earlier
        delves, which this one leaves out."""
        from . import map_lib
        try:
            m = map_lib.load_map("ancient-ruins")
        except OSError:
            m = {}
        self._cols = int(m.get("cols", 30))
        self._rows = int(m.get("rows", 18))
        self.ambient_light = m.get("ambient_light", False)
        self.outdoor = m.get("outdoor", False)
        self.floor = m.get("floor", Scenario.floor)
        self._walls = [tuple(c) for c in m.get("walls")] if "walls" in m else self._build_walls()
        self._torches = [tuple(c) for c in m.get("torches", [(2, 4), (2, 12), (18, 1), (19, 8), (24, 8)])]
        self._traps = [list(c) for c in m.get("traps", [[11, 8, "bear trap"], [13, 8, "alarm trap"]])]
        self._chests = [list(c) for c in m.get("chests", [[18, 3, ["Scroll of Sleep", "Semi-precious Gemstone", "50 Copper"]]])]
        self._relics = [list(c) for c in m.get("relics", [[27, 11, data.CODEX_ITEM]])]
        self.secret_walls = {tuple(c) for c in m.get("secret_walls", [[14, 6]])}
        self.escape_cells = {tuple(c) for c in m.get("escape_cells", [[0, 7], [0, 8], [1, 7], [1, 8]])}
        self._player_deploy = [tuple(c) for c in m.get("deploy_player",
            [(1, 7), (1, 8), (2, 7), (2, 8), (2, 6), (2, 9), (3, 7), (3, 8)])]
        self.cleared = set(cleared or ())
        self.enemies = []
        for i, u in enumerate(map_lib.npc_units(m)):
            u.ruins_key = f"npc:{i}"
            if u.ruins_key not in self.cleared:
                self.enemies.append(u)

    def _build_walls(self):
        w = set()
        cols, rows = self._cols, self._rows
        # Outer boundary
        for x in range(cols):
            w.add((x, 0))
            w.add((x, rows - 1))
        for y in range(rows):
            if y not in (7, 8):  # Entrance doorway at (0, 7) and (0, 8)
                w.add((0, y))
            w.add((cols - 1, y))

        # Solid dead-space blocks
        for x in range(1, 9):
            for y in range(1, 3):
                w.add((x, y))
        for x in range(1, 9):
            for y in range(15, rows - 1):
                w.add((x, y))
        for x in range(9, 16):
            for y in range(14, rows - 1):
                w.add((x, y))
        for x in range(23, cols - 1):
            for y in range(1, 6):
                w.add((x, y))
        for x in range(16, cols - 1):
            for y in range(16, rows - 1):
                w.add((x, y))

        # Chamber 1 divider (between room 1 and corridor)
        for y in (3, 4, 5, 6, 7, 10, 11, 12, 13, 14):
            w.add((8, y))
        # Pillars in Chamber 1
        w.add((4, 5))
        w.add((4, 11))

        # Chamber 2 (Corridor) walls
        for x in range(9, 15):
            w.add((x, 6))  # Note: (14, 6) is the secret wall
            w.add((x, 13))

        # Vault (Chambers 3 & 4) walls
        for y in range(1, 7):
            w.add((13, y))
            w.add((22, y))
        for x in range(14, 23):
            w.add((x, 6))

        # Chamber 5 (Boss Sanctum) walls and pillars
        for y in (6, 7, 8, 9, 10, 13, 14, 15):
            w.add((15, y))
        w.add((19, 8))
        w.add((19, 13))
        w.add((24, 8))
        w.add((24, 13))

        return w

    def _make_board(self):
        return Board(walls=self._walls, cols=self._cols, rows=self._rows)

    def _deploy_cells(self, u):
        if u.team == "player":
            return self._player_deploy
        cell = getattr(u, "map_cell", None)
        if cell:
            return [cell]
        return [(25, 11), (6, 6), (6, 9)]

    def build(self, battle):
        super().build(battle)
        battle.secret_walls = set(self.secret_walls)
        battle.escape_cells = set(self.escape_cells)

        for p in self._torches:
            if p not in battle.board.walls:
                battle.ground.append(GroundObject.torch(p))

        for i, tr in enumerate(self._traps):
            self._lay(battle, f"trap:{i}", GroundObject.trap((tr[0], tr[1]), str(tr[2]).lower(), "enemy"))
        for i, ch in enumerate(self._chests):
            if len(ch) >= 3 and battle.board.in_bounds((ch[0], ch[1])):
                self._lay(battle, f"chest:{i}", GroundObject.chest((ch[0], ch[1]), list(ch[2])))
        for i, rel in enumerate(self._relics):
            if len(rel) >= 3 and battle.board.in_bounds((rel[0], rel[1])):
                self._lay(battle, f"relic:{i}", GroundObject.relic((rel[0], rel[1]), rel[2]))

    def _lay(self, battle, key, obj):
        if key not in self.cleared:
            obj.ruins_key = key
            obj.fixture = True
            battle.ground.append(obj)

    def win_check(self, battle):
        players = list(battle.player_units)
        standing = [u for u in players if u.alive]
        fled = [u for u in players if u.fled]
        has_codex = any(
            data.CODEX_ITEM in getattr(u, "inventory", []) or 
            data.CODEX_ITEM in getattr(u, "picked_up_items", []) 
            for u in players
        )
        if not standing and fled and (has_codex or not any(u.alive for u in battle.foe_units)):
            return "player"
        return None

    held_note = "The last foe is down. The ruins are yours to search -- leave by the entrance."

    def holds_field(self, battle):
        return True

    def treasure_on_floor(self, battle):
        """The chests and relics still where the ruins keep them: someone has to go and take them."""
        return [o for o in battle.ground if o.is_relic or o.is_chest]

    def after_battle(self, guild, battle):
        """The ruins remember the delve: a foe down stays down, and what a hand took off the
        floor is not there next time. The rest (a chest unopened, a trap unsprung, the Codex)
        is part of the place, not field loot: it waits for the next delve."""
        for c in battle.foe_units:
            key = getattr(c.char, "ruins_key", None)
            if key and not c.alive:
                guild.ruins_cleared.add(key)
        left = {o.ruins_key for o in battle.ground if getattr(o, "ruins_key", None)}
        guild.ruins_cleared |= self._laid_keys() - left

    def _laid_keys(self):
        keys = {f"trap:{i}" for i in range(len(self._traps))}
        keys |= {f"chest:{i}" for i in range(len(self._chests))}
        keys |= {f"relic:{i}" for i in range(len(self._relics))}
        return keys - self.cleared


def ruins_empty(guild):
    """Every foe of the Ancient Ruins is dead and its chests and the Codex are taken: nothing is
    left down there."""
    return _ruins_keys() <= guild.ruins_cleared


@functools.cache
def _ruins_keys():
    scenario = AncientRuinsScenario()
    return frozenset({u.ruins_key for u in scenario.enemies}
                     | {f"chest:{i}" for i in range(len(scenario._chests))}
                     | {f"relic:{i}" for i in range(len(scenario._relics))})

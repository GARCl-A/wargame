"""The Dragon's Lair: the Blood Cult's third errand (`missions.BLOOD_CLUTCH`), a heist under the Mine.

- **The lair** is a secret node (`world.Node.hidden`) off the Mine: with the job out, a group at
  the Mine searches the deep galleries (`search`, a Wisdom check); found, it stays on the map.
- **Inside** (`LairScenario`), one dark, hot cave: the way in, the kobolds' warren, the hoard, the
  clutch, and the dragon (`npcs/dragon.json`, racial 20) asleep in the hall beside them.
- **Kobold patrols** walk their rounds (their `patrol_route`, `ai.scripted._patrol`). One that sees the
  squad challenges it before ringing the alarm (`contact`: a dialogue on the board,
  `dialogue.Challenge`): a Draconic speaker can bluff (+2 DC for every bluff already told here)
  or pay; anyone can fight, and a patrol not silenced before its next turn rings the alarm. A
  patrol that sees someone carrying an egg does not talk.
- **The dragon sleeps in stages** (asleep -> stirring -> awake) that noise fills (`Sleep`): running
  or heavy armour near it, a sneak that fails (DEX against 10 + its WIS), a blow struck anywhere,
  a handful of the hoard, an egg lifted, the alarm. Stirring, it wakes on anyone it sees close;
  awake, its breath sets the lair alight.
- **Won** when the squad stands at the way in with an egg and leaves (`withdraw`), or the dragon
  falls -- then the eggs still on the ground are the guild's too.
"""

import random

from . import data, dialogue, encounters, items, missions, npc_lib
from .board import Board, grid_distance
from .conditions import Demoralized, Surprised
from .ground import GroundObject
from .scenario import Scenario

NODE = "dragon_lair"
SEARCH_HOURS = 3
SEARCH_DC = 12
DRAGON_SLUG = "dragon"
EGG = items.DRAGON_EGG_ITEM
SHRINE_EGG_PRICE = 1200        # what a school's keeper pays for an egg (the Market pays its usual half of $400)

COLS, ROWS = 44, 22
ENTRANCE = ((0, 10), (0, 11))
MOUTH = (1, 8, 4, 13)          # the way in, where the squad deploys and leaves
ROOMS = (                      # (x0, y0, x1, y1), inclusive; every way the dragon fits through is 3 wide,
    (5, 10, 8, 11),            # the tunnel in -- kobold-sized: the dragon cannot follow
    (9, 4, 18, 17),            # the kobolds' warren
    (19, 5, 21, 7),            # warren -> hoard
    (22, 2, 30, 9),            # the hoard
    (19, 14, 21, 16),          # warren -> clutch
    (22, 12, 29, 19),          # the clutch
    (31, 4, 32, 6),            # hoard -> hall
    (30, 14, 32, 16),          # clutch -> hall
    (33, 3, 42, 18),           # the dragon's hall
)
PILLARS = ((12, 8), (12, 13), (15, 8), (15, 13))
DRAGON_CELL = (37, 9)
EGG_CELLS = ((24, 14), (27, 14), (24, 17), (27, 17))
HOARD_PILES = ((23, 3), (26, 3), (29, 3), (24, 6), (27, 6), (23, 8), (29, 8), (26, 8))
HEX_SCROLL = "Scroll of Hex"
HEX_CELL = (29, 3)
PILE_COPPER = (15, 40)
PILE_GEM_ODDS = 0.25
TORCHES = ((2, 9), (2, 12))
PATROLS = (                    # (start cells, round)
    (((10, 5), (11, 5), (10, 6)), ((10, 5), (17, 5), (17, 16), (10, 16))),
    (((17, 10), (17, 11), (16, 10)), ((17, 10), (20, 6), (26, 5), (20, 6), (17, 10), (20, 15), (25, 15), (20, 15))),
)
PATROL_SIGHT = 6

# the dragon's sleep: noise it takes to stir and to wake, and what each sound is worth
STIR_AT = 6
WAKE_AT = 14
STIR_SIGHT = 5                 # stirring, it wakes on a foe it sees this close
HEAR_RANGE = 14                # footsteps and armour count only this close to it
RUN = 2                        # a walk past half the walker's speed
CLANK = 1                      # heavy armour on the move
MISSTEP = 1                    # a sneak that fails
BLOW = 3                       # a turn in which anyone was hurt
HOARD = 2                      # a handful of the hoard
LIFT = 2                       # an egg lifted
ALARM = 8


def _cells(x0, y0, x1, y1):
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


def _scout(party):
    return max(party, key=lambda u: u.mod_wisdom) if party else None


def search(guild, group, rng=random):
    """The roll at the end of `SEARCH_HOURS` in the Mine's deep galleries (an `orders.search`
    order) looking for the lair. Only finds it while
    the Dragon's Clutch is out. -> (found, message)."""
    scout = _scout(group.members)
    who = scout.name if scout else "The squad"
    if missions.pending_clutch(guild) is None:
        return False, f"{who} walks the deep galleries for {SEARCH_HOURS} hours: rock, and the miners' echoes."
    nat = rng.randint(1, 20)
    wis = scout.mod_wisdom if scout else 0
    total = nat + wis
    if total >= SEARCH_DC:
        guild.reveal_node(NODE)
        return True, (f"{who} follows the warm air past where the miners stopped, to a cave that smells "
                      "of sulphur and old gold. The Dragon's Lair is found.")
    return False, (f"{who} searches for {SEARCH_HOURS} hours and finds no way down "
                   f"(d20({nat}) {wis:+}(WIS) = {total} vs DC {SEARCH_DC}).")


def kobold(level, rng=random):
    return encounters.build_enemy(encounters.clamp_level(level), rng, race_pool=data.KOBOLD_POOL)


def build_patrols(level, rng=random):
    """The kobold patrols at the squad's `level`, on their rounds; the first of each holds a torch."""
    out = []
    for pid, (starts, route) in enumerate(PATROLS):
        for i, cell in enumerate(starts):
            u = kobold(level, rng)
            u.map_cell = cell
            u.patrol_route = route
            u.patrol_id = pid
            u.awareness_radius = PATROL_SIGHT
            if i == 0:
                u.equipped_offhand = data.TORCH_ITEM
            elif u.equipped_offhand == data.TORCH_ITEM:
                u.equipped_offhand = None
            out.append(u)
    return out


def build_dragon():
    u = npc_lib.load_npc(DRAGON_SLUG)
    u.dormant = True
    u.awareness_radius = 0
    u.map_cell = DRAGON_CELL
    return u


def dragon_of(battle):
    return next((u for u in battle.foe_units
                 if getattr(getattr(u, "char", None), "npc_slug", None) == DRAGON_SLUG), None)


def carries_egg(unit):
    return EGG in getattr(unit, "inventory", ())


class LairScenario(Scenario):
    floor = "cave"
    ambient_light = False
    outdoor = False
    torch_count = 0
    breath_burns = True            # the dragon's breath leaves the cells it reaches on fire

    def __init__(self, level=1, rng=random):
        self._cols, self._rows = COLS, ROWS
        self.rng = rng
        self.enemies = build_patrols(level, rng) + [build_dragon()]
        self.noise = 0
        self.stage = "asleep"
        self.bluffs = 0
        self.parleyed = set()      # patrol ids talked or paid off
        self.alarm_due = set()     # patrol ids fought: they ring the alarm on their next turn
        self.alarm = False
        self._hp = None

    # -- the board ---------------------------------------------------- #
    def _make_board(self):
        floor = set().union(*(_cells(*r) for r in (MOUTH, *ROOMS))) | set(ENTRANCE)
        floor -= set(PILLARS)
        walls = _cells(0, 0, COLS - 1, ROWS - 1) - floor
        return Board(walls=walls, cols=COLS, rows=ROWS)

    def _deploy_cells(self, u):
        if u.team == "player":
            return sorted(_cells(*MOUTH))
        cell = getattr(u, "map_cell", None)
        return [cell] if cell else sorted(_cells(*ROOMS[1]))

    def build(self, battle):
        super().build(battle)
        battle.escape_cells = set(ENTRANCE)
        for p in TORCHES:
            battle.ground.append(GroundObject.torch(p))
        for p in EGG_CELLS:
            battle.ground.append(GroundObject.relic(p, EGG))
        for p in HOARD_PILES:
            pile = [f"{self.rng.randint(*PILE_COPPER)} copper"]
            if self.rng.random() < PILE_GEM_ODDS:
                pile.append(data.GEM_ITEM)
            if p == HEX_CELL:
                pile.append(HEX_SCROLL)
            battle.ground.append(GroundObject.chest(p, pile))
        for u in battle.foe_units:
            u.patrol_step = 0

    # -- the dragon's sleep ------------------------------------------- #
    def hear(self, battle, amount, what):
        """`amount` of noise reaches the dragon (`what` made it); its sleep moves on a stage when
        the noise crosses `STIR_AT` / `WAKE_AT`."""
        dragon = dragon_of(battle)
        if self.stage == "awake" or dragon is None or not dragon.alive or amount <= 0:
            return
        self.noise += amount
        battle.log(f"  ({what}: the noise in the lair is {self.noise}/{WAKE_AT})")
        if self.noise >= WAKE_AT:
            self.wake(battle, dragon)
        elif self.noise >= STIR_AT and self.stage == "asleep":
            self.stage = "stirring"
            dragon.awareness_radius = STIR_SIGHT
            battle.log(f"{dragon.name} stirs in its sleep, and one eye half opens...")
            battle.fx(dragon.pos, "stirs...", "faint")

    def wake(self, battle, dragon):
        self.stage = "awake"
        dragon.dormant = False
        dragon.alerted = True
        battle.aggressor = "enemy"         # the lair hunts the thieves now (`ai.target._search`)
        battle.log(f"*** {dragon.name} wakes! ***")
        battle.fx(dragon.pos, "AWAKE!", "crit")

    def _near_dragon(self, battle, unit):
        dragon = dragon_of(battle)
        return dragon is not None and battle.units_distance(unit, dragon) <= HEAR_RANGE

    def on_turn_start(self, battle, unit):
        self._hp = (unit, {u: u.hp for u in battle.units})
        if getattr(unit, "patrol_id", None) in self.alarm_due and unit.alive:
            self.raise_alarm(battle, f"{unit.name} lived to ring the alarm")

    def on_turn_end(self, battle, unit):
        start = self._hp
        if start is not None and start[0] is unit and any(u.hp < hp for u, hp in start[1].items()):
            self.hear(battle, BLOW, "steel rings in the dark")
        if unit.team != "player" or not unit.alive or self.stage == "awake":
            return
        steps = max(0, len(unit.path) - 1)
        if not steps or not self._near_dragon(battle, unit):
            return
        if steps > unit.speed // 2:
            self.hear(battle, RUN, f"{unit.name} runs")
        else:
            dragon = dragon_of(battle)
            nat = self.rng.randint(1, 20)
            if nat + unit.mod_dexterity < 10 + dragon.mod_wisdom:
                self.hear(battle, MISSTEP, f"{unit.name} misplaces a foot")
        if unit.armor is not None and unit.armor.speed_penalty:
            self.hear(battle, CLANK, f"{unit.name}'s armour clanks")

    def on_round(self, battle):
        if self.stage == "awake" and battle.fire:
            battle.spread_fire(1, self.rng)

    def on_pick_up(self, battle, unit, obj):
        if obj.is_chest:
            self.hear(battle, HOARD, f"{unit.name} scoops up the hoard")
        elif obj.is_relic and obj.item_name == EGG:
            self.hear(battle, LIFT, f"{unit.name} lifts an egg")

    # -- the patrols --------------------------------------------------- #
    def patrol(self, battle, pid):
        return [u for u in battle.foe_units if getattr(u, "patrol_id", None) == pid and u.alive]

    def raise_alarm(self, battle, why):
        self.alarm_due.clear()
        battle.aggressor = "enemy"
        if not self.alarm:
            self.alarm = True
            battle.log(f"*** {why}: the alarm rings through the lair! ***")
        for u in battle.foe_units:
            if getattr(u, "patrol_id", None) is not None:
                u.alerted = True
                u.patrol_route = None
        self.hear(battle, ALARM, "the alarm")

    def contact(self, battle, unit, seen):
        """A patrol member on its rounds sees the squad. -> "fight" (its side fights now), "wait"
        (a talk is on, the turn waits on it) or "pass" (it lets them be)."""
        pid = unit.patrol_id
        if any(getattr(u, "alerted", False) for u in self.patrol(battle, pid)):
            return "fight"
        if any(carries_egg(s) for s in seen):
            self.raise_alarm(battle, f"{unit.name} sees the master's egg")
            return "fight"
        if pid in self.parleyed:
            return "pass"
        enc = dialogue.Challenge(self.patrol(battle, pid), self.bluffs)
        members = [c.char for c in battle.player_units if c.alive and not c.ai_ally]
        handler = getattr(battle, "talk_handler", None)
        if handler is not None:
            handler(enc, members, lambda result: self.settle(battle, pid, enc, result))
            return "wait"
        result = dialogue.ai_play(enc, members, 0.5, self.rng)
        self.settle(battle, pid, enc, result)
        return "fight" if result.kind == "fight" else "pass"

    def settle(self, battle, pid, enc, result):
        """What the patrol's challenge ended in, on the board."""
        battle.log(result.text)
        self.bluffs += enc.bluffs_told
        patrol = self.patrol(battle, pid)
        if result.kind != "fight":
            self.parleyed.add(pid)
            return
        for u in patrol:
            u.alerted = True
            u.patrol_route = None
        opening = result.opening
        if opening is not None and opening.surprised == "player":
            self.raise_alarm(battle, "The bluff fails")
            for c in battle.player_units:
                if c.alive:
                    c.add_condition(Surprised())
        else:
            self.alarm_due.add(pid)
            battle.log("  Silence them before they can call out!")
        if opening is not None and opening.demoralized == "enemy":
            for u in patrol:
                u.add_condition(Demoralized())

    # -- the end -------------------------------------------------------- #
    def can_withdraw(self, battle):
        dragon = dragon_of(battle)
        if dragon is not None and not dragon.alive:
            return True
        standing = [u for u in battle.player_units if u.alive and not u.ai_ally]
        mouth = _cells(*MOUTH) | set(ENTRANCE)
        return (bool(standing) and any(carries_egg(u) for u in standing)
                and all(set(battle.cells_of(u)) <= mouth for u in standing))

    def relics_left(self, battle):
        """The eggs still on the ground once the dragon is dead: the guild's to take."""
        dragon = dragon_of(battle)
        if dragon is not None and dragon.alive:
            return []
        return [o.item_name for o in battle.ground if o.is_relic and o.item_name == EGG]

    def heist_goal(self, battle, unit):
        """`(cell, reach)` the squad's AI heads for (`ai.scripted._heist`): a free cell of the way out once
        anyone holds an egg, else beside the nearest egg still on the ground; None for neither."""
        standing = [u for u in battle.player_units if u.alive]
        if any(carries_egg(u) for u in standing):
            mouth = _cells(*MOUTH)
            if set(battle.cells_of(unit)) <= mouth:
                return None
            free = sorted(mouth - battle.occupied(exclude=unit))
            return (min(free, key=lambda c: grid_distance(unit.pos, c)), 0) if free else None
        eggs = [o.pos for o in battle.ground if o.is_relic and o.item_name == EGG]
        if not eggs:
            return None
        return min(eggs, key=lambda c: grid_distance(unit.pos, c)), 1


def eggs_taken(battle):
    """How many eggs the squad came out with: carried by its survivors, plus the ground's once the
    dragon is dead. None from a lost fight."""
    if not isinstance(battle.scenario, LairScenario) or battle.winner != "player":
        return 0
    carried = sum(u.inventory.count(EGG) for u in battle.player_units if u.survived)
    return carried + len(battle.scenario.relics_left(battle))

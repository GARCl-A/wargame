"""The Necromancer at the Front: the Faith Order's second errand (`missions.FAITH_NECROMANCER`).

Soldiers who fell at the Battlefield get back up days later. The cause is a necromancer
hiding in the middle of the war, invisible from the first round, raising the dead of both
armies (`actions.RaiseDeadAction`, `actions.InvisibilityAction`). Nobody sees him: the
player reads where the dead rise from (the log names the cell, the ground stirs there) and
finds him with a bump, an Investigate or a wound.

Three sides on one big field at night: the guild and Ledger Hold's soldiers (`player`), the
frontier warband (`enemy`, more than the soldiers) and the necromancer with his dead
(`undead`, hostile to both). A few dead from the days before lie in no man's land
(`fallen`, a side that never acts) so he has bodies from round one.

The necromancer's fall drops every undead with him and meets the errand; the player may then
withdraw (`Battle.withdraw`) or fight the warband on for its loot. The soldiers may all die:
the errand is the necromancer.
"""

import random

from . import battlefield, encounters, npc_lib
from .board import Board
from .conditions import Invisible
from .data import race_by_name
from .scenario import Scenario

SLUG = "necromancer"
UNDEAD = "undead"
FALLEN = "fallen"

COLS, ROWS = 48, 30
PARAPET_X = (6, COLS - 7)
SOLDIERS = 4
WARBAND = 8
ZOMBIES = 4
CORPSES = 6
MIDFIELD = 6                           # the undead start this many columns either side of the centre
WARBAND_ARMOR = "Studded Leather"      # the raiders come better armoured than Ledger Hold's line


def build_zombies(level, rng=random):
    """The dead he already woke: soldiers of both armies, Zombies now, at the warband's level, in
    the armour of the army each fell with."""
    out = []
    for i in range(ZOMBIES):
        z = encounters.build_enemy(encounters.clamp_level(level + battlefield.WARBAND_EDGE), rng,
                                   race_pool=[race_by_name("Zombie")])
        z.team = UNDEAD
        out.append(battlefield.dress(z, _army_armor(i)))
    return out


def _army_armor(i):
    return battlefield.SOLDIER_ARMOR if i % 2 else WARBAND_ARMOR


def build_corpses(level, rng=random):
    """The dead of the days before, half of each army, lying in no man's land."""
    out = []
    for i in range(CORPSES):
        gap = -battlefield.SOLDIER_GAP if i % 2 else battlefield.WARBAND_EDGE
        u = encounters.build_enemy(encounters.clamp_level(level + gap), rng)
        u.team = FALLEN
        out.append(battlefield.dress(u, _army_armor(i)))
    return out


def necromancer():
    u = npc_lib.load_npc(SLUG)
    u.team = UNDEAD
    return u


def is_necromancer(unit):
    return getattr(getattr(unit, "char", None), "npc_slug", None) == SLUG


def the_necromancer(battle):
    return next((u for u in battle.units if is_necromancer(u)), None)


class NecromancerScenario(Scenario):
    outdoor = False                    # night on the front, whatever the clock says
    ambient_light = False
    torch_count = 0
    strips_the_dead = True             # the pay is the field: every body's armour and kit

    def __init__(self, squad, rng=random):
        level = encounters.squad_level(squad)
        self.allies = battlefield.build_soldiers(level, rng)
        self.enemies = [battlefield.dress(u, WARBAND_ARMOR) for u in battlefield.build_warband(level, rng, WARBAND)]
        self.others = {UNDEAD: [necromancer(), *build_zombies(level, rng)],
                       FALLEN: build_corpses(level, rng)}
        self.caster_down = False       # the necromancer has fallen: the errand is met

    def _make_board(self):
        walls = battlefield.parapet(PARAPET_X[0], ROWS) | battlefield.parapet(PARAPET_X[1], ROWS)
        return Board(walls=walls, cols=COLS, rows=ROWS)

    def _spawn_cells(self, team):
        mid = COLS // 2
        xs = {"player": range(PARAPET_X[0]),
              "enemy": range(PARAPET_X[1] + 1, COLS),
              UNDEAD: range(mid - MIDFIELD, mid + MIDFIELD),
              FALLEN: range(PARAPET_X[0] + 2, PARAPET_X[1] - 1)}[team]
        return [(x, y) for x in xs for y in range(ROWS)]

    def build(self, battle):
        super().build(battle)
        battlefield.watch_fires(battle, PARAPET_X, ROWS)
        for u in battle.units:
            if u.team == FALLEN:
                u.hp, u.status = 0, "dead"
            elif is_necromancer(u):
                u.add_condition(Invisible())

    def win_check(self, battle):
        """The necromancer's fall drops his dead with him; the fight itself goes on."""
        caster = the_necromancer(battle)
        if not self.caster_down and caster is not None and not caster.alive:
            self.caster_down = True
            battle.log(f"{caster.name} falls -- and every dead thing he raised falls with him.")
            for u in battle.units:
                if u.team == UNDEAD and u.alive:
                    u.hp, u.status = 0, "dead"
            battle.log("The necromancer is down. The squad may withdraw, or fight on for the field.")

    def can_withdraw(self, battle):
        return self.caster_down


def errand_met(battle):
    """The necromancer fell in this fight (the errand is done, whatever came after)."""
    return isinstance(battle.scenario, NecromancerScenario) and battle.scenario.caster_down


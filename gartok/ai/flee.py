"""Running away, delaying and skittish beasts."""

from .. import actions, intel
from ..board import cells, grid_distance
from .common import _axes, _mindless
from .target import _target


def _try_escape_grapple(battle, unit):
    """Attempt to break free from a grapple when holding a ranged weapon, fleeing,
    unable to hit any foe, or heavily hurt."""
    if not actions.ESCAPE_GRAPPLE.available(battle, unit):
        return False
    foes_in_reach = [f for f in battle.units if f.alive and f.team != unit.team
                     and actions.ATTACK.can(battle, unit, f)]
    wants_dist = unit.ranged or unit.needs_ammo or bool(unit.weapon and unit.weapon.get("range", 0) > 1)
    if wants_dist or _should_flee(battle, unit) or not foes_in_reach:
        actions.ESCAPE_GRAPPLE.execute(battle, unit)
        return True
    if unit.hp <= unit.hp_max * 0.4:
        actions.ESCAPE_GRAPPLE.execute(battle, unit)
        return True
    return False


FLEE_HP = 0.1               # share of its HP at which a unit thinks of running (a person runs near 0)


FLEE_HP_CHAOTIC = 0.5


FLEE_OUTNUMBERED = 1        # foes in sight past the allies standing before it runs (chaotic: 0)


def _should_flee(battle, unit):
    """Whether the unit breaks and runs this turn. Never from a non-lethal bout
    (the arena -- nobody dies). Chaotic units break sooner and while less outnumbered;
    lawful units stay while any ally is still standing."""
    if not battle.lethal or _mindless(unit):
        return False
    order = _axes(unit)[0]
    allies = [u for u in battle.units
              if u.alive and u.team == unit.team and u is not unit]
    foes = intel.visible_foes(battle, unit)
    if not foes:
        return False
    if order > 0 and allies:                 # lawful: hold the line
        return False
    hurt = unit.hp <= unit.hp_max * (FLEE_HP_CHAOTIC if order < 0 else FLEE_HP)
    outmatched = len(foes) > len(allies) + (0 if order < 0 else FLEE_OUTNUMBERED)
    return hurt and outmatched


def _try_vanish(battle, unit):
    """Invisibility as a way out of a lethal fight: cast when the unit would break and run, or
    when it is down to a third and a foe it sees can reach it this round. Returns True if it vanished."""
    vanish = actions.CastSpellAction("invisibility")
    if not battle.lethal or _mindless(unit) or not vanish.available(battle, unit):
        return False
    if _should_flee(battle, unit):
        vanish.execute(battle, unit)
        return True
    foes = intel.visible_foes(battle, unit)
    if unit.hp <= unit.hp_max * 0.34 and any(
            battle.units_distance(unit, f) <= (f.attack_range if f.ranged else f.speed + 1) for f in foes):
        vanish.execute(battle, unit)
        return True
    return False


def _slipping_away(battle, unit):
    """An invisible unit at half its HP or less makes for the edge instead of striking (a blow
    would show it)."""
    return (battle.lethal and unit.has_condition("invisible") and not _mindless(unit)
            and unit.hp <= unit.hp_max * 0.5)


def _should_delay(battle, unit):
    """A melee unit that cannot reach anyone this turn waits for an ally that is
    already in the fight, so it arrives after the line has formed. Never a flag
    runner (it has somewhere to be)."""
    if (unit.ranged or getattr(unit, "ctf_runner", False) or not actions.DELAY.available(battle, unit)
            or "raise_dead" in getattr(unit, "spells_known", ())):
        return False
    foes = intel.visible_foes(battle, unit)
    if not foes or any(battle.units_distance(unit, f) <= unit.speed + 1 for f in foes):
        return False
    after = battle.order[battle.turn_idx + 1:]
    return any(u.alive and u.team == unit.team
               and any(battle.units_distance(u, f) <= 1 for f in foes) for u in after)


SKITTISH_SLUGS = frozenset({"aurochs"})


SKITTISH_ALARM = 12       # squares: a beast this near anyone runs


SKITTISH_STAMINA = 3      # turns of running before it turns and charges


SKITTISH_CHARGE_ROUNDS = 2    # rounds it then stands and fights


def _is_skittish(unit):
    return getattr(getattr(unit, "char", None), "npc_slug", None) in SKITTISH_SLUGS


def _skitter(battle, unit):
    """A hunted beast's turn: "idle" (nobody near enough to spook it), "moved"
    (ran for the open ground farthest from the party), or "fight" -- cornered, or
    winded after `SKITTISH_STAMINA` turns of running, when it lowers its head and
    charges. The cells it likes are far from every foe and out in the open, so a
    straight chase just herds it round the groves; it is pinned in a canyon or
    pincered."""
    foes = [e for e in battle.units if e.alive and e.team != unit.team]
    if not foes:
        return "idle"
    here = min(grid_distance(unit.pos, f.pos) for f in foes)
    if getattr(unit, "charging_until", 0) >= battle.round_no:
        return "fight"
    if here > SKITTISH_ALARM:
        unit.fled_turns = 0
        return "idle"
    if getattr(unit, "flee_round", None) != battle.round_no:
        if getattr(unit, "fled_turns", 0) >= SKITTISH_STAMINA:
            unit.fled_turns = 0
            unit.charging_until = battle.round_no + SKITTISH_CHARGE_ROUNDS - 1
            battle.log(f"{unit.name} is winded -- it lowers its head and charges!")
            return "fight"
        unit.fled_turns = getattr(unit, "fled_turns", 0) + 1
        unit.flee_round = battle.round_no
    board = battle.board

    def score(cell):
        near = min(grid_distance(cell, f.pos) for f in foes)
        open_ground = sum(1 for n in board.neighbors(cell) if n not in board.walls)
        edge = min(cell[0], cell[1], board.cols - 1 - cell[0], board.rows - 1 - cell[1])
        return near * 2 + open_ground + min(edge, 4)

    best = max(battle.reachable(unit), key=score, default=None)
    if best is None or best == unit.pos or min(
            grid_distance(best, f.pos) for f in foes) <= here:
        battle.log(f"{unit.name} is cornered and turns to fight!")
        return "fight"
    actions.MOVE.execute(battle, unit, best)
    unit.walking = False
    return "moved"


def _retreat_from(battle, unit, foe):
    """Back away from `foe` into a safe cell that increases distance from it,
    or Defend if no retreat cell is available. Returns True if acted."""
    if unit.ap < 1 or not unit.alive:
        return False
    reach = battle.reachable(unit)
    cur_dist = battle.units_distance(unit, foe)
    safe = [
        p for p in reach
        if all(c not in battle.fire for c in cells(p, unit.footprint))
        and grid_distance(p, foe.pos) > cur_dist
    ]
    if safe:
        dest = max(safe, key=lambda p: grid_distance(p, foe.pos))
        actions.MOVE.execute(battle, unit, dest)
        unit.walking = False
        return True
    if actions.DEFEND.available(battle, unit):
        actions.DEFEND.execute(battle, unit)
        return True
    return False


def _leave_fire(battle, unit):
    """Standing in the flames: walk to the nearest cell that is not burning, toward the foe
    when there is one. Returns True if it moved."""
    if not battle.burning_under(unit) or unit.ap < 1:
        return False
    foe = _target(battle, unit)
    safe = [p for p in battle.reachable(unit)
            if not any(c in battle.fire for c in cells(p, unit.footprint))]
    if not safe:
        return False
    goal = foe.pos if foe is not None else unit.pos
    dest = min(safe, key=lambda p: (grid_distance(p, goal), grid_distance(p, unit.pos)))
    actions.MOVE.execute(battle, unit, dest)
    unit.walking = False
    return True

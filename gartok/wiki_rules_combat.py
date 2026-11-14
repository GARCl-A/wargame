"""The Rules chapter's fight sections: the numbers read off the modules that run them."""

from . import actions, conditions, data, i18n
from .actions import base, combat, movement
from .board import CLIMB_DC_ROPE, CLIMB_DC_STONE


def _lines(section, n, **fmt):
    return [i18n.t(f"wiki_rules.{section}.{i}", **fmt) for i in range(1, n + 1)]


def built():
    dice, faces = data.FIRE_DICE
    return {
        "attack": _lines("attack", 5, obscured=base.OBSCURED_PENALTY, horn_cost=actions.SIGNAL_HORN.cost,
                         horn_radius=actions.SIGNAL_HORN.RADIUS, horn_bonus=actions.SIGNAL_HORN.BONUS),
        "ammo": _lines("ammo", 2, reload=actions.RELOAD.cost, quiver=data.QUIVER_AMMO),
        "push": _lines("push", 2, cost=actions.PUSH.cost, dc=combat.PUSH_DC_BASE),
        "hidden": _lines("hidden", 2, cost=actions.INVESTIGATE.cost, radius=actions.INVESTIGATE.RADIUS, base=actions.INVESTIGATE.BASE_DC),
        "sides": _lines("sides", 1),
        "dying": _lines("dying", 5, turns=data.DYING_TURNS, save=data.DEATH_SAVE_MIN, aid=data.FIRST_AID_DC,
                        charges=data.FIRST_AID_CHARGES, repair=data.AUTOMATON_REPAIR_DC),
        "nonlethal": _lines("nonlethal", 2, pen=base.NONLETHAL_PENALTY),
        "demoralize": _lines("demoralize", 2, cost=actions.DEMORALIZE.cost, range=data.DEMORALIZE_RANGE,
                             max=conditions.DEMORALIZE_MAX_STACKS),
        "terrain": _lines("terrain", 5, breath=data.BREATH_BASE, stone=CLIMB_DC_STONE, rope=CLIMB_DC_ROPE,
                          swim=movement.SWIM_DIVISOR, dice=dice, faces=faces),
    }

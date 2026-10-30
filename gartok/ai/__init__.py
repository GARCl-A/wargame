"""Enemy squad AI.

Simple heuristic over `actions.py`: if unarmed, recover the dropped weapon; if
holding an empty crossbow, reload it; otherwise spend the points attacking the
weakest target in range (or demoralize it if out of reach); otherwise advance.
Sees through each unit's own eyes.

**Tendency colours the edges** (§8 / "Fleeing" in RULES.md), on
the morality axis mostly:
- **Evil** finishes downed enemies -- a coup de grace on an adjacent body, so the
  player cannot stabilize it. Only in a lethal fight (the arena knocks out anyway).
- **Good** stabilizes an adjacent downed ally before doing anything else, and when
  it does run it drags the wounded out with it (that part is in `Flee.execute`).
- **Chaotic** breaks and runs sooner; **Lawful** holds the line while any ally
  still stands.

The package is cut by concern (README *Structure*): `turn` runs one turn over the others.
"""

# ruff: noqa: F401
import sys

from .. import actions
from ..board import grid_distance
from .attack import _best_cone, _breath_spot, _finish_off, _hex_or_roots, _pick_attack, _sleep_immune, _try_breath, _try_capture, _try_shove, _try_throw
from .common import _wants_alive
from .flee import FLEE_HP, SKITTISH_STAMINA, _leave_fire, _should_flee, _skitter, _try_vanish
from .movement import _recover_torch, _recover_weapon, _step_over_terrain, _step_toward, _try_assess, trap_cell
from .scripted import _ctf_goal, _heist, _patrol
from .support import _ally_to_help, _try_drink_potion, _try_healing_touch
from .target import GROUP_GAP, SEARCH_STEP, _approach_reach, _flank_cell, _focus_key, _search, _search_goal, _target
from .turn import take_turn
from .reckon import _two_points, _unflank_worth, _weapon_action_worth


def module_of(name):
    """The submodule that defines the threshold `name`: set it there, a copy imported elsewhere would not follow."""
    for mod in (m for k, m in sys.modules.items() if k.startswith(__name__ + ".")):
        if name in vars(mod):
            return mod
    raise AttributeError(name)

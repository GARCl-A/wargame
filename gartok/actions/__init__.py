"""Combat actions.

Model: 2 action points per turn. Each action is a class that knows its cost, what
kind of target it needs, whether it can be done now and how it resolves. The UI
builds the buttons from `PANEL_ACTIONS`; the AI scores from the same objects.

Adding an action (a new world thing that becomes a mechanic) = one class in the
module that fits (base / combat / movement / support / spells) and one entry in the
registry below. Nothing else needs to know it exists.
"""

from .base import (  # noqa: F401
    Action,
    _attackable_target,
    _cell_free,
    _drop_cell,
    _facing,
    _flanked,
    _hostile_target,
    _pack_flank,
    _phalanxed,
    _pickable,
    _resolve_hit,
    _shared_language,
    _shovable_target,
    _sign,
)
from .combat import (  # noqa: F401
    Attack,
    AttackTongue,
    Defend,
    Demoralize,
    Flee,
    Push,
    Reload,
    Throw,
    _strike,
)
from .movement import (  # noqa: F401
    Climb,
    DropIn,
    Jump,
    Move,
    Swim,
    _VerticalStep,
)
from .spells import (  # noqa: F401
    CastSpellAction,
    FloatingDiskAction,
    LightGlobeAction,
    MagicMissileAction,
    ShareMagicAction,
    SleepAction,
    SpellAction,
    _PlacedSpellAction,
)
from .support import (
    Disarm,
    Dismount,
    Delay,
    DrinkPotion,
    EatCorpse,
    EndTurn,
    FirstAid,
    Investigate,
    Mount,
    PickUp,
    SignalHorn,
    SpinWeb,
    Stabilize,
    WakeUp,
)

# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #

MOVE = Move()
ATTACK = Attack()
ATTACK_TONGUE = AttackTongue()
RELOAD = Reload()
DEFEND = Defend()
THROW = Throw()
PICK_UP = PickUp()
DEMORALIZE = Demoralize()
STABILIZE = Stabilize()
FIRST_AID = FirstAid()
PUSH = Push()
CLIMB = Climb()
DROP = DropIn()
JUMP = Jump()
SWIM = Swim()
FLEE = Flee()
EAT_CORPSE = EatCorpse()
SPIN_WEB = SpinWeb()
MOUNT = Mount()
DISMOUNT = Dismount()
WAKE_UP = WakeUp()
DELAY = Delay()
END = EndTurn()
SHARE_MAGIC = ShareMagicAction()
INVESTIGATE = Investigate()
DISARM = Disarm()
DRINK_POTION = DrinkPotion()
SIGNAL_HORN = SignalHorn()

# Panel actions split into clear combat and utility categories for the UI.
COMBAT_ACTIONS = [
    ATTACK,
    THROW,
    DEMORALIZE,
    PUSH,
    DEFEND,
    RELOAD,
    ATTACK_TONGUE,
    FLEE,
    DELAY,
    END,
]

UTILITY_ACTIONS = [
    FIRST_AID,
    STABILIZE,
    DRINK_POTION,
    SIGNAL_HORN,
    PICK_UP,
    DISARM,
    INVESTIGATE,
    JUMP,
    CLIMB,
    DROP,
    SWIM,
    SHARE_MAGIC,
    EAT_CORPSE,
    SPIN_WEB,
    MOUNT,
    DISMOUNT,
    WAKE_UP,
]

PANEL_ACTIONS = COMBAT_ACTIONS + UTILITY_ACTIONS

"""Morale: the number that decides when a fighter breaks and runs.

Every combatant of a lethal fight carries `morale`, from a start value that is also its ceiling
(`morale_max`). What happens in the fight moves it; at 0 or less the unit is `Routed` and `ai/` plays it,
a guild member included, until a rise above 0 hands the fight back. RULES.md *Morale and fleeing* is the prose and the
wiki's Rules tab reads the constants below, so a number tuned here changes the page.

There is no event bus: falls come from blows, fire, traps, spells and bleeding alike. `settle(battle)`
is the single hook; it compares every combatant with the state it saw last (`morale_watch`) and applies
the difference, so calling it again changes nothing. `Battle` calls it after every action and at every
turn change.
"""

from . import data, vision
from .board import cells
from .conditions import Routed
from .i18n import Msg

BASE = 7                     # + WIS mod + CHA mod + racial level + alignment + talents
LAWFUL, CHAOTIC = 1, -1
START_MIN = 1                # nobody starts the fight already running
PER_RACIAL_LEVEL = 1
ALLY_DOWN = -1              # an ally it sees goes down, each time
ALLY_DEAD = -1              # an ally it sees dies, once (on top of the fall)
HP_MARKS_ONCE = (0.50, 0.25)    # the share of its HP, first time it gets there
HP_MARK_EVERY = 0.10            # the share of its HP, every time it gets there from above
HP_MARK = -1
DEMORALIZED = -1            # each Demoralize that lands
FOE_DOWN = 1                # every fighter of the other sides when one of them is downed, by anyone

DOWNED = ("dying", "stable", "broken")


class _Watch:
    """What `settle` saw of one combatant last time."""
    __slots__ = ("demoralized", "low", "once", "status")

    def __init__(self, status, once, low, demoralized):
        self.status, self.once, self.low, self.demoralized = status, once, low, demoralized


def mindless(c):
    """The dead, the raised and the machines have no nerve to lose."""
    return bool(getattr(c, "raised", False) or c.race.get("kind") == "undead" or getattr(c.ability, "breaks_when_downed", False))


def has_morale(battle, c):
    """Only a lethal fight tests nerve (the arena never kills), and only a mind that can fear."""
    return battle.lethal and not mindless(c)


def start_value(char):
    """The morale a character takes into a fight: 7 + WIS mod + CHA mod + racial level, +1 lawful or -1
    chaotic, plus the `morale` channel of its talents, never under `START_MIN`."""
    order = data.alignment_axes(char.alignment)[0]
    total = (BASE + char.mod_wisdom + char.mod_charisma + char.racial_level * PER_RACIAL_LEVEL
             + (LAWFUL if order > 0 else CHAOTIC if order < 0 else 0) + int(char.talent_bonus("morale")))
    return max(START_MIN, total)


def start(c):
    c.morale_max = c.morale = start_value(c.char)
    watch(c)


def _share(c):
    return max(c.hp, 0) / c.hp_max


def watch(c):
    """Take `c`'s present state as the baseline `settle` measures against."""
    share = _share(c)
    c.morale_watch = _Watch(c.status, {m for m in HP_MARKS_ONCE if share <= m}, share <= HP_MARK_EVERY,
                            c.shaken)


def lift(c, amount):
    """Give `c` back up to `amount` morale, never over its ceiling; returns what it regained."""
    gained = min(amount, c.morale_max - c.morale)
    c.morale += max(gained, 0)
    return max(gained, 0)


def wounds_taken(c):
    """How many of the wound marks (`HP_MARKS_ONCE`, `HP_MARK_EVERY`) `c`'s visible hit points have crossed."""
    share = _share(c)
    return sum(share <= m for m in HP_MARKS_ONCE) + (share <= HP_MARK_EVERY)


def _sees(battle, witness, body):
    """`witness` has `body` in sight; a dead one counts (`can_see_unit` refuses the dead)."""
    if any(vision.can_see(battle, witness, cell) for cell in cells(body.pos, body.footprint)):
        return True
    return battle.units_distance(witness, body) <= 1 and battle.los_between(witness, body)


def settle(battle):
    """Fold into every morale what happened since the last call. Idempotent."""
    if not battle.lethal:
        return
    units = battle.units
    losses, gains = {}, {}
    for u in units:
        w = u.morale_watch
        was, now = w.status, u.status
        w.status = now
        fell = was == "up" and (now in DOWNED or now == "dead")
        died = now == "dead" and (was == "up" or was in DOWNED)
        if fell:
            for g in units:
                if g.team != u.team and g.status == "up" and has_morale(battle, g):
                    gains[g] = gains.get(g, 0) + FOE_DOWN
        if (fell or died) and not mindless(u):
            for a in units:
                if (a is not u and a.team == u.team and a.status == "up" and has_morale(battle, a)
                        and _sees(battle, a, u)):
                    if fell:
                        _note(losses, a, ALLY_DOWN, "ally_down")
                    if died:
                        _note(losses, a, ALLY_DEAD, "ally_dead")
    for u in units:
        if u.status in ("dead", "fled") or not has_morale(battle, u):
            continue
        w = u.morale_watch
        share = _share(u)
        for mark in HP_MARKS_ONCE:
            if share <= mark and mark not in w.once:
                w.once.add(mark)
                _note(losses, u, HP_MARK, "wounded")
        if share <= HP_MARK_EVERY:
            if not w.low:
                w.low = True
                _note(losses, u, HP_MARK, "wounded")
        else:
            w.low = False
        if u.shaken > w.demoralized:
            _note(losses, u, DEMORALIZED * (u.shaken - w.demoralized), "shaken")
            w.demoralized = u.shaken
    for u, why in losses.items():
        for reason, amount in why.items():
            u.morale += amount
            _tell_loss(battle, u, reason, amount)
    for u, amount in gains.items():
        u.morale = min(u.morale_max, u.morale + amount)
    for u in units:
        _sync_rout(battle, u)


def _note(table, unit, amount, reason):
    why = table.setdefault(unit, {})
    why[reason] = why.get(reason, 0) + amount


def _tell_loss(battle, u, reason, amount):
    """The player's own side reads why its morale fell; a foe's stays hidden."""
    if u.team == "player":
        battle.log("log.morale.falls", unit=u.name, amount=-amount, why=Msg(f"log.morale.why.{reason}"),
                   morale=u.morale, ceiling=u.morale_max)


def _sync_rout(battle, u):
    if u.status != "up" or not has_morale(battle, u):
        return
    if u.morale <= 0 and not u.has_condition("routed"):
        u.add_condition(Routed())
        battle.log("log.morale.routs", unit=u.name)
    elif u.morale > 0 and u.has_condition("routed"):
        u.conditions = [c for c in u.conditions if c.id != "routed"]
        battle.log("log.morale.rallies", unit=u.name)


def baseline(battle):
    """Take every combatant's present state as the one `settle` measures from (the fight just began)."""
    for u in battle.units:
        watch(u)


PRESENCE_DC = 10


def dread(battle, unit):
    """Infernal Presence: a foe that begins its turn next to a bearer saves with WIS against
    10 + the bearer's CHA modifier, or loses 1 morale."""
    if unit.status != "up" or not has_morale(battle, unit):
        return
    for bearer in battle.units:
        if (bearer.team == unit.team or not bearer.alive or not hasattr(bearer, "char")
                or not bearer.char.has_talent("infernal_presence") or battle.units_distance(bearer, unit) > 1):
            continue
        roll = data.d20()
        total, dc = roll + unit.mod_wisdom, PRESENCE_DC + bearer.mod_charisma
        args = {"unit": unit.name, "bearer": bearer.name, "roll": roll, "mod": unit.mod_wisdom, "total": total, "dc": dc}
        if total >= dc:
            battle.log("log.infernal_presence_resisted", **args)
            continue
        unit.morale -= 1
        battle.log("log.infernal_presence", **args, morale=unit.morale, ceiling=unit.morale_max)
        _sync_rout(battle, unit)

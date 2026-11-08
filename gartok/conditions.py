"""Conditions: a unit's temporary states (Defending, Demoralized, ...).

Each condition contributes typed modifiers (see `data.resolve_bonus`) and knows
when it expires. `unit.conditions` holds the active ones; `unit.has_condition(id)`
checks.

Adding a world state (poison, grappled, prone, blind, on fire, ...) = a class
here + whoever applies it calls `unit.add_condition(...)`.
"""


HEX_POINTS = 1               # what one Hex takes off every attribute score
HEX_TURNS = 3                # victim turns a Hex stack lasts
BLEEDING_CLAWS_TURNS = 2     # the Catfolk's Claws: each wound bleeds this many turns


class Condition:
    id = ""

    # modifiers the condition injects (format (value, type, label))
    def attack_mods(self):
        return []

    def ac_mods(self):
        return []

    def mental_defense_mods(self):
        return []

    # lifecycle: returning True removes the condition
    def on_turn_start(self, unit, log):
        return False

    def on_turn_end(self, unit, log):
        return False


class Defending(Condition):
    id = "defending"

    def ac_mods(self):
        return [(1, "circumstance", "Defend")]

    def on_turn_start(self, unit, log):
        return True  # the Defend bonus lasts until the start of the next turn


class Demoralized(Condition):
    id = "demoralized"

    def attack_mods(self):
        return [(-1, "status", "Demoralized")]

    def ac_mods(self):
        return [(-1, "status", "Demoralized")]

    def mental_defense_mods(self):
        return [(-1, "status", "Demoralized")]

    def on_turn_end(self, unit, log):
        log("log.cond.demoralized_ends", unit=unit.name)
        return True


class Routed(Condition):
    """Morale spent: the unit runs for the exit and `ai/` plays it, a guild member included. It has no
    timer: `morale.settle` puts it on when morale falls to 0 and lifts it when morale is above 0 again."""
    id = "routed"


class Surprised(Condition):
    """Caught off guard before the fight (`dialogue.py`): the unit loses its first turn
    (`Battle._advance_turn` skips it)."""
    id = "surprised"

    def on_turn_end(self, unit, log):
        return True


class Entangled(Condition):
    """Stuck in a web: -2 AC and no walking, through the victim's next whole turn
    (battle.reachable reads it). Caught mid-turn, it survives that turn's end."""
    id = "entangled"

    def __init__(self):
        self.held = False

    def ac_mods(self):
        return [(-2, "status", "Entangled")]

    def on_turn_start(self, unit, log):
        self.held = True
        return False

    def on_turn_end(self, unit, log):
        if self.held:
            log("log.cond.entangled_ends", unit=unit.name)
        return self.held


class Grappled(Condition):
    """Held fast: speed is 0 (cannot walk or flee) and -2 AC.
    Ends if the grappler falls, dies, moves away, or if the victim escapes."""
    id = "grappled"

    def __init__(self, grappler=None):
        self.grappler = grappler

    def ac_mods(self):
        return [(-2, "status", "Grappled")]

    def modify_speed(self, speed):
        return 0

    def on_turn_start(self, unit, log):
        if self.grappler is not None:
            if not getattr(self.grappler, "alive", True):
                log("log.cond.grappled_ends", unit=unit.name)
                return True
        return False


class Prone(Condition):
    """Down on the ground (Takedown): cannot move until it stands up (Stand Up, 1 AP) and
    attacks at -2. Lasts until it stands."""
    id = "prone"

    def attack_mods(self):
        return [(-2, "status", "Prone")]


class Sleeping(Condition):
    id = "sleeping"

    def __init__(self, duration=None):
        self.duration = duration

    def ac_mods(self):
        return [(-2, "status", "Sleeping")]  # -2 AC while sleeping

    def on_turn_end(self, unit, log):
        if self.duration is not None:
            self.duration -= 1
            if self.duration <= 0:
                log("log.cond.wakes", unit=unit.name)
                return True
        return False


class Bleeding(Condition):
    """Open wounds: `damage` is lost at the end of the victim's own turn, for `duration` more
    turns. A new wound stacks onto it: the damages add up, the duration becomes the longer.
    Armor does not stop it; a unit that is down stops bleeding."""
    id = "bleeding"

    def __init__(self, damage, duration):
        self.damage = damage
        self.duration = duration

    @property
    def label(self):
        return f"bleeding {self.damage} for {self.duration}"

    def stack(self, other):
        self.damage += other.damage
        self.duration = max(self.duration, other.duration)

    def on_turn_end(self, unit, log):
        if unit.hp <= 0:
            return True
        log("log.cond.bleeds", unit=unit.name)
        unit.take_damage(self.damage, log, ignore_dr=True)
        self.duration -= 1
        if unit.hp <= 0:
            return True
        if self.duration > 0:
            return False
        log("log.cond.bleeding_ends", unit=unit.name)
        return True


class Maimed(Condition):
    """Maiming Strike: movement speed halved through the victim's next turn."""
    id = "maimed"

    def __init__(self):
        self.held = False

    def modify_speed(self, speed):
        return max(1, speed // 2)

    def on_turn_start(self, unit, log):
        self.held = True
        return False

    def on_turn_end(self, unit, log):
        if self.held:
            log("log.cond.maimed_ends", unit=unit.name)
        return self.held


class ShieldHooked(Condition):
    """Hook Shield: victim's shield AC bonus nullified through their next turn."""
    id = "shield_hooked"

    def __init__(self):
        self.held = False

    def on_turn_start(self, unit, log):
        self.held = True
        return False

    def on_turn_end(self, unit, log):
        if self.held:
            log("log.cond.shield_ends", unit=unit.name)
        return self.held


class Invisible(Condition):
    """Unseen by every other side (`Combatant.hidden_from`) until it deals damage. A side that
    finds it (a bump, an Investigate, a wound) sees it until the start of its next turn, when it
    slips away again."""
    id = "invisible"

    def __init__(self):
        self.seen_by = set()
        self.wounded = False             # a wound shows where it stands, to every side

    def on_turn_start(self, unit, log):
        self.seen_by.clear()
        self.wounded = False
        return False


class Rooted(Condition):
    """Grasping Roots: the victim walks 1 cell at most, through its next whole turn."""
    id = "rooted"

    def __init__(self):
        self.held = False

    def modify_speed(self, speed):
        return 1

    def on_turn_start(self, unit, log):
        self.held = True
        return False

    def on_turn_end(self, unit, log):
        if self.held:
            log("log.cond.rooted_ends", unit=unit.name)
        return self.held


class Hexed(Condition):
    """Hex: each cast is a stack that takes `points` off every attribute score for `turns` of the
    victim's turns, counted from the first one that starts after the cast; stacks add up. `deltas`,
    `ac_delta` and `hp_lost` are what the stacks do to the modifiers, the AC and the max HP, worked
    out by `Combatant.hex_sync`; the max HP comes back when the hex ends."""
    id = "hexed"

    def __init__(self):
        self.stacks = []                  # [points, turns left, a victim's turn has started since]
        self.deltas = dict.fromkeys(("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"), 0)
        self.ac_delta = 0
        self.hp_lost = 0

    @property
    def points(self):
        return sum(s[0] for s in self.stacks)

    def add_stack(self, points, turns):
        self.stacks.append([points, turns, False])

    def ac_mods(self):
        return [(self.ac_delta, "hex", "Hex")] if self.ac_delta else []

    def mental_defense_mods(self):
        wis = self.deltas.get("wisdom", 0)
        return [(wis, "hex", "Hex")] if wis else []

    def on_turn_start(self, unit, log):
        for stack in self.stacks:
            stack[2] = True
        return False

    def on_turn_end(self, unit, log):
        before = len(self.stacks)
        for stack in self.stacks:
            if stack[2]:
                stack[1] -= 1
        self.stacks = [s for s in self.stacks if s[1] > 0]
        if not self.stacks:
            unit.hp_max += self.hp_lost
            self.hp_lost = 0
            log("log.cond.hexed_ends", unit=unit.name)
            return True
        if len(self.stacks) < before:
            unit.hex_sync(log)
            log("log.cond.hex_fades", unit=unit.name, left=self.points)
        return False


class PixieFlight(Condition):
    """Sprite's Pixie Dust: the unit flies (`Combatant.flies`) through the end of its next turn."""
    id = "pixie_flight"

    def __init__(self):
        self.held = False

    def on_turn_start(self, unit, log):
        self.held = True
        return False

    def on_turn_end(self, unit, log):
        if not self.held:
            return False
        log("log.cond.pixie_ends", unit=unit.name)
        return True

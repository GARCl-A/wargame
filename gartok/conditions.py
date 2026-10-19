"""Conditions: a unit's temporary states (Defending, Demoralized, ...).

Each condition contributes typed modifiers (see `data.resolve_bonus`) and knows
when it expires. `unit.conditions` holds the active ones; `unit.has_condition(id)`
checks.

Adding a world state (poison, grappled, prone, blind, on fire, ...) = a class
here + whoever applies it calls `unit.add_condition(...)`.
"""


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
        log(f"{unit.name} recovers (no longer demoralized).")
        return True


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
            log(f"{unit.name} tears free of the web.")
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
                log(f"{unit.name} is no longer grappled (grappler is down).")
                return True
        return False


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
                log(f"{unit.name} stirs and wakes up.")
                return True
        return False


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
            log(f"{unit.name} recovers from the maiming blow.")
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
            log(f"{unit.name}'s shield is no longer tangled.")
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
            log(f"{unit.name} pulls free of the roots.")
        return self.held


class Hexed(Condition):
    """Hex: -1 on each of the six attribute scores through the victim's next whole turn.
    `deltas` is what that does to each modifier (-1 on an even score, 0 on an odd one),
    worked out by `Combatant.hex` when it lands; `hp_lost` is the max HP an even CON took,
    given back to the max (not the current HP) when it wears off."""
    id = "hexed"

    def __init__(self, deltas, ac_delta=0, hp_lost=0):
        self.deltas = dict(deltas)
        self.ac_delta = ac_delta
        self.hp_lost = hp_lost
        self.held = False

    def ac_mods(self):
        return [(self.ac_delta, "hex", "Hex")] if self.ac_delta else []

    def mental_defense_mods(self):
        wis = self.deltas.get("wisdom", 0)
        return [(wis, "hex", "Hex")] if wis else []

    def on_turn_start(self, unit, log):
        self.held = True
        return False

    def on_turn_end(self, unit, log):
        if not self.held:
            return False
        unit.hp_max += self.hp_lost
        log(f"{unit.name} shakes off the hex.")
        return True

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

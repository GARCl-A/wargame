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

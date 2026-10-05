"""Poison on a character: stacks, the world clock and the Antidote.

Mixed into `unit.Unit`. State lives on the unit (it outlives the battle and goes
into the save): `poisons` maps a poison id to `{"level", "hours", "dc"}` and
`antidote_cooldown` is the hours left before another Antidote may be used. The
attribute loss itself is applied in `Unit._apply_attributes` via `poison_penalty`.
"""

from . import data, items, poisons

PHYSICAL = ("strength", "dexterity", "constitution")


class PoisonMixin:
    # ------------------------------------------------------------------ #
    # reading                                                            #
    # ------------------------------------------------------------------ #
    def poison_penalty(self, attr):
        """Points of `attr` the active poisons are eating right now."""
        return sum(st["level"] * poisons.get(pid).per_stack
                   for pid, st in (getattr(self, "poisons", None) or {}).items()
                   if poisons.get(pid).attribute == attr)

    @property
    def poisoned(self):
        return bool(getattr(self, "poisons", None))

    @property
    def poison_label(self):
        """Short status text, e.g. `Giant Spider Venom 2 (18h)`."""
        return ", ".join(f"{poisons.get(pid).name} {st['level']} ({st['hours']}h)"
                         for pid, st in self.poisons.items())

    @property
    def zeroed_attribute(self):
        """The first physical attribute (Str / Dex / Con) down at zero or below,
        else None. A character with one falls to the ground, dying (see
        `Combatant.check_collapse`)."""
        return next((a for a in PHYSICAL if getattr(self, a) <= 0), None)

    # ------------------------------------------------------------------ #
    # getting poisoned                                                   #
    # ------------------------------------------------------------------ #
    def poison_save(self, dc):
        """Constitution save: d20 + CON mod vs `dc`. -> (passed, natural, total)."""
        nat = data.d20()
        total = nat + self.mod_constitution
        return total >= dc, nat, total

    def add_poison(self, poison_id, dc):
        """One more stack of `poison_id`; the 24h clock restarts and the DC kept
        is the highest seen."""
        poison = poisons.get(poison_id)
        st = self.poisons.setdefault(poison_id, {"level": 0, "hours": poison.hours, "dc": dc})
        st["level"] += 1
        st["hours"] = poison.hours
        st["dc"] = max(st["dc"], dc)
        self._apply_attributes()
        self._derive_combat()
        return st["level"]

    # ------------------------------------------------------------------ #
    # time and treatment                                                 #
    # ------------------------------------------------------------------ #
    def tick_poison(self, hours):
        """`hours` of world time pass: stacks wear off one step per `Poison.hours`
        and the Antidote cooldown runs down. Returns event strings."""
        events = []
        self.antidote_cooldown = max(0, self.antidote_cooldown - hours)
        changed = False
        for pid in list(self.poisons):
            st, poison = self.poisons[pid], poisons.get(pid)
            st["hours"] -= hours
            while st["hours"] <= 0 and st["level"] > 0:
                st["level"] -= 1
                changed = True
                if st["level"] > 0:
                    st["hours"] += poison.hours
                    events.append(f"{self.name}'s {poison.name} eases to {st['level']}.")
                else:
                    events.append(f"{self.name}'s {poison.name} wears off.")
            if st["level"] <= 0:
                del self.poisons[pid]
        if changed:
            self._apply_attributes()
            self._derive_combat()
        return events

    @property
    def can_take_antidote(self):
        return self.poisoned and self.antidote_cooldown <= 0

    def apply_antidote(self):
        """The Antidote's treatment (the item is consumed by the caller): another
        Constitution save against the worst poison's DC. Success sheds one stack
        now and restarts the clock for the next; failure only burns the dose. Either
        way no further Antidote for `ANTIDOTE_COOLDOWN_HOURS`. -> (passed, message)."""
        pid = max(self.poisons, key=lambda p: self.poisons[p]["level"])
        st, poison = self.poisons[pid], poisons.get(pid)
        ok, nat, total = self.poison_save(st["dc"])
        self.antidote_cooldown = poisons.ANTIDOTE_COOLDOWN_HOURS
        roll = f"CON d20({nat}) {self.mod_constitution:+} = {total} vs DC {st['dc']}"
        if not ok:
            return False, f"The Antidote does not take on {self.name} ({roll})."
        st["level"] -= 1
        st["hours"] = poison.hours
        if st["level"] <= 0:
            del self.poisons[pid]
            msg = f"The Antidote clears {poison.name} from {self.name} ({roll})."
        else:
            msg = (f"The Antidote eases {poison.name} on {self.name} to "
                   f"{st['level']} ({roll}).")
        self._apply_attributes()
        self._derive_combat()
        return True, msg

    def antidote_giver(self, others=()):
        """The first of `self` then `others` holding an Antidote, or None."""
        return next((u for u in (self, *others) if u.has_item(items.ANTIDOTE_ITEM)), None)


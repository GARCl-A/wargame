"""Racial abilities: the mechanical effect of each one, in a single place.

Only the NAME of each ability survived in the original generator; the effects
below were designed for the wargame, in d20 style. Each ability is an `Ability`
with:

- passive modifiers (numbers) added in the Unit's combat derivation;
- optional hooks (callables) invoked at fixed points of combat.

Adding or tuning an ability that reuses the existing passives/hooks = editing
only this file. Adding a brand-new *kind* of hook still needs a call site in the
core (unit.py / actions.py) -- there is no plugin bus, and the README says so.

`name` / `effect` are player-facing English; `id` and every field name are
English too. RULES.md is the design-prose doc and may lag the wording; the
generated REFERENCE.md is the authoritative catalog.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from . import data
from .data import d20


@dataclass(frozen=True)
class Ability:
    id: str
    name: str
    effect: str

    # --- passives (Unit combat derivation) ------------------------------- #
    hp_max: int = 0
    speed: int = 0
    ac_natural: int = 0
    damage_reduction: int = 0
    initiative: int = 0
    melee_damage: int = 0
    darkvision: int = 0               # range in squares; 0 = no darkvision
    extra_languages: int = 0
    demoralize_ignores_language: bool = False
    carry_size: Optional[str] = None  # size used for carry capacity only (overrides the real size)
    breaks_when_downed: bool = False  # 0 HP -> "broken" (no death clock), not "dying"
    flies: bool = False               # moves freely in 3D (ignores pits) and takes no fall damage
    climb_speed: bool = False         # moves up/down pit walls as normal movement (seam, unused)
    auto_climb_dc: int = 0            # climbs any surface of this DC or lower with no check

    # --- hooks (all optional) ------------------------------------------- #
    # mods are always (value, type, label) -> see data.resolve_bonus
    attack_mods: Optional[Callable] = None     # (unit, target, flanking) -> list[mod]
    feint: Optional[Callable] = None           # (unit, target) -> list[mod]   (once per battle)
    on_attack_miss: Optional[Callable] = None  # (battle, unit, target, bonus, ac, log)  (once per battle)
    on_downed: Optional[Callable] = None       # (unit, log) -> bool (True = survived)   (once per battle)
    on_turn_start: Optional[Callable] = None   # (unit, log)

    @property
    def desc(self):
        return f"{self.name}: {self.effect}"


# --------------------------------------------------------------------------- #
# Hooks                                                                        #
# --------------------------------------------------------------------------- #

def _pack_tactics_mods(unit, target, flanking):
    return [(2, "circumstance", "Pack Tactics")] if flanking else []


def _ancestral_blood_mods(unit, target, flanking):
    return [(2, "circumstance", "Ancestral Blood")] if target.size == "Large" else []


def _primal_blood(battle, unit, target, bonus, ac, log):
    nat = d20()
    total = nat + bonus
    hits = nat == 20 or total >= ac
    log(f"  Primal Blood: rerolls d20({nat}) = {total} -> "
        + ("hit." if hits else "misses again."))
    if hits:
        target.take_damage(unit.damage_roll(crit=nat == 20), log)


def _ferocity(unit, log):
    """Drop to 0 HP and start dying, but keep fighting until the end of this turn
    (`Unit.end_turn` resolves the fall). Only fires from >0 HP and not already
    dying -- guaranteed by the call site (once per battle, on the fatal hit)."""
    unit.hp = 0
    unit.death_clock = 0
    unit.ferocity_pending = True
    log(f"  Ferocity! {unit.name} hits 0 HP but stays on their feet until the end of their turn.")


# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #

_LIST = [
    Ability("darkvision", "Darkvision",
            f"sees {data.DARKVISION} squares in the dark as if it were lit.",
            darkvision=data.DARKVISION),
    Ability("inorganic_body", "Inorganic Body",
            "at 0 HP goes BROKEN instead of dying (no death save) until an ally "
            f"repairs it (Stabilize: INT vs DC {data.AUTOMATON_REPAIR_DC}).",
            breaks_when_downed=True),
    Ability("gallop", "Gallop",
            "+3 m (2 squares) of speed.", speed=2),
    Ability("sleep_immunity", "Sleep Immunity",
            "immune to stun (unused in the MVP); +1 AC [natural].", ac_natural=1),
    Ability("strong_stomach", "Strong Stomach",
            "+3 max HP.", hp_max=3),
    Ability("primal_blood", "Primal Blood",
            "once per battle, rerolls a missed attack.",
            on_attack_miss=_primal_blood),
    Ability("pack_tactics", "Pack Tactics",
            "+2 [circumstance] to attack if an ally is adjacent to the target.",
            attack_mods=_pack_tactics_mods),
    Ability("strong_body", "Strong Body",
            "for carry capacity (and only that), counts as a Large creature.",
            carry_size="Large"),
    Ability("amphibious", "Amphibious",
            "+1 square of speed.", speed=1),
    Ability("keen_hearing", "Keen Hearing",
            "+3 initiative.", initiative=3),
    Ability("climber", "Climber",
            "climbs any surface of DC 25 or lower with no check (still costs the action).",
            auto_climb_dc=25),
    Ability("extra_language", "Extra Language (Human)",
            "speaks a second random language: can Demoralize enemies that share "
            "either of the two.",
            extra_languages=1),
    Ability("mimic_sounds", "Mimic Sounds",
            "can Demoralize with no shared language (mimics the target's voice) "
            "-- offence only; being demoralized still needs a common tongue.",
            demoralize_ignores_language=True),
    Ability("ancestral_blood", "Ancestral Blood",
            "+2 [circumstance] to attack against Large targets.",
            attack_mods=_ancestral_blood_mods),
    Ability("autotroph", "Autotroph",
            "photosynthesises: never needs to eat, immune to the hunger rules."),
    Ability("ferocity", "Ferocity",
            "once per battle, when downed drops to 0 HP and dying, but only "
            "falls at the end of their turn (the death save runs normally from there).",
            on_downed=_ferocity),
    Ability("flight", "Flight",
            "flies: moves freely in three dimensions (up and down pits with no "
            "check, ignores terrain) and never takes falling damage.",
            flies=True),
]

ABILITIES = {a.id: a for a in _LIST}

_NONE = Ability("none", "No ability", "no effect.")


def get(ability_id):
    return ABILITIES.get(ability_id, _NONE)

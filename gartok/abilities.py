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

import functools
import math
from collections.abc import Callable
from dataclasses import dataclass, fields

from . import data, i18n


@dataclass(frozen=True)
class Ability:
    id: str

    # --- passives (Unit combat derivation) ------------------------------- #
    hp_max: int = 0
    speed: int = 0
    ac_natural: int = 0
    damage_reduction: int = 0
    initiative: int = 0
    melee_damage: int = 0
    melee_reach: int = 0              # extra squares of reach on every melee attack
    darkvision: int = 0               # range in squares; 0 = no darkvision
    extra_languages: int = 0
    demoralize_ignores_language: bool = False
    demoralize_vs_weaker: int = 0     # Demoralize bonus against a target with a lower STR modifier
    carry_size: str | None = None  # size used for carry capacity only (overrides the real size)
    carry_mult: float = 1.0
    breaks_when_downed: bool = False  # 0 HP -> "broken" (no death clock), not "dying"
    flies: bool = False               # moves freely in 3D (ignores pits) and takes no fall damage
    climb_speed: bool = False         # moves up/down pit walls as normal movement (seam, unused)
    auto_climb_dc: int = 0            # climbs any surface of this DC or lower with no check
    water_breathing: bool = False    # never runs out of breath while submerged
    sleep_immunity: bool = False      # the Sleep spell (magic.py) never affects this unit
    venom: str | None = None          # poison id (poisons.py): a bite that hurts forces a Constitution save
    finesse: bool = False             # every melee attack hits with the better of Strength and Dexterity
    fall_free: int = 0                # levels of a fall that cost nothing (the first level is always free)

    # --- hooks (all optional) ------------------------------------------- #
    # mods are always (value, type, label) -> see data.resolve_bonus
    attack_mods: Callable | None = None     # (unit, target, flanking) -> list[mod]
    feint: Callable | None = None           # (unit, target) -> list[mod]   (once per battle)
    on_attack_miss: Callable | None = None  # (battle, unit, target, bonus, ac, log)  (once per battle)
    on_downed: Callable | None = None       # (unit, log) -> bool (True = survived)   (once per battle)
    on_turn_start: Callable | None = None   # (unit, log)

    @property
    def name(self):
        if "+" in self.id:
            return ", ".join(ABILITIES[i].name for i in self.id.split("+"))
        return i18n.name("ability", self.id)

    @property
    def effect(self):
        if "+" in self.id:
            return " ".join(f"{ABILITIES[i].name}: {ABILITIES[i].effect}" for i in self.id.split("+"))
        return i18n.desc("ability", self.id, darkvision=data.DARKVISION, automaton_repair_dc=data.AUTOMATON_REPAIR_DC)

    @property
    def desc(self):
        return f"{self.name}: {self.effect}"


# --------------------------------------------------------------------------- #
# Hooks                                                                        #
# --------------------------------------------------------------------------- #

def _pack_tactics_mods(unit, target, flanking):
    return [(2, "circumstance", i18n.t("log.mod.pack_tactics"))] if flanking else []


def _wolf_pack_tactics_mods(unit, target, flanking):
    """A real pack, not just a flank: the bonus scales with how many allies
    are already on the target, same "circumstance" bonus type as the Goblin's
    (see `_pack_flank` in `actions.py`, which now hands back the adjacent-ally
    *count* instead of a bare bool)."""
    return [(2 * flanking, "circumstance", i18n.t("log.mod.pack_tactics"))] if flanking else []






def _ferocity(unit, log):
    """Drop to 0 HP and start dying, but keep fighting until the end of this turn
    (`Unit.end_turn` resolves the fall). Only fires from >0 HP and not already
    dying -- guaranteed by the call site (once per battle, on the fatal hit)."""
    unit.hp = 0
    unit.death_clock = 0
    unit.ferocity_pending = True
    log("log.ferocity", unit=unit.name)


# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #

_LIST = [
    Ability("browbeat", demoralize_vs_weaker=2),
    Ability("darkvision", darkvision=data.DARKVISION),
    Ability("inorganic_body", breaks_when_downed=True),
    Ability("gallop", speed=2),
    Ability("sleep_immunity", sleep_immunity=True),
    Ability("strong_stomach"),
    Ability("nature_magic"),
    Ability("pack_tactics", attack_mods=_pack_tactics_mods),
    Ability("strong_body", carry_size="Large"),
    Ability("beast_of_burden", carry_mult=2.0),
    Ability("amphibious", water_breathing=True),
    Ability("innocent_face"),
    Ability("climber", auto_climb_dc=25),
    Ability("extra_language", extra_languages=1),
    Ability("catfall", fall_free=3),
    Ability("mimic_sounds", demoralize_ignores_language=True),
    Ability("blood_magic"),
    Ability("autotroph"),
    Ability("ferocity", on_downed=_ferocity),
    Ability("flight", flies=True),
    Ability("spider_venom", venom="giant_spider_venom"),
    Ability("serpentine", finesse=True),
    Ability("wolf_pack_tactics", melee_damage=1, attack_mods=_wolf_pack_tactics_mods),
    Ability("reach", melee_reach=1),
]

ABILITIES = {a.id: a for a in _LIST}

_NONE = Ability("none")


_SUMMED = ("hp_max", "speed", "fall_free", "ac_natural", "damage_reduction", "initiative",
           "melee_damage", "melee_reach", "extra_languages", "demoralize_vs_weaker")
_WIDEST = ("darkvision", "auto_climb_dc")


def _chain(hooks, merge):
    hooks = [h for h in hooks if h]
    if not hooks:
        return None
    return lambda *args: merge(h(*args) for h in hooks)


@functools.cache
def _combined(ids):
    """Several abilities folded into one: numbers add (darkvision and climb DC
    take the widest), flags OR, and each hook runs every part's version."""
    parts = [ABILITIES[i] for i in ids]
    merged = {}
    for f in fields(Ability):
        vals = [getattr(p, f.name) for p in parts]
        if f.name in _SUMMED:
            merged[f.name] = sum(vals)
        elif f.name in _WIDEST:
            merged[f.name] = max(vals)
        elif f.name == "carry_mult":
            merged[f.name] = math.prod(vals)
        elif f.name in ("carry_size", "venom"):
            merged[f.name] = next((v for v in vals if v), None)
        elif isinstance(vals[0], bool):
            merged[f.name] = any(vals)
    merged["attack_mods"] = _chain([p.attack_mods for p in parts],
                                   lambda rs: [m for r in rs for m in r])
    merged["feint"] = _chain([p.feint for p in parts], lambda rs: [m for r in rs for m in r])
    merged["on_attack_miss"] = _chain([p.on_attack_miss for p in parts], list)
    merged["on_downed"] = _chain([p.on_downed for p in parts], any)
    merged["on_turn_start"] = _chain([p.on_turn_start for p in parts], list)
    return Ability("+".join(ids), **merged)


def get(spec):
    """An ability by id, or a tuple of ids merged into one (a race with several)."""
    if isinstance(spec, str):
        return ABILITIES.get(spec, _NONE)
    return _combined(tuple(spec))

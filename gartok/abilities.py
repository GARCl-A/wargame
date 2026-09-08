"""Racial abilities: the mechanical effect of each one, in a single place.

Only the NAME of each ability survived in the original generator; the effects
below were designed for the wargame, in d20 style. Each ability is an `Ability`
with:

- passive modifiers (numbers) added in the Unit's combat derivation;
- optional hooks (callables) invoked at fixed points of combat.

Adding or tuning an ability that reuses the existing passives/hooks = editing
only this file. Adding a brand-new *kind* of hook still needs a call site in the
core (unit.py / actions.py) -- there is no plugin bus, and the README says so.

`name` / `effect` stay in Portuguese: they are shown in the UI and mirror
GARTOK-regras.md.  `id` and every field name are English.
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
    breaks_when_downed: bool = False  # 0 PV -> "broken" (no death clock), not "dying"

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
    return [(2, "circunstancia", "Luta em bando")] if flanking else []


def _ancestral_blood_mods(unit, target, flanking):
    return [(2, "circunstancia", "Sangue ancestral")] if target.size == "Grande" else []


def _mimic_sounds_feint(unit, target):
    return [(4, "circunstancia", "Imitar sons")]


def _primal_blood(battle, unit, target, bonus, ac, log):
    nat = d20()
    total = nat + bonus
    hits = nat == 20 or total >= ac
    log(f"  Sangue primal: rerrola d20({nat}) = {total} -> "
        + ("acerto." if hits else "erra de novo."))
    if hits:
        target.take_damage(unit.damage_roll(crit=nat == 20), log)


def _ferocity(unit, log):
    """Drop to 0 PV and start dying, but keep fighting until the end of this turn
    (`Unit.end_turn` resolves the fall). Only fires from >0 PV and not already
    dying -- guaranteed by the call site (once per battle, on the fatal hit)."""
    unit.hp = 0
    unit.death_clock = 0
    unit.ferocity_pending = True
    log(f"  Ferocidade! {unit.name} chega a 0 PV mas segue de pe ate o fim do seu turno.")


def _autotroph(unit, log):
    if unit.hp < unit.hp_max:
        unit.hp += 1
        log(f"{unit.name} regenera 1 PV (autotrofo).")


# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #

_LIST = [
    Ability("darkvision", "Visao no escuro",
            f"enxerga {data.DARKVISION} casas no escuro como se fosse claro.",
            darkvision=data.DARKVISION),
    Ability("inorganic_body", "Corpo inorganico",
            "reduz todo dano recebido em 1; a 0 PV fica QUEBRADO (sem teste de "
            "morte) ate um aliado o consertar (Estabilizar: INT vs DC "
            f"{data.AUTOMATON_REPAIR_DC}).",
            damage_reduction=1, breaks_when_downed=True),
    Ability("gallop", "Galopar",
            "+3 m (2 casas) de deslocamento.", speed=2),
    Ability("sleep_immunity", "Imunidade a sono",
            "imune a atordoamento (nao usado no MVP); +1 CA [natural].", ac_natural=1),
    Ability("strong_stomach", "Estomago forte",
            "+3 PV maximos.", hp_max=3),
    Ability("primal_blood", "Sangue primal",
            "1x por batalha, rerrola um ataque errado.",
            on_attack_miss=_primal_blood),
    Ability("pack_tactics", "Luta em bando",
            "+2 [circunstancia] no ataque se um aliado esta adjacente ao alvo.",
            attack_mods=_pack_tactics_mods),
    Ability("strong_body", "Corpo forte",
            "para capacidade de carga (e so para isso), conta como criatura Grande.",
            carry_size="Grande"),
    Ability("amphibious", "Anfibio",
            "+1 casa de deslocamento.", speed=1),
    Ability("keen_hearing", "Audicao agucada",
            "+3 iniciativa.", initiative=3),
    Ability("climber", "Escalador",
            "+1 casa de deslocamento.", speed=1),
    Ability("extra_language", "Idioma adicional (Humano)",
            "fala um segundo idioma sorteado: pode Desmoralizar inimigos que "
            "compartilhem qualquer um dos dois.",
            extra_languages=1),
    Ability("mimic_sounds", "Imitar sons",
            "1x por batalha, +4 [circunstancia] num ataque (feinte); "
            "Desmoralizar dispensa idioma em comum.",
            feint=_mimic_sounds_feint, demoralize_ignores_language=True),
    Ability("ancestral_blood", "Sangue ancestral",
            "+2 [circunstancia] no ataque contra alvos Grandes.",
            attack_mods=_ancestral_blood_mods),
    Ability("autotroph", "Autotrofo",
            "regenera 1 PV no inicio do seu turno.",
            on_turn_start=_autotroph),
    Ability("ferocity", "Ferocidade",
            "1x por batalha, ao cair fica a 0 PV e morrendo, mas so desmaia no "
            "fim do seu turno (o teste de morte segue normal a partir dai).",
            on_downed=_ferocity),
    Ability("flight", "Voo",
            "+2 casas de deslocamento, ignora terreno; +1 CA [natural].",
            speed=2, ac_natural=1),
]

ABILITIES = {a.id: a for a in _LIST}

_NONE = Ability("none", "Sem habilidade", "sem efeito.")


def get(ability_id):
    return ABILITIES.get(ability_id, _NONE)

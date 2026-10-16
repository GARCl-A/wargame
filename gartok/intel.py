"""Who knows what about whom in a fight.

A side sees a foe's position, race, size, alignment, the *names* of its gear, its
visible conditions and its health in `STEPS` steps. Everything else is learned
with Intelligence: the first time anyone on a side sees a foe, every teammate
that sees it rolls d20 + INT against `DC = BASE_DC + the foe's racial level`; the
best margin is stored and shared by the side, and opens the fields of the bands
it reaches (`FIELDS`). `assess` rolls again at a bonus on one target. A failed
roll reveals nothing and never lies.

The bestiary is what a guild keeps between fights: the races it has fought (a
lower DC), the racial abilities it has seen (free on the next one of the race) and
what it learned of each authored NPC (known in every later fight against it).

The AI is another player: it rolls the same checks and reads only `known_fields`.
`battle.intel` holds the per-fight state; this module is the free functions over it,
like `vision.py`.
"""

import math
import random
from dataclasses import dataclass, field

from . import items, magic, talents

STEPS = 5                 # a foe's health shows in this many steps
BASE_DC = 8
RACE_DISCOUNT = 2         # the DC drops this much against a race the guild has fought
ASSESS_BONUS = 4
EASY, MEDIUM, HARD = 0, 5, 10     # the margin a band opens at

FIELDS = {                # field -> the band that opens it
    "damage_die": EASY, "speed": EASY, "level": EASY, "racial_ability": EASY,
    "to_hit": MEDIUM, "damage_bonus": MEDIUM, "ac": MEDIUM, "md": MEDIUM,
    "attrs": HARD, "hp": HARD, "talents": HARD, "spells": HARD, "artifact": HARD,
}
BANDS = (("EASY", EASY), ("MEDIUM", MEDIUM), ("HARD", HARD))
LABELS = {
    "damage_die": "damage die", "speed": "speed", "level": "level", "racial_ability": "racial ability",
    "to_hit": "to hit", "damage_bonus": "damage bonus", "ac": "AC", "md": "mental defense",
    "attrs": "attributes", "hp": "hit points", "talents": "talents", "spells": "spells", "artifact": "artefact",
}
_ATTRS = (("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
          ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma"))
_ARTIFACT_EFFECTS = {
    items.BIWOLF_LEATHER_ITEM: "+1 AC against anything that is not a humanoid.",
    "Signal Horn": "Blown once per battle: allies near it gain +2 initiative.",
}


class Bestiary:
    """What a guild has learned about the world's fighters; saved with the guild."""

    def __init__(self, races=(), abilities=(), named=None):
        self.races = set(races)             # race names fought
        self.abilities = set(abilities)     # racial ability ids seen
        self.named = dict(named or {})      # authored NPC slug -> the best margin ever read

    def to_dict(self):
        return {"races": sorted(self.races), "abilities": sorted(self.abilities), "named": dict(self.named)}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("races", ()), d.get("abilities", ()), d.get("named"))


class Intel:
    """One fight's knowledge: each side's best margin per foe, what a side may add to a roll."""

    def __init__(self, battle):
        self.rng = random.Random("|".join(sorted(u.name for u in battle.units)))
        teams = battle.teams
        self.margin = {t: {} for t in teams}
        self.bonus = dict.fromkeys(teams, 0)
        self.bestiary = dict.fromkeys(teams)
        self.assessed = {}
        self.last_seen = {t: {} for t in teams}   # foe -> the cell its side last saw it on
        if battle.aggressor:        # whoever brought the fight knows where its prey was when it set out
            self.last_seen[battle.aggressor] = {u: u.pos for u in battle.units if u.team != battle.aggressor}
        self.visited = {t: set() for t in teams}  # search waypoints a side has been near
        self._sight = {}

    def bind(self, team, bestiary=None, bonus=0):
        self.bestiary[team] = bestiary
        self.bonus[team] = bonus


@dataclass
class Known:
    """What one side knows of one unit: `fields` maps each field to its value, or None while hidden."""
    full: bool
    margin: int | None
    dc: int
    steps: int
    fields: dict = field(default_factory=dict)
    visible: dict = field(default_factory=dict)

    def knows(self, name):
        return self.fields.get(name) is not None


def health_steps(unit):
    """How many of the `STEPS` the unit's health fills: at least one while it stands."""
    if unit.hp <= 0 or unit.dead:
        return 0
    return max(1, math.ceil(STEPS * unit.hp / unit.hp_max))


def dc(battle, team, target):
    best = battle.intel.bestiary[team]
    seen = best is not None and target.race["name"] in best.races
    return BASE_DC + target.char.racial_level - (RACE_DISCOUNT if seen else 0)


def _slug(target):
    return getattr(target.char, "npc_slug", None)


def _store(battle, team, target, margin):
    margins = battle.intel.margin[team]
    old = margins.get(target)
    if old is not None and margin <= old:
        return
    margins[target] = margin
    best = battle.intel.bestiary[team]
    if best is None:
        return
    if margin >= EASY:
        best.abilities.add(target.ability.id)
    slug = _slug(target)
    if slug is not None:
        best.named[slug] = max(margin, best.named.get(slug, margin))


def _roll(battle, team, roller, bonus=0):
    return battle.intel.rng.randint(1, 20) + roller.mod_intelligence + battle.intel.bonus[team] + bonus


def _sight(battle, team):
    """`{foe: [teammates that see it]}` for the foes `team` sees now, and where it last saw each.
    Cheap to call often: it is worked out again only when something on the board has moved."""
    intel = battle.intel
    key = (battle.round_no, battle.turn_idx, tuple((u.pos, u.alive, u.has_torch) for u in battle.units))
    cached = intel._sight.get(team)
    if cached and cached[0] == key:
        return cached[1]
    mates = [u for u in battle.units if u.team == team and u.alive]
    seen = {}
    for foe in battle.units:
        if foe.team == team or not foe.alive:
            continue
        seers = [m for m in mates if battle.can_see_unit(m, foe)]
        if seers:
            seen[foe] = seers
    memory = intel.last_seen[team]
    for foe in [f for f in memory if not f.alive]:
        del memory[foe]
    for foe in seen:
        memory[foe] = foe.pos
    intel._sight[team] = (key, seen)
    return seen


def observe(battle, team):
    """Roll the opening check for every foe `team` sees for the first time."""
    intel = battle.intel
    seen = _sight(battle, team)
    best = intel.bestiary[team]
    for foe, seers in seen.items():
        if foe in intel.margin[team]:
            continue
        need = dc(battle, team, foe)
        margin = max(_roll(battle, team, m) for m in seers) - need
        slug = _slug(foe)
        if best is not None and slug in best.named:
            margin = max(margin, best.named[slug])
        _store(battle, team, foe, margin)
        if best is not None:
            best.races.add(foe.race["name"])


def visible_foes(battle, unit):
    """The foes some unit of `unit`'s side sees: all it may count, measure or flee from."""
    return list(_sight(battle, unit.team))


def assess_block(battle, actor, target):
    """Why `actor` cannot assess `target` now, or "" when it can: a foe in sight, once a round."""
    if target is None or not target.alive or target.team == actor.team:
        return "not a foe"
    if not battle.can_see_unit(actor, target):
        return "not in sight"
    if battle.intel.assessed.get((actor.team, target)) == battle.round_no:
        return "already assessed this round"
    return ""


def assess(battle, actor, target):
    """The assess roll: d20 + INT + `ASSESS_BONUS` against the same DC. Returns
    `(nat total, margin, fields this opened)`; the stored margin is the better of the two."""
    team = actor.team
    observe(battle, team)
    before = _open(battle, team, target)
    total = _roll(battle, team, actor, ASSESS_BONUS)
    margin = total - dc(battle, team, target)
    battle.intel.assessed[(team, target)] = battle.round_no
    _store(battle, team, target, margin)
    return total, margin, sorted(_open(battle, team, target) - before, key=list(FIELDS).index)


def _open(battle, team, target):
    """The fields `team` has open on `target` right now."""
    if target.team == team:
        return set(FIELDS)
    margin = battle.intel.margin[team].get(target)
    opened = {name for name, need in FIELDS.items() if margin is not None and margin >= need}
    best = battle.intel.bestiary[team]
    if best is not None and target.ability.id in best.abilities:
        opened.add("racial_ability")
    if target.team != team and not target.equipped_artifact:
        opened.discard("artifact")
    return opened


def _damage_die(u):
    n, faces = u.unarmed_damage if (u.unarmed or u.improvised) else u.weapon["damage"]
    return f"{n}d{faces}"


def _to_hit(u):
    bonus, src = (u.mod_strength, "STR") if u.improvised else u.attack_bonus
    return f"{bonus:+} ({src})"


def _damage_bonus(u):
    return u.mod_strength if (u.unarmed or u.improvised or not u.ranged) else 0


def _artifact_effect(u):
    name = u.equipped_artifact
    if name in _ARTIFACT_EFFECTS:
        return _ARTIFACT_EFFECTS[name]
    attr = items.ARTIFACT_ATTRIBUTES.get(name)
    return f"+{attr[1]} {attr[0].capitalize()} while worn." if attr else "No effect anyone has found."


def _value(name, u):
    if name == "damage_die":
        return _damage_die(u)
    if name == "speed":
        return u.speed
    if name == "level":
        return u.char.racial_level
    if name == "racial_ability":
        return (u.ability.name, u.ability.effect)
    if name == "to_hit":
        return _to_hit(u)
    if name == "damage_bonus":
        return _damage_bonus(u)
    if name == "ac":
        return u.ac
    if name == "md":
        return u.mental_defense
    if name == "attrs":
        return [(abbr, getattr(u, attr)) for abbr, attr in _ATTRS]
    if name == "hp":
        return (max(u.hp, 0), u.hp_max)
    if name == "talents":
        return [(t.name, t.effect) for t in (talents.get(i) for ids in u.char.talents.values() for i in ids) if t]
    if name == "spells":
        return [magic.SPELLS[s].name for s in u.spells_known if s in magic.SPELLS]
    return _artifact_effect(u)


def _conditions(u):
    out = []
    if u.dying:
        out.append(f"dying {u.death_clock}")
    elif u.stable:
        out.append("stable")
    elif u.broken:
        out.append("broken")
    if u.has_condition("sleeping"):
        out.append("asleep")
    if u.demoralized:
        out.append("demoralized")
    if u.poisoned:
        out.append("poisoned")
    if u.hunger_level:
        out.append(u.hunger_label)
    return out


def knows(battle, team, target, name):
    """Does `team` have field `name` open on `target`?"""
    observe(battle, team)
    return name in _open(battle, team, target)


def known_fields(battle, team, target):
    """What `team` knows of `target`: the one read the modal, the board and `ai.py` share."""
    observe(battle, team)
    opened = _open(battle, team, target)
    fields = {name: (_value(name, target) if name in opened else None)
              for name in FIELDS if not (name == "artifact" and not target.equipped_artifact)}
    visible = {"name": target.name, "race": target.race["name"], "size": target.size,
               "alignment": target.alignment, "conditions": _conditions(target),
               "weapon": target.weapon_name, "armor": target.armor_name if target.armor else None,
               "artifact": target.equipped_artifact}
    return Known(full=target.team == team, margin=battle.intel.margin[team].get(target),
                 dc=dc(battle, team, target), steps=health_steps(target), fields=fields, visible=visible)


def shown(battle, target, name, value):
    """`value` of `target`'s field `name` as a log line shows it: the number when the player's side
    has read it, else "?"."""
    observe(battle, "player")
    return str(value) if name in _open(battle, "player", target) else "?"

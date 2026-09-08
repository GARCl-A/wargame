"""Talent trees: what each track of experience lets a character get better at.

One tree per XP track (see `progression.py`). Reaching a new level in a track
grants one pick in that track's tree; `Unit.choose_talent` spends it. Mirrors
`abilities.py` -- a frozen-dataclass registry, effects as plain numeric knobs
read back where they matter: `Unit._derive_combat` (HP, AC, carry),
`Combatant.attack_mods` / `damage_roll` / `attack_range` (the combat ones),
`economy` (the haggle ones) and `recruit.convince` (the pitch one). Adding a
node that reuses an existing knob = editing only this file.

**Design premise (see the `gartok-talent-trees` memo).** The tree goes from
general to specific: a tier-1 root is a broad identity; each step deeper makes
the character a specialist in one particular action. **No pick is mutually
exclusive** -- one pick per track level, the player fills the tree however they
like (bottom-up, straight down one branch, spread wide), and over enough levels
can hold every node. A tier-2 node just needs its tier-1 root first (`requires`).

`name` / `effect` are player-facing (English, the current text standard); `id`
and field names are English identifiers.
"""

from dataclasses import dataclass

TRACKS = ("combat", "work")

# Work-track tuning knobs, kept here so the trees are the one place to tune.
COIN_BONUS = 0.20         # "Piecework": fraction added to coin from paid work
ACTIVITY_SPEEDUP = 0.10   # "Brisk Hands": fraction shaved off an activity's clock
                          #   cost (user weighing 0.05 -- tune here after the math)


@dataclass(frozen=True)
class Talent:
    id: str
    track: str                       # "combat" | "work"
    tier: int                        # 1 = a root; deeper nodes sit at higher tiers
    name: str
    effect: str
    requires: str | None = None      # id of a talent that must be taken first
    icon: str = ""                   # "<category>/<name>" under assets/icons/ (level screen)

    # --- effect knobs (all optional) ---------------------------------- #
    attr_bonus: tuple = ()           # ((attribute, amount), ...) -- added to the SCORE
    haggle_charisma: int = 0         # +N Charisma, market buy/sell checks only
    carry_buffer: int = 0            # +N kg of stagger-check headroom, spent only on
                                     #   non-weapon/non-consumable cargo actually carried
    # combat, tier 2
    to_hit_str: int = 0              # +N to hit on Strength-based attacks
    to_hit_dex: int = 0             # +N to hit on Dexterity-based attacks
    melee_damage: int = 0           # +N damage on melee attacks
    ranged_reach: int = 0           # +N squares of range on ranged / thrown weapons
    hp_per_hd: int = 0              # +N max HP per Hit Die the character has
    ac_bonus: int = 0              # +N AC, flat
    # work, tier 2
    coin_gain: float = 0.0          # +X fraction of coin from an activity that pays in coin
    activity_speed: float = 0.0     # activity finishes at (1 - X) of its clock cost
    recruit_charisma: int = 0       # +N to the recruiter's side of a taverna pitch
    food_haggle: int = 0            # +N market haggle steps on food, shared language or not

    @property
    def desc(self):
        return f"{self.name}: {self.effect}"


_LIST = [
    # ================================================================== #
    # combat -- pick the kind of fighter you are, then the action you     #
    # specialise in                                                       #
    # ================================================================== #
    Talent("strong", "combat", 1, "Strong",
           "+1 Strength.", attr_bonus=(("strength", 1),), icon="action/muscle-up"),
    Talent("sure_strike", "combat", 2, "Sure Strike",
           "+1 to hit with Strength-based attacks.",
           requires="strong", to_hit_str=1, icon="action/targeting"),
    Talent("heavy_hand", "combat", 2, "Heavy Hand",
           "+1 damage on melee attacks.",
           requires="strong", melee_damage=1, icon="action/crush"),

    Talent("agile", "combat", 1, "Agile",
           "+1 Dexterity.", attr_bonus=(("dexterity", 1),), icon="action/acrobatic"),
    Talent("long_reach", "combat", 2, "Long Reach",
           "+1 square of range with ranged and thrown weapons.",
           requires="agile", ranged_reach=1, icon="action/bowman"),
    Talent("deadeye", "combat", 2, "Deadeye",
           "+1 to hit with Dexterity-based attacks.",
           requires="agile", to_hit_dex=1, icon="action/ricochet"),

    Talent("tough", "combat", 1, "Tough",
           "+1 Constitution.", attr_bonus=(("constitution", 1),), icon="body/bell-shield"),
    Talent("hardy", "combat", 2, "Hardy",
           "+1 max HP for every Hit Die you have.",
           requires="tough", hp_per_hd=1, icon="body/heart-inside"),
    Talent("bulwark", "combat", 2, "Bulwark",
           "+1 AC.", requires="tough", ac_bonus=1, icon="body/surrounded-shield"),

    # ================================================================== #
    # work -- two roots, carrier and negotiator                           #
    # ================================================================== #
    Talent("carrier", "work", 1, "Carrier",
           "carry up to 1 kg more gear before you stagger (not food or weapons).",
           carry_buffer=1, icon="body/lift"),
    Talent("piecework", "work", 2, "Piecework",
           "+20% coin from work that pays in coin.",
           requires="carrier", coin_gain=COIN_BONUS, icon="action/profit"),
    Talent("brisk_hands", "work", 2, "Brisk Hands",
           "work finishes 10% faster -- you keep the time.",
           requires="carrier", activity_speed=ACTIVITY_SPEEDUP, icon="action/sprint"),

    Talent("negotiator", "work", 1, "Negotiator",
           "+1 Charisma for market buy and sell checks.", haggle_charisma=1,
           icon="action/shaking-hands"),
    Talent("fixer", "work", 2, "Fixer",
           "+1 to your pitch when talking someone into the guild.",
           requires="negotiator", recruit_charisma=1, icon="action/convince"),
    Talent("provisioner", "work", 2, "Provisioner",
           "+1 to haggling on food, shared language or not.",
           requires="negotiator", food_haggle=1, icon="action/trade"),
]

TALENTS = {t.id: t for t in _LIST}

# Per-track, in list order (root then its children) -- what the level screen draws.
TREE = {track: [t for t in _LIST if t.track == track] for track in TRACKS}


def get(talent_id):
    return TALENTS.get(talent_id)

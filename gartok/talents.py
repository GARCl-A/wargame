"""Talent trees: what each track of experience lets a character get better at.

One tree per XP track (see `progression.py`). Reaching a new level in a track
grants one pick in that track's tree; `Unit.choose_talent` spends it. Mirrors
`abilities.py` -- a frozen-dataclass registry.

A talent's mechanical effect is a tuple of `Effect(channel, amount[, stat])`
contributions, not a wall of typed fields. A resolver (`talents.bonus` /
`Unit.talent_bonus`) sums the amounts feeding one channel; each channel has
exactly one consumer that reads it back:

    channel           consumer                         stat
    attr              Unit._apply_attributes           attribute name
    to_hit            Unit.attack_bonus / Combatant     "strength" | "dexterity"
    melee_damage      Combatant.damage_roll            --
    melee_reach       Combatant.attack_range           --
    ranged_reach      Combatant.attack_range/throw     --
    hp_per_hd         Unit._derive_hp (x Hit Dice)     --
    ac                Unit._derive_ac                  --
    mental_defense    Unit._derive_ac                  --
    initiative        Combatant.initiative_bonus       --
    speed             Unit._derive_speed               --
    carry_buffer      Unit._carry_relief (capped)      --
    haggle_cha        Unit.haggle_charisma_mod         --
    food_haggle       Unit.price_mods (economy)        --
    coin_gain         Guild.work_shift                 --
    activity_speed    Guild.work_shift                 --
    recruit_cha       recruit.convince                 --

Adding a node that reuses a channel = editing only this file. A node that needs
a brand-new channel adds one consumer call site -- no plugin bus, same as the
racial-ability hooks.

**Design premise (see the `gartok-talent-trees` memo).** The tree goes from
general to specific: a tier-1 root is a broad identity; each step deeper makes
the character a specialist in one particular action. **No pick is mutually
exclusive** -- one pick per track level, the player fills the tree however they
like (bottom-up, straight down one branch, spread wide), and over enough levels
can hold every node. A deeper node just needs the one above it first (`requires`),
which chains: `fleet` (tier 3) pulls in `deadeye` then `agile`.

**The racial track** (`racial`) earns no XP of its own -- its level is
`progression.racial_level(combat_level + work_level)`, so every level anywhere
grants a racial pick (and a hit die). Its nodes are **race-gated**: a `Talent`
with `race` set only shows / can be picked for that race. Grippli is the first
race with an authored node (`tongue`); other races have racial levels and picks
but no nodes yet, same way the combat / work trees started.

`name` / `effect` are player-facing (English, the current text standard); `id`
and field names are English identifiers.
"""

from dataclasses import dataclass

TRACKS = ("combat", "work", "racial")
XP_TRACKS = ("combat", "work")        # the tracks that earn their own XP / level directly

# Work-track tuning knobs, kept here so the trees are the one place to tune.
COIN_BONUS = 0.20         # "Piecework": fraction added to coin from paid work
ACTIVITY_SPEEDUP = 0.10   # "Brisk Hands": fraction shaved off an activity's clock
                          #   cost (user weighing 0.05 -- tune here after the math)


@dataclass(frozen=True)
class Effect:
    """One typed contribution a talent makes. `channel` names what it feeds;
    `stat` narrows it on the per-attribute channels (`attr`, `to_hit`) and is
    "" everywhere else. `talents.bonus` sums the amounts for a (channel, stat)."""
    channel: str
    amount: float
    stat: str = ""


@dataclass(frozen=True)
class Talent:
    id: str
    track: str                       # "combat" | "work" | "racial"
    tier: int                        # 1 = a root; deeper nodes sit at higher tiers
    name: str
    effect: str                      # player-facing one-liner
    requires: str | None = None      # id of a talent that must be taken first
    race: str | None = None          # racial track: only offered to this race (None = any)
    icon: str = ""                   # "<category>/<name>" under assets/icons/ (level screen)
    effects: tuple = ()              # Effect(...) contributions -- see the module docstring

    @property
    def desc(self):
        return f"{self.name}: {self.effect}"


_LIST = [
    # ================================================================== #
    # combat -- pick the kind of fighter you are, then the action you     #
    # specialise in                                                       #
    # ================================================================== #
    Talent("strong", "combat", 1, "Strong", "+1 Strength.",
           effects=(Effect("attr", 1, "strength"),), icon="action/muscle-up"),
    Talent("sure_strike", "combat", 2, "Sure Strike",
           "+1 to hit with Strength-based attacks.", requires="strong",
           effects=(Effect("to_hit", 1, "strength"),), icon="action/targeting"),
    Talent("heavy_hand", "combat", 2, "Heavy Hand",
           "+1 damage on melee attacks.", requires="strong",
           effects=(Effect("melee_damage", 1),), icon="action/crush"),

    Talent("agile", "combat", 1, "Agile", "+1 Dexterity.",
           effects=(Effect("attr", 1, "dexterity"),), icon="action/acrobatic"),
    Talent("long_reach", "combat", 2, "Long Reach",
           "+1 square of range with ranged and thrown weapons.", requires="agile",
           effects=(Effect("ranged_reach", 1),), icon="action/bowman"),
    Talent("deadeye", "combat", 2, "Deadeye",
           "+1 to hit with Dexterity-based attacks.", requires="agile",
           effects=(Effect("to_hit", 1, "dexterity"),), icon="action/ricochet"),
    Talent("fleet", "combat", 3, "Fleet", "+1 square of Speed.", requires="deadeye",
           effects=(Effect("speed", 1),), icon="action/leapfrog"),

    Talent("tough", "combat", 1, "Tough", "+1 Constitution.",
           effects=(Effect("attr", 1, "constitution"),), icon="body/bell-shield"),
    Talent("hardy", "combat", 2, "Hardy",
           "+1 max HP for every Hit Die you have.", requires="tough",
           effects=(Effect("hp_per_hd", 1),), icon="body/heart-inside"),
    Talent("bulwark", "combat", 2, "Bulwark", "+1 AC.", requires="tough",
           effects=(Effect("ac", 1),), icon="body/surrounded-shield"),

    Talent("alert", "combat", 1, "Alert", "+1 Wisdom.",
           effects=(Effect("attr", 1, "wisdom"),), icon="head/gaze"),
    Talent("quick_wits", "combat", 2, "Quick Wits", "+2 initiative.",
           requires="alert",
           effects=(Effect("initiative", 2),), icon="head/quick-man"),
    Talent("iron_will", "combat", 2, "Iron Will", "+2 Mental Defense.",
           requires="alert",
           effects=(Effect("mental_defense", 2),), icon="action/meditation"),

    # ================================================================== #
    # work -- two roots, carrier and negotiator                           #
    # ================================================================== #
    Talent("carrier", "work", 1, "Carrier",
           "carry up to 1 kg more gear before you stagger (not food or weapons).",
           effects=(Effect("carry_buffer", 1),), icon="body/lift"),
    Talent("piecework", "work", 2, "Piecework",
           "+20% coin from work that pays in coin.", requires="carrier",
           effects=(Effect("coin_gain", COIN_BONUS),), icon="action/profit"),
    Talent("brisk_hands", "work", 2, "Brisk Hands",
           "work finishes 10% faster -- you keep the time.", requires="carrier",
           effects=(Effect("activity_speed", ACTIVITY_SPEEDUP),), icon="action/sprint"),

    Talent("negotiator", "work", 1, "Negotiator",
           "+1 Charisma for market buy and sell checks.",
           effects=(Effect("haggle_cha", 1),), icon="action/shaking-hands"),
    Talent("fixer", "work", 2, "Fixer",
           "+1 to your pitch when talking someone into the guild.", requires="negotiator",
           effects=(Effect("recruit_cha", 1),), icon="action/convince"),
    Talent("provisioner", "work", 2, "Provisioner",
           "+1 to haggling on food, shared language or not.", requires="negotiator",
           effects=(Effect("food_haggle", 1),), icon="action/trade"),

    # ================================================================== #
    # racial -- race-gated; the level is racial_level (sum of the other    #
    # tracks on a scale). One authored node so far.                       #
    # ================================================================== #
    Talent("tongue", "racial", 1, "Tongue",
           "your tongue is a third limb and a weapon: +1 square of reach on "
           "melee attacks.", race="Grippli",
           effects=(Effect("melee_reach", 1),), icon="action/swallow"),
]

TALENTS = {t.id: t for t in _LIST}

# Per-track, in list order (root then its children) -- what the level screen draws.
# TREE["racial"] holds every racial node; `racial_tree` narrows it to one race.
TREE = {track: [t for t in _LIST if t.track == track] for track in TRACKS}


def get(talent_id):
    return TALENTS.get(talent_id)


def racial_tree(race_name):
    """The racial nodes offered to `race_name` -- those with no `race` gate plus
    that race's own. Empty for a race with nothing authored yet."""
    return [t for t in TREE["racial"] if t.race in (None, race_name)]


def bonus(talent_ids, channel, stat=""):
    """Total the given talents contribute to `channel` (narrowed to `stat` on the
    per-attribute channels). Unknown ids are skipped."""
    total = 0
    for tid in talent_ids:
        t = TALENTS.get(tid)
        if t is None:
            continue
        total += sum(e.amount for e in t.effects
                     if e.channel == channel and e.stat == stat)
    return total

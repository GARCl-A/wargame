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
    unarmed_dice      Unit._derive_combat (+N dice)    --
    size_up           Unit._derive_size (+N sizes)     --
    unarmed_finesse   Unit.attack_bonus / Combatant    --
    spin_web          actions.SpinWeb                  --
    venom             actions.base._envenom            poison id
    swim_reach        actions.Swim (+squares per swim) --
    ranged_reach      Combatant.attack_range/throw     --
    hp_per_hd         Unit._derive_hp (x Hit Dice)     --
    post_combat_heal  campaign._carry_forward          --
    ac                Unit._derive_ac                  --
    mental_defense    Unit._derive_ac                  --
    initiative        Combatant.initiative_bonus       --
    speed             Unit._derive_speed               --
    carry_buffer      Unit._carry_relief (capped)      --
    armor_weight_relief Unit.load / Combatant.load     --
    haggle_cha        Unit.haggle_charisma_mod         --
    food_haggle       Unit.price_mods (economy)        --
    coin_gain         Guild.work_shift                 --
    activity_speed    Guild.work_shift                 --
    work_rest         Guild.pass_time (passive heal)   --
    recruit_cha       recruit.convince                 --
    craft_bonus       Unit.progress_crafting           --
    language_study    magic._progress_language         --
    fletcher          campaign._fletcher_rest_pass     --
    dragon_breath     actions.DragonBreath             --
    mighty_shove      actions.Push                     --

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
race with authored nodes (`tongue`, `webbed_feet`); other races have racial levels and picks
but no nodes yet, same way the combat / work trees started.

**The magic track** (`magic`) earns magic XP (`progression.py`). Each school has one root,
granted rather than picked (`granted=True`): a character holds it while that school is in its
`magic_sources`, and only then can it pick the branch under it (`school` names the school).

`name` / `effect` are player-facing (English, the current text standard); `id`
and field names are English identifiers.
"""

from dataclasses import dataclass

TRACKS = ("combat", "work", "racial", "magic")
XP_TRACKS = ("combat", "work", "magic")   # the tracks that earn their own XP / level directly

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
    track: str                       # "combat" | "work" | "racial" | "magic"
    tier: int                        # 1 = a root; deeper nodes sit at higher tiers
    name: str
    effect: str                      # player-facing one-liner
    requires: str | None = None      # id of a talent that must be taken first
    race: str | tuple | None = None  # racial track: only offered to this race, or these (None = any)
    icon: str = ""                   # "<category>/<name>" under assets/icons/ (level screen)
    effects: tuple = ()              # Effect(...) contributions -- see the module docstring
    school: str | None = None        # magic track: the school this node belongs to
    granted: bool = False            # magic root: held while the school is held, never picked

    @property
    def desc(self):
        return f"{self.name}: {self.effect}"

    @property
    def races(self):
        """The races this node is offered to; empty for any race."""
        return () if self.race is None else (self.race,) if isinstance(self.race, str) else tuple(self.race)

    def for_race(self, race_name):
        return not self.races or race_name in self.races


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
    Talent("recovery", "combat", 3, "Recovery",
           "heal 1 HP after every fight you survive.", requires="hardy",
           effects=(Effect("post_combat_heal", 1),), icon="body/arm-bandage"),
    Talent("bulwark", "combat", 2, "Bulwark", "+1 AC.", requires="tough",
           effects=(Effect("ac", 1),), icon="body/surrounded-shield"),
    Talent("armor_bearer", "combat", 3, "Armor Bearer",
           "reduces the carried weight of equipped armor by up to 6 kg.", requires="bulwark",
           effects=(Effect("armor_weight_relief", 6),), icon="body/master-of-arms"),

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

    Talent("steady_pace", "work", 3, "Steady Pace",
           "work counts as rest: you recover HP while you work, as if resting.",
           requires="brisk_hands",
           effects=(Effect("work_rest", 1),), icon="body/knee-bandage"),

    Talent("charismatic", "work", 1, "Charismatic", "+1 Charisma.",
           effects=(Effect("attr", 1, "charisma"),), icon="action/talk"),
    Talent("negotiator", "work", 2, "Negotiator",
           "+1 Charisma for market buy and sell checks.", requires="charismatic",
           effects=(Effect("haggle_cha", 1),), icon="action/shaking-hands"),
    Talent("fixer", "work", 2, "Fixer",
           "+1 to your pitch when talking someone into the guild.", requires="charismatic",
           effects=(Effect("recruit_cha", 1),), icon="action/convince"),
    Talent("provisioner", "work", 3, "Provisioner",
           "+1 to haggling on food, shared language or not.", requires="negotiator",
           effects=(Effect("food_haggle", 1),), icon="action/trade"),

    Talent("clever", "work", 1, "Clever", "+1 Intelligence.",
           effects=(Effect("attr", 1, "intelligence"),), icon="head/brain"),
    Talent("linguist", "work", 2, "Linguist",
           "+2 to progress rolls when studying a foreign language.", requires="clever",
           effects=(Effect("language_study", 2),), icon="head/spectacles"),
    Talent("crafter", "work", 2, "Crafter",
           "+1 to progress rolls when crafting items.", requires="clever",
           effects=(Effect("craft_bonus", 1),), icon="action/crafting"),
    Talent("apothecary", "work", 3, "Apothecary",
           "learn a random apothecary recipe (or +1 brewing rolls if all known).",
           requires="crafter",
           effects=(), icon="action/pouring-chalice"),
    Talent("blacksmith", "work", 3, "Blacksmith",
           "learn a random forge recipe (or +1 forging rolls if all known).",
           requires="crafter",
           effects=(), icon="body/blacksmith"),
    Talent("fletcher", "work", 3, "Fletcher",
           "carve arrows on rest: consumes 1 Lumber to refill quivers whenever the group rests.",
           requires="crafter",
           effects=(Effect("fletcher", 1),), icon="action/bowman"),

    # ================================================================== #
    # racial -- race-gated; the level is racial_level (sum of the other    #
    # tracks on a scale). One authored node so far.                       #
    # ================================================================== #
    Talent("tongue", "racial", 1, "Tongue",
           "your tongue is a third limb and a weapon: +1 square of reach on "
           "melee attacks.", race="Grippli",
           effects=(Effect("melee_reach", 1),), icon="action/swallow"),
    Talent("webbed_feet", "racial", 1, "Webbed Feet",
           "a strong swimmer: +1 square on every Swim, never past your full speed.",
           race="Grippli", effects=(Effect("swim_reach", 1),), icon="action/drowning"),
    Talent("fruitful", "racial", 1, "Fruitful",
           "your leafy body blooms at dawn: produce 1 fresh fruit each day to "
           "nourish yourself or your companions.", race="Treefolk",
           effects=(Effect("fruitful", 1),), icon="action/fruiting"),
    Talent("cosmopolitan", "racial", 1, "Cosmopolitan",
           "at home among strangers: reduces alignment distance penalties by 1 "
           "when recruiting, negotiating, or trading.", race="Human",
           effects=(Effect("align_distance_reduction", 1),), icon="action/shaking-hands"),
    Talent("halfling_luck", "racial", 1, "Halfling Luck",
           "fate bends around you: once every 24 hours, reroll your first "
           "failed d20 test (in or out of combat).", race="Halfling",
           effects=(Effect("halfling_luck", 1),), icon="action/juggler"),
    Talent("woodland_scout", "racial", 1, "Woodland Scout",
           "the forest whispers its secrets to you: while the group travels Cautious, "
           "the chance of an ambush on the road or on a hunt is 10% lower.", race="Elf",
           effects=(Effect("woodland_scout", 1),), icon="action/run"),
    Talent("intimidating_presence", "racial", 1, "Intimidating Presence",
           "a terrifying physical presence: you may use your Strength modifier "
           "instead of Charisma when attempting to Demoralize enemies.", race=("Orc", "Ogre"),
           effects=(Effect("intimidating_presence", 1),), icon="action/shouting"),
    Talent("swarm_logic", "racial", 1, "Swarm Logic",
           "there is safety, and speed, in numbers: you work 10% faster for "
           "every other Goblin working alongside you.", race="Goblin",
           effects=(Effect("swarm_logic", 1),), icon="action/hive-mind"),
    Talent("tireless_worker", "racial", 1, "Tireless Worker",
           "machines do not sleep or complain: you complete simple labor "
           "and gathering tasks significantly faster.", race="Automaton",
           effects=(Effect("activity_speed", 0.25),), icon="gui/auto-repair"),
    Talent("centaur_mount", "racial", 1, "Mount",
           "your strong back: allow a Medium or Small ally to ride you.", race="Centaur",
           effects=(Effect("centaur_mount", 1),), icon="body/cavalry"),
    Talent("giant_grip", "racial", 1, "Giant's Grip",
           "immense physical strength: wield weapons one size above your own (Large for a Goliath, "
           "Huge for an Ogre).", race=("Goliath", "Ogre"),
           effects=(Effect("giant_grip", 1),), icon="action/muscle-up"),
    Talent("mighty_shove", "racial", 1, "Mighty Shove",
           "your Push throws the target 3 squares back and deals 1d6; whatever stops it on the way "
           "(a wall, or a body, which takes the 1d6 too) deals 1d6 more.", race="Ogre",
           effects=(Effect("mighty_shove", 1),), icon="action/back-forth"),
    Talent("phalanx", "racial", 1, "Phalanx",
           "martial discipline: +1 AC if you are adjacent to at least one ally.", race="Hobgoblin",
           effects=(Effect("phalanx", 1),), icon="body/surrounded-shield"),
    Talent("organic_harvester", "racial", 1, "Organic Harvester",
           "scavenging instinct: 25% chance per organic loot type to find more meat "
           "or hide after a beast battle.", race="Lizardfolk",
           effects=(Effect("organic_harvester", 1),), icon="action/eating"),
    Talent("corpse_eater", "racial", 1, "Corpse Eater",
           "brutal feast: spend 1 AP to eat a dead enemy, satiating hunger and "
           "demoralizing enemies who see you.", race="Gnoll",
           effects=(Effect("corpse_eater", 1),), icon="action/swallow"),
    Talent("gnome_magic_excitement", "racial", 1, "Magic Excitement",
           "enthusiasm for the unknown: on the first day studying a new spell, roll twice for progress.", race="Gnome",
           effects=(), icon="hat/magic-hat"),
    Talent("kenku_faith_initiate", "racial", 1, "Faith Initiate",
           "divine calling: you become initiated in faith magic. If already initiated, gain a free spell.", race="Kenku",
           effects=(), icon="action/prayer"),
    Talent("sprite_nature_initiate", "racial", 1, "Nature Initiate",
           "fey magic: you become initiated in nature magic and gain the Share Magic action.", race="Sprite",
           effects=(), icon="hat/flower-hat"),
    Talent("dwarf_crafting", "racial", 1, "Dwarven Forging",
           "your ancestral craft: you learn the recipes to forge the Dwarf Axe, Shield and Armor.", race="Dwarf",
           effects=(), icon="body/blacksmith"),
    Talent("kobold_trapper", "racial", 1, "Trapper",
           "cunning mechanisms: you learn the recipes for the Bear and Alarm traps, and can deploy them.", race="Kobold",
           effects=(), icon="body/sinking-trap"),
    Talent("aurochs_might", "racial", 1, "Aurochs Might",
           "a gore that lifts a man: +5 squares of speed and +3 damage on melee attacks.",
           race="Ox", effects=(Effect("speed", 5), Effect("melee_damage", 3)),
           icon="action/crush"),
    Talent("rending_bite", "racial", 1, "Rending Bite",
           "jaws that tear: roll one extra die on your unarmed attack.", race="Wolf",
           effects=(Effect("unarmed_dice", 1),), icon="action/eating"),
    Talent("elder_skeleton", "racial", 1, "Elder Skeleton",
           "centuries of unlife sharpen the mind and the voice: +4 Intelligence and "
           "+4 Charisma.", race="Skeleton",
           effects=(Effect("attr", 4, "intelligence"), Effect("attr", 4, "charisma")),
           icon="hat/crowned-skull"),
    Talent("skeleton_faith_initiate", "racial", 1, "Faith Initiate",
           "a vow that outlasted death: you become initiated in faith magic. If already "
           "initiated, gain a free spell.", race="Skeleton",
           effects=(), icon="action/prayer"),
    Talent("deft_bones", "racial", 1, "Deft Bones",
           "light, quick bones: your unarmed attacks hit with the better of Strength "
           "or Dexterity.", race="Skeleton",
           effects=(Effect("unarmed_finesse", 1),), icon="action/sprint"),
    Talent("giant_growth", "racial", 1, "Giant Growth",
           "you swell past your kin: your size goes up one step (Medium to Large, 2x2).",
           race="Giant Spider",
           effects=(Effect("size_up", 1),), icon="body/cavalry"),
    Talent("titanic_growth", "racial", 2, "Titanic Growth",
           "a second growth spurt: your size goes up another step (Large to Huge, 3x3).",
           requires="giant_growth", race="Giant Spider",
           effects=(Effect("size_up", 1),), icon="body/cavalry"),
    Talent("spin_web", "racial", 1, "Spin Web",
           "spin a web trap next to you, as wide as your own body (1x1, 2x2 or 3x3): "
           "the first foe to touch it is stuck, unable to walk through its next turn.",
           race="Giant Spider",
           effects=(Effect("spin_web", 1),), icon="action/hive-mind"),
    Talent("serpent_growth", "racial", 1, "Serpent Growth",
           "you outgrow your coils: your size goes up one step (Small to Medium).", race="Snake",
           effects=(Effect("size_up", 1),), icon="body/cavalry"),
    Talent("great_serpent", "racial", 2, "Great Serpent",
           "a second shedding: your size goes up another step (Medium to Large, 2x2).",
           requires="serpent_growth", race="Snake",
           effects=(Effect("size_up", 1),), icon="body/cavalry"),
    Talent("snake_venom", "racial", 1, "Snake Venom",
           "your fangs run with venom: a bite that hurts forces a Constitution save (DC 11 + your "
           "racial level) or the victim is poisoned, one stack more per failed save, each eating a "
           "point of Constitution.", race="Snake",
           effects=(Effect("venom", 1, "snake_venom"),), icon="head/snake-bite"),
    Talent("dire_growth", "racial", 1, "Dire Growth",
           "you grow past your kin: your size goes up one step (a Wolf becomes Large).", race="Wolf",
           effects=(Effect("size_up", 1),), icon="body/cavalry"),

    # ================================================================== #
    # magic -- one granted root per school, its branch below             #
    # ================================================================== #
    Talent("bloodline", "magic", 1, "Bloodline",
           "initiated into Blood: the magic was born with you, in your veins.",
           school="blood", granted=True, icon="map/blood"),
    Talent("dragon", "magic", 2, "Dragon",
           "dragon blood runs in you: your hide hardens into scales (+1 AC).",
           requires="bloodline", school="blood",
           effects=(Effect("ac", 1),), icon="head/horned-reptile"),
    Talent("dragon_breath", "magic", 3, "Dragon Breath",
           "2 points: breathe a cone 3 squares deep (1, 3 and 5 wide); one attack roll "
           "against everyone in it, allies too, 2d6 damage on each hit.",
           requires="dragon", school="blood",
           effects=(Effect("dragon_breath", 1),), icon="body/fire-dash"),
    Talent("nature_initiated", "magic", 1, "Nature Initiated",
           "initiated into Nature: the green answers you.",
           school="nature", granted=True, icon="map/leaf"),
    Talent("faith_initiated", "magic", 1, "Faith Initiated",
           "initiated into Faith: a higher call answers you.",
           school="faith", granted=True, icon="head/spiked-halo"),
]

TALENTS = {t.id: t for t in _LIST}

# Per-track, in list order (root then its children) -- what the level screen draws.
# TREE["racial"] holds every racial node; `racial_tree` narrows it to one race.
TREE = {track: [t for t in _LIST if t.track == track] for track in TRACKS}
TREES = TREE


def get(talent_id):
    return TALENTS.get(talent_id)


def racial_tree(race_name):
    """The racial nodes offered to `race_name` -- those with no `race` gate plus
    that race's own. Empty for a race with nothing authored yet."""
    return [t for t in TREE["racial"] if t.for_race(race_name)]


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

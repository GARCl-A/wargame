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
    melee_reach       Combatant.tongue_reach           --
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
    haul_buffer       Unit._carry_relief (capped)      --
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
    tavern_perform_bonus Guild.perform_shift           --
    woodcarver_bonus  Unit.craft_bonus                 --
    skinner_bonus     hunt.grant_haul / campaign       --
    wheelwright       Guild.repair_wagon               --
    deep_reserves     Unit.hunger_level                --
    rest_heal_bonus   guild_upkeep.rest_heal           --
    field_cook        Group.light_campfire             --
    hardened          guild_upkeep.nonlethal_clear_hours --
    field_medic_bonus GroupScreen first aid (no combat) --
    herd_capacity_bonus Group.herd_capacity            --
    triage            guild_upkeep.rest_heal           --
    pathfinder        vocations.travel_mult            --
    dragon_breath     actions.DragonBreath             --
    mighty_shove      actions.Push                     --
    spell_to_hit      actions.SpellAction              --
    spell_damage      actions.SpellAction              --
    spell_heal        actions.SpellAction              --
    spell_range       actions.SpellAction              --
    obscured_penalty_relief actions.base.obscured_penalty --
    flank_defense     actions.base._flank_penalty      --
    demoralize_bonus  actions.combat.Demoralize        --
    gruesome_takedown actions.base._resolve_hit        --
    demoralized_target_damage actions.base._resolve_hit --
    assess_bonus      intel._roll                      --
    assess_active_bonus intel.assess                   --
    full_intel_to_hit Combatant.attack_mods            --
    grab_bonus        actions.combat.Grab              --
    push_bonus        actions.combat.Push              --
    flank_finesse_damage actions.base._resolve_hit     --
    defend_mental_defense Combatant.mental_defense     --
    demoralize_ally_initiative actions.combat.execute_demoralize --
    full_intel_crit_range actions.base._resolve_hit    --
    unarmed_cleave    actions.weapon_actions.Cleave    --
    flies             Combatant.flies                  --
    fly_speed         Unit._derive_speed               --
    grudge / ambush_predator / under_the_whip / arena_born / cavalry_charge
                      Combatant.racial_hit_mods         --
    underfoot / tiny_target  Combatant.ac_vs            --
    hold_the_line     actions.base._held_line          --
    blood_frenzy / thornskin / stone_endurance / gore_charge
                      actions.base._resolve_hit        --
    savage_attacks    Combatant.damage_roll            --
    twilight_sight    vision.dark_range                --
    bloodscent        vision.can_see_unit              --
    sticky_tongue     actions.AttackTongue             --
    jump_reach        actions.Jump                     --
    tail_sweep        actions.TailSweep                --
    lift_rider        actions.LiftRider                --
    pixie_dust        actions.PixieDust                --
    trap_range        Battle.can_plant_trap            --
    trap_salvage      campaign.absorb_battle           --
    deep_miner        Guild.gather_shift               --
    quartermaster     cohesion._roll_groups            --
    parley            dialogue.Encounter.mod           --
    small_appetite    Unit.consume_daily_food          --
    bountiful_harvest guild_upkeep / rest (Bloom Fruit) --

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
`progression.racial_level(combat_level + work_level + magic_level)`, so every level
anywhere grants a hit die, and every 5th racial level a racial pick. Its nodes are **race-gated**: a `Talent`
with `race` set only shows / can be picked for that race (or any component race of a hybrid).
Most races have authored nodes (e.g. Grippli's `tongue` and `webbed_feet`, Dragon's `dragon` and `dragon_breath`,
Wolf's `pack_hunter`); other races have racial levels and picks and gain nodes as they are designed.

**The magic track** (`magic`) earns magic XP (`progression.py`). Its nodes are school-agnostic
and open to any caster, regardless of which school they are initiated in.

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


def _race_names(race_spec):
    if isinstance(race_spec, dict):
        return tuple(race_spec.get("races") or (race_spec["name"],))
    if isinstance(race_spec, (list, tuple, set)):
        return tuple(race_spec)
    if isinstance(race_spec, str):
        return tuple(s.strip() for s in race_spec.split(",") if s.strip())
    return ()


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
        return not self.races or any(r in self.races for r in _race_names(race_name))


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
    Talent("blind_strike", "combat", 3, "Blind Strike",
           "reduces the attack penalty against obscured or dark targets by 1.", requires="sure_strike",
           effects=(Effect("obscured_penalty_relief", 1),), icon="head/blindfold"),
    Talent("heavy_hand", "combat", 2, "Heavy Hand",
           "+1 damage on melee attacks.", requires="strong",
           effects=(Effect("melee_damage", 1),), icon="action/crush"),
    Talent("wrestler", "combat", 3, "Wrestler",
           "+1 to Push and Grab checks.", requires="heavy_hand",
           effects=(Effect("push_bonus", 1), Effect("grab_bonus", 1)), icon="action/grab"),

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
    Talent("nimble_skirmisher", "combat", 3, "Nimble Skirmisher",
           "+2 damage on Dexterity melee attacks against flanked targets.", requires="deadeye",
           effects=(Effect("flank_finesse_damage", 2),), icon="action/backstab"),

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
    Talent("peripheral_vision", "combat", 3, "Peripheral Vision",
           "when flanked, your AC is only reduced by 1 instead of 2.",
           requires="quick_wits",
           effects=(Effect("flank_defense", 1),), icon="head/one-eyed"),
    Talent("iron_will", "combat", 2, "Iron Will", "+2 Mental Defense.",
           requires="alert",
           effects=(Effect("mental_defense", 2),), icon="action/meditation"),
    Talent("iron_stance", "combat", 3, "Iron Stance",
           "using Defend grants +2 Mental Defense in addition to AC until your next turn.",
           requires="iron_will",
           effects=(Effect("defend_mental_defense", 2),), icon="body/bell-shield"),

    Talent("imposing", "combat", 1, "Imposing", "+1 Charisma.",
           effects=(Effect("attr", 1, "charisma"),), icon="action/shouting"),
    Talent("menacing", "combat", 2, "Menacing",
           "+1 to Demoralize checks.", requires="imposing",
           effects=(Effect("demoralize_bonus", 1),), icon="action/shouting"),
    Talent("gruesome_takedown", "combat", 2, "Gruesome Takedown",
           "upon downing a foe, immediately make a free Demoralize check against "
           "the nearest enemy within range (ignores language).", requires="imposing",
           effects=(Effect("gruesome_takedown", 1),), icon="body/deadly-strike"),
    Talent("cull_the_broken", "combat", 3, "Cull the Broken",
           "+2 damage on attacks against demoralized targets.", requires="menacing",
           effects=(Effect("demoralized_target_damage", 2),), icon="action/boot-stomp"),
    Talent("inspiring_shout", "combat", 3, "Inspiring Shout",
           "upon successfully demoralizing an enemy, grant +1 initiative to the next ally in turn order.",
           requires="gruesome_takedown",
           effects=(Effect("demoralize_ally_initiative", 1),), icon="action/shouting"),

    Talent("tactical_mind", "combat", 1, "Tactical Mind", "+1 Intelligence.",
           effects=(Effect("attr", 1, "intelligence"),), icon="head/brain"),
    Talent("sharp_analysis", "combat", 2, "Sharp Analysis",
           "+1 on all Assess and enemy observation checks.", requires="tactical_mind",
           effects=(Effect("assess_bonus", 1),), icon="head/spectacles"),
    Talent("combat_analysis", "combat", 2, "Combat Analysis",
           "+2 on active Assess checks made during battle.", requires="tactical_mind",
           effects=(Effect("assess_active_bonus", 2),), icon="action/targeting"),
    Talent("exploit_weakness", "combat", 3, "Exploit Weakness",
           "+2 to hit against enemies with Full Intel.", requires="combat_analysis",
           effects=(Effect("full_intel_to_hit", 2),), icon="gui/convergence-target"),
    Talent("anatomist", "combat", 3, "Anatomist",
           "your critical hit range expands by 1 against enemies with Full Intel (crits on 19-20).",
           requires="sharp_analysis",
           effects=(Effect("full_intel_crit_range", 1),), icon="head/spectacles"),

    # ================================================================== #
    # work -- 6 attribute roots, 5 talents each = 30 talents             #
    # ================================================================== #
    # --- STR: Heavy Labor & Carrying ---
    Talent("brawny", "work", 1, "Brawny", "+1 Strength.",
           effects=(Effect("attr", 1, "strength"),), icon="body/lift"),
    Talent("piecework", "work", 2, "Piecework",
           "+20% coin from work that pays in coin.", requires="brawny",
           effects=(Effect("coin_gain", COIN_BONUS),), icon="action/profit"),
    Talent("brisk_hands", "work", 2, "Brisk Hands",
           "work finishes 10% faster -- you keep the time.", requires="brawny",
           effects=(Effect("activity_speed", ACTIVITY_SPEEDUP),), icon="action/sprint"),
    Talent("steady_pace", "work", 3, "Steady Pace",
           "work counts as rest: you recover HP while you work, as if resting.",
           requires="brisk_hands",
           effects=(Effect("work_rest", 1),), icon="body/knee-bandage"),
    Talent("heavy_haul", "work", 3, "Heavy Haul",
           "carry up to 6 kg more before you stagger, in anything that is not equipment "
           "(materials, food, loot -- not weapons, armor, shields or artifacts).",
           requires="piecework",
           effects=(Effect("haul_buffer", 6),), icon="body/weight-lifting-up"),

    # --- CHA: Market, Recruitment & Tavern ---
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
    Talent("troubadour", "work", 3, "Troubadour",
           "+1 on performance rolls when playing on the tavern stage.", requires="fixer",
           effects=(Effect("tavern_perform_bonus", 1),), icon="action/sing"),

    # --- INT: Crafting & Lore ---
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

    # --- DEX: Woodworking, Leather & Wagons ---
    Talent("nimble_fingers", "work", 1, "Nimble Fingers", "+1 Dexterity.",
           effects=(Effect("attr", 1, "dexterity"),), icon="action/button-finger"),
    Talent("woodcarver", "work", 2, "Woodcarver",
           "+1 to progress rolls on the Carpenter's recipes.", requires="nimble_fingers",
           effects=(Effect("woodcarver_bonus", 1),), icon="action/stone-crafting"),
    Talent("skinner", "work", 2, "Skinner",
           "harvest 1 additional 1sqm Hide when hunting beasts in the Wilds.", requires="nimble_fingers",
           effects=(Effect("skinner_bonus", 1),), icon="map/hide"),
    Talent("fletcher", "work", 3, "Fletcher",
           "carve arrows on rest: consumes 1 Lumber to refill quivers whenever the group rests.",
           requires="woodcarver",
           effects=(Effect("fletcher", 1),), icon="action/bowman"),
    Talent("wheelwright", "work", 3, "Wheelwright",
           "skilled cartwright: repairs restore double HP on damaged wagons.",
           requires="woodcarver",
           effects=(Effect("wheelwright", 1),), icon="gui/auto-repair"),

    # --- CON: Field Endurance & Recovery ---
    Talent("sturdy", "work", 1, "Sturdy", "+1 Constitution.",
           effects=(Effect("attr", 1, "constitution"),), icon="body/heart-inside"),
    Talent("deep_reserves", "work", 2, "Deep Reserves",
           "tolerate missing 1 daily meal before suffering hunger penalties.", requires="sturdy",
           effects=(Effect("deep_reserves", 1),), icon="body/spartan"),
    Talent("restful_sleep", "work", 2, "Restful Sleep",
           "recover +1 additional HP for every 8 hours of unbroken rest.", requires="sturdy",
           effects=(Effect("rest_heal_bonus", 1),), icon="body/sleeping-bag"),
    Talent("field_cook", "work", 3, "Field Cook",
           "efficient camp cook: field campfires burn for 6 hours instead of 4.",
           requires="deep_reserves",
           effects=(Effect("field_cook", 1),), icon="body/cook"),
    Talent("hardened", "work", 3, "Hardened",
           "tough worker frame: clear non-lethal damage after 16 hours of unbroken rest instead of 24.",
           requires="restful_sleep",
           effects=(Effect("hardened", 1),), icon="body/strong"),

    # --- WIS: Field Medicine, Animals & Scouting ---
    Talent("observant", "work", 1, "Observant", "+1 Wisdom.",
           effects=(Effect("attr", 1, "wisdom"),), icon="head/gaze"),
    Talent("field_medic", "work", 2, "Field Medic",
           "+2 to First Aid and Stabilize checks outside of combat.", requires="observant",
           effects=(Effect("field_medic_bonus", 2),), icon="body/arm-bandage"),
    Talent("beast_whisperer", "work", 2, "Beast Whisperer",
           "skilled with pack animals: grants +1 herd capacity to the group.", requires="observant",
           effects=(Effect("herd_capacity_bonus", 1),), icon="map/ox"),
    Talent("triage", "work", 3, "Triage",
           "field medic triage: everyone in your group recovers +1 extra HP per 8 hours of rest.",
           requires="field_medic",
           effects=(Effect("triage", 1),), icon="body/knee-bandage"),
    Talent("pathfinder", "work", 3, "Pathfinder",
           "skilled trail scout: reduces travel time by 10% on paths and roads.",
           requires="beast_whisperer",
           effects=(Effect("pathfinder", 1),), icon="gui/path-distance"),

    # ================================================================== #
    # racial -- race-gated; the level is racial_level (sum of the other    #
    # tracks on a scale).                                                 #
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
    Talent("thick_hide", "racial", 1, "Thick Hide", "+1 AC.", race="Ox",
           effects=(Effect("ac", 1),), icon="body/surrounded-shield"),
    Talent("gore_charge", "racial", 1, "Gore Charge",
           "after walking 4+ squares this turn, a melee hit also throws the target 2 squares "
           "straight back.", race="Ox",
           effects=(Effect("gore_charge", 2),), icon="action/back-forth"),
    Talent("deep_miner", "racial", 1, "Deep Miner",
           "at home under the mountain: the odds of a pack finding your crew while gathering "
           "at the Mine are 25% lower.", race="Dwarf",
           effects=(Effect("deep_miner", 0.25),), icon="action/mining"),
    Talent("grudge", "racial", 1, "Grudge",
           "a dwarf never forgets: +1 to hit anyone who has hurt you this fight.", race="Dwarf",
           effects=(Effect("grudge", 1),), icon="head/dwarf-face"),
    Talent("self_repair", "racial", 1, "Self-Repair",
           "your works mend themselves: heal 1 HP after every fight you survive.", race="Automaton",
           effects=(Effect("post_combat_heal", 1),), icon="gui/auto-repair"),
    Talent("iron_plating", "racial", 1, "Iron Plating", "+1 AC.", race="Automaton",
           effects=(Effect("ac", 1),), icon="head/metal-golem-head"),
    Talent("cavalry_charge", "racial", 2, "Cavalry Charge",
           "your rider strikes with your weight behind the blow: +2 to hit for whoever rides "
           "you, on a turn you have moved.", requires="centaur_mount", race="Centaur",
           effects=(Effect("cavalry_charge", 2),), icon="body/mounted-knight"),
    Talent("lift_rider", "racial", 1, "Lift Rider",
           "1 point: swing an adjacent Small or Medium ally onto your back, awake or fallen, "
           "and carry them as you move.", race="Centaur",
           effects=(Effect("lift_rider", 1),), icon="body/lift"),
    Talent("twilight_sight", "racial", 1, "Twilight Sight",
           "elven eyes in the dusk: in the dark you see 6 m as if the ground were lit.", race="Elf",
           effects=(Effect("twilight_sight", 4),), icon="head/elf-ear"),
    Talent("light_step", "racial", 1, "Light Step", "+1 square of Speed.", race="Elf",
           effects=(Effect("speed", 1),), icon="action/sprint"),
    Talent("blood_frenzy", "racial", 1, "Blood Frenzy",
           "+2 damage on melee attacks against a target below half its HP.", race="Gnoll",
           effects=(Effect("blood_frenzy", 2),), icon="body/enrage"),
    Talent("bloodscent", "racial", 1, "Bloodscent",
           "you smell the wounded: you know where every foe below half its HP is within "
           "6 squares, seen or not.", race="Gnoll",
           effects=(Effect("bloodscent", 6),), icon="head/nose-side"),
    Talent("arcane_curiosity", "racial", 2, "Arcane Curiosity",
           "+1 square of range with non-melee spells.", requires="gnome_magic_excitement",
           race="Gnome", effects=(Effect("spell_range", 1),), icon="hat/pointy-hat"),
    Talent("underfoot", "racial", 1, "Underfoot",
           "+2 AC against attackers of Large size or bigger.", race="Gnome",
           effects=(Effect("underfoot", 2),), icon="action/dodging"),
    Talent("small_appetite", "racial", 1, "Small Appetite",
           "a goblin lives on scraps: you need a meal only every other day.", race="Goblin",
           effects=(Effect("small_appetite", 1),), icon="head/goblin-head"),
    Talent("under_the_whip", "racial", 1, "Under the Whip",
           "+1 to hit while an ally of a higher combat level than yours stands within "
           "6 squares.", race="Goblin",
           effects=(Effect("under_the_whip", 1),), icon="body/slavery-whip"),
    Talent("stone_endurance", "racial", 1, "Stone's Endurance",
           "once per fight, the first blow that hurts you deals 1d4 + your Constitution "
           "modifier less.", race="Goliath",
           effects=(Effect("stone_endurance", 4),), icon="body/stone-bust"),
    Talent("arena_born", "racial", 1, "Arena Born",
           "+1 to hit in arena bouts.", race="Goliath",
           effects=(Effect("arena_born", 1),), icon="body/medallist"),
    Talent("sticky_tongue", "racial", 2, "Sticky Tongue",
           "a Lash that hits also grabs the target and reels it 1 square in.",
           requires="tongue", race="Grippli",
           effects=(Effect("sticky_tongue", 1),), icon="action/pull"),
    Talent("frog_leap", "racial", 1, "Frog Leap",
           "+2 squares on every Jump.", race="Grippli",
           effects=(Effect("jump_reach", 2),), icon="action/jump-across"),
    Talent("brave", "racial", 1, "Brave", "+2 Mental Defense.", race="Halfling",
           effects=(Effect("mental_defense", 2),), icon="body/ninja-heroic-stance"),
    Talent("second_breakfast", "racial", 1, "Second Breakfast",
           "recover +1 additional HP for every 8 hours of unbroken rest.", race="Halfling",
           effects=(Effect("rest_heal_bonus", 1),), icon="body/cook"),
    Talent("quartermaster", "racial", 1, "Quartermaster",
           "an orderly camp: +2 on the daily cohesion roll of an overextended group you lead.",
           race="Hobgoblin",
           effects=(Effect("quartermaster", 2),), icon="body/guards"),
    Talent("hold_the_line", "racial", 1, "Hold the Line",
           "while you Defend, every ally adjacent to you has +1 AC.", race="Hobgoblin",
           effects=(Effect("hold_the_line", 1),), icon="body/pikeman"),
    Talent("ambush_predator", "racial", 1, "Ambush Predator",
           "+2 to hit a foe that has not yet had a turn this fight.", race="Lizardfolk",
           effects=(Effect("ambush_predator", 2),), icon="head/lizardman"),
    Talent("tail_sweep", "racial", 1, "Tail Sweep",
           "2 points: your tail sweeps two adjacent foes -- an unarmed strike and a Push "
           "on each.", race="Lizardfolk",
           effects=(Effect("tail_sweep", 1),), icon="action/slalom"),
    Talent("polyglot", "racial", 2, "Polyglot",
           "+2 to progress rolls when studying a foreign language.", requires="cosmopolitan",
           race="Human", effects=(Effect("language_study", 2),), icon="action/conversation"),
    Talent("parley", "racial", 1, "Parley",
           "+1 when you Persuade, Bluff or Intimidate in the talk before a fight.", race="Human",
           effects=(Effect("parley", 1),), icon="action/discussion"),
    Talent("eye_for_detail", "racial", 1, "Eye for Detail",
           "+1 on all Assess and enemy observation checks.", race="Kenku",
           effects=(Effect("assess_bonus", 1),), icon="head/kenku-head"),
    Talent("mimic_voices", "racial", 1, "Mimic Voices",
           "+1 on performance rolls when playing on the tavern stage.", race="Kenku",
           effects=(Effect("tavern_perform_bonus", 1),), icon="action/sing"),
    Talent("trap_master", "racial", 2, "Trap Master",
           "plant your traps up to 3 squares away when a fight begins.",
           requires="kobold_trapper", race="Kobold",
           effects=(Effect("trap_range", 3),), icon="body/sinking-trap"),
    Talent("trap_salvage", "racial", 1, "Trap Salvage",
           "after a won fight, your traps that never sprang go back into your pack.",
           race="Kobold", effects=(Effect("trap_salvage", 1),), icon="action/snatch"),
    Talent("savage_attacks", "racial", 1, "Savage Attacks",
           "a critical hit rolls one more weapon die.", race="Orc",
           effects=(Effect("savage_attacks", 1),), icon="head/orc-head"),
    Talent("war_cry", "racial", 1, "War Cry", "+1 to Demoralize checks.", race="Orc",
           effects=(Effect("demoralize_bonus", 1),), icon="action/screaming"),
    Talent("tiny_target", "racial", 1, "Tiny Target",
           "+2 AC against ranged and thrown attacks.", race="Sprite",
           effects=(Effect("tiny_target", 2),), icon="action/evasion"),
    Talent("pixie_dust", "racial", 1, "Pixie Dust",
           "1 point: an adjacent ally takes wing through the end of their next turn.",
           race="Sprite", effects=(Effect("pixie_dust", 1),), icon="action/flying-fox"),
    Talent("bountiful_harvest", "racial", 2, "Bountiful Harvest",
           "you bloom twice at dawn, and your fruit heals 1d4 HP to whoever eats it.",
           requires="fruitful", race="Treefolk",
           effects=(Effect("bountiful_harvest", 1),), icon="head/sprout"),
    Talent("thornskin", "racial", 1, "Thornskin",
           "whoever hits you in melee takes 1 damage.", race="Treefolk",
           effects=(Effect("thornskin", 1),), icon="body/spiked-wall"),
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
    Talent("dragon", "racial", 1, "Dragon",
           "dragon blood runs in you: your hide hardens into scales (+1 AC).",
           race="Dragon",
           effects=(Effect("ac", 1),), icon="head/horned-reptile"),
    Talent("dragon_breath", "racial", 2, "Dragon Breath",
           "2 points: breathe a cone 3 squares deep (1, 3 and 5 wide); one attack roll "
           "against everyone in it, allies too, 2d6 damage on each hit.",
           requires="dragon", race="Dragon",
           effects=(Effect("dragon_breath", 1),), icon="body/fire-dash"),
    Talent("sweeping_claws", "racial", 2, "Sweeping Claws",
           "your claws sweep in wide lethal arcs: you can use Cleave while unarmed, "
           "striking two adjacent foes with your natural weapon.",
           requires="dragon", race="Dragon",
           effects=(Effect("unarmed_cleave", 1),), icon="body/deadly-strike"),
    Talent("draconic_wings", "racial", 3, "Draconic Wings",
           "massive leathery wings carry you aloft: you gain flight (move freely across "
           "3D terrain and pits, immune to fall damage) and your speed increases to 12 squares.",
           requires="dragon", race="Dragon",
           effects=(Effect("flies", 1), Effect("fly_speed", 12)), icon="action/flying-fox"),
    Talent("death_grip", "racial", 1, "Death Grip",
           "your cold dead hands lock like iron: +2 to grab checks.",
           race="Zombie",
           effects=(Effect("grab_bonus", 2),), icon="action/grab"),
    Talent("zombie_bite", "racial", 2, "Zombie Bite",
           "sink your teeth into held flesh: an attack targeting a grappled foe; "
           "+2 to hit, deals 1d8 + Strength damage.",
           requires="death_grip", race="Zombie",
           effects=(Effect("zombie_bite", 1),), icon="head/snake-bite"),

    # ================================================================== #
    # magic -- school-agnostic spellcasting mastery                      #
    # ================================================================== #
    Talent("arcane_mind", "magic", 1, "Arcane Mind", "+1 Intelligence.",
           effects=(Effect("attr", 1, "intelligence"),), icon="head/brain"),
    Talent("spell_focus", "magic", 2, "Spell Focus",
           "+1 to hit with spell attacks.", requires="arcane_mind",
           effects=(Effect("spell_to_hit", 1),), icon="action/targeting"),
    Talent("destructive_casting", "magic", 2, "Destructive Casting",
           "+1 damage with damaging spells.", requires="arcane_mind",
           effects=(Effect("spell_damage", 1),), icon="body/fire-dash"),
    Talent("blessed_hands", "magic", 2, "Blessed Hands",
           "+1 HP restored with healing spells.", requires="arcane_mind",
           effects=(Effect("spell_heal", 1),), icon="head/spiked-halo"),
    Talent("focused_will", "magic", 2, "Focused Will",
           "+1 Mental Defense.", requires="arcane_mind",
           effects=(Effect("mental_defense", 1),), icon="action/meditation"),
    Talent("far_cast", "magic", 3, "Far Cast",
           "+1 square of range with non-melee spells.", requires="spell_focus",
           effects=(Effect("spell_range", 1),), icon="action/ricochet"),
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

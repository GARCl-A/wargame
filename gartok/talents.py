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
    natural_dice      Unit.natural_weapon (+N dice)    --
    natural_claws     Unit.natural_weapon (Claws)      --
    infernal_presence battle.Battle._apply_presence    --
    size_up           Unit._derive_size (+N sizes)     --
    natural_trait     Unit.natural_weapon              weapon trait id
    spin_web          actions.SpinWeb                  --
    venom             actions.base._envenom            poison id
    swim_reach        actions.Swim (+squares per swim) --
    ranged_reach      Combatant.attack_range/throw     --
    crossbow_damage   Combatant.damage_roll            --
    crossbow_crit_range actions.base._resolve_hit      --
    crossbow_ambush   actions.base._resolve_hit (Brutal vs off-guard) --
    throw_resupply    actions.Throw (draws the same weapon from the pack) --
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
    off_guard_defense     actions.base._off_guard_penalty  --
    bleeding_claws    actions.base._claw               --
    night_prowler     vocations.ambush_mult            --
    open_market       economy.haggle_voice             --
    demoralize_bonus  actions.combat.Demoralize        --
    demoralize_no_language actions.combat.Demoralize   --
    gruesome_takedown actions.base._resolve_hit        --
    demoralized_target_damage actions.base._resolve_hit --
    demoralized_target_brutal actions.base._resolve_hit --
    assess_bonus      intel._roll                      --
    assess_active_bonus intel.assess                   --
    full_intel_to_hit Combatant.attack_mods            --
    full_intel_brutal actions.base._resolve_hit        --
    grab_bonus        actions.combat.Grab              --
    push_bonus        actions.combat.Push              --
    off_guard_finesse_damage actions.base._resolve_hit     --
    free_hand_damage  Combatant.damage_roll            --
    free_step         actions.FreeStep                 --
    defend_mental_defense Combatant.mental_defense     --
    demoralize_ally_initiative actions.combat.execute_demoralize --
    demoralize_rally  actions.combat.execute_demoralize --
    demoralize_morale actions.combat.execute_demoralize --
    ally_takedown_demoralize actions.base._check_gruesome_takedown --
    full_intel_crit_range actions.base._resolve_hit    --
    flies             Combatant.flies                  --
    fly_speed         Unit._derive_speed               --
    grudge / ambush_predator / under_the_whip / arena_born / cavalry_charge
                      Combatant.racial_hit_mods         --
    underfoot / tiny_target  Combatant.ac_vs            --
    hold_the_line     actions.base._held_line          --
    blood_frenzy / thornskin / stone_endurance / gore_charge
                      actions.base._resolve_hit        --
    run_down_hit      Combatant.attack_mods            --
    run_down_damage   Combatant.damage_roll            --
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
    morale            morale.start_value (the fight's starting morale) --

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

`name` / `effect` are player-facing and read from the catalog (`name.talent.<id>`,
`desc.talent.<id>`); `id` and field names are English identifiers.
"""

from dataclasses import dataclass

from . import i18n

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
    requires: str | None = None      # id of a talent that must be taken first (the one the tree hangs it under)
    also: str | None = None          # a second talent it needs: a hybrid of two branches
    race: str | tuple | None = None  # racial track: only offered to this race, or these (None = any)
    icon: str = ""                   # "<category>/<name>" under assets/icons/ (level screen)
    effects: tuple = ()              # Effect(...) contributions -- see the module docstring
    school: str | None = None        # magic track: the school this node belongs to
    granted: bool = False            # magic root: held while the school is held, never picked
    redundant_with: str | None = None  # an Ability flag that already does what this does: not offered to that race

    @property
    def needs(self):
        """Every talent that must be held first."""
        return tuple(x for x in (self.requires, self.also) if x)

    @property
    def name(self):
        return i18n.name("talent", self.id)

    @property
    def effect(self):
        """The player-facing one-liner."""
        return i18n.desc("talent", self.id)

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
    Talent("strong", "combat", 1, effects=(Effect("attr", 1, "strength"),), icon="action/muscle-up"),
    Talent("sure_strike", "combat", 2, requires="strong",
           effects=(Effect("to_hit", 1, "strength"),), icon="action/targeting"),
    Talent("blind_strike", "combat", 3, requires="sure_strike",
           effects=(Effect("obscured_penalty_relief", 1),), icon="head/blindfold"),
    Talent("heavy_hand", "combat", 2, requires="strong",
           effects=(Effect("melee_damage", 1),), icon="action/crush"),
    Talent("wrestler", "combat", 3, requires="heavy_hand",
           effects=(Effect("push_bonus", 1), Effect("grab_bonus", 1)), icon="action/grab"),

    Talent("agile", "combat", 1, effects=(Effect("attr", 1, "dexterity"),), icon="action/acrobatic"),
    Talent("long_reach", "combat", 2, requires="agile",
           effects=(Effect("ranged_reach", 1),), icon="action/bowman"),
    Talent("ready_hand", "combat", 3, requires="long_reach", also="strong",
           effects=(Effect("throw_resupply", 1),), icon="action/switch-weapon"),
    Talent("deadeye", "combat", 2, requires="agile",
           effects=(Effect("to_hit", 1, "dexterity"),), icon="action/ricochet"),
    Talent("heavy_bolts", "combat", 3, requires="deadeye",
           effects=(Effect("crossbow_damage", 2),), icon="action/crush"),
    Talent("keen_bolts", "combat", 3, requires="deadeye",
           effects=(Effect("crossbow_crit_range", 1),), icon="action/targeting"),
    Talent("ambush_shot", "combat", 4, requires="heavy_bolts", also="keen_bolts",
           effects=(Effect("crossbow_ambush", 1),), icon="action/backstab"),
    Talent("duelist", "combat", 2, requires="agile",
           effects=(Effect("free_hand_damage", 1),), icon="action/riposte"),
    Talent("fleet", "combat", 3, requires="deadeye",
           effects=(Effect("speed", 1),), icon="action/leapfrog"),
    Talent("free_step", "combat", 4, requires="fleet",
           effects=(Effect("free_step", 1),), icon="action/slalom"),
    Talent("nimble_skirmisher", "combat", 3, requires="deadeye",
           effects=(Effect("off_guard_finesse_damage", 2),), icon="action/backstab"),

    Talent("tough", "combat", 1, effects=(Effect("attr", 1, "constitution"),), icon="body/bell-shield"),
    Talent("hardy", "combat", 2, requires="tough",
           effects=(Effect("hp_per_hd", 1),), icon="body/heart-inside"),
    Talent("recovery", "combat", 3, requires="hardy",
           effects=(Effect("post_combat_heal", 1),), icon="body/arm-bandage"),
    Talent("bulwark", "combat", 2, requires="tough",
           effects=(Effect("ac", 1),), icon="body/surrounded-shield"),
    Talent("armor_bearer", "combat", 3, requires="bulwark",
           effects=(Effect("armor_weight_relief", 6),), icon="body/master-of-arms"),

    Talent("alert", "combat", 1, effects=(Effect("attr", 1, "wisdom"),), icon="head/gaze"),
    Talent("quick_wits", "combat", 2, requires="alert",
           effects=(Effect("initiative", 2),), icon="head/quick-man"),
    Talent("peripheral_vision", "combat", 3, requires="quick_wits",
           effects=(Effect("off_guard_defense", 1),), icon="head/one-eyed"),
    Talent("iron_will", "combat", 2, requires="alert",
           effects=(Effect("mental_defense", 2),), icon="action/meditation"),
    Talent("iron_stance", "combat", 3, requires="iron_will",
           effects=(Effect("defend_mental_defense", 2),), icon="body/bell-shield"),

    Talent("imposing", "combat", 1, effects=(Effect("attr", 1, "charisma"),), icon="action/shouting"),
    Talent("menacing", "combat", 2, requires="imposing",
           effects=(Effect("demoralize_bonus", 2),), icon="action/shouting"),
    Talent("gruesome_takedown", "combat", 2, requires="imposing",
           effects=(Effect("gruesome_takedown", 1),), icon="body/deadly-strike"),
    Talent("cull_the_broken", "combat", 3, requires="menacing",
           effects=(Effect("demoralized_target_damage", 2),), icon="action/boot-stomp"),
    Talent("merciless", "combat", 4, requires="cull_the_broken",
           effects=(Effect("demoralized_target_brutal", 1),), icon="action/boot-stomp"),
    Talent("wordless_menace", "combat", 3, requires="menacing",
           effects=(Effect("demoralize_no_language", 1),), icon="action/shouting",
           redundant_with="demoralize_ignores_language"),
    Talent("inspiring_shout", "combat", 3, requires="gruesome_takedown",
           effects=(Effect("demoralize_ally_initiative", 1), Effect("demoralize_rally", 1)), icon="action/shouting"),
    Talent("dread_voice", "combat", 3, requires="menacing",
           effects=(Effect("demoralize_morale", 1),), icon="action/screaming"),
    Talent("grim_chorus", "combat", 3, requires="gruesome_takedown",
           effects=(Effect("ally_takedown_demoralize", 1),), icon="action/boot-stomp"),

    Talent("tactical_mind", "combat", 1, effects=(Effect("attr", 1, "intelligence"),), icon="head/brain"),
    Talent("analytical_eye", "combat", 2, requires="tactical_mind",
           effects=(Effect("assess_bonus", 2), Effect("assess_active_bonus", 2)), icon="head/spectacles"),
    Talent("exploit_weakness", "combat", 3, requires="analytical_eye",
           effects=(Effect("full_intel_to_hit", 2),), icon="gui/convergence-target"),
    Talent("anatomist", "combat", 3, requires="analytical_eye",
           effects=(Effect("full_intel_crit_range", 1),), icon="head/spectacles"),
    Talent("surgical_strike", "combat", 4, requires="exploit_weakness",
           effects=(Effect("full_intel_brutal", 1),), icon="action/targeting"),

    # ================================================================== #
    # work -- 6 attribute roots, 5 talents each = 30 talents             #
    # ================================================================== #
    # --- STR: Heavy Labor & Carrying ---
    Talent("brawny", "work", 1, effects=(Effect("attr", 1, "strength"),), icon="body/lift"),
    Talent("piecework", "work", 2, requires="brawny",
           effects=(Effect("coin_gain", COIN_BONUS),), icon="action/profit"),
    Talent("brisk_hands", "work", 2, requires="brawny",
           effects=(Effect("activity_speed", ACTIVITY_SPEEDUP),), icon="action/sprint"),
    Talent("steady_pace", "work", 3, requires="brisk_hands",
           effects=(Effect("work_rest", 1),), icon="body/knee-bandage"),
    Talent("heavy_haul", "work", 3, requires="piecework",
           effects=(Effect("haul_buffer", 6),), icon="body/weight-lifting-up"),

    # --- CHA: Market, Recruitment & Tavern ---
    Talent("charismatic", "work", 1, effects=(Effect("attr", 1, "charisma"),), icon="action/talk"),
    Talent("negotiator", "work", 2, requires="charismatic",
           effects=(Effect("haggle_cha", 1),), icon="action/shaking-hands"),
    Talent("fixer", "work", 2, requires="charismatic",
           effects=(Effect("recruit_cha", 1),), icon="action/convince"),
    Talent("provisioner", "work", 3, requires="negotiator",
           effects=(Effect("food_haggle", 1),), icon="action/trade"),
    Talent("troubadour", "work", 3, requires="fixer",
           effects=(Effect("tavern_perform_bonus", 1),), icon="action/sing"),

    # --- INT: Crafting & Lore ---
    Talent("clever", "work", 1, effects=(Effect("attr", 1, "intelligence"),), icon="head/brain"),
    Talent("linguist", "work", 2, requires="clever",
           effects=(Effect("language_study", 2),), icon="head/spectacles"),
    Talent("crafter", "work", 2, requires="clever",
           effects=(Effect("craft_bonus", 1),), icon="action/crafting"),
    Talent("apothecary", "work", 3, requires="crafter",
           effects=(), icon="action/pouring-chalice"),
    Talent("blacksmith", "work", 3, requires="crafter",
           effects=(), icon="body/blacksmith"),

    # --- DEX: Woodworking, Leather & Wagons ---
    Talent("nimble_fingers", "work", 1, effects=(Effect("attr", 1, "dexterity"),), icon="action/button-finger"),
    Talent("woodcarver", "work", 2, requires="nimble_fingers",
           effects=(Effect("woodcarver_bonus", 1),), icon="action/stone-crafting"),
    Talent("skinner", "work", 2, requires="nimble_fingers",
           effects=(Effect("skinner_bonus", 1),), icon="map/hide"),
    Talent("fletcher", "work", 3, requires="woodcarver",
           effects=(Effect("fletcher", 1),), icon="action/bowman"),
    Talent("wheelwright", "work", 3, requires="woodcarver",
           effects=(Effect("wheelwright", 1),), icon="gui/auto-repair"),

    # --- CON: Field Endurance & Recovery ---
    Talent("sturdy", "work", 1, effects=(Effect("attr", 1, "constitution"),), icon="body/heart-inside"),
    Talent("deep_reserves", "work", 2, requires="sturdy",
           effects=(Effect("deep_reserves", 1),), icon="body/spartan"),
    Talent("restful_sleep", "work", 2, requires="sturdy",
           effects=(Effect("rest_heal_bonus", 1),), icon="body/sleeping-bag"),
    Talent("field_cook", "work", 3, requires="deep_reserves",
           effects=(Effect("field_cook", 1),), icon="body/cook"),
    Talent("hardened", "work", 3, requires="restful_sleep",
           effects=(Effect("hardened", 1),), icon="body/strong"),

    # --- WIS: Field Medicine, Animals & Scouting ---
    Talent("observant", "work", 1, effects=(Effect("attr", 1, "wisdom"),), icon="head/gaze"),
    Talent("field_medic", "work", 2, requires="observant",
           effects=(Effect("field_medic_bonus", 2),), icon="body/arm-bandage"),
    Talent("beast_whisperer", "work", 2, requires="observant",
           effects=(Effect("herd_capacity_bonus", 1),), icon="map/ox"),
    Talent("triage", "work", 3, requires="field_medic",
           effects=(Effect("triage", 1),), icon="body/knee-bandage"),
    Talent("pathfinder", "work", 3, requires="beast_whisperer",
           effects=(Effect("pathfinder", 1),), icon="gui/path-distance"),

    # ================================================================== #
    # racial -- race-gated; the level is racial_level (sum of the other    #
    # tracks on a scale).                                                 #
    # ================================================================== #
    Talent("tongue", "racial", 1, race="Grippli",
           effects=(Effect("melee_reach", 1),), icon="action/swallow"),
    Talent("webbed_feet", "racial", 1, race="Grippli", effects=(Effect("swim_reach", 1),), icon="action/drowning"),
    Talent("fruitful", "racial", 1, race="Treefolk",
           effects=(Effect("fruitful", 1),), icon="action/fruiting"),
    Talent("cosmopolitan", "racial", 1, race="Human",
           effects=(Effect("align_distance_reduction", 1),), icon="action/shaking-hands"),
    Talent("halfling_luck", "racial", 1, race="Halfling",
           effects=(Effect("halfling_luck", 1),), icon="action/juggler"),
    Talent("woodland_scout", "racial", 1, race="Elf",
           effects=(Effect("woodland_scout", 1),), icon="action/run"),
    Talent("intimidating_presence", "racial", 1, race=("Orc", "Ogre"),
           effects=(Effect("intimidating_presence", 1),), icon="action/shouting"),
    Talent("swarm_logic", "racial", 1, race="Goblin",
           effects=(Effect("swarm_logic", 1),), icon="action/hive-mind"),
    Talent("tireless_worker", "racial", 1, race="Automaton",
           effects=(Effect("activity_speed", 0.25),), icon="gui/auto-repair"),
    Talent("centaur_mount", "racial", 1, race="Centaur",
           effects=(Effect("centaur_mount", 1),), icon="body/cavalry"),
    Talent("giant_grip", "racial", 1, race=("Goliath", "Ogre"),
           effects=(Effect("giant_grip", 1),), icon="action/muscle-up"),
    Talent("mighty_shove", "racial", 1, race="Ogre",
           effects=(Effect("mighty_shove", 1),), icon="action/back-forth"),
    Talent("phalanx", "racial", 1, race="Hobgoblin",
           effects=(Effect("phalanx", 1),), icon="body/surrounded-shield"),
    Talent("organic_harvester", "racial", 1, race="Lizardfolk",
           effects=(Effect("organic_harvester", 1),), icon="action/eating"),
    Talent("corpse_eater", "racial", 1, race="Gnoll",
           effects=(Effect("corpse_eater", 1),), icon="action/swallow"),
    Talent("gnome_magic_excitement", "racial", 1, race="Gnome",
           effects=(), icon="hat/magic-hat"),
    Talent("kenku_faith_initiate", "racial", 1, race="Kenku",
           effects=(), icon="action/prayer"),
    Talent("sprite_nature_initiate", "racial", 1, race="Sprite",
           effects=(), icon="hat/flower-hat"),
    Talent("dwarf_crafting", "racial", 1, race="Dwarf",
           effects=(), icon="body/blacksmith"),
    Talent("kobold_trapper", "racial", 1, race="Kobold",
           effects=(), icon="body/sinking-trap"),
    Talent("aurochs_might", "racial", 1, race="Ox", effects=(Effect("speed", 5), Effect("melee_damage", 3)),
           icon="action/crush"),
    Talent("thick_hide", "racial", 1, race="Ox",
           effects=(Effect("ac", 1),), icon="body/surrounded-shield"),
    Talent("gore_charge", "racial", 1, race="Ox",
           effects=(Effect("gore_charge", 2),), icon="action/back-forth"),
    Talent("deep_miner", "racial", 1, race="Dwarf",
           effects=(Effect("deep_miner", 0.25),), icon="action/mining"),
    Talent("grudge", "racial", 1, race="Dwarf",
           effects=(Effect("grudge", 1),), icon="head/dwarf-face"),
    Talent("self_repair", "racial", 1, race="Automaton",
           effects=(Effect("post_combat_heal", 1),), icon="gui/auto-repair"),
    Talent("iron_plating", "racial", 1, race="Automaton",
           effects=(Effect("ac", 1),), icon="head/metal-golem-head"),
    Talent("cavalry_charge", "racial", 2, requires="centaur_mount", race="Centaur",
           effects=(Effect("cavalry_charge", 2),), icon="body/mounted-knight"),
    Talent("lift_rider", "racial", 1, race="Centaur",
           effects=(Effect("lift_rider", 1),), icon="body/lift"),
    Talent("run_down", "racial", 1, race="Centaur",
           effects=(Effect("run_down_hit", 1), Effect("run_down_damage", 2)), icon="action/boot-stomp"),
    Talent("twilight_sight", "racial", 1, race="Elf",
           effects=(Effect("twilight_sight", 4),), icon="head/elf-ear"),
    Talent("light_step", "racial", 1, race="Elf",
           effects=(Effect("speed", 1),), icon="action/sprint"),
    Talent("blood_frenzy", "racial", 1, race="Gnoll",
           effects=(Effect("blood_frenzy", 2),), icon="body/enrage"),
    Talent("bloodscent", "racial", 1, race="Gnoll",
           effects=(Effect("bloodscent", 6),), icon="head/nose-side"),
    Talent("arcane_curiosity", "racial", 2, requires="gnome_magic_excitement",
           race="Gnome", effects=(Effect("spell_range", 1),), icon="hat/pointy-hat"),
    Talent("underfoot", "racial", 1, race="Gnome",
           effects=(Effect("underfoot", 2),), icon="action/dodging"),
    Talent("small_appetite", "racial", 1, race="Goblin",
           effects=(Effect("small_appetite", 1),), icon="head/goblin-head"),
    Talent("under_the_whip", "racial", 1, race="Goblin",
           effects=(Effect("under_the_whip", 1),), icon="body/slavery-whip"),
    Talent("stone_endurance", "racial", 1, race="Goliath",
           effects=(Effect("stone_endurance", 4),), icon="body/stone-bust"),
    Talent("arena_born", "racial", 1, race="Goliath",
           effects=(Effect("arena_born", 1),), icon="body/medallist"),
    Talent("sticky_tongue", "racial", 2, requires="tongue", race="Grippli",
           effects=(Effect("sticky_tongue", 1),), icon="action/pull"),
    Talent("frog_leap", "racial", 1, race="Grippli",
           effects=(Effect("jump_reach", 2),), icon="action/jump-across"),
    Talent("brave", "racial", 1, race="Halfling",
           effects=(Effect("mental_defense", 2),), icon="body/ninja-heroic-stance"),
    Talent("second_breakfast", "racial", 1, race="Halfling",
           effects=(Effect("rest_heal_bonus", 1),), icon="body/cook"),
    Talent("quartermaster", "racial", 1, race="Hobgoblin",
           effects=(Effect("quartermaster", 2),), icon="body/guards"),
    Talent("hold_the_line", "racial", 1, race="Hobgoblin",
           effects=(Effect("hold_the_line", 1),), icon="body/pikeman"),
    Talent("ambush_predator", "racial", 1, race="Lizardfolk",
           effects=(Effect("ambush_predator", 2),), icon="head/lizardman"),
    Talent("tail_sweep", "racial", 1, race="Lizardfolk",
           effects=(Effect("tail_sweep", 1),), icon="action/slalom"),
    Talent("polyglot", "racial", 2, requires="cosmopolitan",
           race="Human", effects=(Effect("language_study", 2),), icon="action/conversation"),
    Talent("parley", "racial", 1, race="Human",
           effects=(Effect("parley", 1),), icon="action/discussion"),
    Talent("eye_for_detail", "racial", 1, race="Kenku",
           effects=(Effect("assess_bonus", 2),), icon="head/kenku-head"),
    Talent("mimic_voices", "racial", 1, race="Kenku",
           effects=(Effect("tavern_perform_bonus", 1),), icon="action/sing"),
    Talent("razor_claws", "racial", 1, race="Catfolk",
           effects=(Effect("bleeding_claws", 1),), icon="action/tearing"),
    Talent("night_prowler", "racial", 1, race="Catfolk",
           effects=(Effect("night_prowler", 1),), icon="body/shadow-follower"),
    Talent("open_market", "racial", 1, race="Catfolk",
           effects=(Effect("open_market", 1),), icon="action/trade"),
    Talent("trap_master", "racial", 2, requires="kobold_trapper", race="Kobold",
           effects=(Effect("trap_range", 3),), icon="body/sinking-trap"),
    Talent("trap_salvage", "racial", 1, race="Kobold", effects=(Effect("trap_salvage", 1),), icon="action/snatch"),
    Talent("savage_attacks", "racial", 1, race="Orc",
           effects=(Effect("savage_attacks", 1),), icon="head/orc-head"),
    Talent("war_cry", "racial", 1, race="Orc",
           effects=(Effect("demoralize_bonus", 1),), icon="action/screaming"),
    Talent("tiny_target", "racial", 1, race="Sprite",
           effects=(Effect("tiny_target", 2),), icon="action/evasion"),
    Talent("pixie_dust", "racial", 1, race="Sprite", effects=(Effect("pixie_dust", 1),), icon="action/flying-fox"),
    Talent("bountiful_harvest", "racial", 2, requires="fruitful", race="Treefolk",
           effects=(Effect("bountiful_harvest", 1),), icon="head/sprout"),
    Talent("thornskin", "racial", 1, race="Treefolk",
           effects=(Effect("thornskin", 1),), icon="body/spiked-wall"),
    Talent("rending_bite", "racial", 1, race="Wolf",
           effects=(Effect("natural_dice", 1),), icon="action/eating"),
    Talent("elder_skeleton", "racial", 1, race="Skeleton",
           effects=(Effect("attr", 4, "intelligence"), Effect("attr", 4, "charisma")),
           icon="hat/crowned-skull"),
    Talent("skeleton_faith_initiate", "racial", 1, race="Skeleton",
           effects=(), icon="action/prayer"),
    Talent("deft_bones", "racial", 1, race="Skeleton",
           effects=(Effect("natural_trait", 1, "finesse"),), icon="action/sprint"),
    Talent("giant_growth", "racial", 1, race="Giant Spider",
           effects=(Effect("size_up", 1),), icon="body/cavalry"),
    Talent("titanic_growth", "racial", 2, requires="giant_growth", race="Giant Spider",
           effects=(Effect("size_up", 1),), icon="body/cavalry"),
    Talent("spin_web", "racial", 1, race="Giant Spider",
           effects=(Effect("spin_web", 1),), icon="action/hive-mind"),
    Talent("serpent_growth", "racial", 1, race="Snake",
           effects=(Effect("size_up", 1),), icon="body/cavalry"),
    Talent("great_serpent", "racial", 2, requires="serpent_growth", race="Snake",
           effects=(Effect("size_up", 1),), icon="body/cavalry"),
    Talent("snake_venom", "racial", 1, race="Snake",
           effects=(Effect("venom", 1, "snake_venom"),), icon="head/snake-bite"),
    Talent("dire_growth", "racial", 1, race="Wolf",
           effects=(Effect("size_up", 1),), icon="body/cavalry"),
    Talent("dragon", "racial", 1, race="Dragon",
           effects=(Effect("ac", 1),), icon="head/horned-reptile"),
    Talent("dragon_breath", "racial", 2, requires="dragon", race="Dragon",
           effects=(Effect("dragon_breath", 1),), icon="body/fire-dash"),
    Talent("sweeping_claws", "racial", 2, requires="dragon", race="Dragon",
           effects=(Effect("natural_trait", 1, "cleave"),), icon="body/deadly-strike"),
    Talent("draconic_wings", "racial", 3, requires="dragon", race="Dragon",
           effects=(Effect("flies", 1), Effect("fly_speed", 12)), icon="action/flying-fox"),
    Talent("death_grip", "racial", 1, race="Zombie",
           effects=(Effect("grab_bonus", 2),), icon="action/grab"),
    Talent("demon_claws", "racial", 1, race="Demon",
           effects=(Effect("natural_claws", 1),), icon="action/tearing"),
    Talent("cleaving_claws", "racial", 2, requires="demon_claws", race="Demon",
           effects=(Effect("natural_trait", 1, "cleave"),), icon="body/deadly-strike"),
    Talent("infernal_wings", "racial", 3, requires="demon_claws", race="Demon",
           effects=(Effect("flies", 1), Effect("fly_speed", 12)), icon="action/flying-fox"),
    Talent("infernal_presence", "racial", 1, race="Demon",
           effects=(Effect("infernal_presence", 1),), icon="action/screaming"),
    Talent("zombie_bite", "racial", 2, requires="death_grip", race="Zombie",
           effects=(Effect("zombie_bite", 1),), icon="head/snake-bite"),

    # ================================================================== #
    # magic -- school-agnostic spellcasting mastery                      #
    # ================================================================== #
    Talent("arcane_mind", "magic", 1, effects=(Effect("attr", 1, "intelligence"),), icon="head/brain"),
    Talent("spell_focus", "magic", 2, requires="arcane_mind",
           effects=(Effect("spell_to_hit", 1),), icon="action/targeting"),
    Talent("destructive_casting", "magic", 2, requires="arcane_mind",
           effects=(Effect("spell_damage", 1),), icon="body/fire-dash"),
    Talent("blessed_hands", "magic", 2, requires="arcane_mind",
           effects=(Effect("spell_heal", 1),), icon="head/spiked-halo"),
    Talent("focused_will", "magic", 2, requires="arcane_mind",
           effects=(Effect("mental_defense", 1),), icon="action/meditation"),
    Talent("far_cast", "magic", 3, requires="spell_focus",
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


def stats(talent_ids, channel):
    """The `stat` of every effect the given talents have on `channel` (for the channels whose stat
    names what is granted, such as a weapon trait)."""
    return [e.stat for tid in talent_ids if (t := TALENTS.get(tid)) is not None
            for e in t.effects if e.channel == channel and e.amount]


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

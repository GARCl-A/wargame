"""The builds the race study fights with: coherent archetypes (a weapon, a talent line, and for the
casters a school and a spell set; the armour is bought by the game's rule, see `_arm`) and random kits, applied to any race at level 0 or 5.

A build is a recipe, not a character: the attributes are still 3d6 (or a fixed 10 in the `fixed` control), so
what a race brings stays the race's. `make_unit` reports what could not be applied (a weapon the body cannot
wield, armour too heavy) instead of faking it; the study logs it.
"""

from __future__ import annotations

from typing import NamedTuple

from gartok import data, economy, items, magic, outfit, talents
from gartok.unit import Unit

MAP_SLUG = "capture-the-flag-the-gamers"      # the Ribbit Brothers' map, fought as plain elimination

LEVELS = (0, 5)
L5_MELEE = {"combat": 5, "work": 5, "magic": 0}          # combat + work + magic = 10, racial 5 (level 5)
L5_CASTER = {"combat": 3, "work": 4, "magic": 3}
L5_RACIAL = 5


AUTO = "auto"       # the armour the game's rule buys with what the weapon and the rest leave of the level's budget
SHIELD = "Dwarf Shield"


class Build(NamedTuple):
    id: str
    label: str
    weapons: tuple          # plain names, the first the body can field (`sized_weapons` cuts each for the body)
    armor: str | None
    shield: str | None
    combat: tuple           # talent priority, in prerequisite order; the picks it leaves are random
    work: tuple = ()        # the work-track roots, then random
    sources: tuple = ()
    spells0: tuple = ()     # known at level 0
    spells5: tuple = ()     # known at level 5
    magic_talents: tuple = ()
    quiver: bool = False
    thrower: bool = False   # buys spares of its thrown weapon, as an archer buys Quivers
    armor_first: bool = False   # buys the armour, then the shield, then the weapon with what is left
    role: str = "melee"


FRONT = ("brawny", "sturdy", "nimble_fingers")
HEAVY = ("strong", "sure_strike", "heavy_hand", "tough", "hardy")
CASTER_MAGIC = ("arcane_mind", "spell_focus", "destructive_casting")
CASTER_WORK = ("nimble_fingers", "sturdy", "clever")

BUILDS = {b.id: b for b in (
    Build("sword_board", "Sword and shield", ("Sword",), AUTO, SHIELD, HEAVY, FRONT),
    Build("axe_board", "Axe and shield", ("Axe",), AUTO, SHIELD, HEAVY, FRONT),
    Build("broadsword", "Broadsword: two-handed", ("Broadsword",), AUTO, None, HEAVY, FRONT),
    Build("glaive", "Glaive: reach", ("Glaive",), AUTO, None, HEAVY, FRONT),
    Build("fortress", "Armour, then shield, then the weapon", ("Hammer",), AUTO, SHIELD,
          ("tough", "bulwark", "armor_bearer", "strong", "heavy_hand"), ("sturdy", "brawny"), armor_first=True),
    Build("rapier_duelist", "Rapier, free hand", ("Rapier",), AUTO, None,
          ("agile", "duelist", "deadeye", "nimble_skirmisher", "fleet"), ("brawny", "nimble_fingers", "sturdy")),
    Build("dagger_skirmisher", "Dagger: flanks for the sneak attack", ("Dagger",), AUTO, None,
          ("agile", "nimble_skirmisher", "deadeye", "fleet", "duelist"), ("brawny", "nimble_fingers", "sturdy")),
    Build("sage_archer", "Longbow: initiative", ("Longbow",), AUTO, None,
          ("agile", "long_reach", "deadeye", "alert", "quick_wits"), ("brawny", "nimble_fingers", "observant"),
          quiver=True, role="ranged"),
    Build("archer", "Longbow: two random talents", ("Longbow",), AUTO, None,
          ("agile", "long_reach", "deadeye"), ("brawny", "nimble_fingers"), quiver=True, role="ranged"),
    Build("intimidator", "Demoralize, then cull or take down", ("Sword",), AUTO, None,
          ("imposing", "menacing", "wordless_menace", "cull_the_broken", "dread_voice"), ("brawny", "charismatic", "sturdy", "nimble_fingers")),
    Build("commander", "Shouts the line on", ("Hatchet",), AUTO, SHIELD,
          ("imposing", "menacing", "wordless_menace", "gruesome_takedown", "inspiring_shout"),
          ("brawny", "charismatic", "sturdy", "nimble_fingers", "observant")),
    Build("analyst", "Assess: reads the foe", ("Rapier",), AUTO, None,
          ("tactical_mind", "combat_analysis", "sharp_analysis", "anatomist", "exploit_weakness"),
          ("brawny", "sturdy", "clever", "nimble_fingers")),
    Build("smart_miner", "Pick: Armor Pierce, reads the foe for crits", ("Pick",), AUTO, None,
          ("tactical_mind", "sharp_analysis", "anatomist", "strong", "heavy_hand"),
          ("brawny", "sturdy", "clever", "nimble_fingers")),
    Build("nature_caster", "Nature: Water Jet, Roots, Sleep", ("Quarterstaff",), AUTO, None,
          ("tactical_mind", "combat_analysis", "sharp_analysis"), CASTER_WORK, ("nature",),
          (), ("water_jet", "grasping_roots", "sleep"), CASTER_MAGIC, role="caster"),
    Build("blood_caster", "Blood: Hex, Dragonfire, Magic Missile, Sleep", ("Dagger",), AUTO, None,
          ("tactical_mind", "combat_analysis", "sharp_analysis"), CASTER_WORK, ("blood",),
          (), ("hex", "dragonfire", "magic_missile", "sleep"), CASTER_MAGIC, role="caster"),
    Build("faith_caster", "Faith: Healing Touch, Spare the Dying, Sleep, Magic Missile", ("Quarterstaff",), AUTO, None,
          ("tough", "bulwark", "hardy"), CASTER_WORK, ("faith",),
          (), ("healing_touch", "spare_the_dying", "sleep", "magic_missile"),
          ("arcane_mind", "spell_focus", "blessed_hands"), role="caster"),
    Build("thrower", "Shortspear thrown: spares in the pack", ("Shortspear",), AUTO, None,
          ("agile", "strong", "long_reach", "ready_hand", "deadeye"), ("brawny", "nimble_fingers", "sturdy", "observant"),
          thrower=True, role="ranged"),
    Build("crossbow", "Crossbow and quiver", ("Crossbow",), AUTO, None,
          ("agile", "long_reach", "heavy_bolts", "keen_bolts", "deadeye"), ("brawny", "nimble_fingers", "sturdy", "observant"),
          quiver=True, role="ranged"),
)}

# The talent choices inside a build, each a full combat priority: fought as mirrors of the same build, not as builds.
VARIANTS = {
    # Free Step needs Fleet, so a pair holding it holds both
    "rapier_duelist": {f"{x} + {y}": ("agile", "duelist", "deadeye", x, y)
                       for x, y in (("nimble_skirmisher", "fleet"), ("fleet", "free_step"))},
    "dagger_skirmisher": {f"{x} + {y}": ("agile", "nimble_skirmisher", "deadeye", x, y)
                          for x, y in (("fleet", "duelist"), ("fleet", "free_step"))},
    "intimidator": {k: ("imposing", "menacing", "wordless_menace", k, "strong")
                    for k in ("cull_the_broken", "gruesome_takedown")},
}
COMBAT_IDS = frozenset(t.id for t in talents.TREE["combat"])
TALKERS = ("intimidator", "commander")   # the builds a player stacks languages on
# The builds whose weapon is a question, and the weapons it is asked over.
SWEEP_BUILDS = ("fortress", "intimidator", "commander", "analyst", "nature_caster", "blood_caster", "faith_caster")

PLAIN = Build("plain", "Sword, shield, no talent line (the base of the single-factor tests)", ("Sword",),
              "Chainmail", SHIELD, ())
BUILD_IDS = tuple(BUILDS)


def sweep_weapons(build_id, level):
    """The weapons a weapon sweep tries on `build_id`: the thrower's thrown ones, the melee ones for every other build, and the
    bows and crossbows too for the Commander (whose archers the author expects to do well)."""
    names = [w for w in CATALOG if affordable(w, level)]
    if build_id == "thrower":
        return [w for w in names if items.get(w).has_trait("thrown")]
    return [w for w in names if build_id == "commander" or not items.get(w).range]


def lookup(build_id):
    return BUILDS.get(build_id, PLAIN)


MELEE_REF = "sword_board"
RANDOM_KIT = "random"

TORCH = items.TORCH_ITEM


CATALOG = [d.name for d in items.weapons().values() if d.base is None]        # plain names; each body buys its own cut
ARMORS = sorted(d.name for d in items.armor().values() if d.base is None)
THROWN_SPARES = 8           # spares of the thrown weapon a thrower buys at most (the cap `tests/test_thrown_supply.py` measures)
EXTRA_QUIVERS = 2           # an archer buys a bow and one Quiver, then the armour, then up to this many more Quivers


def affordable(name, level):
    """Whether the level's budget pays for `name` at all (the rest of the kit is bought from what it leaves)."""
    return economy.buy_price(name) <= outfit.budget(level)


def exists(build_id, level):
    """A build exists at a level when the budget pays for its first weapon: it is that weapon that makes the build. (One that buys
    its weapon last, the Fortress, may still find the armour left nothing for it: it fights unarmed, and the study says so.)"""
    return build_id == RANDOM_KIT or affordable(lookup(build_id).weapons[0], level)


def builds_at(level):
    return [b for b in BUILD_IDS if exists(b, level) and any(fields(b, r[1], level) for r in data.RACES)]

LEVEL1_SPELLS = tuple(s.id for s in magic.SPELLS.values() if s.level == 1)
LEVEL0_SPELLS = tuple(s.id for s in magic.SPELLS.values() if s.level == 0 and s.id not in ("light_globe", "floating_disk"))


def level_plan(build_id, level):
    if level == 0:
        return {"combat": 0, "work": 0, "magic": 0}
    return L5_CASTER if build_id != RANDOM_KIT and lookup(build_id).role == "caster" else L5_MELEE


def _pick(unit, track, priority, rng, ban=(), notes=None):
    """Spend every pick of `track`: the priority list first (a talent whose prerequisite is not held yet waits for the
    next pass), then at random among the legal ones. A listed talent still missing while picks remain is noted."""
    progress = True
    while progress:
        progress = False
        for tid in priority:
            if unit.picks_available(track) > 0 and tid not in ban and tid not in unit.talents[track]:
                progress = bool(unit.choose_talent(track, tid)) or progress
    if notes is not None and unit.picks_available(track) > 0:
        notes += [f"talent {tid} not legal" for tid in priority if tid not in ban and tid not in unit.talents[track]]
    tree = talents.TREE[track]
    while unit.picks_available(track) > 0:
        picked = unit.talents[track]
        options = [t.id for t in tree if t.id not in picked and t.id not in ban and unit.offerable(track, t)
                   and t.for_race(unit.race["name"])]
        if not options or not unit.choose_talent(track, rng.choice(options)):
            break


def racial_options(race):
    """The racial talents a level-5 `race` can pick first."""
    unit = Unit("player")
    unit.set_race(race)
    unit.set_track_level("racial", L5_RACIAL)
    return [t.id for t in talents.racial_tree(race) if unit.offerable("racial", t) and t.for_race(race)]


def _spend_racial_and_work(unit, rng, drop_racial=False, work=(), racial=None):
    """Work picks: the build's attribute roots first, then at random; the racial pick is `racial` when the study forces one,
    else a random legal one (a race's nodes are not a build choice)."""
    for tid in work:
        if unit.picks_available("work") > 0:
            unit.choose_talent("work", tid)
    for track in ("work", "racial"):
        tree = talents.TREE[track] if track in talents.XP_TRACKS else talents.racial_tree(unit.race["name"])
        while unit.picks_available(track) > 0:
            options = [t.id for t in tree if unit.offerable(track, t) and t.for_race(unit.race["name"])]
            if not options:
                break
            if not unit.choose_talent(track, racial if track == "racial" and racial in options else rng.choice(options)):
                break
    if drop_racial:
        for tid in list(unit.talents["racial"]):
            unit.drop_talent("racial", tid)


def fix_body(unit):
    """The `fixed` control: every attribute 10 and every hit die at its average, so only the race differs."""
    for attr in data.ATTRIBUTES:
        unit.base_attributes[attr] = 10
    unit._apply_attributes()
    avg = (unit.race["hd"] + 1) // 2
    unit._hp_roll = avg
    unit._level_hp_rolls = [avg] * len(unit._level_hp_rolls)
    unit._derive_combat()


def sized_weapons(unit, weapons):
    """Each plain weapon cut for `unit`, shelf or not: the biggest size its body wields down to its own, the way the
    study measures a race's potential (a Centaur takes the Large one, a Goblin the Small, a body never a smaller one to save coin)."""
    order = data.SIZE_ORDER
    floor = min(order.index(unit.size), order.index("Medium"))
    return [v.name for w in weapons for v in reversed(items.sizes_of(w))
            if order.index(v.size) >= floor and unit.can_wield(v.name)]


def _cut(unit, name):
    """Armor or a shield `name` made for `unit`'s body (a Huge body wears the Large cut, the biggest there is)."""
    if name is None:
        return None
    size = data.SIZE_ORDER[min(data.SIZE_ORDER.index(unit.size), data.SIZE_ORDER.index("Large"))]
    return items.sized(name, size).name


def _buy_armor(unit, armor, left, notes, lit):
    if armor == AUTO:
        if lit:
            unit.equipped_offhand = items.TORCH_ITEM
        outfit._armor(unit, left)
        if lit:
            unit.equipped_offhand = None
    elif armor:
        armor = _cut(unit, armor)
        unit.give_to_armor(armor)
        if unit.equipped_armor != armor:
            notes.append("armour refused")
    unit._derive_combat()
    return left - (economy.buy_price(unit.equipped_armor) if unit.equipped_armor else 0)


def _buy_shield(unit, shield, left, notes):
    if economy.buy_price(shield) > left:
        notes.append("no shield")
        return left
    unit.give_to_offhand(shield)
    unit._derive_combat()
    if unit.encumbered:
        unit.equipped_offhand = None
        unit._derive_combat()
        notes.append("no shield")
        return left
    return left - economy.buy_price(shield)


def _arm(unit, weapons, armor, shield, quiver, notes, level=0, spares=0, armor_first=False):
    """Buy the kit with the level's budget, in this order: the weapon, the first Quiver of a bow, the armour the game's rule
    picks from what is left, the archer's extra Quivers, the shield. Each later item takes what the earlier ones leave and
    stops at the copper or the load. `armor_first` turns it round: the armour with the whole budget, the shield, and the weapon
    from the rest (a two-handed one gives the shield back)."""
    left = outfit.budget(level)
    unit.equipped_weapon = None
    weapons, shield = sized_weapons(unit, weapons), _cut(unit, shield)
    if armor_first:
        left = _buy_armor(unit, armor, left, notes, lit=False)
        if shield:
            left = _buy_shield(unit, shield, left, notes)
    held = None
    shielded = bool(armor_first and shield and unit.equipped_offhand == shield)
    for w in weapons:
        refund = economy.buy_price(shield) if shielded and items.get(w).hands > 1 else 0
        if not unit.can_wield(w) or economy.buy_price(w) > left + refund:
            continue
        unit.equipped_weapon = None
        unit.give_to_hand(w)
        unit._derive_combat()
        if armor_first and unit.encumbered:
            unit.equipped_weapon = None
            unit._derive_combat()
            continue
        held = w
        break
    if held is None:                                      # the budget bought the armour and left no weapon: fists
        unit.equipped_weapon = None
        notes.append("unarmed")
        unit._derive_combat()
        return
    if shielded and unit.equipped_offhand != shield:        # a two-handed weapon frees the hand: the shield is sold back
        unit.equipped_offhand = None
        left += economy.buy_price(shield)
        notes.append("shield given back")
    left -= economy.buy_price(held)
    if quiver and not unit.has_item(items.AMMO_ITEM):
        unit.give_to_pack(items.AMMO_ITEM)
        left -= economy.buy_price(items.AMMO_ITEM)
    unit._derive_combat()
    if not armor_first:
        lit = unit.equipped_offhand is None and items.get(unit.equipped_weapon).hands == 1     # the light `light_squad` may hand it
        left = _buy_armor(unit, armor, left, notes, lit)
    if quiver:
        for _ in range(EXTRA_QUIVERS):
            if economy.buy_price(items.AMMO_ITEM) > left:
                break
            unit.give_to_pack(items.AMMO_ITEM)
            unit._derive_combat()
            if unit.encumbered:
                unit.remove_named(items.AMMO_ITEM)
                unit._derive_combat()
                break
            left -= economy.buy_price(items.AMMO_ITEM)
    for _ in range(spares):
        if economy.buy_price(held) > left:
            break
        unit.give_to_pack(held)
        unit._derive_combat()
        if unit.encumbered:
            unit.remove_named(held)
            unit._derive_combat()
            break
        left -= economy.buy_price(held)
    if shield and not armor_first and items.get(held).hands == 1:
        _buy_shield(unit, shield, left, notes)


def _cast(unit, build, level, notes):
    """The school and the spells. At level 0 nobody learns: only a race that starts with magic (the Gnome, nature) keeps what it
    has, and any other caster is left out of the study there (`fields`)."""
    if not level:
        if build.role == "caster" and not unit.spells_known:
            notes.append("no spell")
        return
    for src in build.sources:
        unit.add_magic_source(src)
    unit.spells_known = [s for s in build.spells5 if magic.casts(unit, magic.SPELLS[s])]


def fields(build_id, race, level):
    """Whether `race` can field `build_id` at `level`: a caster at level 0 only if the race starts with its school's magic."""
    if build_id == RANDOM_KIT:
        return True
    build = lookup(build_id)
    return bool(level or build.role != "caster" or (race == "Gnome" and "nature" in build.sources))


def make_unit(team, race, build_id, level, rng, *, fixed=False, drop_racial=False, over=None):
    """`(unit, notes)`: a level-`level` fighter of `race` built as `build_id` (or a random kit).

    `over` changes one factor of the build for the single-factor tests: `weapon`, `armor` ("none" strips it),
    `shield` ("none" strips it), `combat` (a whole talent priority, the variants), `force` / `ban` (a combat talent),
    `drop_spell`, `spares`."""
    over = over or {}
    unit = Unit(team)
    unit.set_race(race)
    notes = []
    plan = level_plan(build_id, level)
    unit.set_kit(None, None)
    if level:
        for track, lv in plan.items():
            if lv:
                unit.set_track_level(track, lv)
        unit.set_track_level("racial", L5_RACIAL)
    if build_id == RANDOM_KIT:
        _random_kit(unit, level, rng, notes, drop_racial, fixed)
    else:
        build = lookup(build_id)
        if "weapon" in over:
            build = build._replace(weapons=(over["weapon"],), quiver=bool(items.get(over["weapon"]).range))
        build = build._replace(armor=AUTO if build.armor else None)
        if "combat" in over:
            build = build._replace(combat=tuple(over["combat"]))
        if "armor" in over:
            build = build._replace(armor=None if over["armor"] == "none" else over["armor"])
        if "shield" in over:
            build = build._replace(shield=None if over["shield"] == "none" else over["shield"])
        if "drop_spell" in over:
            build = build._replace(spells5=tuple(x for x in build.spells5 if x != over["drop_spell"]))
        ban = tuple(over.get("ban", ()))
        _pick(unit, "combat", tuple(over.get("force", ())) + build.combat, rng, ban, notes)
        if plan["magic"]:
            _pick(unit, "magic", tuple(over.get("force", ())) + build.magic_talents, rng, ban, notes)
        _spend_racial_and_work(unit, rng, drop_racial or over.get("drop_racial", False), build.work, over.get("racial"))
        _cast(unit, build, level, notes)
        if fixed:
            fix_body(unit)
        _arm(unit, build.weapons, build.armor, build.shield, build.quiver, notes, level,
             over.get("spares", THROWN_SPARES if build.thrower else 0), build.armor_first)
    unit.hp = unit.hp_max
    _learn_languages(unit, build_id, rng)
    return unit, notes


def _learn_languages(unit, build_id, rng):
    """A player building for intimidation learns more tongues: Draconic (a quest dictionary) and three at random."""
    if build_id in TALKERS:
        for lang in ["Draconic", *rng.sample([l for l in data.LANGUAGES if l not in unit.languages and l != "Draconic"], 3)]:
            if lang not in unit.languages:
                unit.languages.append(lang)


def _random_kit(unit, level, rng, notes, drop_racial=False, fixed=False):
    caster = rng.random() < 0.25
    plan = L5_CASTER if (caster and level) else L5_MELEE
    if caster and level and unit.magic_level != plan["magic"]:
        unit.set_track_level("combat", plan["combat"])
        unit.set_track_level("work", plan["work"])
        unit.set_track_level("magic", plan["magic"])
        unit.set_track_level("racial", L5_RACIAL)
    if level:
        _pick(unit, "combat", (), rng)
        if caster:
            _pick(unit, "magic", (), rng)
        _spend_racial_and_work(unit, rng, drop_racial)
    if caster:
        src = rng.choice(magic.SOURCES)
        unit.add_magic_source(src)
        pool = [s.id for s in magic.SPELLS.values() if magic.casts(unit, s) and s.level <= (1 if level else 0)
                and s.id not in ("light_globe", "floating_disk")]
        unit.spells_known = rng.sample(pool, min(len(pool), rng.randint(2, 4)))
    weapon = rng.choice([w for w in CATALOG if sized_weapons(unit, (w,)) and affordable(w, level)] or ["Dagger"])
    shield = SHIELD if items.get(weapon).hands == 1 and rng.random() < 0.5 else None
    quiver = bool(items.get(weapon).range)
    if fixed:
        fix_body(unit)
    _arm(unit, (weapon,), AUTO, shield, quiver, notes, level)


def sees_in_the_dark(unit):
    return max(unit.ability.darkvision, int(unit.talent_bonus("twilight_sight"))) > 0


def light_squad(squad):
    """The band's torch-bearer, once the three are built (the game only lights the enemy band): nobody if the whole squad sees in
    the dark or one already carries a light, else the first with a free off hand, a Duelist last: it pays for the torch with
    its free-hand bonus, one of the build's weaknesses in a dark map."""
    if all(sees_in_the_dark(u) for u in squad) or any(u.equipped_offhand in (items.TORCH_ITEM, items.LANTERN_ITEM) for u in squad):
        return
    free = [u for u in squad if u.equipped_offhand is None
            and (u.equipped_weapon is None or items.get(u.equipped_weapon).hands == 1)]
    for u in sorted(free, key=outfit._keeps_hand_free)[:1]:
        u.equipped_offhand = items.TORCH_ITEM
        u._derive_combat()

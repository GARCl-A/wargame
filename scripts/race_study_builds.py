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


# The work tree's roots are +1 to an attribute: each build takes the three that serve its fight, in order.
WORK_ROOTS = {
    "sword_board": ("brawny", "sturdy", "nimble_fingers"),
    "axe_bruiser": ("brawny", "sturdy", "nimble_fingers"),
    "greatsword": ("brawny", "sturdy", "nimble_fingers"),
    "glaive_reach": ("brawny", "nimble_fingers", "sturdy"),
    "fortress": ("sturdy", "brawny", "nimble_fingers"),
    "rapier_duelist": ("nimble_fingers", "sturdy", "brawny"),
    "dagger_skirmisher": ("nimble_fingers", "sturdy", "brawny"),
    "spear_line": ("brawny", "nimble_fingers", "sturdy"),
    "longbow": ("nimble_fingers", "sturdy", "brawny"),
    "shortbow": ("nimble_fingers", "sturdy", "brawny"),
    "crossbow": ("nimble_fingers", "sturdy", "brawny"),
    "intimidator": ("charismatic", "brawny", "sturdy"),
    "commander": ("charismatic", "brawny", "sturdy"),
    "analyst": ("clever", "nimble_fingers", "sturdy"),
    "smart_miner": ("clever", "brawny", "sturdy"),
    "sentinel": ("sturdy", "brawny", "observant"),
    "battlemage": ("brawny", "clever", "sturdy", "nimble_fingers"),
}
for _id in ("nature_striker", "nature_control", "blood_striker", "blood_hexer", "faith_support", "faith_striker"):
    WORK_ROOTS[_id] = ("clever", "sturdy", "nimble_fingers")


class Build(NamedTuple):
    id: str
    label: str
    weapons: tuple          # first one the body can wield
    armor: str | None
    shield: str | None
    combat: tuple           # talent priority
    sources: tuple = ()
    spells0: tuple = ()     # known at level 0
    spells5: tuple = ()     # known at level 5
    magic_talents: tuple = ()
    quiver: bool = False
    role: str = "melee"


SHIELD = "Dwarf Shield"
CASTER_COMBAT = ("tough", "hardy", "agile", "alert", "tactical_mind")
CASTER_MAGIC = ("arcane_mind", "spell_focus", "destructive_casting", "far_cast")

BUILDS = {b.id: b for b in (
    Build("sword_board", "Sword and shield: strong and tough", ("Sword",), "Chainmail", SHIELD,
          ("strong", "tough", "hardy", "bulwark", "sure_strike")),
    Build("axe_bruiser", "Axe: heavy hitter", ("Axe", "Hatchet"), "Brigandine", None,
          ("strong", "heavy_hand", "sure_strike", "tough", "hardy")),
    Build("greatsword", "Broadsword: two-handed", ("Broadsword", "Sword"), "Chainmail", None,
          ("strong", "heavy_hand", "sure_strike", "blind_strike", "tough")),
    Build("glaive_reach", "Glaive: reach", ("Glaive", "Shortspear"), "Studded Leather", None,
          ("strong", "agile", "heavy_hand", "sure_strike", "tough")),
    Build("fortress", "Hammer and shield: the wall", ("Hammer", "Club"), "Plate Armor", SHIELD,
          ("tough", "bulwark", "armor_bearer", "hardy", "strong")),
    Build("rapier_duelist", "Rapier: agile finesse", ("Rapier", "Dagger"), "Leather Jerkin", None,
          ("agile", "deadeye", "nimble_skirmisher", "fleet", "tough")),
    Build("dagger_skirmisher", "Dagger: fast skirmisher", ("Dagger",), "Studded Leather", None,
          ("agile", "deadeye", "fleet", "nimble_skirmisher", "tough")),
    Build("spear_line", "Shortspear and shield: the line", ("Shortspear",), "Studded Leather", SHIELD,
          ("strong", "agile", "tough", "sure_strike", "bulwark")),
    Build("longbow", "Longbow and quiver: the archer", ("Longbow",), "Studded Leather", None,
          ("agile", "deadeye", "long_reach", "fleet", "nimble_skirmisher"), quiver=True, role="ranged"),
    Build("shortbow", "Shortbow and quiver: the light archer", ("Shortbow",), "Leather Jerkin", None,
          ("agile", "deadeye", "fleet", "tough", "nimble_skirmisher"), quiver=True, role="ranged"),
    Build("crossbow", "Light crossbow and quiver: the heavy shot", ("Light Crossbow",), "Brigandine", None,
          ("agile", "deadeye", "strong", "tough", "hardy"), quiver=True, role="ranged"),
    Build("intimidator", "Sword: Demoralize and cull", ("Sword",), "Chainmail", None,
          ("imposing", "menacing", "cull_the_broken", "strong", "tough")),
    Build("commander", "Hatchet, shield: shouts the line on", ("Hatchet", "Axe"), "Studded Leather", SHIELD,
          ("imposing", "gruesome_takedown", "inspiring_shout", "tough", "strong")),
    Build("analyst", "Rapier: reads the foe", ("Rapier", "Dagger"), "Studded Leather", None,
          ("tactical_mind", "sharp_analysis", "combat_analysis", "exploit_weakness", "anatomist")),
    Build("smart_miner", "Pick: Armor Pierce, reads the foe for crits", ("Pick", "Axe"), "Chainmail", None,
          ("strong", "sure_strike", "tactical_mind", "sharp_analysis", "anatomist")),
    Build("sentinel", "Sword and shield: alert and iron-willed", ("Sword",), "Chainmail", SHIELD,
          ("alert", "iron_will", "iron_stance", "tough", "hardy")),
    Build("nature_striker", "Nature: Magic Missile, Water Jet, Sleep", ("Quarterstaff", "Dagger"), "Leather Jerkin", None,
          CASTER_COMBAT, ("nature",), ("magic_missile", "grasping_roots"),
          ("magic_missile", "water_jet", "sleep", "grasping_roots"), CASTER_MAGIC, role="caster"),
    Build("nature_control", "Nature: Roots, Sleep, Magic Missile", ("Quarterstaff", "Dagger"), "Leather Jerkin", None,
          CASTER_COMBAT, ("nature",), ("grasping_roots", "magic_missile"),
          ("grasping_roots", "sleep", "magic_missile", "water_jet"), CASTER_MAGIC, role="caster"),
    Build("blood_striker", "Blood: Dragonfire, Magic Missile, Hex", ("Dagger", "Quarterstaff"), "Leather Jerkin", None,
          CASTER_COMBAT, ("blood",), ("magic_missile", "hex"),
          ("dragonfire", "magic_missile", "hex", "sleep"), CASTER_MAGIC, role="caster"),
    Build("blood_hexer", "Blood: Hex, Sleep, Magic Missile", ("Dagger", "Quarterstaff"), "Leather Jerkin", None,
          CASTER_COMBAT, ("blood",), ("hex", "magic_missile"),
          ("hex", "sleep", "magic_missile", "dragonfire"), CASTER_MAGIC, role="caster"),
    Build("faith_support", "Faith: Healing Touch, Sleep, Magic Missile", ("Quarterstaff", "Hammer"), "Studded Leather", None,
          CASTER_COMBAT, ("faith",), ("magic_missile", "spare_the_dying"),
          ("healing_touch", "sleep", "magic_missile", "spare_the_dying"), CASTER_MAGIC, role="caster"),
    Build("faith_striker", "Faith: Magic Missile, Sleep, Healing Touch", ("Hammer", "Quarterstaff"), "Chainmail", None,
          CASTER_COMBAT, ("faith",), ("magic_missile", "spare_the_dying"),
          ("magic_missile", "sleep", "healing_touch"), CASTER_MAGIC, role="caster"),
    Build("battlemage", "Sword, blood: Hex, Dragonfire, Magic Missile", ("Sword",), "Chainmail", None,
          ("strong", "tough", "agile", "hardy", "sure_strike"), ("blood",), ("magic_missile", "hex"),
          ("magic_missile", "hex", "dragonfire"), CASTER_MAGIC, role="caster"),
)}

PLAIN = Build("plain", "Sword, shield, no talent line (the base of the single-factor tests)", ("Sword",),
              "Chainmail", SHIELD, ())
BUILD_IDS = tuple(BUILDS)


def lookup(build_id):
    return BUILDS.get(build_id, PLAIN)


MELEE_REF = "sword_board"
CASTER_REF = "nature_striker"
RANGED_REF = "longbow"
RANDOM_KIT = "random"

TORCH = items.TORCH_ITEM


def _catalog_weapons():
    return [d.name for d in items.weapons().values()
            if d.size not in (items.WeaponSize.LARGE, items.WeaponSize.HUGE)]


CATALOG = _catalog_weapons()
ARMORS = sorted(items.armor())
LEVEL1_SPELLS = tuple(s.id for s in magic.SPELLS.values() if s.level == 1)
LEVEL0_SPELLS = tuple(s.id for s in magic.SPELLS.values() if s.level == 0 and s.id not in ("light_globe", "floating_disk"))


def level_plan(build_id, level):
    if level == 0:
        return {"combat": 0, "work": 0, "magic": 0}
    return L5_CASTER if build_id != RANDOM_KIT and lookup(build_id).role == "caster" else L5_MELEE


def _pick(unit, track, priority, rng, ban=()):
    """Spend every pick of `track`: the priority list first, then at random among the legal ones."""
    for tid in priority:
        if unit.picks_available(track) > 0 and tid not in ban:
            unit.choose_talent(track, tid)
    tree = talents.TREE[track]
    while unit.picks_available(track) > 0:
        picked = unit.talents[track]
        options = [t.id for t in tree if t.id not in picked and t.id not in ban and unit.offerable(track, t)
                   and t.for_race(unit.race["name"])]
        if not options or not unit.choose_talent(track, rng.choice(options)):
            break


def _spend_racial_and_work(unit, rng, drop_racial=False, work=()):
    """Work picks: the build's attribute roots first, then at random; racial picks in tree order (a race's nodes
    are not a build choice)."""
    for tid in work:
        if unit.picks_available("work") > 0:
            unit.choose_talent("work", tid)
    for track in ("work", "racial"):
        tree = talents.TREE[track] if track in talents.XP_TRACKS else talents.racial_tree(unit.race["name"])
        while unit.picks_available(track) > 0:
            options = [t.id for t in tree if unit.offerable(track, t) and t.for_race(unit.race["name"])]
            if not options:
                break
            if not unit.choose_talent(track, options[0] if track == "racial" else rng.choice(options)):
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


AUTO = "auto"       # the armour the game's rule buys with what the weapon and the rest leave of the level's budget


def _arm(unit, weapons, armor, shield, quiver, notes, level=0):
    held = next((w for w in weapons if unit.can_wield(w)), None)
    if held is None:
        notes.append("no weapon")
        held = "Dagger"
    unit.equipped_weapon = None
    unit.give_to_hand(held)
    if shield and items.get(held).hands == 1:
        unit.give_to_offhand(shield)
    if quiver and not unit.has_item(items.AMMO_ITEM):
        unit.give_to_pack(items.AMMO_ITEM)
    unit._derive_combat()
    if armor == AUTO:
        spent = sum(economy.buy_price(x) for x in (unit.equipped_weapon, unit.equipped_offhand) if x and x != items.TORCH_ITEM)
        spent += economy.buy_price(items.AMMO_ITEM) if quiver else 0
        lit = unit.equipped_offhand is None and items.get(unit.equipped_weapon).hands == 1     # the light `light_squad` may hand it
        if lit:
            unit.equipped_offhand = items.TORCH_ITEM
        outfit._armor(unit, outfit.budget(level) - spent)
        if lit:
            unit.equipped_offhand = None
    elif armor:
        unit.give_to_armor(armor)
        if unit.equipped_armor != armor:
            notes.append("armour refused")
    unit._derive_combat()


def _cast(unit, build, level):
    for src in build.sources:
        unit.add_magic_source(src)
    known = build.spells5 if level else build.spells0
    unit.spells_known = [s for s in known if magic.casts(unit, magic.SPELLS[s])]


def make_unit(team, race, build_id, level, rng, *, fixed=False, drop_racial=False, over=None):
    """`(unit, notes)`: a level-`level` fighter of `race` built as `build_id` (or a random kit).

    `over` changes one factor of the build for the single-factor tests: `weapon`, `armor` ("none" strips it),
    `shield` ("none" strips it), `force` / `ban` (a combat talent), `drop_spell`, `ammo` (bolts carried, in
    quivers of 20)."""
    over = over or {}
    unit = Unit(team)
    unit.set_race(race)
    notes = []
    plan = level_plan(build_id, level)
    unit.set_kit("Dagger", None)
    if level:
        for track, lv in plan.items():
            if lv:
                unit.set_track_level(track, lv)
        unit.set_track_level("racial", L5_RACIAL)
    if build_id == RANDOM_KIT:
        _random_kit(unit, level, rng, notes, drop_racial)
    else:
        build = lookup(build_id)
        if "weapon" in over:
            build = build._replace(weapons=(over["weapon"],), quiver=bool(items.get(over["weapon"]).range))
        build = build._replace(armor=AUTO if build.armor else None)
        if "armor" in over:
            build = build._replace(armor=None if over["armor"] == "none" else over["armor"])
        if "shield" in over:
            build = build._replace(shield=None if over["shield"] == "none" else over["shield"])
        if "drop_spell" in over:
            build = build._replace(spells0=tuple(x for x in build.spells0 if x != over["drop_spell"]),
                                   spells5=tuple(x for x in build.spells5 if x != over["drop_spell"]))
        _pick(unit, "combat", tuple(over.get("force", ())) + tuple(build.combat), rng, ban=tuple(over.get("ban", ())))
        if plan["magic"]:
            _pick(unit, "magic", tuple(over.get("force", ())) + tuple(build.magic_talents), rng, ban=tuple(over.get("ban", ())))
        _spend_racial_and_work(unit, rng, drop_racial, WORK_ROOTS.get(build.id, ()))
        _cast(unit, build, level)
        _arm(unit, build.weapons, build.armor, build.shield, build.quiver, notes, level)
    if fixed:
        fix_body(unit)
    if over.get("ammo"):
        unit.give_to_pack(items.AMMO_ITEM)
        for _ in range(over["ammo"] // 20 - 1):
            unit.give_to_pack(items.AMMO_ITEM)
        unit.quiver_charges = over["ammo"]
    unit.hp = unit.hp_max
    return unit, notes


def _random_kit(unit, level, rng, notes, drop_racial=False):
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
    weapon = rng.choice([w for w in CATALOG if unit.can_wield(w)] or ["Dagger"])
    shield = SHIELD if items.get(weapon).hands == 1 and rng.random() < 0.5 else None
    quiver = bool(items.get(weapon).range)
    _arm(unit, (weapon,), AUTO, shield, quiver, notes, level)


def light_squad(squad):
    """A Torch in the first free off hand, the same for both sides (the game only lights the enemy band)."""
    held = [u for u in squad if u.equipped_offhand in (items.TORCH_ITEM, items.LANTERN_ITEM)]
    if held:
        return
    free = [u for u in squad if u.equipped_offhand is None
            and (u.equipped_weapon is None or items.get(u.equipped_weapon).hands == 1)]
    for u in sorted(free, key=lambda u: bool(u.talent_bonus("free_hand_damage")))[:1]:
        u.equipped_offhand = items.TORCH_ITEM
        u._derive_combat()

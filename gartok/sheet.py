"""A character's sheet as a plain dict (`unit_to_ch`), with no pygame: what the web's sheets and
cards read, and what `ui/sheet_card.py` paints for the Editor and the battle."""

from . import data, magic, weapon_traits


def _to_hit(u):
    """Base attack bonus and its attribute; a ranged weapon with no ammo is a STR melee."""
    if u.improvised:
        return u.mod_strength, "STR"
    return u.attack_bonus


def _weapon_line(u):
    if u.unarmed:
        n, faces = u.unarmed_damage
        return "unarmed", f"{n}d{faces} {u.mod_strength:+} (STR)", "melee"
    n, faces = (u.unarmed_damage if u.improvised else u.weapon["damage"])
    if u.improvised:
        return (f"{u.weapon_name} (no arrow -> improvised)",
                f"{n}d{faces} {u.mod_strength:+} (STR)", "melee")
    bonus = u.mod_strength if not u.ranged else 0
    dmg = f"{n}d{faces}" + (f" {bonus:+} (STR)" if bonus else "")
    hands = "2 hands" if u.weapon["hands"] == 2 else "1 hand"
    size_str = f"{u.weapon.get('size')} · " if u.weapon.get("size") and u.weapon.get("size") != "Medium" else ""
    if u.ranged:
        reach = f"{size_str}range {u.weapon['range']}  ·  {u.ammo} arrows  ·  {hands}"
    else:
        thrown = f"  ·  thrown {u.weapon['thrown']}" if u.weapon["thrown"] else ""
        reach = f"{size_str}melee  ·  {hands}{thrown}"
    return u.weapon_name, dmg, reach


_ATTRS = [("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
          ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma")]


def unit_to_ch(u):
    """Adapts a Unit or Combatant (`u`) into the plain dict every block
    painter below reads. `u` should be a `Combatant` when to-hit/ammo
    need battle context (see callers) -- a bare `Unit` works too since
    `Combatant` proxies the same attributes it doesn't override."""
    status = []
    if u.dying:
        status.append(f"dying {u.death_clock}/{data.DYING_TURNS}")
    elif u.stable:
        status.append("stable")
    elif u.broken:
        status.append("broken")
    elif u.fled:
        status.append("fled")
    elif u.dead:
        status.append("dead")
    elif u.hunger_level:
        status.append(u.hunger_label)
    if u.sick:
        status.append("sick")
    if u.poisoned:
        status.append(u.poison_label)
    tags = ["champion of the pit"] if getattr(u, "arena_title", False) else []

    wname, dmg, reach = _weapon_line(u)
    bab, src = _to_hit(u)
    tongue = None
    if u.has_tongue_weapon:
        tn, tf = u.tongue_weapon["damage"]
        tb = u.mod_strength + u.char.talent_bonus("melee_damage")
        tongue = (u.tongue_weapon_name,
                  f"{tn}d{tf}" + (f" {tb:+} (STR)" if tb else ""), u.tongue_reach)

    held = " + ".join(p for p in ("weapon" if u.weapon_hand else "",
                                  "torch" if u.torch_hand else "",
                                  "lantern" if u.lantern_hand else "") if p) or "empty"
    a = u.armor
    armor = (f"{u.armor_name}  ·  +{a['ac']} AC") if a else None
    pack = list(u.inventory)

    pen = u.hunger_attribute_penalty
    enc = -2 if getattr(u, "encumbered", False) else 0

    def eff(name):
        return getattr(u, name) + pen + (enc if name in ("strength", "dexterity") else 0)

    return {
        "name": u.name, "race": u.race["name"], "occ": u.occupation["name"],
        "align": u.alignment, "size": u.size, "age": u.age, "combat": f"N{u.combat_level}",
        "status": status, "tags": tags,
        "hp": (max(u.hp, 0), u.hp_max), "ac": u.ac, "md": u.mental_defense, "spd": u.speed,
        "init": f"{u.initiative_bonus():+}",
        "attrs": [(k, eff(name), getattr(u, f"mod_{name}"), eff(name) < getattr(u, name)) for k, name in _ATTRS],
        "weapon": {"nm": wname, "hit": f"d20 {bab:+} ({src})", "dmg": dmg, "tags": reach,
                  "crit": "crit 20, fumble 1",
                  "action": None if u.unarmed else weapon_traits.action_name(u.weapon)},
        "tongue": tongue,
        "gear": {"hands": held, "armor": armor, "pack": pack,
                "load": (u.load, u.carry_normal, u.carry_max), "copper": u.money},
        "langs": list(u.languages),
        "recipes": list(getattr(u, "recipes", []) or []),
        "magic": (list(u.magic_sources), [magic.SPELLS[s].name for s in u.spells_known if s in magic.SPELLS]),
        "ability": (u.ability.name, u.ability.effect),
        "unit": u,                    # kept for tooltip lookups (hp_breakdown, etc.)
    }

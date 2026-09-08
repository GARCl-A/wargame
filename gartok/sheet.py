"""Rendering a Unit as display text.

This used to be `Unit.ficha()` -- presentation logic living in the model. It now
takes a Unit and returns a list of lines; the UI decides fonts, wrapping and
placement.
"""

from . import data

_ATTR_LABELS = [
    ("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
    ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma"),
]


def _weapon_line(u):
    if u.unarmed:
        n, faces = u.unarmed_damage
        return f"Weapon: unarmed  {n}d{faces} (melee attack)"
    if u.improvised:
        n, faces = u.unarmed_damage
        return (f"Weapon: {u.weapon_name} NO ARROW -> improvised  "
                f"{n}d{faces} (melee)")
    reach = f" (range {u.weapon['range']})" if u.ranged else " (melee)"
    thrown = f"  thrown {u.weapon['thrown']}" if u.weapon["thrown"] else ""
    ammo = f"  arrows {u.ammo}" if u.needs_ammo else ""
    hands = "2 hands" if u.weapon["hands"] == 2 else "1 hand"
    n, faces = u.weapon["damage"]
    return f"Weapon: {u.weapon_name}  {n}d{faces}  [{hands}]" + reach + thrown + ammo


def _armor_line(u):
    a = u.armor
    if not a:
        return "Armor: (none)"
    parts = [f"+{a['ac']} AC"]
    if a["max_dex"] is not None:
        parts.append(f"DEX max +{a['max_dex']}")
    if a["speed"]:
        parts.append(f"-{a['speed']} speed")
    return f"Armor: {u.armor_name}  ({', '.join(parts)})"


def character_sheet(u):
    """Full unit sheet as a list of text lines (no newlines, no wrapping)."""
    held = " + ".join(x for x in ("weapon" if u.weapon_hand else "",
                                  "torch" if u.torch_hand else "") if x) or "nothing"
    hands_line = f"Hands: {held}" + (f"  ({u.free_hands} free)" if u.free_hands else "")
    inv = ", ".join(u.inventory) if u.inventory else "(empty)"
    if data.FIRST_AID_ITEM in u.inventory:
        inv = inv.replace(data.FIRST_AID_ITEM,
                          f"{data.FIRST_AID_ITEM} ({u.first_aid_charges} charges)")

    down = (f"   [DYING {u.death_clock}/{data.DYING_TURNS}]" if u.dying
            else "   [STABLE - unconscious]" if u.stable
            else "   [BROKEN - repair: INT vs DC 15]" if u.broken
            else "   [FLED the fight]" if u.fled
            else "   [DEAD]" if u.dead else "")
    stats = (f"HP {max(u.hp, 0)}/{u.hp_max}   AC {u.ac}   MD {u.mental_defense}   Speed {u.speed}"
             + (f"   takes {u.footprint}x{u.footprint}" if u.footprint > 1 else "")
             + ("   [demoralized]" if u.demoralized else "") + down)

    attr_pairs = [(lbl, getattr(u, name), getattr(u, f"mod_{name}"))
                  for lbl, name in _ATTR_LABELS]
    line_a = "   ".join(f"{lbl} {val} ({m:+})" for lbl, val, m in attr_pairs[:3])
    line_b = "   ".join(f"{lbl} {val} ({m:+})" for lbl, val, m in attr_pairs[3:])

    return [
        u.name,
        f"Alignment: {u.alignment}   Age: {u.age}   "
        f"Combat N{u.combat_level} ({u.combat_xp} XP)"
        + (f"   Work N{u.work_level} ({u.work_xp})" if u.work_xp or u.work_level else ""),
        stats,
        line_a,
        line_b,
        _weapon_line(u),
        hands_line,
        _armor_line(u),
        f"Inventory: {inv}",
        f"Load: {u.load} / normal {u.carry_normal} / high {u.carry_max}"
        + ("   OVERLOADED: -2 STR, -2 DEX, -1 speed" if u.encumbered else ""),
        f"Languages: {', '.join(u.languages)}"
        + ("  (mimics voices: Demoralize needs no language)" if u.ability.demoralize_ignores_language
           else "  (Demoralize needs a shared language)"),
        u.ability.desc,
    ]

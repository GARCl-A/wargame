"""Rendering a Unit as display text.

This used to be `Unit.ficha()` -- presentation logic living in the model. It now
takes a Unit and returns a list of lines; the UI decides fonts, wrapping and
placement. The attribute labels stay in Portuguese (FOR/DES/...), matching the
rest of the interface.
"""

from . import data

_ATTR_LABELS = [
    ("FOR", "strength"), ("DES", "dexterity"), ("CON", "constitution"),
    ("INT", "intelligence"), ("SAB", "wisdom"), ("CAR", "charisma"),
]


def _weapon_line(u):
    if u.unarmed:
        n, faces = u.unarmed_damage
        return f"Arma: desarmado  {n}d{faces} (ataque corpo-a-corpo)"
    if u.improvised:
        n, faces = u.unarmed_damage
        return (f"Arma: {u.weapon_name} SEM FLECHA -> improvisada  "
                f"{n}d{faces} (corpo-a-corpo)")
    reach = f" (alcance {u.weapon['range']})" if u.ranged else " (corpo-a-corpo)"
    thrown = f"  arremesso {u.weapon['thrown']}" if u.weapon["thrown"] else ""
    ammo = f"  flechas {u.ammo}" if u.needs_ammo else ""
    hands = "2 maos" if u.weapon["hands"] == 2 else "1 mao"
    n, faces = u.weapon["damage"]
    return f"Arma: {u.weapon_name}  {n}d{faces}  [{hands}]" + reach + thrown + ammo


def _armor_line(u):
    a = u.armor
    if not a:
        return "Armadura: (vazio)"
    parts = [f"+{a['ac']} CA"]
    if a["max_dex"] is not None:
        parts.append(f"DES max +{a['max_dex']}")
    if a["speed"]:
        parts.append(f"-{a['speed']} desloc")
    return f"Armadura: {u.armor_name}  ({', '.join(parts)})"


def character_sheet(u):
    """Full unit sheet as a list of text lines (no newlines, no wrapping)."""
    held = " + ".join(x for x in ("arma" if u.weapon_hand else "",
                                  "tocha" if u.torch_hand else "") if x) or "nada"
    hands_line = f"Maos: {held}" + (f"  ({u.free_hands} livre)" if u.free_hands else "")
    inv = ", ".join(u.inventory) if u.inventory else "(vazio)"
    if data.FIRST_AID_ITEM in u.inventory:
        inv = inv.replace(data.FIRST_AID_ITEM,
                          f"{data.FIRST_AID_ITEM} ({u.first_aid_charges} cargas)")

    down = (f"   [MORRENDO {u.death_clock}/{data.DYING_TURNS}]" if u.dying
            else "   [ESTAVEL - inconsciente]" if u.stable
            else "   [QUEBRADO - consertar: INT vs DC 15]" if u.broken
            else "   [FUGIU do combate]" if u.fled
            else "   [MORTO]" if u.dead else "")
    stats = (f"PV {max(u.hp, 0)}/{u.hp_max}   CA {u.ac}   DM {u.mental_defense}   Desloc {u.speed}"
             + (f"   ocupa {u.footprint}x{u.footprint}" if u.footprint > 1 else "")
             + ("   [desmoralizado]" if u.demoralized else "") + down)

    attr_pairs = [(lbl, getattr(u, name), getattr(u, f"mod_{name}"))
                  for lbl, name in _ATTR_LABELS]
    line_a = "   ".join(f"{lbl} {val} ({m:+})" for lbl, val, m in attr_pairs[:3])
    line_b = "   ".join(f"{lbl} {val} ({m:+})" for lbl, val, m in attr_pairs[3:])

    return [
        u.name,
        f"Tendencia: {u.alignment}   Idade: {u.age}   XP de combate: {u.combat_xp}"
        + (f"   XP de trabalho: {u.work_xp}" if u.work_xp else ""),
        stats,
        line_a,
        line_b,
        _weapon_line(u),
        hands_line,
        _armor_line(u),
        f"Inventario: {inv}",
        f"Carga: {u.load} / normal {u.carry_normal} / alta {u.carry_max}"
        + ("   SOBRECARREGADO: -2 FOR, -2 DES, -1 desloc" if u.encumbered else ""),
        f"Idiomas: {', '.join(u.languages)}"
        + ("  (imita vozes: Desmoraliza sem idioma)" if u.ability.demoralize_ignores_language
           else "  (Desmoralizar exige idioma em comum)"),
        u.ability.desc,
    ]

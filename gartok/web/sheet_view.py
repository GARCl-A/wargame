"""A member's sheet as the browser's book reads it, read-only: the guild's MEMBERS page and the modal any
screen that shows a person opens (`Session.sheet`, `Sheet` in `shell.js`). A unit with no guild yet (the
draft's pool) has no band, roles or record of who brought them in.
"""

from .. import data, item_icon, talents
from ..animals import Animal
from ..combatant import Combatant
from ..constants import fmt_money
from ..guild_sheet import ATTRIBUTE_LABELS, GuildSheet, node_label
from ..sheet import unit_to_ch
from .map_session import _portrait
from .stable_tab import _face


def _breakdown(title, terms, total):
    lines = [title] + [f"{label}: {v}" if i == 0 else f"{label}: {v:+}" for i, (label, v) in enumerate(terms)]
    return "\n".join([*lines, f"= {total}"])


def _hp_tip(u):
    b = u.hp_breakdown()
    lines = ["Hit points", f"{b['hit_dice']} hit dice of d{b['hd']}: {b['dice_sum']}", f"CON {b['con_total']:+}"]
    if b["talent_total"]:
        lines.append(f"Talents {b['talent_total']:+}")
    if b["ability_bonus"]:
        lines.append(f"{b['ability_name']} {b['ability_bonus']:+}")
    if b["starving"]:
        lines.append("Starving: held at 1")
    return "\n".join([*lines, f"= {b['final_max']}"])


def _talents(u):
    return [{"name": t.name if t else tid.title(), "desc": t.desc if t else ""}
            for track in talents.TRACKS for tid in u.talents.get(track, []) for t in (talents.get(tid),)]


def _record(s, u):
    who = s._recruited_by(u)
    out = [f"Recruited by {who}." if who else "A founding member of the guild.",
           s._sponsor_line(u).replace(" -- ", ": ") + "."]
    if getattr(u, "arena_title", False):
        out.append("Holds the title Champion of the Pit.")
    if getattr(u, "bio", ""):
        out.append(u.bio)
    return out


def member_sheet(u, guild=None, task=None):
    """The book's two pages for `u`; `task` is what the band is doing, as the map words it."""
    s = GuildSheet(guild) if guild is not None else None
    c = Combatant(u)
    ch = unit_to_ch(c)
    grp = guild.group_of(u) if guild is not None else None
    w = ch["weapon"]
    weapon = GuildSheet._weapon_data(u, c, ch)
    gear = GuildSheet._gear_data(u, c)
    load = gear["load"]
    rations, autotroph = gear["rations"]
    stamps = []
    if s is not None:
        if u is guild.leader:
            stamps.append({"text": "Guild leader", "tone": "leader"})
        elif s._is_group_leader(u):
            stamps.append({"text": "Leads the band", "tone": "leader"})
    if getattr(u, "arena_title", False):
        stamps.append({"text": "Champion of the Pit", "tone": ""})
    return {
        "uid": u.uid, "name": u.name, "portrait": _portrait(u), "race": u.race["name"],
        "occ": u.occupation["name"], "age": u.age, "align": u.alignment.capitalize(),
        "band": grp.display_name if grp else None, "gid": grp.gid if grp else None,
        "where": node_label(grp.node) if grp else "Not yet sworn in" if guild is None else "Camp",
        "task": task or (GuildSheet._group_task(grp).lower() if grp else "no orders"),
        "stamps": stamps, "status": ch["status"], "hungry": u.hunger_level > 0,
        "attrs": [{"k": k, "v": v, "mod": mod, "low": low} for k, v, mod, low in ch["attrs"]],
        "hp": list(ch["hp"]), "hp_tip": _hp_tip(u),
        "stats": [{"k": "AC", "v": ch["ac"], "tip": _breakdown("Armour class", u.ac_breakdown(), c.ac)},
                  {"k": "MD", "v": ch["md"], "tip": _breakdown("Mental defense", u.md_breakdown(), c.mental_defense)},
                  {"k": "SPD", "v": ch["spd"], "tip": _breakdown("Speed (squares)", u.speed_breakdown(), c.speed)},
                  {"k": "INIT", "v": ch["init"], "tip": _breakdown("Initiative", u.initiative_breakdown(), ch["init"])}],
        "weapon": {"name": weapon["name"], "tags": weapon["tags"], "crit": w["crit"], "action": w["action"],
                   "glyph": item_icon.glyph(u.equipped_weapon) if u.equipped_weapon else "item/knapsack",
                   "chips": [{"k": k, "v": v, "tip": t} for k, v, t in weapon["chips"]]},
        "kit": [{"k": "Hands", "v": gear["hands"], "note": ""},
                {"k": "Body", "v": gear["armor"], "note": gear["armor_note"]},
                {"k": "Purse", "v": fmt_money(gear["coins"]), "note": ""},
                {"k": "Rations", "v": "Feeds on light" if autotroph else str(rations or "None"),
                 "note": "" if autotroph else "days of food" if rations else "nothing to eat in the pack",
                 "bad": not autotroph and not rations},
                {"k": "Load", "v": f"{load[0]:.1f} kg",
                 "note": f"of {load[1]:g} at a normal pace, {load[2]:g} at most", "bad": load[0] > load[1]}],
        "ability": list(ch["ability"]), "langs": ch["langs"], "racial": u.racial_level,
        "tracks": [{k: t[k] for k in ("label", "value", "frac", "text", "tip")} for t in GuildSheet._tracks(u)],
        "talents": _talents(u),
        "record": _record(s, u) if s is not None else [u.bio] if getattr(u, "bio", "") else [],
    }


def animal_sheet(a, guild):
    s = GuildSheet(guild)
    grp = s._group_of(a)
    pulled = grp.pulling(a) if grp else None
    return {
        "uid": a.uid, "beast": True, "name": a.species, "portrait": _face(a.species, a.uid),
        "sub": f"{a.size} animal", "band": grp.display_name if grp else None, "gid": grp.gid if grp else None,
        "where": node_label(grp.node) if grp else "Camp",
        "hp": [max(0, a.hp), a.hp_max],
        "attrs": [{"k": k, "v": a.attributes[n], "mod": data.mod(a.attributes[n]), "low": False}
                  for k, n in ATTRIBUTE_LABELS],
        "speed": f"{a.speed:g} m",
        "ability": [a.ability.name, a.ability.effect] if a.race["ability"] else None,
        "work": [{"k": k.title(), "v": v, "tone": tone} for k, v, tone in GuildSheet._animal_work_rows(a, pulled)],
    }


def sheet_of(unit, guild=None, task=None):
    return animal_sheet(unit, guild) if isinstance(unit, Animal) else member_sheet(unit, guild, task)


"""A member's sheet as the browser's book reads it, read-only: the guild's MEMBERS page and the modal any
screen that shows a person opens (`Session.sheet`, `Sheet` in `shell.js`). A unit with no guild yet (the
draft's pool) has no band, roles or record of who brought them in.
"""

from .. import data, i18n, item_icon, talents, wiki_terms
from ..animals import Animal
from ..combatant import Combatant
from ..constants import fmt_money
from ..guild_sheet import ATTRIBUTE_LABELS, GuildSheet, node_label
from ..sheet import unit_to_ch
from .map_session import _portrait
from .stable_tab import _face


def _term(label):
    """A breakdown term written in English ("DEX", "Plate (drag)", "Elf base") in the current language."""
    for suffix, kind in ((" (natural)", None), (" (drag)", "item"), (" base", "race")):
        if label.endswith(suffix):
            head = label[:-len(suffix)]
            shown = i18n.name(kind, head) if kind else head
            word = i18n.lab(suffix.strip(" ()"))
            return f"{shown} {word}" if suffix == " base" else f"{shown} ({word})"
    return i18n.lab(label)


def _breakdown(title, terms, total):
    lines = [title] + [f"{_term(label)}: {v}" if i == 0 else f"{_term(label)}: {v:+}" for i, (label, v) in enumerate(terms)]
    return "\n".join([*lines, f"= {total}"])


def _hp_tip(u):
    b = u.hp_breakdown()
    lines = [i18n.t("sheet_view.hit_points"), i18n.t("sheet_view.hit_dice_of_d", dice=b['hit_dice'], die=b['hd'], total=b['dice_sum']), i18n.t("sheet_view.con", b=b['con_total'])]
    if b["talent_total"]:
        lines.append(i18n.t("sheet_view.talents", b=b['talent_total']))
    if b["ability_bonus"]:
        lines.append(f"{b['ability_name']} {b['ability_bonus']:+}")
    if b["starving"]:
        lines.append(i18n.t("sheet_view.starving_held_at"))
    return "\n".join([*lines, f"= {b['final_max']}"])


def _talents(u):
    return [{"name": t.name if t else tid.title(), "desc": t.desc if t else ""}
            for track in talents.TRACKS for tid in u.talents.get(track, []) for t in (talents.get(tid),)]


def bio(u):
    """The backstory of `u`: an authored NPC's is the catalog's `desc.npc.<slug>` (its English is the NPC
    file's own `bio`, see `i18n._npc_bios`), else the unit's own text."""
    slug = getattr(u, "bio_slug", None)
    return (i18n.desc("npc", slug) if slug else "") or getattr(u, "bio", "")


def _record(s, u):
    who = s._recruited_by(u)
    out = [i18n.t("sheet_view.recruited_by", who=who) if who else i18n.t("sheet_view.founding_member_of_guild"),
           s._sponsor_line(u) + "."]
    if getattr(u, "arena_title", False):
        out.append(i18n.t("sheet_view.holds_title_champion_of_pit"))
    text = bio(u)
    if text:
        out.append(text)
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
            stamps.append({"text": i18n.t("sheet_view.guild_leader"), "tone": "leader"})
        elif s._is_group_leader(u):
            stamps.append({"text": i18n.t("sheet_view.leads_band"), "tone": "leader"})
    if getattr(u, "arena_title", False):
        stamps.append({"text": i18n.t("sheet_view.champion_of_pit"), "tone": ""})
    return {
        "uid": u.uid, "name": u.name, "portrait": _portrait(u), "race": u.race_label,
        "age": u.age, "align": i18n.name("alignment", u.alignment),
        "band": grp.display_name if grp else None, "gid": grp.gid if grp else None,
        "where": node_label(grp.node) if grp else i18n.t("sheet_view.not_yet_sworn_in") if guild is None else i18n.lab("Camp"),
        "task": task or (GuildSheet._group_task(grp).lower() if grp else i18n.t("sheet_view.no_orders")),
        "stamps": stamps, "status": ch["status"], "hungry": u.hunger_level > 0,
        "attrs": [{"k": k, "v": v, "mod": mod, "low": low} for k, v, mod, low in ch["attrs"]],
        "hp": list(ch["hp"]), "hp_tip": _hp_tip(u),
        "stats": [{"k": "AC", "v": ch["ac"], "tip": _breakdown(i18n.t("sheet_view.armour_class"), u.ac_breakdown(), c.ac)},
                  {"k": "MD", "v": ch["md"], "tip": _breakdown(i18n.t("sheet_view.mental_defense"), u.md_breakdown(), c.mental_defense)},
                  {"k": "SPD", "v": ch["spd"], "tip": _breakdown(i18n.lab("Speed (squares)"), u.speed_breakdown(), c.speed)},
                  {"k": "INIT", "v": ch["init"], "tip": _breakdown(i18n.lab("Initiative"), u.initiative_breakdown(), ch["init"])}],
        "weapon": {"name": weapon["name"], "tags": weapon["tags"], "crit": w["crit"], "action": w["action"],
                   "action_tip": wiki_terms.action_tip(w["action"]),
                   "glyph": item_icon.glyph(u.equipped_weapon) if u.equipped_weapon else "item/knapsack",
                   "chips": [{"k": k, "v": v, "tip": t} for k, v, t in weapon["chips"]]},
        "kit": [{"k": "Hands", "v": gear["hands"], "note": ""},
                {"k": "Body", "v": gear["armor"], "note": gear["armor_note"]},
                {"k": "Purse", "v": fmt_money(gear["coins"]), "note": ""},
                {"k": "Rations", "v": i18n.t("sheet_view.feeds_on_light") if autotroph else str(rations or i18n.lab("None")),
                 "note": "" if autotroph else i18n.t("sheet_view.days_of_food") if rations else i18n.t("sheet_view.nothing_to_eat_in_pack"),
                 "bad": not autotroph and not rations},
                {"k": "Load", "v": i18n.t("sheet_view.kg", load=load[0]),
                 "note": i18n.t("sheet_view.of_at_normal_pace_at", load=load[1], most=load[2]), "bad": load[0] > load[1]}],
        "ability": list(ch["ability"]), "langs": ch["langs"], "racial": u.racial_level,
        "tracks": [{k: t[k] for k in ("label", "value", "frac", "text", "tip")} for t in GuildSheet._tracks(u)],
        "talents": _talents(u),
        "record": _record(s, u) if s is not None else [text] if (text := bio(u)) else [],
    }


def animal_sheet(a, guild):
    s = GuildSheet(guild)
    grp = s._group_of(a)
    pulled = grp.pulling(a) if grp else None
    return {
        "uid": a.uid, "beast": True, "name": i18n.name("race", a.species), "portrait": _face(a.species, a.uid),
        "sub": i18n.t("sheet_view.animal", size=i18n.name("size", a.size)), "band": grp.display_name if grp else None, "gid": grp.gid if grp else None,
        "where": node_label(grp.node) if grp else i18n.lab("Camp"),
        "hp": [max(0, a.hp), a.hp_max],
        "attrs": [{"k": i18n.lab(k), "v": a.attributes[n], "mod": data.mod(a.attributes[n]), "low": False}
                  for k, n in ATTRIBUTE_LABELS],
        "speed": f"{a.speed:g} m",
        "ability": [a.ability.name, a.ability.effect] if a.race["ability"] else None,
        "work": [{"k": k.title(), "v": v, "tone": tone} for k, v, tone in GuildSheet._animal_work_rows(a, pulled)],
    }


def sheet_of(unit, guild=None, task=None):
    return animal_sheet(unit, guild) if isinstance(unit, Animal) else member_sheet(unit, guild, task)


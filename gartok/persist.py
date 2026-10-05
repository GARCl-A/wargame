"""Worlds and saves: each world (one guild's campaign) is a folder under `saves/`.
`current.json` is the live state -- rewritten after the draft, every battle and
every manage step -- next to the snapshots that let a player go back in time:
`auto_<ts>.json` (taken right before each fight, the last `AUTOSAVES_KEPT` are
kept) and `manual_<ts>.json` (named by the player, never pruned). Loading any
snapshot makes it the new `current`; the others stay on the list. A wipe does
not delete the world.

The player roster is saved as **groups** (`gartok/group.py`): each group's own
member list, map node and leader (a uid, resolved back to a `Unit` after its
members load), plus a small shared campaign meta (wins, clock, bank chest, the
guild's own leader + whether its one free change is spent, the guild's chosen
name/banner, the taverna's current weekly pool of would-be recruits). A save
from before the groups layer (`"roster"`/`"node"`, no `"groups"` key) loads as
one group holding the whole old roster; a save from before leadership existed
(no `"leader"` key on the guild or a group) auto-picks one by Charisma on load
(`Guild._sync_leadership`/`Group.ensure_leader`). Enemies are rolled fresh each
battle and battle state lives on a throwaway `Combatant` wrapper, never on the
`Unit`, so disk never sees it -- a saved unit is always "full HP, standing".
"""

import json
import os
import shutil
import sys
import time
import uuid

from . import items, missions
from .clock import Clock
from .group import Group
from .guild import Guild
from .holdings import CityProperty, Stash
from .tutorial import TutorialState
from .unit import ATTRIBUTES, Unit

# Se estiver rodando como um executável do PyInstaller, sys.frozen será True.
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(__file__))

SAVE_DIR = os.path.join(_BASE_DIR, "saves")
CURRENT = "current"
AUTOSAVES_KEPT = 10
SAVE_VERSION = 18                # bumped when the payload shape changes; `from_save` still tolerates missing keys


def new_world_id():
    return uuid.uuid4().hex[:8]


def world_dir(world):
    return os.path.join(SAVE_DIR, str(world))


def save_path(world, save_id=CURRENT):
    return os.path.join(world_dir(world), f"{save_id}.json")


def _serialize_pack(pack):
    res = []
    for it in pack:
        if hasattr(it, "to_dict"):
            res.append(it.to_dict())
        elif isinstance(it, str):
            res.append(items.create_instance(it, qty=1).to_dict())
        elif isinstance(it, (tuple, list)) and len(it) == 2:
            res.append(items.create_instance(it[0], qty=it[1]).to_dict())
        elif isinstance(it, dict):
            res.append(it)
        else:
            res.append({"id": str(it).lower(), "name": str(it), "qty": 1})
    return res


def unit_to_dict(u):
    """The minimum to rebuild a unit deterministically (see `Unit.from_save`)."""
    return {
        "uid": u.uid,                            # stable identity (recruiter binding references it)
        "recruited_by": u.recruited_by,          # uid of the member who recruited this one, or None
        "name": u.name,
        "auto_name": u._auto_name,
        "portrait_id": getattr(u, "portrait_id", None),
        "race": u.race["name"],
        "occupation": u.occupation["name"],
        "alignment": u.alignment,
        "crime": u.crime,                        # rap sheet the guard tests at a jurisdiction node
        "unfed_days": u.unfed_days,              # hunger counter (0 = fed today)
        "sick": getattr(u, "sick", False),       # food poisoning
        "medicine_attempted_today": getattr(u, "medicine_attempted_today", False),
        "treated": getattr(u, "treated", False),
        "first_aid_charges": u.first_aid_charges,
        "quiver_charges": u.quiver_charges,
        "consecutive_rest_hours": u.consecutive_rest_hours,
        "last_daily_luck_day": getattr(u, "last_daily_luck_day", 0),
        "hp": getattr(u, "hp", u.hp_max),
        "share_food": u.share_food,              # pools rations for hungry guild-mates
        "combat_xp": u.combat_xp,                # combat XP (see progression.py)
        "work_hours": u.work_hours,              # lifetime hours of lumber-yard day-labour
        "bio": u.bio,                            # free-text backstory (blank for a rolled character)
        "arena_title": u.arena_title,            # holds the "Champion of the Pit" title (arena.py)
        "recipes": list(u.recipes),
        "crafting_target": u.crafting_target,
        "crafting_progress": u.crafting_progress,
        "craft_bonuses": dict(u.craft_bonuses),
        "magic_source": u.magic_source,          # nature / blood / faith, or None (see magic.py)
        "spells_known": list(u.spells_known),
        "study_target": u.study_target,          # spell id or language name being studied at the taverna, or None
        "study_progress": u.study_progress,
        "talents": {t: list(v) for t, v in u.talents.items()},   # picked talent ids per track
        "level_hp_rolls": list(u._level_hp_rolls),               # 1dHD per mean-level gained
        "base_attributes": {a: u.base_attributes[a] for a in ATTRIBUTES},
        "age_base": u._age_base,                 # the generator's d100 roll (age at age_mult x1)
        "age": u.age,                            # shown age -- editable in the creator, else age_base x age_mult
        "hp_roll": u._hp_roll,                   # 1dHD, rolled once at creation
        "hp_override": u._hp_override,           # creator-set HP max that wins over the formula, or None
        "racial_override": u._racial_override,   # creator-pinned racial level (hit dice + racial picks), or None
        "hp_max": u.hp_max,                      # kept for pre-hunger saves / at-a-glance
        "languages": list(u.languages),          # racial + random extras + any learned via study
        "equipped_weapon": u.equipped_weapon,    # weapon hand (None = unarmed)
        "equipped_offhand": u.equipped_offhand,  # off hand: a torch, or None
        "equipped_tongue": u.equipped_tongue,    # Grippli Tongue slot: a 1-handed weapon, or None
        "equipped_armor": u.equipped_armor,      # body slot: armor name, or None
        "inventory": _serialize_pack(u._base_inventory),    # the pack: spare items, weapons included
        "locked_items": dict(u.locked_items),    # item name -> count exempt from distribute_load
        "dormant": getattr(u, "dormant", False),
        "awareness_radius": getattr(u, "awareness_radius", 0),
    }


def group_to_dict(g):
    return {
        "gid": g.gid,
        "name": g.name,
        "node": g.node,
        "leader": g.leader.uid if g.leader else None,
        "members": [unit_to_dict(u) for u in g.members],
    }


def group_from_dict(d):
    members = [Unit.from_save(m) for m in d["members"]]
    leader = next((u for u in members if u.uid == d.get("leader")), None)
    return Group(members, node=d.get("node"), name=d.get("name"), gid=d.get("gid"),
                 leader=leader)


def _payload(guild, kind, label):
    return {
        "save_version": SAVE_VERSION,
        "save_kind": kind,
        "save_label": label,
        "day": guild.clock.day,
        "battles_won": guild.battles_won,
        "reputation": dict(guild.reputation),
        "deeds_done": list(guild.deeds_done),
        "arena_challenge_day": guild.arena_challenge_day,
        "clock_seconds": guild.clock.seconds,
        "bank_capacity": guild.bank.capacity,
        "bank_items": _serialize_pack(guild.bank.items),
        "property_city_unlocked": guild.house.owned,
        "property_city_items": _serialize_pack(guild.house.stash.items),
        "property_city_tax_due_day": guild.house.tax_due_day,
        "property_city_missed_payments": guild.house.missed_payments,
        "property_city_squatting": guild.house.squatting,
        "bankers_debt": guild.bankers_debt,
        "property_city_debt_since": guild.bankers_debt_since,
        "garrison_stock": {node_id: list(items) for node_id, items in guild.garrison_stock.items()},
        "wilds_claim_stage": guild.wilds_claim_stage,
        "wilds_claim_fence_lumber": guild.wilds_claim_fence_lumber,
        "wilds_claim_sustain_days_left": guild.wilds_claim_sustain_days_left,
        "wilds_claim_owner": guild.wilds_claim_owner,
        "ancient_ruins_discovered": getattr(guild, "ancient_ruins_discovered", False),
        "market_stock": dict(guild.market_stock),
        "total_spent": guild.total_spent,
        "items_sold_kinds": sorted(guild.items_sold_kinds),
        "missions": [missions.mission_to_dict(m) for m in guild.missions],
        "leader": guild.leader.uid if guild.leader else None,
        "leader_swaps_used": guild.leader_swaps_used,
        "leaving": dict(guild.leaving),
        "name": guild.name,
        "banner_color": list(guild.banner_color),
        "banner_icon": guild.banner_icon,
        "saved_at": time.time(),
        "squad": [u.name for u in guild.roster],   # flattened names, for the slot summary
        "groups": [group_to_dict(g) for g in guild.groups],
        "taverna_week": guild.taverna_week,
        "taverna_pool": ([unit_to_dict(u) for u in guild.taverna_pool]
                         if guild.taverna_pool is not None else None),
        "taverna_blocked": guild.taverna_blocked,
        "prison_week": guild.prison_week,
        "prison_pool": ([unit_to_dict(u) for u in guild.prison_pool]
                         if guild.prison_pool is not None else None),
        "prison_blocked": guild.prison_blocked,
        "jailed": [{"unit": unit_to_dict(u), "released_day": day}
                   for u, day in guild.jailed],
        "tutorial_seen": sorted(guild.tutorial.seen),
        "tutorial_enabled": guild.tutorial.enabled,
    }


def save_game(world, guild, kind="current", label=""):
    """Write `guild` into `world`'s folder and return the save id. `kind` is
    "current" (the live file, overwritten), "auto" or "manual" (a new snapshot)."""
    os.makedirs(world_dir(world), exist_ok=True)
    save_id = CURRENT if kind == "current" else f"{kind}_{time.time_ns()}"
    path = save_path(world, save_id)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(_payload(guild, kind, label), fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)                       # atomic: never leave a half-written save
    if kind == "auto":
        _prune_autosaves(world)
    return save_id


def _prune_autosaves(world):
    autos = sorted(f for f in os.listdir(world_dir(world))
                   if f.startswith("auto_") and f.endswith(".json"))
    for name in autos[:-AUTOSAVES_KEPT]:
        os.remove(os.path.join(world_dir(world), name))


def load_game(world, save_id=CURRENT):
    """-> Guild (groups + campaign meta). Missing keys default (old saves); a
    save from before the groups layer (`"roster"`/`"node"`, no `"groups"`) is
    rebuilt as a single group holding the whole old roster at the old node."""
    with open(save_path(world, save_id), encoding="utf-8") as fh:
        payload = json.load(fh)
    if "groups" in payload:
        groups = [group_from_dict(d) for d in payload["groups"]]
    else:
        roster = [Unit.from_save(d) for d in payload["roster"]]
        groups = [Group(roster, node=payload.get("node"))]
    pool = payload.get("taverna_pool")
    p_pool = payload.get("prison_pool")
    roster = [u for g in groups for u in g.members]
    leader = next((u for u in roster if u.uid == payload.get("leader")), None)
    return Guild(None, groups=groups,
                 battles_won=payload.get("battles_won", 0),
                 reputation=payload.get("reputation", {}),
                 deeds_done=payload.get("deeds_done", []),
                 arena_challenge_day=payload.get("arena_challenge_day"),
                 clock=Clock(payload.get("clock_seconds", 0)),
                 bank=Stash(payload.get("bank_capacity", 0), payload.get("bank_items", [])),
                 house=CityProperty(owned=payload.get("property_city_unlocked", False),
                                    contents=payload.get("property_city_items", []),
                                    tax_due_day=payload.get("property_city_tax_due_day"),
                                    missed_payments=payload.get("property_city_missed_payments", 0),
                                    squatting=payload.get("property_city_squatting", False)),
                 bankers_debt=payload.get("bankers_debt", 0),
                 bankers_debt_since=payload.get("property_city_debt_since"),
                 garrison_stock=payload.get("garrison_stock"),
                 wilds_claim_stage=payload.get("wilds_claim_stage", "NONE"),
                 wilds_claim_fence_lumber=payload.get("wilds_claim_fence_lumber", 0),
                 wilds_claim_sustain_days_left=payload.get("wilds_claim_sustain_days_left"),
                 wilds_claim_owner=payload.get("wilds_claim_owner"),
                 market_stock=payload.get("market_stock"),
                 total_spent=payload.get("total_spent", 0),
                 items_sold_kinds=payload.get("items_sold_kinds", []),
                 missions=[missions.mission_from_dict(d) for d in payload.get("missions", [])],
                 taverna_week=payload.get("taverna_week"),
                 taverna_pool=[Unit.from_save(d) for d in pool] if pool is not None else None,
                 taverna_blocked=payload.get("taverna_blocked"),
                 prison_week=payload.get("prison_week"),
                 prison_pool=[Unit.from_save(d) for d in p_pool] if p_pool is not None else None,
                 prison_blocked=payload.get("prison_blocked"),
                 jailed=[(Unit.from_save(d["unit"]), d["released_day"])
                         for d in payload.get("jailed", [])],
                 leader=leader, leader_swaps_used=payload.get("leader_swaps_used", 0),
                 leaving=payload.get("leaving"),
                 name=payload.get("name", ""), banner_color=payload.get("banner_color"),
                 banner_icon=payload.get("banner_icon"),
                 ancient_ruins_discovered=payload.get("ancient_ruins_discovered", False),
                 tutorial=TutorialState(seen=payload.get("tutorial_seen", []),
                                       enabled=payload.get("tutorial_enabled", True)))


def delete_world(world):
    shutil.rmtree(world_dir(world), ignore_errors=True)


def delete_save(world, save_id):
    if save_id == CURRENT:
        return
    try:
        os.remove(save_path(world, save_id))
    except FileNotFoundError:
        pass


def _summary(world, save_id):
    """Menu row for one save file, or None if it is missing/unreadable."""
    try:
        with open(save_path(world, save_id), encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    return {
        "world": world, "id": save_id,
        "kind": payload.get("save_kind", "current"),
        "label": payload.get("save_label", ""),
        "name": payload.get("name", ""),
        "squad": payload.get("squad", []),
        "battles_won": payload.get("battles_won", 0),
        "day": payload.get("day"),
        "saved_at": payload.get("saved_at", 0),
    }


def list_saves(world):
    """Every save of `world`, newest first -- `current` included."""
    try:
        names = os.listdir(world_dir(world))
    except FileNotFoundError:
        return []
    rows = [_summary(world, n[:-5]) for n in names if n.endswith(".json")]
    return sorted((r for r in rows if r), key=lambda r: r["saved_at"], reverse=True)


def list_worlds():
    """One row per world with a live save (the menu's guild list), most recently
    played first: {world, name, squad, battles_won, saved_at, saves}."""
    try:
        worlds = [d for d in os.listdir(SAVE_DIR) if os.path.isdir(world_dir(d))]
    except FileNotFoundError:
        return []
    rows = []
    for w in worlds:
        cur = _summary(w, CURRENT)
        if cur:
            rows.append({**cur, "saves": sum(f.endswith(".json") for f in os.listdir(world_dir(w)))})
    return sorted(rows, key=lambda r: r["saved_at"], reverse=True)

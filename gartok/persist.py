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
name/banner, the taverna's current weekly pool of would-be recruits). Enemies are rolled fresh each
battle and battle state lives on a throwaway `Combatant` wrapper, never on the
`Unit`, so disk never sees it -- a saved unit is always "full HP, standing".

A group's `order` (travel, rest, garrison...) and its `pending` forced order
(an ambush that came due, enemy pack included) are saved too, so a load picks
the world back up where it stood.
Nothing mid-battle or mid-hunt is ever saved (`App._can_save`).
"""

import copy
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import fields

from . import missions
from .animals import Animal
from .clock import Clock
from .group import NORMAL, Group
from .guild import Guild
from .holdings import CityProperty, Garage, Stash
from .orders import Order
from .shop import Shop
from .tutorial import TutorialState
from .unit import ATTRIBUTES, Unit
from .wagon import Wagon

# Se estiver rodando como um executável do PyInstaller, sys.frozen será True.
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(__file__))

SAVE_DIR = os.path.join(_BASE_DIR, "saves")
CURRENT = "current"
AUTOSAVES_KEPT = 10
SAVE_VERSION = 2                 # bumped when the payload shape changes; nothing upgrades an older save


class SaveVersionError(Exception):
    """The save was written by another version of the game and cannot be read."""


def new_world_id():
    return uuid.uuid4().hex[:8]


def world_dir(world):
    return os.path.join(SAVE_DIR, str(world))


def save_path(world, save_id=CURRENT):
    return os.path.join(world_dir(world), f"{save_id}.json")


def _serialize_pack(pack):
    return [it.to_dict() for it in pack]


def unit_to_dict(u):
    """The minimum to rebuild a unit deterministically (see `Unit.from_save`)."""
    return {
        "uid": u.uid,                            # stable identity (recruiter binding references it)
        "recruited_by": u.recruited_by,          # uid of the member who recruited this one, or None
        "name": u.name,
        "auto_name": u._auto_name,
        "portrait_id": u.portrait_id,
        "portrait_file": getattr(u, "portrait_file", None),
        "race": u.race["name"],
        "occupation": u.occupation["name"],
        "alignment": u.alignment,
        "crime": u.crime,                        # rap sheet the guard tests at a jurisdiction node
        "unfed_days": u.unfed_days,              # hunger counter (0 = fed today)
        "sick": u.sick,                          # food poisoning
        "medicine_attempted_today": u.medicine_attempted_today,
        "treated": u.treated,
        "consecutive_rest_hours": u.consecutive_rest_hours,
        "last_daily_luck_day": u.last_daily_luck_day,
        "hp": u.hp,
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
        "poisons": {pid: dict(st) for pid, st in u.poisons.items()},   # active poison stacks (unit_poison.py)
        "antidote_cooldown": u.antidote_cooldown,    # hours until the next Antidote may be used
        "natural_armor": u.natural_armor,        # flat AC the body itself gives (creator-set), 0 by default
        "racial_override": u._racial_override,   # creator-pinned racial level (hit dice + racial picks), or None
        "languages": list(u.languages),          # racial + random extras + any learned via study
        "equipped_weapon": u.equipped_weapon,    # weapon hand (None = unarmed)
        "equipped_offhand": u.equipped_offhand,  # off hand: a torch, or None
        "equipped_tongue": u.equipped_tongue,    # Grippli Tongue slot: a 1-handed weapon, or None
        "equipped_artifact": u.equipped_artifact,    # artifact slot: an ItemType.ARTIFACT, or None
        "equipped_armor": u.equipped_armor,      # body slot: armor name, or None
        "inventory": _serialize_pack(u._base_inventory),    # the pack: spare items, weapons included
        "locked_items": dict(u.locked_items),    # item name -> count exempt from distribute_load
        "dormant": u.dormant,
        "afoot": u.afoot,
        "awareness_radius": u.awareness_radius,
    }


def wagon_to_dict(w):
    return {"uid": w.uid, "kind": w.kind, "hp": w.hp, "travelled": w.travelled,
            "contents": _serialize_pack(w.stash.items)}


def wagon_from_dict(d):
    return Wagon(d["kind"], d["hp"], d["contents"], d["uid"], d["travelled"])


def garage_from_dict(d, unlimited=False):
    return Garage(d["tier"], [wagon_from_dict(w) for w in d["wagons"]],
                  [Animal.from_dict(a) for a in d["herd"]], unlimited=unlimited)


def garage_to_dict(garage):
    return {"tier": garage.tier,
            "wagons": [wagon_to_dict(w) for w in garage.wagons],
            "herd": [a.to_dict(_serialize_pack) for a in garage.herd]}


_ORDER_SEQUENCES = ("path", "caught", "resume_path")


def order_to_dict(order):
    d = {f.name: getattr(order, f.name) for f in fields(order)}
    for key in _ORDER_SEQUENCES:
        d[key] = list(d[key])
    d["pack"] = [unit_to_dict(u) for u in order.pack]
    return d


def order_from_dict(d):
    kwargs = {f.name: d[f.name] for f in fields(Order)}
    for key in _ORDER_SEQUENCES:
        kwargs[key] = tuple(kwargs[key])
    kwargs["pack"] = tuple(Unit.from_save(u) for u in d["pack"])
    return Order(**kwargs)


def group_to_dict(g):
    return {
        "gid": g.gid,
        "name": g.name,
        "node": g.node,
        "order": order_to_dict(g.order) if g.order is not None else None,
        "pending": order_to_dict(g.pending) if g.pending is not None else None,
        "leader": g.leader.uid if g.leader else None,
        "members": [unit_to_dict(u) for u in g.members],
        "wagons": [wagon_to_dict(w) for w in g.wagons],
        "herd": [a.to_dict(_serialize_pack) for a in g.herd],
        "herd_notice": g.herd_notice,
        "stance": g.stance,
    }


def group_from_dict(d):
    members = [Unit.from_save(m) for m in d["members"]]
    leader = next((u for u in members if u.uid == d["leader"]), None)
    wagons = [wagon_from_dict(w) for w in d["wagons"]]
    herd = [Animal.from_dict(a) for a in d["herd"]]
    group = Group(members, node=d["node"], name=d["name"], gid=d["gid"],
                  leader=leader, wagons=wagons, herd=herd)
    group.herd_notice = d["herd_notice"]
    group.stance = d.get("stance", NORMAL)
    if d["order"]:
        group.order = order_from_dict(d["order"])
    if d["pending"]:
        group.pending = order_from_dict(d["pending"])
    return group


# What `load_game` assumes for a key a save does not carry; a new optional field goes
# here instead of bumping SAVE_VERSION.
PAYLOAD_DEFAULTS = {
    "battles_won": 0, "reputation": {}, "deeds_done": [], "arena_challenge_day": None,
    "bankers_debt": 0, "property_city_debt_since": None, "garrison_stock": {},
    "wilds_claim_stage": "NONE", "wilds_claim_fence_lumber": 0,
    "wilds_claim_sustain_days_left": None, "wilds_claim_owner": None,
    "wilds_claim_campfire": False, "claim_oven": False, "ancient_ruins_discovered": False,
    "ox_fields_discovered": False, "ox_trails": 0,
    "shops": {}, "total_spent": 0, "items_sold_kinds": [], "missions": [],
    "taverna_week": None, "taverna_pool": None, "taverna_blocked": [],
    "prison_week": None, "prison_pool": None, "prison_blocked": [], "jailed": [],
    "recruit_seen": {},
    "leader": None, "leader_swaps_used": 0, "leaving": {}, "vocation": None,
    "tutorial_seen": [], "tutorial_enabled": True,
}


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
        "property_city_oven": guild.house.oven,
        "property_city_garage": garage_to_dict(guild.house.garage),
        "wilds_claim_garage": garage_to_dict(guild.claim_garage),
        "bankers_debt": guild.bankers_debt,
        "property_city_debt_since": guild.bankers_debt_since,
        "garrison_stock": {node_id: list(items) for node_id, items in guild.garrison_stock.items()},
        "wilds_claim_stage": guild.wilds_claim_stage,
        "wilds_claim_fence_lumber": guild.wilds_claim_fence_lumber,
        "wilds_claim_sustain_days_left": guild.wilds_claim_sustain_days_left,
        "wilds_claim_owner": guild.wilds_claim_owner,
        "wilds_claim_campfire": guild.wilds_claim_campfire,
        "claim_oven": guild.claim_oven,
        "ancient_ruins_discovered": guild.ancient_ruins_discovered,
        "ox_fields_discovered": guild.ox_fields_discovered,
        "ox_trails": guild.ox_trails,
        "shops": {node_id: shop.to_dict() for node_id, shop in guild.shops.items()},
        "total_spent": guild.total_spent,
        "items_sold_kinds": sorted(guild.items_sold_kinds),
        "missions": [missions.mission_to_dict(m) for m in guild.missions],
        "leader": guild.leader.uid if guild.leader else None,
        "leader_swaps_used": guild.leader_swaps_used,
        "leaving": dict(guild.leaving),
        "vocation": guild.vocation,
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
        "recruit_seen": guild.recruit_seen,
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
    """-> Guild (groups + campaign meta). A key absent from the file falls back to `PAYLOAD_DEFAULTS`."""
    with open(save_path(world, save_id), encoding="utf-8") as fh:
        payload = json.load(fh)
    payload = {**copy.deepcopy(PAYLOAD_DEFAULTS), **payload}
    if payload.get("save_version") != SAVE_VERSION:
        raise SaveVersionError(f"This save is from another version of the game (save format "
                               f"{payload.get('save_version')}, expected {SAVE_VERSION}) and cannot be loaded.")
    groups = [group_from_dict(d) for d in payload["groups"]]
    pool = payload["taverna_pool"]
    p_pool = payload["prison_pool"]
    roster = [u for g in groups for u in g.members]
    leader = next((u for u in roster if u.uid == payload["leader"]), None)
    return Guild(None, groups=groups,
                 battles_won=payload["battles_won"],
                 reputation=payload["reputation"],
                 deeds_done=payload["deeds_done"],
                 arena_challenge_day=payload["arena_challenge_day"],
                 clock=Clock(payload["clock_seconds"]),
                 bank=Stash(payload["bank_capacity"], payload["bank_items"]),
                 house=CityProperty(owned=payload["property_city_unlocked"],
                                    contents=payload["property_city_items"],
                                    tax_due_day=payload["property_city_tax_due_day"],
                                    missed_payments=payload["property_city_missed_payments"],
                                    squatting=payload["property_city_squatting"],
                                    oven=payload["property_city_oven"],
                                    garage=garage_from_dict(payload["property_city_garage"])),
                 bankers_debt=payload["bankers_debt"],
                 bankers_debt_since=payload["property_city_debt_since"],
                 garrison_stock=payload["garrison_stock"],
                 wilds_claim_stage=payload["wilds_claim_stage"],
                 wilds_claim_fence_lumber=payload["wilds_claim_fence_lumber"],
                 wilds_claim_sustain_days_left=payload["wilds_claim_sustain_days_left"],
                 wilds_claim_owner=payload["wilds_claim_owner"],
                 wilds_claim_campfire=payload["wilds_claim_campfire"],
                 claim_oven=payload["claim_oven"],
                 claim_garage=garage_from_dict(payload["wilds_claim_garage"], unlimited=True),
                 shops={node_id: Shop.from_dict(d) for node_id, d in payload["shops"].items()},
                 total_spent=payload["total_spent"],
                 items_sold_kinds=payload["items_sold_kinds"],
                 missions=[missions.mission_from_dict(d) for d in payload["missions"]],
                 taverna_week=payload["taverna_week"],
                 taverna_pool=[Unit.from_save(d) for d in pool] if pool is not None else None,
                 taverna_blocked=payload["taverna_blocked"],
                 prison_week=payload["prison_week"],
                 prison_pool=[Unit.from_save(d) for d in p_pool] if p_pool is not None else None,
                 prison_blocked=payload["prison_blocked"],
                 recruit_seen=payload["recruit_seen"],
                 jailed=[(Unit.from_save(d["unit"]), d["released_day"])
                         for d in payload["jailed"]],
                 leader=leader, leader_swaps_used=payload["leader_swaps_used"],
                 leaving=payload["leaving"],
                 vocation=payload["vocation"],
                 name=payload["name"], banner_color=payload["banner_color"],
                 banner_icon=payload["banner_icon"],
                 ancient_ruins_discovered=payload["ancient_ruins_discovered"],
                 ox_fields_discovered=payload["ox_fields_discovered"],
                 ox_trails=payload["ox_trails"],
                 tutorial=TutorialState(seen=payload["tutorial_seen"],
                                       enabled=payload["tutorial_enabled"]))


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

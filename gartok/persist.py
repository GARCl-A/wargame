"""Save slots: each slot is one JSON file under `saves/`; the game autosaves to
the active slot after the draft, after every battle and after every manage step.

Only the player roster and a small campaign meta (wins, clock, map node, and the
taverna's current weekly pool of would-be recruits) are persisted. Enemies are
rolled fresh each battle and battle state lives on a throwaway `Combatant`
wrapper, never on the `Unit`, so disk never sees it -- a saved unit is always
"full HP, standing".
"""

import json
import os
import time

from .clock import Clock
from .guild import Guild
from .unit import ATTRIBUTES, Unit

SAVE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "saves")
NUM_SLOTS = 3
SAVE_VERSION = 5                # bumped when the payload shape changes; `from_save` still tolerates missing keys


def slot_path(slot):
    return os.path.join(SAVE_DIR, f"slot_{slot}.json")


def unit_to_dict(u):
    """The minimum to rebuild a unit deterministically (see `Unit.from_save`)."""
    return {
        "uid": u.uid,                            # stable identity (recruiter binding references it)
        "recruited_by": u.recruited_by,          # uid of the member who recruited this one, or None
        "name": u.name,
        "auto_name": u._auto_name,
        "race": u.race["name"],
        "occupation": u.occupation["name"],
        "alignment": u.alignment,
        "gold": u.gold,                          # copper coins carried by the member
        "unfed_days": u.unfed_days,              # hunger counter (0 = fed today)
        "share_food": u.share_food,              # pools rations for hungry guild-mates
        "combat_xp": u.combat_xp,                # combat XP (see progression.py)
        "work_hours": u.work_hours,              # lifetime hours of lumber-yard day-labour
        "bio": u.bio,                            # free-text backstory (blank for a rolled character)
        "arena_title": u.arena_title,            # holds the "Champion of the Pit" title (arena.py)
        "talents": {t: list(v) for t, v in u.talents.items()},   # picked talent ids per track
        "level_hp_rolls": list(u._level_hp_rolls),               # 1dHD per mean-level gained
        "base_attributes": {a: u.base_attributes[a] for a in ATTRIBUTES},
        "age_base": u._age_base,                 # the generator's d100 roll (age at age_mult x1)
        "age": u.age,                            # shown age -- editable in the creator, else age_base x age_mult
        "hp_roll": u._hp_roll,                   # 1dHD, rolled once at creation
        "hp_override": u._hp_override,           # creator-set HP max that wins over the formula, or None
        "racial_override": u._racial_override,   # creator-pinned racial level (hit dice + racial picks), or None
        "hp_max": u.hp_max,                      # kept for pre-hunger saves / at-a-glance
        "languages": list(u.languages),          # racial + random extras
        "equipped_weapon": u.equipped_weapon,    # weapon hand (None = unarmed)
        "equipped_offhand": u.equipped_offhand,  # off hand: a torch, or None
        "equipped_tongue": u.equipped_tongue,    # Grippli Tongue slot: a 1-handed weapon, or None
        "equipped_armor": u.equipped_armor,      # body slot: armor name, or None
        "inventory": list(u._base_inventory),    # the pack: spare items, weapons included
    }


def save_game(slot, guild):
    os.makedirs(SAVE_DIR, exist_ok=True)
    payload = {
        "save_version": SAVE_VERSION,
        "battles_won": guild.battles_won,
        "reputation": dict(guild.reputation),
        "deeds_done": list(guild.deeds_done),
        "arena_challenge_day": guild.arena_challenge_day,
        "clock_seconds": guild.clock.seconds,
        "node": guild.node,
        "saved_at": time.time(),
        "squad": [u.name for u in guild.roster],
        "roster": [unit_to_dict(u) for u in guild.roster],
        "taverna_week": guild.taverna_week,
        "taverna_pool": ([unit_to_dict(u) for u in guild.taverna_pool]
                         if guild.taverna_pool is not None else None),
        "taverna_blocked": guild.taverna_blocked,
    }
    tmp = slot_path(slot) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, slot_path(slot))            # atomic: never leave a half-written slot


def load_game(slot):
    """-> Guild (roster + campaign meta). Missing keys default (old saves)."""
    with open(slot_path(slot), encoding="utf-8") as fh:
        payload = json.load(fh)
    roster = [Unit.from_save(d) for d in payload["roster"]]
    pool = payload.get("taverna_pool")
    return Guild(roster,
                 battles_won=payload.get("battles_won", 0),
                 reputation=payload.get("reputation", {}),
                 deeds_done=payload.get("deeds_done", []),
                 arena_challenge_day=payload.get("arena_challenge_day"),
                 clock=Clock(payload.get("clock_seconds", 0)),
                 node=payload.get("node"),
                 taverna_week=payload.get("taverna_week"),
                 taverna_pool=[Unit.from_save(d) for d in pool] if pool is not None else None,
                 taverna_blocked=payload.get("taverna_blocked"))


def delete_slot(slot):
    try:
        os.remove(slot_path(slot))
    except FileNotFoundError:
        pass


def slot_summaries():
    """One dict per slot for the menu: {index, empty[, squad, battles_won, saved_at]}."""
    out = []
    for i in range(NUM_SLOTS):
        try:
            with open(slot_path(i), encoding="utf-8") as fh:
                payload = json.load(fh)
            out.append({
                "index": i, "empty": False,
                "squad": payload.get("squad", []),
                "battles_won": payload.get("battles_won", 0),
                "saved_at": payload.get("saved_at", 0),
            })
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            out.append({"index": i, "empty": True})
    return out

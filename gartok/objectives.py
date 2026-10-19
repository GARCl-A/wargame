"""Guild objectives: onboarding checklist for a new guild.

A lightweight set of opening goals displayed on the Guild Screen next to
the faction deeds. Pure orientation -- no coins, fame, or mechanical rewards.
"""

from dataclasses import dataclass
from . import items


@dataclass(frozen=True)
class Objective:
    id: str
    name: str
    blurb: str


OBJECTIVES = (
    Objective(
        id="obj_buy_food",
        name="Buy Food",
        blurb="Stock rations or meals from the market or farm.",
    ),
    Objective(
        id="obj_arena_bout",
        name="Arena Bout",
        blurb="Step into the arena pit and fight a bout.",
    ),
    Objective(
        id="obj_combat_lv1",
        name="Combat Level 1",
        blurb="Raise any squad member to Combat Level 1.",
    ),
    Objective(
        id="obj_work_chain",
        name="Woodcutter's Climb",
        blurb="Work Lv 1 -> buy Axes -> Work Lv 2 chain.",
    ),
    Objective(
        id="obj_recruit_tavern",
        name="Tavern Recruit",
        blurb="Recruit a new companion at the City Tavern.",
    ),
    Objective(
        id="obj_recruit_prison",
        name="Bail Prisoner",
        blurb="Pay bail and recruit a prisoner at the City Prison.",
    ),
    Objective(
        id="obj_buy_torch",
        name="Equip a Torch",
        blurb="Buy or carry a Torch or Lantern for night travel and dungeons.",
    ),
)


def _work_chain_blurb(guild) -> str:
    roster = getattr(guild, "roster", ())
    if any(u.work_level >= 2 for u in roster):
        return "Work Lv 2 reached (completed)."
    has_axe = (
        any(u.has_item("Woodcutter's Axe") for u in roster)
        or any(
            it.name == "Woodcutter's Axe"
            for g in getattr(guild, "groups", ())
            for s in getattr(g, "stores", ())
            for it in s.inventory
        )
        or (
            hasattr(guild, "bank")
            and any(it.name == "Woodcutter's Axe" for it in guild.bank.items)
        )
    )
    if has_axe:
        return "Step 2/3: Advance to Work Lv 2 at the Lumber Yard."
    if any(u.work_level >= 1 for u in roster):
        return "Step 1/3: Buy an Axe at the Smithy or Market."
    return "Step 0/3: Work shifts at the Lumber Yard to reach Work Lv 1."


def is_done(guild, obj_id: str) -> bool:
    if obj_id in getattr(guild, "objectives_done", ()):
        return True
    roster = getattr(guild, "roster", ())
    if obj_id == "obj_arena_bout":
        return (
            getattr(guild, "battles_won", 0) > 0
            or "arena_dethrone" in getattr(guild, "deeds_done", ())
            or "arena_ribbit_brothers" in getattr(guild, "deeds_done", ())
            or getattr(guild, "arena_challenge_day", None) is not None
        )
    if obj_id == "obj_combat_lv1":
        return any(u.combat_level >= 1 for u in roster)
    if obj_id == "obj_work_chain":
        return any(u.work_level >= 2 for u in roster)
    return False


def complete(guild, obj_id: str):
    """Mark an objective completed in guild.objectives_done."""
    if not hasattr(guild, "objectives_done"):
        guild.objectives_done = []
    if obj_id not in guild.objectives_done:
        guild.objectives_done.append(obj_id)


def check_and_bank(guild):
    """Check dynamic criteria and bank any newly satisfied objectives."""
    if not hasattr(guild, "objectives_done"):
        guild.objectives_done = []
    done = set(guild.objectives_done)
    newly = []
    for obj in OBJECTIVES:
        if obj.id not in done and is_done(guild, obj.id):
            guild.objectives_done.append(obj.id)
            done.add(obj.id)
            newly.append(obj.id)
    return newly


def card_data(guild) -> dict:
    """Format objectives into a card dictionary for `reputation_panel.draw_reputation`."""
    check_and_bank(guild)
    done_set = set(getattr(guild, "objectives_done", ()))
    deeds = []
    for obj in OBJECTIVES:
        done = obj.id in done_set or is_done(guild, obj.id)
        blurb = _work_chain_blurb(guild) if obj.id == "obj_work_chain" else obj.blurb
        deeds.append((obj.name, blurb, 0, "done" if done else "open"))

    done_count = sum(1 for _, _, _, state in deeds if state == "done")
    total_count = len(deeds)

    return {
        "name": "Guild Objectives",
        "blurb": "Starter checklist to guide your guild's opening moves. No coins or fame -- simple orientation.",
        "rep": f"{done_count}/{total_count}",
        "rep_label": "done",
        "section_title": "Objectives",
        "deeds": deeds,
        "unlocks": [],
    }

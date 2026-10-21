"""Guild objectives: a checklist of small tasks that walks a new guild through what it can do.

Shown on the Guild Screen's REPUTATIONS tab above the faction deeds, all visible from day one
and taken in any order. Pure orientation -- no coins, fame, or mechanical rewards. Most are read
off the guild's state (`is_done`); the few a state cannot tell (a purchase, a treatment, a bout)
are marked by the screen where they happen (`complete`).
"""

from dataclasses import dataclass

AXE = "Axe"


@dataclass(frozen=True)
class Objective:
    id: str
    name: str
    blurb: str


OBJECTIVES = (
    Objective("obj_buy_food", "Buy Food",
              "Everyone eats one food a day. Potatoes and Meat are sold at the Farm."),
    Objective("obj_work_shift", "Earn a Wage",
              "Work a shift at the Lumber Yard or the Mine: little pay, no risk."),
    Objective("obj_buy_torch", "Carry a Light",
              "Buy a Torch or a Lantern at the Market: the dark hides foes, at night and underground."),
    Objective("obj_arena_bout", "Arena Bout",
              "Fight a bout at the Arena: you stake money, and nobody dies."),
    Objective("obj_combat_lv1", "Combat Level 1",
              "Down foes at or above your level until someone reaches Combat Level 1."),
    Objective("obj_medic", "See the Medic",
              "Have the Medic at the Apothecary treat someone wounded, sick or poisoned."),
    Objective("obj_recruit_tavern", "Tavern Recruit",
              "Recruit a new companion at the Tavern."),
    Objective("obj_recruit_prison", "Bail a Prisoner",
              "Pay a prisoner's bail at the City Prison and recruit them."),
    Objective("obj_work_chain", "Woodcutter's Climb",
              "Reach Work Lv 1, buy an Axe at the Smithy, reach Work Lv 2."),
    Objective("obj_licence", "Gather for Yourself",
              "Buy a gathering licence at the Lumber Yard or the Mine and keep what the crew finds."),
    Objective("obj_mission", "Take a Paid Job",
              "Accept a job from a giver's board; a node with work on offer says so on the map."),
    Objective("obj_two_groups", "Split the Guild",
              "Run two groups at once (the gear icon on a group's card splits it)."),
    Objective("obj_strongbox", "Rent the Strongbox",
              "Rent the Bankers' chest in the City to keep what nobody carries."),
    Objective("obj_wagon", "Take to the Road",
              "Get a wagon from the Carpenter and an animal in a Harness from the Farm's stables."),
    Objective("obj_deed", "A Faction's Deed",
              "Pull off any faction's deed; reputation opens new places, shops and jobs."),
    Objective("obj_initiation", "Into Magic",
              "Initiate someone into a magic school at its sanctuary."),
)


def _owns_axe(guild):
    holders = [*guild.roster, *(s for g in guild.groups for s in g.stores)]
    return any(u.has_item(AXE) for u in holders) or any(it.name == AXE for it in guild.bank.items)


def _work_chain_blurb(guild):
    if any(u.work_level >= 2 for u in guild.roster):
        return "Work Lv 2 reached."
    if _owns_axe(guild):
        return "Step 2/3: reach Work Lv 2 at the Lumber Yard, with your own Axe."
    if any(u.work_level >= 1 for u in guild.roster):
        return "Step 1/3: buy an Axe at the Smithy."
    return "Step 0/3: work shifts at the Lumber Yard to reach Work Lv 1."


def _initiated(unit):
    return any(school in unit.magic_sources for school in unit.rite_progress)


_CHECKS = {
    "obj_work_shift": lambda g: any(u.work_hours > 0 for u in g.roster),
    "obj_combat_lv1": lambda g: any(u.combat_level >= 1 for u in g.roster),
    "obj_work_chain": lambda g: any(u.work_level >= 2 for u in g.roster),
    "obj_licence": lambda g: bool(g.licences),
    "obj_mission": lambda g: bool(g.missions),
    "obj_two_groups": lambda g: len(g.groups) >= 2,
    "obj_strongbox": lambda g: g.bank.capacity > 0,
    "obj_wagon": lambda g: any(a.hitch for grp in g.groups for a in grp.herd),
    "obj_deed": lambda g: bool(g.deeds_done),
    "obj_initiation": lambda g: any(_initiated(u) for u in g.roster),
}


def is_done(guild, obj_id: str) -> bool:
    if obj_id in guild.objectives_done:
        return True
    check = _CHECKS.get(obj_id)
    return bool(check and check(guild))


def complete(guild, obj_id: str):
    """Mark an objective completed in guild.objectives_done."""
    if obj_id not in guild.objectives_done:
        guild.objectives_done.append(obj_id)


def check_and_bank(guild):
    """Bank every objective the guild's state now meets, so one that is met only for a while
    (two groups at once) stays done. Returns the ids newly banked."""
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
    done_set = set(guild.objectives_done)
    deeds = []
    for obj in OBJECTIVES:
        done = obj.id in done_set
        blurb = _work_chain_blurb(guild) if obj.id == "obj_work_chain" else obj.blurb
        deeds.append((obj.name, blurb, 0, "done" if done else "open"))
    done_count = sum(1 for _, _, _, state in deeds if state == "done")
    return {
        "name": "Guild Objectives",
        "blurb": "Small tasks that show what the guild can do, in any order. No coins or fame -- just a guide.",
        "rep": f"{done_count}/{len(deeds)}",
        "rep_label": "done",
        "section_title": "Objectives",
        "deeds": deeds,
        "unlocks": [],
    }

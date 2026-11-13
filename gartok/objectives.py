"""Guild objectives: a checklist of small tasks that walks a new guild through what it can do.

Shown on the Guild Screen's REPUTATIONS tab above the faction deeds, all visible from day one
and taken in any order. Pure orientation -- no coins, fame, or mechanical rewards. Most are read
off the guild's state (`is_done`); the few a state cannot tell (a purchase, a treatment, a bout)
are marked by the screen where they happen (`complete`).
"""

from dataclasses import dataclass

from . import i18n, items

AXE = "Axe"


@dataclass(frozen=True)
class Objective:
    id: str

    @property
    def name(self):
        return i18n.name("objective", self.id)

    @property
    def blurb(self):
        return i18n.desc("objective", self.id)


OBJECTIVES = tuple(Objective(i) for i in (
    "obj_buy_food",
    "obj_work_shift",
    "obj_buy_torch",
    "obj_equip_torch",
    "obj_buy_weapon",
    "obj_chop_wood",
    "obj_arena_bout",
    "obj_combat_lv1",
    "obj_medic",
    "obj_recruit_tavern",
    "obj_recruit_prison",
    "obj_work_chain",
    "obj_licence",
    "obj_mission",
    "obj_two_groups",
    "obj_strongbox",
    "obj_pack_animal",
    "obj_wagon",
    "obj_deed",
    "obj_initiation",
))


def _owns_axe(guild):
    holders = [*guild.roster, *(s for g in guild.groups for s in g.stores)]
    return any(items.is_kind(it.name, AXE) for u in holders for it in u._base_inventory) or any(items.is_kind(it.name, AXE) for it in guild.bank.items)


def _work_chain_blurb(guild):
    if any(u.work_level >= 2 for u in guild.roster):
        return i18n.t("objectives.work_lv_reached")
    if _owns_axe(guild):
        return i18n.t("objectives.step_reach_work_lv_at")
    if any(u.work_level >= 1 for u in guild.roster):
        return i18n.t("objectives.step_buy_axe_at_smithy")
    return i18n.t("objectives.step_work_shifts_at_lumber")


def _initiated(unit):
    return any(school in unit.magic_sources for school in unit.rite_progress)


_CHECKS = {
    "obj_equip_torch": lambda g: any(u.equipped_offhand in (items.TORCH_ITEM, items.LANTERN_ITEM) for u in g.roster),
    "obj_work_shift": lambda g: any(u.work_hours > 0 for u in g.roster),
    "obj_combat_lv1": lambda g: any(u.combat_level >= 1 for u in g.roster),
    "obj_work_chain": lambda g: any(u.work_level >= 2 for u in g.roster),
    "obj_licence": lambda g: bool(g.licences),
    "obj_mission": lambda g: bool(g.missions),
    "obj_two_groups": lambda g: len(g.groups) >= 2,
    "obj_strongbox": lambda g: g.bank.capacity > 0,
    "obj_pack_animal": lambda g: any(a.role for grp in g.groups for a in grp.herd),
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
    """The objectives as a card: the count done, the blurb and one row per objective."""
    check_and_bank(guild)
    done_set = set(guild.objectives_done)
    deeds = []
    for obj in OBJECTIVES:
        done = obj.id in done_set
        blurb = _work_chain_blurb(guild) if obj.id == "obj_work_chain" else obj.blurb
        deeds.append((obj.name, blurb, 0, "done" if done else "open"))
    done_count = sum(1 for _, _, _, state in deeds if state == "done")
    return {
        "name": i18n.t("objectives.guild_objectives"),
        "blurb": i18n.t("objectives.small_tasks_that_show_what"),
        "rep": f"{done_count}/{len(deeds)}",
        "rep_label": i18n.t("objectives.done"),
        "section_title": i18n.t("objectives.section"),
        "deeds": deeds,
        "unlocks": [],
    }

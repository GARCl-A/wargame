"""Stints: hours a band spends on a piece of work where it stands -- a show on the tavern stage, a visit
to the Medic, the claim's scouting, fences and hearth, a wagon mended. A stint is a `work` order with its
`task` (`order`), so `campaign.advance` runs its hours alongside every other band's order and `settle`
closes it when they are up: the guild keeps one clock, and no screen spends hours of its own. What a
stint costs up front (the fee, the bricks, the fuel, the Lumber) is taken by the place's desk as it
issues the order.
"""

from collections.abc import Callable
from dataclasses import dataclass

from . import economy, i18n, investigation, medic, orders


@dataclass(frozen=True)
class Stint:
    doing: str           # the catalog key of the band's chip on the map while the hours run
    settle: Callable     # (guild, group, order) -> the lines it says when the hours are up


def order(task, hours, crew=(), clock_hours=None, wagon=None, subject=None):
    """The `work` order for `task`: `hours` is the nominal length (what pay and XP are based on),
    `clock_hours` what the clock runs when Brisk Hands shortens it; `crew` the members it settles for."""
    if task not in STINTS:
        raise ValueError(f"no such stint: {task!r}")
    clock = hours if clock_hours is None else clock_hours
    return orders.Order("work", eta=clock, remaining=clock, hours=hours, task=task,
                        crew=tuple(u.uid for u in crew), wagon=wagon, subject=subject)


def is_stint(order):
    return order is not None and order.kind == "work" and order.task in STINTS


def doing(order):
    return i18n.t(STINTS[order.task].doing)


def settle(guild, group, order):
    return STINTS[order.task].settle(guild, group, order)


def _crew(guild, group, order):
    return [u for u in group.members if u.uid in order.crew and u in guild.roster]


def _perform(guild, group, order):
    return guild.perform_tips(_crew(guild, group, order), order.hours)


def _treat(guild, group, order):
    patients = _crew(guild, group, order)
    medic.treated(guild, patients)
    return [i18n.t("stint.treat.done", names=", ".join(u.name for u in patients))] if patients else []


def _scout(guild, group, order):
    guild.wilds_claim_scout()
    return [i18n.t("stint.scout.done")]


def _fences(guild, group, order):
    if guild.wilds_claim_fence_lumber < economy.WILDS_CLAIM_FENCE_LUMBER:
        return [i18n.t("stint.fences.short")]
    guild.wilds_claim_build_fences()
    return [i18n.t("stint.fences.done")]


def _oven(guild, group, order):
    return guild.claim_oven_built()


def _fire(guild, group, order):
    return guild.claim_fire_catch(group.members)[1]


def _wagon(guild, group, uid):
    garages = [getattr(guild.house, "garage", None), getattr(guild, "claim_garage", None)]
    pool = [*group.wagons, *(w for g in garages if g is not None for w in g.wagons)]
    return next((w for w in pool if w.uid == uid), None)


def _repair(guild, group, order):
    wagon = _wagon(guild, group, order.wagon)
    if wagon is None:
        return []
    ok, lines = guild.repair_roll(group.members, wagon)
    if ok and wagon in group.wagons:
        group.hitch_idle()
    return lines


STINTS = {
    "perform": Stint("stint.perform.doing", _perform),
    "treat": Stint("stint.treat.doing", _treat),
    "claim_scout": Stint("stint.claim_scout.doing", _scout),
    "claim_fences": Stint("stint.claim_fences.doing", _fences),
    "claim_oven": Stint("stint.claim_oven.doing", _oven),
    "claim_fire": Stint("stint.claim_fire.doing", _fire),
    "repair": Stint("stint.repair.doing", _repair),
    "ask_around": Stint("stint.ask_around.doing", lambda guild, group, order: investigation.ask(guild, group, order.subject)),
}

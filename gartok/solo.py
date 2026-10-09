"""Solo tasks: one member busy at a station while the rest of the guild acts.

The member splits off into a group of their own on a `solo` order (`Guild.send_alone`), or
the whole group waits when there is no slot to split into. When the clock runs out
`campaign.advance` calls `finish`, which pays the task out; the member is then left idle where
they stand and the player merges them back by hand. A hospital stay (`medic.admit`) and a
craft (`craft`) share this one mechanism.
"""

from . import medic, orders


def craft(guild, group, unit, recipe, hours, *, alone=True):
    """Send `unit` (of `group`) to craft `recipe` for `hours`. `alone` splits them off with only
    their own pack (else `ok` is False and nothing changes when no slot allows it); otherwise
    the whole group waits and feeds the craft from every pack. The crafting is rolled when the
    hours are done. Returns `(ok, lines)`."""
    if group.locked:
        return False, ["A group with an order in flight cannot start a craft."]
    pool = [unit] if alone else [unit] + [u for u in group.members if u is not unit]
    blocked = guild.craft_blocker(unit, recipe, pool)
    if blocked:
        return False, [blocked]
    order = orders.solo("craft", unit.uid, hours, recipe, clock_hours=hours * guild.work_speedup([unit]))
    if alone:
        if guild.send_alone(group, unit, order, f"{unit.name} (crafting)") is None:
            return False, ["No free group slot to send them alone."]
        return True, [f"{unit.name} sets to work on {recipe} for {hours} h."]
    group.order = order
    return True, [f"The group waits while {unit.name} works on {recipe} for {hours} h."]


def finish(guild, group, order):
    """The order's hours are up: settle the task. Returns the events."""
    unit = next((u for u in group.members if u.uid == order.who), None)
    if unit is None or unit not in guild.roster:
        return []
    if order.task == "hospital":
        return [medic.discharge(unit)]
    pool = [unit] + [u for u in group.members if u is not unit]
    blocked = guild.craft_blocker(unit, order.recipe, pool)
    if blocked:
        return [blocked]
    hours = int(order.hours)
    worked, made, progress = guild.craft_hours(unit, order.recipe, hours, pool)
    return guild.craft_report(unit, order.recipe, hours, worked, made, progress)

"""Solo tasks: one member busy at a station while the rest of the guild acts.

The member splits off into a group of their own on a `solo` order (`Guild.send_alone`), or
the whole group waits when there is no slot to split into. When the clock runs out
`campaign.advance` calls `finish`, which pays the task out; the member is then left idle where
they stand and the player merges them back by hand. A hospital stay (`medic.admit`) and a
craft (`craft`) share this one mechanism.
"""

from collections import Counter

from . import i18n, items, medic, orders


def craft(guild, group, unit, recipe, hours, *, alone=True):
    """Send `unit` (of `group`) to craft `recipe` for `hours`. Either way the craft is fed by the
    whole group's stock (every pack, wagon and animal). `alone` splits them off, carrying the
    recipe's tools and materials the group holds (else `ok` is False and nothing changes when no
    slot allows it); otherwise the whole group waits. The crafting is rolled when the hours are
    done. Returns `(ok, lines)`."""
    if group.locked:
        return False, [i18n.t("solo.group_with_order_in_flight")]
    pool = _stock(group, unit)
    blocked = guild.craft_blocker(unit, recipe, pool)
    if blocked:
        return False, [blocked]
    order = orders.solo("craft", unit.uid, hours, recipe, clock_hours=hours * guild.work_speedup([unit]))
    target = items.CRAFTING_RECIPES[recipe].target if recipe in items.CRAFTING_RECIPES else recipe
    if alone:
        if guild.send_alone(group, unit, order, f"{unit.name} (crafting)") is None:
            return False, [i18n.t("solo.no_free_group_slot_to")]
        _carry_along(unit, recipe, pool)
        return True, [i18n.t("solo.sets_to_work_on_for", name=unit.name, target=target, hours=hours)]
    group.order = order
    return True, [i18n.t("solo.group_waits_while_works_on", name=unit.name, target=target, hours=hours)]


def _stock(group, unit):
    """The group's stock with `unit`'s own pack first, the one a craft draws on first."""
    return [unit, *(c for c in group.carriers if c is not unit)]


def _carry_along(unit, recipe, pool):
    """A crafter leaving the group takes along, out of the group's stock, the recipe's tools
    they lack and every unlocked material it uses."""
    data = items.get_recipe(recipe)
    holders = [h for h in pool if h is not unit]
    for tool in data.tools:
        if not unit.has_item(tool):
            donor = next((h for h in holders if h.has_item(tool)), None)
            if donor is not None:
                donor.remove_named(tool)
                unit.give_to_pack(tool)
    for mat in Counter(data.materials):
        for h in holders:
            moved = h.remove_named(mat, h.unlocked_of(mat))
            if moved:
                unit.give_to_pack(mat, moved)
    unit._derive_combat()


def finish(guild, group, order):
    """The order's hours are up: settle the task. Returns the events."""
    unit = next((u for u in group.members if u.uid == order.who), None)
    if unit is None or unit not in guild.roster:
        return []
    if order.task == "hospital":
        return [medic.discharge(unit)]
    pool = _stock(group, unit)
    blocked = guild.craft_blocker(unit, order.recipe, pool)
    if blocked:
        return [blocked]
    hours = int(order.hours)
    worked, made, progress = guild.craft_hours(unit, order.recipe, hours, pool)
    return guild.craft_report(unit, order.recipe, hours, worked, made, progress)

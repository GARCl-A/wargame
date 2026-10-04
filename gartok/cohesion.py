"""Cohesion: what an overextended group costs the guild, day by day.

A group past its leader's capacity (`Group.overextension`) is tested once a
day (`daily`, called from `Guild._daily_upkeep`): the world rolls 1d20 against
the Mental Defense of the group's weakest member -- group leader and guild
leader exempt -- and a roll at or above it means they walk. With a free group
slot (`Guild.free_slots`) they just split off alone; without one they give
notice (`Guild.leaving`, uid -> the day it lapses) and, if nothing changes,
leave the guild taking what their alignment lets them. See RULES.md, "Fame and
group slots".
"""

from . import data

NOTICE_DAYS = 7


def lawfulness(alignment):
    """"Lawful" | "Neutral" | "Chaotic" -- the law axis of an alignment name."""
    return (alignment or "Neutral").split(" and ")[0]


def weakest(guild, group):
    """The member the day's roll is against: lowest Mental Defense, leaders
    exempt. None when nobody in the group can be tested."""
    pool = [u for u in group.members if u is not group.leader and u is not guild.leader]
    return min(pool, key=lambda u: u.mental_defense, default=None)


def depart(guild, unit):
    """`unit` leaves the guild for good. What they carry out the door depends
    on their law axis; everything else goes to their group's leader."""
    group = guild.group_of(unit)
    law = lawfulness(unit.alignment)
    if law not in ("Lawful", "Chaotic"):
        law = "Neutral"
    left_gold = 0 if law == "Chaotic" else unit.gold
    left_items = list(unit._base_inventory) if law == "Lawful" else []
    leader = group.leader if group is not None else None
    if leader is not None and leader is not unit:
        for entry in left_items:
            if isinstance(entry, tuple):
                leader._pack_add(*entry)
            else:
                leader._pack_add(entry)
        leader.gold += left_gold
    guild.remove_members([unit])
    if leader is not None and leader is not unit and left_items:
        leader._derive_combat()
        if group in guild.groups:
            group.distribute_load()
    took = {"Lawful": "only what they wear and wield",
            "Neutral": "their gear and pack, but no coin",
            "Chaotic": "everything they could carry"}[law]
    return f"{unit.name} leaves the guild, taking {took}."


def _resolve_notices(guild):
    events = []
    by_uid = {u.uid: u for u in guild.roster}
    for uid, due in list(guild.leaving.items()):
        unit = by_uid.get(uid)
        group = guild.group_of(unit) if unit is not None else None
        if (group is None or not group.overextension
                or unit is group.leader or unit is guild.leader):
            guild.leaving.pop(uid)
            if unit is not None:
                events.append(f"{unit.name} settles back in and drops the notice.")
            continue
        if group.locked:
            continue
        if guild.free_slots:
            guild.leaving.pop(uid)
            guild.split_group(group, [unit])
            events.append(f"{unit.name} finds room of their own and leaves {group.display_name}.")
        elif guild.clock.day >= due:
            guild.leaving.pop(uid)
            events.append(depart(guild, unit))
    return events


def _roll_groups(guild, d20):
    events = []
    noticed = {guild.group_of(u) for u in guild.roster if u.uid in guild.leaving}
    for group in list(guild.groups):
        if not group.overextension or group.locked or group in noticed:
            continue
        unit = weakest(guild, group)
        if unit is None or d20() < unit.mental_defense:
            continue
        if guild.free_slots:
            guild.split_group(group, [unit])
            events.append(f"{unit.name} can't stand the crowd and breaks away from "
                          f"{group.display_name}.")
        else:
            guild.leaving[unit.uid] = guild.clock.day + NOTICE_DAYS
            events.append(f"{unit.name} can't stand the crowd and gives notice: "
                          f"{NOTICE_DAYS} days to make room or they leave the guild.")
    return events


def daily(guild, d20=data.d20):
    """One day of cohesion: settle standing notices, then test every group
    still overextended. Returns the events to show."""
    return _resolve_notices(guild) + _roll_groups(guild, d20)

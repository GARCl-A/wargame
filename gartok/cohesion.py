"""Cohesion: what an overextended group costs the guild, day by day.

A group past its leader's capacity (`Group.overextension`) is tested once a
day (`daily`, called from `Guild._daily_upkeep`): the world rolls 1d20 against
the Mental Defense of the group's weakest member -- group leader and guild
leader exempt -- and a roll at or above it means they walk. With a free group
slot (`Guild.free_slots`) they just split off alone; without one they give
notice (`Guild.leaving`, uid -> the day it lapses) and, if nothing changes,
leave the guild taking what their alignment lets them. See RULES.md, "Fame and
group slots".

A herd past its leader's control (`Group.herd_load` over `herd_capacity`) works
the same way, with one 7-day notice per group: when it lapses and the herd is
still too big, one animal strays off and the notice restarts.
"""

from . import data, items

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
    left_coins = [] if law == "Chaotic" else [e for e in unit._base_inventory if items.is_coin(e[0])]
    left_items = ([e for e in unit._base_inventory if not items.is_coin(e[0])]
                  if law == "Lawful" else [])
    leader = group.leader if group is not None else None
    if leader is not None and leader is not unit:
        for name, qty in left_coins:
            leader.give_to_pack(name, qty)
        for entry in left_items:
            leader._pack_add(entry)
    guild.remove_members([unit])
    if leader is not None and leader is not unit and (left_items or left_coins):
        leader._derive_combat()
        if left_items and group in guild.groups:
            group.distribute_load(share_coins=False)
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


def stray(group):
    """An animal wanders off, leaving its tack and load with the group's leader.
    Untacked animals go first, then the latest bought."""
    animal = min(reversed(group.herd), key=lambda a: a.tack is not None)
    group.herd.remove(animal)
    keeper = group.leader or group.members[0]
    if animal.tack:
        keeper.give_to_pack(animal.take_tack())
    for name, qty in animal.stash.items:
        keeper.give_to_pack(name, qty)
    return f"A {animal.species} strays off: {group.display_name} cannot control that big a herd."


def herd_notices(guild):
    """Start (or drop) each group's herd notice without waiting for the daily
    sweep -- a new leader may control fewer animals. Returns the events."""
    events = []
    for group in guild.groups:
        if group.herd_load <= group.herd_capacity:
            group.herd_notice = None
        elif group.herd_notice is None:
            group.herd_notice = guild.clock.day + NOTICE_DAYS
            events.append(f"{group.display_name} has more animals than it can control: "
                          f"{NOTICE_DAYS} days before one strays.")
    return events


def _herds(guild):
    events = herd_notices(guild)
    today = guild.clock.day
    for group in guild.groups:
        if group.herd_notice is not None and today >= group.herd_notice:
            events.append(stray(group))
            group.herd_notice = today + NOTICE_DAYS if group.herd_load > group.herd_capacity else None
    return events


def daily(guild, d20=data.d20):
    """One day of cohesion: settle standing notices, then test every group
    still overextended. Returns the events to show."""
    return _resolve_notices(guild) + _roll_groups(guild, d20) + _herds(guild)

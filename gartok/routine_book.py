"""The Book of routines: how many groups the guild may leave on a routine at once.

Same shape as the group slots (`Guild.group_slots`): fame buys seats, and a seat is taken by every group
holding a routine, stopped or running. The player starts with none. The engine (`routines.assign`) knows
nothing of seats; the player's way in is `assign` here."""

from . import routines

BASE_SLOTS = 0          # a new guild automates nothing
FAME_PER_SLOT = 6       # total reputation that buys one more group on a routine


def slots(guild):
    return BASE_SLOTS + guild.fame // FAME_PER_SLOT


def used(guild):
    return sum(1 for g in guild.groups if g.routine is not None)


def fame_to_next_slot(guild):
    return FAME_PER_SLOT - guild.fame % FAME_PER_SLOT


def assign(guild, group, routine):
    """Put `routine` on an idle `group` if a seat is free. Returns the log lines."""
    if group.routine is None and used(guild) >= slots(guild):
        raise ValueError("no free automation slot")
    return routines.assign(guild, group, routine)

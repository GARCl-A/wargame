"""Crime, jurisdiction and the guard: a personal record (`Unit.crime`, per
character, not per guild) that can catch up with someone in a place the City's
authority reaches (`world.Node.jurisdiction`).

The test is the same idiom `data.DEATH_SAVE_MIN` already uses: `d20() + crime
>= GUARD_CHECK_MIN`, a flat 50% base that climbs in a straight line with the
rap sheet, no separate probability system. A clean record (`crime == 0`) never
rolls -- it can't hit 11 with a d20 alone.

`campaign.advance` runs the test on every group that arrives at a jurisdiction
node (waypoint or final stop, travelling internally within the city included)
and, if it catches someone, pauses that group on a "guard" `Order` for
`justice_screen.GuardScreen` to play out. The whole catch (everyone caught in
that one test, if more than one) resolves as a single decision -- the group
can't do two different things with itself at once:

- **prison** (`jail`): each caught unit's own days (`prison_days`, off the
  crime it had at the moment of arrest) served in `Guild.jailed` -- the same
  "off every `Group` but still on the books" trick `Guild.taverna_pool` uses,
  so upkeep/saves keep seeing it. `release_due` (called once a day from
  `Guild._daily_upkeep`) frees whoever's time is up, back into a group at the
  City.
- **fight** (`patrol_pack` / `resolve_fight_crime`): a real, lethal battle
  through the normal pipeline (`campaign.absorb_battle`) against a patrol
  scaled to the crime that got someone caught -- winning does not clear the
  slate, it adds to it (see `resolve_fight_crime`).
- **flee**: no rules live here -- `campaign.resolve_guard_flee` just moves the
  group back to wherever it came from.

`PRISON_DAYS_PER_CRIME` and `PATROL_LEVEL_CAP`/`PATROL_SIZE` are placeholders
(the plan doc flags them as such) -- tune once this has actually been played.
"""

import random

from . import data, encounters, world
from .group import Group

GUARD_CHECK_MIN = 11        # d20 + crime >= this: same 50%-base idiom as data.DEATH_SAVE_MIN
PRISON_DAYS_PER_CRIME = 2   # placeholder -- tune once this has been played
PATROL_LEVEL_CAP = 6        # placeholder -- a patrol never scales past this mean level
PATROL_SIZE = 2             # guards fielded against a caught unit


def guard_test(unit):
    """True if the guard catches `unit` right now. A clean record never
    rolls -- `crime == 0` can't reach `GUARD_CHECK_MIN` off a d20 alone. Uses
    `data.d20()` straight (like every other check in the game) rather than an
    injected rng, so `tests.helpers.fixed_d20` pins it the same way it does a
    death save."""
    return unit.crime > 0 and data.d20() + unit.crime >= GUARD_CHECK_MIN


def catch(group):
    """Members of `group` the guard catches right now, in member order. Only
    meaningful at a jurisdiction node -- callers check that first."""
    return [u for u in group.members if guard_test(u)]


def prison_days(crime):
    return crime * PRISON_DAYS_PER_CRIME


def jail(guild, unit):
    """Book `unit`: crime resets to 0, a release day is banked, and it leaves
    whatever `Group` it's standing in for `guild.jailed` (the rest of that
    group stays free -- see the module docstring). Returns the days served,
    computed off the crime it had *before* the reset."""
    days = prison_days(unit.crime)
    unit.crime = 0
    guild.jailed.append((unit, guild.clock.day + days))
    guild.remove_members([unit])
    return days


def release_due(guild):
    """Free everyone whose sentence is up, into a group at the City -- an
    existing one standing there, or a fresh solo group if none is. Called
    once a day from `Guild._daily_upkeep`. Returns the released units."""
    due = [pair for pair in guild.jailed if guild.clock.day >= pair[1]]
    if not due:
        return []
    guild.jailed = [pair for pair in guild.jailed if guild.clock.day < pair[1]]
    released = [u for u, _ in due]
    city_group = next((g for g in guild.groups if g.node == world.START_NODE), None)
    for u in released:
        if city_group is None:
            city_group = Group([u], node=world.START_NODE)
            guild.groups.append(city_group)
        else:
            guild.add_member(u, city_group)
    guild._sync_leadership()
    return released


def patrol_level(crime):
    return min(PATROL_LEVEL_CAP, crime)


def patrol_pack(crime, rng=random):
    """The lethal patrol a caught unit's crime scales up against the group --
    reuses the same scaled-enemy core every other fight in the game does."""
    level = patrol_level(crime)
    return [encounters.build_enemy(level, rng) for _ in range(PATROL_SIZE)]


def resolve_fight_crime(unit, outcome):
    """`unit` survived the fight with the patrol: +1 for having brawled with
    the guard at all, plus one more per guard `outcome.player_kos` put down.
    Only units the arrest actually caught bank crime this way -- whoever else
    in the group joined the brawl doesn't (the design doc leaves this open;
    it's the simplest default, and keeps crime tied to who the law was after)."""
    unit.crime += 1 + outcome.player_kos

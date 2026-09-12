"""Missions: paid, time-boxed jobs offered by an NPC at a node -- distinct from
a `factions.Deed` (a silent, one-shot condition that just banks reputation, no
giver, no deadline, no reward). A `Mission` names who wants what, how much it
pays, and how long the guild has to deliver it.

Scoped to the **unit** who accepted it, not the `Group` (`group.py`) they were
standing in at the time -- a group is reshuffled by splits and merges
constantly (see `group.py`'s own docstring), so pinning a mission to one would
strand it the moment that exact group stopped existing. Instead the mission
travels with its unit: `progress`/`turn_in` always resolve *that unit's current
group* (`guild.group_of`, the same trick the shared food larder uses) and count
the whole group's packs -- the unit "shares" the job with whoever it is
grouped with right now, not just whoever it was grouped with at the tanner's
stall.

`TEMPLATES` is hand-grown like `factions._FACTIONS`'s deed lists -- a mission
is what a place wants, authored, not rolled.
"""

from dataclasses import dataclass

from . import factions, world


@dataclass(frozen=True)
class MissionTemplate:
    id: str
    giver: str            # who offers it, e.g. "tanner"
    node: str              # world node id where it's offered and turned in
    name: str
    blurb: str
    goal_item: str
    goal_qty: int
    reward: int             # copper, split evenly across the current group
    deadline_days: int      # in-game days from acceptance to the deadline
    tag: str                # topic a bankers.Deed can key off, e.g. "economic"


@dataclass
class Mission:
    template_id: str
    unit_uid: str           # who accepted it -- see the module docstring
    accepted_day: int
    deadline_day: int
    state: str = "active"    # active | done | failed


TANNER_HIDES = MissionTemplate(
    "tanner_hides", "tanner", "city", "Fifteen Hides",
    "The tanner wants 15 sqm of hide off anything with fur. The Wilds is "
    "thick with it, if you can bring down what's wearing it.",
    goal_item="1sqm Hide", goal_qty=15, reward=200, deadline_days=5,
    tag="economic",
)

TEMPLATES = {TANNER_HIDES.id: TANNER_HIDES}


def offers_at(guild, node_id):
    """Templates offered at `node_id` the guild doesn't already have active --
    a giver only ever has one job out at a time (done or failed, they'll hand
    out another)."""
    active_ids = {m.template_id for m in guild.missions if m.state == "active"}
    return [t for t in TEMPLATES.values()
            if t.node == node_id and t.id not in active_ids]


def template_of(mission):
    return TEMPLATES[mission.template_id]


def accept(guild, unit, template):
    m = Mission(template.id, unit.uid, guild.clock.day,
               guild.clock.day + template.deadline_days)
    guild.missions.append(m)
    return m


def _current_group(guild, mission):
    """Wherever `mission`'s unit is standing right now, or None if it's no
    longer on the roster (permadeath -- the deal died with them)."""
    unit = next((u for u in guild.roster if u.uid == mission.unit_uid), None)
    return guild.group_of(unit) if unit is not None else None


def progress(guild, mission):
    """How many of the goal item the unit's *current* group is carrying."""
    group = _current_group(guild, mission)
    if group is None:
        return 0
    item = template_of(mission).goal_item
    return sum(u._base_inventory.count(item) for u in group.members)


def can_turn_in(guild, mission):
    return (mission.state == "active"
            and progress(guild, mission) >= template_of(mission).goal_qty)


def turn_in(guild, mission):
    """Consume `goal_qty` of the goal item off the current group's packs and
    split the reward evenly across its members. Call `can_turn_in` first --
    raises if the group can't cover the goal. Returns the `factions.Deed`s a
    bankers-style "economic job done" event just banked, for the caller to
    show alongside the payout."""
    if not can_turn_in(guild, mission):
        raise ValueError("mission goal not met")
    t = template_of(mission)
    group = _current_group(guild, mission)
    left = t.goal_qty
    for u in group.members:
        while left > 0 and t.goal_item in u._base_inventory:
            u._base_inventory.remove(t.goal_item)
            left -= 1
    n = len(group.members)
    base, rem = divmod(t.reward, n)
    for i, u in enumerate(group.members):
        u.gold += base + (1 if i < rem else 0)
    mission.state = "done"
    return factions.settle(guild, factions.Event(
        "mission", node=world.node(t.node), tag=t.tag))


def expire_overdue(guild):
    """Fail every active mission whose deadline has passed -- called once a
    day from `Guild._daily_upkeep`. Returns the ones that just failed, for the
    caller to report."""
    failed = []
    for m in guild.missions:
        if m.state == "active" and guild.clock.day > m.deadline_day:
            m.state = "failed"
            failed.append(m)
    return failed


def mission_to_dict(m):
    return {"template_id": m.template_id, "unit_uid": m.unit_uid,
            "accepted_day": m.accepted_day, "deadline_day": m.deadline_day,
            "state": m.state}


def mission_from_dict(d):
    return Mission(d["template_id"], d["unit_uid"], d["accepted_day"],
                   d["deadline_day"], d.get("state", "active"))

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

from . import chest, data, factions, world


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
    starting_item: str | None = None   # handed to the signer's pack the moment they accept


@dataclass
class Mission:
    template_id: str
    unit_uid: str           # who accepted it -- see the module docstring
    accepted_day: int
    deadline_day: int
    state: str = "active"    # active | done | failed
    ambush_done: bool = False   # the trust mission's fortress ambush: fires once (campaign.py)


TANNER_HIDES = MissionTemplate(
    "tanner_hides", "tanner", "city", "Fifteen Hides",
    "The tanner wants 15 sqm of hide off anything with fur. The Wilds is "
    "thick with it, if you can bring down what's wearing it.",
    goal_item="1sqm Hide", goal_qty=15, reward=200, deadline_days=5,
    tag="economic",
)

# The Bankers' trust mission: accepting hands over a sealed chest
# (`starting_item`) instead of asking the guild to gather anything; the
# "goal" delivered back here is the letter Ledger Hold trades for it intact
# (`ledger_screen.py`) -- `turn_in`'s ordinary goal_item/goal_qty count works
# unchanged, it just counts a letter instead of hides. No copper reward: the
# point is the trust, not the pay (see factions.py's `bankers_trust` deed).
TRUST_CHEST = MissionTemplate(
    "bankers_trust_chest", "bankers", "city", "A Test of Trust",
    "The Bankers want proof the guild can be trusted with something precious "
    "before they'll vouch for it: carry a sealed chest to their outpost at "
    "Ledger Hold, safe, and bring back their letter of receipt. Don't peek.",
    goal_item=data.LETTER_ITEM, goal_qty=1, reward=0, deadline_days=7,
    tag="trust", starting_item=data.MISSION_CHEST_ITEM,
)

APOTHECARY_MUSHROOMS = MissionTemplate(
    "apothecary_mushrooms", "apothecary", "city", "Fifteen Red Mushrooms",
    "The apothecary needs 15 red mushrooms to brew more potions. They grow in the Wilds.",
    goal_item="Red Mushroom", goal_qty=15, reward=150, deadline_days=10,
    tag="apothecary",
)

LIBRARY_DICTIONARY = MissionTemplate(
    "library_dictionary", "library", "city", "A New Translation",
    "The library wants a dictionary to expand its archives. Any language will do.",
    goal_item="Any Dictionary", goal_qty=1, reward=250, deadline_days=15,
    tag="library",
)

TEMPLATES = {
    TANNER_HIDES.id: TANNER_HIDES, 
    TRUST_CHEST.id: TRUST_CHEST,
    APOTHECARY_MUSHROOMS.id: APOTHECARY_MUSHROOMS,
    LIBRARY_DICTIONARY.id: LIBRARY_DICTIONARY,
}


def offers_at(guild, node_id):
    """Templates offered at `node_id` the guild hasn't ever accepted --
    these missions are one-offs (not repeatable)."""
    seen_ids = {m.template_id for m in guild.missions}
    return [t for t in TEMPLATES.values()
            if t.node == node_id and t.id not in seen_ids]


def template_of(mission):
    return TEMPLATES[mission.template_id]


def accept(guild, unit, template):
    m = Mission(template.id, unit.uid, guild.clock.day,
               guild.clock.day + template.deadline_days)
    guild.missions.append(m)
    if template.starting_item:
        unit.give_to_pack(template.starting_item)
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
    if item == "Any Dictionary":
        return sum(sum(qty for name, qty in u._base_inventory if name.startswith("Dictionary of ")) for u in group.members)
    return sum(u.count_of(item) for u in group.members)


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
        if left <= 0:
            break
        if t.goal_item == "Any Dictionary":
            for name, qty in list(u._base_inventory):
                if name.startswith("Dictionary of ") and left > 0:
                    left -= u.remove_named(name, min(left, qty))
        else:
            left -= u.remove_named(t.goal_item, left)
    n = len(group.members)
    base, rem = divmod(t.reward, n)
    for i, u in enumerate(group.members):
        u.gold += base + (1 if i < rem else 0)
    mission.state = "done"
    return factions.settle(guild, factions.Event(
        "mission", node=world.node(t.node), tag=t.tag))


def _active_trust_mission(guild):
    return next((m for m in guild.missions
                if m.template_id == TRUST_CHEST.id and m.state == "active"), None)


def open_mission_chest(guild, unit):
    """Pick the trust mission's own `data.MISSION_CHEST_ITEM` instead of
    handing it over intact -- same lock, same odds as any other chest
    (`chest.roll_lock`), but a hit doesn't quietly pay out: it fails whichever
    trust mission that chest belonged to right now and marks the opener a
    criminal (`Unit.crime`), so it can never become the `bankers_trust` deed.
    A miss costs nothing, same as every other chest. Returns `(opened, gems)`,
    `(False, 0)` if `unit` isn't carrying one."""
    if not unit.has_item(data.MISSION_CHEST_ITEM):
        return False, 0
    gems = chest.roll_lock(unit)
    if gems is None:
        return False, 0
    unit.remove_named(data.MISSION_CHEST_ITEM)
    if gems:
        unit.give_to_pack(data.GEM_ITEM, gems)
    mission = _active_trust_mission(guild)
    if mission is not None:
        mission.state = "failed"
    unit.crime += 1
    return True, gems


def pending_fortress_ambush(guild, group):
    """The trust mission's fortress ambush is due right now if: a trust
    mission is active and hasn't sprung it yet, and someone in `group` is
    still carrying the sealed chest (nothing to ambush for once it's already
    been handed over or opened). Returns the `Mission` to mark `ambush_done`
    on, or None -- called from `campaign.py`'s arrival check."""
    mission = _active_trust_mission(guild)
    if mission is None or mission.ambush_done:
        return None
    if not any(u.has_item(data.MISSION_CHEST_ITEM) for u in group.members):
        return None
    return mission


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
            "state": m.state, "ambush_done": m.ambush_done}


def mission_from_dict(d):
    return Mission(d["template_id"], d["unit_uid"], d["accepted_day"],
                   d["deadline_day"], d.get("state", "active"),
                   d.get("ambush_done", False))

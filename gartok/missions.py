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

from . import chest, data, factions, items, recorder, talents, world


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
    deadline_days: int | None   # days from acceptance; None = no deadline
    tags: tuple[str, ...] = ()
    tag: str | None = None
    starting_item: str | None = None   # handed to the signer's pack the moment they accept
    requires: str | None = None        # template id that must be done before this one is offered
    retry_days: int | None = None      # a failed run is offered again this many days after the failure
    reward_recipe: str | None = None   # a crafting recipe every member of the delivering group learns
    reveals: tuple[str, ...] = ()      # hidden nodes the turn-in shows on the map
    returns_goal: bool = False         # the goal item is handed back after the turn-in
    exclusive: str | None = None       # a set only one template of which can ever be done
    goal_captive: str | None = None    # the goal is a captive (its NPC slug), not an item

    def __post_init__(self):
        tags_val = self.tags
        tag_val = self.tag
        if isinstance(tags_val, str):
            tags_val = (tags_val,)
            if not tag_val:
                tag_val = tags_val[0]
        elif not tags_val and tag_val:
            tags_val = (tag_val,)
        elif tags_val and not tag_val:
            tag_val = tags_val[0]
        object.__setattr__(self, "tags", tuple(tags_val) if tags_val else ())
        object.__setattr__(self, "tag", tag_val or (tags_val[0] if tags_val else ""))


@dataclass
class Mission:
    template_id: str
    unit_uid: str           # who accepted it -- see the module docstring
    accepted_day: int
    deadline_day: int | None
    state: str = "active"    # active | done | failed
    ambush_done: bool = False   # the one-shot ambush the mission springs (fortress, Biwolf): fires once
    failed_day: int | None = None   # clock.day it failed, for `MissionTemplate.retry_days`
    recruit_uid: str | None = None


TANNER_HIDES = MissionTemplate(
    "tanner_hides", "tanner", "tanner", "Fifteen Hides",
    "The tanner wants 15 sqm of hide off anything with fur. The Wilds is "
    "thick with it, if you can bring down what's wearing it.",
    goal_item="1sqm Hide", goal_qty=15, reward=200, deadline_days=5,
    tags=("economic", "tanner", "hides"), retry_days=7,
)

# The Biwolf is not on any road: he comes to the smell of meat, at night, to a
# hunt in the Wilds (`hunt.biwolf_lure`). His leather is the goal; with no
# deadline, it is open until delivered -- or failed for good the moment the
# leather is lost (`fail_if_leather_lost`).
TANNER_BIWOLF = MissionTemplate(
    "tanner_biwolf", "tanner", "tanner", "The Biwolf's Hide",
    "The tanner has heard of a wolf the size of a cart that hunts the Wilds by "
    "night. It follows the smell of meat -- hunt after dark with fifteen "
    "portions in your packs and it will find you, and its pack with it. Bring "
    "me its leather.",
    goal_item=items.BIWOLF_LEATHER_ITEM, goal_qty=1, reward=0, deadline_days=None,
    tags=("economic", "tanner", "biwolf"), requires="tanner_hides",
)

# The Bankers' trust mission: accepting hands over a sealed chest
# (`starting_item`) instead of asking the guild to gather anything; the
# "goal" delivered back here is the letter Ledger Hold trades for it intact
# (`ledger_screen.py`) -- `turn_in`'s ordinary goal_item/goal_qty count works
# unchanged, it just counts a letter instead of hides. No copper reward: the
# point is the trust, not the pay (see factions.py's `bankers_trust` deed).
# Aurochs, the immortal ox, is the chain's end: found only by tracking him in the
# Ox Fields (`ox.py`), which the Country Roads show only while this job is out.
# Same rule as the Biwolf's leather: lose the hide after the kill and it fails
# for good (`fail_if_hide_lost`). The pay is double the hides', plus the recipe.
TANNER_OX = MissionTemplate(
    "tanner_ox", "tanner", "tanner", "The Immortal Ox",
    "The tanner tells of Aurochs, an ox that has outlived every hunter sent after it, "
    "grazing the fertile fields south of the farm. Its hide is the finest there is. "
    "Bring it to me and I will teach you what the horn is good for.",
    goal_item=items.THUNDERHIDE_ITEM, goal_qty=1, reward=2 * TANNER_HIDES.reward, deadline_days=None,
    tags=("economic", "tanner", "ox"), requires="tanner_biwolf",
    reward_recipe="Signal Horn",
)

TRUST_CHEST = MissionTemplate(
    "bankers_trust_chest", "bankers", "city", "A Test of Trust",
    "The Bankers want proof the guild can be trusted with something precious "
    "before they'll vouch for it: carry a sealed chest to their outpost at "
    "Ledger Hold, safe, and bring back their letter of receipt. Don't peek.",
    goal_item=data.LETTER_ITEM, goal_qty=1, reward=0, deadline_days=7,
    tags=("trust", "bankers"), starting_item=data.MISSION_CHEST_ITEM,
)

APOTHECARY_MUSHROOMS = MissionTemplate(
    "apothecary_mushrooms", "apothecary", "apothecary", "Fifteen Red Mushrooms",
    "The apothecary needs 15 red mushrooms to brew more potions. They grow in the Wilds.",
    goal_item="Red Mushroom", goal_qty=15, reward=150, deadline_days=10,
    tags=("economic", "apothecary"),
)

LIBRARY_DICTIONARY = MissionTemplate(
    "library_dictionary", "library", "library", "A New Translation",
    "The library wants a dictionary to expand its archives. Dictionaries currently in our shop catalog will not be accepted.",
    goal_item="Any Dictionary", goal_qty=1, reward=250, deadline_days=15,
    tags=("library", "scholarly"),
)

LIBRARY_ANCIENT_CODEX = MissionTemplate(
    "library_ancient_codex", "library", "library", "The Lost Codex",
    "Legends speak of an ancient subterranean library buried off the Old Road. "
    "Delve into the forgotten ruins and retrieve the Ancient Codex.",
    goal_item=data.CODEX_ITEM, goal_qty=1, reward=500, deadline_days=20,
    tags=("library", "ruins"),
    reveals=("blood_sanctuary", "nature_grove", "faith_cathedral"), returns_goal=True,
)


def _codex_delivery(school, node, name, blurb):
    return MissionTemplate(
        f"{school}_codex", school, node, name, blurb,
        goal_item=data.CODEX_ITEM, goal_qty=1, reward=0, deadline_days=None,
        tags=("magic", school, "codex"), requires=LIBRARY_ANCIENT_CODEX.id, exclusive="codex",
    )


CODEX_BLOOD = _codex_delivery(
    "blood", "blood_sanctuary", "The Codex for the Blood",
    "The blood mages have waited for the Ancient Codex. There is only one: give it to us, "
    "and the other schools will never read it.")
CODEX_NATURE = _codex_delivery(
    "nature", "nature_grove", "The Codex for the Green",
    "The grove asks for the Ancient Codex. There is only one: leave it with us, "
    "and the other schools will never read it.")
CODEX_FAITH = _codex_delivery(
    "faith", "faith_cathedral", "The Codex for the Faith",
    "The cathedral asks for the Ancient Codex. There is only one: entrust it to us, "
    "and the other schools will never read it.")
CODEX_DELIVERIES = (CODEX_BLOOD, CODEX_NATURE, CODEX_FAITH)

# The Snake Dragon (`serpent_nest.py`): one beast, wanted dead by one school and alive by another.
SNAKE_SLUG = "snake_dragon"
BLOOD_SNAKE = MissionTemplate(
    "blood_snake", "blood", "blood_sanctuary", "The Dragon's Blood",
    "A snake with dragon blood in it nests near the Lumber Yard -- search the yard for its den. "
    "Bring us its body: the blood is read in the flesh, and the cult would read it.",
    goal_item=items.SNAKE_DRAGON_CORPSE_ITEM, goal_qty=1, reward=0, deadline_days=None,
    tags=("magic", "blood", SNAKE_SLUG), exclusive=SNAKE_SLUG, requires=LIBRARY_ANCIENT_CODEX.id,
)
NATURE_SNAKE = MissionTemplate(
    "nature_snake", "nature", "nature_grove", "The Snake Saved",
    "A snake with dragon blood in it nests near the Lumber Yard -- search the yard for its den. "
    "Something has twisted it, a curse perhaps. Bring it to us alive, bound with rope or chain, "
    "and the grove will tend it.",
    goal_item="Snake Dragon", goal_qty=1, reward=0, deadline_days=None,
    tags=("magic", "nature", SNAKE_SLUG), exclusive=SNAKE_SLUG, goal_captive=SNAKE_SLUG,
    requires=LIBRARY_ANCIENT_CODEX.id,
)
SNAKE_HUNTS = (BLOOD_SNAKE, NATURE_SNAKE)

LEDGER_TREEFOLK = MissionTemplate(
    "ledger_treefolk", "ledger_hold", "ledger_hold", "Treefolk Mentorship",
    "Commander Varkas of Ledger Hold entrusts your guild with a green Treefolk recruit. "
    "Train them on the road until they master their racial roots (racial level 2) and return them to the garrison.",
    goal_item="Treefolk Recruit", goal_qty=1, reward=230, deadline_days=None,
    tags=("guards", "ledger_hold", "mentorship"),
)

TEMPLATES = {
    TANNER_HIDES.id: TANNER_HIDES,
    TANNER_BIWOLF.id: TANNER_BIWOLF,
    TANNER_OX.id: TANNER_OX,
    TRUST_CHEST.id: TRUST_CHEST,
    APOTHECARY_MUSHROOMS.id: APOTHECARY_MUSHROOMS,
    LIBRARY_DICTIONARY.id: LIBRARY_DICTIONARY,
    LIBRARY_ANCIENT_CODEX.id: LIBRARY_ANCIENT_CODEX,
    **{t.id: t for t in CODEX_DELIVERIES},
    **{t.id: t for t in SNAKE_HUNTS},
    LEDGER_TREEFOLK.id: LEDGER_TREEFOLK,
}


def offers_at(guild, node_id):
    """Templates offered at `node_id` the guild hasn't ever accepted --
    these missions are one-offs (not repeatable), except a failed one with
    `retry_days`, offered again once that many days have passed."""
    out = []
    for t in TEMPLATES.values():
        if t.node != node_id or not _open_to_take(guild, t):
            continue
        if t.id == "library_ancient_codex" and "library_initiate" not in guild.deeds_done:
            continue
        if t.id == "ledger_treefolk" and "bankers_trust" not in guild.deeds_done:
            continue
        if closed(guild, t):
            continue
        if t.requires and not any(m.template_id == t.requires and m.state == "done"
                                  for m in guild.missions):
            continue
        out.append(t)
    return out


def board(guild, giver, node_id):
    """The jobs a giver's board shows at `node_id`: those out now, then those on offer;
    when there are none, the last one the guild took (so a finished board reads
    "JOB COMPLETED" and not empty)."""
    mine = [t for t in TEMPLATES.values() if t.giver == giver and t.node == node_id]
    out = {m.template_id for m in guild.missions if m.state == "active"}
    on_offer = {t.id for t in offers_at(guild, node_id)}
    shown = [t for t in mine if t.id in out] + [t for t in mine if t.id in on_offer and t.id not in out]
    shown += [t for t in mine if closed(guild, t) and t not in shown]
    if shown:
        return shown
    taken = [t for t in mine if any(m.template_id == t.id for m in guild.missions)]
    return taken[-1:]


def closed(guild, template):
    """`template` can never be done: another of its exclusive set already was."""
    return template.exclusive is not None and any(
        m.state == "done" and m.template_id != template.id
        and TEMPLATES[m.template_id].exclusive == template.exclusive for m in guild.missions)


def _runs(guild, template):
    return [m for m in guild.missions if m.template_id == template.id]


def retry_in(guild, template):
    """Days until a failed `template` with `retry_days` can be taken again, 0 if it
    can now, None if it never will (no retry, or not failed)."""
    runs = _runs(guild, template)
    if template.retry_days is None or not runs or any(m.state != "failed" for m in runs):
        return None
    last = max(m.failed_day if m.failed_day is not None else guild.clock.day for m in runs)
    return max(0, last + template.retry_days - guild.clock.day)


def _open_to_take(guild, template):
    return not _runs(guild, template) or retry_in(guild, template) == 0


def template_of(mission):
    return TEMPLATES[mission.template_id]


def accept(guild, unit, template):
    deadline = None if template.deadline_days is None else guild.clock.day + template.deadline_days
    m = Mission(template.id, unit.uid, guild.clock.day, deadline)
    guild.missions.append(m)
    recorder.emit("mission", what="accept", id=template.id, reward=template.reward, deadline=template.deadline_days)
    if template.starting_item:
        unit.give_to_pack(template.starting_item)
    return m


def _current_group(guild, mission):
    """Wherever `mission`'s unit is standing right now, or None if it's no
    longer on the roster (permadeath -- the deal died with them)."""
    unit = next((u for u in guild.roster if u.uid == mission.unit_uid), None)
    return guild.group_of(unit) if unit is not None else None


def days_left(guild, mission):
    """Days until the deadline, or None for a mission that has none."""
    if mission.deadline_day is None:
        return None
    return mission.deadline_day - guild.clock.day


def _held(unit, item):
    """`item` in the pack, plus the one worn in the artifact slot: a turn-in
    counts an artifact the signer already put on."""
    return unit.count_of(item) + (unit.equipped_artifact == item)


def progress(guild, mission):
    """How many of the goal item the unit's *current* group is carrying."""
    group = _current_group(guild, mission)
    if group is None:
        return 0
    t = template_of(mission)
    if t.id == "ledger_treefolk":
        recruit = next((u for u in guild.roster if u.uid == mission.recruit_uid), None)
        if recruit is not None and recruit in group.members and recruit.racial_level >= 2:
            return 1
        return 0
    if t.goal_captive:
        return sum(1 for c in group.captives if c.npc_slug == t.goal_captive)
    item = t.goal_item
    if item == "Any Dictionary":
        from .library_screen import library_stock_dictionaries
        stock = set(library_stock_dictionaries(guild))
        return sum(sum(qty for name, qty in u._base_inventory if name.startswith("Dictionary of ") and name not in stock) for u in group.members)
    return sum(_held(u, item) for u in group.members)


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
    if t.id == "ledger_treefolk":
        recruit = next((u for u in guild.roster if u.uid == mission.recruit_uid), None)
        if recruit is not None:
            return deliver_treefolk_recruit(guild, group, mission, recruit)
    left = t.goal_qty
    if t.goal_captive:
        for cap in [c for c in group.captives if c.npc_slug == t.goal_captive][:left]:
            group.captives.remove(cap)
            left -= 1
    for u in group.members:
        if left <= 0:
            break
        if t.goal_item == "Any Dictionary":
            from .library_screen import library_stock_dictionaries
            stock = set(library_stock_dictionaries(guild))
            for name, qty in list(u._base_inventory):
                if name.startswith("Dictionary of ") and name not in stock and left > 0:
                    left -= u.remove_named(name, min(left, qty))
        else:
            left -= u.remove_named(t.goal_item, left)
            if left > 0 and u.equipped_artifact == t.goal_item:
                u.take_from_artifact()
                left -= 1
    if t.returns_goal:
        group.members[0].give_to_pack(t.goal_item, t.goal_qty)
    for node_id in t.reveals:
        guild.reveal_node(node_id)
    n = len(group.members)
    base, rem = divmod(t.reward, n)
    for i, u in enumerate(group.members):
        u.money += base + (1 if i < rem else 0)
    mission.state = "done"
    for other in guild.missions:
        if other.state == "active" and closed(guild, template_of(other)):
            other.state, other.failed_day = "failed", guild.clock.day
    if t.reward_recipe:
        for u in group.members:
            if t.reward_recipe not in u.recipes:
                u.recipes.append(t.reward_recipe)
    recorder.emit("mission", what="turn_in", id=t.id, reward=t.reward)
    return factions.settle(guild, factions.Event(
        "mission", node=world.node(t.node), tag=t.tag, tags=t.tags))


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


def _active(guild, template):
    return next((m for m in guild.missions
                 if m.template_id == template.id and m.state == "active"), None)


def pending_snake(guild):
    """A Snake Dragon job is out: the nest can be searched for from the Lumber Yard."""
    return next((m for t in SNAKE_HUNTS if (m := _active(guild, t)) is not None), None)


def snake_wanted_alive(guild):
    """The Nature Coven's job is out: the squad means to take the Snake Dragon alive."""
    return _active(guild, NATURE_SNAKE) is not None


def pending_biwolf(guild):
    """The Biwolf job, if it is active and has not sprung its ambush yet --
    the Mission to mark `ambush_done` on (`hunt.biwolf_pack`), else None."""
    mission = _active(guild, TANNER_BIWOLF)
    return None if mission is None or mission.ambush_done else mission


def pending_ox(guild):
    """The ox job, while Aurochs still walks: active and not yet slain
    (`slay_ox`). It is what shows the Ox Fields and lets the party track him."""
    mission = _active(guild, TANNER_OX)
    return None if mission is None or mission.ambush_done else mission


def slay_ox(guild):
    """Aurochs fell: the trail is closed for good (`ambush_done`)."""
    mission = _active(guild, TANNER_OX)
    if mission is not None:
        mission.ambush_done = True


def _item_held(guild, item):
    if any(_held(u, item) for u in guild.roster):
        return True
    return (guild.bank.count_of(item) + guild.house.stash.count_of(item)) > 0


def _fail_if_lost(guild, template):
    mission = _active(guild, template)
    if mission is None or not mission.ambush_done or _item_held(guild, template.goal_item):
        return None
    mission.state = "failed"
    mission.failed_day = guild.clock.day
    return mission


def fail_if_leather_lost(guild):
    """After the Biwolf's ambush is over: if the leather is nowhere in the guild
    (left on the field, never dropped), the job fails for good -- there is no
    second ambush. Returns the failed Mission, else None."""
    return _fail_if_lost(guild, TANNER_BIWOLF)


def fail_if_hide_lost(guild):
    """Same for Aurochs: once he is slain, a hide that is nowhere in the guild
    fails the job for good. Returns the failed Mission, else None."""
    return _fail_if_lost(guild, TANNER_OX)


def expire_overdue(guild):
    """Fail every active mission whose deadline has passed -- called once a
    day from `Guild._daily_upkeep`. Returns the ones that just failed, for the
    caller to report."""
    failed = []
    for m in guild.missions:
        if m.state == "active" and m.deadline_day is not None and guild.clock.day > m.deadline_day:
            m.state = "failed"
            m.failed_day = guild.clock.day
            failed.append(m)
    return failed


def mission_to_dict(m):
    return {"template_id": m.template_id, "unit_uid": m.unit_uid,
            "accepted_day": m.accepted_day, "deadline_day": m.deadline_day,
            "state": m.state, "ambush_done": m.ambush_done,
            "failed_day": m.failed_day, "recruit_uid": m.recruit_uid}


def mission_from_dict(d):
    return Mission(d["template_id"], d["unit_uid"], d["accepted_day"],
                   d["deadline_day"], d["state"], d["ambush_done"], d.get("failed_day"),
                   d.get("recruit_uid"))


def make_treefolk_recruit():
    """Create the designated level 0 Treefolk recruit for the Ledger Hold mentorship quest."""
    from . import names
    from .unit import Unit
    race_row = next(r for r in data.RACES if r[1] == "Treefolk")
    race_dict = data._race_dict(*race_row)
    unit = Unit("player", race=race_dict, name=names.random_name())
    unit.base_attributes = {
        "strength": 13,
        "dexterity": 11,
        "constitution": 12,
        "intelligence": 10,
        "wisdom": 10,
        "charisma": 11,
    }
    unit.money = 0
    unit._apply_attributes()
    unit.combat_xp = 0
    unit.work_hours = 0
    unit._level_hp_rolls = []
    unit.magic_xp = 0
    unit.talents = {t: [] for t in talents.TRACKS}
    unit.portrait_file = "treefolk_recruit.png"
    unit.portrait_id = "treefolk_recruit.png"
    unit._derive_combat()
    return unit


def accept_treefolk_mentorship(guild, unit, recruit):
    """Start the Treefolk mentorship mission, binding the recruit to the quest."""
    t = LEDGER_TREEFOLK
    m = Mission(t.id, unit.uid, guild.clock.day, deadline_day=None, recruit_uid=recruit.uid)
    guild.missions.append(m)
    recorder.emit("mission", what="accept", id=t.id, reward=t.reward, deadline=None)
    return m


def deliver_treefolk_recruit(guild, group, mission, recruit):
    """Complete the mentorship: strip recruit gear and return to group stores,
    pay $230 reward, release recruit to garrison, bank deed and faction standing."""
    other_members = [m for m in group.members if m.uid != recruit.uid]
    recipient = other_members[0] if other_members else None

    items_to_return = []
    for slot in ("equipped_weapon", "equipped_offhand", "equipped_armor", "equipped_artifact", "equipped_tongue"):
        item = getattr(recruit, slot, None)
        if item:
            items_to_return.append((item, 1))
            setattr(recruit, slot, None)
    for inst in list(recruit.inventory):
        items_to_return.append((inst.name, inst.qty))
    recruit.inventory.clear()

    if recipient is not None:
        for name, qty in items_to_return:
            recipient.give_to_pack(name, qty)
        recipient._derive_combat()
    elif group.wagons:
        for name, qty in items_to_return:
            group.wagons[0].stash.add(name, qty)

    t = template_of(mission)
    reward = t.reward
    if other_members:
        per, rem = divmod(reward, len(other_members))
        for i, u in enumerate(other_members):
            u.give_to_pack("Copper Coin", per + (1 if i < rem else 0))
    elif group.wagons:
        group.wagons[0].stash.add("Copper Coin", reward)

    guild.remove_members([recruit])
    mission.state = "done"
    recorder.emit("mission", what="turn_in", id=mission.template_id, reward=reward)
    return factions.settle(guild, factions.Event("mission", node=world.node("ledger_hold"), tags=t.tags, tag="ledger_hold"))


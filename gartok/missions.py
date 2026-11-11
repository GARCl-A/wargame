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

from . import chest, data, factions, i18n, items, recorder, talents, world


@dataclass(frozen=True)
class MissionTemplate:
    id: str
    giver: str            # who offers it, e.g. "tanner"
    node: str              # world node id where it's offered and turned in
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
    starting_qty: int = 1              # how many `starting_item`s are handed over
    starting_once: bool = False        # the starting items come with the first run only, not a retry
    fight_at: str | None = None        # the goal is a fight won at this node, not a turn-in
    reward_items: tuple[str, ...] = ()   # handed to the first member of the delivering group at the turn-in
    goal_any: tuple[str, ...] = ()     # the goal is `goal_qty` of these items in any mix (`goal_item` is only the board's icon)
    min_day: int = 0                   # not offered before this day of the campaign
    needs_revealed: str | None = None  # not offered until this hidden node is on the guild's map

    @property
    def name(self):
        return i18n.name("mission", self.id)

    @property
    def blurb(self):
        return i18n.desc("mission", self.id)

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
    escapes: int = 0            # times the Biwolf got away from his ambush: each one makes the next harder


TANNER_HIDES = MissionTemplate(
    "tanner_hides", "tanner", "tanner",
    goal_item="1sqm Hide", goal_qty=15, reward=200, deadline_days=5,
    tags=("economic", "tanner", "hides"), retry_days=7,
)

# The Biwolf is not on any road: he comes to the smell of meat, at night, to a
# hunt in the Wilds (`hunt.biwolf_lure`). His leather is the goal; with no
# deadline, it is open until delivered -- or failed for good the moment the
# leather is lost (`fail_if_leather_lost`).
TANNER_BIWOLF = MissionTemplate(
    "tanner_biwolf", "tanner", "tanner",
    goal_item=items.BIWOLF_LEATHER_ITEM, goal_qty=1, reward=0, deadline_days=None,
    tags=("economic", "tanner", "biwolf"), requires="tanner_hides",
)

# The Bankers' trust mission: accepting hands over a sealed chest
# (`starting_item`) instead of asking the guild to gather anything; the
# "goal" delivered back here is the letter Field Command trades for it intact
# (`ledger.py`) -- `turn_in`'s ordinary goal_item/goal_qty count works
# unchanged, it just counts a letter instead of hides. No copper reward: the
# point is the trust, not the pay (see factions.py's `bankers_trust` deed).
# Aurochs, the immortal ox, is the chain's end: found only by tracking him in the
# Ox Fields (`ox.py`), which the Country Roads show only while this job is out.
# Same rule as the Biwolf's leather: lose the hide after the kill and it fails
# for good (`fail_if_hide_lost`). The pay is double the hides', plus the recipe.
TANNER_OX = MissionTemplate(
    "tanner_ox", "tanner", "tanner",
    goal_item=items.THUNDERHIDE_ITEM, goal_qty=1, reward=2 * TANNER_HIDES.reward, deadline_days=None,
    tags=("economic", "tanner", "ox"), requires="tanner_biwolf",
    reward_recipe="Signal Horn",
)

TRUST_CHEST = MissionTemplate(
    "bankers_trust_chest", "bankers", "city",
    goal_item=data.LETTER_ITEM, goal_qty=1, reward=0, deadline_days=7,
    tags=("trust", "bankers"), starting_item=data.MISSION_CHEST_ITEM,
)

APOTHECARY_MUSHROOMS = MissionTemplate(
    "apothecary_mushrooms", "apothecary", "apothecary",
    goal_item="Red Mushroom", goal_qty=15, reward=150, deadline_days=10,
    tags=("economic", "apothecary"),
)

# Pays no coin: the recipe paper is studied at the tavern like a level-0 spell (`magic.recipe_for_paper`).
APOTHECARY_VENOM = MissionTemplate(
    "apothecary_venom", "apothecary", "apothecary",
    goal_item=items.VENOM_GLAND_ITEM, goal_qty=3, reward=0, deadline_days=60,
    tags=("apothecary", "venom"), requires=APOTHECARY_MUSHROOMS.id,
    goal_any=(items.VENOM_GLAND_ITEM, items.SNAKE_VENOM_GLAND_ITEM),
    reward_items=(items.ANTIDOTE_RECIPE_ITEM, items.ANTIDOTE_ITEM),
)

LIBRARY_DICTIONARY = MissionTemplate(
    "library_dictionary", "library", "library",
    goal_item="Any Dictionary", goal_qty=1, reward=250, deadline_days=15,
    tags=("library", "scholarly"),
)

LIBRARY_ANCIENT_CODEX = MissionTemplate(
    "library_ancient_codex", "library", "library",
    goal_item=data.CODEX_ITEM, goal_qty=1, reward=500, deadline_days=20,
    tags=("library", "ruins"),
    reveals=("blood_sanctuary", "nature_grove", "faith_cathedral"), returns_goal=True,
)


def _codex_delivery(school, node):
    return MissionTemplate(
        f"{school}_codex", school, node,
        goal_item=data.CODEX_ITEM, goal_qty=1, reward=0, deadline_days=None,
        tags=("magic", school, "codex"), requires=LIBRARY_ANCIENT_CODEX.id, exclusive="codex",
    )


CODEX_BLOOD = _codex_delivery(
    "blood", "blood_sanctuary")
CODEX_NATURE = _codex_delivery(
    "nature", "nature_grove")
CODEX_FAITH = _codex_delivery(
    "faith", "faith_cathedral")
CODEX_DELIVERIES = (CODEX_BLOOD, CODEX_NATURE, CODEX_FAITH)

# The Snake Dragon (`serpent_nest.py`): one beast, wanted dead by one school and alive by another.
SNAKE_SLUG = "snake_dragon"
BLOOD_SNAKE = MissionTemplate(
    "blood_snake", "blood", "blood_sanctuary",
    goal_item=items.SNAKE_DRAGON_CORPSE_ITEM, goal_qty=1, reward=0, deadline_days=None,
    tags=("magic", "blood", SNAKE_SLUG), exclusive=SNAKE_SLUG, requires=LIBRARY_ANCIENT_CODEX.id,
)
NATURE_SNAKE = MissionTemplate(
    "nature_snake", "nature", "nature_grove",
    goal_item="Snake Dragon", goal_qty=1, reward=0, deadline_days=None,
    tags=("magic", "nature", SNAKE_SLUG), exclusive=SNAKE_SLUG, goal_captive=SNAKE_SLUG,
    requires=LIBRARY_ANCIENT_CODEX.id,
)
SNAKE_HUNTS = (BLOOD_SNAKE, NATURE_SNAKE)

# The Faith Order's errand of mercy: its medics' potions go with the group to the border war
# (`battlefield.py`). Done the moment the fight is won with every soldier alive; a soldier lost,
# a lost fight or a missed week fails it, and the Order asks again two weeks later -- with no
# fresh potions.
FAITH_BATTLEFIELD = MissionTemplate(
    "faith_battlefield", "faith", "faith_cathedral",
    goal_item="Minor Healing Potion", goal_qty=1,       # goal_item: only the board's icon here
    reward=0, deadline_days=7,
    tags=("magic", "faith", "battlefield"), requires=LIBRARY_ANCIENT_CODEX.id,
    starting_item="Minor Healing Potion", starting_qty=6, starting_once=True,
    retry_days=14, fight_at="battlefield",
)

# The Faith Order's second (`necromancer.py`): the dead at the front will not stay down. Done the
# moment the necromancer falls, whatever happens after; the soldiers do not matter this time. A lost
# fight or a missed deadline fails it, and the Order asks again two weeks later.
FAITH_NECROMANCER = MissionTemplate(
    "faith_necromancer", "faith", "faith_cathedral",
    goal_item="Holy Symbol", goal_qty=1,                  # goal_item: only the board's icon here
    reward=0, deadline_days=14,
    tags=("magic", "faith", "necromancer"), requires=FAITH_BATTLEFIELD.id,
    retry_days=14, fight_at="battlefield",
)

# The Nature Coven's third (`wildfire.py`): an Ogre's goblins set the Wilds on fire. Taking it puts
# the foci and the Great Focus on the map; it is done the moment the Ogre is talked round or beaten,
# and fails on the event's last day with the Ogre still unbeaten.
WILDFIRE_DAYS = 14
NATURE_WILDFIRE = MissionTemplate(
    "nature_wildfire", "nature", "nature_grove",
    goal_item="Scroll of Water Jet", goal_qty=1,          # goal_item: only the board's icon here
    reward=0, deadline_days=WILDFIRE_DAYS,
    tags=("magic", "nature", "wildfire"), requires=LIBRARY_ANCIENT_CODEX.id, fight_at="wilds",
)

# The Blood Cult's third (`lair.py`): a dragon sleeps under the Mine, and the Cult wants its eggs.
# Open to all; done when one egg is handed over, the rest are the guild's to sell.
BLOOD_CLUTCH = MissionTemplate(
    "blood_clutch", "blood", "blood_sanctuary",
    goal_item=items.DRAGON_EGG_ITEM, goal_qty=1, reward=0, deadline_days=None,
    tags=("magic", "blood", "dragon_clutch"), requires=LIBRARY_ANCIENT_CODEX.id,
    reward_items=("Scroll of Dragonfire",),
)

LEDGER_TREEFOLK = MissionTemplate(
    "ledger_treefolk", "ledger_hold", "ledger_hold",
    goal_item="Treefolk Recruit", goal_qty=1, reward=230, deadline_days=None,
    tags=("guards", "ledger_hold", "mentorship"),
)

# The Farmer's (`docs/plans/holy_symbol_quest.md`): Edric Ashvale's daughter went to the Cathedral and sent
# no word. The release switch keeps the whole quest dark (the job, the Farm's tab, the closed shop) until
# the author flips it.
FARMER_QUEST_LIVE = False
FARMER_DAUGHTER = MissionTemplate(
    "farmer_daughter", "farmer", "farm",
    goal_item="Farmer's Daughter", goal_qty=1, reward=300, deadline_days=20,
    tags=("farm", "rescue"), goal_captive="farmers_daughter",
    reward_items=(items.HOLY_SYMBOL_ITEM,), min_day=30, needs_revealed="faith_cathedral",
)

TEMPLATES = {
    TANNER_HIDES.id: TANNER_HIDES,
    TANNER_BIWOLF.id: TANNER_BIWOLF,
    TANNER_OX.id: TANNER_OX,
    TRUST_CHEST.id: TRUST_CHEST,
    APOTHECARY_MUSHROOMS.id: APOTHECARY_MUSHROOMS,
    APOTHECARY_VENOM.id: APOTHECARY_VENOM,
    LIBRARY_DICTIONARY.id: LIBRARY_DICTIONARY,
    LIBRARY_ANCIENT_CODEX.id: LIBRARY_ANCIENT_CODEX,
    **{t.id: t for t in CODEX_DELIVERIES},
    **{t.id: t for t in SNAKE_HUNTS},
    FAITH_BATTLEFIELD.id: FAITH_BATTLEFIELD,
    FAITH_NECROMANCER.id: FAITH_NECROMANCER,
    NATURE_WILDFIRE.id: NATURE_WILDFIRE,
    BLOOD_CLUTCH.id: BLOOD_CLUTCH,
    LEDGER_TREEFOLK.id: LEDGER_TREEFOLK,
    FARMER_DAUGHTER.id: FARMER_DAUGHTER,
}


def offers_at(guild, node_id):
    """Templates offered at `node_id` the guild hasn't ever accepted --
    these missions are one-offs (not repeatable), except a failed one with
    `retry_days`, offered again once that many days have passed."""
    out = []
    for t in TEMPLATES.values():
        if t.node != node_id or not _open_to_take(guild, t):
            continue
        if t is FARMER_DAUGHTER and not FARMER_QUEST_LIVE:
            continue
        if guild.clock.day < t.min_day or (t.needs_revealed and t.needs_revealed not in guild.revealed):
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


def shop_closed(guild, node_id):
    """The text of why `node_id`'s shop sells nothing right now, or None when it is open: the Farm, while
    Edric waits for his daughter."""
    if node_id == FARMER_DAUGHTER.node and FARMER_QUEST_LIVE and any(
            m.template_id == FARMER_DAUGHTER.id and m.state == "active" for m in guild.missions):
        return i18n.t("shop_tab.closed_grief")
    return None


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
    first = not _runs(guild, template)
    m = Mission(template.id, unit.uid, guild.clock.day, deadline)
    guild.missions.append(m)
    recorder.emit("mission", what="accept", id=template.id, reward=template.reward, deadline=template.deadline_days)
    if template.starting_item and (first or not template.starting_once):
        unit.give_to_pack(template.starting_item, template.starting_qty)
    if template is NATURE_WILDFIRE:
        from . import wildfire
        wildfire.start(guild)
    return m


def _current_group(guild, mission):
    """Wherever `mission`'s unit is standing right now, or None if it's no
    longer on the roster (a save from before `Guild.remove_members` handed
    the deal on)."""
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
    if t.fight_at:
        return 0
    if t.goal_captive:
        return sum(1 for c in group.captives if c.npc_slug == t.goal_captive)
    item = t.goal_item
    if item == "Any Dictionary":
        from .trade import library_stock_dictionaries
        stock = set(library_stock_dictionaries(guild))
        return sum(sum(qty for name, qty in u._base_inventory if name.startswith("Dictionary of ") and name not in stock) for u in group.members)
    if t.goal_any:
        return sum(_held(u, name) for u in group.members for name in t.goal_any) + sum(
            s.count_of(name) for s in group.stores for name in t.goal_any)
    return (sum(_held(u, item) for u in group.members)
            + sum(s.count_of(item) for s in group.stores))


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
        raise ValueError(i18n.t("missions.goal_not_met"))
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
    names = t.goal_any or (t.goal_item,)
    for u in group.members:
        if left <= 0:
            break
        if t.goal_item == "Any Dictionary":
            from .trade import library_stock_dictionaries
            stock = set(library_stock_dictionaries(guild))
            for name, qty in list(u._base_inventory):
                if name.startswith("Dictionary of ") and name not in stock and left > 0:
                    left -= u.remove_named(name, min(left, qty))
        else:
            for name in names:
                left -= u.remove_named(name, left)
                if left > 0 and u.equipped_artifact == name:
                    u.take_from_artifact()
                    left -= 1
    if t.goal_item != "Any Dictionary":
        for store in group.stores:
            for name in names:
                if left > 0:
                    left -= store.remove_named(name, left)
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
    for name in t.reward_items:
        group.members[0].give_to_pack(name)
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


def active(guild, template):
    """The run of `template` out now, or None."""
    return next((m for m in guild.missions
                 if m.template_id == template.id and m.state == "active"), None)


def pending_snake(guild):
    """A Snake Dragon job is out: the nest can be searched for from the Lumber Yard."""
    return next((m for t in SNAKE_HUNTS if (m := active(guild, t)) is not None), None)


def pending_clutch(guild):
    """The Dragon's Clutch is out: the lair can be searched for from the Mine."""
    return active(guild, BLOOD_CLUTCH)


def snake_wanted_alive(guild):
    """The Nature Coven's job is out: the squad means to take the Snake Dragon alive."""
    return active(guild, NATURE_SNAKE) is not None


def pending_battlefield(guild, group):
    """The Faith Order's errand, when `group` is the one carrying it (its signer is a member):
    the Battlefield's skirmish is open to that group. Else None."""
    return _held_by(guild, FAITH_BATTLEFIELD, group)


def settle_battlefield(guild, mission, won, lost):
    """The skirmish is over: `won` the fight, `lost` the soldiers who died. Done (and the
    Faith Order's deed) only on a win with nobody lost; any other end fails it, open again
    after `retry_days`. -> (notice, deeds banked)."""
    if won and not lost:
        mission.state = "done"
        recorder.emit("mission", what="turn_in", id=mission.template_id, reward=0)
        t = template_of(mission)
        deeds = factions.settle(guild, factions.Event(
            "mission", node=world.node(t.node), tag=t.tag, tags=t.tags))
        return i18n.t("missions.front.won"), deeds
    mission.state, mission.failed_day = "failed", guild.clock.day
    if lost:
        names = ", ".join(c.name for c in lost)
        why = i18n.t("missions.front.lost_men", names=names)
    else:
        why = i18n.t("missions.front.line_broke")
    return i18n.t("missions.front.failed", why=why, days=template_of(mission).retry_days), []


def _held_by(guild, template, group):
    """`template`'s run out now when its signer is in `group`, else None."""
    m = active(guild, template)
    return m if m is not None and any(u.uid == m.unit_uid for u in group.members) else None


def pending_necromancer(guild, group):
    """The Faith Order's hunt for the necromancer, when `group` carries it. Else None."""
    return _held_by(guild, FAITH_NECROMANCER, group)


def pending_front(guild, group):
    """Either Faith errand at the Battlefield that `group` carries (the skirmish opens for it)."""
    return pending_battlefield(guild, group) or pending_necromancer(guild, group)


def settle_necromancer(guild, mission, fallen):
    """The fight at the front is over: `fallen` = the necromancer went down in it. Done (and the
    Faith Order's deed) when he did; else failed, open again after `retry_days`.
    -> (notice, deeds banked)."""
    if fallen:
        mission.state = "done"
        recorder.emit("mission", what="turn_in", id=mission.template_id, reward=0)
        t = template_of(mission)
        deeds = factions.settle(guild, factions.Event(
            "mission", node=world.node(t.node), tag=t.tag, tags=t.tags))
        return i18n.t("missions.necromancer.won"), deeds
    mission.state, mission.failed_day = "failed", guild.clock.day
    return i18n.t("missions.necromancer.failed", days=template_of(mission).retry_days), []


def settle_wildfire(guild, mission):
    """The Ogre is talked round or beaten: the Coven's errand is done. -> deeds banked."""
    mission.state = "done"
    recorder.emit("mission", what="turn_in", id=mission.template_id, reward=0)
    t = template_of(mission)
    return factions.settle(guild, factions.Event("mission", node=world.node(t.node), tag=t.tag, tags=t.tags))


def pending_biwolf(guild):
    """The Biwolf job, if it is active and he has not fallen yet (`settle_biwolf`), else None."""
    mission = active(guild, TANNER_BIWOLF)
    return None if mission is None or mission.ambush_done else mission


def settle_biwolf(guild, escaped):
    """The Biwolf's ambush is over. If he got away (`escaped`: he still stood, or ran off the
    map) the job stays open and his next ambush is harder (`escapes`, `hunt.biwolf_pack`); once he
    is down the ambush is spent, and a leather nowhere in the guild fails the job for good.
    -> the failed Mission, else None."""
    mission = active(guild, TANNER_BIWOLF)
    if mission is None:
        return None
    if escaped:
        mission.escapes += 1
        return None
    mission.ambush_done = True
    return fail_if_leather_lost(guild)


def pending_ox(guild):
    """The ox job, while Aurochs still walks: active and not yet slain
    (`slay_ox`). It is what shows the Ox Fields and lets the party track him."""
    mission = active(guild, TANNER_OX)
    return None if mission is None or mission.ambush_done else mission


def slay_ox(guild):
    """Aurochs fell: the trail is closed for good (`ambush_done`)."""
    mission = active(guild, TANNER_OX)
    if mission is not None:
        mission.ambush_done = True


def _item_held(guild, item):
    if any(_held(u, item) for u in guild.roster):
        return True
    if any(s.count_of(item) for g in guild.groups for s in g.stores):
        return True
    return (guild.bank.count_of(item) + guild.house.stash.count_of(item)) > 0


def _fail_if_lost(guild, template):
    mission = active(guild, template)
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
            "failed_day": m.failed_day, "recruit_uid": m.recruit_uid, "escapes": m.escapes}


def mission_from_dict(d):
    return Mission(d["template_id"], d["unit_uid"], d["accepted_day"],
                   d["deadline_day"], d["state"], d["ambush_done"], d.get("failed_day"),
                   d.get("recruit_uid"), d.get("escapes", 0))


def make_treefolk_recruit():
    """Create the designated level 0 Treefolk recruit for the Field Command mentorship quest."""
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


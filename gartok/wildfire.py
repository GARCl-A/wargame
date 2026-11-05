"""The Ogre's Wildfire: the Nature Coven's third errand, and the game's first ethereal nodes.

An Ogre leads a goblin band into the Wilds to clear a clearing for his fortress, and they have no
idea how to burn it: every fire they set runs wild. Accepting the job (`missions.NATURE_WILDFIRE`)
puts four nodes on the map at once (`world.add_node`), an hour off The Wilds and an hour off each
other: three small foci and the Great Focus, where the fortress goes up.

- **A small focus** holds a goblin crew and its Hobgoblin foreman. Teach them (CHA, then INT, the
  player picks who rolls) and it is out; a failed check sets them on you. Beat them and the fire
  still burns: putting it out is 16 hours and an INT check (`put_out`, a `work` order with
  `task="put_out"`). Left `BURN_DAYS` days, it burns that stretch of forest and two new foci start
  beside it, linked where it was and an hour farther.
- **The Great Focus** is the Ogre's fortress going up (`fortress_scenario.py`). Talk him round (the
  same chain, harder, easier for every focus already taught) or beat him: either ends the errand.
- **Day `DAYS`** after the acceptance every focus still burning is lost and gone. With the Ogre
  still unbeaten the errand fails and his fortress stands for good, hostile: more ambushes on a
  hunt, and a fight waiting there. Talked round, it stands friendly.

Every focus that burns costs The Wilds `MEAT_LOSS` of its meat for good (`meat_mult`).

The state is `Guild.wildfire` (a `Wildfire`, saved with the guild); `sync_world` puts its nodes
back on the map after a load.
"""

import random
from dataclasses import dataclass, field

from . import data, encounters, factions, i18n, missions, world

DAYS = 14
BURN_DAYS = 7
LINK = 1                      # hours between the Wilds, the foci and the Great Focus
SPREAD = 2                    # foci a burnt one starts
FOCUS_DC = 13
OGRE_DC = 15
PUT_OUT_DC = 13
PUT_OUT_HOURS = 16
MEAT_LOSS = 0.05
CREW = 3                      # goblins at a small focus, beside the foreman
ESCORT = 5                    # goblins and hobgoblins at the Great Focus, beside the Ogre
HOLD_ESCORT = 7               # ... at the finished fortress, once it stands
FOREMAN_EDGE = 1              # the foreman is this many levels over the squad
ESCORT_LEVEL = 6              # the escort's level, whatever the squad's
HOLD_AMBUSH_MULT = 1.5        # a hunt in the Wilds while the hostile fortress stands
HOLD_GOBLIN_ODDS = 0.5        # ... and how often the pack that finds you is its goblins
OGRE_SLUG = "ogre"
GREAT_ID = "wildfire_great"
REWARD = "Scroll of Water Jet"
FORTRESS_ID = "ogre_fortress"
CHECKS = ("charisma", "intelligence")


@dataclass
class Focus:
    id: str
    links: dict                      # node id -> distance (hours at a walk)
    spawn_day: int
    pos: tuple
    great: bool = False
    talk: int = 0                    # checks of the chain passed (2 = taught)
    hostile: bool = False            # a check failed: they fight
    cleared: bool = False            # the crew is beaten: the fire is left to put out

    @property
    def name(self):
        return i18n.t("wildfire.great_focus") if self.great else i18n.t("wildfire.wildfire", rsplit=self.id.rsplit('_', 1)[-1])


@dataclass
class Wildfire:
    start_day: int
    foci: list = field(default_factory=list)
    seq: int = 0
    taught: int = 0
    burned: int = 0
    over: bool = False
    fortress: str | None = None      # None | "friendly" | "hostile"
    fortress_pos: tuple | None = None

    def focus(self, node_id):
        return next((f for f in self.foci if f.id == node_id), None)

    @property
    def great(self):
        return next((f for f in self.foci if f.great), None)


# --------------------------------------------------------------------------- #
# the map                                                                      #
# --------------------------------------------------------------------------- #

def _node(focus):
    if focus.great:
        return world.Node(focus.id, focus.name, "town", focus.pos,
                          blurb=i18n.t("wildfire.felled_trees_ring_of_half"),
                          functions=("ogre_fight",))
    return world.Node(focus.id, focus.name, "town", focus.pos,
                      blurb=i18n.t("wildfire.clearing_on_fire_goblins_feed"),
                      functions=("camp_fight",))


def _fortress_node(state):
    if state.fortress == "friendly":
        return world.Node(FORTRESS_ID, "The Ogre's Fortress", "town", state.fortress_pos,
                          blurb=i18n.t("wildfire.stone_walls_in_clearing_that"),
                          language="Jotun", alignment="Chaotic and Neutral", functions=("shop",),
                          vendors={"shop": world.Vendor("Grumbold the Builder", "Ogre", "chieftain", "ogre.png",
                                                        line=i18n.t("wildfire.big_walls_big_axes_little"))})
    return world.Node(FORTRESS_ID, "The Ogre's Fortress", "town", state.fortress_pos,
                      blurb=i18n.t("wildfire.black_stumps_for_mile_round"), functions=("ogre_fight",))


def sync_world(guild):
    """Put the guild's ethereal nodes back on the map (after a load, or a new guild)."""
    world.clear_runtime()
    state = guild.wildfire
    if state is None:
        return
    if state.fortress is not None:
        world.add_node(_fortress_node(state), [("wilds", LINK)])
    great = state.great
    if great is not None:
        world.add_node(_node(great), [(k, v) for k, v in great.links.items() if world.exists(k)])
    for f in state.foci:
        if not f.great:
            world.add_node(_node(f), [(k, v) for k, v in f.links.items() if world.exists(k)])


def start(guild):
    """The errand is taken: the foci and the Great Focus appear, an hour off The Wilds."""
    day = guild.clock.day
    state = Wildfire(start_day=day)
    wilds = world.node("wilds").pos
    city = world.node("city").pos
    gpos = world.free_spot(wilds, away=city, seed=day)
    great = Focus(GREAT_ID, {"wilds": LINK}, day, gpos, great=True)
    world.add_node(_node(great), list(great.links.items()))
    state.foci.append(great)
    for _ in range(3):
        _spawn(state, {"wilds": LINK, GREAT_ID: LINK}, day, near=wilds, away=city)
    guild.wildfire = state
    return state


def _spawn(state, links, day, near, away):
    state.seq += 1
    nid = f"wildfire_focus_{state.seq}"
    f = Focus(nid, dict(links), day, world.free_spot(near, away=away, seed=day * 31 + state.seq))
    world.add_node(_node(f), [(k, v) for k, v in links.items() if world.exists(k)])
    state.foci.append(f)
    return f


def _vacate(guild, node_id):
    """A node is gone: whoever stood there walks back to The Wilds, whoever was walking to it
    stops where they are."""
    notes = []
    for g in guild.groups:
        order = g.order
        heading = order is not None and order.kind == "travel" and (
            order.dest == node_id or node_id in order.path)
        if g.node == node_id:
            g.node = "wilds"
            g.order = None
            notes.append(i18n.t("wildfire.fire_took_clearing_back_to", display_name=g.display_name))
        elif heading:
            g.order = None
            notes.append(i18n.t("wildfire.clearing_ahead_is_gone_march", display_name=g.display_name))
    return notes


def _remove(guild, state, focus):
    state.foci.remove(focus)
    notes = _vacate(guild, focus.id)
    world.remove_node(focus.id)
    return notes


def _burn(guild, state, focus, spread):
    """`focus` burned through: the forest pays, and (`spread`) two new foci start beside it."""
    state.burned += 1
    notes = [i18n.t("wildfire.burned_through_stretch_of_wilds", name=focus.name)]
    near = focus.pos
    links = {k: v + LINK for k, v in focus.links.items()}
    notes += _remove(guild, state, focus)
    if spread and not focus.great:
        for _ in range(SPREAD):
            child = _spawn(state, links, guild.clock.day, near=near, away=world.node("wilds").pos)
            notes.append(i18n.t("wildfire.fire_jumps_on_is_burning", name=child.name))
    return notes


def daily(guild):
    """A new day: a focus left `BURN_DAYS` burns and spreads; on day `DAYS` the event ends."""
    state = guild.wildfire
    if state is None or state.over:
        return []
    day = guild.clock.day
    if day >= state.start_day + DAYS:
        return _end(guild, state)
    notes = []
    for f in [f for f in state.foci if not f.great and day >= f.spawn_day + BURN_DAYS]:
        notes += _burn(guild, state, f, spread=True)
    return notes


def _end(guild, state):
    state.over = True
    notes = []
    for f in [f for f in state.foci if not f.great]:
        notes += _burn(guild, state, f, spread=False)
    great = state.great
    if great is not None:
        pos = great.pos
        notes += _burn(guild, state, great, spread=False)
        state.fortress, state.fortress_pos = "hostile", pos
        world.add_node(_fortress_node(state), [("wilds", LINK)])
        m = mission(guild)
        if m is not None:
            m.state, m.failed_day = "failed", guild.clock.day
        notes.append(i18n.t("wildfire.ogre_s_fortress_stands_ringed"))
    notes.append(i18n.t("wildfire.wildfires_are_over_burned_wilds", burned=state.burned, round=round(meat_mult(guild) * 100)))
    return notes


# --------------------------------------------------------------------------- #
# what a group can do there                                                    #
# --------------------------------------------------------------------------- #

def mission(guild):
    return missions.active(guild, missions.NATURE_WILDFIRE)


def focus_at(guild, node_id):
    state = guild.wildfire
    return state.focus(node_id) if state is not None else None


def talk_dc(guild, focus):
    if focus.great:
        return OGRE_DC - guild.wildfire.taught
    return FOCUS_DC


def can_talk(focus):
    return not focus.hostile and not focus.cleared and focus.talk < len(CHECKS)


def next_check(focus):
    return CHECKS[focus.talk]


def talk(guild, focus, unit, rng=random):
    """`unit` rolls the next check of the chain. -> (passed, notice). Passing the last one
    resolves the focus; failing any sets the camp on the group (the caller starts the fight)."""
    attr = next_check(focus)
    dc = talk_dc(guild, focus)
    mod = getattr(unit, f"mod_{attr}")
    nat = rng.randint(1, 20)
    total = nat + mod
    roll = i18n.t("wildfire.d_vs_dc", nat=nat, mod=mod, upper=attr[:3].upper(), total=total, dc=dc)
    who = i18n.t("wildfire.ogre") if focus.great else i18n.t("wildfire.foreman")
    if total < dc:
        focus.hostile = True
        return False, i18n.t("wildfire.cannot_reach_they_reach_for", name=unit.name, who=who, roll=roll)
    focus.talk += 1
    if focus.talk < len(CHECKS):
        return True, i18n.t("wildfire.gets_hearing_from_now_show", name=unit.name, who=who, roll=roll)
    return True, i18n.t("wildfire.shows_how_it_is_done", name=unit.name, who=who, roll=roll) + _taught(guild, focus)


def _taught(guild, focus):
    state = guild.wildfire
    if focus.great:
        pos = focus.pos
        _remove(guild, state, focus)
        state.fortress, state.fortress_pos = "friendly", pos
        world.add_node(_fortress_node(state), [("wilds", LINK)])
        return i18n.t("wildfire.ogre_builds_it_right_without") + _done(guild)
    state.taught += 1
    _remove(guild, state, focus)
    return i18n.t("wildfire.goblins_smother_fire_and_keep")


def put_out(guild, group, rng=random):
    """A put-out order ran its hours: the best mind of the group rolls INT. -> notices."""
    focus = focus_at(guild, group.node)
    if focus is None or not focus.cleared:
        return []
    if not group.members:
        return []
    unit = max(group.members, key=lambda u: u.mod_intelligence)
    nat = rng.randint(1, 20)
    total = nat + unit.mod_intelligence
    roll = i18n.t("wildfire.d_int_vs_dc", nat=nat, mod_intelligence=unit.mod_intelligence, total=total, put_out_dc=PUT_OUT_DC)
    if nat != 20 and (nat == 1 or total < PUT_OUT_DC):
        return [i18n.t("wildfire.leads_work_but_fire_is", name=unit.name, roll=roll)]
    _remove(guild, guild.wildfire, focus)
    return [i18n.t("wildfire.leads_work_and_is_out", name=unit.name, other=focus.name, roll=roll)]


def settle_fight(guild, node_id, won):
    """A fight at a focus, the Great Focus or the standing fortress is over. -> notices."""
    state = guild.wildfire
    if state is None or not won:
        return []
    if node_id == FORTRESS_ID and state.fortress == "hostile":
        state.fortress, state.fortress_pos = None, None
        _vacate(guild, FORTRESS_ID)
        world.remove_node(FORTRESS_ID)
        return [i18n.t("wildfire.ogre_s_fortress_falls_goblins")]
    focus = state.focus(node_id)
    if focus is None:
        return []
    if focus.great:
        _remove(guild, state, focus)
        return [i18n.t("wildfire.ogre_is_beaten_his_fortress") + _done(guild)]
    focus.cleared, focus.hostile = True, False
    return [(i18n.t("wildfire.goblins_at_are_beaten_fire", name=focus.name, put_out_hours=PUT_OUT_HOURS, put_out_dc=PUT_OUT_DC))]


def _done(guild):
    """The Ogre is dealt with: the errand is done, the Coven's scroll goes to the signer."""
    m = mission(guild)
    if m is None:
        return ""
    deeds = missions.settle_wildfire(guild, m)
    signer = next((u for u in guild.roster if u.uid == m.unit_uid), None)
    (signer or guild.roster[0]).give_to_pack(REWARD)
    return " ".join([i18n.t("wildfire.nature_coven_sends", reward=REWARD)] + [factions.deed_notice(d) for d in deeds])


# --------------------------------------------------------------------------- #
# the fights                                                                   #
# --------------------------------------------------------------------------- #

def camp_crew(level, rng=random):
    """A small focus: `CREW` Goblins at `level` and their Hobgoblin foreman a step over."""
    crew = [encounters.build_enemy(encounters.clamp_level(level), rng, race_pool=data.GOBLIN_POOL) for _ in range(CREW)]
    return crew + [encounters.build_enemy(encounters.clamp_level(level + FOREMAN_EDGE), rng, race_pool=data.HOBGOBLIN_POOL)]


def ogre_band(rng=random, hold=False):
    """The Ogre and his escort of goblins and hobgoblins at `ESCORT_LEVEL`, more of them once the
    fortress stands (`hold`)."""
    from . import npc_lib  # lazy: npc_lib -> persist -> guild -> guild_upkeep -> here
    n = HOLD_ESCORT if hold else ESCORT
    escort = [encounters.build_enemy(ESCORT_LEVEL, rng, race_pool=data.GOBLINOID_POOL) for _ in range(n)]
    return [npc_lib.load_npc(OGRE_SLUG)] + escort


def talker(focus, level, rng=random):
    """Who answers for a focus in its dialogue: the Ogre, or a crew's Hobgoblin foreman."""
    if focus.great:
        from . import npc_lib  # lazy: see ogre_band
        return npc_lib.load_npc(OGRE_SLUG)
    return encounters.build_enemy(encounters.clamp_level(level + FOREMAN_EDGE), rng, race_pool=data.HOBGOBLIN_POOL)


def ogre_of(battle):
    return next((u for u in battle.enemy_units
                 if getattr(getattr(u, "char", None), "npc_slug", None) == OGRE_SLUG), None)


# --------------------------------------------------------------------------- #
# what it leaves on The Wilds                                                  #
# --------------------------------------------------------------------------- #

def meat_mult(guild):
    state = guild.wildfire
    burned = state.burned if state is not None else 0
    return max(0.0, 1 - MEAT_LOSS * burned)


def hold_standing(guild):
    state = guild.wildfire
    return state is not None and state.fortress == "hostile"


def ambush_mult(guild):
    return HOLD_AMBUSH_MULT if hold_standing(guild) else 1.0


def wilds_pack(guild, rng=random):
    """While the hostile fortress stands, the pack that finds a hunt is often its goblins."""
    if hold_standing(guild) and rng.random() < HOLD_GOBLIN_ODDS:
        return encounters.roll_pack(rng=rng, race_pool=data.GOBLINOID_POOL)
    return encounters.roll_encounter(encounters.WILDS_TABLE, rng=rng)


# --------------------------------------------------------------------------- #
# save / load                                                                  #
# --------------------------------------------------------------------------- #

def to_dict(state):
    if state is None:
        return None
    return {"start_day": state.start_day, "seq": state.seq, "taught": state.taught,
            "burned": state.burned, "over": state.over, "fortress": state.fortress,
            "fortress_pos": list(state.fortress_pos) if state.fortress_pos else None,
            "foci": [{"id": f.id, "links": dict(f.links), "spawn_day": f.spawn_day,
                      "pos": list(f.pos), "great": f.great, "talk": f.talk,
                      "hostile": f.hostile, "cleared": f.cleared} for f in state.foci]}


def from_dict(d):
    if not d:
        return None
    return Wildfire(start_day=d["start_day"], seq=d["seq"], taught=d["taught"], burned=d["burned"],
                    over=d["over"], fortress=d["fortress"],
                    fortress_pos=tuple(d["fortress_pos"]) if d["fortress_pos"] else None,
                    foci=[Focus(f["id"], dict(f["links"]), f["spawn_day"], tuple(f["pos"]),
                                f["great"], f["talk"], f["hostile"], f["cleared"]) for f in d["foci"]])


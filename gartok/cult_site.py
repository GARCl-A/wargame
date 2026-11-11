"""The Demon Cult's site (`docs/plans/holy_symbol_quest.md`): the hidden place off the Country Roads where
Edric Ashvale's daughter is held for the ritual.

The node is ethereal (`world.add_node`): it is on the map, with its two roads (the Country Roads, the Faith
Cathedral), only once the guild has found it, so a route never walks through a place the guild cannot see.
Finding it is a search of the Country Roads while the job is out: Wisdom against a hard DC, helped by every
clue asking around turned up (`investigation.bonus`).
"""

import math
import random

from . import data, i18n, investigation, items, loot, missions, world
from .board import Board, grid_distance
from .ground import GroundObject
from .scenario import Scenario

NODE = "cult_site"
SEARCH_HOURS = 2
SEARCH_DC = 22
SEARCH_PER_CLUE = 2
POS = (0.76, 0.95)
LINKS = (("country_roads", 2), ("faith_cathedral", 2))
AMBUSH_NODES = ("country_roads", "farm")     # while the Demon lives it waits on the roads to the site and at the Farm
AMBUSH_CHANCE = 0.3
LAIR_DAYS = 15          # a failed rite leaves the site abandoned this long, then the Demon comes back to it


def quest_active(guild):
    return missions.active(guild, missions.FARMER_DAUGHTER)


def demon_loose(guild):
    """The rite closed and the Demon has not been killed: the Farm stays shut (`missions.shop_closed`)."""
    return guild.cult.get("state") in ("failed", "lair")


def demon_slain(guild):
    """The Demon is dead, wherever it fell: the Farm opens, the circle goes cold for good."""
    guild.cult["state"] = "demon_dead"
    sync_world(guild)


def ambush(guild, node_id):
    """The Demon's ambush, rolled once per arrival at a node of `AMBUSH_NODES` while it lives. -> its pack or None."""
    from . import npc_lib
    if not demon_loose(guild) or node_id not in AMBUSH_NODES or random.random() >= AMBUSH_CHANCE:
        return None
    return (npc_lib.load_npc(DEMON),)


def _node(guild):
    function = "demon_lair" if guild.cult.get("state") == "lair" else "cult_ritual"
    return world.Node(NODE, "Demon Cult Site", "town", POS, floor="earth", functions=(function,))


def sync_world(guild):
    """Put the site back on the map when the guild has found it (after a load, or a new guild)."""
    if world.exists(NODE):
        world.remove_node(NODE)
    if guild.is_node_revealed(NODE):
        world.add_node(_node(guild), list(LINKS))


def reveal(guild):
    """The site is found: on the guild's map and in the world. -> whether it was new."""
    new = guild.reveal_node(NODE)
    sync_world(guild)
    return new


def search_bonus(guild):
    return investigation.bonus(guild, missions.FARMER_DAUGHTER.id, SEARCH_PER_CLUE)


def search(guild, group):
    """The roll at the end of `SEARCH_HOURS` on the Country Roads. -> (found, message)."""
    scout = max(group.members, key=lambda u: u.mod_wisdom) if group.members else None
    who = scout.name if scout else i18n.t("ox.squad")
    if not quest_active(guild):
        return False, i18n.t("cult_site.nothing_on_the_roads", who=who, hours=SEARCH_HOURS)
    if guild.is_node_revealed(NODE):
        return True, i18n.t("cult_site.already_found", who=who)
    nat = data.d20()
    mod = scout.mod_wisdom if scout else 0
    bonus = search_bonus(guild)
    total = nat + mod + bonus
    if total >= SEARCH_DC:
        reveal(guild)
        return True, i18n.t("cult_site.found", who=who)
    return False, i18n.t("cult_site.missed", who=who, hours=SEARCH_HOURS, nat=nat, mod=f"{mod:+}", bonus=bonus,
                         total=total, dc=SEARCH_DC)


LEADER = "cult-leader"
FIGHTERS = ("cult-fighter-1", "cult-fighter-2")
CHANNELERS = ("cult-channeler-blood", "cult-channeler-nature", "cult-channeler-faith")
DAUGHTER = "farmers-daughter"
DEMON = "the-demon"
GOAL_CAPTIVE = "farmers_daughter"      # what `missions.FARMER_DAUGHTER.goal_captive` asks the band for

COLS, ROWS = 36, 24
POINTS = ((18, 5), (11, 17), (25, 17))      # the triangle: a channeler is bound to each
CENTRE = (18, 13)                           # where the leader closes the rite
BOUND = (18, 14)                            # where the daughter is tied, beside it
STEP, STEPS = 6, 3                          # the bar fills in three steps; an interrupted rite falls back one
BAR_MAX = STEP * STEPS
RING = 8                                    # the old stone circle the rite is held in: its radius round the centre


def _river():
    """The river that waters the Farm, across the north of the map, two to three cells deep (shallow:
    difficult ground, never a pit)."""
    return {(x, y) for x in range(COLS) for y in range(2 + (x // 3) % 2)}


def _stones():
    """The standing stones, one every 20 degrees on the circle but where a point of the triangle, the
    centre or the bound girl stands: cover and corners to break a line of sight, never a wall across."""
    keep = {*POINTS, CENTRE, BOUND}
    out = set()
    for deg in range(0, 360, 20):
        c = (round(CENTRE[0] + RING * math.cos(math.radians(deg))), round(CENTRE[1] + RING * math.sin(math.radians(deg))))
        if 3 <= c[1] < ROWS and all(max(abs(c[0] - k[0]), abs(c[1] - k[1])) > 2 for k in keep):
            out.add(c)
    return out


def _trees(taken):
    """A few trees, never dense: a fixed scatter so the map is the same every time, off the deployment edge,
    away from the circle and the river."""
    rng = random.Random(36)
    spots = []
    while len(spots) < 14:
        c = (rng.randrange(6, COLS - 1), rng.randrange(3, ROWS - 1))
        if math.dist(c, CENTRE) > RING + 2 and all(
                max(abs(c[0] - t[0]), abs(c[1] - t[1])) > 2 for t in (*taken, *spots)):
            spots.append(c)
    return set(spots)


def cultists():
    """The six, fresh from their files, on the enemy side: the leader, two fighters, three channelers."""
    from . import npc_lib       # npc_lib imports persist, which imports this module
    return [npc_lib.load_npc(slug) for slug in (LEADER, *FIGHTERS, *CHANNELERS)]


def slug_of(combatant):
    return getattr(getattr(combatant, "char", None), "npc_slug", None)


def able(combatant):
    """Fit to channel: on its feet, awake and not running (`Routed`). Demoralized does not stop it."""
    return combatant.alive and not combatant.has_condition("sleeping") and not combatant.has_condition("routed")


def knows_the_rite(combatant):
    return slug_of(combatant) in (LEADER, *CHANNELERS)


class CultSiteScenario(Scenario):
    """The triangle of braziers. The three channelers stand on its points and feed the rite one step a
    turn without spending an action (`on_turn_start`); full, the leader walks to the centre and closes it
    on his next turn. Stopping him (down, asleep, routed, or pushed off the centre) sets the bar back one
    step. A closed rite is the failure: the daughter dies and the Demon lays every living body down, nobody
    killed (`spares_the_squad`). The cultists all down first: the daughter is freed."""

    floor = "earth"
    water_look = "river"
    outdoor = True
    torch_count = 0
    spares_the_squad = True

    def __init__(self, squad=None, head_start=False):
        self.allies = []
        self.enemies = cultists()
        self.bar = STEP if head_start else 0
        self.rite_began = False
        self.demon_came = False
        self.daughter_alive = True

    def _make_board(self):
        stones = _stones()
        trees = _trees({*stones, *POINTS, CENTRE, BOUND})
        self.wall_kinds = {**{c: "tree" for c in trees}, **{c: "stone" for c in stones}}
        return Board(walls=stones | trees, water=_river(), cols=COLS, rows=ROWS)

    def _deploy_cells(self, u):
        slug = slug_of(u)
        if slug in CHANNELERS:
            return [POINTS[CHANNELERS.index(slug)]]
        cx, cy = CENTRE
        near = {LEADER: [(cx, cy - 2), (cx - 1, cy - 2), (cx + 1, cy - 2)],
                FIGHTERS[0]: [(cx - 4, cy), (cx - 4, cy + 1), (cx - 3, cy)],
                FIGHTERS[1]: [(cx + 4, cy), (cx + 4, cy + 1), (cx + 3, cy)]}.get(slug, [])
        return near + super()._deploy_cells(u)

    def build(self, battle):
        super().build(battle)
        for pos in (*POINTS, CENTRE):
            brazier = GroundObject.torch(pos)
            brazier.fixture = True
            battle.ground.append(brazier)

    def props(self, battle):
        """Drawn on the board beyond the ground objects: the runes of the triangle and the bound girl."""
        out = [{"kind": "rune", "pos": p} for p in (*POINTS, CENTRE)]
        if self.daughter_alive:
            out.append({"kind": "bound", "pos": BOUND})
        return out

    def hud(self, battle):
        """The rite for the screen: the bar and, once the leader has begun, the warning."""
        text = i18n.t("cult_site.hud_closing" if self.rite_began else "cult_site.hud", bar=self.bar, max=BAR_MAX)
        return {"bar": self.bar, "max": BAR_MAX, "step": STEP, "text": text, "closing": self.rite_began,
                "title": i18n.t("cult_site.hud_title"), "warn": i18n.t("cult_site.hud_warn")}

    @staticmethod
    def _leader(battle):
        return next((u for u in battle.enemy_units if slug_of(u) == LEADER), None)

    def ai_post(self, battle, unit):
        """Where `ai/` ties a cultist (`ai.scripted._channel`): a channeler to its point; the leader to the
        centre once the bar is full, else to a point no one holds, so the rite never starves."""
        slug = slug_of(unit)
        if slug in CHANNELERS:
            return POINTS[CHANNELERS.index(slug)]
        if slug != LEADER:
            return None
        if self.bar >= BAR_MAX:
            return CENTRE
        held = {u.pos for u in battle.units if u.alive and u is not unit}
        free = [p for p in POINTS if p not in held]
        return min(free, key=lambda p: grid_distance(p, unit.pos)) if free else None

    def ai_must_stay(self, battle, unit):
        """The leader at the centre with the bar full spends his whole turn on the rite: no attacks."""
        return slug_of(unit) == LEADER and unit.pos == CENTRE and self.bar >= BAR_MAX

    def on_turn_start(self, battle, unit):
        if self.demon_came or not knows_the_rite(unit) or not able(unit):
            return
        if slug_of(unit) == LEADER and self.rite_began and unit.pos == CENTRE and self.bar >= BAR_MAX:
            self._close(battle)
            return
        if unit.pos in POINTS and self.bar < BAR_MAX:
            self.bar = min(BAR_MAX, self.bar + 1)
            battle.log("cult_site.channels", name=unit.name, bar=self.bar, max=BAR_MAX)
            if self.bar >= BAR_MAX:
                battle.log("cult_site.bar_full")

    def on_turn_end(self, battle, unit):
        if (slug_of(unit) == LEADER and self.bar >= BAR_MAX and not self.rite_began and not self.demon_came
                and unit.pos == CENTRE and able(unit)):
            self.rite_began = True
            battle.log("cult_site.rite_begins", name=unit.name)

    def win_check(self, battle):
        if self.demon_came:
            return "enemy"
        if self.rite_began:
            leader = self._leader(battle)
            if leader is None or not able(leader) or leader.pos != CENTRE:
                self.bar = max(0, self.bar - STEP)
                self.rite_began = False
                battle.log("cult_site.rite_broken", bar=self.bar, max=BAR_MAX)
        return None

    def _close(self, battle):
        """The rite closes: the daughter dies, the Demon lays everyone down, the fight is lost without a death."""
        self.demon_came = True
        self.daughter_alive = False
        battle.log("cult_site.rite_closes")
        battle.log("cult_site.daughter_dies")
        battle.log("cult_site.demon_comes")
        for u in battle.units:
            if u.status in ("up", "dying", "broken", "fled"):
                u.hp, u.status = 0, "stable"
        battle._check_winner()


def head_start(opening):
    """Did the talk before the fight give the rite a head start (a missed Bluff or Intimidate)?"""
    return bool(opening is not None and opening.initiative.get("enemy"))


def _fail(guild, day, remains):
    guild.cult.update(state="failed", failed_day=day, remains=sorted(remains))


def let_proceed(guild):
    """The squad let the rite run: no fight, the girl lost, the site left as a closed rite leaves it (her
    Holy Symbol lies there). -> the notice."""
    _fail(guild, guild.clock.day, [items.HOLY_SYMBOL_ITEM])
    return i18n.t("cult_site.settle_failed")


def daily(guild):
    """Once a day, from `guild_upkeep`: a missed deadline abandons the rite as a closed one would (the site
    shows itself, a pillar of red light), and `LAIR_DAYS` after a failure the Demon makes the site its lair.
    -> the notice lines."""
    cult, today = guild.cult, guild.clock.day
    if not cult.get("state") and any(m.template_id == missions.FARMER_DAUGHTER.id and m.state == "failed"
                                     for m in guild.missions):
        _fail(guild, today, [items.HOLY_SYMBOL_ITEM])
        reveal(guild)
        return [i18n.t("cult_site.pillar_of_light")]
    if cult.get("state") == "failed" and today >= cult.get("failed_day", today) + LAIR_DAYS:
        cult["state"] = "lair"
        sync_world(guild)
        return [i18n.t("cult_site.demon_returns")]
    return []


def free_daughter(guild, group):
    """The cult is down: the daughter walks with the band as a ward (`captives.Captive.ward`), delivered at
    the Farm by the job (`goal_captive`). Once only. -> the notice, or None."""
    if guild.cult.get("state") != "won" or guild.cult.get("freed"):
        return None
    from . import captives, npc_lib
    girl = npc_lib.load_npc(DAUGHTER)
    girl.team = "player"
    group.captives.append(captives.Captive(girl, guild.clock.day, GOAL_CAPTIVE, ward=True))
    guild.cult["freed"] = True
    return i18n.t("cult_site.daughter_walks_with_you", name=girl.name)


def settle_fight(guild, battle, group=None):
    """What the fight leaves of the quest. -> the notice lines. A win frees the daughter (she waits for the
    guild's word, `cult["state"] == "won"`); a closed rite leaves the site abandoned, her body and what the
    guild's dead carried lying there for whoever comes back (`search_remains`)."""
    cult = guild.cult
    if battle.winner == "player":
        cult["state"] = "won"
        walks = free_daughter(guild, group) if group is not None else None
        return [i18n.t("cult_site.settle_won"), *([walks] if walks else [])]
    if battle.scenario.demon_came:
        remains = [items.HOLY_SYMBOL_ITEM]
        for c in battle.player_units:
            if c.status == "dead":
                remains += loot.carried_by(c) + _worn(c.char)
        _fail(guild, battle.clock_day, remains)
        return [i18n.t("cult_site.settle_failed")]
    return []


def _worn(char):
    return [x for x in (char.equipped_armor, char.equipped_offhand, char.equipped_artifact) if x]


def search_remains(guild, group):
    """Search the abandoned circle: the remains go into the first member's pack, once. -> the notice."""
    cult = guild.cult
    remains = list(cult.get("remains", ()))
    if not remains or not group.members:
        return i18n.t("cult_site.remains_none")
    cult["remains"] = []
    carrier = group.members[0]
    for name in remains:
        carrier.give_to_pack(name)
    return i18n.t("cult_site.remains_found", who=carrier.name, items=", ".join(remains))

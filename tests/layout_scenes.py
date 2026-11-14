"""The screens `test_layout.py` draws, each a function that builds a `Game` standing on it: the same
sessions the server opens, put together from the same pieces the web tests use."""

import random

from gartok import node_functions, orders, world
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild
from gartok.unit import Unit
from gartok.wagon import Wagon
from gartok.web.credits_session import CreditsSession
from gartok.web.dialogue_session import DialogueSession
from gartok.web.guild_session import TABS as GUILD_TABS
from gartok.web.guild_session import GuildSession
from gartok.web.hub_session import HUB_KINDS, HubSession
from gartok.web.map_session import MapSession
from gartok.web.server import Game
from gartok.web.settings_session import SettingsSession
from gartok.web.wiki_session import WikiSession
from tests.test_web_report import _fight


def _band(node="lumber_yard", n=3, money=0):
    random.seed(4)
    units = [Unit("Fighter") for _ in range(n)]
    for u in units:
        u.money = money
        u.give_to_pack("Potato", 6)
    group = Group(units, node=node, leader=units[0])
    guild = Guild(None, groups=[group], name="Ink Hands")
    guild.clock = Clock(8 * 3600)
    guild.tutorial.enabled = False
    return guild, group


LONG = ["Bartholomew Wolfgang-Montgomery of Greywater", "Ozymandias Featherstonehaugh", "Anastasia Ravenscroft-Delacroix",
        "Maximilian the Unrelenting", "Isolde Thunderbottom-Hargreaves", "Cornelius Longshanks of the Marches"]


def _crowd(n_groups=5, size=5):
    """A guild late in the game: a long name, many bands with long names, long member names, a wagon each, packs full."""
    random.seed(4)
    groups = []
    for g in range(n_groups):
        units = [Unit("Fighter") for _ in range(size)]
        for i, u in enumerate(units):
            u.name = LONG[(g + i) % len(LONG)]
            u.money = 12345
            u.give_to_pack("Potato", 6)
        group = Group(units, node="lumber_yard", leader=units[0], name=f"The {LONG[g % len(LONG)]} Expedition")
        group.add_wagon(Wagon())
        groups.append(group)
    guild = Guild(None, groups=groups, name="The Most Illustrious Order of the Silver Lantern and the Ember")
    guild.clock = Clock(8 * 3600)
    guild.tutorial.enabled = False
    return guild


def _map(node="lumber_yard"):
    guild, group = _band(node)
    return MapSession(guild), group


def _open(session, map_session=None):
    game = Game(map_session or session)
    if map_session is not None:
        game.open(session)
    return game


def _aside(cls):
    return lambda: Game(cls(lambda: None))


def title():
    return Game.title()


def battle():
    return Game.fight("wilds", 2, 3, seed=4)


def map_():
    return Game(_map()[0])


def guild_tab(tab):
    return lambda: Game(GuildSession(_map()[0], tab))


def crowd_map():
    return Game(MapSession(_crowd()))


def crowd_guild_tab(tab):
    return lambda: Game(GuildSession(MapSession(_crowd()), tab))


def hub(node, kind, tab):
    def build():
        m, group = _map(node)
        session = HubSession(m, group, orders.Order(kind))
        session.pick_tab(tab)
        return _open(session, m)
    return build


def hubs():
    """One scene per tab of every hub the world offers (the first node that has it)."""
    found = {}
    for node in world.NODES:
        for f in node_functions.offered(node):
            if f.order_kind in HUB_KINDS and f.order_kind not in found:
                found[f.order_kind] = node
    scenes = {}
    for kind, node in found.items():
        m, group = _map(node.id)
        for tab, _ in HubSession(m, group, orders.Order(kind)).tabs:
            scenes[f"hub.{kind}.{tab}"] = hub(node.id, kind, tab)
    return scenes


def talk(kind="ambush"):
    from tests.test_web_talk import _ambushed
    from tests.test_web_talk import _open as resolve

    def build():
        game, guild, group = _ambushed(kind)
        guild.tutorial.enabled = False
        resolve(game, group)
        assert isinstance(game.session, DialogueSession)
        return game
    return build


def report(stage):
    def build():
        guild, _squad, fought, outcome = _fight(death=True, level=True, loot=["Axe"])
        guild.tutorial.enabled = False
        m = MapSession(guild)
        from gartok.web.report_session import ReportSession
        session = ReportSession(m, guild.groups[0], fought, outcome, place="The Wilds")
        game = _open(session, m)
        while session.stage[0] != stage:
            session.next()
        return game
    return build


def talents():
    guild, group = _band("city")
    group.members[0].combat_xp = 10
    m = MapSession(guild, "w1")
    sheet = GuildSession(m, "members")
    m.game = Game(m)
    m.game.open(sheet)
    sheet.desk.member = group.members[0]
    sheet.talents()
    return m.game


def arena():
    from tests.test_web_arena import _arena
    from tests.test_web_arena import _guild as arena_guild
    guild, group = arena_guild()
    guild.tutorial.enabled = False
    return _arena(guild, group)[0]


def hunt():
    from tests.test_web_hunt import _guild as hunt_guild
    from tests.test_web_hunt import _hunt
    guild, group = hunt_guild()
    guild.tutorial.enabled = False
    return _hunt(guild, group)[0]


def watch():
    from gartok.web.watch_session import WatchSession
    guild, group = _band("road")
    group.add_wagon(Wagon())
    m = MapSession(guild)
    session = WatchSession(m, group, "ENTER THE RUINS", "what waits inside", lambda party, guarded: {})
    return _open(session, m)


def draft(step="vocation"):
    def build():
        from gartok import vocations
        from gartok.draft import TEAM_SIZE
        game = Game.title()
        game.session.new_guild()
        d = game.session
        d.tutorial.enabled = False
        if step != "vocation":
            d.choose_vocation(next(iter(vocations.VOCATIONS)))
            d.next()
        if step == "charter":
            for i in range(TEAM_SIZE):
                d.pick(i)
            d.next()
        return game
    return build


SCREENS = {
    "title": title,
    "draft.vocation": draft("vocation"),
    "draft.pick": draft("pick"),
    "draft.charter": draft("charter"),
    "map": map_,
    "map.crowd": crowd_map,
    **{f"guild.{tab}": guild_tab(tab) for tab, _ in GUILD_TABS},
    **{f"guild.{tab}.crowd": crowd_guild_tab(tab) for tab, _ in GUILD_TABS},
    "wiki": _aside(WikiSession),
    "settings": _aside(SettingsSession),
    "credits": _aside(CreditsSession),
    "battle": battle,
    "talk": talk(),
    **{f"report.{s}": report(s) for s in ("memorial", "report", "level", "loot")},
    "talents": talents,
    "arena": arena,
    "hunt": hunt,
    "watch": watch,
    **hubs(),
}


# what a screen must have finished before it is looked at: a fight's computer turns play on their own
READY = {"battle": "!!S?.my_turn && !ui.busy"}

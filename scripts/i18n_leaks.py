"""Opens every hub tab, the map and the guild screen in `pt-br` and lists the strings in their payloads that still
read as English: the leaks the AST audit (`i18n_audit.py`) cannot see (single words, ids shown raw, f-strings).

    python scripts/i18n_leaks.py [--lang pt-br]

The names the client shows through `nm()` (items, races) arrive as ids and are not flagged. A heuristic: a string is flagged when it holds an English function word or equals an `en` catalog text the chosen
language has rewritten. Keys that carry ids, paths and glyphs are skipped.
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SKIP_KEYS = {"uid", "id", "glyph", "portrait", "icon", "kind", "key", "tab", "screen", "order", "slug", "sel", "tone",
             "tint", "art", "image", "src", "url", "cls", "class", "color", "sprite", "tile", "bg", "gid", "node", "dest"}
ENGLISH = re.compile(r"\b(the|of|and|to|for|with|you|your|is|are|no|not|has|have|from|into|at|on|in|a|an|it|its|that)\b", re.I)
PT_HINT = re.compile(r"[ãõçéêáíóúâô]|\b(de|do|da|para|com|um|uma|em|no|na|os|as|o|a|e|que|se|por)\b", re.I)


def walk(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in SKIP_KEYS:
                continue
            yield from walk(v, f"{path}.{k}")
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def english(text, rewritten):
    plain = re.sub(r"<[^>]+>|\{[^}]*\}", " ", text).strip()
    if len(plain) < 2 or not re.search(r"[A-Za-z]{2,}", plain):
        return False
    if plain.lower() in rewritten:
        return True
    return len(ENGLISH.findall(plain)) >= 2 and not PT_HINT.search(plain)


def screens(scan):
    """The report, talk, hunt, arena and talents screens, built the way their tests build them."""
    import random
    import tempfile

    from gartok import campaign, persist, world
    from gartok.clock import Clock
    from gartok.guild import Guild
    from gartok.web.arena_session import ArenaSession
    from gartok.web.map_session import MapSession
    from gartok.web.report_session import ReportSession
    from gartok.web.server import Game
    from tests import test_web_arena, test_web_hunt, test_web_talents, test_web_talk
    from tests.helpers import Battle, _unit

    persist.SAVE_DIR = tempfile.mkdtemp()
    for death in (True, False):
        squad = [_unit(seed=i) for i in range(2)]
        foes = [_unit(team="enemy", seed=100 + i) for i in range(2)]
        guild = Guild(squad, node="wilds")
        guild.clock = Clock(24 * 9 * 3600)
        battle = Battle(squad, foes, lethal=True)
        hand = battle.player_units[0]
        if death:
            battle.player_units[-1].hp, battle.player_units[-1].status = 0, "dead"
            battle.player_units[-1].downed_by = battle.enemy_units[0]
            hand.combat_xp_earned = 50
            battle.enemy_units[0].inventory.append("Axe")
        for c in battle.enemy_units:
            c.hp, c.status = 0, "dead"
            hand.credit_kill(c)
        battle.winner, battle.round_no = "player", 4
        outcome = campaign.absorb_battle(guild, squad, battle, node=world.node("wilds"))
        game = Game(MapSession(guild))
        report = ReportSession(game.session, guild.groups[0], battle, outcome, place="wilds")
        game.open(report)
        while game.session is report and report.stage[0] != "map":
            scan(f"report:{report.stage[0]}", report.state())
            if report.stage[0] == "purse":
                report.give(guild.groups[0].members[0].uid)
            report.next()
    for node in ("road", "wilds", "ancient_ruins"):
        for verb in ("persuade", "bluff", "intimidate", "bribe", "attack"):
            random.seed(len(node) * 7 + len(verb))
            game, _guild, g = test_web_talk._ambushed("ambush", node, money=50)
            game.session.act(g.gid, "resolve_event")
            scan(f"talk:{node}", game.session.state())
            try:
                game.session.choose(verb)
                scan(f"talk:{node}:{verb}", game.session.state())
            except ValueError:
                pass
    for target in ("meat", "shrooms"):
        guild, g = test_web_hunt._guild()
        _game, hunt = test_web_hunt._hunt(guild, g)
        hunt.set_target(target)
        hunt.set_hours(hunt._offered()[-1])
        scan(f"hunt:{target}", hunt.state())
        hunt.start()
        scan(f"hunt:{target}:started", hunt.state())
    guild, g = test_web_arena._guild(money=500)
    _game, arena = test_web_arena._arena(guild, g)
    guild.deeds_done.append("arena_dethrone")
    for i in range(4):
        arena = ArenaSession(arena.map, g)
        arena.pick_bout(i)
        scan(f"arena:{i}", arena.state())
    _game, tree, _units = test_web_talents._open()
    for track in tree.state()["tracks"]:
        scan(f"talents:{track['track']}", tree.state())


def main(lang):
    from gartok import i18n, node_functions, orders, world
    from gartok.group import Group
    from gartok.guild import Guild
    from gartok.web.guild_session import GuildSession
    from gartok.web.hub_session import HUB_KINDS, HubSession
    from gartok.web.map_session import MapSession
    from tests.helpers import standard_unit

    en, target = i18n.catalog("en"), i18n.catalog(lang)
    rewritten = {str(en[k]).lower() for k in en if isinstance(en[k], str) and not k.startswith("name.") and target.get(k) not in (None, en[k])
                 and len(str(en[k])) > 3}
    i18n.set_language(lang)
    seen = {}

    def scan(where, payload):
        for path, text in walk(payload):
            if english(text, rewritten):
                seen.setdefault(text, f"{where}{path}")

    def guild_at(node):
        units = [standard_unit() for _ in range(2)]
        for u in units:
            u.money = 200
            u.give_to_pack("Potato", 4)
        return Guild(None, groups=[Group(units, node=node, leader=units[0])], name="Ink Hands")

    for node in world.NODES:
        guild = guild_at(node.id)
        session = MapSession(guild)
        scan(f"map:{node.id}", session.state())
        try:
            scan(f"guild:{node.id}", GuildSession(session).state())
        except Exception as exc:
            print("guild screen failed:", node.id, exc)
        for f in node_functions.offered(node):
            if f.order_kind not in HUB_KINDS:
                continue
            try:
                hub = HubSession(session, guild.groups[0], orders.Order(f.order_kind))
                for key, _label in hub.tabs:
                    scan(f"hub:{node.id}/{f.order_kind}/{key}", hub.pick_tab(key))
            except Exception as exc:
                print("hub failed:", node.id, f.order_kind, exc)
    from gartok import combat_lab
    from gartok.web.battle_session import BattleSession
    from gartok.web.wiki_session import WikiSession
    wiki = WikiSession(lambda: {"screen": "title"})
    for chapter in [c["id"] for c in wiki.state()["chapters"]]:
        scan(f"wiki:{chapter}", wiki.chapter(chapter))
    for fight in combat_lab.FIGHTS:
        battle, meta = combat_lab.build(fight, 2, 4, seed=3)
        scan(f"battle:{fight}", BattleSession(battle, meta).state())
    screens(scan)
    for text, where in sorted(seen.items(), key=lambda kv: kv[1]):
        print(f"{where}: {text[:140]!r}")
    print(f"{len(seen)} suspect strings")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="pt-br")
    main(ap.parse_args().lang)

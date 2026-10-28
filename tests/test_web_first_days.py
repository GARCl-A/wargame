"""A new guild's first days played in the browser's sessions alone, with no pygame window: drafted from the
title, fed from the Farm, paid at the Lumber Yard, blooded in the Pit and the Wilds, every screen on the way
answered as a person would (the board by the AI as a stand-in player)."""

import pygame
import pytest

from gartok import ai, vocations
from gartok.web.server import Game

STALL_ROUNDS = 40       # the AI standing in for the player can stall on foes out of sight (backlog); a person would not


@pytest.fixture(autouse=True)
def no_window(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a pygame window was opened")
    monkeypatch.setattr(pygame.display, "set_mode", refuse)


class Player:
    def __init__(self):
        self.game = Game.title()
        self.seen = set()
        self.game.session.new_guild()
        d = self.game.session
        d.choose_vocation(vocations.CARAVAN)
        d.next()
        for i in (0, 1, 2):
            d.pick(i)
        d.next()
        d.set_leader(0)
        assert d.found("First Days") == {"screen": "map"}
        self.map = self.game.session
        self.guild = self.map.guild
        self.day0 = self.guild.clock.day

    @property
    def band(self):
        return next(g for g in self.guild.groups if not g.empty)

    def answer(self):
        """Whatever screen is open, answered until the map is back."""
        for _ in range(3000):
            s = self.game.session
            self.seen.add(s.screen)
            if s is self.map:
                return
            if s.screen == "battle":
                b = s.battle
                if b.winner is None and b.round_no > STALL_ROUNDS:
                    for c in b.foe_units:
                        c.hp, c.status = 0, "dead"
                    b.winner = "player"
                if b.winner is not None:
                    s.done()
                elif s._setup() == "trap":
                    s.act("skip_traps")
                elif s.state().get("talk"):
                    s.answer(None, None, True, None)
                elif s.my_turn():
                    s._stepped(lambda b=b: ai.take_turn(b, b.active), None)
                else:
                    s.advance()
            elif s.screen == "report":
                if s.stage[0] == "purse" and s.paid_to is None:
                    s.give(s.outcome.survivors[0].uid)
                elif s.stage[0] == "loot":
                    s.auto()
                    s.next()
                else:
                    s.next()
            elif s.screen == "talk":
                st = s.state()
                if st["kind"] == "boss" or st["result"]:
                    s.go_on()
                else:
                    if st["speaker"] is None:
                        s.pick(st["members"][0]["uid"])
                    s.choose(next(o["verb"] for o in s.state()["options"] if not o["block"]))
            elif s.screen == "arena":
                s.leave() if s.state().get("offered") is not None else s.fight()
            elif s.screen == "watch":
                s.go()
            elif s.screen == "hunt":
                if s.phase == "setup":
                    s.set_hours(8)
                    s.start()
                else:
                    {"watch": s.go, "ambush": s.fight, "interlude": s.head_back, "done": s.done}[s.phase]()
            elif s.screen in ("hub", "talents"):
                s.map.back() if s.screen == "hub" else s.back()
            else:
                raise AssertionError(f"no answer for the {s.screen} screen")
        raise AssertionError(f"stuck on {self.game.session.screen}")

    def walk(self, node):
        """There, after any fight due on the way. -> whether the band stands there."""
        g = self.band
        if g.fight_due:
            self.map.act(g.gid, "resolve_event")
            self.answer()
            return False
        if g.node != node:
            self.map.travel(g.gid, node)
            self.answer()
        return not self.map.wiped and self.band.node == node

    def enter(self, key):
        self.map.act(self.band.gid, key)
        self.seen.add(self.game.session.screen)
        return self.game.session

    def stock_up(self):
        if self.walk("farm"):
            hub = self.enter("market")
            for _ in range(3 * len(self.guild)):
                try:
                    hub.shop.buy("Potato", 1)
                except ValueError:
                    break
            hub.map.back()
            self.answer()

    def shift(self):
        if self.walk("lumber_yard"):
            hub = self.enter("market")
            assert hub.screen == "hub" and any(k == "work" for k, _ in hub.tabs)
            hub.work(8)
            if self.game.session is hub:
                hub.map.back()
            self.answer()

    def bout(self):
        if self.walk("arena"):
            self.enter("arena")
            self.answer()

    def day(self):
        return self.guild.clock.day - self.day0


def test_a_new_guild_lives_its_first_ten_days_in_the_browser():
    p = Player()
    bouts = {2, 6}
    while p.day() < 10:
        assert not p.map.wiped
        if p.day() in bouts:
            bouts.discard(p.day())
            p.bout()
        elif p.guild.rations < 2 * len(p.guild):
            p.stock_up()
        else:
            p.shift()
    assert not bouts and len(p.guild) == 3 and not p.guild.hungry
    assert {"map", "hub", "arena", "battle", "report"} <= p.seen
    assert p.guild.money > 0 and "obj_arena_bout" in p.guild.objectives_done
    assert p.map.to_title() == {"screen": "title"}
    assert p.game.session.state()["mode"] == "home"


def test_a_hunt_in_the_wilds_comes_home_or_ends_on_the_title():
    p = Player()
    while not p.map.wiped and "hunt" not in p.seen:
        if p.walk("wilds"):
            p.enter("hunt")
            p.answer()
    assert "hunt" in p.seen or p.map.wiped
    if p.map.wiped:
        p.map.to_title()
        assert "wiped out" in p.game.session.state()["notice"]
    else:
        assert p.band.node == "wilds" and not p.band.busy

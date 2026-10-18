"""The line each arena boss says before the guild's first bout against them: Adelio before the
champion bout, the three Ribbit brothers (eldest first) before the Games' capstone; once a guild.
It is a `dialogue.BossTalk`: no verbs, the dialogue screen walks the lines and the last one fights."""

import pygame

from gartok import arena, economy, i18n, persist, world
from gartok.dialogue_screen import DialogueScreen
from gartok.guild import Guild
from tests.helpers import Unit, make_app


def test_adelio_speaks_before_the_first_champion_bout():
    talk = arena.boss_talk(Guild([Unit("a")]), arena.champion_bout())
    adelio = talk.leader
    assert adelio.name == "Adelio Small-Knife" and talk.kind == "boss" and talk.offered() == ()
    assert adelio.portrait_file == "adelio.png" and adelio.race["name"] == "Halfling"
    assert talk.line == i18n.t("arena_talk.adelio-small-knife") != "arena_talk.adelio-small-knife"
    assert talk.caption(adelio) == "champion of the pit"
    assert talk.current().kind == "fight"


def test_the_ribbit_brothers_speak_one_line_each_the_eldest_first():
    talk = arena.boss_talk(Guild([Unit("a")]), arena.boss_bout())
    assert [u.name for u, _, _ in talk.lines] == ["Ribit", "Bufo", "Peep"]
    assert all(i18n.has(f"arena_talk.{slug}") for slug, _ in arena.BOSS_TALKS["boss"])
    assert talk.current().kind == "next"
    talk.advance()
    assert talk.leader.name == "Bufo" and talk.line == i18n.t("arena_talk.bufo")
    assert talk.advance().kind == "fight" and talk.leader.name == "Peep"


def test_no_talk_once_heard_nor_before_an_ordinary_bout():
    guild = Guild([Unit("a")])
    guild.boss_talks_seen.add("champion")
    assert arena.boss_talk(guild, arena.champion_bout()) is None
    assert arena.boss_talk(guild, arena.boss_bout()) is not None
    for offer in (arena.scrapper_bout(), arena.defense_bout(), None):
        assert arena.boss_talk(guild, offer) is None


def test_what_was_heard_survives_a_save():
    guild = Guild([Unit("a")])
    guild.boss_talks_seen.update({"champion", "boss"})
    world_id = persist.new_world_id()
    persist.save_game(world_id, guild)
    assert persist.load_game(world_id).boss_talks_seen == {"champion", "boss"}


def _press(screen, key):
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))


def test_the_screen_walks_the_lines_with_no_answer_and_starts_the_fight_once():
    pygame.init()
    from gartok.ui import tokens
    guild = Guild([Unit("a")])
    talk = arena.boss_talk(guild, arena.boss_bout())
    done = []
    screen = DialogueScreen(tokens.fonts(), guild, guild.groups[0], talk, done.append, decided=talk.current())
    assert screen.tutorial_key() is None
    surf = pygame.Surface((1000, 640))
    screen.draw(surf)
    assert screen.hits["speakers"] == [] and screen.hits["options"] == []
    button = screen.hits["button"]
    screen.mouse = button.center
    screen.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=button.center))
    _press(screen, pygame.K_RETURN)
    assert talk.leader.name == "Peep" and not done
    screen.draw(surf)
    _press(screen, pygame.K_SPACE)
    assert [r.kind for r in done] == ["fight"]


def test_the_first_champion_bout_opens_on_the_talk_and_the_second_goes_straight_in(monkeypatch):
    guild = Guild([Unit("a"), Unit("b")], node="arena")
    app = make_app(guild)
    app._arena_purse = None
    entered = []
    monkeypatch.setattr(economy, "charge_richest_first", lambda *a: None)
    app._enter_battle = lambda battle, node: entered.append(battle)
    node = world.node("arena")

    app._start_battle(guild.roster, node, arena.champion_bout())
    assert isinstance(app.scene, DialogueScreen) and app.scene.encounter.kind == "boss" and not entered
    assert "champion" in guild.boss_talks_seen
    assert not app._can_save()
    app.scene.go_on()
    assert len(entered) == 1

    app._start_battle(guild.roster, node, arena.champion_bout())
    assert len(entered) == 2

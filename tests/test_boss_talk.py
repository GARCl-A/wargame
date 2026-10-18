"""The line each arena boss says before the guild's first bout against them: Adelio before the
champion bout, the three Ribbit brothers (eldest first) before the Games' capstone; once a guild."""

import pygame

from gartok import arena, economy, i18n, persist, world
from gartok.boss_talk_screen import BossTalkScreen
from gartok.guild import Guild
from tests.helpers import Unit, make_app


def test_adelio_speaks_before_the_first_champion_bout():
    cards = arena.boss_talk(Guild([Unit("a")]), arena.champion_bout())
    assert [c["name"] for c in cards] == ["Adelio Small-Knife"]
    assert cards[0]["portrait"] == "adelio.png" and cards[0]["race"] == "Halfling"
    assert cards[0]["line"] == i18n.t("arena_talk.adelio-small-knife") != "arena_talk.adelio-small-knife"


def test_the_ribbit_brothers_speak_one_card_each_the_eldest_first():
    cards = arena.boss_talk(Guild([Unit("a")]), arena.boss_bout())
    assert [c["name"] for c in cards] == ["Ribit", "Bufo", "Peep"]
    assert all(i18n.has(f"arena_talk.{slug}") for slug, _ in arena.BOSS_TALKS["boss"])


def test_no_talk_once_heard_nor_before_an_ordinary_bout():
    guild = Guild([Unit("a")])
    guild.boss_talks_seen.add("champion")
    assert arena.boss_talk(guild, arena.champion_bout()) == []
    assert arena.boss_talk(guild, arena.boss_bout())
    for offer in (arena.scrapper_bout(), arena.defense_bout(), None):
        assert arena.boss_talk(guild, offer) == []


def test_what_was_heard_survives_a_save():
    guild = Guild([Unit("a")])
    guild.boss_talks_seen.update({"champion", "boss"})
    world_id = persist.new_world_id()
    persist.save_game(world_id, guild)
    assert persist.load_game(world_id).boss_talks_seen == {"champion", "boss"}


def _press(screen, key):
    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))


def test_the_screen_walks_the_cards_and_starts_the_fight_once():
    pygame.init()
    from gartok.ui import tokens
    done = []
    screen = BossTalkScreen(tokens.fonts(), arena.boss_talk(Guild([Unit("a")]), arena.boss_bout()),
                            lambda: done.append(1))
    surf = pygame.Surface((1000, 640))
    screen.draw(surf)
    assert not screen.last
    screen.mouse = screen.button.center
    screen.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=screen.button.center))
    _press(screen, pygame.K_RETURN)
    assert screen.last and not done
    _press(screen, pygame.K_SPACE)
    _press(screen, pygame.K_SPACE)
    assert done == [1]
    screen.draw(surf)


def test_the_first_champion_bout_opens_on_the_talk_and_the_second_goes_straight_in(monkeypatch):
    guild = Guild([Unit("a"), Unit("b")], node="arena")
    app = make_app(guild)
    app._arena_purse = None
    entered = []
    monkeypatch.setattr(economy, "charge_richest_first", lambda *a: None)
    app._enter_battle = lambda battle, node: entered.append(battle)
    node = world.node("arena")

    app._start_battle(guild.roster, node, arena.champion_bout())
    assert isinstance(app.scene, BossTalkScreen) and not entered
    assert "champion" in guild.boss_talks_seen
    assert not app._can_save()
    app.scene.advance()
    assert len(entered) == 1

    app._start_battle(guild.roster, node, arena.champion_bout())
    assert len(entered) == 2

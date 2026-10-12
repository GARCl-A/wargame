"""Tests for Ribbit brothers recruitment, arena offer filter, and cameos."""

import random
import pygame

from gartok import arena, matchup, world
from gartok.guild import Guild
from gartok.ribbit_prompt_screen import RibbitPromptScreen
from gartok.unit import Unit


def test_ribbit_brothers_loaded_as_recruit_candidates():
    brothers = arena.load_ribbit_brothers()
    assert len(brothers) == 3
    names = {b.name for b in brothers}
    assert names == {"Bufo", "Ribit", "Peep"}
    for b in brothers:
        assert b.side == "player"
        assert b.arena_role is None
        assert b.hp > 0


def test_ribbit_prompt_screen_buttons():
    called = []
    screen = RibbitPromptScreen(None, on_recruit=lambda: called.append("recruit"),
                                on_leave=lambda: called.append("leave"))
    surf = pygame.Surface((800, 600))
    from gartok.ui.tokens import fonts
    screen.fonts = fonts()
    screen.draw(surf)

    assert len(screen.buttons) == 2
    rec_btn = next(r for k, r in screen.buttons if k == "recruit")
    leave_btn = next(r for k, r in screen.buttons if k == "leave")

    screen._click(rec_btn.center)
    assert called == ["recruit"]

    screen._click(leave_btn.center)
    assert called == ["recruit", "leave"]


def test_arena_hides_boss_bout_once_ribbit_brothers_beaten():
    from gartok.app import App
    app = App.__new__(App)
    app.guild = Guild([Unit("player")], node="arena")
    app.guild.deeds_done = ["arena_dethrone"]
    app.ui_fonts = None

    captured = {}
    def fake_squad_screen(fonts, roster, node, **kw):
        captured["offers"] = kw["arena_offers"]
        return object()

    import gartok.app as app_mod
    orig = app_mod.SquadScreen
    app_mod.SquadScreen = fake_squad_screen
    try:
        app._open_arena(app.guild.groups[0], world.node("arena"))
        names = {o.name for o in captured["offers"] if o.stage2}
        assert "Games: The Ribbit Brothers" in names

        app.guild.deeds_done = ["arena_dethrone", "arena_ribbit_brothers"]
        app._open_arena(app.guild.groups[0], world.node("arena"))
        names2 = {o.name for o in captured["offers"] if o.stage2}
        assert "Games: The Ribbit Brothers" not in names2
    finally:
        app_mod.SquadScreen = orig


def test_unrecruited_ribbit_brothers_can_cameo_in_games():
    guild = Guild([Unit("player")], deeds_done=["arena_dethrone", "arena_ribbit_brothers"])
    brawl = arena.brawl_bout()

    names = set()
    for seed in range(80):
        random.seed(seed)
        enemies, _ = matchup.build(world.node("arena"), brawl, squad_size=3, guild=guild)
        names.update(e.name for e in enemies)

    # Within 80 rolls, at least one of the 3 unrecruited brothers should cameo
    assert any(n in names for n in ("Bufo", "Ribit", "Peep"))


def test_recruited_ribbit_brothers_never_cameo():
    # If all three brothers are recruited into the guild roster, none can cameo
    brothers = arena.load_ribbit_brothers()
    guild = Guild([Unit("player"), *brothers],
                  deeds_done=["arena_dethrone", "arena_ribbit_brothers"])
    brawl = arena.brawl_bout()

    names = set()
    for seed in range(80):
        random.seed(seed)
        enemies, _ = matchup.build(world.node("arena"), brawl, squad_size=3, guild=guild)
        names.update(e.name for e in enemies)

    assert not any(n in names for n in ("Bufo", "Ribit", "Peep"))


def test_recruited_adelio_never_cameos():
    from tests.helpers import Unit as HelperUnit
    adelio = arena.load_champion()
    adelio.side = "player"
    guild = Guild([adelio], deeds_done=["arena_dethrone"])
    rookie = arena.scrapper_bout()

    names = set()
    for seed in range(80):
        random.seed(seed)
        enemies, _ = matchup.build(world.node("arena"), rookie, squad_size=1, guild=guild)
        names.update(e.name for e in enemies)

    assert "Adelio Small-Knife" not in names

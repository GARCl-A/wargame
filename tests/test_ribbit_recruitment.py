"""Tests for Ribbit brothers recruitment, arena offer filter, and cameos."""

import random

from gartok import arena, matchup, world
from gartok.guild import Guild
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


def test_unrecruited_ribbit_brothers_can_cameo_in_games():
    guild = Guild([Unit("player")], deeds_done=["arena_dethrone", "arena_ribbit_brothers"])
    brawl = arena.brawl_bout()

    names = set()
    for seed in range(160):
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
    for seed in range(160):
        random.seed(seed)
        enemies, _ = matchup.build(world.node("arena"), brawl, squad_size=3, guild=guild)
        names.update(e.name for e in enemies)

    assert not any(n in names for n in ("Bufo", "Ribit", "Peep"))


def test_recruited_adelio_never_cameos():
    adelio = arena.load_champion()
    adelio.side = "player"
    guild = Guild([adelio], deeds_done=["arena_dethrone"])
    rookie = arena.scrapper_bout()

    names = set()
    for seed in range(160):
        random.seed(seed)
        enemies, _ = matchup.build(world.node("arena"), rookie, squad_size=1, guild=guild)
        names.update(e.name for e in enemies)

    assert "Adelio Small-Knife" not in names

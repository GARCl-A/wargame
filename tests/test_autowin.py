"""Tests for the Auto-Win Monte Carlo simulation and eligibility criteria."""

import time

from gartok import autowin, campaign, data, world
from gartok.battle import Battle
from gartok.guild import Guild
from gartok.scenario import Scenario
from gartok.unit import Unit


def _make_fighter(level=4, weapon="Broadsword", hp=20):
    u = Unit("player", name=f"Hero_L{level}")
    u.strength = 18
    u.dexterity = 14
    u.constitution = 14
    u.equipped_weapon = weapon
    u.equipped_offhand = None
    u.hp_max = hp
    u.hp = hp
    return u


def _make_scrapper(name="Ruffian", hp=4):
    u = Unit("enemy", name=name)
    u.strength = 8
    u.dexterity = 8
    u.constitution = 8
    u.equipped_weapon = "Club"
    u.hp_max = hp
    u.hp = hp
    return u


def test_autowin_overwhelming_victory():
    squad = [_make_fighter(level=4, hp=25) for _ in range(4)]
    enemies = [_make_scrapper(hp=3)]
    res = autowin.simulate_matchup(squad, enemies, max_iterations=5, max_time=0.5)
    assert res.eligible is True
    assert res.win_rate == 1.0
    assert res.iterations > 0
    assert isinstance(res.avg_damage, dict)


def test_autowin_disqualified_by_danger_or_defeat():
    weakling = [_make_scrapper(hp=2)]
    bosses = [_make_fighter(level=5, hp=30) for _ in range(4)]
    res = autowin.simulate_matchup(weakling, bosses, max_iterations=5, max_time=0.5)
    assert res.eligible is False


def test_autowin_disqualified_by_ammo_spent():
    archer = Unit("player", name="Archer")
    archer.strength = 14
    archer.dexterity = 16
    archer.hp_max = 20
    archer.hp = 20
    archer.equipped_weapon = "Light Crossbow"
    archer.give_to_pack(data.AMMO_ITEM)
    archer.quiver_charges = 10

    enemies = [_make_scrapper(hp=15)]
    res = autowin.simulate_matchup([archer], enemies, max_iterations=5, max_time=0.5)
    # Even if archer wins, using a crossbow uses ammo, which strictly invalidates auto-win
    assert res.eligible is False


def test_autowin_estimator_thread():
    squad = [_make_fighter(level=4, hp=25) for _ in range(4)]
    enemies = [_make_scrapper(hp=3)]
    estimator = autowin.AutoWinEstimator()
    estimator.request(squad, enemies, max_iterations=5, max_time=0.5)
    assert estimator.computing is True

    # Wait for background thread
    for _ in range(50):
        if not estimator.computing:
            break
        time.sleep(0.02)

    assert estimator.computing is False
    assert estimator.result is not None
    assert estimator.result.eligible is True


def test_autowin_resolution_absorption():
    hero = _make_fighter(level=4, hp=20)
    guild = Guild([hero])
    enemy = _make_scrapper(hp=5)
    enemy.give_to_pack("Copper Coin")

    squad = [hero]
    enemies = [enemy]

    # Simulate damage application and instant win battle construction
    avg_damage = 2.0
    hero.hp = max(1, hero.hp - round(avg_damage))
    assert hero.hp == 18

    # Create battle in resolved state
    battle = Battle(squad, enemies, scenario=Scenario(), lethal=True)
    for c in battle.enemy_units:
        c.hp = 0
        c.status = "dead"
    for c in battle.player_units:
        c.status = "up"
        c.combat_xp_earned = 0
    battle.winner = "player"
    battle.round_no = 2

    victories_before = guild.battles_won
    outcome = campaign.absorb_battle(guild, squad, battle, node=world.node("road"))

    assert outcome.won is True
    assert guild.battles_won == victories_before + 1
    assert hero.combat_xp == 0
    assert hero.hp == 18
    assert outcome.loot_pool  # Enemy drop is available for loot


def test_combatant_respects_char_current_hp():
    hero = _make_fighter(level=4, hp=20)
    hero.hp = 14  # Wounded outside battle
    from gartok.combatant import Combatant
    c = Combatant(hero)
    assert c.hp == 14
    assert c.hp_max == 20


def test_autowin_hunt_screen_flow():
    import sys
    from unittest.mock import MagicMock
    if "pygame" not in sys.modules:
        try:
            pass
        except Exception:
            sys.modules["pygame"] = MagicMock()
            sys.modules["pygame.base"] = MagicMock()

    from gartok import hunt
    from gartok.hunt_screen import HuntScreen

    hero = _make_fighter(level=4, hp=20)
    guild = Guild([hero])
    group = guild.groups[0]
    group.node = "wilds"
    state = hunt.HuntState(list(group.members), world.node("wilds"), hours_left=4)

    autowin_called = []
    def on_autowin(st, pack, res):
        autowin_called.append((st, pack, res))

    def on_ambush(st, pack):
        pass

    screen = HuntScreen(None, guild, state, phase="setup",
                        on_ambush=on_ambush, on_done=lambda: None,
                        on_autowin=on_autowin)
    
    # Simulate an ambush triggering
    screen.ambush_pack = [_make_scrapper(hp=2)]
    screen.phase = "ambush"
    screen.autowin_estimator.result = autowin.AutoWinResult(eligible=True, win_rate=1.0)

    # Click autowin
    btn_rect = MagicMock()
    btn_rect.collidepoint.return_value = True
    screen.buttons = [("autowin_ambush", btn_rect)]
    screen._click((0, 0))
    assert len(autowin_called) == 1
    assert autowin_called[0][2].eligible is True


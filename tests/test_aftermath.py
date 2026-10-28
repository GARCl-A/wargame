"""The screens after a fight: the memorial, the after-action report, the level-up card, and the
VICTORY / FLED / DEFEAT word the battle screen and the report share."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


from gartok import aftermath, campaign, persist
from gartok.clock import Clock
from gartok.guild import Guild
from gartok.unit import Unit
from tests.helpers import Battle, _unit, world

NODE = "wilds"


def _fight(n=2, foes=1, seed=0):
    squad = [_unit(seed=seed + i) for i in range(n)]
    enemies = [_unit(team="enemy", seed=100 + seed + i) for i in range(foes)]
    guild = Guild(squad, node=NODE)
    battle = Battle(squad, enemies, lethal=True)
    return guild, squad, battle


def _won(battle, killer=0):
    hand = battle.player_units[killer]
    for c in battle.enemy_units:
        c.hp, c.status = 0, "dead"
        hand.credit_kill(c)
    battle.winner = "player"


def _death(battle, victim, by):
    victim.hp, victim.status = 0, "dead"
    victim.downed_by = by
    battle.log(f"{victim.name} goes down.")


# --------------------------------------------------------------------------- #
# the data                                                                     #
# --------------------------------------------------------------------------- #
def test_the_report_names_who_downed_whom_and_the_squad_status():
    guild, squad, battle = _fight(n=2)
    foe = battle.enemy_units[0]
    _death(battle, battle.player_units[1], foe)
    _won(battle)
    outcome = campaign.absorb_battle(guild, squad, battle, node=world.node(NODE))
    assert outcome.result == "VICTORY"
    assert [r.status for r in outcome.report] == ["standing", "fallen"]
    assert outcome.report[0].downed == [foe.name]
    assert (foe.name, squad[1].name, True) in outcome.takedowns
    assert (squad[0].name, foe.name, False) in outcome.takedowns


def test_a_death_in_battle_leaves_a_memorial_with_the_killer_place_and_days():
    guild, squad, battle = _fight(n=2)
    guild.clock = Clock(24 * 9 * 3600)
    squad[1].joined_day = 4
    foe = battle.enemy_units[0]
    _death(battle, battle.player_units[1], foe)
    _won(battle)
    outcome = campaign.absorb_battle(guild, squad, battle, node=world.node(NODE))
    [m] = outcome.memorials
    assert m.name == squad[1].name and m.killer == foe.name
    assert m.place == world.node(NODE).name and m.cause == "Killed in combat"
    assert m.day == guild.clock.day and m.days_lived == guild.clock.day - 4 + 1
    assert m.line and squad[1].name in m.line


def test_a_level_up_keeps_the_numbers_before_and_after():
    guild, squad, battle = _fight(n=1, foes=1)
    battle.player_units[0].combat_xp_earned = 50
    battle.winner = "player"
    before = squad[0].combat_level
    outcome = campaign.absorb_battle(guild, squad, battle, node=world.node(NODE))
    [lu] = outcome.level_ups
    assert lu.unit is squad[0] and lu.before["combat"] == before
    assert lu.after["combat"] == squad[0].combat_level > before
    labels = [g[0] for g in lu.gains]
    assert labels[0] == "Combat level"
    assert outcome.report[0].xp_gain == 50 and outcome.report[0].xp_before == 0


def test_no_xp_no_level_up():
    guild, squad, battle = _fight(n=1)
    battle.winner = "player"
    outcome = campaign.absorb_battle(guild, squad, battle, node=world.node(NODE))
    assert outcome.level_ups == [] and outcome.memorials == []


def test_the_result_word_reads_the_side_not_just_a_winner():
    _, _, battle = _fight(n=2)
    assert aftermath.result_word(battle) == "DEFEAT"
    battle.winner = "enemy"
    assert aftermath.result_word(battle) == "DEFEAT"
    assert aftermath.result_word(battle, "enemy") == "VICTORY"
    battle.player_units[0].status = "fled"
    assert aftermath.result_word(battle) == "FLED"
    battle.winner = "player"
    assert aftermath.result_word(battle) == "VICTORY"


def test_the_battle_screen_says_the_squad_fled():
    from gartok.battle_screen import BattleScreen
    _, _, battle = _fight(n=1)
    battle.player_units[0].status = "fled"
    battle.winner = "enemy"
    scr = BattleScreen(None, battle, on_battle_end=lambda *a: None)
    assert scr._winner_text() == "You fled"


# --------------------------------------------------------------------------- #
# joining day                                                                  #
# --------------------------------------------------------------------------- #
def test_a_recruit_signs_on_the_day_it_joins_and_keeps_it_through_a_save():
    guild, squad, _ = _fight(n=1)
    guild.clock = Clock(24 * 6 * 3600)
    newcomer = _unit(seed=50)
    guild.add_member(newcomer, guild.groups[0])
    assert newcomer.joined_day == guild.clock.day and squad[0].joined_day == 1
    back = Unit.from_save(persist.unit_to_dict(newcomer))
    assert back.joined_day == guild.clock.day


def test_an_old_save_without_the_day_reads_as_day_one():
    d = persist.unit_to_dict(_unit(seed=3))
    del d["joined_day"]
    assert Unit.from_save(d).joined_day == 1


def test_a_starved_member_gets_a_memorial_with_where_they_fell():
    u = _unit(seed=1)
    guild = Guild([u, _unit(seed=2)], node="market")
    u._base_inventory = []
    for other in guild.roster:
        other._base_inventory = []
    for _ in range(30):
        guild.pass_time(24)
        if u not in guild.roster:
            break
    assert u not in guild.roster
    assert u.memorial.cause == "Starved to death" and u.memorial.place == world.node("market").name
    assert "without a meal" in u.memorial.line


# --------------------------------------------------------------------------- #
# the flow                                                                     #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# the screens                                                                  #
# --------------------------------------------------------------------------- #


def test_work_shift_level_up_queues_pending_level_up():
    from gartok import economy, orders
    u = _unit(seed=7)
    guild = Guild([u], node="lumber_yard")
    u.work_hours = 2 * economy.LUMBER_XP_HOURS - 2
    guild.groups[0].order = orders.work(guild, guild.groups[0], 4)
    res = campaign.advance(guild)
    assert len(res.level_ups) == 1
    lu = res.level_ups[0]
    assert lu.unit is u
    assert ("Work level", 0, 1) in lu.gains

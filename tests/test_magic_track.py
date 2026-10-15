"""The magic track (talents.py / progression.py) and the Dragon Breath it grants."""

from unittest.mock import patch

from gartok import ai, campaign, magic, progression
from gartok.board import cone_cells
from tests.helpers import Battle, Combatant, Unit, actions, persist


def _blooded(level=2, *picks):
    u = Unit("enemy")
    u.add_magic_source("blood")
    u.set_track_level("magic", level)
    for tid in picks:
        assert u.choose_talent("magic", tid)
    return u


def test_the_school_root_is_granted_by_initiation_never_picked():
    u = Unit("player")
    assert not u.holds_talent("magic", "bloodline")
    u.add_magic_source("blood")
    assert u.holds_talent("magic", "bloodline") and u.has_talent("bloodline")
    u.set_track_level("magic", 1)
    assert not u.choose_talent("magic", "bloodline")
    assert u.talents["magic"] == []


def test_a_branch_opens_only_under_a_school_the_unit_holds():
    u = Unit("player")
    u.set_track_level("magic", 2)
    assert not u.choose_talent("magic", "dragon")
    assert "magic" not in u.pending_picks
    u.add_magic_source("blood")
    assert "magic" in u.pending_picks
    assert u.choose_talent("magic", "dragon")


def test_dragon_hardens_the_hide_and_losing_the_school_drops_the_branch():
    u = Unit("player")
    ac = u.ac
    u.add_magic_source("blood")
    u.set_track_level("magic", 2)
    u.choose_talent("magic", "dragon")
    u.choose_talent("magic", "dragon_breath")
    assert u.ac == ac + 1
    u.set_magic_source("blood", False)
    assert u.talents["magic"] == [] and u.ac == ac


def test_magic_levels_feed_the_racial_track():
    u = Unit("player")
    u.set_track_level("combat", 2)
    u.set_track_level("work", 2)
    before = u.racial_xp
    u.set_track_level("magic", 3)
    assert u.racial_xp == before + 3


def test_a_magic_kill_banks_magic_xp_not_combat_xp():
    batt = Battle([Unit("player")], [Unit("enemy")])
    mage, foe = batt.units
    mage.credit_kill(foe, magic=True)
    assert mage.magic_xp_earned == progression.xp_award(0, foe.combat_level)
    assert mage.combat_xp_earned == 0


def test_absorbing_a_battle_banks_the_magic_xp():
    from gartok.guild import Guild
    p = Unit("player")
    guild = Guild([p])
    batt = Battle([p], [Unit("enemy")])
    mage, foe = batt.player_units[0], batt.enemy_units[0]
    mage.magic_xp_earned = 3
    foe.status, foe.hp = "dead", 0
    batt.winner = "player"
    out = campaign.absorb_battle(guild, [p], batt)
    assert p.magic_xp == 3 and out.xp_awards[p.name] == 3


def test_finishing_a_spell_study_banks_magic_xp():
    u = Unit("player")
    u.add_magic_source("nature")
    u.give_to_pack("Scroll of Light Globe")
    magic.begin_study(u, "light_globe")
    u.study_progress = magic.points_to_learn(0)
    magic.progress_study(u)
    assert "light_globe" in u.spells_known
    assert u.magic_xp == magic.study_xp(magic.SPELLS["light_globe"])


def test_magic_xp_and_picks_survive_a_save():
    u = _blooded(2, "dragon")
    back = Unit.from_save(persist.unit_to_dict(u))
    assert back.magic_xp == u.magic_xp and back.talents["magic"] == ["dragon"]


def test_a_save_without_a_magic_track_still_loads():
    d = persist.unit_to_dict(Unit("player"))
    del d["talents"]["magic"]
    del d["magic_xp"]
    assert Unit.from_save(d).talents["magic"] == []


def test_a_cone_is_one_three_and_five_cells_wide():
    east = cone_cells((5, 5), (1, 0), 3)
    assert sorted(east) == sorted([(6, 5), (7, 4), (7, 5), (7, 6),
                                   (8, 3), (8, 4), (8, 5), (8, 6), (8, 7)])
    diag = cone_cells((5, 5), (1, 1), 3)
    assert len(diag) == 9 and (6, 6) in diag and (8, 8) in diag and (6, 8) in diag


def _breath_battle(players, breather_pos=(5, 5)):
    batt = Battle([Unit("player") for _ in players], [_blooded(2, "dragon", "dragon_breath")])
    batt.board.walls.clear()
    for u, pos in zip(batt.player_units, players):
        u.pos = pos
    dragon = batt.enemy_units[0]
    dragon.pos, dragon.ap = breather_pos, 2
    return batt, dragon


def _join(batt, team, pos):
    c = Combatant(Unit(team), team)
    c.pos = pos
    batt.units.append(c)
    (batt.player_units if team == "player" else batt.enemy_units).append(c)
    return c


def test_dragon_breath_needs_the_talent():
    batt = Battle([Unit("player")], [Unit("enemy")])
    assert not actions.DRAGON_BREATH.available(batt, batt.enemy_units[0])
    batt, dragon = _breath_battle([(6, 5)])
    assert actions.DRAGON_BREATH.available(batt, dragon)


def test_one_roll_hits_everyone_in_the_cone_allies_too():
    batt, dragon = _breath_battle([(6, 5), (7, 4)])
    ally_c = _join(batt, "enemy", (8, 5))
    far = _join(batt, "player", (5, 9))
    for u in batt.units:
        u.hp = 30
    hp = {u: u.hp for u in batt.units}
    with patch("gartok.actions.combat.d20", return_value=20), \
            patch("gartok.actions.combat.roll", return_value=5) as dice:
        actions.DRAGON_BREATH.execute(batt, dragon, (6, 5))
    assert dragon.ap == 0
    assert dice.call_count == 3
    assert all(hp[u] - u.hp == max(0, 5 - u.dr) for u in (*batt.player_units[:2], ally_c))
    assert far.hp == hp[far]


def test_a_wall_shelters_whoever_stands_behind_it():
    batt, dragon = _breath_battle([(8, 5)])
    batt.board.walls.update({(6, 5), (7, 5), (7, 4), (7, 6)})
    assert batt.player_units[0] not in actions.DRAGON_BREATH.caught(batt, dragon, (6, 4))


def test_a_breath_kill_is_magic_xp():
    batt, dragon = _breath_battle([(6, 5)])
    victim = batt.player_units[0]
    victim.hp = 1
    with patch("gartok.actions.combat.d20", return_value=20):
        actions.DRAGON_BREATH.execute(batt, dragon, (6, 5))
    assert not victim.alive and dragon.kills == 1 and dragon.combat_xp_earned == 0


def test_the_ai_breathes_only_on_three_foes_or_more():
    batt, dragon = _breath_battle([(6, 5), (7, 4), (7, 6)])
    with patch("gartok.actions.combat.d20", return_value=1):
        assert ai._try_breath(batt, dragon)
    batt, dragon = _breath_battle([(6, 5), (7, 4)])
    assert not ai._try_breath(batt, dragon)


def test_the_ai_holds_its_breath_when_its_own_side_would_take_as_much():
    batt, dragon = _breath_battle([(6, 5), (7, 4), (7, 6)])
    for pos in ((8, 3), (8, 4), (8, 5)):
        _join(batt, "enemy", pos)
    assert not ai._try_breath(batt, dragon)

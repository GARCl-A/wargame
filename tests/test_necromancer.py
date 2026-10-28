"""The Faith Order's second errand (missions.FAITH_NECROMANCER, necromancer.py): a third side on
the board, Raise Dead and Invisibility (level 2), Search, the Zombie, the necromancer's fall and
the withdraw, the mission and the AI."""

import random

from gartok import (
    actions,
    ai,
    artwork,
    data,
    factions,
    loot,
    magic,
    missions,
    necromancer,
)
from gartok.clock import Clock
from gartok.conditions import Invisible
from gartok.guild import Guild
from tests.helpers import Battle, Unit

RAISE = "raise_dead"


def _three_sides(seed=3):
    """A player, an enemy and an undead on an open board, nobody in reach of anybody."""
    random.seed(seed)
    batt = Battle([Unit("player")], [Unit("enemy")], others={"undead": [Unit("enemy")]})
    p, e, z = batt.units
    batt.board.walls.clear()
    batt.ambient_light = True
    p.pos, e.pos, z.pos = (1, 1), (10, 1), (5, 6)
    return batt, p, e, z


def _caster(batt, unit, *spells):
    unit.spells_known = list(spells)
    unit.ap = 2
    return unit


def _kill(unit):
    unit.hp, unit.status = 0, "dead"


# --- three sides ------------------------------------------------------------- #

def test_a_third_side_is_hostile_to_both_others():
    batt, _p, e, z = _three_sides()
    assert batt.teams == ["player", "enemy", "undead"]
    assert z.team == "undead" and z in batt.foe_units and z not in batt.enemy_units
    z.pos = (11, 1)
    assert actions.ATTACK.can(batt, e, z) or batt.units_distance(e, z) == 1
    _, enemies = batt.cells_by_side(e)
    assert z.pos in enemies
    assert set(batt.intel.margin) == {"player", "enemy", "undead"}


def test_the_player_wins_only_once_every_other_side_is_down():
    batt, _p, e, z = _three_sides()
    _kill(e)
    assert batt._check_winner() is None              # the undead still stand
    _kill(z)
    assert batt._check_winner() == "player"


def test_a_two_sided_fight_has_no_further_side():
    random.seed(1)
    batt = Battle([Unit("player")], [Unit("enemy")])
    assert batt.teams == ["player", "enemy"] and batt.other_units == []


def test_a_body_laid_out_dead_never_takes_the_first_turn():
    random.seed(1)
    sc = necromancer.NecromancerScenario([Unit("player")], random.Random(1))
    batt = Battle([Unit("player")], sc.enemies, scenario=sc, allies=sc.allies, others=sc.others)
    assert batt.active.alive


# --- Raise Dead ---------------------------------------------------------------- #

def test_raise_dead_is_faith_level_two_and_costs_both_actions():
    spell = magic.SPELLS[RAISE]
    assert spell.level == 2 and spell.sources == ("faith",)
    assert actions.CastSpellAction(RAISE).cost == 2
    assert magic.SPELLS["invisibility"].level == 2 and len(magic.SPELLS["invisibility"].sources) == 3


def test_raise_dead_stands_a_dead_body_up_on_the_casters_side_with_one_hp():
    batt, _p, e, z = _three_sides()
    _caster(batt, z, RAISE)
    e.pos = (7, 6)
    raise_dead = actions.CastSpellAction(RAISE)
    assert not raise_dead.can(batt, z, e.pos)        # alive: nothing to raise
    e.status = "dying"
    assert not raise_dead.can(batt, z, e.pos)        # dying is not dead
    _kill(e)
    assert raise_dead.can(batt, z, e.pos)
    raise_dead.execute(batt, z, e.pos)
    assert e.alive and e.hp == 1 and e.team == "undead" and e.raised
    assert z.ap == 0
    assert any("rises again" in line and str(e.pos) in line for line in batt.log_lines)


def test_a_raised_body_falls_for_good_and_is_not_raised_twice():
    batt, _p, e, z = _three_sides()
    _caster(batt, z, RAISE)
    e.pos = (7, 6)
    _kill(e)
    actions.CastSpellAction(RAISE).execute(batt, z, e.pos)
    e.take_damage(5, batt.log)
    assert e.dead
    z.ap = 2
    assert not actions.CastSpellAction(RAISE).can(batt, z, e.pos)


def test_raise_dead_needs_reach_and_sight():
    batt, _p, e, z = _three_sides()
    _caster(batt, z, RAISE)
    _kill(e)
    e.pos = (5 + actions.RaiseDeadAction.REACH + 1, 6)
    assert not actions.CastSpellAction(RAISE).can(batt, z, e.pos)
    e.pos = (8, 6)
    batt.board.walls.update({(7, y) for y in range(12)})
    assert not actions.CastSpellAction(RAISE).can(batt, z, e.pos)


def test_a_guild_members_body_can_be_raised_against_the_guild():
    batt, p, e, z = _three_sides()
    _caster(batt, z, RAISE)
    p.pos = (7, 6)
    _kill(p)
    actions.CastSpellAction(RAISE).execute(batt, z, p.pos)
    assert p.team == "undead" and p in batt.player_units
    assert actions._hostile_target(e, p)


def test_the_raised_cannot_be_put_to_sleep():
    batt, p, e, z = _three_sides()
    _caster(batt, z, RAISE)
    e.pos = (7, 6)
    _kill(e)
    actions.CastSpellAction(RAISE).execute(batt, z, e.pos)
    _caster(batt, p, "sleep")
    p.pos = (3, 6)
    actions.CastSpellAction("sleep").execute(batt, p, e)
    assert not e.has_condition("sleeping")


# --- Invisibility and Search ----------------------------------------------------- #

def test_an_invisible_unit_is_unseen_and_untargetable_by_other_sides():
    batt, p, _e, z = _three_sides()
    z.add_condition(Invisible())
    p.pos = (4, 6)
    assert not batt.can_see_unit(p, z)
    assert not actions.ATTACK.can(batt, p, z)
    _caster(batt, p, "magic_missile")
    assert not actions.CastSpellAction("magic_missile").can(batt, p, z)
    assert ai._target(batt, p) is not z


def test_casting_invisibility_takes_both_actions_once():
    batt, _p, _e, z = _three_sides()
    _caster(batt, z, "invisibility")
    vanish = actions.CastSpellAction("invisibility")
    vanish.execute(batt, z)
    assert z.has_condition("invisible") and z.ap == 0
    z.ap = 2
    assert not vanish.available(batt, z)


def test_raising_keeps_the_caster_hidden_but_a_blow_breaks_it():
    batt, p, e, z = _three_sides()
    _caster(batt, z, RAISE, "magic_missile")
    z.add_condition(Invisible())
    e.pos = (7, 6)
    _kill(e)
    actions.CastSpellAction(RAISE).execute(batt, z, e.pos)
    assert z.has_condition("invisible")
    p.pos = (4, 6)
    z.ap = 2
    random.seed(0)
    missile = actions.CastSpellAction("magic_missile")
    for _ in range(20):                             # until one lands
        hp = p.hp
        z.ap = 2
        missile.execute(batt, z, p)
        if p.hp < hp:
            break
    assert not z.has_condition("invisible")


def test_walking_into_an_unseen_foe_bumps_into_it_and_shows_it():
    batt, p, _e, z = _three_sides()
    z.add_condition(Invisible())
    z.pos = (3, 1)
    p.ap = 2
    assert actions.MOVE.can(batt, p, (5, 1)) or (5, 1) in batt.reachable(p)
    batt.move_unit(p, (5, 1))
    assert p.pos == (2, 1)
    assert batt.can_see_unit(p, z) and not z.hidden_from("player")
    assert z.hidden_from("enemy")                    # only the side that bumped into it


def test_investigate_finds_an_unseen_foe_close_by(monkeypatch):
    from gartok.actions import support
    batt, p, _e, z = _three_sides()
    z.add_condition(Invisible())
    p.ap = 2
    assert actions.INVESTIGATE.available(batt, p)
    p.pos, p.ap = (4, 4), 2
    monkeypatch.setattr(support, "d20", lambda: 20)
    actions.INVESTIGATE.execute(batt, p)
    assert not z.hidden_from("player")
    z.condition("invisible").on_turn_start(z, batt.log)     # its own turn: it slips away again
    assert z.hidden_from("player")


def test_investigate_misses_a_foe_out_of_range_and_is_offered_only_with_one_hidden(monkeypatch):
    from gartok.actions import support
    batt, p, _e, z = _three_sides()
    p.ap = 2
    assert not actions.INVESTIGATE.available(batt, p)
    z.add_condition(Invisible())
    p.ap = 2
    monkeypatch.setattr(support, "d20", lambda: 20)
    actions.INVESTIGATE.execute(batt, p)                  # (1, 1) to (5, 6): too far
    assert z.hidden_from("player")


def test_a_wound_shows_an_invisible_unit_to_every_side():
    batt, _p, _e, z = _three_sides()
    z.add_condition(Invisible())
    z.take_damage(1, batt.log)
    assert not z.hidden_from("player") and not z.hidden_from("enemy")


# --- the Zombie -------------------------------------------------------------------- #

def test_the_zombie_is_a_slow_tough_undead_with_its_own_portraits():
    zombie = data.race_by_name("Zombie")
    assert zombie["kind"] == "undead" and "sleep_immunity" in zombie["ability"]
    assert zombie["speed"] < data.race_by_name("Skeleton")["speed"]
    assert zombie["mods"][2] == 4
    assert "Zombie" not in data.RACE_NAMES and "Zombie" in data.ALL_RACE_NAMES
    assert artwork.RACE_ICON["Zombie"]
    assert artwork.portrait("Zombie", 0, 32) is not None


def test_the_dead_do_not_run():
    random.seed(2)
    z = Unit("enemy", race=data.race_by_name("Zombie"))
    batt = Battle([Unit("player"), Unit("player"), Unit("player")], [z])
    undead = batt.enemy_units[0]
    undead.hp = 1
    assert not ai._should_flee(batt, undead)


# --- the scenario ------------------------------------------------------------------ #

def _front(seed=4, level=3):
    random.seed(seed)
    squad = [Unit("player") for _ in range(4)]
    for u in squad:
        u.set_track_level("combat", level)
    sc = necromancer.NecromancerScenario(squad, random.Random(seed))
    batt = Battle(squad, sc.enemies, scenario=sc, allies=sc.allies, others=sc.others,
                  daylight=False, aggressor="enemy")
    return batt, sc


def test_the_front_is_a_big_dark_field_with_four_groups_and_the_dead_of_days_before():
    batt, _sc = _front()
    assert (batt.board.cols, batt.board.rows) == (necromancer.COLS, necromancer.ROWS)
    assert not batt.ambient_light
    allies = [u for u in batt.player_units if u.ai_ally]
    assert len(allies) == necromancer.SOLDIERS < len(batt.enemy_units) == necromancer.WARBAND
    caster = necromancer.the_necromancer(batt)
    assert caster.team == "undead" and caster.has_condition("invisible") and caster.racial_level == 15
    assert sum(1 for u in batt.units if u.race["name"] == "Zombie") == necromancer.ZOMBIES
    fallen = [u for u in batt.units if u.team == necromancer.FALLEN]
    assert len(fallen) == necromancer.CORPSES and all(u.dead for u in fallen)
    assert all(necromancer.PARAPET_X[0] < u.pos[0] < necromancer.PARAPET_X[1] for u in fallen)


def test_his_fall_drops_his_dead_and_opens_the_withdraw():
    batt, _sc = _front()
    caster = necromancer.the_necromancer(batt)
    assert not batt.can_withdraw
    caster.take_damage(999, batt.log)
    assert batt._check_winner() is None             # the warband still stands
    assert all(not u.alive for u in batt.units if u.team == "undead")
    assert necromancer.errand_met(batt) and batt.can_withdraw
    batt.withdraw()
    assert batt.winner == "player" and batt.withdrew


def test_fighting_on_ends_as_a_normal_fight_and_keeps_the_errand():
    batt, _sc = _front()
    necromancer.the_necromancer(batt).take_damage(999, batt.log)
    batt._check_winner()
    for u in batt.enemy_units:
        _kill(u)
    assert batt._check_winner() is None and batt.binding_captives     # he lies dying: bind him or not
    batt.round_no += 2
    assert batt._check_winner() == "player" and not batt.withdrew
    assert necromancer.errand_met(batt)


def test_the_field_is_rich_with_what_every_body_wore_and_his_pack():
    batt, _sc = _front()
    caster = necromancer.the_necromancer(batt)
    caster.take_damage(999, batt.log)
    batt._check_winner()
    worn = [u.char.equipped_armor for u in batt.units if u.team != "player" and u.char.equipped_armor]
    pool = loot.field_loot(batt, [], random.Random(0))
    assert worn and all(pool.count(a) >= worn.count(a) for a in set(worn))
    assert "Precious Gemstone" in pool and "Scroll of Raise Dead" in pool and "Scroll of Healing Touch" in pool
    assert "Gold Coin" not in pool and "Copper Coin" not in pool


def test_only_a_field_that_strips_the_dead_gives_up_their_armour():
    random.seed(2)
    foe = Unit("enemy")
    foe.give_to_armor("Leather Jerkin")
    batt = Battle([Unit("player")], [foe])
    _kill(batt.enemy_units[0])
    assert "Leather Jerkin" not in loot.field_loot(batt, [], random.Random(0))


# --- the AI ------------------------------------------------------------------------ #

def test_the_necromancer_raises_the_strongest_body_in_reach_and_never_strikes():
    batt, _p, e, z = _three_sides()
    _caster(batt, z, RAISE, "magic_missile")
    z.add_condition(Invisible())
    e.pos = (7, 6)
    _kill(e)
    weak = Unit("enemy")
    batt.reinforce(weak, [(6, 8)], team="enemy")
    body = batt.units[-1]
    body.hp_max_cache = None
    _kill(body)
    batt.order = [z]
    batt.turn_idx = 0
    strongest = max([e, body], key=lambda u: u.hp_max)
    ai.take_turn(batt, z)
    assert strongest.alive and strongest.team == "undead"
    assert z.has_condition("invisible")


def test_the_necromancer_walks_toward_a_far_body():
    batt, _p, e, z = _three_sides()
    _caster(batt, z, RAISE)
    e.pos = (15, 10)
    _kill(e)
    before = batt.units_distance(z, e)
    batt.order, batt.turn_idx = [z], 0
    ai.take_turn(batt, z)
    assert batt.units_distance(z, e) < before


def test_with_nothing_in_sight_the_ai_searches_for_what_it_cannot_see():
    batt, p, e, z = _three_sides()
    _kill(e)
    z.add_condition(Invisible())
    batt.ambient_light = True
    batt.order, batt.turn_idx = [p], 0
    p.ap = 2
    ai.take_turn(batt, p)
    assert any("searches" in line for line in batt.log_lines)       # Investigate, with no wall about


# --- the mission ------------------------------------------------------------------- #

def _guild():
    random.seed(5)
    members = [Unit("player"), Unit("player")]
    guild = Guild(members, node="faith_cathedral", clock=Clock(10 * 3600))
    for t in (missions.LIBRARY_ANCIENT_CODEX, missions.FAITH_BATTLEFIELD):
        guild.missions.append(missions.Mission(t.id, members[0].uid, 0, None, state="done"))
    return guild, members


def test_the_cathedral_asks_once_mercy_at_the_front_is_done():
    guild, _ = _guild()
    assert missions.FAITH_NECROMANCER in missions.offers_at(guild, "faith_cathedral")
    guild.missions.pop()
    assert missions.FAITH_NECROMANCER not in missions.offers_at(guild, "faith_cathedral")


def test_the_errand_opens_the_skirmish_for_the_group_that_carries_it():
    guild, (signer, _) = _guild()
    missions.accept(guild, signer, missions.FAITH_NECROMANCER)
    group = guild.group_of(signer)
    assert missions.pending_necromancer(guild, group) is not None
    assert missions.pending_front(guild, group) is missions.pending_necromancer(guild, group)


def test_his_fall_settles_the_errand_with_the_faith_orders_deed():
    guild, (signer, _) = _guild()
    m = missions.accept(guild, signer, missions.FAITH_NECROMANCER)
    _notice, deeds = missions.settle_necromancer(guild, m, fallen=True)
    assert m.state == "done" and [d.id for d in deeds] == ["faith_necromancer"]
    assert "faith_battlefield" not in [d.id for d in deeds]
    assert factions.DEEDS["faith_necromancer"].faction == "faith_order"


def test_a_fight_he_survives_fails_the_errand_until_the_order_asks_again():
    guild, (signer, _) = _guild()
    m = missions.accept(guild, signer, missions.FAITH_NECROMANCER)
    notice, deeds = missions.settle_necromancer(guild, m, fallen=False)
    assert m.state == "failed" and not deeds and "14 days" in notice

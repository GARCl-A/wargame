"""Capture (actions.Capture) and the captives a group keeps afterwards (captives.py)."""

from gartok import ai, campaign, captives, cohesion
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import Battle, Unit, actions, items, persist


def _bound_fight(tool="Rope", foes=1):
    p = Unit("player")
    for t in ("Rope", "Chains"):
        p.remove_named(t, 99)
    p.give_to_pack(tool)
    guild = Guild([p])
    batt = Battle([p], [Unit("enemy") for _ in range(foes)])
    batt.board.walls.clear()
    me = batt.player_units[0]
    me.pos, me.ap = (5, 5), 2
    for i, foe in enumerate(batt.enemy_units):
        foe.pos = (6, 5 + i * 3)
    return guild, batt, me, batt.enemy_units[0]


def _down(foe, status="dying"):
    foe.hp, foe.status = 0, status


def test_capture_needs_a_rope_or_chains():
    _, batt, me, foe = _bound_fight(tool="Torch")
    _down(foe)
    assert not actions.CAPTURE.applicable(batt, me)[0]
    for tool in ("Rope", "Chains"):
        _, batt, me, foe = _bound_fight(tool=tool)
        _down(foe)
        assert actions.CAPTURE.can(batt, me, foe)


def test_capture_only_takes_an_adjacent_fallen_foe():
    _, batt, me, foe = _bound_fight()
    assert not actions.CAPTURE.can(batt, me, foe)          # still standing
    _down(foe, "stable")
    foe.pos = (8, 5)
    assert not actions.CAPTURE.can(batt, me, foe)          # out of reach


def test_a_bound_foe_is_spared_and_uses_up_the_rope():
    _, batt, me, foe = _bound_fight()
    _down(foe)
    actions.CAPTURE.execute(batt, me, foe)
    assert foe.captured and foe.status == "stable"
    assert "Rope" not in me.inventory and me.ap == 1
    assert not actions.ATTACK.can(batt, me, foe)


def test_the_squad_gets_one_round_to_bind_the_fallen():
    _, batt, _me, foe = _bound_fight()
    _down(foe, "stable")
    assert batt._check_winner() is None and batt.binding_captives
    batt.round_no += 2
    assert batt._check_winner() == "player"


def test_no_bind_round_without_a_rope():
    _, batt, _me, foe = _bound_fight(tool="Torch")
    _down(foe, "stable")
    assert batt._check_winner() == "player"


def test_a_won_fight_hands_the_captive_to_the_group():
    guild, batt, me, foe = _bound_fight()
    _down(foe)
    actions.CAPTURE.execute(batt, me, foe)
    batt.winner = "player"
    out = campaign.absorb_battle(guild, [me.char], batt)
    group = guild.groups[0]
    assert [c.unit for c in group.captives] == [foe.char] and out.captive_notes
    assert me.char.count_of("Rope") == 0


def test_a_captive_counts_on_the_herd_and_slips_away_past_it():
    group = Group([Unit("player")], node="city")
    for _ in range(group.herd_capacity + 1):
        group.captives.append(captives.Captive(Unit("enemy"), 0))
    assert group.herd_load > group.herd_capacity
    cohesion.stray(group)
    assert len(group.captives) == group.herd_capacity


def test_a_captive_dies_after_seven_days_leaving_a_body_worth_keeping():
    guild = Guild([Unit("player")])
    group = guild.groups[0]
    group.captives.append(captives.Captive(Unit("enemy"), guild.clock.day, "snake_dragon"))
    group.captives.append(captives.Captive(Unit("enemy"), guild.clock.day))
    for _ in range(captives.CAPTIVE_DAYS - 1):
        guild.clock.advance_hours(24)
        assert not captives.daily(guild)
    guild.clock.advance_hours(24)
    assert len(captives.daily(guild)) == 2 and not group.captives
    assert group.leader.count_of(items.SNAKE_DRAGON_CORPSE_ITEM) == 1


def test_the_body_rots_in_three_days():
    guild = Guild([Unit("player")])
    holder = guild.roster[0]
    holder.give_to_pack(items.SNAKE_DRAGON_CORPSE_ITEM)
    spoiled = []
    for _ in range(4):
        guild._rot_food(holder._base_inventory, spoiled)
    assert holder.count_of(items.SNAKE_DRAGON_CORPSE_ITEM) == 0
    assert spoiled == [items.SNAKE_DRAGON_CORPSE_ITEM]


def test_captives_survive_a_save():
    guild = Guild([Unit("player")])
    group = guild.groups[0]
    group.captives.append(captives.Captive(Unit("enemy"), 3, "snake_dragon"))
    back = persist.group_from_dict(persist.group_to_dict(group))
    (cap,) = back.captives
    assert cap.taken_day == 3 and cap.npc_slug == "snake_dragon"
    assert cap.unit.name == group.captives[0].unit.name


def test_releasing_a_captive_frees_its_place():
    group = Group([Unit("player")], node="city")
    cap = captives.Captive(Unit("enemy"), 0)
    group.captives.append(cap)
    captives.release(group, cap)
    assert group.herd_load == 0


def test_the_player_side_ai_binds_a_wanted_foe():
    _, batt, me, foe = _bound_fight()
    _down(foe, "stable")
    batt.wanted_alive.add(foe)
    assert ai._try_capture(batt, me)
    assert foe.captured


def test_the_ai_leaves_an_unwanted_body_alone():
    _, batt, me, foe = _bound_fight()
    _down(foe, "stable")
    assert not ai._try_capture(batt, me)

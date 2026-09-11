"""Save round-trips: units, loadout, the slot file."""

import os
import random

from tests.helpers import Combatant, data, persist, recruit, Unit, _unit


def test_unit_save_round_trip_keeps_rolled_values():
    from gartok import persist
    from gartok.unit import ATTRIBUTES
    random.seed(7)
    u = Unit("player")
    u._base_inventory = ["Rope", "Map"]
    v = Unit.from_save(persist.unit_to_dict(u))
    for f in ("name", "alignment", "age", "hp_max", "ac", "speed",
              "mental_defense", "languages", "_base_inventory", "gold"):
        assert getattr(v, f) == getattr(u, f), f
    assert v.race["name"] == u.race["name"]
    assert v.occupation["name"] == u.occupation["name"]
    assert [getattr(v, a) for a in ATTRIBUTES] == [getattr(u, a) for a in ATTRIBUTES]


def test_weapon_is_an_item_hand_and_pack():
    u = _unit()
    start = u.equipped_weapon
    assert start in data.WEAPONS and Combatant(u).weapon_hand
    u.give_to_pack(u.take_from_hand())               # stow it
    assert u.equipped_weapon is None and start in u._base_inventory
    c = Combatant(u)
    assert c.unarmed and not c.weapon_hand           # fights unarmed next battle
    u.give_to_hand("Axe")                        # draw a different weapon
    assert u.equipped_weapon == "Axe"
    c = Combatant(u)
    assert c.weapon_name == "Axe" and not c.unarmed


def test_offhand_torch_lights_unless_a_two_handed_weapon_blocks_it():
    u = _unit()
    u.equipped_weapon, u.equipped_offhand = "Dagger", data.TORCH_ITEM
    assert Combatant(u).torch_hand                    # one-handed weapon: off hand free
    u.equipped_weapon = "Light Crossbow"                  # two-handed: off hand occupied
    assert not Combatant(u).torch_hand
    assert u.equipped_offhand == data.TORCH_ITEM      # still assigned, just not lit


def test_equipping_two_handed_weapon_bumps_offhand_torch_to_pack():
    u = _unit()
    u.equipped_weapon, u.equipped_offhand = "Dagger", data.TORCH_ITEM
    u.give_to_hand("Light Crossbow")
    assert u.equipped_offhand is None and data.TORCH_ITEM in u._base_inventory


def test_offhand_lantern_only_lights_while_equipped():
    u = _unit()
    u.equipped_weapon, u.equipped_offhand = "Dagger", data.LANTERN_ITEM
    c = Combatant(u)
    assert c.lantern_hand and c.light_radius == data.LIGHT_SOURCES[data.LANTERN_ITEM]
    u.equipped_weapon = "Light Crossbow"                  # two-handed: off hand occupied
    assert not Combatant(u).lantern_hand and Combatant(u).light_radius == 0
    assert u.equipped_offhand == data.LANTERN_ITEM        # still assigned, just not lit

    u2 = _unit()
    u2._base_inventory = [data.LANTERN_ITEM]               # a lantern left in the pack
    assert Combatant(u2).light_radius == 0                # does not light on its own


def test_equipping_two_handed_weapon_bumps_offhand_lantern_to_pack():
    u = _unit()
    u.equipped_weapon, u.equipped_offhand = "Dagger", data.LANTERN_ITEM
    u.give_to_hand("Light Crossbow")
    assert u.equipped_offhand is None and data.LANTERN_ITEM in u._base_inventory


def test_equipped_weapon_survives_save():
    from gartok import persist
    random.seed(9)
    u = Unit("player")
    u.give_to_hand("Axe")
    u.give_to_offhand(data.TORCH_ITEM)
    u.give_to_pack("Dagger")
    v = Unit.from_save(persist.unit_to_dict(u))
    assert v.equipped_weapon == "Axe"
    assert v.equipped_offhand == data.TORCH_ITEM and Combatant(v).torch_hand
    assert "Dagger" in v._base_inventory


def test_save_slot_file_round_trip():
    from gartok import persist
    from gartok.guild import Guild
    from gartok.clock import Clock
    slot = persist.NUM_SLOTS - 1
    if os.path.exists(persist.slot_path(slot)):
        return                                        # never clobber a real save
    random.seed(8)
    guild = Guild([Unit("player") for _ in range(3)], battles_won=4,
                  reputation={"arena": 3}, deeds_done=["arena_first_blood"],
                  arena_challenge_day=12, clock=Clock(30 * 3600), node="wilds",
                  bank_capacity=10, bank_items=["Rope", "Sack"])
    guild.roster[0].gold = 42
    guild.roster[0].arena_title = True
    guild.roster[0].bio = "kept the belt through a lean winter"
    pool = recruit.refresh_pool(guild)
    recruit.bar(guild, pool[0], guild.roster[0])
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.battles_won == 4 and back.arena_reputation == 3
        assert back.deeds_done == ["arena_first_blood"]
        assert back.arena_challenge_day == 12
        assert back.roster[0].arena_title and "belt" in back.roster[0].bio
        assert back.clock.seconds == 30 * 3600 and back.node == "wilds"
        assert back.bank_capacity == 10 and back.bank_items == ["Rope", "Sack"]
        assert [u.name for u in back.roster] == [u.name for u in guild.roster]
        assert [u.hp_max for u in back.roster] == [u.hp_max for u in guild.roster]
        assert back.roster[0].gold == 42
        assert back.taverna_week == guild.taverna_week
        assert [u.uid for u in back.taverna_pool] == [u.uid for u in pool]
        assert back.taverna_blocked == [[pool[0].uid, guild.roster[0].uid]]
    finally:
        persist.delete_slot(slot)


def test_load_game_falls_back_to_one_group_for_a_pre_groups_save():
    """A save from before the groups layer has flat "roster"/"node" keys and no
    "groups" key at all -- `load_game` must still rebuild a working Guild."""
    import json

    from gartok import persist
    slot = persist.NUM_SLOTS - 1
    if os.path.exists(persist.slot_path(slot)):
        return                                        # never clobber a real save
    random.seed(8)
    old_payload = {
        "save_version": 6,
        "battles_won": 2,
        "reputation": {},
        "deeds_done": [],
        "arena_challenge_day": None,
        "clock_seconds": 3600,
        "node": "wilds",
        "bank_capacity": 0,
        "bank_items": [],
        "saved_at": 0,
        "squad": ["Bob"],
        "roster": [persist.unit_to_dict(Unit("player"))],
        "taverna_week": None,
        "taverna_pool": None,
        "taverna_blocked": [],
    }
    os.makedirs(persist.SAVE_DIR, exist_ok=True)
    with open(persist.slot_path(slot), "w", encoding="utf-8") as fh:
        json.dump(old_payload, fh)
    try:
        guild = persist.load_game(slot)
        assert len(guild.groups) == 1
        assert guild.node == "wilds"
        assert len(guild.roster) == 1
    finally:
        persist.delete_slot(slot)


def test_leadership_survives_a_save_round_trip():
    from gartok import persist
    from gartok.guild import Guild
    slot = persist.NUM_SLOTS - 1
    if os.path.exists(persist.slot_path(slot)):
        return                                        # never clobber a real save
    random.seed(11)
    a, b, c = Unit("player"), Unit("player"), Unit("player")
    guild = Guild([a, b, c], node="city", leader=b)   # b leads the guild AND its one starting group
    guild.set_leader(c)                               # spend the one free swap: c leads the guild now
    away = guild.split_group(guild.groups[0], [a])    # b's group is untouched by the guild-level swap
    away.set_leader(a)
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.leader.uid == c.uid
        assert back.leader_swaps_used == 1
        back_a = next(u for u in back.roster if u.uid == a.uid)
        back_b = next(u for u in back.roster if u.uid == b.uid)
        assert back.group_of(back_a).leader.uid == a.uid       # the split-off group: its own leader
        assert back.group_of(back_b).leader.uid == b.uid       # the original group kept its own leader
    finally:
        persist.delete_slot(slot)


def test_uid_is_stable_across_a_save_round_trip():
    u = _unit(seed=3)
    assert Unit.from_save(persist.unit_to_dict(u)).uid == u.uid


def test_from_save_backfills_a_uid_for_pre_uid_saves():
    d = persist.unit_to_dict(_unit(seed=3))
    d.pop("uid")
    assert Unit.from_save(d).uid                            # got a fresh one, no crash


def test_recruited_by_survives_a_save_round_trip():
    u = _unit(seed=3)
    u.recruited_by = "deadbeef"
    assert Unit.from_save(persist.unit_to_dict(u)).recruited_by == "deadbeef"

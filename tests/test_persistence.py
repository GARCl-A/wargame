"""Save round-trips: units, loadout, the slot file."""

import os
import random

from gartok.holdings import Stash
from tests.helpers import Combatant, Unit, _unit, data, packed, persist, recruit


def test_unit_save_round_trip_keeps_rolled_values():
    from gartok import persist
    from gartok.unit import ATTRIBUTES
    random.seed(7)
    u = Unit("player")
    u._base_inventory = packed(["Rope", "Map"])
    v = Unit.from_save(persist.unit_to_dict(u))
    for f in ("name", "alignment", "age", "hp_max", "ac", "speed",
              "mental_defense", "languages", "_base_inventory", "money",
              "quiver_charges", "first_aid_charges"):
        assert getattr(v, f) == getattr(u, f), f
    assert v.race["name"] == u.race["name"]
    assert v.occupation["name"] == u.occupation["name"]
    assert [getattr(v, a) for a in ATTRIBUTES] == [getattr(u, a) for a in ATTRIBUTES]


def test_locked_items_round_trip_through_save():
    from gartok import persist
    u = Unit("player")
    u._base_inventory = packed(["Rope", "Rope", "Torch"])
    u.toggle_lock("Rope")
    v = Unit.from_save(persist.unit_to_dict(u))
    assert v.locked_items == {"Rope": 2}
    assert v.locked_of("Rope") == 2 and v.locked_of("Torch") == 0


def test_old_flat_inventory_save_loads_as_stacks():
    """A save from before quantity-stacks stored `"inventory"` as a flat
    `list[str]` (repetition = stack). `from_save` still has to load one."""
    from gartok import persist
    u = Unit("player")
    d = persist.unit_to_dict(u)
    d["inventory"] = ["Rope", "Rope", "Map"]           # old-shape fixture
    v = Unit.from_save(d)
    assert v.count_of("Rope") == 2 and v.count_of("Map") == 1
    assert v._base_inventory == [("Rope", 2), ("Map", 1)]
    assert persist.unit_to_dict(v)["inventory"] == [{"id": "rope", "name": "Rope", "qty": 2}, {"id": "map", "name": "Map", "qty": 1}]


def test_missing_locked_items_key_loads_as_unlocked():
    """Older saves never wrote `locked_items` -- `persist.py` tolerates the
    missing key rather than erroring."""
    from gartok import persist
    u = Unit("player")
    u._base_inventory = packed(["Rope"])
    d = persist.unit_to_dict(u)
    del d["locked_items"]
    v = Unit.from_save(d)
    assert v.locked_items == {} and v.locked_of("Rope") == 0


def test_weapon_is_an_item_hand_and_pack():
    u = _unit()
    start = u.equipped_weapon
    assert start in data.WEAPONS and Combatant(u).weapon_hand
    u.give_to_pack(u.take_from_hand())               # stow it
    assert u.equipped_weapon is None and u.has_item(start)
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
    assert u.equipped_offhand is None and u.has_item(data.TORCH_ITEM)


def test_offhand_lantern_only_lights_while_equipped():
    u = _unit()
    u.equipped_weapon, u.equipped_offhand = "Dagger", data.LANTERN_ITEM
    c = Combatant(u)
    assert c.lantern_hand and c.light_radius == data.LIGHT_SOURCES[data.LANTERN_ITEM]
    u.equipped_weapon = "Light Crossbow"                  # two-handed: off hand occupied
    assert not Combatant(u).lantern_hand and Combatant(u).light_radius == 0
    assert u.equipped_offhand == data.LANTERN_ITEM        # still assigned, just not lit

    u2 = _unit()
    u2._base_inventory = packed([data.LANTERN_ITEM])        # a lantern left in the pack
    assert Combatant(u2).light_radius == 0                # does not light on its own


def test_equipping_two_handed_weapon_bumps_offhand_lantern_to_pack():
    u = _unit()
    u.equipped_weapon, u.equipped_offhand = "Dagger", data.LANTERN_ITEM
    u.give_to_hand("Light Crossbow")
    assert u.equipped_offhand is None and u.has_item(data.LANTERN_ITEM)


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
    assert v.has_item("Dagger")


def test_save_slot_file_round_trip():
    from gartok import missions, persist
    from gartok.clock import Clock
    from gartok.guild import Guild
    slot = "testworld"
    if os.path.exists(persist.save_path(slot)):
        return                                        # never clobber a real save
    random.seed(8)
    guild = Guild([Unit("player") for _ in range(3)], battles_won=4,
                  reputation={"arena": 3}, deeds_done=["arena_first_blood"],
                  arena_challenge_day=12, clock=Clock(30 * 3600), node="wilds",
                  bank=Stash(10, ["Rope", "Sack"]))
    guild.roster[0].money = 42
    guild.roster[0].arena_title = True
    guild.roster[0].bio = "kept the belt through a lean winter"
    pool = recruit.refresh_pool(guild)
    recruit.bar(guild, pool[0], guild.roster[0])
    guild.market_stock["1sqm Hide"] = 2
    m = missions.accept(guild, guild.groups[0].leader, missions.TANNER_HIDES)
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert back.battles_won == 4 and back.arena_reputation == 3
        assert back.deeds_done == ["arena_first_blood"]
        assert back.arena_challenge_day == 12
        assert back.roster[0].arena_title and "belt" in back.roster[0].bio
        assert back.clock.seconds == 30 * 3600 and back.groups[0].node == "wilds"
        assert back.bank.capacity == 10 and back.bank.items == [("Rope", 1), ("Sack", 1)]
        assert [u.name for u in back.roster] == [u.name for u in guild.roster]
        assert [u.hp_max for u in back.roster] == [u.hp_max for u in guild.roster]
        assert back.roster[0].money == 42
        assert back.taverna_week == guild.taverna_week
        assert [u.uid for u in back.taverna_pool] == [u.uid for u in pool]
        assert back.taverna_blocked == [[pool[0].uid, guild.roster[0].uid]]
        assert back.market_stock["1sqm Hide"] == 2
        assert len(back.missions) == 1
        assert back.missions[0].template_id == m.template_id
        assert back.missions[0].unit_uid == m.unit_uid
        assert back.missions[0].deadline_day == m.deadline_day
    finally:
        persist.delete_world(slot)


def test_load_game_falls_back_to_one_group_for_a_pre_groups_save():
    """A save from before the groups layer has flat "roster"/"node" keys and no
    "groups" key at all -- `load_game` must still rebuild a working Guild."""
    import json

    from gartok import persist
    slot = "testworld"
    if os.path.exists(persist.save_path(slot)):
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
    os.makedirs(persist.world_dir(slot), exist_ok=True)
    with open(persist.save_path(slot), "w", encoding="utf-8") as fh:
        json.dump(old_payload, fh)
    try:
        guild = persist.load_game(slot)
        assert len(guild.groups) == 1
        assert guild.groups[0].node == "wilds"
        assert len(guild.roster) == 1
    finally:
        persist.delete_world(slot)


def test_leadership_survives_a_save_round_trip():
    from gartok import persist
    from gartok.guild import Guild
    slot = "testworld"
    if os.path.exists(persist.save_path(slot)):
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
        persist.delete_world(slot)


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


def test_crime_and_jailed_survive_a_save_round_trip():
    from gartok import justice
    from gartok.guild import Guild
    slot = "testworld"
    if os.path.exists(persist.save_path(slot)):
        return                                        # never clobber a real save
    random.seed(4)
    free, culprit = Unit("player"), Unit("player")
    free.crime, culprit.crime = 0, 5
    guild = Guild([free, culprit], node="city")
    justice.jail(guild, culprit)                      # off the roster, into guild.jailed
    free.crime = 1                                     # a clean-ish member still on the books
    try:
        persist.save_game(slot, guild)
        back = persist.load_game(slot)
        assert [u.uid for u in back.roster] == [free.uid]
        assert back.roster[0].crime == 1
        assert len(back.jailed) == 1
        back_u, back_day = back.jailed[0]
        assert back_u.uid == culprit.uid and back_u.crime == 0
        assert back_day == guild.jailed[0][1]
    finally:
        persist.delete_world(slot)


def test_mission_ambush_done_survives_a_dict_round_trip():
    from gartok import missions
    m = missions.Mission("bankers_trust_chest", "some-uid", 1, 8, ambush_done=True)
    back = missions.mission_from_dict(missions.mission_to_dict(m))
    assert back.ambush_done is True


def test_quiver_charges_survive_save_round_trip():
    u = _unit()
    u.give_to_pack(data.AMMO_ITEM)
    u.quiver_charges = 14
    d = persist.unit_to_dict(u)
    assert "quiver_charges" not in d                  # the charges ride on the item
    v = Unit.from_save(d)
    assert v.quiver_charges == 14


def test_from_save_reads_the_legacy_character_level_quiver_charges():
    u = _unit()
    u.give_to_pack(data.AMMO_ITEM)
    d = persist.unit_to_dict(u)
    d["quiver_charges"] = 7
    assert Unit.from_save(d).quiver_charges == 7


def test_from_save_gives_an_old_save_a_full_quiver():
    u = _unit()
    u.give_to_pack(data.AMMO_ITEM)
    assert Unit.from_save(persist.unit_to_dict(u)).quiver_charges == data.QUIVER_AMMO


# --------------------------------------------------------------------------- #
# worlds: current + autosaves + manual saves                                  #
# --------------------------------------------------------------------------- #

def _world_guild(name="Iron Fists"):
    from gartok.guild import Guild
    guild = Guild([Unit("player")], node="city", name=name)
    return guild


def test_a_world_keeps_current_plus_every_snapshot_kind():
    world = persist.new_world_id()
    guild = _world_guild()
    persist.save_game(world, guild)
    persist.save_game(world, guild, kind="auto", label="before the wolves")
    persist.save_game(world, guild, kind="manual", label="safe point")

    rows = persist.list_saves(world)
    assert {r["kind"] for r in rows} == {"current", "auto", "manual"}
    assert {r["label"] for r in rows if r["kind"] != "current"} == {"before the wolves", "safe point"}
    assert all(r["name"] == "Iron Fists" and r["saved_at"] for r in rows)
    assert [r["saved_at"] for r in rows] == sorted((r["saved_at"] for r in rows), reverse=True)


def test_only_the_newest_autosaves_are_kept_and_manual_ones_never_pruned():
    world = persist.new_world_id()
    guild = _world_guild()
    persist.save_game(world, guild, kind="manual", label="mine")
    for i in range(persist.AUTOSAVES_KEPT + 3):
        persist.save_game(world, guild, kind="auto", label=f"fight {i}")

    autos = [r for r in persist.list_saves(world) if r["kind"] == "auto"]
    assert len(autos) == persist.AUTOSAVES_KEPT
    assert {r["label"] for r in autos} == {f"fight {i}" for i in range(3, persist.AUTOSAVES_KEPT + 3)}
    assert any(r["kind"] == "manual" for r in persist.list_saves(world))


def test_a_snapshot_loads_the_guild_as_it_was():
    world = persist.new_world_id()
    guild = _world_guild()
    guild.battles_won = 2
    snap = persist.save_game(world, guild, kind="auto", label="x")
    guild.battles_won = 9
    persist.save_game(world, guild)

    assert persist.load_game(world).battles_won == 9
    assert persist.load_game(world, snap).battles_won == 2


def test_list_worlds_groups_saves_by_guild_newest_first():
    a, b = persist.new_world_id(), persist.new_world_id()
    persist.save_game(a, _world_guild("Alpha"))
    persist.save_game(b, _world_guild("Beta"))
    persist.save_game(b, _world_guild("Beta"), kind="auto", label="x")

    rows = persist.list_worlds()
    assert {r["name"] for r in rows} == {"Alpha", "Beta"}
    assert next(r for r in rows if r["name"] == "Beta")["saves"] == 2
    assert persist.list_worlds()[0]["saved_at"] >= persist.list_worlds()[-1]["saved_at"]


def test_delete_save_never_touches_current_and_delete_world_removes_everything():
    world = persist.new_world_id()
    snap = persist.save_game(world, _world_guild(), kind="manual", label="m")
    persist.save_game(world, _world_guild())
    persist.delete_save(world, persist.CURRENT)
    assert {r["id"] for r in persist.list_saves(world)} == {persist.CURRENT, snap}
    persist.delete_save(world, snap)
    assert [r["id"] for r in persist.list_saves(world)] == [persist.CURRENT]
    persist.delete_world(world)
    assert persist.list_saves(world) == [] and persist.list_worlds() == []

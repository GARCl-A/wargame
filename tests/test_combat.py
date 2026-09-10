"""Actions, hands/inventory/carry, falling and death, ammo, fleeing."""

import random

from tests.helpers import (
    abilities, actions, Battle, COLS, Combatant, data, fixed_d20, GroundObject,
    Unit, _combatant, _melee_battle, _recruit, _unit,
)


def test_attack_spends_point():
    batt, a, d = _melee_battle()
    a.ap = 2
    actions.ATTACK.execute(batt, a, d)
    assert a.ap == 1


def test_defend_adds_condition():
    batt, a, _ = _melee_battle()
    a.ap = 2
    actions.DEFEND.execute(batt, a)
    assert a.defending and a.ap == 1


def test_throw_disarms_and_drops_object():
    batt, a, d = _melee_battle()
    a.equip_weapon("Dagger")
    a.pos, d.pos = (5, 5), (8, 5)
    a.ap = 2
    n_obj = len(batt.ground)
    assert actions.THROW.can(batt, a, d)
    actions.THROW.execute(batt, a, d)
    assert a.unarmed and len(batt.ground) == n_obj + 1


def test_pickup_recovers_weapon_from_ground():
    batt, a, d = _melee_battle()
    a.disarm()
    batt.ground.append(GroundObject.weapon(a.pos, "Axe"))
    a.ap = 2
    assert actions.PICK_UP.available(batt, a)
    actions.PICK_UP.execute(batt, a)
    assert not a.unarmed and a.weapon_name == "Axe"


def test_demoralize_requires_shared_language():
    batt, a, d = _melee_battle()
    a.languages, d.languages = ["Elvish"], ["Orcish"]
    a._ability = abilities.get("none")
    a.ap = 2
    assert actions.DEMORALIZE.can(batt, a, d) is False
    d.languages = ["Elvish"]
    # can() still depends on mutual sight; force bright light with adjacency + torch
    a.torch_hand = True
    assert actions.DEMORALIZE.can(batt, a, d) is True


# --------------------------------------------------------------------------- #
# hands / inventory / carry                                                    #
# --------------------------------------------------------------------------- #

def test_crossbow_takes_two_hands():
    u = _combatant()
    u.equip_weapon("Light Crossbow")
    assert u.weapon["hands"] == 2 and u.free_hands == 0
    dropped = u.equip_torch()                         # only fits by dropping the crossbow
    assert dropped == [("weapon", "Light Crossbow")] and u.has_torch and u.unarmed


def test_one_handed_weapon_and_torch_coexist():
    u = _combatant()
    u.equip_weapon("Dagger")
    dropped = u.equip_torch()
    assert dropped == [] and not u.unarmed and u.has_torch and u.free_hands == 0


def test_stowed_weapon_weighs_the_same_as_wielded():
    from gartok.data import WEAPONS, item_weight
    assert item_weight("Axe") == WEAPONS["Axe"]["weight"]
    u = _unit()
    u.equipped_weapon = None
    u._base_inventory = ["Axe"]
    assert Combatant(u).load == round(WEAPONS["Axe"]["weight"], 1)


def test_load_sums_weapon_torch_and_items():
    from gartok.data import WEAPONS, TORCH_WEIGHT, item_weight
    u = _combatant()
    u.equip_weapon("Axe")
    u.torch_hand = True
    u.inventory = ["Rope", "Map"]
    expected = round(WEAPONS["Axe"]["weight"] + TORCH_WEIGHT
                     + item_weight("Rope") + item_weight("Map"), 1)
    assert u.load == expected


def test_pickup_torch_with_free_hand_does_not_drop_weapon():
    batt, a, d = _melee_battle()
    a.equip_weapon("Dagger")                           # one-handed weapon
    batt.ground.append(GroundObject.torch(a.pos))
    a.ap = 2
    n_obj = len(batt.ground)
    actions.PICK_UP.execute(batt, a)
    assert a.has_torch and not a.unarmed and len(batt.ground) == n_obj - 1


def test_shepherd_spawns_neutral_sheep_that_blocks():
    random.seed(0)
    shepherd = _unit()
    shepherd.set_occupation("Shepherd")
    assert shepherd.starting_creature == "Sheep" and shepherd._base_inventory == []
    batt = Battle([shepherd], [Unit("enemy")])
    assert len(batt.creatures) == 1 and batt.creatures[0] not in batt.units

    batt.board.walls = set()
    batt.creatures[0].pos = (8, 6)                    # pin the sheep for the test
    p = batt.units[0]
    p.pos, p.ap, p.walking = (7, 6), 2, False
    assert (8, 6) not in batt.reachable(p)            # the sheep's cell blocks
    assert (9, 6) in batt.reachable(p)                # but you can go around


def test_initiative_keys_off_wisdom_not_dexterity():
    c = _combatant()
    c.char._ability = abilities.get("none")            # drop any racial init bonus
    c.char.wisdom, c.char.dexterity = 18, 3
    c.char._derive_combat()
    assert c.mod_wisdom != c.mod_dexterity             # the two genuinely differ here
    assert c.initiative_bonus() == c.mod_wisdom


# --------------------------------------------------------------------------- #
# falling, stabilizing and death                                               #
# --------------------------------------------------------------------------- #

def test_downed_enters_dying_not_dead():
    batt, a, d = _melee_battle()
    d.take_damage(999, batt.log)
    assert d.dying and not d.dead and not d.alive and d.downed
    assert d.hp == 0 and d.death_clock == 0


def test_death_save_survives_on_third_turn():
    batt, a, d = _melee_battle()
    d.go_down(batt.log)
    with fixed_d20(data.DEATH_SAVE_MIN):              # exactly clears the save
        batt._resolve_dying_turn(d); assert d.dying and d.death_clock == 1
        batt._resolve_dying_turn(d); assert d.dying and d.death_clock == 2
        batt._resolve_dying_turn(d); assert d.stable and d.survived


def test_death_save_can_kill():
    batt, a, d = _melee_battle()
    d.go_down(batt.log)
    with fixed_d20(data.DEATH_SAVE_MIN - 1):          # one short -> dies
        for _ in range(3):
            batt._resolve_dying_turn(d)
    assert d.dead and not d.survived


def test_ally_stabilize_success_and_failure():
    batt, a, d = _melee_battle()
    b = _recruit(batt)
    b.pos = (5, 6)
    a.go_down(batt.log); a.pos = (5, 5)
    b.ap = 2
    with fixed_d20(1):                                # botched -> still dying
        actions.STABILIZE.execute(batt, b, a)
    assert a.dying and b.ap == 1
    b.ap = 2
    with fixed_d20(20):                               # clean -> stable
        actions.STABILIZE.execute(batt, b, a)
    assert a.stable and b.ap == 1


def test_first_aid_consumes_charge_either_way():
    batt, a, d = _melee_battle()
    medic = _recruit(batt)
    medic.pos = (5, 6)
    medic.first_aid_charges = 10
    a.go_down(batt.log); a.pos = (5, 5)

    medic.ap = 2
    with fixed_d20(1):                                # a failed check still burns a charge
        actions.FIRST_AID.execute(batt, medic, a)
    assert a.dying and medic.first_aid_charges == 9 and medic.ap == 1

    medic.ap = 2
    with fixed_d20(20):                               # a success burns one too
        actions.FIRST_AID.execute(batt, medic, a)
    assert a.stable and medic.first_aid_charges == 8


def test_medic_carries_first_aid_kit():
    u = _unit()
    u.set_occupation("Physician")
    c = Combatant(u)
    assert data.FIRST_AID_ITEM in c.inventory
    assert c.first_aid_charges == data.FIRST_AID_CHARGES


def test_finish_off_dying_enemy_kills():
    batt, a, d = _melee_battle()
    d.go_down(batt.log)
    a.ap = 2
    random.seed(2)                                    # any non-fumble hit finishes it
    for _ in range(20):
        if not d.dying:
            break
        a.ap = 2
        actions.ATTACK.execute(batt, a, d)
    assert d.dead


def test_hitting_stable_reverts_to_dying():
    batt, a, d = _melee_battle()
    d.status, d.hp = "stable", 0
    a.ap = 2
    for _ in range(20):
        a.ap = 2
        actions.ATTACK.execute(batt, a, d)
        if d.status != "stable":
            break
    assert d.dying and d.death_clock == 0


def test_victory_when_a_side_is_all_downed():
    batt, a, d = _melee_battle()
    d.status = "dying"
    batt._check_winner()
    assert batt.winner == "player"
    assert d.status in ("stable", "dead")             # dangling save resolved


def test_win_waits_for_dying_allies_to_resolve():
    """Enemy is down but an ally is still bleeding out and a teammate stands:
    the battle is not called until the dying ally is stable or dead."""
    batt, a, d = _melee_battle()
    mate = _recruit(batt)
    mate.pos = (5, 6)
    a.go_down(batt.log)                               # a is dying, mate stands
    d.status = "dead"                                 # enemy side wiped
    assert batt._check_winner() is None               # mop-up, not over yet
    assert batt._mopup_open
    with fixed_d20(data.DEATH_SAVE_MIN):              # the dying ally pulls through
        for _ in range(data.DYING_TURNS):
            batt._resolve_dying_turn(a)
    assert a.stable
    assert batt._check_winner() == "player"


def test_lost_lethal_battle_takes_the_whole_squad():
    batt, a, d = _melee_battle()
    a.status = "stable"                               # would have "survived"
    # enemy still stands, no player is up -> total defeat
    batt._check_winner()
    assert batt.winner == "enemy"
    assert a.status == "dead" and not a.survived


def test_lethal_flag_defaults_true_and_permadeath_still_bites():
    batt, a, d = _melee_battle()
    assert batt.lethal and not a.nonlethal
    d.take_damage(999, batt.log)
    assert d.dying                                    # not knocked out -- dying


# --------------------------------------------------------------------------- #
# ammo and improvised weapon                                                   #
# --------------------------------------------------------------------------- #

def test_crossbowman_starts_with_ammo():
    u = _unit()
    u.set_occupation("Crossbowman")
    assert Combatant(u).ammo == data.QUIVER_AMMO and u.weapon_name == "Light Crossbow"


def test_crossbow_starts_unloaded_and_must_reload_first():
    u = _unit()
    u.set_occupation("Crossbowman")
    c = Combatant(u)
    assert not c.crossbow_loaded and not c.ranged and c.improvised   # can't shoot yet
    assert c.can_reload and c.attack_range == 1                       # swings it until reloaded


def test_crossbow_reload_cycle():
    batt, a, d = _melee_battle()
    batt.board.walls = set()                          # clear lane between shooter and target
    a.equip_weapon("Light Crossbow"); a.ammo = 3; a.crossbow_loaded = True
    a.pos, d.pos = (2, 5), (9, 5)
    a.torch_hand = False
    for u in batt.units:                              # light the lane so LOS+sight hold
        u._ability = abilities.get("none")
    batt.ground = [GroundObject.torch((6, 5))]
    a.ap = 2

    # loaded -> the shot fires and empties the crossbow, quiver untouched
    assert a.ranged and actions.ATTACK.can(batt, a, d)
    actions.ATTACK.execute(batt, a, d)
    assert a.ammo == 3 and not a.crossbow_loaded and a.improvised

    # empty -> can't shoot; Reload chambers one bolt from the quiver (1 AP)
    assert not actions.ATTACK.can(batt, a, d) and actions.RELOAD.can(batt, a)
    actions.RELOAD.execute(batt, a)
    assert a.ammo == 2 and a.crossbow_loaded and a.ap == 0

    # quiver dry -> no reload, stuck swinging it as an improvised club
    a.ammo, a.crossbow_loaded = 0, False
    assert not actions.RELOAD.can(batt, a) and a.improvised and a.attack_range == 1


def test_tongue_lash_strikes_at_reach_two_with_the_tongue_weapon():
    batt, a, d = _melee_battle()
    batt.board.walls = set()
    a.char.talents["racial"] = ["tongue"]
    a.char.equipped_tongue = "Axe"
    a.reset_battle_state()                            # re-seed the tongue weapon
    a.pos, d.pos = (5, 5), (7, 5)                     # two squares apart
    a.ap = 2
    d.hp = d.hp_max = 60
    d.dr = 0
    assert not actions.ATTACK.can(batt, a, d)         # the hand weapon can't reach
    assert actions.ATTACK_TONGUE.can(batt, a, d)
    with fixed_d20(19):
        actions.ATTACK_TONGUE.execute(batt, a, d)
    assert a.ap == 1 and d.hp < 60                    # spent a point, landed the blow


def test_ai_lashes_with_the_tongue_when_the_hand_weapon_falls_short():
    from gartok import ai
    batt, a, d = _melee_battle()
    batt.board.walls = set()
    d.char.talents["racial"] = ["tongue"]
    d.char.equipped_tongue = "Axe"
    d.reset_battle_state()
    a.pos, d.pos = (5, 5), (7, 5)                     # player two squares from the enemy
    a.hp = a.hp_max = 40
    a.dr = 0
    d.ap = 2
    hp = a.hp
    ai.take_turn(batt, d)
    assert a.hp < hp                                  # the enemy reached out and hit
    """`Unit.attack_bonus` -- the base to-hit the guild screen shows on the
    weapon row (and `sheet_panel._to_hit` reuses)."""
    u = _unit()
    u.strength, u.dexterity = 16, 8               # +3 STR, -1 DEX
    u._derive_combat()
    u.take_from_hand()                            # start from empty hands
    assert u.attack_bonus == (3, "STR")           # unarmed hits with Strength
    u.give_to_hand("Axe")                         # plain melee -> STR
    assert u.attack_bonus == (3, "STR")
    u.give_to_hand("Dagger")                      # finesse -> better of STR/DEX
    assert u.attack_bonus == (3, "STR/DEX")
    u.give_to_hand("Light Crossbow")              # ranged -> DEX
    assert u.attack_bonus == (-1, "DEX")


def test_attack_bonus_folds_in_the_to_hit_talent():
    u = _unit(seed=1)
    u.combat_xp = 10
    u.choose_talent("combat", "strong")
    u.choose_talent("combat", "sure_strike")      # +1 to hit on STR attacks
    u.give_to_hand("Axe")
    assert u.attack_bonus[0] == u.mod_strength + 1
    u._base_inventory.append("Quiver")
    u.give_to_hand("Light Crossbow")              # DEX attack -> Sure Strike doesn't apply
    assert u.attack_bonus[0] == u.mod_dexterity


def test_crossbow_without_ammo_is_improvised():
    u = _combatant()
    u.equip_weapon("Light Crossbow"); u.ammo = 0
    assert u.improvised and not u.ranged and u.attack_range == 1
    # to-hit uses Strength (melee), not Dexterity
    labels = {lbl for _, _, lbl in u.attack_mods(None)}
    assert "STR" in labels and "DEX" not in labels
    # damage die is the size unarmed die, never 1d8
    faces = data.UNARMED_ATTACK[u.size][1]
    assert max(u.damage_roll() for _ in range(200)) <= faces + u.mod_strength + u._ability.melee_damage


# --------------------------------------------------------------------------- #
# flee the battle                                                              #
# --------------------------------------------------------------------------- #

def test_flee_needs_the_map_edge():
    batt, a, d = _melee_battle()
    a.pos, d.pos = (5, 5), (12, 9)                    # a mid-board, foe far
    assert not actions.FLEE.available(batt, a)
    a.pos = (0, 5)                                    # left edge, foe still 12 away
    assert actions.FLEE.available(batt, a)


def test_flee_succeeds_when_faster_or_far_and_ends_the_fight_left_behind():
    batt, a, d = _melee_battle()
    mate = _recruit(batt)
    a.pos, mate.pos, d.pos = (0, 5), (5, 5), (2, 5)   # foe adjacent-ish to a
    a.speed, d.speed = 9, 4                           # a outruns the pursuer
    a.ap = 2
    mate.go_down(batt.log)                            # a downed ally left on the field
    actions.FLEE.execute(batt, a, None)
    assert a.fled and a.survived and not a.alive and a.ap == 0
    # still an enemy up and no player standing -> enemy "wins", the downed mate is lost
    assert batt.winner == "enemy" and mate.dead


def test_flee_blocked_when_pursuers_keep_pace():
    batt, a, d = _melee_battle()
    a.pos, d.pos = (0, 5), (2, 5)                     # edge, but the foe is 2 away
    a.speed, d.speed = 5, 8                           # slower than the pursuer
    assert not actions.FLEE.available(batt, a)        # not faster, not far enough
    actions.FLEE.execute(batt, a, None)
    assert not a.fled and a.status == "up"


def test_all_enemies_fleeing_hands_the_player_the_win():
    batt, a, d = _melee_battle()
    d.pos, d.speed = (COLS - 1, 5), 9
    a.speed = 4
    actions.FLEE.execute(batt, d, None)
    assert d.fled and batt.winner == "player"


def test_flee_drags_an_adjacent_downed_ally_and_leaves_the_far_one():
    batt, a, d = _melee_battle()
    near, far = _recruit(batt), _recruit(batt)
    a.pos, near.pos, far.pos, d.pos = (0, 5), (0, 6), (8, 8), (11, 9)
    a.speed = 9
    near.go_down(batt.log); far.go_down(batt.log)
    a.ap = 2
    actions.FLEE.execute(batt, a, None)
    assert a.fled and near.fled and near.survived
    assert batt.winner == "enemy" and far.dead      # too far to drag -> lost with the defeat

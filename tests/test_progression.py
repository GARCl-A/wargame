"""XP tracks, the talent trees, mean-level hit dice."""

import random

from tests.helpers import (
    abilities, actions, Battle, Combatant, data, economy, persist, recruit, talents,
    Unit, _combatant, _FixedRNG, _melee_battle, _unit,
)


# --------------------------------------------------------------------------- #
# combat XP                                                                    #
# --------------------------------------------------------------------------- #

def test_downing_a_standing_enemy_credits_the_killer():
    batt, a, d = _melee_battle()
    a.equip_weapon("Axe")
    d.dr = 0
    random.seed(2)
    for _ in range(30):
        if not d.alive:
            break
        d.hp = 1
        a.ap = 2
        actions.ATTACK.execute(batt, a, d)
    assert not d.alive and a.kills == 1


def test_finishing_a_downed_enemy_does_not_double_count():
    batt, a, d = _melee_battle()
    a.equip_weapon("Axe")
    d.go_down(batt.log)                                 # already dying: someone else's kill
    random.seed(2)
    for _ in range(30):
        if d.dead:
            break
        a.ap = 2
        actions.ATTACK.execute(batt, a, d)
    assert d.dead and a.kills == 0


def test_ferocity_credits_the_hit_that_brought_the_orc_to_zero():
    batt, a, d = _melee_battle()
    d.char._ability = abilities.get("ferocity")
    d.char.ability_id = "ferocity"
    d.dr = 0
    a.equip_weapon("Axe")
    random.seed(2)
    for _ in range(30):
        if d.ferocity_pending or not d.alive:
            break
        d.hp = 3
        a.ap = 2
        actions.ATTACK.execute(batt, a, d)
    assert d.ferocity_pending and a.kills == 0        # still on its feet: no credit yet
    d.end_turn(batt.log)
    assert not d.alive and a.kills == 1               # falls at end of turn -> attacker credited


def test_absorb_battle_folds_kills_into_combat_xp():
    from gartok import campaign
    from gartok.guild import Guild
    random.seed(2)
    squad = [Unit("player") for _ in range(2)]
    guild = Guild(list(squad))
    battle = Battle(squad, [Unit("enemy")])
    battle.winner = "player"
    battle.player_units[0].status = battle.player_units[1].status = "up"
    battle.player_units[0].combat_xp_earned = 2
    out = campaign.absorb_battle(guild, squad, battle)
    assert squad[0].combat_xp == 2 and squad[1].combat_xp == 0
    assert out.xp_awards == {squad[0].name: 2}


def test_combat_xp_survives_a_save_round_trip():
    u = _unit(seed=1)
    u.combat_xp = 5
    assert Unit.from_save(persist.unit_to_dict(u)).combat_xp == 5


# --------------------------------------------------------------------------- #
# leveling: progression curves, talents, mean-level hit dice                    #
# --------------------------------------------------------------------------- #

def test_combat_level_thresholds():
    from gartok import progression
    assert progression.combat_level(2) == 0
    assert progression.combat_level(3) == 1
    assert progression.combat_level(9) == 1
    assert progression.combat_level(10) == 2


def test_xp_award_scales_by_level_gap():
    from gartok import progression
    assert progression.xp_award(0, 0) == 1
    assert progression.xp_award(0, 10) == 11
    assert progression.xp_award(1, 1) == 1
    assert progression.xp_award(3, 0) == 0        # veteran mopping up: nothing


def test_credit_kill_uses_the_attacker_and_victim_levels():
    atk = _combatant(seed=1, combat_xp=10)        # combat level 2
    vic = _combatant(seed=2, combat_xp=0)         # combat level 0
    atk.credit_kill(vic)
    assert atk.kills == 1 and atk.combat_xp_earned == 0
    vic2 = _combatant(seed=3, combat_xp=10)
    atk.credit_kill(vic2)
    assert atk.combat_xp_earned == 1              # equal level -> +1


def test_choosing_a_combat_root_raises_the_real_attribute():
    u = _unit(seed=1)
    u.combat_xp = 3
    before = u.strength
    assert u.pending_picks == ["combat"]
    assert u.choose_talent("combat", "strong")
    assert u.strength == before + 1               # the score itself, shown on the sheet
    assert u.pending_picks == []
    assert not u.choose_talent("combat", "agile")  # pick already spent
    assert not u.choose_talent("combat", "strong")  # not twice


def test_negotiator_lifts_only_the_haggle_charisma():
    u = _unit(seed=4)
    u.work_hours = economy.LUMBER_XP_HOURS * 2    # work level 1
    cha_mod = u.mod_charisma
    assert u.choose_talent("work", "negotiator")
    assert u.mod_charisma == cha_mod              # the real Charisma is untouched
    assert u.haggle_charisma_mod == data.mod(
        u.charisma + u.hunger_attribute_penalty + 1)


def test_carrier_widens_the_stagger_threshold_by_up_to_a_kg_of_gear():
    u = _unit(seed=5)
    u.work_hours = economy.LUMBER_XP_HOURS * 2
    u._base_inventory = ["Rope", "1kg Meat"]      # 2 kg cargo + a consumable
    u._derive_combat()
    load, base_normal = u.load, u.carry_normal
    assert u.choose_talent("work", "carrier")
    assert u.load == load                         # displayed weight unchanged
    assert u.carry_relief == 1.0                  # a full kg: the Rope covers it
    assert u.carry_normal == round(base_normal + 1.0, 1)

    u._base_inventory = ["Chisel"]               # 0.3 kg of cargo -> only 0.3 relief
    u._derive_combat()
    assert u.carry_relief == round(data.item_weight("Chisel"), 1)

    u._base_inventory = ["1kg Meat", "Axe"]      # only food + a weapon -> no relief
    u._derive_combat()
    assert u.carry_relief == 0.0 and u.carry_normal == base_normal


def test_talent_effects_resolve_by_channel_and_stat():
    from gartok import talents
    # channel gate: melee_damage is not to_hit
    assert talents.bonus(["heavy_hand"], "melee_damage") == 1
    assert talents.bonus(["heavy_hand"], "to_hit", "strength") == 0
    # stat gate on to_hit: Sure Strike is STR-only, Deadeye DEX-only, no crossover
    assert talents.bonus(["sure_strike"], "to_hit", "strength") == 1
    assert talents.bonus(["sure_strike"], "to_hit", "dexterity") == 0
    assert talents.bonus(["deadeye"], "to_hit", "dexterity") == 1
    # unknown ids are skipped, not fatal
    assert talents.bonus(["nope", "strong"], "attr", "strength") == 1

    u = _unit(seed=7)
    u.talents = {"combat": ["agile", "deadeye"], "work": []}
    u._apply_attributes()
    u._derive_combat()
    u.equipped_weapon = None                         # unarmed -> a STR attack
    assert u.attack_bonus == (u.mod_strength, "STR")  # Deadeye (DEX-only) adds nothing
    u.equipped_weapon = "Light Crossbow"             # ranged -> a DEX attack
    assert u.attack_bonus == (u.mod_dexterity + 1, "DEX")


def test_carrier_never_lifts_the_carry_max_ceiling():
    u = _unit(seed=5)
    u.work_hours = economy.LUMBER_XP_HOURS * 2
    u._base_inventory = ["Rope"]
    u._derive_combat()
    ceiling = u.carry_max
    assert u.choose_talent("work", "carrier")
    assert u.carry_max == ceiling


def test_mean_level_grants_a_hit_die():
    u = _unit(seed=1)
    hp0 = u.hp_max
    u.combat_xp = 3                               # combat 1 / work 0 -> mean 0
    assert not u.collect_levels()
    assert u.hp_max == hp0
    u.combat_xp = 10                              # combat 2 / work 0 -> mean 1
    assert u.collect_levels()
    assert len(u._level_hp_rolls) == 1
    assert u.hp_max > hp0
    assert not u.collect_levels()                 # idempotent


def test_talents_and_hit_dice_survive_a_save_without_rerolling():
    u = _unit(seed=1)
    u.combat_xp = 10
    u.collect_levels()
    u.choose_talent("combat", "tough")
    d = persist.unit_to_dict(u)
    back = Unit.from_save(d)
    assert back.talents == u.talents
    assert back._level_hp_rolls == u._level_hp_rolls
    assert back.hp_max == u.hp_max
    assert back.constitution == u.constitution


# --------------------------------------------------------------------------- #
# talents: tier 2 (specialise the tier-1 identity)                             #
# --------------------------------------------------------------------------- #

def test_tier2_talent_needs_its_root_first():
    u = _unit(seed=1)
    u.combat_xp = 10                              # combat level 2 -> 2 picks
    assert not u.choose_talent("combat", "sure_strike")   # no Strong yet
    assert u.choose_talent("combat", "strong")
    assert u.choose_talent("combat", "sure_strike")
    assert u.talents["combat"] == ["strong", "sure_strike"]


def test_sure_strike_and_deadeye_key_off_the_attack_attribute():
    tgt = _combatant(seed=7)

    def to_hit(weapon, *picks, ammo=False):
        u = _unit(seed=1)
        u.combat_xp = 10
        for p in picks:
            assert u.choose_talent("combat", p)
        if ammo:
            u._base_inventory.append("Quiver")
        u.give_to_hand(weapon)
        c = Combatant(u)
        c.crossbow_loaded = True                  # measure the bolt, not the improvised swing
        return sum(v for v, *_ in c.attack_mods(tgt))

    # Sure Strike (under Strong): +1 on a Strength swing, nothing on a bolt
    assert to_hit("Axe", "strong", "sure_strike") == to_hit("Axe", "strong") + 1
    assert to_hit("Light Crossbow", "strong", "sure_strike", ammo=True) \
        == to_hit("Light Crossbow", "strong", ammo=True)
    # Deadeye (under Agile): the mirror image
    assert to_hit("Light Crossbow", "agile", "deadeye", ammo=True) \
        == to_hit("Light Crossbow", "agile", ammo=True) + 1
    assert to_hit("Axe", "agile", "deadeye") == to_hit("Axe", "agile")


def test_heavy_hand_adds_one_melee_damage():
    def dmg(*picks):
        u = _unit(seed=1)
        u.combat_xp = 10
        for p in picks:
            assert u.choose_talent("combat", p)
        u.give_to_hand("Axe")
        c = Combatant(u)
        random.seed(99)
        return c.damage_roll()

    assert dmg("strong", "heavy_hand") == dmg("strong") + 1


def test_long_reach_extends_ranged_and_thrown_not_melee():
    u = _unit(seed=1)
    u.combat_xp = 10
    assert u.choose_talent("combat", "agile")
    assert u.choose_talent("combat", "long_reach")
    u._base_inventory.append("Quiver")

    u.give_to_hand("Light Crossbow")
    loaded = Combatant(u)
    loaded.crossbow_loaded = True
    assert loaded.attack_range == data.WEAPONS["Light Crossbow"]["range"] + 1
    u.give_to_hand("Dagger")
    assert Combatant(u).throw_range == data.WEAPONS["Dagger"]["thrown"] + 1
    u.give_to_hand("Axe")
    assert Combatant(u).attack_range == 1         # melee reach is untouched


def test_hardy_adds_hp_per_hit_die_and_bulwark_adds_ac():
    u = _unit(seed=1)
    u.combat_xp = 21                              # combat level 3 -> 3 picks
    u.collect_levels()                            # mean level 1 -> one extra hit die
    hit_dice = 1 + len(u._level_hp_rolls)
    assert u.choose_talent("combat", "tough")
    hp_after_tough, ac_after_tough = u.hp_max, u.ac
    assert u.choose_talent("combat", "hardy")
    assert u.hp_max == hp_after_tough + hit_dice
    assert u.choose_talent("combat", "bulwark")
    assert u.ac == ac_after_tough + 1


def test_tier2_talent_effect_survives_a_save():
    u = _unit(seed=1)
    u.combat_xp = 10
    u.choose_talent("combat", "tough")
    u.choose_talent("combat", "bulwark")
    ac = u.ac
    back = Unit.from_save(persist.unit_to_dict(u))
    assert back.talents["combat"] == ["tough", "bulwark"]
    assert back.ac == ac


def test_tree_layout_places_every_node_below_its_parent():
    """`level_screen._tree_layout` positions the talent graph: every node placed,
    roots on top, each child one tier below its `requires` and its parent
    centred over its children. Tier-agnostic -- a deeper tree lays out the same."""
    from gartok.level_screen import _tree_layout
    for track in talents.TRACKS:
        nodes = talents.TREE[track]
        pos, span, depths = _tree_layout(track)
        assert set(pos) == {t.id for t in nodes}
        assert depths >= 2
        for t in nodes:
            col, depth = pos[t.id]
            assert 0 <= col <= span
            assert depth == (0 if t.requires is None
                             else pos[t.requires][1] + 1)
            kids = [c for c in nodes if c.requires == t.id]
            if kids:
                assert col == sum(pos[k.id][0] for k in kids) / len(kids)


def _work_ready(*picks):
    """A fresh Unit at work level 2 with the given work talents spent."""
    u = Unit("player")
    u.gold = 0
    u._base_inventory = []
    u.work_hours = economy.LUMBER_XP_HOURS * 6    # work_xp 6 -> work level 2 -> 2 picks
    u._derive_combat()
    for p in picks:
        assert u.choose_talent("work", p)
    return u


def test_piecework_lifts_pay_and_brisk_hands_is_individual():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(3)
    plain = _work_ready()
    rich = _work_ready("carrier", "piecework")
    quick = _work_ready("carrier", "brisk_hands")

    # mixed crew: pay is per-worker; the guild leaves when the SLOWEST is done
    guild = Guild([plain, rich, quick], clock=Clock(6 * 3600))
    base = economy.lumber_pay(16)                 # 12 copper
    guild.work_shift([plain, rich, quick], 16)
    assert plain.gold == base
    assert rich.gold == round(base * 1.20)        # Piecework: +20%
    assert quick.gold == base                     # speed does not touch the pay
    assert all(u.work_hours == economy.LUMBER_XP_HOURS * 6 + 16
               for u in (plain, rich, quick))     # full hours banked for XP
    assert guild.clock.seconds == 6 * 3600 + 16 * 3600    # plain drags: full 16 h

    # a Brisk worker on their own: 16 h of work banked in 14.4 h of the clock
    solo = Guild([_work_ready("carrier", "brisk_hands")], clock=Clock(6 * 3600))
    solo.work_shift(solo.roster, 16)
    assert solo.roster[0].work_hours == economy.LUMBER_XP_HOURS * 6 + 16
    assert solo.clock.seconds == 6 * 3600 + round(16 * 0.9 * 3600)


def test_provisioner_discounts_food_with_no_shared_language():
    u = _work_ready("negotiator", "provisioner")
    u.languages = ["Orcish"]                      # not the market's Ankarin
    mods = economy.deal_mods([u], "Ankarin", "Lawful and Neutral")
    assert economy.deal_value(mods, "Axe", "buy") == 0.0          # no general haggle
    assert economy.deal_value(mods, "1kg Meat", "buy") == economy.CHA_DEAL_STEP
    assert economy.deal_value(mods, "1kg Meat", "sell") == 0.0    # buy side only


def test_provisioner_stacks_on_the_base_haggle_for_food_only():
    u = _work_ready("negotiator", "provisioner")
    u.languages = ["Ankarin"]
    u.charisma = 12
    u.alignment = "Lawful and Neutral"           # same as the vendor -> +0.10
    u._derive_combat()
    mods = economy.deal_mods([u], "Ankarin", "Lawful and Neutral")
    general = economy.deal_value(mods, "Axe", "buy")
    assert 0 < general < economy.DEAL_MAX
    assert economy.deal_value(mods, "1kg Meat", "buy") == round(
        general + economy.CHA_DEAL_STEP, 3)
    assert economy.deal_value(mods, "1kg Meat", "sell") == general   # not on sells


def test_fixer_lifts_the_recruiters_pitch():
    r = _work_ready("negotiator", "fixer")
    r.languages = ["Ankarin"]
    r.alignment = "Neutral and Neutral"
    r.mod_charisma = 0                            # pin after the talent re-derive
    c = _unit(seed=2, languages=["Ankarin"], alignment="Neutral and Neutral")
    c.mod_charisma = 0

    p = recruit.convince(r, c, 2, rng=_FixedRNG(10, 10))   # 10 +1 Fixer = 11 vs 10
    assert p.ok and (1, "Fixer") in p.modifiers
    # same rolls, no talent: 10 vs 10 -> tie -> the stranger stays put
    bare = _unit(seed=1, languages=["Ankarin"], alignment="Neutral and Neutral")
    bare.mod_charisma = 0
    assert not recruit.convince(bare, c, 2, rng=_FixedRNG(10, 10)).ok

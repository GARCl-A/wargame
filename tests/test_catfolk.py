"""The Catfolk: its d100 slots, Catfall, Razor Claws (Bleeding), Night Prowler and Open Market."""

from types import SimpleNamespace

from gartok import data, economy, items, vocations
from gartok.actions.base import _resolve_hit
from gartok.battle import Battle
from gartok.conditions import Bleeding
from gartok.group import CAUTIOUS, NORMAL
from tests.helpers import fixed_d20, standard_unit


def _catfolk(*picks, team="player"):
    u = standard_unit(team)
    u.set_race("Catfolk")
    u.set_track_level("racial", 15)
    for p in picks:
        assert u.choose_talent("racial", p), p
    return u


def _duel(picks=(), foe_race="Human", armed=False):
    cat = _catfolk(*picks)
    if not armed:
        cat.equipped_weapon = None
    foe = standard_unit("enemy")
    foe.set_race(foe_race)
    foe._hp_roll = foe.race["hd"]
    foe._derive_combat()
    foe.hp = foe.hp_max
    batt = Battle([cat], [foe])
    batt.board.walls = set()
    batt.ambient_light = True
    a, d = batt.units
    a.pos, d.pos = (5, 5), (6, 5)
    return batt, a, d


# --- the race ------------------------------------------------------------------ #

def test_the_d100_table_gives_the_catfolk_three_slots_and_still_sums_to_100():
    slots, prev = {}, 0
    for row in data.RACES:
        slots[row[1]], prev = row[0] - prev, row[0]
    assert prev == 100
    assert slots["Catfolk"] == slots["Kenku"] == 3
    assert (slots["Dwarf"], slots["Elf"], slots["Goblin"]) == (14, 14, 14)


def test_the_catfolk_holds_three_racial_talents_and_speaks_sylvan():
    race = data.race_by_name("Catfolk")
    assert race["language"] == "Sylvan" and race["ability"] == "catfall"
    u = _catfolk("razor_claws", "night_prowler", "open_market")
    assert u.talents["racial"] == ["razor_claws", "night_prowler", "open_market"]


def test_the_catfolk_sits_in_the_caravan_and_not_the_kenku():
    caravan = vocations.VOCATIONS[vocations.CARAVAN].races
    assert "Catfolk" in caravan and "Kenku" not in caravan


# --- Catfall ------------------------------------------------------------------- #

def test_catfall_makes_a_drop_of_four_levels_free_and_trims_the_rest():
    batt, cat, human = _duel()
    batt.apply_fall(cat, 4, batt.log)
    assert cat.hp == cat.hp_max
    with fixed_d20(10):
        batt.apply_fall(cat, 5, batt.log)           # one die instead of four
    assert 1 <= cat.hp_max - cat.hp <= 6
    batt.apply_fall(human, 4, batt.log)             # 3d6 for everyone else
    assert 3 <= human.hp_max - human.hp <= 18


def test_the_ai_reckons_the_fall_a_catfolk_shrugs_off_as_free():
    from gartok.ai import reckon
    batt, cat, human = _duel()
    batt.elevation = lambda unit: 0
    batt.elevation_at = lambda dest, unit: -4
    assert reckon._fall_worth(batt, cat, (7, 5)) == 0.0
    assert reckon._fall_worth(batt, human, (7, 5)) > 0.0


# --- Bleeding ------------------------------------------------------------------ #

def _tick(unit):
    unit.end_turn(lambda *_a, **_k: None)


def test_bleeding_stacks_damage_and_renews_duration_to_the_longer():
    _, _, d = _duel()
    d.add_condition(Bleeding(1, 2))
    hp = d.hp
    _tick(d)
    assert hp - d.hp == 1 and d.condition("bleeding").duration == 1
    d.add_condition(Bleeding(1, 2))                  # (1,1) + (1,2) -> (2,2)
    assert (d.condition("bleeding").damage, d.condition("bleeding").duration) == (2, 2)
    _tick(d)
    assert hp - d.hp == 3
    d.add_condition(Bleeding(1, 2))                  # (2,1) + (1,2) -> (3,2)
    _tick(d)
    assert hp - d.hp == 6
    d.add_condition(Bleeding(3, 5))                  # (3,1) + (3,5) -> (6,5)
    bleed = d.condition("bleeding")
    assert (bleed.damage, bleed.duration) == (6, 5)


def test_bleeding_ends_when_the_duration_runs_out():
    _, _, d = _duel()
    d.add_condition(Bleeding(1, 2))
    _tick(d)
    _tick(d)
    assert not d.has_condition("bleeding")
    hp = d.hp
    _tick(d)
    assert d.hp == hp


def test_bleeding_ignores_damage_reduction_and_can_drop_a_unit():
    _, _, d = _duel()
    d.dr = 5
    d.hp = 3
    d.add_condition(Bleeding(2, 3))
    _tick(d)
    assert d.hp == 1                                 # the full 2, armor or not
    _tick(d)
    assert d.hp <= 0 and d.dying                     # the bleed took the last points
    assert not d.has_condition("bleeding")


def test_razor_claws_make_a_bare_handed_hit_bleed_for_one_over_two_turns():
    batt, cat, human = _duel(("razor_claws",))
    cat.char.strength = 18
    with fixed_d20(20):
        _resolve_hit(batt, cat, human, 20, 0, "", "claw")
    bleed = human.condition("bleeding")
    assert bleed is not None and (bleed.damage, bleed.duration) == (1, 2)
    with fixed_d20(20):
        _resolve_hit(batt, cat, human, 20, 0, "", "claw")
    assert human.condition("bleeding").damage == 2


def test_razor_claws_do_nothing_with_a_weapon_in_hand_or_without_the_talent():
    batt, cat, human = _duel(("razor_claws",), armed=True)
    assert cat.armed
    with fixed_d20(20):
        _resolve_hit(batt, cat, human, 20, 0, "", "blade")
    assert not human.has_condition("bleeding")
    batt, plain, human = _duel(())
    with fixed_d20(20):
        _resolve_hit(batt, plain, human, 20, 0, "", "fist")
    assert not human.has_condition("bleeding")


def test_everyone_bleeds_even_an_automaton():
    batt, cat, robot = _duel(("razor_claws",), foe_race="Automaton")
    cat.char.strength = 18
    with fixed_d20(20):
        _resolve_hit(batt, cat, robot, 20, 0, "", "claw")
    assert robot.has_condition("bleeding")


def test_the_bleed_shows_in_what_a_side_knows_of_the_foe():
    from gartok import intel
    _, _, d = _duel()
    d.add_condition(Bleeding(2, 3))
    assert "bleeding 2 for 3" in intel._conditions(d)


# --- Night Prowler ------------------------------------------------------------- #

def _guild_at(hour):
    from gartok.clock import Clock
    return SimpleNamespace(clock=Clock(hour * 3600), vocation=None, charter=None)


def test_night_prowler_cuts_the_ambush_chance_only_at_night_and_only_when_cautious(monkeypatch):
    monkeypatch.setattr(vocations, "_is", lambda guild, v: False)
    night, day = _guild_at(22), _guild_at(12)
    assert vocations.ambush_mult(night, CAUTIOUS, prowler=True) == vocations.NIGHT_PROWLER_AMBUSH == 0.8
    assert vocations.ambush_mult(day, CAUTIOUS, prowler=True) == 1.0
    assert vocations.ambush_mult(night, NORMAL, prowler=True) == 1.0
    assert vocations.ambush_mult(night, CAUTIOUS, prowler=False) == 1.0


def test_night_prowler_multiplies_with_the_woodland_scout(monkeypatch):
    monkeypatch.setattr(vocations, "_is", lambda guild, v: False)
    mult = vocations.ambush_mult(_guild_at(23), CAUTIOUS, scout=True, prowler=True)
    assert abs(mult - 0.9 * 0.8) < 1e-9


def test_a_group_with_a_night_prowler_gets_the_road_ambush_trimmed_at_night(monkeypatch):
    from unittest.mock import patch

    from gartok import forced, world
    from gartok.clock import Clock
    from gartok.guild import Guild
    cat = _catfolk("night_prowler")
    guild = Guild([cat], node="road")
    guild.clock = Clock(22 * 3600)
    group = guild.groups[0]
    group.stance = CAUTIOUS
    roll = world.ROAD_AMBUSH_CHANCE * 0.9            # between x0.8 and x1
    pack = [standard_unit("enemy")] * 3
    with patch("gartok.forced.random.random", return_value=roll), \
            patch("gartok.forced.encounters.roll_encounter", return_value=pack):
        assert forced.road_ambush_catch(guild, group, None, ["road"]) is None
        guild.clock = Clock(12 * 3600)
        assert forced.road_ambush_catch(guild, group, None, ["road"]).kind == "ambush"


# --- Open Market --------------------------------------------------------------- #

def _shopper(cat, alignment):
    u = _catfolk("open_market") if cat else standard_unit()
    u.languages = ["Ankarin"]
    u.alignment = alignment
    return u


def test_open_market_removes_only_the_penalty_for_a_different_tendency():
    far = "Chaotic and Evil"                          # vendor below is Lawful and Good: distance 4
    vendor = "Lawful and Good"
    assert economy.market_deal([_shopper(False, far)], "Ankarin", vendor) == -0.10
    assert economy.market_deal([_shopper(True, far)], "Ankarin", vendor) == 0.0


def test_open_market_keeps_the_break_for_a_kindred_tendency():
    same = "Lawful and Good"
    assert economy.market_deal([_shopper(True, same)], "Ankarin", same) == 0.10


def test_a_cautious_hunt_that_crosses_dusk_is_trimmed_only_for_the_dark_hours():
    from gartok import hunt
    cat = _catfolk("night_prowler")
    guild = _guild_at(15)

    class Roll:                                         # always rolls this share of the plain hourly chance
        def random(self):
            return hunt.AMBUSH_CHANCE_PER_HOUR * 0.9

    def stretch(stance, hours=8, start=15):
        state = hunt.begin(guild, [cat], None, stance, hours_left=hours)
        return state, hunt.hunt_stretch(state, rng=Roll(), hour=start)

    cautious, (elapsed, ambushed) = stretch(CAUTIOUS)
    assert cautious.night_mult == vocations.NIGHT_PROWLER_AMBUSH
    assert ambushed and elapsed == 1                    # a bright afternoon hour: the roll lands
    _, (elapsed, ambushed) = stretch(CAUTIOUS, start=19)
    assert not ambushed and elapsed == 8                # all dark: 0.9 x 0.8 sits under the chance
    _, (elapsed, ambushed) = stretch(NORMAL, start=19)
    assert ambushed and elapsed == 1                    # no stance, no trim


def test_a_hunt_saved_before_night_prowler_still_loads():
    from gartok import hunt
    state = hunt.begin(_guild_at(10), [_catfolk()], None, NORMAL, hours_left=4)
    saved = hunt.to_dict(state)
    del saved["night_mult"]
    assert hunt.from_dict(saved, [_catfolk()], None).night_mult == 1.0


def test_the_ai_values_a_clawed_blow_above_a_plain_one():
    from gartok.ai import reckon
    batt, cat, human = _duel(("razor_claws",))
    batt2, plain, human2 = _duel(())
    assert reckon._strike_worth(batt, cat, human) > reckon._strike_worth(batt2, plain, human2)


def test_a_seized_weapon_strike_does_not_bleed_even_from_bare_hands():
    batt, cat, human = _duel(("razor_claws",))
    cat.char.strength = 18
    dagger = items.get("Dagger")
    with fixed_d20(20):
        _resolve_hit(batt, cat, human, 20, 0, "", "wrest", weapon=dagger)
    assert not human.has_condition("bleeding")


def test_the_ai_goes_for_the_foe_whose_wounds_are_about_to_finish_it():
    from gartok.ai.target import _focus_key
    batt2 = Battle([standard_unit()], [standard_unit("enemy"), standard_unit("enemy")])
    me, bleeding, fresh = batt2.units
    me.pos, bleeding.pos, fresh.pos = (5, 5), (6, 5), (5, 6)
    batt2.intel.margin["player"][bleeding] = batt2.intel.margin["player"][fresh] = 12
    bleeding.hp = fresh.hp = 6
    assert _focus_key(batt2, me, bleeding) == _focus_key(batt2, me, fresh)
    bleeding.add_condition(Bleeding(3, 2))
    assert _focus_key(batt2, me, bleeding) < _focus_key(batt2, me, fresh)

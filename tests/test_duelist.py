"""Finesse fighters: Dexterity alone on the blow, the Duelist's empty hand, the Free Step, and the AI
that steps to a flank and leaves the light to someone else."""

from gartok import actions, ai, items, outfit
from gartok.ai.target import _flank_step, _free_approach
from tests.helpers import Battle, standard_unit

PATH = ("agile", "deadeye", "fleet", "free_step")


def _fencer(team="player", *talents, weapon="Rapier", offhand=None, dex=14, strength=8):
    u = standard_unit(team)
    u.base_attributes["dexterity"], u.base_attributes["strength"] = dex, strength
    u._apply_attributes()
    u.set_kit(weapon, None)
    u.equipped_offhand = offhand
    if weapon == "Shortbow":
        u.give_to_pack(items.AMMO_ITEM)
    for i, t in enumerate(talents, 1):
        u.set_track_level("combat", i)
        assert u.choose_talent("combat", t), t
    u._derive_combat()
    u.hp = u.hp_max
    return u


def _damage(c, monkeypatch):
    monkeypatch.setattr("gartok.combatant.roll", lambda n, faces: n)
    return c.damage_roll()


def test_a_finesse_blow_adds_dexterity_not_strength(monkeypatch):
    b = Battle([_fencer(dex=16, strength=6)], [standard_unit("enemy")])
    c = b.units[0]
    assert _damage(c, monkeypatch) == 1 + c.mod_dexterity
    assert c.mod_dexterity != c.mod_strength


def test_a_plain_blade_still_adds_strength(monkeypatch):
    b = Battle([_fencer(weapon="Club", dex=6, strength=16)], [standard_unit("enemy")])
    c = b.units[0]
    assert _damage(c, monkeypatch) == 1 + c.mod_strength


def test_the_duelist_adds_one_with_an_empty_off_hand(monkeypatch):
    b = Battle([_fencer("player", "agile", "duelist")], [standard_unit("enemy")])
    c = b.units[0]
    assert c.free_hand
    assert _damage(c, monkeypatch) == 1 + c.mod_dexterity + 1


def test_the_duelist_loses_the_point_to_a_shield_a_torch_or_a_second_hand(monkeypatch):
    for offhand in ("Dwarf Shield", items.TORCH_ITEM):
        c = Battle([_fencer("player", "agile", "duelist", offhand=offhand)], [standard_unit("enemy")]).units[0]
        assert not c.free_hand
        assert _damage(c, monkeypatch) == 1 + c.mod_dexterity
    two = Battle([_fencer("player", "agile", "duelist", weapon="Broadsword")], [standard_unit("enemy")]).units[0]
    assert not two.free_hand


def test_the_duelist_point_is_for_finesse_only(monkeypatch):
    c = Battle([_fencer("player", "agile", "duelist", weapon="Club", strength=16)], [standard_unit("enemy")]).units[0]
    assert _damage(c, monkeypatch) == 1 + c.mod_strength


def test_the_free_step_needs_the_talent_and_fleet():
    assert not _fencer("player", "agile").talent_bonus("free_step")
    assert not actions.FREE_STEP.available(*_walker(("agile",)))
    assert actions.FREE_STEP.available(*_walker(PATH))


def _walker(path):
    b = Battle([_fencer("player", *path)], [standard_unit("enemy")])
    c, foe = b.units
    b.board.walls.clear()
    c.pos, foe.pos = (5, 5), (12, 12)
    return b, c


def test_the_free_step_moves_one_square_for_no_action_point_once_a_turn():
    b, c = _walker(PATH)
    ap = c.ap
    assert actions.FREE_STEP.can(b, c, (6, 5)) and not actions.FREE_STEP.can(b, c, (8, 5))
    actions.FREE_STEP.execute(b, c, (6, 5))
    assert c.pos == (6, 5) and c.ap == ap
    assert not actions.FREE_STEP.available(b, c)
    c.start_turn(b.log)
    assert actions.FREE_STEP.available(b, c)


def test_the_free_step_leaves_a_started_walk_as_it_was():
    b, c = _walker(PATH)
    actions.FREE_STEP.execute(b, c, (6, 5))
    assert not c.walking and c.moved == 0


def _flank_fight(path=(), weapon="Rapier"):
    me = _fencer("player", *path, weapon=weapon)
    mate = standard_unit("player")
    b = Battle([me, mate], [standard_unit("enemy")])
    c, m, foe = b.units
    b.board.walls.clear()
    b.ambient_light = True
    foe.pos = (5, 5)
    m.pos = (4, 5)
    c.pos = (5, 4)
    return b, c, m, foe


def test_a_fencer_beside_the_foe_steps_to_the_far_side_for_a_flank():
    b, c, _m, foe = _flank_fight(PATH)
    c.pos = (6, 4)
    step = _flank_step(b, c, foe)
    assert step is not None and actions._flanked(b, c, foe) is False
    c.pos = step
    assert actions._flanked(b, c, foe)


def test_the_free_step_is_the_one_the_ai_takes(monkeypatch):
    b, c, _m, foe = _flank_fight(PATH)
    c.pos = (6, 4)
    ai.take_turn(b, c)
    assert c.free_step_used and actions._flanked(b, c, foe)


def test_a_unit_already_flanking_or_alone_does_not_step():
    b, c, _m, foe = _flank_fight(PATH)
    c.pos = (6, 5)
    assert _flank_step(b, c, foe) is None
    _m.pos = (11, 11)
    c.pos = (5, 4)
    assert _flank_step(b, c, foe) is None


def test_a_unit_with_ground_to_cover_spends_the_free_step_on_the_approach():
    b, c = _walker(PATH)
    foe = b.units[1]
    step = _free_approach(b, c, foe)
    assert step is not None and step != c.pos
    b.ambient_light = True
    ai.take_turn(b, c)
    assert c.free_step_used


def test_a_unit_already_in_reach_keeps_the_free_step_for_a_flank_or_nothing():
    b, c = _walker(PATH)
    foe = b.units[1]
    c.pos, foe.pos = (5, 5), (6, 5)
    assert _free_approach(b, c, foe) is None


def test_a_unit_without_the_talent_has_no_free_approach():
    b, c = _walker(("agile",))
    assert _free_approach(b, c, b.units[1]) is None


def test_a_ranged_unit_never_steps_to_flank():
    b, c, _m, foe = _flank_fight(PATH, weapon="Shortbow")
    c.pos = (6, 4)
    assert c.ranged and _flank_step(b, c, foe) is None


def _band(duelist_first=True):
    d = _fencer("player", "agile", "duelist")
    plain = _fencer("player", offhand=None)
    for u in (d, plain):
        u.set_track_level("combat", 2)
    return [d, plain] if duelist_first else [plain, d]


def test_a_band_hands_its_light_to_a_mate_and_not_to_the_duelist():
    band = _band()
    outfit.light_the_band(band)
    assert band[0].equipped_offhand is None
    assert band[1].equipped_offhand == items.TORCH_ITEM


def test_a_band_of_duelists_alone_still_carries_a_light():
    band = [_fencer("player", "agile", "duelist") for _ in range(2)]
    for u in band:
        u.set_track_level("combat", 2)
    outfit.light_the_band(band)
    assert sum(u.equipped_offhand == items.TORCH_ITEM for u in band) == 1


def test_paying_a_point_for_a_flank_is_not_worth_it_without_a_talent_that_pays_back():
    b, c, _m, foe = _flank_fight()
    c.pos = (6, 4)
    assert _flank_step(b, c, foe) is None


def test_a_duelist_with_a_plain_blade_takes_the_light():
    d = _fencer("player", "agile", "duelist", weapon="Club")
    d.set_track_level("combat", 2)
    outfit.light_the_band([d, _fencer("player", weapon="Broadsword")])
    assert d.equipped_offhand == items.TORCH_ITEM

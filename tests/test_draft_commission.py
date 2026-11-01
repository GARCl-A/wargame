"""Tests for the founding draft: a pool of nine, pick three, and the commission tokens."""

import subprocess
import sys
from gartok import archetypes, recruit
from gartok.draft import (
    COMMISSION_TOKENS,
    POOL_SIZE,
    TEAM_SIZE,
    Draft,
    leader_recruits,
)
from gartok.guild import Guild
from gartok.unit import Unit

def _commission(d, labels, target):
    d.pending_labels = list(labels)
    d.replace(target)


def test_the_draft_and_its_web_session_load_without_pygame():
    code = ("import sys; sys.modules['pygame'] = None; "
            "import gartok.draft, gartok.sheet, gartok.art_files, gartok.web.draft_session")
    subprocess.run([sys.executable, "-c", code], check=True)


def test_archetype_catalog_completeness():
    assert len(archetypes.ARCHETYPES) == 8
    for key, arc in archetypes.ARCHETYPES.items():
        assert arc.key == key
        assert arc.label
        assert arc.desc and arc.rule
        assert callable(arc.predicate)


def test_archetype_compatibility_rules():
    assert archetypes.is_compatible(["LEADER"], "TOUGH") is True
    assert archetypes.is_compatible(["STRONG"], "LEADER") is True
    assert archetypes.is_compatible(["LEADER"], "LEADER") is False


def test_generate_candidate_satisfies_requested_labels():
    assert archetypes.generate_candidate(["LEADER"]).mod_charisma >= 2
    assert archetypes.generate_candidate(["STRONG"]).mod_strength >= 2
    u_both = archetypes.generate_candidate(["LEADER", "TOUGH"])
    assert u_both.mod_charisma >= 2
    assert u_both.hp_max >= 8


def test_draft_starts_with_a_pool_of_nine_and_three_tokens():
    d = Draft()
    assert POOL_SIZE == 9 and TEAM_SIZE == 3
    assert len(d.pool) == POOL_SIZE
    assert d.tokens == COMMISSION_TOKENS == 3
    assert d.picks == [] and d.leader_pick is None


def test_picking_toggles_and_caps_at_three():
    d = Draft()
    units = d.pool[:4]
    for u in units[:3]:
        d.toggle_pick(u)
    d.toggle_pick(units[3])
    assert d.picks == units[:3]
    d.toggle_pick(units[0])
    assert d.picks == units[1:3]
    d.toggle_pick(units[3])
    assert d.picks == [units[1], units[2], units[3]]


def test_commission_replaces_the_chosen_card_and_spends_tokens_then():
    d = Draft()
    target = d.pool[4]
    d.pending_labels = ["LEADER"]
    assert d.tokens == 3
    d.replace(target)
    assert d.tokens == 2 and not d.pending_labels
    fresh = d.pool[4]
    assert fresh is not target and len(d.pool) == POOL_SIZE
    assert fresh.mod_charisma >= 2
    assert d.commissioned[id(fresh)] == ["LEADER"] and id(target) not in d.commissioned


def test_replacing_a_picked_card_drops_it_from_the_squad():
    d = Draft()
    target = d.pool[0]
    d.toggle_pick(target)
    d.toggle_pick(d.pool[1])
    _commission(d, ["STRONG"], target)
    assert target not in d.picks and len(d.picks) == 1
    assert d.pool[0].mod_strength >= 2


def test_tokens_carry_across_commissions_and_run_out():
    d = Draft()
    _commission(d, ["STRONG"], d.pool[0])
    assert d.tokens == 2
    _commission(d, ["LEADER", "TOUGH"], d.pool[1])
    assert d.tokens == 0
    assert d.pool[1].mod_charisma >= 2 and d.pool[1].hp_max >= 8


def test_each_founder_shows_what_the_guild_leader_could_recruit():
    for u in Draft().pool:
        total, parts = leader_recruits(u)
        guild = Guild([u])
        guild.leader = u
        assert total == recruit.capacity(guild, u)
        assert f"CHA {u.mod_charisma:+d}" in parts


def test_commission_archetypes_are_roles_not_a_race_picker():
    """A commission must leave the race open: for every archetype it takes at
    least four races to cover half of the candidates it can produce."""
    import random
    from collections import Counter
    random.seed(11)
    pool = [Unit("player") for _ in range(6000)]
    for key, arc in archetypes.ARCHETYPES.items():
        races = Counter(u.race["name"] for u in pool if arc.predicate(u))
        total, covered, needed = sum(races.values()), 0, 0
        for _, n in races.most_common():
            covered += n
            needed += 1
            if covered >= total / 2:
                break
        assert needed >= 3 and len(races) >= 10, (key, races.most_common(4))


def test_strong_is_about_strength_not_size():
    from tests.helpers import Unit
    u = Unit("player")
    u.set_base_attribute("strength", 20)
    assert archetypes.ARCHETYPES["STRONG"].predicate(u)
    u.set_base_attribute("strength", 6)
    assert not archetypes.ARCHETYPES["STRONG"].predicate(u)


def _body(**attrs):
    from tests.helpers import standard_unit
    u = standard_unit()
    for a, v in attrs.items():
        u.set_base_attribute(a, v)
    return u


def test_healthy_is_constitution_and_tough_is_hit_points():
    """The two are told apart on purpose: a high CON can sit on a small hit die, and the other way round."""
    healthy, tough = archetypes.ARCHETYPES["HEALTHY"], archetypes.ARCHETYPES["TOUGH"]
    u = _body(constitution=14)
    assert healthy.predicate(u) and not healthy.predicate(_body(constitution=13))
    u._hp_roll = 1
    u._derive_combat()
    assert u.hp_max < 8 and not tough.predicate(u)
    u = _body(constitution=8)
    u._hp_roll = 10
    u._derive_combat()
    assert tough.predicate(u) and not healthy.predicate(u)


def test_risky_names_each_reason_and_leaves_an_ordinary_body_alone():
    assert archetypes.risks(_body()) == []
    assert not archetypes.ARCHETYPES["RISKY"].predicate(_body())
    assert any("CON 8" in r for r in archetypes.risks(_body(constitution=8)))
    assert not archetypes.risks(_body(constitution=9))
    low = _body(strength=9, dexterity=9, constitution=9, intelligence=10, wisdom=10, charisma=10)
    assert sum(getattr(low, a) for a in archetypes.ATTRIBUTES) == 57 and not archetypes.risks(low)
    low.set_base_attribute("charisma", 9)
    assert any("add up to 56" in r for r in archetypes.risks(low))


def test_risky_when_the_strength_cannot_carry_the_starting_kit():
    assert archetypes.STARTER_KIT_KG == 8.0
    ok, weak = _body(strength=8), _body(strength=7)
    assert ok.carry_normal >= archetypes.STARTER_KIT_KG and not archetypes.risks(ok)
    assert weak.carry_normal < archetypes.STARTER_KIT_KG
    assert any("starting kit" in r for r in archetypes.risks(weak))


def test_a_card_says_why_it_is_risky_and_it_can_be_commissioned():
    text = next(t for lb, _, t in archetypes.unit_archetypes(_body(constitution=6)) if lb == "RISKY")
    assert "CON 6" in text
    u = archetypes.generate_candidate(["RISKY", "LEADER"])
    assert archetypes.ARCHETYPES["RISKY"].predicate(u) and u.mod_charisma >= 2

"""The tavern pitch and the weekly pool."""

import random

from tests.helpers import recruit, _FixedRNG, _person


def test_recruit_needs_a_shared_language():
    r = _person(1, lang="Ankarin")
    c = _person(2, lang="Orcish")
    assert not recruit.can_pitch(r, c)
    p = recruit.convince(r, c, 3)
    assert not p.ok and p.reason == "no shared language"


def test_recruit_is_a_charisma_contest_and_ties_go_to_the_stranger():
    r = _person(1, cha=2)
    c = _person(2, cha=0)
    tie = recruit.convince(r, c, 2, rng=_FixedRNG(10, 12))   # 12 vs 12 -> stranger stays put
    win = recruit.convince(r, c, 2, rng=_FixedRNG(11, 12))   # 13 vs 12 -> signs on
    assert not tie.ok and win.ok
    assert tie.modifiers == []                               # guild of 2 -> no size penalty


def test_taverna_pool_is_stable_within_the_week_then_refreshes():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(1)
    g = Guild([_person(1)], clock=Clock())
    first = list(recruit.refresh_pool(g))
    assert recruit.refresh_pool(g) is g.taverna_pool and g.taverna_pool == first
    g.clock.advance_hours(24 * recruit.REFRESH_DAYS)         # a week goes by
    recruit.refresh_pool(g)
    assert [u.uid for u in g.taverna_pool] != [u.uid for u in first]
    assert g.taverna_blocked == []                           # bars cleared with the new crop


def test_failed_pitch_bars_that_recruiter_only():
    from gartok.guild import Guild
    from gartok.clock import Clock
    g = Guild([], clock=Clock())
    r1, r2, cand = _person(1), _person(3), _person(2)
    recruit.bar(g, cand, r1)
    recruit.bar(g, cand, r1)                                 # idempotent
    assert recruit.barred(g, cand, r1) and not recruit.barred(g, cand, r2)
    assert g.taverna_blocked == [[cand.uid, r1.uid]]


def test_enlist_pulls_the_recruit_out_of_the_pool():
    from gartok.guild import Guild
    from gartok.clock import Clock
    random.seed(2)
    g = Guild([_person(1)], clock=Clock())
    pool = recruit.refresh_pool(g)
    cand = pool[1]
    recruit.enlist(g, cand, g.roster[0])
    assert cand in g.roster and cand not in g.taverna_pool and len(g.taverna_pool) == 2


def test_taverna_screen_pitch_does_not_double_pop_the_shared_pool():
    """Regression: TavernaScreen(candidates=None) hands out the live
    guild.taverna_pool -- the same list `recruit.enlist` already trims on a
    win. Popping self.sel again on top of that used to raise IndexError."""
    from gartok.guild import Guild
    from gartok.clock import Clock
    from gartok.taverna_screen import TavernaScreen

    random.seed(4)
    recruiter = _person(1, cha=100)                    # always wins the contest
    g = Guild([recruiter], clock=Clock())
    scr = TavernaScreen(fonts=None, guild=g, party=[recruiter], node=None, on_done=lambda: None)
    assert scr.candidates is g.taverna_pool

    scr.sel = len(scr.candidates) - 1                  # click the last stranger in the row
    cand = scr.candidates[scr.sel]
    recruiter.languages = list(cand.languages)          # guarantee the pitch can be made at all
    scr._pitch(recruiter)                              # must not raise IndexError

    assert cand in g.roster and cand not in g.taverna_pool
    assert cand not in scr.candidates


def test_recruit_alignment_distance_docks_the_pitch():
    r = _person(1, align="Lawful and Good")
    c = _person(2, align="Chaotic and Evil")                  # distance 4
    p = recruit.convince(r, c, 0, rng=_FixedRNG(15, 12))   # 15 - 4 = 11  vs  12 -> fail
    assert not p.ok
    assert any(v == -4 for v, _ in p.modifiers)


def test_recruit_bigger_guild_is_a_harder_sell():
    assert (recruit.size_penalty(2), recruit.size_penalty(3), recruit.size_penalty(7)) == (0, 1, 5)
    r, c = _person(1), _person(2)
    small = recruit.convince(r, c, 2, rng=_FixedRNG(11, 10))
    big = recruit.convince(r, c, 6, rng=_FixedRNG(11, 10))   # same rolls, -4 for the crowd
    assert small.ok and not big.ok


def test_enlist_binds_the_recruit_to_the_recruiter():
    from gartok.guild import Guild
    r, c = _person(1), _person(2)
    g = Guild([r])
    recruit.enlist(g, c, r)
    assert c in g.roster and c.recruited_by == r.uid


def test_recruit_capacity_is_base_plus_charisma_for_a_non_leader():
    from gartok.guild import Guild
    leader, m = _person(1, cha=4), _person(2, cha=2)   # highest CHA auto-leads
    g = Guild([leader, m])
    assert g.leader is leader
    assert recruit.capacity(g, m) == recruit.BASE_RECRUIT_CAPACITY + 2


def test_recruit_capacity_never_goes_negative():
    from gartok.guild import Guild
    leader, m = _person(1, cha=4), _person(2, cha=-4)
    g = Guild([leader, m])
    assert recruit.capacity(g, m) == 0


def test_guild_leader_adds_their_racial_level_to_capacity():
    from gartok.guild import Guild
    leader, m = _person(1, cha=0), _person(2, cha=0)
    g = Guild([leader, m])
    assert g.leader is leader                          # tie on CHA -> first stays leader (max() default)
    leader.set_track_level("combat", 3)
    leader.set_track_level("work", 2)
    assert leader.racial_level > 0
    assert recruit.capacity(g, leader) == recruit.BASE_RECRUIT_CAPACITY + leader.racial_level
    assert recruit.capacity(g, m) == recruit.BASE_RECRUIT_CAPACITY   # no leader bonus


def test_slots_free_drops_as_recruits_are_enlisted_and_blocks_past_capacity():
    from gartok.guild import Guild
    r = _person(1, cha=0)                               # capacity == BASE_RECRUIT_CAPACITY == 1
    g = Guild([r])
    assert recruit.slots_free(g, r) == 1
    recruit.enlist(g, _person(2), r)
    assert recruit.slots_free(g, r) == 0   # the taverna screen's eligibility gate reads this same check


def test_a_dead_recruiters_line_keeps_working():
    """Killing a recruiter doesn't cripple their own recruits' ability to
    keep the chain going -- `recruited_by` pointing at a dead uid is inert,
    not a standing penalty on the descendant."""
    from gartok.guild import Guild
    r, extra = _person(1, cha=0), _person(3, cha=4)
    g = Guild([r, extra])
    cand = _person(2, cha=4)
    recruit.enlist(g, cand, r)
    g.remove_members([r])                                # r dies; cand and extra survive
    assert cand.recruited_by == r.uid                     # the record itself doesn't change
    assert cand in g.roster and r not in g.roster
    assert recruit.slots_free(g, cand) == recruit.BASE_RECRUIT_CAPACITY + 4   # unaffected
    grandchild = _person(4)
    recruit.enlist(g, grandchild, cand)                   # the chain still extends
    assert grandchild.recruited_by == cand.uid


def test_bail_cost():
    """(sum(attributes) * (racial_level + 1)) + 20 -- the `+1` (added in
    7c80f3c, after this test's first version) keeps a level-0 candidate's
    bail scaled to attributes instead of a flat 20 copper."""
    from gartok.unit import ATTRIBUTES
    cand = _person(1)
    cand.set_track_level("combat", 2)
    cand._racial_override = 1

    total = sum(getattr(cand, a) for a in ATTRIBUTES)
    expected = (total * (1 + 1)) + 20

    assert recruit.bail_cost(cand) == expected


def test_prison_pool_management():
    from gartok.guild import Guild
    from gartok.clock import Clock
    g = Guild([_person(1)], clock=Clock())
    first = list(recruit.refresh_prison_pool(g))
    assert recruit.refresh_prison_pool(g) is g.prison_pool and g.prison_pool == first
    
    cand = first[0]
    rec = g.roster[0]
    recruit.prison_bar(g, cand, rec)
    assert recruit.prison_barred(g, cand, rec)
    
    g.clock.advance_hours(24 * recruit.REFRESH_DAYS)
    recruit.refresh_prison_pool(g)
    assert g.prison_blocked == []
    
    new_pool = list(recruit.refresh_prison_pool(g))
    assert new_pool != first


def test_pitch_block_reasons():
    from gartok.guild import Guild
    # 1. Eligible member -> None
    r1 = _person(1, lang="Comum", cha=1)
    cand_comum = _person(2, lang="Comum")
    g = Guild([r1])
    assert recruit.pitch_block_reason(g, [r1], cand_comum) is None

    # 2. No one shares language
    cand_orque = _person(3, lang="Orque")
    assert recruit.pitch_block_reason(g, [r1], cand_orque) == "no one in the party can speak with them"

    # 3. Whole party tried
    recruit.bar(g, cand_comum, r1)
    assert recruit.pitch_block_reason(g, [r1], cand_comum) == "everyone already tried this week"

    # 4. All speakers tried, but other non-speakers exist in party
    r2 = _person(4, lang="Anao", cha=1)
    g.add_member(r2, g.groups[0])
    assert recruit.pitch_block_reason(g, [r1, r2], cand_comum) == "all speakers already tried this week"

    # 5. No sponsor slots free in entire party
    cand_elfico = _person(5, lang="Elfico")
    r3 = _person(6, lang="Elfico", cha=0)  # cap=1
    g2 = Guild([r3])
    dummy = _person(7)
    recruit.enlist(g2, dummy, r3)          # r3 slots_free == 0
    assert recruit.slots_free(g2, r3) == 0
    assert recruit.pitch_block_reason(g2, [r3], cand_elfico) == "no sponsor slots free in party"

    # 6. Speakers have no slots, but another party member has slots (who doesn't speak the tongue)
    r4_open = _person(8, lang="Comum", cha=2)  # has slots, doesn't speak Elfico
    g2.add_member(r4_open, g2.groups[0])
    assert recruit.slots_free(g2, r4_open) > 0
    assert recruit.pitch_block_reason(g2, [r3, r4_open], cand_elfico) == "speakers have no sponsor slots free"

    # 7. Some speakers tried, others have no slots
    r5_speaker = _person(9, lang="Elfico", cha=1)  # has slot, but will be barred
    g2.add_member(r5_speaker, g2.groups[0])
    recruit.bar(g2, cand_elfico, r5_speaker)
    # r5_speaker is barred; r3 is unbarred but has 0 slots
    assert recruit.pitch_block_reason(g2, [r3, r5_speaker], cand_elfico) == "speakers already tried or have no room"

    # 8. Prison barred check
    cand_prison = _person(10, lang="Comum")
    r6 = _person(11, lang="Comum", cha=1)
    g3 = Guild([r6])
    assert recruit.pitch_block_reason(g3, [r6], cand_prison, is_prison=True) is None
    recruit.prison_bar(g3, cand_prison, r6)
    assert recruit.pitch_block_reason(g3, [r6], cand_prison, is_prison=True) == "everyone already tried this week"


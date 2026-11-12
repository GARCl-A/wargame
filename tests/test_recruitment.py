"""The tavern pitch and the weekly pool."""

import random

from tests.helpers import _FixedRNG, _person, recruit, standard_unit


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
    from gartok.clock import Clock
    from gartok.guild import Guild
    random.seed(1)
    g = Guild([_person(1)], clock=Clock())
    first = list(recruit.refresh_pool(g))
    assert recruit.refresh_pool(g) is g.taverna_pool and g.taverna_pool == first
    g.clock.advance_hours(24 * recruit.REFRESH_DAYS)         # a week goes by
    recruit.refresh_pool(g)
    assert [u.uid for u in g.taverna_pool] != [u.uid for u in first]
    assert g.taverna_blocked == []                           # bars cleared with the new crop


def test_failed_pitch_bars_that_recruiter_only():
    from gartok.clock import Clock
    from gartok.guild import Guild
    g = Guild([], clock=Clock())
    r1, r2, cand = _person(1), _person(3), _person(2)
    recruit.bar(g, cand, r1)
    recruit.bar(g, cand, r1)                                 # idempotent
    assert recruit.barred(g, cand, r1) and not recruit.barred(g, cand, r2)
    assert g.taverna_blocked == [[cand.uid, r1.uid]]


def test_enlist_pulls_the_recruit_out_of_the_pool():
    from gartok.clock import Clock
    from gartok.guild import Guild
    random.seed(2)
    g = Guild([_person(1)], clock=Clock())
    pool = recruit.refresh_pool(g)
    cand = pool[1]
    recruit.enlist(g, cand, g.roster[0])
    assert cand in g.roster and cand not in g.taverna_pool and len(g.taverna_pool) == 2


def test_taverna_pitch_does_not_double_pop_the_shared_pool():
    """Regression: Tavern(candidates=None) hands out the live
    guild.taverna_pool -- the same list `recruit.enlist` already trims on a
    win. Popping self.sel again on top of that used to raise IndexError."""
    from gartok.clock import Clock
    from gartok.guild import Guild
    from gartok.tavern import Tavern

    random.seed(4)
    recruiter = _person(1, cha=100)                    # always wins the contest
    g = Guild([recruiter], clock=Clock())
    scr = Tavern(g, g.groups[0])
    assert scr.candidates == g.taverna_pool

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
    from gartok.clock import Clock
    from gartok.guild import Guild
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

    # 5. No recruitment slots in the whole party (leads, whatever else is wrong)
    cand_elfico = _person(5, lang="Elfico")
    r3 = _person(6, lang="Elfico", cha=0)  # cap=1
    g2 = Guild([r3])
    dummy = _person(7)
    recruit.enlist(g2, dummy, r3)          # r3 slots_free == 0
    assert recruit.slots_free(g2, r3) == 0
    assert recruit.pitch_block_reason(g2, [r3], cand_elfico) == "no recruitment slots available"

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


def test_prison_pitch_removes_candidate_without_index_error(monkeypatch):
    from gartok.guild import Guild
    from gartok.tavern import Prison
    from gartok.unit import Unit

    recruiter = Unit("player")
    recruiter.money = 500
    recruiter.mod_charisma = 5
    recruiter.languages = ["Common"]
    g = Guild([recruiter])
    recruit.refresh_prison_pool(g)
    assert len(g.prison_pool) >= 2

    # Test selecting the LAST candidate in the pool (e.g. index PRISON_SIZE - 1)
    scr = Prison(g, g.groups[0])
    last_idx = len(scr.candidates) - 1
    scr.sel = last_idx
    target_cand = scr.candidates[last_idx]
    target_cand.languages = ["Common"]

    # Force convince to succeed
    monkeypatch.setattr(recruit, "convince", lambda *a, **kw: recruit.Pitch(True, 15, 10, 5, 2, []))

    scr._pitch(recruiter)

    assert target_cand in g.roster
    assert target_cand not in g.prison_pool
    assert target_cand not in scr.candidates
    assert scr.sel == len(scr.candidates) - 1            # the selection follows the shrunken list

    # Calling pitch with sel=None or out of bounds is safe
    scr.sel = None
    scr._pitch(recruiter)
    assert scr.sel is None

    # Test failed pitch
    scr.sel = 0
    remaining_cand = scr.candidates[0]
    remaining_cand.languages = ["Common"]
    gold_before = recruiter.money
    monkeypatch.setattr(recruit, "convince", lambda *a, **kw: recruit.Pitch(False, 5, 12, -7, 2, []))
    scr._pitch(recruiter)
    assert recruit.prison_barred(g, remaining_cand, recruiter)
    assert recruiter.money == gold_before
    assert remaining_cand not in g.roster
    assert remaining_cand in scr.candidates
    assert scr.sel == 0                                   # still looking at them after the failed pitch





def _prison(party_gold=500):
    from gartok.guild import Guild
    from gartok.tavern import Prison
    from gartok.unit import Unit
    recruiter = Unit("player")
    recruiter.money = party_gold
    recruiter.mod_charisma = 5
    recruiter.languages = ["Common"]
    g = Guild([recruiter])
    scr = Prison(g, g.groups[0])
    scr.candidates[0].languages = ["Common"]
    return scr, g, recruiter


def test_the_prison_is_the_tavern_with_a_bail_and_a_bonus():
    from gartok.tavern import Tavern
    scr, g, recruiter = _prison()
    cand = scr.candidates[0]
    assert isinstance(scr, Tavern)
    assert scr._bail(cand) == recruit.bail_cost(cand)
    base = (recruiter.mod_charisma - recruit.size_penalty(len(g.roster))
            + recruiter.talent_bonus("recruit_cha"))
    assert scr._net(recruiter, cand) >= base - recruit.ALIGNMENT_PENALTY * 4 + 2


def test_a_prison_pitch_without_the_bail_money_rolls_nothing(monkeypatch):
    scr, g, recruiter = _prison(party_gold=0)
    rolled = []
    monkeypatch.setattr(recruit, "convince", lambda *a, **kw: rolled.append(1))
    scr.sel = 0
    scr._pitch(recruiter)
    assert not rolled and "Not enough coin" in scr.notice


def test_a_prison_pitch_takes_the_bail_only_on_success_and_adds_the_bonus(monkeypatch):
    scr, g, recruiter = _prison()
    cand = scr.candidates[0]
    cost = recruit.bail_cost(cand)
    seen = {}

    def fake(*a, **kw):
        seen.update(kw)
        return recruit.Pitch(True, 15, 10, 5, 2, [])

    monkeypatch.setattr(recruit, "convince", fake)
    scr.sel = 0
    before = recruiter.money
    scr._pitch(recruiter)
    assert before - recruiter.money == cost
    assert (2, "paid bail") in seen["extra_mods"]
    assert cand in g.roster


def test_a_failed_prison_pitch_costs_nothing_and_still_bars(monkeypatch):
    scr, g, recruiter = _prison()
    cand = scr.candidates[0]
    monkeypatch.setattr(recruit, "convince", lambda *a, **kw: recruit.Pitch(False, 5, 15, 5, 2, []))
    scr.sel = 0
    before = recruiter.money
    scr._pitch(recruiter)
    assert recruiter.money == before and cand not in g.roster and scr._barred(cand, recruiter)


def test_every_doubling_of_the_bail_adds_one_and_costs_double(monkeypatch):
    scr, g, recruiter = _prison(party_gold=5000)
    cand = scr.candidates[0]
    bail = recruit.bail_cost(cand)
    scr.sel = 0
    base = scr._net(recruiter, cand)
    seen = {}

    def fake(*a, **kw):
        seen.update(kw)
        return recruit.Pitch(True, 15, 10, 5, 2, [])

    monkeypatch.setattr(recruit, "convince", fake)
    scr._raise(1)
    scr._raise(1)
    assert scr.raise_k == 2 and scr._due(cand) == bail * 4 and scr._net(recruiter, cand) == base + 2
    before = recruiter.money
    scr._pitch(recruiter)
    assert (2, "extra bail") in seen["extra_mods"] and before - recruiter.money == bail * 4
    assert scr.raise_k == 0


def test_a_doubling_the_purse_cannot_cover_is_refused_and_picking_resets_it():
    scr, g, recruiter = _prison()
    cand = scr.candidates[0]
    scr.sel = 0
    for _ in range(40):
        scr._raise(1)
    k = scr.raise_k
    assert scr._due(cand) <= scr._wealth() < recruit.bail_cost(cand) << (k + 1)
    scr._raise(-1)
    assert scr.raise_k == k - 1
    scr._pick_candidate(0)
    assert scr.raise_k == 0
    scr._raise(-1)
    assert scr.raise_k == 0


def test_the_taverna_pitch_is_free_and_adds_no_bonus(monkeypatch):
    from gartok.guild import Guild
    from gartok.tavern import Tavern
    recruiter = standard_unit()
    recruiter.money = 50
    recruiter.languages = ["Common"]
    g = Guild([recruiter])
    cand = standard_unit()
    cand.languages = ["Common"]
    scr = Tavern(g, g.groups[0], candidates=[cand])
    seen = {}
    monkeypatch.setattr(recruit, "convince",
                        lambda *a, **kw: seen.update(kw) or recruit.Pitch(False, 5, 12, -7, 2, []))
    scr._pitch(recruiter)
    assert recruiter.money == 50 and seen["extra_mods"] == []


def test_a_rejected_stranger_reads_rejected_only_when_nobody_can_still_pitch(monkeypatch):
    from gartok.guild import Guild
    from gartok.tavern import Tavern
    first, second = standard_unit(), standard_unit()
    for u in (first, second):
        u.languages = ["Common"]
    g = Guild([first, second])
    cand = standard_unit()
    cand.languages = ["Common"]
    scr = Tavern(g, g.groups[0], candidates=[cand])
    monkeypatch.setattr(recruit, "convince", lambda *a, **kw: recruit.Pitch(False, 5, 12, -7, 2, []))
    scr._pitch(first)
    assert scr._cand_status(cand) == (f"{second.name} can pitch", "good")
    scr._pitch(second)
    assert scr._cand_status(cand) == ("rejected this week", "bad")


def _hint(guild, group, cand):
    """What the Tavern's dossier says under the pitch, with the first member picked to make it."""
    from gartok import world
    from gartok.web.tavern_tab import TavernTab
    tab = TavernTab(guild, group, world.node("tavern"), candidates=[cand])
    tab.recruiter(group.members[0].uid)
    hint = tab.state("recruits")["dossier"]["hint"]
    return hint and hint["text"]


def test_taverna_says_why_nobody_can_pitch():
    from gartok.guild import Guild
    r = _person(1, lang="Comum")
    cand = _person(2, lang="Orque")
    g = Guild([r])
    assert "no one in the party can speak with them" in _hint(g, g.groups[0], cand)


def test_taverna_warns_when_the_recruit_overflows_the_group():
    from tests.test_cohesion import _full_guild, _unit
    guild, group, _m = _full_guild(extra=0)
    assert "group is full" in _hint(guild, group, _unit(1))


def test_no_slots_is_the_first_reason_even_when_the_language_is_missing_too():
    from gartok.guild import Guild
    r = _person(1, lang="Comum", cha=0)
    g = Guild([r])
    recruit.enlist(g, _person(2), r)
    stranger = _person(3, lang="Orque")
    assert recruit.pitch_block_reason(g, [r], stranger) == "no recruitment slots available"


def test_map_flags_a_pool_that_turned_over_until_the_guild_walks_in():
    from gartok.clock import Clock
    from gartok.guild import Guild
    from gartok.tavern import Prison, Tavern
    g = Guild([_person(1)], clock=Clock())
    assert recruit.has_new_faces(g, "taverna") and recruit.has_new_faces(g, "prison")
    Tavern(g, g.groups[0])
    assert not recruit.has_new_faces(g, "taverna") and recruit.has_new_faces(g, "prison")
    Prison(g, g.groups[0])
    assert not recruit.has_new_faces(g, "prison")
    g.clock.advance_hours(24 * recruit.REFRESH_DAYS)
    assert recruit.has_new_faces(g, "taverna") and recruit.has_new_faces(g, "prison")


def _talker(*talents, cha=2):
    u = standard_unit()
    u.languages = ["Common"]
    for level, tid in enumerate(talents, 1):
        u.set_track_level("work", level)
        assert u.choose_talent("work", tid)
    u.mod_charisma = cha
    return u


_JOINT = ("charismatic", "fixer", "joint_pitch")
_CUT = (*_JOINT, "crowd_pleaser")


def test_the_crowd_penalty_cut_rounds_up_and_never_touches_a_small_guild():
    cutter, plain = _talker(*_CUT), _talker()
    paid = {n: recruit.size_penalty(recruit.FREE_SLOTS + n, cutter) for n in (0, 1, 5, 10, 11, 20)}
    assert paid == {0: 0, 1: 0, 5: 4, 10: 9, 11: 9, 20: 18}
    assert [recruit.size_penalty(recruit.FREE_SLOTS + n, plain) for n in (0, 1, 5, 20)] == [0, 1, 5, 20]
    assert recruit.size_penalty(recruit.FREE_SLOTS + 5) == 5


def _joint_scene(allies=2):
    from gartok.clock import Clock
    from gartok.guild import Guild
    a = _talker(*_JOINT)
    mates = [_talker(cha=1) for _ in range(allies)]
    cand = standard_unit("player")
    cand.languages = ["Common"]
    g = Guild([a, *mates], clock=Clock())
    return g, a, mates, cand


def _no_bar(cand, member):
    return False


def test_allies_who_could_recruit_alone_are_the_joint_pitch_rollers():
    g, a, mates, cand = _joint_scene(allies=3)
    mates[0].languages = ["Other"]
    mates[1].mod_charisma = -5                                 # no free slot: 1 + (-5) < 1
    assert recruit.joint_allies(g, g.roster, cand, a, _no_bar) == [mates[2]]
    assert recruit.joint_allies(g, g.roster, cand, a, lambda c, m: m is mates[2]) == []
    assert recruit.joint_allies(g, g.roster, cand, mates[2], _no_bar) == []     # no talent, no joint pitch


def test_a_joint_pitch_rolls_one_die_per_roller_each_with_plus_one_per_other_and_the_best_counts():
    g, a, mates, cand = _joint_scene()
    allies = recruit.joint_allies(g, g.roster, cand, a, _no_bar)
    assert len(allies) == 2
    pitch = recruit.convince(a, cand, recruit.FREE_SLOTS, rng=_FixedRNG(4, 17, 9, 10), allies=allies)
    assert pitch.rolls == [4, 17, 9] and pitch.recruiter_roll == 17
    assert pitch.recruiter_total == 17 + a.mod_charisma + 2 + a.talent_bonus("recruit_cha")
    assert pitch.candidate_roll == 10 and pitch.ok
    alone = recruit.convince(a, cand, recruit.FREE_SLOTS, rng=_FixedRNG(4, 10))
    assert alone.rolls == [4] and not alone.ok


def test_a_joint_pitch_that_wins_uses_only_the_slot_of_the_one_who_pitched(monkeypatch):
    from gartok.tavern import Tavern
    g, a, mates, cand = _joint_scene()
    scr = Tavern(g, g.groups[0], [cand])
    scr.party = [a, *mates]
    scr.selected_recruiter = a
    scr.sel = 0
    used = [recruit.slots_used(g, m) for m in (a, *mates)]
    orig = recruit.convince
    monkeypatch.setattr(recruit, "convince", lambda *x, **kw: orig(*x, **{**kw, "rng": _FixedRNG(20, 20, 20, 1)}))
    scr._pitch(a)
    assert cand.recruited_by == a.uid
    assert recruit.slots_used(g, a) == used[0] + 1 and [recruit.slots_used(g, m) for m in mates] == used[1:]
    assert g.taverna_blocked == []


def test_a_joint_pitch_that_fails_bars_everyone_who_rolled(monkeypatch):
    from gartok.tavern import Tavern
    g, a, mates, cand = _joint_scene()
    bystander = _talker()
    g.add_member(bystander, g.groups[0])
    scr = Tavern(g, g.groups[0], [cand])
    scr.party = [a, *mates]
    scr.selected_recruiter = a
    scr.sel = 0
    orig = recruit.convince
    monkeypatch.setattr(recruit, "convince", lambda *x, **kw: orig(*x, **{**kw, "rng": _FixedRNG(1, 1, 1, 20)}))
    scr._pitch(a)
    assert {tuple(b) for b in g.taverna_blocked} == {(cand.uid, m.uid) for m in (a, *mates)}


def test_with_the_choice_off_the_pitch_is_alone_and_bars_only_the_pitcher(monkeypatch):
    from gartok.tavern import Tavern
    g, a, mates, cand = _joint_scene()
    scr = Tavern(g, g.groups[0], [cand])
    scr.party = [a, *mates]
    scr.selected_recruiter = a
    scr.sel = 0
    scr.joint = False
    seen = {}
    orig = recruit.convince

    def spy(*x, **kw):
        seen.update(kw)
        return orig(*x, **{**kw, "rng": _FixedRNG(1, 20)})
    monkeypatch.setattr(recruit, "convince", spy)
    scr._pitch(a)
    assert not seen["allies"]
    assert g.taverna_blocked == [[cand.uid, a.uid]]


def test_a_prison_joint_pitch_bars_through_the_prison_list(monkeypatch):
    from gartok.tavern import Prison
    g, a, mates, cand = _joint_scene()
    a.money = 1000
    scr = Prison(g, g.groups[0])
    scr.party = [a, *mates]
    scr.selected_recruiter = a
    scr.sel = 0
    orig = recruit.convince
    monkeypatch.setattr(recruit, "convince", lambda *x, **kw: orig(*x, **{**kw, "rng": _FixedRNG(1, 1, 1, 20)}))
    cand = scr.candidates[0]
    cand.languages = ["Common"]
    scr._pitch(a)
    assert {tuple(b) for b in g.prison_blocked} == {(cand.uid, m.uid) for m in (a, *mates)}
    assert g.taverna_blocked == []


def test_the_work_tree_reaches_joint_pitch_and_crowd_pleaser_through_fixer():
    from gartok import talents
    assert talents.get("joint_pitch").requires == "fixer" and talents.get("joint_pitch").tier == 3
    assert talents.get("crowd_pleaser").requires == "joint_pitch" and talents.get("crowd_pleaser").tier == 4
    u = standard_unit()
    u.set_track_level("work", 1)
    assert not u.choose_talent("work", "joint_pitch")
    assert [u.set_track_level("work", n) or u.choose_talent("work", t)
            for n, t in enumerate(_CUT, 1)] == [True] * 4

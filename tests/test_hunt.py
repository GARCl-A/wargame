"""Hunting the wilds: the hour-by-hour stretch and the meat payout."""

import random

from tests.helpers import Unit


def test_hunt_stretch_stops_on_the_first_ambush():
    from gartok import hunt

    class AlwaysAmbush:
        def random(self): return 0.0

    st = hunt.HuntState([], None, hours_left=8)
    elapsed, ambushed = hunt.hunt_stretch(st, AlwaysAmbush())
    assert ambushed and elapsed == 1
    assert st.hours_hunted == 1 and st.hours_left == 7

    class NeverAmbush:
        def random(self): return 1.0

    st = hunt.HuntState([], None, hours_left=5)
    elapsed, ambushed = hunt.hunt_stretch(st, NeverAmbush())
    assert not ambushed and elapsed == 5
    assert st.hours_hunted == 5 and st.hours_left == 0


def test_grant_meat_splits_the_haul_and_banks_the_hours():
    from gartok import hunt
    random.seed(0)
    party = [Unit("player"), Unit("player")]
    for u in party:
        u._base_inventory = []
        u.work_hours = 0
    st = hunt.HuntState(party, None, hours_left=0, hours_hunted=9)
    lines = hunt.grant_meat(st)
    total_meat = sum(u._base_inventory.count("Meat") for u in party)
    assert total_meat == 9 // hunt.HUNT_MEAT_HOURS            # 4 kg
    assert all(u.work_hours == 9 for u in party)              # both credited the hours
    assert any("meat" in ln for ln in lines)


class _ScriptRNG:
    """Feeds `hunt_stretch` a fixed sequence of `random()` values (ambush when
    the value is below `AMBUSH_CHANCE_PER_HOUR`)."""
    def __init__(self, *vals):
        self.vals = list(vals)

    def random(self):
        return self.vals.pop(0)


def test_a_won_ambush_lets_the_hunt_carry_on_from_where_it_stopped():
    """The keep-hunting loop: an ambush interrupts a stretch, the party wins,
    and the remaining daylight is hunted -- meat and work hours accrue across
    BOTH stretches, banked once at the end."""
    from gartok import hunt
    random.seed(0)
    party = [Unit("player"), Unit("player")]
    for u in party:
        u._base_inventory = []
        u.work_hours = 0
    st = hunt.HuntState(party, None, hours_left=8)

    elapsed, ambushed = hunt.hunt_stretch(st, _ScriptRNG(0.9, 0.9, 0.01))
    assert (elapsed, ambushed) == (3, True)                   # 3 h in, a pack hits
    assert st.hours_hunted == 3 and st.hours_left == 5 and st.meat == 1

    # won the fight -> spend the daylight that's left, no more ambushes
    elapsed, ambushed = hunt.hunt_stretch(st, _ScriptRNG(*[0.9] * 5))
    assert (elapsed, ambushed) == (5, False)
    assert st.hours_hunted == 8 and st.hours_left == 0 and st.meat == 4

    hunt.grant_meat(st)
    assert sum(u._base_inventory.count("Meat") for u in party) == 4
    assert all(u.work_hours == 8 for u in party)              # the whole hunt, both stretches


def test_hunt_screen_offers_the_interlude_after_a_won_ambush_then_wraps_up():
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok import hunt, world
    from gartok.clock import Clock
    from gartok.guild import Guild
    from gartok.hunt_screen import HuntScreen
    from gartok.theme import Fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    random.seed(0)

    party = [Unit("player")]
    party[0]._base_inventory = []
    party[0].work_hours = 0
    guild = Guild(list(party), node="wilds", clock=Clock(6 * 3600))
    st = hunt.HuntState(list(party), world.node("wilds"), hours_left=0)
    fired = []
    scr = HuntScreen(Fonts(), guild, st, phase="setup",
                     on_ambush=lambda s, pack: fired.append(s.hours_hunted),
                     on_done=lambda: fired.append("done"))

    def scripted(state, rng=None):
        step = 3 if not state.fights else state.hours_left
        state.hours_left -= step
        state.hours_hunted += step
        return step, state.fights == 0                    # ambush only on the first stretch

    orig, hunt.hunt_stretch = hunt.hunt_stretch, scripted
    try:
        scr.hours = 8
        scr._do_stretch()                                # setup -> a pack after 3 h
        assert fired == [3] and scr.phase == "setup" and st.fights == 1

        st.hours_left = 5                                 # app rebuilds the screen at interlude
        scr.phase = "interlude"
        scr._do_stretch()                                # KEEP HUNTING -> daylight runs out
    finally:
        hunt.hunt_stretch = orig

    assert scr.phase == "done"
    assert st.hours_hunted == 8 and party[0]._base_inventory.count("Meat") == 4
    assert party[0].work_hours == 8                       # grant_meat banked the full hunt

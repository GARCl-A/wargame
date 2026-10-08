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
    st = hunt.HuntState(party, None, hours_left=0, hours_hunted=9, yield_hours=9.0)
    lines = hunt.grant_haul(st)
    total_meat = sum(u.count_of("Meat") for u in party)
    assert total_meat == 9 // hunt.HUNT_MEAT_HOURS            # 4 kg
    assert all(u.work_hours == 9 * 4 for u in party)          # both credited, a level 3 job for level 0: x4
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
    party = [Unit("player"), Unit("player"), Unit("player")]      # a crew of three yields 1.0
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

    hunt.grant_haul(st)
    assert sum(u.count_of("Meat") for u in party) == 4
    assert all(u.work_hours == 8 * 4 for u in party)          # the whole hunt, both stretches, x4


def test_hunt_screen_offers_the_interlude_after_a_won_ambush_then_wraps_up():
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from gartok import hunt, world
    from gartok.clock import Clock
    from gartok.guild import Guild
    from gartok.hunt_screen import HuntScreen
    from gartok.ui.tokens import fonts as ui_fonts
    pygame.init()
    pygame.display.set_mode((1, 1))
    random.seed(0)

    party = [Unit("player")]
    party[0]._base_inventory = []
    party[0].work_hours = 0
    guild = Guild(list(party), node="wilds", clock=Clock(6 * 3600))
    st = hunt.HuntState(list(party), world.node("wilds"), hours_left=0)
    fired = []
    scr = HuntScreen(ui_fonts(), guild, st, phase="setup",
                     on_ambush=lambda s, pack: fired.append(s.hours_hunted),
                     on_done=lambda: fired.append("done"))

    def scripted(state, rng=None):
        step = 3 if not state.fights else state.hours_left
        state.hours_left -= step
        state.hours_hunted += step
        state.yield_hours += step
        return step, state.fights == 0                    # ambush only on the first stretch

    orig, hunt.hunt_stretch = hunt.hunt_stretch, scripted
    try:
        scr.hours = 8
        scr._do_stretch()                                # setup -> a pack after 3 h
        assert scr.phase == "ambush" and st.fights == 1
        surf = pygame.Surface((1280, 800))
        scr.draw(surf)
        scr._click(next(r.center for k, r in scr.buttons if k == "fight_ambush"))
        assert fired == [3]

        st.hours_left = 5                                 # app rebuilds the screen at interlude
        scr.phase = "interlude"
        scr._do_stretch()                                # KEEP HUNTING -> daylight runs out
    finally:
        hunt.hunt_stretch = orig

    assert scr.phase == "done"
    assert st.hours_hunted == 8 and party[0].count_of("Meat") == 4
    assert party[0].work_hours == 8 * 4                   # grant_meat banked the full hunt, x4


def test_forage_stretch_finds_shrooms_and_fruit():
    from gartok import hunt

    party = [Unit("player"), Unit("player"), Unit("player")]       # yield 1.0: the rolls are the base odds
    st = hunt.HuntState(party, None, hours_left=2, target="shrooms")

    class ForageRNG:
        def __init__(self):
            # Hour 1: shroom (<0.10), fruit (<0.15), no ambush (>=0.15)
            # Hour 2: no shroom (>=0.10), fruit (<0.15), no ambush (>=0.15)
            self.vals = [0.05, 0.05, 0.9, 0.5, 0.05, 0.9]

        def random(self):
            return self.vals.pop(0)

    elapsed, ambushed = hunt.hunt_stretch(st, ForageRNG())
    assert elapsed == 2
    assert not ambushed
    assert st.shrooms_found == 1
    assert st.fruit_found == 2


def test_grant_forage_distributes_both_shrooms_and_fruit():
    from gartok import hunt

    party = [Unit("player"), Unit("player")]
    for u in party:
        u._base_inventory = []
    st = hunt.HuntState(party, None, hours_left=0, hours_hunted=4, target="shrooms", shrooms_found=2, fruit_found=2)
    lines = hunt.grant_haul(st)

    assert sum(u.count_of("Red Mushroom") for u in party) == 2
    assert sum(u.count_of("Fruit") for u in party) == 2
    assert any("Red Mushroom" in ln and "Fruit" in ln for ln in lines)



def test_the_setup_screen_can_be_left_without_spending_time():
    import pygame

    from gartok import hunt, world
    from gartok.guild import Guild
    from gartok.hunt_screen import HuntScreen
    from gartok.unit import Unit

    guild = Guild([Unit("player")])
    state = hunt.HuntState(list(guild.roster), world.node("wilds"), hours_left=0)
    left = []
    screen = HuntScreen(None, guild, state, phase="setup", on_ambush=lambda *a: None,
                        on_done=lambda: left.append(True))
    screen.draw(pygame.Surface((1280, 720)))
    clock_before = guild.clock.seconds

    rect = dict(screen.buttons)["leave"]
    screen._click(rect.center)

    assert left == [True]
    assert guild.clock.seconds == clock_before
    assert state.hours_hunted == 0


def test_party_yield_curve_is_one_at_three_and_saturates_at_seven():
    from gartok import hunt
    assert hunt.party_yield(0) == 0
    assert hunt.party_yield(3) == 1.0
    ys = [hunt.party_yield(n) for n in range(1, 8)]
    assert ys == sorted(ys) and len(set(ys)) == 7              # every hand up to 7 adds something
    assert hunt.party_yield(7) == hunt.party_yield(12)           # and the 8th adds nothing
    gains = [b - a for a, b in zip(ys, ys[1:])]
    assert gains == sorted(gains, reverse=True)                  # diminishing returns


def test_more_hunters_bring_back_more_meat_but_less_each():
    from gartok import hunt
    meat = {}
    for n in (1, 3, 6):
        st = hunt.HuntState([Unit("player") for _ in range(n)], None, hours_left=16)
        hunt.hunt_stretch(st, _ScriptRNG(*[0.9] * 16))
        meat[n] = st.meat
    assert meat[1] < meat[3] < meat[6]
    assert meat[3] == 16 // hunt.HUNT_MEAT_HOURS
    assert meat[6] / 6 < meat[3] / 3 < meat[1] / 1


def test_foraging_odds_scale_with_the_party_too():
    from gartok import hunt

    class Always:
        def __init__(self):
            self.seq = iter([0.5, 0.12, 0.9] * 4)               # per hour: shroom miss, fruit 0.12, no ambush

        def random(self):
            return next(self.seq)                               # fruit needs < 0.15 * yield

    solo = hunt.HuntState([Unit("player")], None, hours_left=4, target="shrooms")
    crew = hunt.HuntState([Unit("player") for _ in range(3)], None, hours_left=4, target="shrooms")
    hunt.hunt_stretch(solo, Always())
    hunt.hunt_stretch(crew, Always())
    assert solo.fruit_found == 0 and crew.fruit_found == 4

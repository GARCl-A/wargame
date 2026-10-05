"""The Wilds encounter comparison script: it must keep running, and level 5 must
always be in the sweep."""

import importlib.util
import os

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "encounter_sim.py")


def _sim():
    spec = importlib.util.spec_from_file_location("encounter_sim", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_kind_finishes_a_level_5_battle_in_each_section():
    sim = _sim()
    for kind in sim.KINDS:
        wilds = sim._job(("wilds", 1, ("wilds", 5, kind), (kind, 5, 4)))
        scaling = sim._job(("scaling", 2, ("scaling", kind, 5), (kind, 5, 5, 4)))
        for _, res, _ in (wilds, scaling):
            assert not res["stuck"] and res["winner"] in ("player", "enemy")
    for a, b in (("Wolf", "Giant Spider"), ("Skeleton", "Bandit")):
        _, res, extra = sim._job(("h2h", 3, ("h2h", 5, a, b), (a, b, 5, True)))
        assert not res["stuck"] and extra["a_won"] in (True, False)


def test_the_sweep_always_includes_level_5():
    sim = _sim()
    jobs = sim.build_jobs(1, [0, 5], 4)
    tags = {j[2] for j in jobs}
    assert ("wilds", 5, "Wolf") in tags and ("scaling", "Skeleton", 5) in tags
    assert ("h2h", 5, "Wolf", "Bandit") in tags

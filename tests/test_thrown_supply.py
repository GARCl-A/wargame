"""How many spare throwing weapons are reasonable to carry: the most a thrower uses in a fight when its
pack never runs dry, against what the race study's thrower builds buy (`race_study_builds.THROWN_SPARES`)."""

import pytest

from scripts import race_study as rs
from scripts import race_study_builds as rb

FIGHTS = 24
THROWERS = {"javelin": "Shortspear", "knife": "Dagger"}


def _throws(weapon, level=5):
    """Throws each thrower made in a fight against a sword-and-shield squad, with a pack that outlasts the fight."""
    out = []
    for i in range(FIGHTS):
        job = rs._job("th", level, i, "Human", "thrower", "Human", "sword_board", fx=True, oa={"spares": 12, "weapon": weapon})
        out += [u["acts"].get("throw", 0) for u in rs.play(job)["units"] if u["s"] == "A"]
    return sorted(out)


@pytest.mark.balance
@pytest.mark.parametrize("build", THROWERS)
def test_the_spares_a_thrower_buys_cover_nine_fights_in_ten(build):
    used = _throws(THROWERS[build])
    p90 = used[int(len(used) * 0.9)]
    assert p90 <= rb.THROWN_SPARES, f"{build}: 90% of throwers throw up to {p90} times, they buy {rb.THROWN_SPARES} spares"


@pytest.mark.balance
@pytest.mark.parametrize("build", THROWERS)
def test_more_spares_than_the_cap_would_mostly_stay_in_the_pack(build):
    used = _throws(THROWERS[build])
    beyond = sum(1 for n in used if n > rb.THROWN_SPARES)
    assert beyond <= len(used) * 0.15


@pytest.mark.parametrize("build", THROWERS)
def test_a_thrower_carries_its_spares_unencumbered_at_level_5(build):
    import random
    unit, _ = rb.make_unit("player", "Human", "thrower", 5, random.Random(1), fixed=True, over={"weapon": THROWERS[build]})
    spares = sum(q for n, q in unit._base_inventory if n == unit.equipped_weapon)
    assert spares >= 1 and not unit.encumbered

import random

from gartok import names


def test_generated_names_are_short_and_never_stack_two_heavy_syllables():
    rng = random.Random(7)
    sample = [names.random_name(rng) for _ in range(2000)]
    assert max(map(len, sample)) <= names.MAX_LETTERS
    short = sum(len(n) <= 6 for n in sample)
    assert short > len(sample) * 0.4
    for n in sample:
        low = n.lower()
        assert sum(h in low for h in ("gorm", "throg", "skel")) < 2


def test_epithets_are_distinct_within_a_pack_and_restart_past_the_list():
    assert len(set(names.epithets(5))) == 5
    assert len(names.epithets(len(names.EPITHETS) + 3)) == len(names.EPITHETS) + 3

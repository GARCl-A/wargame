import random
import zlib

import pytest

from gartok import i18n, world


@pytest.fixture(autouse=True)
def _dice_seeded_by_the_test(request):
    """Each test rolls the same dice whatever ran before it, alone, serial or under xdist.
    crc32, not hash(): a str hash changes per process."""
    random.seed(zlib.crc32(request.node.nodeid.encode()))


@pytest.fixture(autouse=True)
def _no_ethereal_nodes_leak():
    """An event's nodes (`world.add_node`) live in the world module: take them off after each test."""
    yield
    world.clear_runtime()


@pytest.fixture(autouse=True)
def _english_text():
    """The text assertions are English: a test that picks a language puts it back."""
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: a real check that takes over a second (whole AI fights, sight, layout)")
    config.addinivalue_line("markers", "balance: a design number off a sim, not a bug check; run it (-m balance) "
                                       "with scripts/economy_report.py after touching wages, prices or loot")

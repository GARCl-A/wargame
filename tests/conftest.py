import pytest

from gartok import world


@pytest.fixture(autouse=True)
def _no_ethereal_nodes_leak():
    """An event's nodes (`world.add_node`) live in the world module: take them off after each test."""
    yield
    world.clear_runtime()


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: a real check that takes over a second (whole AI fights, sight, layout)")
    config.addinivalue_line("markers", "balance: a design number off a sim, not a bug check; run it (-m balance) "
                                       "with scripts/economy_report.py after touching wages, prices or loot")

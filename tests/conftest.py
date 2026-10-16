import pytest

from gartok import world


@pytest.fixture(autouse=True)
def _no_ethereal_nodes_leak():
    """An event's nodes (`world.add_node`) live in the world module: take them off after each test."""
    yield
    world.clear_runtime()

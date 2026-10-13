import pytest
from gartok import persist, world
from gartok.guild import Guild
from tests.helpers import Unit


def test_hidden_node_not_in_known_by_default():
    hidden_node = world.Node("secret_cave", "Secret Cave", "town", (0.5, 0.5), "A hidden cave.", hidden=True)
    orig_nodes = list(world.NODES)
    try:
        world.NODES.append(hidden_node)
        g = Guild([Unit("player")], node="city")
        known_ids = {n.id for n in world.known(g)}
        assert "secret_cave" not in known_ids
        assert not g.is_node_revealed("secret_cave")

        # Reveal node
        first = g.reveal_node("secret_cave")
        assert first is True
        assert g.is_node_revealed("secret_cave")
        assert "secret_cave" in {n.id for n in world.known(g)}

        # Second reveal is no-op
        second = g.reveal_node("secret_cave")
        assert second is False
    finally:
        world.NODES[:] = orig_nodes


def test_revealed_nodes_persistence():
    world_id = persist.new_world_id()
    g = Guild([Unit("player")], node="city")
    g.reveal_node("secret_sanctum")

    try:
        persist.save_game(world_id, g)
        loaded = persist.load_game(world_id)

        assert loaded.is_node_revealed("secret_sanctum")
        assert "secret_sanctum" in loaded.revealed
    finally:
        persist.delete_world(world_id)

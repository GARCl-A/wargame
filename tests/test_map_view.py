"""What the map shows of a band and its node (`map_view.py`): the reads both front-ends share, with no window."""

import subprocess
import sys

from gartok import orders, world
from gartok.group import Group
from gartok.guild import Guild
from gartok.map_view import position
from tests.helpers import standard_unit


def _guild(node_id):
    u = standard_unit()
    guild = Guild([u])
    guild.groups = [Group([u], node_id)]
    guild.house.owned = True
    return guild


def test_the_map_view_loads_without_pygame():
    code = "import sys; sys.modules['pygame'] = None; import gartok.map_view"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_a_walking_band_stands_part_way_along_its_leg():
    guild = _guild("city")
    g = guild.groups[0]
    assert position(g) == "city"
    dest = world.neighbors("city")[0][0]
    g.order = orders.travel(g, dest)
    g.order.remaining = g.order.eta * 0.4
    assert position(g) == ("city", dest, 0.6)

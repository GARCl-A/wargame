"""What the map shows of a band and its node (`map_view.py`): the reads both front-ends share, with no window."""

import subprocess
import sys

from gartok import orders, world
from gartok.group import Group
from gartok.guild import Guild
from gartok.map_inspector import TONE_COLORS
from gartok.map_screen import MapScreen
from gartok.map_view import position
from gartok.ui.tokens import T
from gartok.ui.tokens import fonts as ui_fonts
from gartok.web.map_session import MapSession
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


def test_the_blocks_carry_a_tone_and_no_colour():
    guild = _guild("city")
    blocks = MapSession(guild)._inspector_content(guild.groups[0], world.node("city"))
    tones = {b["tone"] for b in blocks if "tone" in b}
    assert tones and tones <= set(TONE_COLORS)
    assert not any("color" in b for b in blocks)


def test_both_maps_read_the_same_blocks_and_pygame_paints_the_tones():
    guild = _guild("city")
    g, here = guild.groups[0], world.node("city")
    ms = MapScreen(ui_fonts(), guild, lambda: None, lambda: None, lambda: None, lambda grp: None)
    assert ms._inspector_content(g, here) == MapSession(guild)._inspector_content(g, here)
    painted = ms._painted([{"type": "text", "text": "x", "tone": "bad"}, {"type": "button", "key": "k"}])
    assert painted[0]["color"] == T.BLOOD
    assert "color" not in painted[1]


def test_a_walking_band_stands_part_way_along_its_leg():
    guild = _guild("city")
    g = guild.groups[0]
    assert position(g) == "city"
    dest = world.neighbors("city")[0][0]
    g.order = orders.travel(g, dest)
    g.order.remaining = g.order.eta * 0.4
    assert position(g) == ("city", dest, 0.6)

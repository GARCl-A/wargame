"""Each place's floor on the battle board (`ui/floors.py`): what paints it and who picks it."""

from gartok import world
from gartok.scenario import (
    WildsScenario,
    scenario_for,
)

def test_a_road_fights_on_packed_earth_and_the_city_on_cobbles():
    assert scenario_for(world.node("road")).floor == "earth"
    assert scenario_for(world.node("country_roads")).floor == "earth"
    assert scenario_for(world.node("prison")).floor == "cobble"
    assert scenario_for(world.node("wilds")).floor == "grass"
    assert WildsScenario().floor == "grass"                  # the road's floor rides on its own copy

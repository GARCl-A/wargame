"""A wagon left outside: the squad selector for the Ancient Ruins and a Wilds hunt,
the risk it shows, and the one silent roll when the party comes back out."""


from gartok import data, wagon_watch, world
from gartok.animals import Animal
from gartok.group import Group
from gartok.wagon import Wagon
from tests.helpers import Unit


class _Roll:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


def _group(species=("Donkey",), members=2, wagons=1):
    g = Group([Unit("player") for _ in range(members)], node="ancient_ruins",
              wagons=[Wagon() for _ in range(wagons)], herd=[Animal(s) for s in species])
    return g


def test_flight_chances_live_in_the_beast_table():
    assert [data.race_by_name(s)["flight"] for s in ("Donkey", "Horse", "Ox")] == [0.05, 0.10, 0.15]
    assert data.race_by_name("Wolf")["flight"] == 0.0


def test_the_flightiest_animal_sets_the_chance():
    assert wagon_watch.flight_chance(_group(("Donkey", "Ox"))) == 0.15
    assert wagon_watch.flight_chance(_group(())) == 0.0


def test_the_ruins_add_the_old_roads_chance_to_the_animals_and_the_wilds_do_not():
    g = _group(("Horse",))
    assert wagon_watch.risk(g, world.node("ancient_ruins")) == world.ROAD_AMBUSH_CHANCE + 0.10
    assert wagon_watch.risk(g, world.node("wilds")) == 0.10


def test_only_a_group_with_a_wagon_needs_a_watch():
    assert wagon_watch.needs_watch(_group())
    assert not wagon_watch.needs_watch(_group(wagons=0))


def test_an_unguarded_wagon_is_lost_with_its_cargo_and_animals_on_a_hit():
    g = _group(("Ox",))
    g.wagons[0].stash.put("Potato")
    node = world.node("wilds")
    assert wagon_watch.leave_outside(g, node, guarded=False, rng=_Roll(0.14))
    assert g.wagons == [] and g.herd == []


def test_an_unguarded_wagon_survives_a_miss():
    g = _group(("Ox",))
    assert not wagon_watch.leave_outside(g, world.node("wilds"), guarded=False, rng=_Roll(0.15))
    assert len(g.wagons) == 1 and len(g.herd) == 1


def test_a_guarded_wagon_is_never_lost():
    g = _group(("Ox",))
    assert not wagon_watch.leave_outside(g, world.node("ancient_ruins"), guarded=True, rng=_Roll(0.0))
    assert len(g.wagons) == 1

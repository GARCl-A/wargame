"""The Stables (animals and tack) and the Carpenter's wagon yard, paid with the party's coin."""

from gartok import animals, data, economy, items, orders, wagon, world
from gartok.group import HERD_BASE, Group
from gartok.guild import Guild
from gartok.web.hub_session import tabs_for
from gartok.web.stable_tab import StableTab, WagonTab
from tests.helpers import Unit


def _stables(coins, w=None, pets=(), wis=0, tab=StableTab):
    a, b = Unit("player"), Unit("player")
    a.money, b.money = coins, 0
    a.mod_wisdom = b.mod_wisdom = wis
    g = Group([a, b], node="farm", wagons=[w] if w else [], herd=list(pets))
    guild = Guild(None, groups=[g])
    return tab(guild, g, world.node("farm")), g, a


def _yard(coins, w=None, pets=()):
    return _stables(coins, w, pets, tab=WagonTab)


def _keys(scr):
    """What the tab offers now, as `verb:arg` keys."""
    st = scr.state()
    if isinstance(scr, WagonTab):
        return ({f"buy_wagon:{k}" for k, o in zip(wagon.VEHICLES, st["offers"]) if o["can"]}
                | {f"sell_wagon:{i}" for i, w in enumerate(st["wagons"]) if not w["loaded"]})
    return ({f"buy:{o['name']}" for o in st["offers"] if o["can"]}
            | {f"fit:{i}:{f['tack']}" for i, a in enumerate(st["herd"]) for f in a["fits"] if f["can"]}
            | {f"sell:{i}" for i in range(len(st["herd"]))})


def _click(scr, key):
    verb, _, arg = key.partition(":")
    g = scr.group
    try:
        if verb == "buy_wagon":
            scr.buy(arg)
        elif verb == "sell_wagon":
            scr.sell(g.wagons[int(arg)].uid)
        elif verb == "buy":
            scr.buy(arg)
        elif verb == "fit":
            i, tack = arg.split(":", 1)
            scr.fit(g.herd[int(i)].uid, tack)
        elif verb == "sell":
            scr.sell(g.herd[int(arg)].uid)
    except ValueError:
        pass


def test_the_stables_are_on_the_farm_outside_the_city_and_the_map_can_send_a_group_there():
    assert world.node("farm").has("stable") and not world.node("city").has("stable")
    path, hours = world.route("city", "farm")
    assert path == ["city", "farm"] and hours > 0
    assert world.node("farm").jurisdiction is None
    assert "stable" in orders.INTERACTIVE_KINDS


def test_wagons_are_sold_at_the_carpenter_and_no_longer_at_the_stables():
    scr, _, _ = _stables(10_000, wagon.Wagon())
    assert not any(k.startswith(("buy_wagon", "sell_wagon")) for k in _keys(scr))

    def tabs(node_id):
        return [k for k, _ in tabs_for("market", world.node(node_id))]
    assert "wagons" not in tabs("farm") and "stable" in tabs("farm")
    assert "wagons" in tabs("carpenter")


def test_buying_the_wagon_takes_the_coin_and_gives_the_group_a_wagon():
    scr, g, a = _yard(wagon.VEHICLES["Cart"].price + 7)
    assert "buy_wagon:Cart" in _keys(scr)
    _click(scr, "buy_wagon:Cart")
    assert len(g.wagons) == 1 and a.money == 7 and g.wagons[0]._group is g


def test_the_wagon_is_refused_when_the_party_cannot_pay():
    scr, g, _ = _yard(wagon.VEHICLES["Cart"].price - 1)
    assert "buy_wagon:Cart" not in _keys(scr)
    _click(scr, "buy_wagon:Cart")
    assert g.wagons == []


def test_an_animal_is_bought_with_no_tack_and_no_wagon_needed():
    scr, g, a = _stables(1000)
    _click(scr, "buy:Donkey")
    assert [x.species for x in g.herd] == ["Donkey"] and g.herd[0].tack is None
    assert a.money == 1000 - animals.PRICE["Donkey"]


def test_the_group_cannot_keep_a_herd_beyond_its_leaders_control():
    scr, g, a = _stables(10_000, pets=[animals.Animal("Donkey") for _ in range(HERD_BASE)])
    assert not any(k.startswith("buy:") for k in _keys(scr))
    _click(scr, "buy:Ox")
    assert len(g.herd) == HERD_BASE and a.money == 10_000


def test_a_wise_leader_can_buy_more_animals():
    scr, g, _ = _stables(10_000, pets=[animals.Animal("Donkey") for _ in range(HERD_BASE)], wis=2)
    assert "buy:Ox" in _keys(scr)
    _click(scr, "buy:Ox")
    assert len(g.herd) == HERD_BASE + 1


def test_tack_is_bought_onto_the_animal_and_decides_its_role():
    scr, g, a = _stables(1000, pets=[animals.Animal("Donkey")])
    _click(scr, f"fit:0:{animals.HARNESS}")
    assert g.herd[0].role == "draft" and a.money == 1000 - items.get(animals.HARNESS).price
    assert not any(k.startswith("fit:") for k in _keys(scr))


def test_an_animal_wears_only_one_set_of_tack():
    scr, g, a = _stables(1000, pets=[animals.Animal("Donkey", tack=animals.PACK_SADDLE)])
    _click(scr, f"fit:0:{animals.HARNESS}")
    assert g.herd[0].tack == animals.PACK_SADDLE and a.money == 1000


def test_tack_that_cannot_be_afforded_is_not_offered():
    scr, g, _ = _stables(items.get(animals.HARNESS).price - 1, pets=[animals.Animal("Donkey")])
    keys = _keys(scr)
    assert f"fit:0:{animals.HARNESS}" not in keys


def test_a_loaded_animal_has_to_be_unloaded_before_it_is_sold():
    pet = animals.Animal("Donkey", tack=animals.PACK_SADDLE)
    pet.stash.put("Rope")
    scr, g, _ = _stables(0, pets=[pet])
    _click(scr, "sell:0")
    assert g.herd == [pet] and pet.tack == animals.PACK_SADDLE
    assert "unload" in scr.notice


def test_selling_an_animal_pays_the_resale_and_keeps_the_tack():
    scr, g, _ = _stables(0, pets=[animals.Animal("Ox", tack=animals.HARNESS)])
    before = g.leader.money
    _click(scr, "sell:0")
    assert g.herd == []
    assert g.leader.money - before == int(animals.PRICE["Ox"] * economy.SELL_FACTOR)
    assert g.leader.count_of(animals.HARNESS) == 1


def test_the_wagon_can_only_be_sold_empty():
    w = wagon.Wagon()
    w.stash.items.append(items.create_instance("Rope"))
    scr, g, _ = _yard(0, w)
    _click(scr, "sell_wagon:0")
    assert g.wagons

    g.wagons[0].stash.items.clear()
    assert "sell_wagon:0" in _keys(scr)
    _click(scr, "sell_wagon:0")
    assert g.wagons == []


def test_the_tabs_answer_in_every_state():
    pets = [animals.Animal("Donkey", tack=animals.HARNESS), animals.Animal("Ox"),
            animals.Animal("Donkey", tack=animals.PACK_SADDLE)]
    for w, p in ((None, ()), (wagon.Wagon(), ()), (wagon.Wagon(), pets), (None, pets)):
        for tab in (StableTab, WagonTab):
            scr, _, _ = _stables(500, w, p, tab=tab)
            _keys(scr)


def test_a_carriage_is_bought_beside_a_cart():
    scr, g, a = _yard(10_000, wagon.Wagon())
    assert {"buy_wagon:Cart", "buy_wagon:Carriage"} <= _keys(scr)
    _click(scr, "buy_wagon:Carriage")
    assert [w.kind for w in g.wagons] == ["Cart", "Carriage"]
    assert a.money == 10_000 - wagon.VEHICLES["Carriage"].price


def test_a_new_wagon_takes_the_idle_harnessed_animal():
    pet = animals.Animal("Ox", tack=animals.HARNESS)
    scr, g, _ = _yard(1000, pets=[pet])
    _click(scr, "buy_wagon:Cart")
    assert g.pulling(pet) is g.wagons[0]


def test_selling_a_wagon_pays_its_own_price_and_frees_its_animals():
    pet = animals.Animal("Ox", tack=animals.HARNESS)
    scr, g, _ = _yard(0, wagon.Wagon("Carriage"), pets=[pet])
    g.hitch_idle()
    _click(scr, "sell_wagon:0")
    assert g.wagons == [] and pet.hitch is None
    assert g.leader.money == int(wagon.VEHICLES["Carriage"].price * economy.SELL_FACTOR)


def test_every_species_is_for_sale_with_its_loads():
    scr, _, a = _stables(10_000)
    assert {f"buy:{s}" for s in data.LIVESTOCK} <= _keys(scr)
    _click(scr, "buy:Horse")
    assert scr.group.herd[0].species == "Horse" and a.money == 10_000 - animals.PRICE["Horse"]


def test_walking_beside_the_wagon_survives_a_save():
    from gartok import persist
    u = Unit("player")
    u.afoot = True
    assert Unit.from_save(persist.unit_to_dict(u)).afoot is True

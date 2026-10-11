from gartok import economy, gather, items, sources


def test_every_base_material_declares_a_source():
    bare = [n for n in sources.base_materials() if not sources.sources_of(n)]
    assert bare == []


def test_a_crafted_item_is_not_a_base_material():
    base = sources.base_materials()
    assert "Jerky" not in base and "Minor Healing Potion" not in base
    assert {"Lumber", "Meat", "Iron Ore", "Semi-precious Gemstone"} <= set(base)


def test_everything_gathered_is_a_base_material():
    base = set(sources.base_materials())
    assert {n for table in gather.TABLES.values() for n, _ in table} <= base


def test_the_declared_sources_name_real_base_materials():
    assert set(sources.DECLARED) <= set(sources.base_materials())


def test_a_traded_material_is_on_a_shelf():
    shelved = set(economy.MARKET_STOCK) | set(economy.LIBRARY_SUPPLIES)
    traded = [n for n in sources.base_materials()
              if any(s.kind == sources.TRADED for s in sources.sources_of(n))]
    assert traded and all(n in shelved for n in traded)


def test_a_beast_drop_is_found_from_the_beast_table():
    assert sources.Source(sources.DROPPED, "Giant Spider") in sources.sources_of("Venom Gland")
    assert items.get("Venom Gland") is not None

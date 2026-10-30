from gartok import persist, unit

def test_portrait_id_survives_a_save_round_trip():
    u = unit.Unit("player")
    v = unit.Unit.from_save(persist.unit_to_dict(u))
    assert v.portrait_id == u.portrait_id


def test_the_prison_tab_carries_the_units_portrait():
    from gartok import world
    from gartok.guild import Guild
    from gartok.web.shop_tab import _portrait
    from gartok.web.tavern_tab import TavernTab

    u = unit.Unit("player")
    guild = Guild([u], node="prison")
    tab = TavernTab(guild, guild.groups[0], world.node("prison"), prison=True)
    pitchers = tab.state("recruits")["dossier"]["pitchers"]
    assert [p["portrait"] for p in pitchers] == [_portrait(u)] and _portrait(u)


def test_portrait_file_survives_save_round_trip():
    u = unit.Unit("player")
    u.portrait_file = "adelio.png"
    u.portrait_id = "adelio.png"
    saved = persist.unit_to_dict(u)
    assert saved["portrait_file"] == "adelio.png"
    v = unit.Unit.from_save(saved)
    assert v.portrait_file == "adelio.png"
    assert v.portrait_id == "adelio.png"

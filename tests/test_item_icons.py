
def test_every_catalogue_item_has_an_icon_of_its_own():
    from gartok import item_icon, items
    bare = [n for n in items.all_items() if item_icon._base(n) not in item_icon.ICONS]
    assert not bare, f"add these to item_icon.ICONS: {bare}"


def test_sizes_scrolls_and_dictionaries_share_one_icon_and_an_unknown_item_still_draws():
    from gartok import item_icon
    assert item_icon.icon_spec("Large Axe")[::3] == item_icon.icon_spec("Axe")[::3]
    assert item_icon.icon_spec("Scroll of Sleep")[:2] == item_icon.icon_spec("Scroll")[:2]
    assert item_icon.icon_spec("Dictionary of Elvish")[:2] == item_icon.icon_spec("Dictionary")[:2]
    assert item_icon.icon_spec("Meat (3 days old)")[0] == "steak"
    assert item_icon.icon_spec("Nothing Of The Kind")[0] == "coin"


def test_a_mission_goal_of_any_dictionary_draws_the_dictionary_icon():
    from gartok import item_icon
    any_one, plain = item_icon.icon_spec("Any Dictionary"), item_icon.icon_spec("Dictionary of Ankarin")
    assert (any_one[0], any_one[1], any_one[4]) == (plain[0], plain[1], plain[4])


def test_every_item_kind_has_a_glyph_file_for_the_web_client():
    import os

    from gartok import item_icon, items
    from gartok.web.session import ASSETS
    root = os.path.join(ASSETS, "icons")
    glyphs = {item_icon.glyph(n) for n in items.all_items()}
    glyphs |= {"item/" + g for g in (*item_icon.GLYPHS.values(), *item_icon.HEAD_GLYPHS.values(),
                                     *item_icon.STYLE_GLYPHS.values())}
    missing = [g for g in glyphs if not os.path.isfile(os.path.join(root, g + ".svg"))]
    assert not missing, f"fetch these from game-icons.net into assets/icons/: {missing}"
    assert {kind for kind, _m, _s in item_icon.ICONS.values()} <= set(item_icon.GLYPHS) | {"hafted"}

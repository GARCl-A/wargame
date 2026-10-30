"""The client's kit: the pieces two or more screens draw live once (`kit.js`, `kit.css`), and every hover
is the game's own tooltip, never the browser's `title`."""

import os
import re

from gartok.web.map_session import MapSession
from tests.helpers import packed, standard_unit

CLIENT = os.path.join(os.path.dirname(__file__), "..", "gartok", "web", "client")


def _read(path):
    with open(os.path.join(CLIENT, path), encoding="utf-8") as f:
        return f.read()


def _sources():
    for root, _, files in os.walk(CLIENT):
        for name in files:
            if name.endswith((".js", ".html")):
                path = os.path.relpath(os.path.join(root, name), CLIENT).replace(os.sep, "/")
                yield path, _read(path)


def test_no_hover_is_the_browsers_title():
    for path, src in _sources():
        src = src.replace("<title>GARTOK Tactical</title>", "")
        assert not re.search(r"\btitle=|\.title\s*=[^=]", src), path


def test_the_shared_pieces_are_declared_once_in_the_kit():
    shared = ("ico", "money", "plural", "sign", "kg", "tip", "stagePoint", "popAt", "dropMarker")
    kit = _read("kit.js")
    for name in shared:
        assert re.search(rf"^(?:const|function) {name}\b", kit, re.M), name
    for path, src in _sources():
        if path == "kit.js":
            continue
        for name in shared:
            assert not re.search(rf"^\s*(?:const|let|function) {name}\b", src, re.M), (path, name)
    index = _read("index.html")
    assert index.index("/client/kit.js") < index.index("/client/shell.js") and "/client/kit.css" in index


def test_the_pack_columns_and_item_rows_come_from_the_kit():
    for path in ("screens/hub/shop.js", "screens/hub/vault.js"):
        src = _read(path)
        assert "Kit.column(" in src and "Kit.item(" in src and "Kit.purse(" in src and "Kit.stepper(" in src, path
        assert 'class="it ' not in src and "Distribute load" not in src, path
    bands = _read("screens/guild/bands.js")
    assert "Kit.item(" in bands and 'class="it ${' not in bands
    css = _read("kit.css")
    assert ".col.pack .chead" in css and "#tip{" in css and "#ghost{" in css
    for path in ("screens/hub/hub.css", "screens/guild/guild.css"):
        assert "#ghost{" not in _read(path) and ".it .slotname" not in _read(path), path


def test_the_shop_the_sheet_and_the_alerts_hover_with_the_tooltip():
    assert '${tip(r.tip, "item")}' in _read("screens/hub/shop.js")
    assert 'tip(it.tip, "item")' in _read("kit.js")
    shell = _read("shell.js")
    assert '${tip(u.hp_tip, "sum")}' in shell and '${tip(s.tip, "sum")}' in shell
    assert "<small>" not in re.search(r'\$\("alerts"\)\.innerHTML = .*', _read("screens/map/map.js")).group(0)


def test_the_food_alert_says_only_low_on_food_and_tells_the_rest_on_hover():
    from gartok.guild import Guild
    crew = [standard_unit() for _ in range(2)]
    for u in crew:
        u._base_inventory = packed(["Potato"])
    (alert,) = MapSession(Guild(crew, node="city"), None)._alerts()
    assert alert["title"] == "LOW ON FOOD"
    assert "2 meals left for 2 members" in alert["text"]
    for u in crew:
        u._base_inventory = packed([])
        u.unfed_days = 1
    (alert,) = MapSession(Guild(crew, node="city"), None)._alerts()
    assert alert["title"] == "STARVING" and "2 members hungry" in alert["text"] and "dies in" in alert["text"]

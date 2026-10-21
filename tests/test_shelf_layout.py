"""The hub shelf keeps its rows' controls inside them and scrolls when long; the quantity box keeps
its amount clear of its buttons; the load menu summarises a guild's squad by count."""

import pygame

from gartok.ui import shop_shelf
from gartok.ui.loadout_panel import quantity_prompt
from gartok.ui.tokens import fonts as ui_fonts


def _row(name="Musical Instrument", price=4, base=4, stock=30, tag="light"):
    return {"name": name, "base_name": name, "spec": "", "price": price, "base_price": base,
            "weight": 2.0, "stock": stock, "afford": True, "fits": True, "sel": False,
            "tag": tag, "qty": 1, "size": None}


def _shelf(rows, kind="kit"):
    pygame.init()
    surf = pygame.Surface((1920, 1080))
    data = {"kind": kind, "all_size": None, "rows": rows, "cats": [("Consumables & kit", "kit")], "cat": "kit",
            "foot": {"left": "Auto-sell · mark a kind", "button": "sell marked", "enabled": False}}
    return shop_shelf.draw_shelf(surf, ui_fonts(), pygame.Rect(40, 0, 540, 700), data, (0, 0))


def test_a_shelf_row_keeps_its_stepper_inside_it():
    out = _shelf([_row(price=27, base=30, stock=0)])
    assert len(out["rows"]) == 1 and len(out["qty_hits"]) == 2
    for r, _, _ in out["qty_hits"]:
        assert out["rows"][0][0].contains(r)


def test_a_long_shelf_scrolls_instead_of_running_into_the_footer():
    out = _shelf([_row(name=f"Item {i}") for i in range(30)], kind="weapons")
    assert out["max_scroll"] > 0
    assert all(r.bottom <= out["list"].bottom for r, _ in out["rows"])
    assert out["button"] is None                    # nothing marked: the auto-sell is off


def test_the_quantity_box_keeps_the_amount_clear_of_its_buttons():
    pygame.init()
    surf = pygame.Surface((640, 480))
    res = quantity_prompt(surf, ui_fonts(), (320, 240), "mint gold coins", 12, 40, "PAY $1,212", (0, 0))
    (minus, _), (plus, _), (confirm, _) = res["hits"]
    amount = ui_fonts()["bodyb"].size("12 / 40")
    assert minus.right < 320 - amount[0] // 2 and plus.left > 320 + amount[0] // 2
    assert confirm.top > minus.bottom and res["rect"].contains(confirm)


def test_a_world_card_shows_the_member_count_not_their_names(monkeypatch):
    from gartok import persist
    from gartok.menu_screen import MenuScreen

    world = {"world": "w1", "name": "G" * 80, "squad": ["Aaaa Bbbb", "Cccc Dddd", "Eeee Ffff"],
             "battles_won": 2, "saves": 1, "saved_at": 0}
    monkeypatch.setattr(persist, "list_worlds", lambda: [world])
    pygame.init()
    screen = MenuScreen(ui_fonts(), *[lambda *a: None] * 4)
    shown = []
    import gartok.menu_screen as menu_module
    real = menu_module.text
    monkeypatch.setattr(menu_module, "text", lambda s, f, t, *a, **k: shown.append(t) or real(s, f, t, *a, **k))
    screen.mouse = (0, 0)
    screen.draw(pygame.Surface((1024, 640)))
    assert "3 members" in shown and not any("Aaaa" in str(t) for t in shown)
    assert all(ui_fonts()["bodyb"].size(t)[0] < 1024 for t in shown if isinstance(t, str) and t.startswith("G"))

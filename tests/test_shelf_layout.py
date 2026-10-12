"""The market shelf and the quantity box lay their columns out from what the rows hold, so
neighbours never land on each other; the load menu summarises a guild's squad by count."""

import pygame

from gartok.ui import market_panel
from gartok.ui.loadout_panel import quantity_prompt
from gartok.ui.tokens import T
from gartok.ui.tokens import fonts as ui_fonts


def _row(name="Musical Instrument", price=4, base=4, stock=30, tag="light"):
    return {"name": name, "base_name": name, "spec": "", "price": price, "base_price": base,
            "weight": 2.0, "stock": stock, "afford": True, "fits": True, "sel": False,
            "tag": tag, "qty": 1, "size": None}


def test_each_column_sits_left_of_the_next_whatever_the_rows_hold():
    pygame.init()
    F = ui_fonts()
    wt_x = 380
    for kit, weapons in ((True, False), (False, True), (False, False)):
        rows = [_row(price=12345, base=99999, stock=0), _row(tag="material")]
        c = market_panel._columns(F, 16, wt_x, rows, kit, weapons)
        ctl_w = market_panel._STEPPER_W if kit else market_panel._SIZE_W if weapons else 0
        assert c["name_right"] <= c["ctl_x"] - T.S + (T.S if not ctl_w else 0)
        assert c["ctl_x"] + ctl_w <= c["tag_x"]
        assert c["tag_x"] < c["price_x"] - F["body"].size("$12,345")[0] < wt_x
        assert c["name_right"] > 16 + 40            # the name keeps some room


def test_the_shelf_draws_a_row_with_a_was_price_and_a_sold_out_tag_inside_its_panel():
    pygame.init()
    F = ui_fonts()
    surf = pygame.Surface((520, 300))
    rect = pygame.Rect(8, 8, 412, 280)
    data = {"kind": "kit", "all_size": None, "hover": False, "rows": [_row(price=27, base=30, stock=0)]}
    out = market_panel.stock_list(surf, F, rect, data, (0, 0))
    assert len(out["rows"]) == 1 and len(out["qty_hits"]) == 2
    for r, _, _ in out["qty_hits"]:
        assert out["rows"][0][0].contains(r)


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

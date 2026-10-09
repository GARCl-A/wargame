"""Tests for the founding draft: a pool of nine, pick three, and the commission tokens."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from gartok import archetypes
from gartok.draft_screen import (
    COMMISSION_TOKENS,
    POOL_SIZE,
    TEAM_SIZE,
    DraftScreen,
)
from gartok.ui.tokens import fonts as ui_fonts
from gartok.unit import Unit

SIZE = (1280, 800)


def _screen(on_done=lambda *args: None):
    pygame.init()
    ds = DraftScreen(ui_fonts(), on_done)
    surf = pygame.Surface(SIZE)
    ds.draw(surf)
    return ds, surf


def _commission(ds, surf, labels, target):
    ds._click(ds.commission_btn_rect.center)
    ds.draw(surf)
    for rect, key, _can in ds.modal_item_rects:
        if key in labels:
            ds._click(rect.center)
    ds.draw(surf)
    ds._click(ds.modal_confirm_rect.center)
    ds.draw(surf)
    ds._click(next(r for r, u in ds.card_rects if u is target).center)
    ds.draw(surf)


def test_archetype_catalog_completeness():
    assert len(archetypes.ARCHETYPES) == 7
    for key, arc in archetypes.ARCHETYPES.items():
        assert arc.key == key
        assert arc.label
        assert arc.desc
        assert callable(arc.predicate)


def test_archetype_compatibility_rules():
    assert archetypes.is_compatible(["LEADER"], "TOUGH") is True
    assert archetypes.is_compatible(["STRONG"], "LEADER") is True
    assert archetypes.is_compatible(["LEADER"], "LEADER") is False


def test_generate_candidate_satisfies_requested_labels():
    assert archetypes.generate_candidate(["LEADER"]).mod_charisma >= 2
    assert archetypes.generate_candidate(["STRONG"]).mod_strength >= 2
    u_both = archetypes.generate_candidate(["LEADER", "TOUGH"])
    assert u_both.mod_charisma >= 2
    assert u_both.hp_max >= 8


def test_draft_starts_with_a_pool_of_nine_and_three_tokens():
    ds, _ = _screen()
    assert POOL_SIZE == 9 and TEAM_SIZE == 3
    assert len(ds.pool) == POOL_SIZE
    assert ds.tokens == COMMISSION_TOKENS == 3
    assert ds.picks == [] and ds.phase == "pick"


def test_picking_toggles_and_caps_at_three():
    ds, _ = _screen()
    units = ds.pool[:4]
    for u in units[:3]:
        ds._toggle_pick(u)
    ds._toggle_pick(units[3])
    assert ds.picks == units[:3]
    ds._toggle_pick(units[0])
    assert ds.picks == units[1:3]
    ds._toggle_pick(units[3])
    assert ds.picks == [units[1], units[2], units[3]]


def test_continue_needs_three_picks_then_opens_identity():
    ds, surf = _screen()
    for rect, _u in ds.card_rects[:2]:
        ds._click(rect.center)
    ds.draw(surf)
    ds._click(ds.continue_rect.center)
    assert ds.phase == "pick" and len(ds.picks) == 2
    ds._click(ds.card_rects[2][0].center)
    ds.draw(surf)
    ds._click(ds.continue_rect.center)
    assert ds.phase == "identity"


def test_scrolling_reaches_the_last_card_and_clicks_outside_the_view_are_ignored():
    ds, surf = _screen()
    assert ds.max_scroll > 0
    first_row_y = ds.card_rects[0][0].y
    ds.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=-50))
    assert ds.scroll == ds.max_scroll
    ds.draw(surf)
    assert ds.card_rects[0][0].y < first_row_y
    assert ds.card_rects[-1][1] is ds.pool[-1]
    ds._click((ds.pool_view.x + 2, ds.pool_view.bottom + 20))
    assert ds.picks == []


def test_commission_open_cancel_spends_nothing():
    ds, surf = _screen()
    ds._click(ds.commission_btn_rect.center)
    assert ds.commission_modal_open
    ds.draw(surf)
    assert len(ds.modal_item_rects) == 7
    ds._click(ds.modal_cancel_rect.center)
    assert not ds.commission_modal_open and ds.tokens == 3 and not ds.pending_labels


def test_commission_replaces_the_chosen_card_and_spends_tokens_then():
    ds, surf = _screen()
    target = ds.pool[4]
    ds.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=-50))
    ds.draw(surf)
    ds._click(ds.commission_btn_rect.center)
    ds.draw(surf)
    leader = next(r for r, k, _c in ds.modal_item_rects if k == "LEADER")
    ds._click(leader.center)
    ds.draw(surf)
    ds._click(ds.modal_confirm_rect.center)
    assert ds.pending_labels == ["LEADER"] and ds.tokens == 3
    ds.draw(surf)
    ds._click(next(r for r, u in ds.card_rects if u is target).center)

    assert ds.tokens == 2 and not ds.pending_labels
    fresh = ds.pool[4]
    assert fresh is not target and len(ds.pool) == POOL_SIZE
    assert fresh.mod_charisma >= 2
    assert ds.commissioned[id(fresh)] == ["LEADER"] and id(target) not in ds.commissioned
    ds.draw(surf)


def test_commission_target_mode_can_be_cancelled_for_free():
    ds, surf = _screen()
    ds._click(ds.commission_btn_rect.center)
    ds.draw(surf)
    ds._click(ds.modal_item_rects[0][0].center)
    ds.draw(surf)
    ds._click(ds.modal_confirm_rect.center)
    ds.draw(surf)
    assert ds.handle_escape() is True
    assert not ds.pending_labels and ds.tokens == 3
    assert ds.handle_escape() is False


def test_replacing_a_picked_card_drops_it_from_the_squad():
    ds, surf = _screen()
    target = ds.pool[0]
    ds._toggle_pick(target)
    ds._toggle_pick(ds.pool[1])
    _commission(ds, surf, ["STRONG"], target)
    assert target not in ds.picks and len(ds.picks) == 1
    assert ds.pool[0].mod_strength >= 2


def test_tokens_carry_across_commissions_and_run_out():
    ds, surf = _screen()
    _commission(ds, surf, ["STRONG"], ds.pool[0])
    assert ds.tokens == 2
    _commission(ds, surf, ["LEADER", "TOUGH"], ds.pool[1])
    assert ds.tokens == 0
    assert ds.pool[1].mod_charisma >= 2 and ds.pool[1].hp_max >= 8
    ds._click(ds.commission_btn_rect.center)
    assert not ds.commission_modal_open


def test_zero_tokens_disables_commission_button():
    ds, surf = _screen()
    ds.tokens = 0
    ds.draw(surf)
    ds._click(ds.commission_btn_rect.center)
    assert ds.commission_modal_open is False


def test_commission_cannot_exceed_remaining_tokens():
    ds, surf = _screen()
    ds.tokens = 1
    ds._click(ds.commission_btn_rect.center)
    ds.draw(surf)
    ds._click(ds.modal_item_rects[0][0].center)
    ds.draw(surf)
    ds._click(ds.modal_item_rects[1][0].center)
    assert len(ds.selected_modal_labels) == 1


def test_commission_archetypes_are_roles_not_a_race_picker():
    """A commission must leave the race open: for every archetype it takes at
    least four races to cover half of the candidates it can produce."""
    import random
    from collections import Counter
    random.seed(11)
    pool = [Unit("player") for _ in range(6000)]
    for key, arc in archetypes.ARCHETYPES.items():
        races = Counter(u.race["name"] for u in pool if arc.predicate(u))
        total, covered, needed = sum(races.values()), 0, 0
        for _, n in races.most_common():
            covered += n
            needed += 1
            if covered >= total / 2:
                break
        assert needed >= 3 and len(races) >= 10, (key, races.most_common(4))


def test_strong_is_about_strength_not_size():
    from tests.helpers import Unit
    u = Unit("player")
    u.set_base_attribute("strength", 20)
    assert archetypes.ARCHETYPES["STRONG"].predicate(u)
    u.set_base_attribute("strength", 6)
    assert not archetypes.ARCHETYPES["STRONG"].predicate(u)

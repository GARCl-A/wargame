"""Tests for the Recruit Commission with Label Tokens system in DraftScreen and archetypes.py."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from gartok import archetypes
from gartok.draft_screen import DraftScreen, COMMISSION_TOKENS, DRAFT_CHOICES, DRAFT_ROUNDS
from gartok.ui.tokens import fonts as ui_fonts
from gartok.unit import Unit


def test_archetype_catalog_completeness():
    assert len(archetypes.ARCHETYPES) == 12
    for key, arc in archetypes.ARCHETYPES.items():
        assert arc.key == key
        assert arc.label
        assert arc.desc
        assert callable(arc.predicate)


def test_archetype_compatibility_rules():
    assert archetypes.is_compatible(["LEADER"], "TOUGH") is True
    assert archetypes.is_compatible(["PACK MULE"], "DAMAGE DEALER") is True
    assert archetypes.is_compatible(["FAST"], "LARGE") is True

    # Incompatible pairs
    assert archetypes.is_compatible(["PACK MULE"], "SEES IN DARK") is False
    assert archetypes.is_compatible(["SEES IN DARK"], "PACK MULE") is False
    assert archetypes.is_compatible(["MAGIC"], "PACK MULE") is False
    assert archetypes.is_compatible(["FAST"], "SEES IN DARK") is False
    assert archetypes.is_compatible(["LARGE"], "MAGIC") is False

    # Cannot select same label twice
    assert archetypes.is_compatible(["LEADER"], "LEADER") is False


def test_generate_candidate_satisfies_requested_labels():
    # Single label: LEADER
    u_leader = archetypes.generate_candidate(["LEADER"])
    assert u_leader.mod_charisma >= 2

    # Single label: PACK MULE
    u_pack = archetypes.generate_candidate(["PACK MULE"])
    assert u_pack.carry_normal >= 35

    # Multi-label: LEADER + TOUGH
    u_both = archetypes.generate_candidate(["LEADER", "TOUGH"])
    assert u_both.mod_charisma >= 2
    assert u_both.hp_max >= 8


def test_draft_screen_initial_tokens_and_modal_state():
    pygame.init()
    F = ui_fonts()
    ds = DraftScreen(F, lambda *args: None)

    assert ds.tokens == COMMISSION_TOKENS
    assert ds.tokens == 3
    assert ds.commission_modal_open is False
    assert ds.selected_modal_labels == []
    assert len(ds.candidates) == DRAFT_CHOICES


def test_draft_screen_open_cancel_commission_modal():
    pygame.init()
    F = ui_fonts()
    ds = DraftScreen(F, lambda *args: None)
    surf = pygame.Surface((1280, 800))
    ds.draw(surf)

    # Click the commission button to open modal
    assert ds.commission_btn_rect is not None
    ds._click(ds.commission_btn_rect.center)
    assert ds.commission_modal_open is True

    # Draw to populate modal rects
    ds.draw(surf)
    assert ds.modal_cancel_rect is not None
    assert ds.modal_confirm_rect is not None
    assert len(ds.modal_item_rects) == 12

    # Click cancel closes modal with 0 tokens spent
    ds._click(ds.modal_cancel_rect.center)
    assert ds.commission_modal_open is False
    assert ds.tokens == 3


def test_draft_screen_commission_flow_deducts_tokens_and_guarantees_archetypes():
    pygame.init()
    F = ui_fonts()
    ds = DraftScreen(F, lambda *args: None)
    surf = pygame.Surface((1280, 800))
    ds.draw(surf)

    # Open modal
    ds._click(ds.commission_btn_rect.center)
    ds.draw(surf)

    # Find the LEADER chip in modal_item_rects
    leader_rect = None
    for rect, key, can_toggle in ds.modal_item_rects:
        if key == "LEADER":
            leader_rect = rect
            break
    assert leader_rect is not None

    # Click LEADER
    ds._click(leader_rect.center)
    assert "LEADER" in ds.selected_modal_labels

    # Confirm commission
    ds.draw(surf)
    ds._click(ds.modal_confirm_rect.center)

    assert ds.commission_modal_open is False
    assert ds.tokens == 2  # 3 - 1 = 2 tokens left
    assert ds.commissioned_labels == ["LEADER"]

    # All 3 candidates must satisfy LEADER
    for cand in ds.candidates:
        assert cand.mod_charisma >= 2

    # Draw screen and verify candidates have the ★ LEADER tag
    ds.draw(surf)
    first_cand = ds.candidates[0]
    tags = [t[0] for t in archetypes.unit_archetypes(first_cand)]
    assert "LEADER" in tags


def test_draft_screen_multi_round_token_persistence():
    pygame.init()
    F = ui_fonts()
    done_result = {}

    def on_done(picks, leader, name, banner_color, banner_icon):
        done_result.update(picks=picks, leader=leader, name=name)

    ds = DraftScreen(F, on_done)
    surf = pygame.Surface((1280, 800))
    ds.draw(surf)

    # Round 1: Commission 1 token on PACK MULE
    ds._click(ds.commission_btn_rect.center)
    ds.draw(surf)
    for rect, key, can_toggle in ds.modal_item_rects:
        if key == "PACK MULE":
            ds._click(rect.center)
            break
    ds.draw(surf)
    ds._click(ds.modal_confirm_rect.center)
    assert ds.tokens == 2

    # Pick candidate 0
    pick_rect, picked_unit = ds.card_rects[0]
    ds._click(pick_rect.center)
    assert len(ds.picks) == 1
    assert ds.commissioned_labels == []  # Reset for round 2

    # Round 2: Pick directly without spending tokens
    assert ds.tokens == 2  # Tokens carried over!
    ds.draw(surf)
    pick_rect, _ = ds.card_rects[1]
    ds._click(pick_rect.center)
    assert len(ds.picks) == 2

    # Round 3: Commission 2 tokens on LEADER + TOUGH
    assert ds.tokens == 2
    ds.draw(surf)
    ds._click(ds.commission_btn_rect.center)
    ds.draw(surf)
    for rect, key, can_toggle in ds.modal_item_rects:
        if key in ("LEADER", "TOUGH"):
            ds._click(rect.center)
    ds.draw(surf)
    ds._click(ds.modal_confirm_rect.center)
    assert ds.tokens == 0

    # Pick candidate 2
    ds.draw(surf)
    pick_rect, _ = ds.card_rects[2]
    ds._click(pick_rect.center)

    # Phase should now be identity
    assert len(ds.picks) == 3
    assert ds.phase == "identity"


def test_draft_screen_zero_tokens_disables_commission_button():
    pygame.init()
    F = ui_fonts()
    ds = DraftScreen(F, lambda *args: None)
    ds.tokens = 0
    surf = pygame.Surface((1280, 800))
    ds.draw(surf)

    # Click on disabled commission button should not open modal
    ds._click(ds.commission_btn_rect.center)
    assert ds.commission_modal_open is False

"""A centred, veiled card: a title, a few serif paragraphs and one button --
the tutorial's "read this once" card.

`draw_intro_card(surf, F, title, paragraphs, button_label, mpos)` takes plain
strings; it sizes itself from the surface (proportional with a clamp) and
returns `(card_rect, button_rect)` for the caller's hit-testing. `note` is an
optional closing line in brass (a "look here next" pointer).
"""

import pygame

from .primitives import hline, panel, text, wrap, draw_button
from .tokens import T

_MIN_W, _MAX_W = 520, 780
_SIZES = (("name", 22), ("body", 18))      # (font key, line height): the second when the first won't fit
_BUTTON = (160, 36)


def _layout(F, w, paragraphs, note, font_key, line_h):
    pad = T.S * 4
    inner = w - 2 * pad
    blocks = [wrap(F[font_key], p, inner) for p in paragraphs]
    note_lines = wrap(F[font_key], note, inner) if note else []
    body_h = sum(len(b) * line_h for b in blocks) + T.S * 2 * (len(blocks) - 1)
    if note_lines:
        body_h += T.S * 2 + len(note_lines) * line_h
    title_h = T.S * 5
    rule_h = T.S * 4
    h = pad + title_h + rule_h + body_h + T.S * 4 + _BUTTON[1] + pad
    return pad, blocks, note_lines, title_h, rule_h, h


def draw_intro_card(surf, F, title, paragraphs, button_label, mpos=(-1, -1), note=None):
    W, H = surf.get_size()
    w = int(min(max(W * 0.6, _MIN_W), _MAX_W, W - T.S * 4))
    for font_key, line_h in _SIZES:
        pad, blocks, note_lines, title_h, rule_h, h = _layout(
            F, w, paragraphs, note, font_key, line_h)
        if h <= H - T.S * 2:
            break
    inner = w - 2 * pad

    veil = pygame.Surface((W, H), pygame.SRCALPHA)
    veil.fill((6, 7, 12, 210))
    surf.blit(veil, (0, 0))

    rect = pygame.Rect(0, 0, w, min(h, H - T.S * 2))
    rect.center = (W // 2, H // 2)
    panel(surf, rect, hover=True)
    pygame.draw.rect(surf, T.BRASS_DIM, rect.inflate(-T.S * 2, -T.S * 2), 1)

    y = rect.y + pad
    text(surf, F["titleb"], title, (rect.centerx, y + title_h // 2), T.BRASS, center=True)
    y += title_h + T.S
    _rule(surf, rect.centerx, y, inner)
    y += rule_h - T.S

    for i, lines in enumerate(blocks):
        color = T.TX if i == 0 else T.TX_MUTED
        for ln in lines:
            text(surf, F[font_key], ln, (rect.x + pad, y), color)
            y += line_h
        y += T.S * 2
    for ln in note_lines:
        text(surf, F[font_key], ln, (rect.x + pad, y), T.BRASS)
        y += line_h

    button = pygame.Rect(0, 0, *_BUTTON)
    button.midbottom = (rect.centerx, rect.bottom - pad)
    draw_button(surf, F, button, button_label, primary=True, mpos=mpos)
    return rect, button


def _rule(surf, cx, y, width):
    half = width // 2
    gap = T.S * 2
    hline(surf, cx - half, cx - gap, y, T.BRASS_DIM)
    hline(surf, cx + gap, cx + half, y, T.BRASS_DIM)
    d = T.S // 2
    pygame.draw.polygon(surf, T.BRASS, [(cx, y - d), (cx + d, y), (cx, y + d), (cx - d, y)])

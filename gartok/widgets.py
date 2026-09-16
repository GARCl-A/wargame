"""Shared interactive components built on theme.py's primitives.

`theme.py` owns tokens and stateless drawing (colours, fonts, `panel`, `text`,
`token_badge`). This module owns the pieces that carry mouse/hit-test state --
buttons, the footer bar, the roster card, scrolling, and the full-screen modal
base -- so a screen composes these instead of hand-rolling its own hover/hit
logic. Every screen already carries `self.mouse` (`screen.Screen`) and
`self.fonts`; the widgets here read those two directly off the caller.
"""

import pygame

from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, RADIUS, SP3, SURFACE_1, SURFACE_2,
                    SURFACE_3, SURFACE_4, panel, set_pointer, text, token_badge)

FOOTER_H = 52
FOOTER_NOTICE_DY = 22          # a notice/error line sits this far above the row
FOOTER_HINT = "Esc for the pause menu"

LEFT_W, PRIMARY_W, SECONDARY_W = 140, 220, 180


# --------------------------------------------------------------------------- #
# buttons                                                                      #
# --------------------------------------------------------------------------- #

def draw_button(surf, rect, label, fonts, mouse, *, enabled=True, primary=False,
                danger=False, font=None, fill_well=None, fill_raised=None,
                fill_hover=None, line=None, ink=None, ink_dim=None, ink_faint=None):
    """The one button look in the game: filled + accent on hover (always
    filled for `primary`), outlined otherwise, dimmed when disabled. Returns
    whether the mouse is hovering it -- always False when `enabled` is False,
    so callers can feed the result straight into `set_pointer`/`self._hot`
    without a separate `and enabled` check.

    `fill_well`/`fill_raised`/`fill_hover`/`line`/`ink`/`ink_dim`/`ink_faint`
    let a screen with its own surface ramp (e.g. map_screen's warm palette)
    recolour the neutral parts of the button without touching the shared
    accent/danger semantics -- default to the app's own cool ramp when left
    unset."""
    hov = enabled and rect.collidepoint(mouse)
    accent = DANGER if danger else ACCENT
    accent_ink = INK if danger else ACCENT_INK
    well = SURFACE_1 if fill_well is None else fill_well
    raised = SURFACE_3 if fill_raised is None else fill_raised
    hover = SURFACE_4 if fill_hover is None else fill_hover
    border_line = LINE_SOFT if line is None else line
    lbl_ink = INK if ink is None else ink
    lbl_ink_dim = INK_DIM if ink_dim is None else ink_dim
    lbl_ink_faint = INK_FAINT if ink_faint is None else ink_faint
    if not enabled:
        fill, border, txt_ink = well, border_line, lbl_ink_faint
    elif primary:
        fill = accent if hov else raised
        border = accent
        txt_ink = accent_ink if hov else accent
    else:
        fill = hover if hov else well
        border = accent if hov else border_line
        txt_ink = lbl_ink if hov else lbl_ink_dim
    panel(surf, rect, fill=fill, border=border, width=1, radius=RADIUS)
    text(surf, label, font or fonts.body_bd, txt_ink, rect.center, center=True)
    return hov


class ButtonsMixin:
    """`add_button` draws and registers a hit in one call; `buttons_hit` is the
    `_click` side. `self.buttons` stays a plain `[(key, rect)]` list -- several
    tests read it directly -- so a screen can still append to it by hand for
    anything `add_button` doesn't cover (e.g. a bespoke card that acts as its
    own button)."""

    def _reset_buttons(self):
        self.buttons = []
        self._hot = False

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False,
                   danger=False, font=None, fill_well=None, fill_raised=None,
                   fill_hover=None, line=None, ink=None, ink_dim=None, ink_faint=None):
        hov = draw_button(surf, rect, label, self.fonts, self.mouse,
                          enabled=enabled, primary=primary, danger=danger, font=font,
                          fill_well=fill_well, fill_raised=fill_raised,
                          fill_hover=fill_hover, line=line, ink=ink,
                          ink_dim=ink_dim, ink_faint=ink_faint)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or hov
        return hov

    def buttons_hit(self, pos):
        for key, rect in self.buttons:
            if rect.collidepoint(pos):
                return key
        return None


def _padded(item):
    """`(key, label)` or `(key, label, enabled)` -> always the 3-tuple."""
    return item if len(item) == 3 else (*item, True)


def footer_bar(screen_obj, surf, *, back=None, secondary=None, primary=None,
              notice=None, notice_color=INFO, hint=FOOTER_HINT, margin=None):
    """The bottom action row most activity screens share: an optional back
    button bottom-left, up to two confirm buttons stacked right-to-left
    (`primary` rightmost and filled, `secondary` beside it, both outlined
    otherwise), an optional notice line above the row, and the pause hint.
    Each slot is `(key, label)` or `(key, label, enabled)`; pass `hint=None`
    to a screen that already draws its own. Draws via `screen_obj.add_button`
    (requires `ButtonsMixin`)."""
    W, H = surf.get_size()
    m = margin if margin is not None else MARGIN
    y = H - FOOTER_H

    if notice:
        text(surf, notice, screen_obj.fonts.body_sm, notice_color, (m, y - FOOTER_NOTICE_DY))

    if back is not None:
        key, label, enabled = _padded(back)
        screen_obj.add_button(surf, pygame.Rect(m, y, LEFT_W, 36), key, label, enabled=enabled)

    rx = W - m
    if primary is not None:
        key, label, enabled = _padded(primary)
        rect = pygame.Rect(rx - PRIMARY_W, y, PRIMARY_W, 36)
        screen_obj.add_button(surf, rect, key, label, enabled=enabled, primary=True)
        rx = rect.x - SP3

    if secondary is not None:
        key, label, enabled = _padded(secondary)
        rect = pygame.Rect(rx - SECONDARY_W, y, SECONDARY_W, 36)
        screen_obj.add_button(surf, rect, key, label, enabled=enabled)
        rx = rect.x - SP3

    if hint:
        text(surf, hint, screen_obj.fonts.label, INK_FAINT, (m, y + 12))


# --------------------------------------------------------------------------- #
# full-screen modals                                                           #
# --------------------------------------------------------------------------- #

def draw_veil(surf, alpha=210):
    """The dark scrim every modal drops over the frozen scene behind it."""
    W, H = surf.get_size()
    veil = pygame.Surface((W, H), pygame.SRCALPHA)
    veil.fill((6, 7, 12, alpha))
    surf.blit(veil, (0, 0))


def draw_scene_behind(surf, resume_to, *, alpha=210):
    """Redraws `resume_to` frozen (cursor parked off-screen so it shows no
    hover) and veils it -- the shared backdrop for `PauseScreen`, `AlertScreen`
    and any other full-screen modal."""
    try:
        resume_to.mouse = (-1, -1)
        resume_to.draw(surf)
    except Exception:
        surf.fill(SURFACE_1)
    draw_veil(surf, alpha)


def modal_frame(rect, *, fill=SURFACE_2, border=ACCENT, width=2, radius=8):
    return {"fill": fill, "border": border, "width": width, "radius": radius}


class ModalScreen(ButtonsMixin):
    """Mix into a `Screen` subclass that covers the whole window over a frozen
    `resume_to`. Subclasses implement `card_rect(size) -> Rect`, `draw_body(surf,
    card)` (fill the card's inside and call `self.add_button(...)` for its
    controls) and `on_button(key)`. `draw`/`_click` are provided."""

    resume_to = None

    def draw(self, screen):
        self._reset_buttons()
        draw_scene_behind(screen, self.resume_to)
        card = self.card_rect(screen.get_size())
        panel(screen, card, fill=SURFACE_2, border=ACCENT, width=2, radius=8)
        self.draw_body(screen, card)
        set_pointer(self._hot)

    def _click(self, pos):
        key = self.buttons_hit(pos)
        if key is not None:
            self.on_button(key)


# --------------------------------------------------------------------------- #
# roster card                                                                  #
# --------------------------------------------------------------------------- #

def unit_card(surf, rect, unit, fonts, mouse, *, selected=False, disabled=False,
             lines=(), subtitle=None):
    """The compact roster card frame used on squad/guild/group/tavern screens:
    an emphasised panel, the unit's token + name, an optional subtitle line
    (race/occupation), then caller-supplied stat lines. `lines` is
    `[(text, color)]`, drawn in `fonts.mono_sm`/`body_sm` below the header --
    each screen keeps deciding *what* those lines say (HP/AC, hunger, price,
    ...); this only collapses the frame + header that were redrawn per-screen.
    Returns whether the mouse is over the card."""
    hov = rect.collidepoint(mouse)
    pad = SP3
    panel(surf, rect, fill=SURFACE_1 if disabled else SURFACE_2,
         border=DANGER if disabled else ACCENT if selected else (INFO if hov else LINE_SOFT),
         width=2 if (selected or hov or disabled) else 1, radius=RADIUS)

    tok = (rect.x + pad + 12, rect.y + pad + 12)
    token_badge(surf, tok, unit, fonts)
    text(surf, unit.name, fonts.card_name, INK, (tok[0] + 24, rect.y + pad))
    y = rect.y + pad + 20
    if subtitle:
        text(surf, subtitle, fonts.body_sm, INK_DIM, (tok[0] + 24, y))
        y = rect.y + pad + 44
    else:
        y = rect.y + pad + 40

    for line, color in lines:
        text(surf, line, fonts.mono_sm, color, (rect.x + pad, y))
        y += 17

    return hov


# --------------------------------------------------------------------------- #
# scroll                                                                       #
# --------------------------------------------------------------------------- #

class ScrollList:
    """Owns the scroll offset for a long vertical list: `handle_wheel` on
    `pygame.MOUSEWHEEL`, `clamp` after layout knows the content/view heights,
    and `draw_bar` for the track. Screens keep their own item layout -- this
    only owns the one clamped integer every one of them re-derived by hand."""

    def __init__(self, step=1):
        self.offset = 0
        self.step = step

    def handle_wheel(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self.offset -= event.y * self.step

    def clamp(self, item_count, visible_count):
        max_off = max(0, item_count - visible_count)
        self.offset = max(0, min(self.offset, max_off))
        return self.offset

    def draw_bar(self, surf, track_rect, item_count, visible_count):
        if item_count <= visible_count:
            return
        pygame.draw.rect(surf, SURFACE_1, track_rect, border_radius=3)
        span = max(18, track_rect.h * visible_count // item_count)
        top = track_rect.y + (track_rect.h - span) * self.offset // max(1, item_count - visible_count)
        bar = pygame.Rect(track_rect.x, top, track_rect.w, span)
        pygame.draw.rect(surf, SURFACE_4, bar, border_radius=3)

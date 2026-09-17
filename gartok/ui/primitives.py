"""Generic drawing primitives shared by every war-table panel: text
helpers, the one button style the whole screen uses, the `panel`/`modal_card`/
`draw_card` chrome every card and dialog sits on, and `contained` -- the
"this content lives inside that rect, period" clip scope."""

import contextlib

import pygame
from pygame import gfxdraw

from .. import artwork
from .. import theme as _theme
from .tokens import T, mix


@contextlib.contextmanager
def contained(surf, rect):
    """Clips drawing to `rect` for the scope of the `with` block, then
    restores whatever clip was in effect before -- a component that draws
    a card/panel wraps its own content in this so a height miscalculation
    crops instead of spilling into whatever sits next to it. A safety net,
    not a substitute for sizing the rect right in the first place."""
    prev = surf.get_clip()
    surf.set_clip(rect.clip(prev) if prev else rect)
    try:
        yield
    finally:
        surf.set_clip(prev)


def panel(surf, rect, hover=False, width=1):
    """The steel card every card/modal in this design sits on -- brass
    border and a lighter fill when `hover` is true, muted steel otherwise."""
    fill = T.STEEL_HI if hover else T.STEEL
    border = T.BRASS if hover else T.STEEL_LINE
    pygame.draw.rect(surf, fill, rect)
    pygame.draw.rect(surf, border, rect, width)


def modal_card(surf, size, veil=False):
    """Centers a `panel` of `size` on `surf`; with `veil` dims everything
    behind it first. Returns the card Rect for the caller to place content in."""
    W, H = surf.get_size()
    if veil:
        v = pygame.Surface((W, H), pygame.SRCALPHA)
        v.fill((6, 7, 12, 210))
        surf.blit(v, (0, 0))
    rect = pygame.Rect(0, 0, *size)
    rect.center = (W // 2, H // 2)
    panel(surf, rect)
    return rect


def draw_card(surf, F, rect, title, subtitle=None, hover=False, enabled=True, locked=False):
    """A selectable card: `panel` chrome plus a caps title and an optional
    muted subtitle -- the "pick one of a few big choices" pattern (menu
    slots, editor doors, and whatever else lands on a picker screen next)."""
    active = hover and enabled
    with contained(surf, rect):
        panel(surf, rect, hover=active)
        tcol = T.BRASS if active else (T.TX if enabled else T.TX_FAINT)
        caps(surf, F["head"], title, (rect.x + T.S * 3, rect.y + T.S * 2), tcol)
        if subtitle:
            text(surf, F["body_sm"], subtitle,
                 (rect.x + T.S * 3, rect.y + T.S * 2 + 26),
                 T.TX_MUTED if enabled else T.TX_FAINT)
        if locked:
            caps(surf, F["microb"], "LOCKED",
                 (rect.right - T.S * 3, rect.y + T.S * 2), T.TX_FAINT, right=True)


def text(surf, font, s, pos, color, right=False, center=False):
    img = font.render(s, True, color)
    r = img.get_rect()
    if right:
        r.topright = pos
    elif center:
        r.center = pos
    else:
        r.topleft = pos
    surf.blit(img, r)
    return r


def caps(surf, font, s, pos, color, **kw):
    return text(surf, font, s.upper(), pos, color, **kw)


def hline(surf, x1, x2, y, c=T.STEEL_LINE):
    pygame.draw.line(surf, c, (x1, y), (x2, y), 1)


def ellipsize(s, font, max_px):
    """`s` clipped with a trailing ellipsis so it renders within `max_px`."""
    if max_px <= 0 or font.size(s)[0] <= max_px:
        return s
    while s and font.size(s + "…")[0] > max_px:
        s = s[:-1]
    return s + "…"


def wrap(font, s, w):
    out, cur = [], ""
    for word in s.split():
        probe = (cur + " " + word).strip()
        if font.size(probe)[0] <= w:
            cur = probe
        else:
            out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out


def draw_button(surf, F, rect, label, sub=None, primary=False, danger=False,
                 ghost=False, enabled=True, mpos=(-1, -1), fnt=None):
    if not enabled:
        caps(surf, fnt or F["microb"], label, rect.center, T.TX_FAINT, center=True)
        pygame.draw.rect(surf, T.STEEL_LINE, rect, 1)
        return rect.bottom + T.S

    hover = rect.collidepoint(mpos)
    if primary:
        fill = T.BLOOD if danger else T.BRASS
        if hover:
            fill = mix(fill, (255, 255, 255), 0.25)
        pygame.draw.rect(surf, fill, rect)
        pygame.draw.rect(surf, mix(fill, (255, 255, 255), .25), rect, 1)
        fg = (255, 245, 235) if danger else T.TABLE
    else:
        bg = mix(T.TABLE, T.STEEL_LINE, 0.4) if hover else T.TABLE
        if hover:
            pygame.draw.rect(surf, bg, rect)
        pygame.draw.rect(surf, mix(T.STEEL_LINE, (255, 255, 255), 0.3) if hover
                         else T.STEEL_LINE, rect, 1)
        fg = T.TX_FAINT if ghost else T.TX_MUTED
        if hover and ghost:
            fg = T.TX_MUTED
        elif hover:
            fg = T.TX

    ly = rect.centery - (10 if sub else 0)
    caps(surf, fnt or F["microb"], label, (rect.centerx, ly), fg, center=True)
    if sub:
        text(surf, F["body"], sub, (rect.centerx, rect.centery + 10),
             mix(fg, T.TABLE, .25) if primary else T.TX_FAINT, center=True)
    return rect.bottom + T.S


def format_tooltip(title, description, F, max_px=260):
    """A tooltip's content: an accent title line + wrapped muted body --
    the shape `draw_tooltip` expects."""
    lines = [(title, F["microb"], T.BRASS)]
    for ln in wrap(F["body_sm"], description, max_px):
        lines.append((ln, F["body_sm"], T.TX_MUTED))
    return lines


def draw_tooltip(surf, F, content, pos):
    """Floating box near the mouse. `content` is a list of (text, font,
    color) tuples (see `format_tooltip`), or a plain string wrapped to a
    single muted style."""
    if not content:
        return
    if isinstance(content, str):
        content = [(ln, F["body_sm"], T.TX_MUTED) for ln in wrap(F["body_sm"], content, 260)]
    if not content:
        return
    pad = T.S * 2
    tw = max(fo.size(s)[0] for s, fo, _ in content) + 2 * pad
    th = 2 * pad + sum(fo.get_height() + 2 for _, fo, _ in content)
    W, H = surf.get_size()
    bx = min(pos[0] + 16, W - tw - T.S)
    by = min(pos[1] + 16, H - th - T.S)
    rect = pygame.Rect(bx, by, tw, th)
    panel(surf, rect)
    y = rect.y + pad
    for s, fo, c in content:
        text(surf, fo, s, (rect.x + pad, y), c)
        y += fo.get_height() + 2


def scrollbar(surf, rect, scroll, max_scroll, content_h):
    """A thin brass-on-steel track+thumb along `rect`'s right edge -- the
    same shape every scrollable list in this design uses (the caller only
    draws this when `max_scroll > 0`)."""
    sb_bg = pygame.Rect(rect.right - 4, rect.y, 4, rect.h)
    pygame.draw.rect(surf, T.STEEL_LINE, sb_bg)
    sb_h = max(20.0, rect.h * (rect.h / content_h))
    sb_y = rect.y + (rect.h - sb_h) * (scroll / max_scroll) if max_scroll else rect.y
    pygame.draw.rect(surf, T.BRASS, pygame.Rect(sb_bg.x, sb_y, 4, sb_h))


def tabs(surf, F, pos, items, active, mpos=(-1, -1), right=False):
    """A row of tab buttons -- `items` is a list of ids, drawn upper-cased.
    `right=True` lays them out leftward from `pos` (the row's right edge)
    instead of rightward from it. The active tab gets a brass underline."""
    x = pos[0]
    widths = [F["microb"].size(t.upper())[0] + T.S * 4 for t in items]
    if right:
        x -= sum(widths)
    rects = {}
    for t, w in zip(items, widths):
        r = pygame.Rect(x, pos[1], w, T.S * 4)
        rects[t] = r
        on = t == active
        draw_button(surf, F, r, t, ghost=not on, mpos=mpos)
        if on:
            pygame.draw.line(surf, T.BRASS, (r.x, r.bottom - 2), (r.right, r.bottom - 2), 2)
        x += w
    return rects


def smooth_circle(surf, color, center, radius, width=0):
    """Anti-aliased circle -- replaces `pygame.draw.circle` where edges matter
    (the unit token disc, mainly)."""
    x, y = int(center[0]), int(center[1])
    r = int(radius)
    if width == 0:
        gfxdraw.filled_circle(surf, x, y, r, color)
        gfxdraw.aacircle(surf, x, y, r, color)
    else:
        pygame.draw.circle(surf, color, center, radius, width)
        gfxdraw.aacircle(surf, x, y, r, color)
        if width > 1:
            gfxdraw.aacircle(surf, x, y, r - width + 1, color)


TOKEN_INK = (15, 15, 20)               # ink for the race glyph / letter on a unit token


def token_badge(surf, F, center, unit, *, color=None, r=14):
    """The round unit token: a coloured disc carrying the unit's race
    silhouette (`artwork.race_icon`), falling back to its board letter when
    the race has no glyph. `unit` may also be a bare letter string.

    `color` defaults to the guild's live banner colour (`theme.PLAYER_C`,
    read off the module each call, not captured, so a colour picked after
    this screen loads still applies) -- the one piece of theme.py state this
    component still shares with the legacy screens instead of owning a
    second copy of it."""
    smooth_circle(surf, color or _theme.PLAYER_C, center, r)
    race = getattr(unit, "race", None)
    sil = artwork.race_icon(race["name"], round(r * 1.6), TOKEN_INK) if race else None
    if sil is not None:
        surf.blit(sil, sil.get_rect(center=center))
    else:
        text(surf, F["bodyb"], str(getattr(unit, "token", unit)), center, TOKEN_INK, center=True)


def tracked(surf, font, s, pos, color, spacing=1):
    """`s` rendered with extra letter-spacing, for small caps labels."""
    x, y = pos
    for ch in s:
        img = font.render(ch, True, color)
        surf.blit(img, (x, y))
        x += img.get_width() + spacing
    return x


def section(surf, F, label, x, y, w, *, color=None):
    """A small tracked keyword with an underline; returns the y below it."""
    tracked(surf, F["micro"], label.upper(), (x, y), color or T.BRASS)
    ry = y + 14
    hline(surf, x, x + w, ry)
    return ry + T.S


FOOTER_H = 52
FOOTER_NOTICE_DY = 22          # a notice line sits this far above the row
FOOTER_HINT = "Esc for the pause menu"
LEFT_W, PRIMARY_W, SECONDARY_W = 140, 220, 180


def _padded(item):
    """`(key, label)` or `(key, label, enabled)` -> always the 3-tuple."""
    return item if len(item) == 3 else (*item, True)


def footer_bar(screen_obj, surf, F, *, back=None, secondary=None, primary=None,
               notice=None, notice_color=None, hint=FOOTER_HINT, margin=None):
    """The bottom action row most activity screens share: an optional back
    button bottom-left, up to two confirm buttons stacked right-to-left
    (`primary` rightmost and filled, `secondary` beside it), an optional
    notice line above the row, and the pause hint. Each slot is `(key,
    label)` or `(key, label, enabled)`; pass `hint=None` to a screen that
    already draws its own. Draws via `screen_obj.add_button` -- the screen
    owns how that lands on the surface (its own `ButtonsMixin` override,
    drawing through this module's `draw_button`)."""
    W, H = surf.get_size()
    m = margin if margin is not None else T.S * 3
    y = H - FOOTER_H

    if notice:
        text(surf, F["body_sm"], notice, (m, y - FOOTER_NOTICE_DY), notice_color or T.TX_MUTED)

    hx = m
    if back is not None:
        key, label, enabled = _padded(back)
        screen_obj.add_button(surf, pygame.Rect(m, y, LEFT_W, 36), key, label, enabled=enabled)
        hx = m + LEFT_W + T.S * 3

    rx = W - m
    if primary is not None:
        key, label, enabled = _padded(primary)
        rect = pygame.Rect(rx - PRIMARY_W, y, PRIMARY_W, 36)
        screen_obj.add_button(surf, rect, key, label, enabled=enabled, primary=True)
        rx = rect.x - T.S * 3

    if secondary is not None:
        key, label, enabled = _padded(secondary)
        rect = pygame.Rect(rx - SECONDARY_W, y, SECONDARY_W, 36)
        screen_obj.add_button(surf, rect, key, label, enabled=enabled)
        rx = rect.x - T.S * 3

    if hint:
        text(surf, F["micro"], hint, (hx, y + 12), T.TX_FAINT)


def header(surf, F, rect, title, sub, tabitems, active, mpos=(-1, -1)):
    """The screen-title chrome every full-window screen opens with: a
    discreet back arrow (drawn only -- the caller wires the click, since
    "back" means different things to different screens), the title in the
    display serif, a caps subtitle line, and a row of `tabs` anchored to
    the rect's right edge. Returns the tab hit rects."""
    pygame.draw.rect(surf, T.STEEL, rect)
    hline(surf, rect.x, rect.right, rect.bottom - 1)
    back_rect = pygame.Rect(rect.x, rect.y, T.S * 6, rect.h)
    arrow_col = T.BRASS if back_rect.collidepoint(mpos) else T.TX_MUTED
    cx = rect.x + T.S * 3
    pygame.draw.lines(surf, arrow_col, False,
                      [(cx + 6, rect.centery - 7), (cx - 2, rect.centery),
                       (cx + 6, rect.centery + 7)], 2)
    text(surf, F["titleb"], title, (rect.x + T.S * 6, rect.y + T.S * 2), T.TX)
    caps(surf, F["micro"], sub, (rect.x + T.S * 6, rect.y + T.S * 2 + 30), T.TX_FAINT)
    return tabs(surf, F, (rect.right - T.S * 3, rect.y + T.S * 2), tabitems, active,
                mpos=mpos, right=True)

"""Generic drawing primitives shared by every war-table panel: text
helpers, the one button style the whole screen uses, the `panel`/`modal_card`/
`draw_card` chrome every card and dialog sits on, and `contained` -- the
"this content lives inside that rect, period" clip scope."""

import contextlib

import pygame

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

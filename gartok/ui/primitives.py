"""Generic drawing primitives shared by every war-table panel: text
helpers, the one button style the whole screen uses, and `contained` --
the "this content lives inside that rect, period" clip scope."""

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

"""War-table design tokens: palette, spacing and fonts.

Deliberately separate from `gartok.theme` -- that ramp is the cool
blue-grey tuned for the app's flat UI screens, while this one is the
"steel desk + paper map" language the war-table prototype introduced. The
two coexist until map_screen finishes migrating onto this component set.
"""

import pygame


class T:
    # --- table (chrome: darkened steel) --------------------------------
    TABLE      = (17, 18, 20)
    STEEL      = (26, 28, 32)
    STEEL_HI   = (36, 39, 45)
    STEEL_LINE = (56, 60, 68)

    # --- paper (the world, laid on the table) ---------------------------
    PAPER      = (168, 154, 126)
    PAPER_HI   = (182, 169, 141)
    PAPER_LOW  = (140, 127, 102)
    INK        = (46, 39, 30)
    INK_SOFT   = (92, 79, 60)
    WASH_GREEN = (118, 124, 86)
    WASH_ROCK  = (128, 122, 110)
    WASH_TOWN  = (152, 128, 96)

    # --- ink on the chrome ----------------------------------------------
    TX         = (228, 228, 230)
    TX_MUTED   = (146, 152, 162)
    TX_FAINT   = (94, 100, 110)

    # --- metal / state (the screen's only glow) --------------------------
    BRASS      = (214, 168, 84)
    BRASS_DIM  = (128, 100, 50)
    BLOOD      = (176, 66, 58)
    GREEN      = (106, 146, 98)

    S = 8
    F_MICRO   = 11   # caps label
    F_BODY_SM = 12   # muted blurb / dialog subtitle
    F_BODY    = 13   # body / stat
    F_NAME    = 16   # proper name
    F_TITLE   = 24   # screen title
    F_HEAD    = 18   # card / section heading
    F_BIG     = 28   # clock reading / critical number


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


_font_cache = None


def fonts():
    """Cached after the first call -- callers that don't hold onto their own
    `self._F` (a modal mixin, a one-off block render) can call this every
    frame without re-hitting `pygame.font.SysFont` each time."""
    global _font_cache
    if _font_cache is None:
        cond = "dejavusanscondensed,dejavusans,arial"
        serif = "dejavuserif,georgia,serif"
        _font_cache = {
            "micro":   pygame.font.SysFont(cond, T.F_MICRO),
            "microb":  pygame.font.SysFont(cond, T.F_MICRO, bold=True),
            "body_sm": pygame.font.SysFont(cond, T.F_BODY_SM),
            "body":    pygame.font.SysFont(cond, T.F_BODY),
            "bodyb":   pygame.font.SysFont(cond, T.F_BODY, bold=True),
            "name":    pygame.font.SysFont(serif, T.F_NAME),
            "nameb":   pygame.font.SysFont(serif, T.F_NAME, bold=True),
            "titleb":  pygame.font.SysFont(serif, T.F_TITLE, bold=True),
            "head":    pygame.font.SysFont(cond, T.F_HEAD, bold=True),
            "big":     pygame.font.SysFont(cond, T.F_BIG, bold=True),
            "ink":     pygame.font.SysFont(serif, T.F_BODY),
            "inkb":    pygame.font.SysFont(serif, T.F_BODY, bold=True),
        }
    return _font_cache

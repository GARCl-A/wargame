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


ARCHETYPE_COLORS = {"brass": T.BRASS, "green": T.GREEN, "muted": T.TX_MUTED}


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


_font_cache = None


def fonts():
    """Cached after the first call -- callers that don't hold onto their own
    `self._F` (a modal mixin, a one-off block render) can call this every
    frame without re-hitting `pygame.font.SysFont` each time."""
    global _font_cache
    if _font_cache is None:
        if not pygame.font.get_init():
            pygame.font.init()
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


_SANS = "segoeui,calibri,arial"
_MONO = "consolas,dejavusansmono,couriernew"


class LegacyFonts:
    """The old font bundle (`fonts.body`, `fonts.num`, ...) that `app` still hands
    to every screen's constructor. Only the screens still on `theme` read it;
    built once after `pygame.init()`. New code uses `fonts()` above."""

    def __init__(self):
        S = lambda name, size, bold=False: pygame.font.SysFont(name, size, bold=bold)

        # weighted sans: identity, headings, labels, running text
        self.title    = S(_SANS, 28, bold=True)
        self.heading  = S(_SANS, 16, bold=True)
        self.label    = S(_SANS, 12, bold=True)
        self.body     = S(_SANS, 15)
        self.body_sm  = S(_SANS, 13)
        self.body_bd  = S(_SANS, 15, bold=True)

        # monospace: numbers, dice math, the log
        self.num_lg   = S(_MONO, 28, bold=True)
        self.num      = S(_MONO, 20, bold=True)
        self.mono     = S(_MONO, 13)
        self.mono_sm  = S(_MONO, 12)

        # --- back-compat aliases used by sheet.py and older call sites --- #
        self.font      = self.body
        self.big       = self.title
        self.small     = self.body_sm
        self.tiny      = S(_SANS, 12)
        self.kw        = self.label
        self.card_name = S(_SANS, 18, bold=True)
        self.card_val  = self.num

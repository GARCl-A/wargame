"""War-table design tokens: palette, spacing and fonts.

The "steel desk + paper map" language: the one palette, spacing grid and
font set every screen draws from (see `README.md` next to this file).
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
    F_DISPLAY = 64   # the game's name on the title screen, serif small caps

    # the hub screens (a node's tabs: shop, forge, recruit...) read a step above the base set
    F_HUB_TITLE = 26   # the keeper's name, serif small caps
    F_HUB_HEAD  = 18   # a panel's heading ("For Sale", "Party"), serif small caps
    F_HUB_CARD  = 16   # a member card's name, serif small caps
    F_HUB_ROW   = 14   # an item row's name
    F_HUB_BODY  = 13   # body text, tracked tab and button labels
    F_HUB_SUB   = 12   # the line under a row, hints
    F_HUB_LABEL = 11   # tracked caps labels
    F_HUB_VALUE = 24   # a header card's figure
    F_HUB_DEAL  = 16   # the deal card's headline
    F_HUB_PRICE = 16   # a shelf row's price


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


_font_cache = None


def _hub_fonts(serif):
    """The hub screens' set (`hub_*`): plain sans (not condensed) for text, serif small caps
    for names and headings -- each small-caps size comes with its `_sc` lower-case partner."""
    sans = "dejavusans,arial"
    out = {}
    for key, size in (("hub_title", T.F_HUB_TITLE), ("hub_head", T.F_HUB_HEAD), ("hub_card", T.F_HUB_CARD),
                      ("display", T.F_DISPLAY)):
        out[key] = pygame.font.SysFont(serif, size, bold=True)
        out[key + "_sc"] = pygame.font.SysFont(serif, int(size * 0.76), bold=True)
    for key, size, bold in (("hub_row", T.F_HUB_ROW, False), ("hub_body", T.F_HUB_BODY, False),
                            ("hub_bodyb", T.F_HUB_BODY, True), ("hub_sub", T.F_HUB_SUB, False),
                            ("hub_subb", T.F_HUB_SUB, True), ("hub_label", T.F_HUB_LABEL, True),
                            ("hub_value", T.F_HUB_VALUE, True), ("hub_deal", T.F_HUB_DEAL, True),
                            ("hub_price", T.F_HUB_PRICE, True)):
        out[key] = pygame.font.SysFont(sans, size, bold=bold)
    out["hub_quote"] = pygame.font.SysFont(sans, T.F_HUB_BODY + 1, italic=True)
    out["hub_quote_sm"] = pygame.font.SysFont(sans, T.F_HUB_SUB, italic=True)
    return out


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
            **_hub_fonts(serif),
        }
    return _font_cache

"""The frame every hub screen (a node's tabs: shop, forge, recruit...) sits in.

    hub_layout(size)                                   -> {"header", "tabs", "body", "footer"} rects
    draw_header(surf, F, rect, keeper, cards, help_w)  -> the keeper big at the left, cards at the right
    draw_tabs(surf, F, rect, tabs, active, mpos)       -> [(rect, key)] of the tabs
    draw_footer(surf, F, rect, back, hints, mpos)      -> the back button's rect
    hub_button(surf, F, rect, label, ...)              -> the frame's button (outlined, or filled brass)

`keeper` is {"place", "name", "caption", "bent", "line", "portrait"} -- or {"place"} alone for a
place with no keeper, drawn as a plain title. A card is {"label", "value", "sub" (optional),
"tone": "money" | "good" | "bad" | None, "warm": bool}: a big figure, or with a `sub` a headline
over a line of reasons (the shop's deal). Fonts are the `hub_*` set of `tokens.fonts()`.
"""

import pygame

from .. import artwork
from .primitives import small_caps, spaced, spaced_width, text, wrap
from .tokens import T, mix

_TONE = {"money": T.BRASS, "good": T.GREEN, "bad": T.BLOOD, None: T.TX}
MARGIN = T.S * 3               # the frame's side margin; a tab's body lines up with it
HELP_W = T.S * 5               # the reopen-tutorial disc at the header's right


def hub_layout(size):
    """The frame's rects for a window of `size`: the header, the tab row under it, the
    tab's body and the footer row."""
    W, H = size
    m = MARGIN
    head_h = round(max(T.S * 14, min(T.S * 16, H * 0.12)))      # room for a two-line keeper's line
    tabs = pygame.Rect(0, head_h, W, T.S * 5 + 4)
    foot_h = T.S * 5
    footer = pygame.Rect(m, H - T.S * 3 - foot_h, W - 2 * m, foot_h)
    body = pygame.Rect(0, tabs.bottom + T.S * 2, W, max(1, footer.y - T.S * 2 - (tabs.bottom + T.S * 2)))
    return {"header": pygame.Rect(0, 0, W, head_h), "tabs": tabs, "body": body, "footer": footer, "margin": m}


def hub_button(surf, F, rect, label, *, primary=False, enabled=True, mpos=(-1, -1)):
    hot = enabled and rect.collidepoint(mpos)
    if primary:
        fill = (mix(T.BRASS, T.TX, 0.15) if hot else T.BRASS) if enabled else T.BRASS_DIM
        pygame.draw.rect(surf, fill, rect, border_radius=6)
        spaced(surf, F["hub_bodyb"], label, rect.center, T.TABLE, anchor="center")
    else:
        pygame.draw.rect(surf, mix(T.TABLE, T.BRASS, 0.08) if hot else T.TABLE, rect, border_radius=6)
        pygame.draw.rect(surf, T.BRASS if enabled else T.STEEL_LINE, rect, 1, border_radius=6)
        spaced(surf, F["hub_bodyb"], label, rect.center, T.BRASS if enabled else T.TX_FAINT, anchor="center")


def button_width(F, label):
    return spaced_width(F["hub_bodyb"], label) + T.S * 5


def _card(surf, F, rect, card):
    fill = mix(T.STEEL, T.BRASS, 0.04) if card.get("warm") else T.STEEL
    pygame.draw.rect(surf, fill, rect, border_radius=6)
    pygame.draw.rect(surf, T.STEEL_LINE, rect, 1, border_radius=6)
    x = rect.x + T.S * 2
    label = spaced(surf, F["hub_label"], card["label"], (x, rect.y + T.S + 2), T.TX_MUTED)
    color = _TONE[card.get("tone")]
    if card.get("sub"):
        sub = F["hub_sub"]
        text(surf, sub, card["sub"], (x - 1, rect.bottom - T.S - sub.get_height()), T.TX_MUTED)
        text(surf, F["hub_deal"], card["value"], (x - 2, label.bottom + 2), color)
    else:
        value = F["hub_value"]
        text(surf, value, card["value"], (x - 2, (label.bottom + rect.bottom - value.get_height()) // 2), color)


def card_width(F, card):
    sub = F["hub_sub"].size(card.get("sub", ""))[0]
    head = F["hub_deal" if card.get("sub") else "hub_value"].size(card["value"])[0]
    return max(T.S * 18, sub + T.S * 4, head + T.S * 4, spaced_width(F["hub_label"], card["label"]) + T.S * 4)


def draw_header(surf, F, rect, keeper, cards, help_w=HELP_W):
    """The keeper big at the left; `cards` right-aligned, leaving `help_w` at the right edge
    for the tutorial disc. Returns the rect the tutorial disc sits in."""
    m = MARGIN
    card_h = max(T.S * 9, rect.h - T.S * 6)      # room for a label, a headline and a reason
    card_y = rect.y + (rect.h - card_h) // 2
    help_r = pygame.Rect(rect.right - m - help_w, card_y, help_w, help_w)
    right = help_r.x - T.S * 2
    cards_left = right
    for card in reversed(cards):
        w = card_width(F, card)
        r = pygame.Rect(right - w, card_y, w, card_h)
        _card(surf, F, r, card)
        right = cards_left = r.x - T.S * 2

    port = rect.h - T.S * 4
    x = rect.x + m
    if keeper.get("portrait"):
        img = artwork.portrait(None, keeper["portrait"], port)
        if img is not None:
            surf.blit(img, (x, rect.y + T.S * 2))
            x += port + T.S * 2 + 4
    if not keeper.get("name"):
        small_caps(surf, F["hub_title"], F["hub_title_sc"], keeper["place"], (x, rect.centery), T.TX,
                   anchor="midleft")
        return help_r
    place = spaced(surf, F["hub_label"], keeper["place"], (x, rect.y + T.S * 2 + 4), T.BRASS)
    name = small_caps(surf, F["hub_title"], F["hub_title_sc"], keeper["name"], (x, place.bottom + 2), T.TX)
    tag = "  ·  ".join(p for p in (keeper.get("caption"), keeper.get("bent")) if p)
    if tag and name.right + T.S * 2 + F["hub_body"].size(tag)[0] < cards_left - T.S * 2:
        text(surf, F["hub_body"], tag, (name.right + T.S * 2, name.bottom - F["hub_body"].get_height() - 3), T.TX_MUTED)
    elif tag:
        text(surf, F["hub_sub"], tag, (place.right + T.S * 2, place.y - 1), T.TX_MUTED)
    if keeper.get("line"):
        _quote(surf, F, x, name.bottom + T.S - 2, cards_left - T.S * 2 - x, f"“{keeper['line']}”")
    return help_r


def _quote(surf, F, x, y, room, quote):
    """The keeper's line in its box: at full size if it fits `room`, smaller if not, and in two
    lines at the smaller size as the last resort."""
    pad = T.S + 4
    font = F["hub_quote"]
    lines = [quote]
    if font.size(quote)[0] + 2 * pad > room:
        font = F["hub_quote_sm"]
        if font.size(quote)[0] + 2 * pad > room:
            lines = wrap(font, quote, room - 2 * pad)[:2]
    lh = font.get_linesize()
    w = max(font.size(line)[0] for line in lines) + 2 * pad
    q = pygame.Rect(x, y, min(w, room), max(T.S * 3 + 4, len(lines) * lh + T.S))
    pygame.draw.rect(surf, mix(T.STEEL, T.TABLE, 0.3), q, border_radius=6)
    pygame.draw.rect(surf, T.STEEL_LINE, q, 1, border_radius=6)
    ty = q.centery - len(lines) * lh // 2
    for line in lines:
        text(surf, font, line, (q.x + pad, ty), T.TX)
        ty += lh


def draw_tabs(surf, F, rect, tabs, active, mpos):
    """The tab row between two rules; the active tab is underlined in brass."""
    pygame.draw.line(surf, T.STEEL_LINE, (rect.x, rect.y), (rect.right, rect.y))
    pygame.draw.line(surf, T.STEEL_LINE, (rect.x, rect.bottom - 1), (rect.right, rect.bottom - 1))
    hits = []
    x = rect.x + T.S * 3
    for key, label in tabs:
        w = spaced_width(F["hub_bodyb"], label) + T.S * 4
        r = pygame.Rect(x, rect.y + 1, w, rect.h - 2)
        on = key == active
        hot = not on and r.collidepoint(mpos)
        spaced(surf, F["hub_bodyb"], label, r.center, T.TX if (on or hot) else T.TX_MUTED, anchor="center")
        if on:
            pygame.draw.rect(surf, T.BRASS, pygame.Rect(r.x, rect.bottom - 4, r.w, 3))
        hits.append((r, key))
        x = r.right + T.S * 2
    return hits


def draw_footer(surf, F, rect, back, hints, mpos):
    """The back button at the left, the keyboard hints at the right."""
    back_r = pygame.Rect(rect.x, rect.y, button_width(F, back), rect.h)
    hub_button(surf, F, back_r, back, mpos=mpos)
    if hints:
        text(surf, F["hub_sub"], hints, (rect.right, rect.centery - F["hub_sub"].get_height() // 2),
             T.TX_FAINT, right=True)
    return back_r

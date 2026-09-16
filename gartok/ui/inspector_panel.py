"""The INSPECTOR zone: the one place on the screen with descriptive
text -- the selected band's party, status and whatever it can be told to
do right now.

Purely presentational: it takes the selected band's name/status/party and
an ordered list of content `blocks` (buttons, button rows, text lines,
section headers) instead of branching on node kind or order state itself
-- that dispatch is the caller's job (a war-table mock's three canned
orders, or a real screen's dozen node-kind actions), so this component
doesn't grow a case per screen that uses it.

`button`, when given, replaces the built-in button drawing -- a real
screen with its own hit-testing/registration (e.g. `ButtonsMixin.add_button`)
passes its own callable instead of the presentation-only default.
"""

import pygame

from .primitives import caps, draw_button, hline, text, wrap
from .tokens import T

ROLE_MARK = {"vanguard": "shield", "archer": "bow", "hand": "sword", "healer": "cross"}


def draw_role(surf, p, kind, c):
    x, y = p
    if kind == "shield":
        pygame.draw.polygon(surf, c, [(x, y - 6), (x + 5, y - 3), (x + 5, y + 2),
                                      (x, y + 6), (x - 5, y + 2), (x - 5, y - 3)], 1)
    elif kind == "bow":
        pygame.draw.arc(surf, c, pygame.Rect(x - 5, y - 6, 10, 12), -1.2, 1.2, 1)
        pygame.draw.line(surf, c, (x + 3, y - 5), (x + 3, y + 5), 1)
    elif kind == "cross":
        pygame.draw.line(surf, c, (x, y - 5), (x, y + 5), 2)
        pygame.draw.line(surf, c, (x - 4, y - 1), (x + 4, y - 1), 2)
    else:
        pygame.draw.line(surf, c, (x - 4, y + 5), (x + 4, y - 5), 2)
        pygame.draw.line(surf, c, (x - 3, y - 3), (x + 2, y + 2), 1)


def _default_button(surf, F, rect, mpos, *, key=None, label="", sub=None,
                    primary=False, danger=False, enabled=True, font=None):
    if not enabled:
        text(surf, font or F["microb"], label.upper(), rect.center, T.TX_FAINT, center=True)
        pygame.draw.rect(surf, T.STEEL_LINE, rect, 1)
        return
    draw_button(surf, F, rect, label, sub=sub, primary=primary, danger=danger,
               mpos=mpos, fnt=font)


def block_height(item):
    if item["type"] == "text":
        return 16
    if item["type"] == "wrapped_text":
        return 15 * len(item.get("_lines", item["text"].split("\n")))
    if item["type"] == "section":
        return T.S * 2
    if item["type"] in ("button", "button_row"):
        return item.get("height", T.S * 5)
    return 0


def draw_blocks(surf, F, x, y, w, blocks, mpos, button):
    """Lays out `blocks` top-down from `(x, y)`, `w` wide. Returns the y
    just past the last block. Each block is one of:
      {"type": "section", "label": str}
      {"type": "text", "text": str, "color": color}
      {"type": "wrapped_text", "text": str, "color": color, "line_h": int}
      {"type": "button", "key", "label", "height", "sub", "primary",
       "danger", "enabled", "font"}
      {"type": "button_row", "items": [{...same as button, minus height}],
       "height": int, "gap": int}
    """
    for item in blocks:
        y += item.get("gap_before", 0)
        kind = item["type"]
        if kind == "section":
            caps(surf, F["micro"], item["label"], (x, y), T.TX_FAINT)
            y += T.S * 2
        elif kind == "text":
            text(surf, item.get("font") or F["body_sm"] if "body_sm" in F else F["body"],
                item["text"], (x, y), item.get("color", T.TX_FAINT))
            y += item.get("line_h", 16)
        elif kind == "wrapped_text":
            lines = wrap(F.get("body_sm", F["body"]), item["text"], w)
            line_h = item.get("line_h", 15)
            for ln in lines:
                text(surf, F.get("body_sm", F["body"]), ln, (x, y), item.get("color", T.TX_FAINT))
                y += line_h
        elif kind == "button":
            h = item.get("height", T.S * 5)
            r = pygame.Rect(x, y, w, h)
            button(surf, F, r, mpos, key=item.get("key"), label=item["label"],
                  sub=item.get("sub"), primary=item.get("primary", False),
                  danger=item.get("danger", False), enabled=item.get("enabled", True),
                  font=item.get("font"))
            y = r.bottom + T.S
        elif kind == "button_row":
            h = item.get("height", 34)
            gap = item.get("gap", T.S)
            n = len(item["items"])
            col_w = (w - (n - 1) * gap) // n
            for i, sub_item in enumerate(item["items"]):
                r = pygame.Rect(x + i * (col_w + gap), y, col_w, h)
                button(surf, F, r, mpos, key=sub_item.get("key"), label=sub_item["label"],
                      enabled=sub_item.get("enabled", True), font=sub_item.get("font"))
            y += h + T.S
    return y


def draw_inspector(surf, F, rect, name, state_label, state_color, where, party,
                   blocks, bottom_blocks=(), mpos=(-1, -1), button=None, party_icon=None):
    """`party` items are `(name, role, hp_frac)`, or `(name, role, hp_frac,
    *extra)` -- `party_icon(surf, item, center)`, when given, draws whatever
    the caller wants for that row's mark (e.g. a real screen's own unit
    token art) in place of the built-in role glyph (shield/bow/cross/sword,
    from `role`)."""
    if button is None:
        button = _default_button

    pygame.draw.rect(surf, T.STEEL, rect)
    pygame.draw.line(surf, T.STEEL_LINE, (rect.x, rect.y), (rect.x, rect.bottom), 1)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4
    y = rect.y + T.S * 2

    caps(surf, F["micro"], "selected band", (x, y), T.TX_FAINT)
    y += T.S * 2
    text(surf, F["nameb"], name, (x, y), T.TX)
    y += T.S * 3
    caps(surf, F["micro"], state_label, (x, y), state_color)
    text(surf, F["body"], f"  ·  {where}", (x + 84, y - 1), T.TX_FAINT)
    y += T.S * 4

    caps(surf, F["micro"], "party", (x, y), T.TX_FAINT)
    y += T.S * 2
    for item in party:
        nm, role = item[0], item[1]
        row = pygame.Rect(x, y, w, T.S * 3)
        pygame.draw.rect(surf, T.TABLE, row)
        center = (row.x + T.S * 2, row.centery)
        if party_icon is not None:
            party_icon(surf, item, center)
        else:
            draw_role(surf, center, ROLE_MARK.get(role, "sword"), T.TX_MUTED)
        text(surf, F["body"], nm, (row.x + T.S * 4, row.centery - 7), T.TX)
        y = row.bottom + 4
    y += T.S * 2

    hline(surf, x, x + w, y)
    y += T.S * 4

    y = draw_blocks(surf, F, x, y, w, blocks, mpos, button)

    bottom_h = T.S * 2 + sum(block_height(b) + b.get("gap_before", 0) + T.S for b in bottom_blocks)
    by = max(y, rect.bottom - bottom_h)
    hline(surf, x, x + w, by)
    draw_blocks(surf, F, x, by + T.S * 2, w, bottom_blocks, mpos, button)

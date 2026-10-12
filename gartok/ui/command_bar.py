"""The COMMAND zone: top strip with the clock, danger/deadline alerts and
the guild's headline stats. Data-driven -- `messages` and `metrics` are
supplied by the caller instead of hardcoded, so a real screen can feed it
`guild.clock` / `arena.defense_due` the same way the prototype feeds it
mock strings."""

import pygame

from .primitives import caps, draw_button, ellipsize, hline, text
from .tokens import T, mix


def draw_command(surf, F, rect, day, time_str, messages, metrics, mpos=(0, 0),
                 guild_label="guild", icon_fn=None, card=None):
    """Draws the command strip. `messages` items are `(text, color)` or
    `(text, color, icon_key)`; `icon_fn(surf, icon_key, icon_rect, color)`,
    when given, draws the alert's icon in place of the default "!" glyph
    (a real screen wires this to its own icon set, e.g. `artwork.icon`).

    Returns `(hovered, buttons)`: `hovered` is hover tooltip data for an
    alert icon under the mouse, as `(x, y, text, color)`, or None;
    `buttons` is `{"help": rect, "guild": rect, "card": rect}` (`card` only when drawn) for the caller's own
    click-dispatch (this component draws but doesn't register hits itself).

    `card`, when given, is a wide alert after the icon tray for what must not be
    missed: `(title, tip, critical)`, blood red when `critical`, brass otherwise;
    `tip` shows on hover like an icon's. It shrinks (the title clips) to fit
    before the metrics."""
    pygame.draw.rect(surf, T.STEEL, rect)
    hline(surf, rect.x, rect.right, rect.bottom - 1)
    x = rect.x + T.S * 3
    y = rect.y + 16

    day_label = f"day {day}"
    caps(surf, F["micro"], day_label, (x, y), T.TX_FAINT)
    text(surf, F["big"], time_str, (x, y + 14), T.TX)
    x += max(F["micro"].size(day_label.upper())[0], F["big"].size(time_str)[0]) + T.S * 3
    pygame.draw.line(surf, T.STEEL_LINE, (x, rect.y + T.S), (x, rect.bottom - T.S), 1)
    x += T.S * 3

    # message tray: icons with hover tooltips
    icon_x = x
    icon_y = rect.centery - 16
    icon_size = 32
    hovered = None

    for m in messages:
        m_text, m_color = m[0], m[1]
        m_icon = m[2] if len(m) > 2 else None
        icon_rect = pygame.Rect(icon_x, icon_y, icon_size, icon_size)
        pygame.draw.rect(surf, m_color, icon_rect)
        pygame.draw.rect(surf, T.TX_FAINT, icon_rect, 1)
        if icon_fn is not None and m_icon is not None:
            icon_fn(surf, m_icon, icon_rect, T.TABLE)
        else:
            caps(surf, F["body"], "!", (icon_rect.centerx, icon_rect.centery - 7), T.TABLE, center=True)

        if icon_rect.collidepoint(mpos):
            hovered = (icon_rect.centerx, icon_rect.bottom + 8, m_text, m_color)

        icon_x += icon_size + T.S

    # right-edge menus (? and GUILD) -- width follows the guild button's own
    # label so a level-up badge folded into it doesn't get clipped
    bh = T.S * 4
    help_w = 32
    guild_w = max(80, F["microb"].size(guild_label.upper())[0] + T.S * 4)
    bx = rect.right - T.S * 2 - help_w
    by = rect.centery - bh // 2

    help_rect = pygame.Rect(bx, by, help_w, bh)
    draw_button(surf, F, help_rect, "?", ghost=True, mpos=mpos)

    bx -= guild_w + T.S
    guild_rect = pygame.Rect(bx, by, guild_w, bh)
    draw_button(surf, F, guild_rect, guild_label, ghost=True, mpos=mpos)

    # guild metrics sit left of the menus -- each column's width (and the
    # block's total width) comes from what's actually in `metrics`, not a
    # count/width assumed up front, so adding/dropping/renaming a stat
    # never overlaps or leaves a gap.
    col_widths = [max(F["micro"].size(label.upper())[0], F["big"].size(value)[0]) + T.S * 4
                  for label, value in metrics]
    x = bx - T.S * 3 - sum(col_widths)
    metrics_x = x
    pygame.draw.line(surf, T.STEEL_LINE, (x, rect.y + T.S), (x, rect.bottom - T.S), 1)
    x += T.S * 3

    for (label, value), col_w in zip(metrics, col_widths):
        caps(surf, F["micro"], label, (x, y), T.TX_FAINT)
        text(surf, F["big"], value, (x, y + 14), T.TX)
        x += col_w

    buttons = {"help": help_rect, "guild": guild_rect}
    if card is not None:
        title, tip, critical = card
        col = T.BLOOD if critical else T.BRASS
        cr = pygame.Rect(icon_x, rect.centery - T.S * 5 // 2, 0, T.S * 5)
        cr.w = min(F["nameb"].size(title)[0] + T.S * 4, metrics_x - T.S * 2 - icon_x)
        if cr.w > T.S * 6:
            pygame.draw.rect(surf, mix(col, T.STEEL, .55 if critical else .75), cr)
            pygame.draw.rect(surf, col, cr, 1)
            pygame.draw.rect(surf, col, pygame.Rect(cr.x, cr.y, T.S // 2, cr.h))
            label = ellipsize(title, F["nameb"], cr.w - T.S * 3)
            text(surf, F["nameb"], label, (cr.x + T.S * 2, cr.centery - F["nameb"].get_height() // 2), T.TX)
            if cr.collidepoint(mpos):
                hovered = (cr.centerx, cr.bottom + 8, tip, col)
            buttons["card"] = cr

    return hovered, buttons

"""The screens after a fight: the memorial of a lost character, the after-action report and
the level-up card. Each takes plain dicts and lays out inside the surface it is given.

`draw_memorial(surf, F, d, mpos)` -- a centred card built to be screenshotted:
- `name`, `race`, `occupation`, `portrait_id`;
- `cause` ("Killed in combat"), `days` ("15 days with the guild"), `span` ("day 3 to day 17"),
  `place` and `killer` (either may be None), `line` (the log line of the fall, or None);
- `tag` (the small caps line on top, "IN MEMORIAM · 1 OF 2"), `button`.
Returns the button rect.

`draw_report(surf, F, d, mpos)` -- the after-action report, full window:
- `result` (VICTORY / FLED / DEFEAT), `sub` (where, how many rounds);
- `rows`: `{name, race, portrait_id, status, downed: [str], level, bar (0..1), xp_note}`;
  `status` is standing / stable / fled / fallen;
- `takedowns`: `[(who, whom, mine)]`, `mine` when the victim was on the squad;
- `deeds`: `[(name, line)]`; `notes`: `[str]`; `button`.
Returns the button rect.

`draw_level_up(surf, F, d, mpos)` -- one character's new level:
- `name`, `race`, `portrait_id`, `stamp` ("LEVEL 3"), `track` ("COMBAT");
- `gains`: `[(label, before, shown, after)]`, `shown` the number on its way up;
- `talents` (label of the talent button, or None), `button`, `tag`.
Returns `(talents_rect or None, button_rect)`.
"""

import pygame

from .. import artwork
from .primitives import (
    caps,
    draw_button,
    ellipsize,
    hline,
    modal_card,
    panel,
    section,
    text,
    wrap,
)
from .tokens import T, mix

_BUTTON = (T.S * 20, T.S * 5)
_STATUS = {"standing": ("STANDING", T.GREEN), "stable": ("DOWN, STABLE", T.BRASS),
           "fled": ("FLED", T.TX_MUTED), "fallen": ("FALLEN", T.BLOOD)}
_RESULT = {"VICTORY": T.BRASS, "FLED": T.TX_MUTED, "DEFEAT": T.BLOOD}


def _medallion(surf, center, size, race, portrait_id, ring, grey=False):
    x, y = center[0] - size // 2, center[1] - size // 2
    port = artwork.portrait(race, portrait_id, size)
    if port is not None:
        if grey:
            port = pygame.transform.grayscale(port)
        surf.blit(port, (x, y))
    else:
        pygame.draw.circle(surf, T.STEEL_HI, center, size // 2)
        icon = artwork.race_icon(race, size // 2, T.TX_MUTED)
        if icon is not None:
            surf.blit(icon, (x + size // 4, y + size // 4))
    pygame.draw.circle(surf, ring, center, size // 2, 2)


def _card_w(surf, lo, hi, frac):
    W, _ = surf.get_size()
    return int(min(max(W * frac, lo), hi, W - T.S * 4))


def _pair(surf, F, x, y, w, label, value, color=T.TX):
    caps(surf, F["micro"], label, (x, y + 2), T.TX_FAINT)
    text(surf, F["bodyb"], ellipsize(value, F["bodyb"], w - T.S * 18), (x + T.S * 18, y), color)
    return y + T.S * 3


# ---------------------------------------------------------------------- #
# memorial                                                               #
# ---------------------------------------------------------------------- #
def draw_memorial(surf, F, d, mpos=(-1, -1)):
    _, H = surf.get_size()
    w = _card_w(surf, 380, 520, 0.36)
    pad = T.S * 4
    inner = w - 2 * pad
    size = max(T.S * 12, min(T.S * 20, H // 4))
    quote = wrap(F["ink"], f"“{d['line']}”", inner) if d.get("line") else []
    facts = [(k, v) for k, v in (("DAYS", d["days"]), ("FELL AT", d.get("place")),
                                 ("DOWNED BY", d.get("killer")), ("CAUSE", d["cause"])) if v]
    h = (pad + T.S * 3 + size + T.S * 3 + T.S * 5 + T.S * 3 + T.S * 3 + T.S * 2
         + len(facts) * T.S * 3 + T.S * 2 + len(quote) * T.S * 3 + T.S * 3 + _BUTTON[1] + pad)
    rect = modal_card(surf, (w, min(h, H - T.S * 2)), veil=True)
    pygame.draw.rect(surf, T.BLOOD, rect, 2, border_radius=4)

    cx, y = rect.centerx, rect.y + pad
    caps(surf, F["microb"], d.get("tag", "IN MEMORIAM"), (cx, y), T.BLOOD, center=True)
    y += T.S * 3
    _medallion(surf, (cx, y + size // 2), size, d["race"], d.get("portrait_id"), T.BLOOD, grey=True)
    y += size + T.S * 3
    text(surf, F["titleb"], ellipsize(d["name"], F["titleb"], inner), (cx, y), T.TX, center=True)
    y += T.S * 5
    text(surf, F["body"], f"{d['race']} · {d['occupation']}", (cx, y), T.TX_MUTED, center=True)
    y += T.S * 3
    text(surf, F["micro"], d.get("span", ""), (cx, y), T.TX_FAINT, center=True)
    y += T.S * 3
    hline(surf, rect.x + pad, rect.right - pad, y)
    y += T.S * 2
    for label, value in facts:
        y = _pair(surf, F, rect.x + pad, y, inner, label, value,
                  T.BLOOD if label == "DOWNED BY" else T.TX)
    y += T.S * 2
    for ln in quote:
        text(surf, F["ink"], ln, (rect.x + pad, y), T.TX_MUTED)
        y += T.S * 3

    button = pygame.Rect(0, 0, *_BUTTON)
    button.bottomright = (rect.right - pad, rect.bottom - pad)
    draw_button(surf, F, button, d.get("button", "CONTINUE"), primary=True, danger=True, mpos=mpos)
    return button


# ---------------------------------------------------------------------- #
# after-action report                                                    #
# ---------------------------------------------------------------------- #
def _member_row(surf, F, r, row):
    panel(surf, r)
    label, col = _STATUS.get(row["status"], ("", T.TX_MUTED))
    size = r.h - T.S * 2
    _medallion(surf, (r.x + T.S + size // 2, r.centery), size, row["race"], row.get("portrait_id"),
               col, grey=row["status"] == "fallen")
    x = r.x + T.S * 2 + size
    right = r.right - T.S * 2
    text(surf, F["name"], ellipsize(row["name"], F["name"], right - x - T.S * 16), (x, r.y + T.S), T.TX)
    caps(surf, F["microb"], label, (right, r.y + T.S + 4), col, right=True)
    downed = row.get("downed") or ()
    line = f"downed {', '.join(downed)}" if downed else "downed nobody"
    text(surf, F["body_sm"], ellipsize(line, F["body_sm"], right - x), (x, r.y + T.S * 4),
         T.TX if downed else T.TX_FAINT)

    bar_y = r.bottom - T.S * 2 - 4
    caps(surf, F["micro"], f"LV {row['level']}", (x, bar_y - 4), T.TX_MUTED)
    track = pygame.Rect(x + T.S * 6, bar_y, max(T.S * 4, right - x - T.S * 18), 6)
    pygame.draw.rect(surf, T.STEEL_HI, track, border_radius=3)
    fill = pygame.Rect(track.x, track.y, int(track.w * max(0.0, min(1.0, row["bar"]))), track.h)
    if fill.w:
        pygame.draw.rect(surf, T.BRASS if row["status"] != "fallen" else T.TX_FAINT, fill, border_radius=3)
    text(surf, F["micro"], row.get("xp_note", ""), (right, bar_y - 4), T.BRASS if row.get("xp_note") else T.TX_FAINT,
         right=True)


def draw_report(surf, F, d, mpos=(-1, -1)):
    W, H = surf.get_size()
    surf.fill(T.TABLE)
    color = _RESULT.get(d["result"], T.TX)
    m = T.S * 3 if W < 1200 else T.S * 5
    head = pygame.Rect(0, 0, W, T.S * 9)
    pygame.draw.rect(surf, T.STEEL, head)
    hline(surf, 0, W, head.bottom - 1)
    pygame.draw.rect(surf, color, pygame.Rect(0, head.bottom - 3, W, 3))
    caps(surf, F["microb"], "AFTER-ACTION REPORT", (m, T.S * 2), T.TX_FAINT)
    text(surf, F["titleb"], d["result"], (m, T.S * 4), color)
    caps(surf, F["micro"], d.get("sub", ""), (W - m, T.S * 4 + 8), T.TX_MUTED, right=True)

    body_top = head.bottom + T.S * 3
    body_bottom = H - T.S * 3 - _BUTTON[1] - T.S * 2
    wide = W >= 900
    left_w = int((W - 2 * m) * (0.58 if wide else 1.0))
    row_h = T.S * 9
    rows = d.get("rows", ())
    y = section(surf, F, f"the squad · {len(rows)}", m, body_top, left_w)
    for row in rows:
        if y + row_h > body_bottom:
            break
        _member_row(surf, F, pygame.Rect(m, y, left_w, row_h), row)
        y += row_h + T.S

    if wide:
        x, w, y = m + left_w + T.S * 4, W - 2 * m - left_w - T.S * 4, body_top
    else:
        x, w = m, W - 2 * m
        y += T.S * 2
    takedowns = d.get("takedowns", ())
    y = section(surf, F, f"takedowns · {len(takedowns)}", x, y, w)
    if not takedowns:
        text(surf, F["body_sm"], "Nobody was put down.", (x, y), T.TX_FAINT)
        y += T.S * 3
    for i, (who, whom, mine) in enumerate(takedowns):
        if y + T.S * 3 > body_bottom - T.S * 3:
            text(surf, F["body_sm"], f"and {len(takedowns) - i} more", (x, y), T.TX_FAINT)
            y += T.S * 3
            break
        col = T.BLOOD if mine else T.TX
        text(surf, F["body_sm"], ellipsize(f"{who}  →  {whom}", F["body_sm"], w), (x, y), col)
        y += T.S * 3
    if d.get("deeds"):
        y = section(surf, F, "deeds", x, y + T.S * 2, w, color=T.GREEN)
        for name, line in d["deeds"]:
            text(surf, F["bodyb"], ellipsize(name, F["bodyb"], w), (x, y), T.GREEN)
            text(surf, F["body_sm"], ellipsize(line, F["body_sm"], w), (x, y + T.S * 2 + 2), T.TX_MUTED)
            y += T.S * 6
    if d.get("notes"):
        y = section(surf, F, "notes", x, y + T.S * 2, w)
        for note in d["notes"]:
            for ln in wrap(F["body_sm"], note, w):
                if y + T.S * 3 > body_bottom:
                    break
                text(surf, F["body_sm"], ln, (x, y), T.TX_MUTED)
                y += T.S * 2 + 4

    button = pygame.Rect(0, 0, *_BUTTON)
    button.bottomright = (W - m, H - T.S * 3)
    draw_button(surf, F, button, d.get("button", "CONTINUE"), primary=True, mpos=mpos)
    return button


# ---------------------------------------------------------------------- #
# level up                                                               #
# ---------------------------------------------------------------------- #
def _stamp(surf, F, center, label):
    font = F["big"]
    pad = T.S * 2
    tw, th = font.size(label)
    s = pygame.Surface((tw + pad * 2, th + pad), pygame.SRCALPHA)
    pygame.draw.rect(s, (*T.BRASS, 255), s.get_rect(), 3, border_radius=4)
    pygame.draw.rect(s, (*T.BRASS, 255), s.get_rect().inflate(-8, -8), 1, border_radius=3)
    s.blit(font.render(label, True, T.BRASS), (pad, pad // 2))
    s = pygame.transform.rotate(s, 9)
    surf.blit(s, s.get_rect(center=center))


def draw_level_up(surf, F, d, mpos=(-1, -1)):
    _, H = surf.get_size()
    w = _card_w(surf, 420, 560, 0.4)
    pad = T.S * 4
    inner = w - 2 * pad
    size = max(T.S * 14, min(T.S * 24, H // 3))
    gains = d.get("gains", ())
    h = pad + T.S * 3 + size + T.S * 3 + T.S * 5 + T.S * 3 + T.S * 2 + len(gains) * T.S * 4 + T.S * 3 + _BUTTON[1] + pad
    rect = modal_card(surf, (w, min(h, H - T.S * 2)), veil=True)
    pygame.draw.rect(surf, T.BRASS, rect, 1, border_radius=4)

    cx, y = rect.centerx, rect.y + pad
    caps(surf, F["microb"], d.get("tag", "LEVEL UP"), (cx, y), T.BRASS, center=True)
    y += T.S * 3
    _medallion(surf, (cx, y + size // 2), size, d["race"], d.get("portrait_id"), T.BRASS)
    _stamp(surf, F, (cx + size * 2 // 5, y + size * 3 // 4), d["stamp"])
    y += size + T.S * 3
    text(surf, F["titleb"], ellipsize(d["name"], F["titleb"], inner), (cx, y), T.TX, center=True)
    y += T.S * 5
    caps(surf, F["micro"], f"{d.get('track', '')} TRACK", (cx, y), T.TX_FAINT, center=True)
    y += T.S * 3
    hline(surf, rect.x + pad, rect.right - pad, y)
    y += T.S * 2
    for label, before, shown, after in gains:
        done = shown == after
        caps(surf, F["micro"], label, (rect.x + pad, y + 6), T.TX_MUTED)
        text(surf, F["body"], str(before), (rect.right - pad - T.S * 12, y + 4), T.TX_FAINT, right=True)
        text(surf, F["body"], "→", (rect.right - pad - T.S * 9, y + 4 + F["body"].get_height() // 2), T.TX_FAINT,
             center=True)
        text(surf, F["head"], str(shown), (rect.right - pad, y), T.BRASS if done else mix(T.TX, T.BRASS, 0.5),
             right=True)
        y += T.S * 4

    button = pygame.Rect(0, 0, *_BUTTON)
    button.bottomright = (rect.right - pad, rect.bottom - pad)
    draw_button(surf, F, button, d.get("button", "CONTINUE"), primary=True, mpos=mpos)
    talents = None
    if d.get("talents"):
        talents = pygame.Rect(0, 0, *_BUTTON)
        talents.bottomright = (button.x - T.S * 2, button.bottom)
        draw_button(surf, F, talents, d["talents"], mpos=mpos)
    return talents, button

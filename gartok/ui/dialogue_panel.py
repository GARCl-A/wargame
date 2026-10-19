"""The dialogue before a fight: who meets you, what they say, who answers and how.

    draw_dialogue(surf, F, rect, d, mpos) -> {"speakers": [(id, rect)], "options": [(id, rect)],
                                              "button": rect | None}

`d` is a plain dict:

- `leader`: {"name", "caption" ("Orc bandit"), "race", "portrait"} or None (nobody talks);
- `line`: what the leader says; `foes`: one short line per foe ("Grusk · Orc");
- `speakers`: [{"id", "name", "caption" ("CHA +2 · Common, Orcish"), "selected"}];
- `options`: [{"id", "label", "note", "check" ("CHA +2 vs DC 12"), "odds" (0..1 or None),
  "block" ("" or why it is closed)}];
- `result`: None while choosing, else {"text", "tone" ("peace" | "fight" | "next"),
  "button" (its label)}.

The left column is the foe, the right one the answer: the speakers on top, then either the
options or the result and its one button. Sizes come from `rect`; when the full chips and answers do not fit, both go to one line each.
"""

import pygame

from .. import artwork
from .primitives import caps, draw_button, ellipsize, hline, panel, section, smooth_circle, text, wrap
from .tokens import T

_ROW_H = T.S * 7
_CHIP_H = T.S * 6
_SLIM_H = T.S * 4             # a chip or an answer on one line, when the full ones do not fit
_BUTTON = (T.S * 24, T.S * 5)
_TONE = {"peace": T.GREEN, "fight": T.BLOOD, "next": T.BRASS}


def _foe_column(surf, F, rect, d):
    pad = T.S * 3
    x, y, w = rect.x + pad, rect.y + pad, rect.w - 2 * pad
    leader = d.get("leader")
    if leader is None:
        text(surf, F["body"], "Nobody here talks.", (x, y), T.TX_MUTED)
        return
    size = max(T.S * 8, min(T.S * 14, rect.w // 3))
    port = artwork.portrait(leader.get("race"), leader.get("portrait"), size)
    if port is not None:
        surf.blit(port, (x, y))
    else:
        smooth_circle(surf, T.STEEL_HI, (x + size // 2, y + size // 2), size // 2)
        icon = artwork.race_icon(leader.get("race"), size // 2, T.TX_MUTED)
        if icon is not None:
            surf.blit(icon, (x + size // 4, y + size // 4))
    nx = x + size + T.S * 2
    text(surf, F["name"], ellipsize(leader["name"], F["name"], rect.right - pad - nx), (nx, y + T.S), T.TX)
    caps(surf, F["micro"], leader.get("caption", ""), (nx, y + T.S * 4), T.TX_FAINT)
    y += size + T.S * 2
    for ln in wrap(F["body"], d.get("line", ""), w):
        text(surf, F["body"], ln, (x, y), T.TX)
        y += T.S * 3
    y += T.S * 2
    foes = d.get("foes", ())
    y = section(surf, F, f"facing you · {len(foes)}", x, y, w, color=T.BLOOD)
    room = max(1, (rect.bottom - pad - y) // (T.S * 3))
    shown = foes if len(foes) <= room else [*foes[:room - 1], f"and {len(foes) - room + 1} more"]
    for ln in shown:
        text(surf, F["body_sm"], ellipsize(ln, F["body_sm"], w), (x, y), T.TX_MUTED)
        y += T.S * 3


def _speakers(surf, F, x, y, w, speakers, mpos, hits, compact):
    y = section(surf, F, "who speaks", x, y, w)
    chip_h = _SLIM_H if compact else _CHIP_H
    cols = max(1, min(len(speakers), w // (T.S * (20 if compact else 26))))
    cw = (w - (cols - 1) * T.S) // cols
    for i, s in enumerate(speakers):
        r = pygame.Rect(x + (i % cols) * (cw + T.S), y + (i // cols) * (chip_h + T.S), cw, chip_h)
        hover = r.collidepoint(mpos)
        panel(surf, r, hover=hover or s.get("selected"))
        if s.get("selected"):
            pygame.draw.rect(surf, T.BRASS, r, 2)
        tcol = T.BRASS if s.get("selected") else (T.TX if hover else T.TX_MUTED)
        if compact:
            name = text(surf, F["bodyb"], ellipsize(s["name"], F["bodyb"], cw // 2), (r.x + T.S, r.y + 8), tcol)
            text(surf, F["body_sm"], ellipsize(s.get("caption", ""), F["body_sm"], r.right - T.S - name.right - T.S),
                 (name.right + T.S, r.y + 9), T.TX_FAINT)
        else:
            text(surf, F["bodyb"], ellipsize(s["name"], F["bodyb"], cw - T.S * 2), (r.x + T.S, r.y + 6), tcol)
            text(surf, F["body_sm"], ellipsize(s.get("caption", ""), F["body_sm"], cw - T.S * 2),
                 (r.x + T.S, r.y + 26), T.TX_FAINT)
        hits.append((s["id"], r))
    rows = (len(speakers) + cols - 1) // cols
    return y + rows * (chip_h + T.S) + T.S


def _check(o):
    check = o.get("check", "")
    if o.get("odds") is not None:
        check = f"{check}  ·  {round(o['odds'] * 100)}%"
    return check


def _options(surf, F, x, y, w, options, mpos, hits, compact):
    y = section(surf, F, "answer", x, y, w)
    for o in options:
        r = pygame.Rect(x, y, w, _SLIM_H if compact else _ROW_H)
        closed = bool(o.get("block"))
        hover = r.collidepoint(mpos) and not closed
        panel(surf, r, hover=hover)
        tcol = T.TX_FAINT if closed else (T.BRASS if hover else T.TX)
        sub = o.get("block") or o.get("note", "")
        scol = T.BLOOD if closed else T.TX_MUTED
        check = _check(o)
        cw = F["micro"].size(check.upper())[0] + T.S * 3 if check else 0
        if compact:
            label = caps(surf, F["bodyb"], o["label"], (r.x + T.S * 2, r.y + 8), tcol)
            text(surf, F["body_sm"], ellipsize(sub, F["body_sm"], r.right - cw - label.right - T.S * 3),
                 (label.right + T.S * 2, r.y + 9), scol)
            cy = r.y + 10
        else:
            caps(surf, F["head"], o["label"], (r.x + T.S * 2, r.y + T.S), tcol)
            text(surf, F["body_sm"], ellipsize(sub, F["body_sm"], w - T.S * 4), (r.x + T.S * 2, r.y + T.S * 4), scol)
            cy = r.y + T.S + 4
        if check:
            caps(surf, F["micro"], check, (r.right - T.S * 2, cy), T.TX_FAINT if closed else T.TX_MUTED, right=True)
        if not closed:
            hits.append((o["id"], r))
        y = r.bottom + T.S
    return y


def _fits(w, h, speakers, options):
    cols = max(1, min(len(speakers), w // (T.S * 26)))
    rows = (len(speakers) + cols - 1) // cols
    need = T.S * 3 + rows * (_CHIP_H + T.S) + T.S * 3 + T.S * 3 + len(options) * (_ROW_H + T.S)
    return need <= h


def _result(surf, F, x, y, w, result, mpos):
    tone = _TONE.get(result.get("tone"), T.BRASS)
    y = section(surf, F, "what happens", x, y, w, color=tone)
    for ln in wrap(F["body"], result["text"], w):
        text(surf, F["body"], ln, (x, y), T.TX)
        y += T.S * 3
    button = pygame.Rect(x + w - _BUTTON[0], y + T.S * 2, *_BUTTON)
    draw_button(surf, F, button, result.get("button", "GO ON"), primary=True,
                danger=result.get("tone") == "fight", mpos=mpos)
    return button


def draw_dialogue(surf, F, rect, d, mpos=(-1, -1)):
    hits = {"speakers": [], "options": [], "button": None}
    left_w = max(T.S * 30, min(T.S * 52, int(rect.w * 0.38)))
    left = pygame.Rect(rect.x, rect.y, left_w, rect.h)
    right = pygame.Rect(left.right + T.S * 2, rect.y, rect.w - left_w - T.S * 2, rect.h)
    panel(surf, left)
    _foe_column(surf, F, left, d)
    pad = T.S * 3
    x, y, w = right.x + pad, right.y + pad, right.w - 2 * pad
    panel(surf, right)
    speakers, options = d.get("speakers", ()), d.get("options", ())
    compact = not _fits(w, right.h - 2 * pad, speakers, options)
    if speakers:
        y = _speakers(surf, F, x, y, w, speakers, mpos, hits["speakers"], compact)
        hline(surf, x, x + w, y)
        y += T.S * 2
    if d.get("result"):
        hits["button"] = _result(surf, F, x, y, w, d["result"], mpos)
    else:
        _options(surf, F, x, y, w, options, mpos, hits["options"], compact)
    return hits

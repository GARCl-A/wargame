"""Combat juice for the battle screen: floating damage/heal/roll numbers and
the squash-and-hop hit/lunge reactions, both driven off the same per-frame
tick. Pure presentation state -- nothing here reads or writes battle rules,
it only watches HP deltas and drains `battle.fx_events` (the semantic-kind
pings `actions.py` queues through `battle.fx`)."""

import math
import random

import pygame

from .theme import DANGER, INK_FAINT, OK, WARN

# `battle.fx` hands back a semantic kind, not a colour -- combat state stays
# presentation-agnostic, this is the one place that maps kind -> colour.
_FX_COLORS = {"ok": OK, "crit": WARN, "faint": INK_FAINT}


def _sgn(v):
    return (v > 0) - (v < 0)


class BattleFX:
    def __init__(self):
        self._hp_seen = {}      # id(unit) -> last hp we drew
        self._floaters = []     # rising damage / heal / roll numbers
        self._react = {}        # id(unit) -> {kind, t, dur, [dir]} squash + hop

    def detect(self, battle, tile, unit_rect, cell_rect):
        """Compare each unit's HP to last frame; spawn a floating number and a
        hit reaction on a change, and a lunge on whoever is acting. Also drains
        `battle.fx_events` into floaters of their own."""
        actor = battle.active if battle.winner is None else None
        for u in battle.units:
            hp = u.hp
            prev = self._hp_seen.get(id(u))
            self._hp_seen[id(u)] = hp
            if prev is None or hp == prev:
                continue
            r = unit_rect(u)
            delta = hp - prev
            if delta < 0:
                self._spawn(r, tile, str(delta), DANGER)
                self._react[id(u)] = {"kind": "hit", "t": 0.0, "dur": 260.0}
                if actor and actor.alive and actor.team != u.team and actor is not u:
                    ax, ay = actor.pos
                    self._react[id(actor)] = {
                        "kind": "lunge", "t": 0.0, "dur": 200.0,
                        "dir": (_sgn(u.pos[0] - ax), _sgn(u.pos[1] - ay))}
            else:
                self._spawn(r, tile, f"+{delta}", OK)
                self._react[id(u)] = {"kind": "hit", "t": 0.0, "dur": 240.0}

        for pos, text_str, kind in getattr(battle, "fx_events", []):
            self._spawn(cell_rect(*pos), tile, text_str, _FX_COLORS.get(kind, INK_FAINT))
        if hasattr(battle, "fx_events"):
            battle.fx_events.clear()

    def _spawn(self, r, tile, s, color):
        stack = sum(1 for f in self._floaters
                    if abs(f["x"] - r.centerx) < tile and f["age"] < 240)
        self._floaters.append({
            "x": r.centerx + random.randint(-4, 4),
            "y": r.top - 6 - 14 * stack,
            "vy": -0.03, "age": 0.0, "hold": 140.0,
            "alpha": 255.0, "fade": 0.28, "text": s, "color": color})

    def advance(self, dt):
        for f in self._floaters:
            f["y"] += f["vy"] * dt
            f["age"] += dt
            if f["age"] > f["hold"]:
                f["alpha"] -= f["fade"] * dt
        self._floaters = [f for f in self._floaters if f["alpha"] > 0]
        for k in list(self._react):
            self._react[k]["t"] += dt
            if self._react[k]["t"] >= self._react[k]["dur"]:
                del self._react[k]

    def rect_for(self, unit, r):
        """Offset + squash `r` for `unit`'s current hit reaction (a 3px hop on a
        hit, a shove toward the target on a lunge)."""
        fx = self._react.get(id(unit))
        if not fx:
            return r
        wave = math.sin(math.pi * min(1.0, fx["t"] / fx["dur"]))
        if fx["kind"] == "lunge":
            dx, dy, sq = fx["dir"][0] * 5 * wave, fx["dir"][1] * 5 * wave, 0.09 * wave
        else:
            dx, dy, sq = 0.0, -3 * wave, 0.14 * wave
        out = pygame.Rect(0, 0, round(r.w * (1 + sq)), round(r.h * (1 - sq)))
        out.midbottom = (r.centerx + round(dx), r.bottom + round(dy))
        return out

    def draw(self, screen, fonts, clip_rect):
        clip = screen.get_clip()
        screen.set_clip(clip_rect)
        for fl in self._floaters:
            a = max(0, min(255, int(fl["alpha"])))
            img = fonts.num.render(fl["text"], True, fl["color"])
            sh = fonts.num.render(fl["text"], True, (12, 12, 16))
            img.set_alpha(a)
            sh.set_alpha(a // 2)
            rect = img.get_rect(center=(int(fl["x"]), int(fl["y"])))
            screen.blit(sh, rect.move(1, 1))
            screen.blit(img, rect)
        screen.set_clip(clip)

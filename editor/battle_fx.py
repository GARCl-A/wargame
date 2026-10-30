"""Combat juice for the battle screen: floating damage/heal/roll numbers, the
name of the action just done over its actor, the flight of a shot or a throw,
the squash-and-hop hit/lunge reactions, the hit flash, the crit banner and the
sounds, all driven off the same per-frame tick. Pure presentation state --
nothing here reads or writes battle rules, it only watches HP deltas and
drains `battle.fx_events`, `battle.cues` and `battle.acts` (the pings `actions`
queues through `battle.fx` / `battle.cue` / `battle.announce`). What the side
cannot see is heard, never shown."""

import math
import random

import pygame

from editor import sound
from editor.ui.board_style import DANGER, INK_FAINT, OK, WARN

# `battle.fx` hands back a semantic kind, not a colour -- combat state stays
# presentation-agnostic, this is the one place that maps kind -> colour.
_FX_COLORS = {"ok": OK, "crit": WARN, "faint": INK_FAINT}

FLASH_MS = 180
BANNER_MS = 1100
SHOT_MS = 200           # the missile's flight from the actor to the target
TRAIL_MS = 380          # the streak it leaves, fading
NAME_HOLD_MS = 650      # how long an action's name hangs before it fades


def _sgn(v):
    return (v > 0) - (v < 0)


class BattleFX:
    def __init__(self):
        self._hp_seen = {}      # id(unit) -> last hp we drew
        self._up_seen = {}      # id(unit) -> was it standing last frame
        self._floaters = []     # rising damage / heal / roll numbers
        self._react = {}        # id(unit) -> {kind, t, dur, [dir]} squash + hop
        self._flash = {}        # id(unit) -> ms left of its hit flash
        self.banner = None      # {"text", "t"}: the crit banner across the board
        self._shots = []        # {"a", "b", "t", "color"}: a missile in flight, then its trail

    def detect(self, battle, tile, unit_rect, cell_rect, seen=None, color_of=None):
        """Compare each unit's HP to last frame; spawn a floating number, a flash
        and a hit reaction on a change, and a lunge on whoever is acting. Also
        drains `battle.acts` into the action's name and its missile, in the actor's
        side colour (`color_of(unit)`), `battle.fx_events` into floaters and
        `battle.cues` into the crit banner. `seen(pos)` says whether the side sees
        a cell: what it does not see only makes a sound, and an action is shown
        only when its actor is seen. Each sound plays once a frame, however many hits."""
        seen = seen or (lambda pos: True)
        color_of = color_of or (lambda unit: INK_FAINT)
        for actor, name, aim in getattr(battle, "acts", []):
            if not seen(actor.pos):
                continue
            color, r = color_of(actor), unit_rect(actor)
            if aim is not None:
                self._shots.append({"a": r.center, "b": cell_rect(*aim).center, "t": 0.0, "color": color})
            if name:
                self._spawn(r, tile, name, color, font="bodyb", hold=NAME_HOLD_MS)
        if hasattr(battle, "acts"):
            battle.acts.clear()
        sounds = set()
        for kind, pos in getattr(battle, "cues", []):
            sounds.add(kind)
            if kind == "crit" and seen(pos):
                self.banner = {"text": "Critical hit", "t": 0.0}
        if hasattr(battle, "cues"):
            battle.cues.clear()

        actor = battle.active if battle.winner is None else None
        for u in battle.units:
            hp = u.hp
            up = u.alive and hp > 0
            prev = self._hp_seen.get(id(u))
            was_up = self._up_seen.get(id(u))
            self._hp_seen[id(u)] = hp
            self._up_seen[id(u)] = up
            if was_up and not up:
                sounds.add("fall")
            if prev is None or hp == prev:
                continue
            delta = hp - prev
            if delta < 0:
                sounds.add("hit")
            if not seen(u.pos):
                continue
            r = unit_rect(u)
            if delta < 0:
                self._spawn(r, tile, str(delta), DANGER)
                self._react[id(u)] = {"kind": "hit", "t": 0.0, "dur": 260.0}
                self._flash[id(u)] = FLASH_MS
                if actor and actor.alive and actor.team != u.team and actor is not u:
                    ax, ay = actor.pos
                    self._react[id(actor)] = {
                        "kind": "lunge", "t": 0.0, "dur": 200.0,
                        "dir": (_sgn(u.pos[0] - ax), _sgn(u.pos[1] - ay))}
            else:
                self._spawn(r, tile, f"+{delta}", OK)
                self._react[id(u)] = {"kind": "hit", "t": 0.0, "dur": 240.0}

        for pos, text_str, kind in getattr(battle, "fx_events", []):
            if seen(pos):
                self._spawn(cell_rect(*pos), tile, text_str, _FX_COLORS.get(kind, INK_FAINT))
        if hasattr(battle, "fx_events"):
            battle.fx_events.clear()

        if "crit" in sounds:
            sounds.discard("hit")
        for cue in sorted(sounds):
            sound.play(cue)

    def _spawn(self, r, tile, s, color, font="head", hold=140.0):
        stack = sum(1 for f in self._floaters
                    if abs(f["x"] - r.centerx) < tile and f["age"] < 240)
        self._floaters.append({
            "x": r.centerx + random.randint(-4, 4),
            "y": r.top - 6 - 14 * stack,
            "vy": -0.03, "age": 0.0, "hold": hold,
            "alpha": 255.0, "fade": 0.28, "text": s, "color": color, "font": font})

    def advance(self, dt):
        for f in self._floaters:
            f["y"] += f["vy"] * dt
            f["age"] += dt
            if f["age"] > f["hold"]:
                f["alpha"] -= f["fade"] * dt
        self._floaters = [f for f in self._floaters if f["alpha"] > 0]
        for sh in self._shots:
            sh["t"] += dt
        self._shots = [sh for sh in self._shots if sh["t"] < SHOT_MS + TRAIL_MS]
        for k in list(self._react):
            self._react[k]["t"] += dt
            if self._react[k]["t"] >= self._react[k]["dur"]:
                del self._react[k]
        self._flash = {k: ms - dt for k, ms in self._flash.items() if ms > dt}
        if self.banner is not None:
            self.banner["t"] += dt
            if self.banner["t"] >= BANNER_MS:
                self.banner = None

    def flash_for(self, unit):
        """How red `unit`'s token burns from a hit just taken: 1 at the blow, 0 when gone."""
        return max(0.0, self._flash.get(id(unit), 0) / FLASH_MS)

    def banner_alpha(self):
        """The crit banner's opacity: a quick fade in, a hold, a slower fade out."""
        if self.banner is None:
            return 0.0
        t = self.banner["t"]
        return min(1.0, t / 90, (BANNER_MS - t) / 400)

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

    def _draw_shots(self, screen, clip_rect):
        if not self._shots:
            return
        layer = pygame.Surface(clip_rect.size, pygame.SRCALPHA)
        ox, oy = clip_rect.topleft
        for sh in self._shots:
            (ax, ay), (bx, by) = sh["a"], sh["b"]
            ax, ay, bx, by = ax - ox, ay - oy, bx - ox, by - oy
            k = min(1.0, sh["t"] / SHOT_MS)
            head = (ax + (bx - ax) * k, ay + (by - ay) * k)
            fade = 1.0 - max(0.0, sh["t"] - SHOT_MS) / TRAIL_MS
            pygame.draw.line(layer, (*sh["color"], round(170 * fade)), (ax, ay), head, 3)
            if k < 1.0:
                pygame.draw.circle(layer, (*sh["color"], 255), head, 4)
                pygame.draw.circle(layer, (250, 245, 230, 255), head, 2)
        screen.blit(layer, clip_rect.topleft)

    def draw(self, screen, fonts, clip_rect):
        clip = screen.get_clip()
        screen.set_clip(clip_rect)
        self._draw_shots(screen, clip_rect)
        for fl in self._floaters:
            a = max(0, min(255, int(fl["alpha"])))
            font = fonts[fl.get("font", "head")]
            img = font.render(fl["text"], True, fl["color"])
            sh = font.render(fl["text"], True, (12, 12, 16))
            img.set_alpha(a)
            sh.set_alpha(a // 2)
            rect = img.get_rect(center=(int(fl["x"]), int(fl["y"])))
            screen.blit(sh, rect.move(1, 1))
            screen.blit(img, rect)
        screen.set_clip(clip)

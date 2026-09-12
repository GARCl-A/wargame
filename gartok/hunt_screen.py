"""The hunt: spend daylight in the wilds for meat, ambushes and all.

Reached from the map's Wilds node through the party picker (`SquadScreen`). The
screen runs in three phases, rebuilt by `app` around any ambush battle since a
fight destroys the screen:

- "setup"     -- pick a shift length, CONFIRM to head out (first stretch);
- "interlude" -- back from a won ambush with daylight left: KEEP HUNTING or HEAD BACK;
- "done"      -- the wrap-up: the haul is banked (`hunt.grant_meat`), CONTINUE to the map.

All the persistent state lives on `app._hunt` (a `hunt.HuntState`); this screen
just drives one stretch at a time and shows what happened.
"""

import pygame

from . import hunt
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP2, SP3, SURFACE_1,
                    SURFACE_2, SURFACE_3, panel, section, text,
                    token_badge, wrap_lines)


class HuntScreen(Screen):
    native = True

    def __init__(self, fonts, guild, state, phase, on_ambush, on_done, on_tick=None):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.state = state
        self.phase = phase                # "setup" | "interlude" | "done"
        self.on_ambush = on_ambush
        self.on_done = on_done
        # `app` passes the real tick (`_hunt_tick`, via `campaign.advance`,
        # keeps other groups synced); the `pass_time` fallback is test-only.
        self.on_tick = on_tick or guild.pass_time
        self.hours = hunt.HUNT_SHIFT_HOURS[1]   # default: the second option
        self.stretch_events = []          # daily-upkeep lines from the last stretch
        self.result = None                # hunt.grant_meat lines, once wrapped up
        self.chips = []                   # [(rect, hours)]
        self.buttons = []                 # [(key, rect)]
        if self.phase == "done":
            self._wrap_up()

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py) -- one card for all three phases; the risk
    # and the payoff are the same story throughout                       #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "hunt"

    def tutorial_anchor(self, size):
        """Below the (fixed-height) party row, above wherever the phase content
        starts (`body_top = H - 264` in `draw`) -- empty in all three phases,
        unlike the band right above the footer (setup's hour chips sit there)."""
        w, _h = size
        party_bottom = MARGIN + 72 + 96
        return (MARGIN, party_bottom + SP3, min(340, w - 2 * MARGIN), "down")

    # ------------------------------------------------------------------ #
    def _wrap_up(self):
        self.phase = "done"
        self.state.party = [u for u in self.state.party if u in self.guild.roster]
        if self.result is None:
            self.result = hunt.grant_meat(self.state)

    def _do_stretch(self):
        elapsed, ambushed = hunt.hunt_stretch(self.state)
        self.stretch_events = self.on_tick(elapsed)
        self.state.party = [u for u in self.state.party if u in self.guild.roster]
        if self.guild.empty or not self.state.party:
            self._wrap_up()
            return
        if ambushed:
            self.state.fights += 1
            self.on_ambush(self.state, hunt.wilds_pack())
        else:
            self._wrap_up()

    # ------------------------------------------------------------------ #
    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "confirm":
                self.state.hours_left = self.hours
                self._do_stretch()
            elif key == "hunt_on":
                self._do_stretch()
            elif key == "head_back":
                self._wrap_up()
            elif key == "done":
                self.on_done()
            return
        if self.phase == "setup":
            for rect, h in self.chips:
                if rect.collidepoint(px):
                    self.hours = h
                    return

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((17, 21, 18))
        self.chips = []
        self.buttons = []

        text(screen, "THE WILDS", f.title, INK, (MARGIN, MARGIN - 2))
        clock = self.guild.clock
        text(screen, f"{clock.label}   ·   {len(self.state.party)} in the party   ·   "
             f"meat: 1 kg per {hunt.HUNT_MEAT_HOURS} h hunted", f.body, INK_DIM,
             (MARGIN, MARGIN + 30))

        self._draw_party(screen, MARGIN + 72)

        body_top = screen.get_height() - 264
        if self.phase == "setup":
            self._draw_setup(screen, body_top)
        elif self.phase == "interlude":
            self._draw_interlude(screen, body_top)
        else:
            self._draw_done(screen, body_top)
        self._draw_footer(screen)

    # ------------------------------------------------------------------ #
    def _draw_party(self, screen, top):
        f = self.fonts
        party = self.state.party
        n = max(1, len(party))
        gap = SP3
        card_w = min(240, (screen.get_width() - 2 * MARGIN - (n - 1) * gap) // n)
        card_h = 96
        for i, u in enumerate(party):
            rect = pygame.Rect(MARGIN + i * (card_w + gap), top, card_w, card_h)
            panel(screen, rect, fill=SURFACE_2, border=LINE_SOFT, radius=RADIUS)
            pad = SP3
            tok = (rect.x + pad + 12, rect.y + pad + 12)
            token_badge(screen, tok, u, f)
            text(screen, u.name, f.card_name, INK, (tok[0] + 24, rect.y + pad))
            text(screen, f"{u.race['name']}  ·  {u.occupation['name']}", f.body_sm,
                 INK_DIM, (tok[0] + 24, rect.y + pad + 20))
            y = rect.y + pad + 46
            text(screen, f"{u.rations} rations", f.mono_sm, OK, (rect.x + pad, y))
            text(screen, f"{u.work_xp} work XP", f.mono_sm, INFO,
                 (rect.right - pad, y), right=True)

    def _draw_setup(self, screen, top):
        f = self.fonts
        w = screen.get_width() - 2 * MARGIN
        top = section(screen, "HOW LONG", MARGIN, top, w, f)
        gap = SP2
        opts = hunt.HUNT_SHIFT_HOURS
        cw = (w - (len(opts) - 1) * gap) // len(opts)
        for i, h in enumerate(opts):
            r = pygame.Rect(MARGIN + i * (cw + gap), top, cw, 56)
            sel = h == self.hours
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if (sel or hov) else SURFACE_1,
                  border=ACCENT if sel else LINE_SOFT, width=2 if sel else 1,
                  radius=RADIUS)
            text(screen, f"{h} h", f.body_bd, ACCENT if sel else INK,
                 (r.x + SP2, r.y + 8))
            text(screen, f"~{h // hunt.HUNT_MEAT_HOURS} kg meat", f.body_sm, INK_DIM,
                 (r.x + SP2, r.y + 30))
            self.chips.append((r, h))
        top += 66
        odds = round(hunt.AMBUSH_CHANCE_PER_HOUR * 100)
        text(screen, f"{odds}% chance each hour that a pack finds you first -- "
             f"a scaled fight, lethal, but the bodies are worth looting.",
             f.body_sm, INK_FAINT, (MARGIN, top))

    def _draw_interlude(self, screen, top):
        f = self.fonts
        w = screen.get_width() - 2 * MARGIN
        top = section(screen, "THE HUNT GOES ON", MARGIN, top, w, f)
        text(screen, f"Pack driven off. {self.state.hours_left} h of daylight left, "
             f"{self.state.meat} kg of meat so far.", f.body, INK_DIM, (MARGIN, top))
        top += 24
        self._draw_events(screen, top)

    def _draw_done(self, screen, top):
        f = self.fonts
        w = screen.get_width() - 2 * MARGIN
        top = section(screen, "BACK FROM THE WILDS", MARGIN, top, w, f)
        for ln in self.result or []:
            text(screen, ln, f.body_sm, OK if "meat" in ln else INFO, (MARGIN, top))
            top += 16
        top += 8
        self._draw_events(screen, top)

    def _draw_events(self, screen, top):
        f = self.fonts
        w = screen.get_width() - 2 * MARGIN
        for ln in self.stretch_events:
            for wln in wrap_lines([ln], f.body_sm, w):
                col = DANGER if "starved" in ln or "did not eat" in ln else INK_FAINT
                text(screen, wln, f.body_sm, col, (MARGIN, top))
                top += 16

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen):
        f = self.fonts
        y = screen.get_height() - 56
        right = screen.get_width() - MARGIN

        def button(key, label, x, wide=240, primary=True):
            r = pygame.Rect(x, y, wide, 36)
            hov = r.collidepoint(self.mouse)
            if primary:
                panel(screen, r, fill=ACCENT if hov else SURFACE_3, border=ACCENT,
                      width=1, radius=RADIUS)
                text(screen, label, f.body_bd, ACCENT_INK if hov else ACCENT,
                     r.center, center=True)
            else:
                panel(screen, r, fill=SURFACE_3 if hov else SURFACE_2,
                      border=LINE_SOFT, width=1, radius=RADIUS)
                text(screen, label, f.body, INK if hov else INK_DIM,
                     r.center, center=True)
            self.buttons.append((key, r))

        if self.phase == "setup":
            button("confirm", "INTO THE WILDS", right - 240)
        elif self.phase == "interlude":
            button("hunt_on", "KEEP HUNTING", right - 240)
            button("head_back", "HEAD BACK", MARGIN, wide=160, primary=False)
        else:
            button("done", "CONTINUE", right - 240)

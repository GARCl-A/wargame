"""The hunt: spend daylight in the wilds for meat, ambushes and all.

Reached from the map's Wilds node through the party picker (`SquadScreen`). The
screen runs in three phases, rebuilt by `app` around any ambush battle since a
fight destroys the screen:

- "setup"     -- pick a shift length, CONFIRM to head out (first stretch) or LEAVE;
- "interlude" -- back from a won ambush with daylight left: KEEP HUNTING or HEAD BACK;
- "done"      -- the wrap-up: the haul is banked (`hunt.grant_meat`), CONTINUE to the map.

All the persistent state lives on `app._hunt` (a `hunt.HuntState`); this screen
just drives one stretch at a time and shows what happened.
"""

import pygame

from . import autowin, hunt, ox
from .scenario import Scenario
from .screen import Screen
from .ui.primitives import (
    caps,
    draw_button,
    footer_bar,
    panel,
    section,
    text,
    wrap,
)
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class HuntScreen(Screen):
    native = True

    def __init__(self, fonts, guild, state, phase, on_ambush, on_done, on_tick=None, on_autowin=None):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.state = state
        self.phase = phase                # "setup" | "interlude" | "ambush" | "done"
        self.on_ambush = on_ambush
        self.on_done = on_done
        self.on_autowin = on_autowin
        self.ambush_pack = None
        self.autowin_estimator = autowin.AutoWinEstimator()
        # `app` passes the real tick (`_hunt_tick`, via `campaign.advance`,
        # keeps other groups synced); the `pass_time` fallback is test-only.
        self.on_tick = on_tick or guild.pass_time
        shifts = ox.TRACK_SHIFT_HOURS if state.target == "ox" else hunt.HUNT_SHIFT_HOURS
        self.hours = shifts[1]            # default: the second option
        self.stretch_events = []          # daily-upkeep lines from the last stretch
        self.result = None                # hunt.grant_haul lines, once wrapped up
        self.chips = []                   # [(rect, hours)]
        self.target_chips = []            # [(rect, target_str)]
        self.buttons = []                 # [(key, rect)]
        self._hot = False
        if self.phase == "done":
            self._wrap_up()

    def _reset_buttons(self):
        self.buttons = []
        self._hot = False

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False,
                   danger=False, font=None, sub=None):
        """Draws through `ui.primitives.draw_button` and tracks button hit rects."""
        draw_button(surf, self._F, rect, label, sub=sub, primary=primary, danger=danger,
                   enabled=enabled, mpos=self.mouse, fnt=font)
        hov = enabled and rect.collidepoint(self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or hov
        return hov

    # ------------------------------------------------------------------ #
    # tutorial (screen.py) -- one card for all three phases; the risk
    # and the payoff are the same story throughout                       #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "hunt"

    def tutorial_badge_rect(self, size):
        W, H = size
        m = T.S * 3
        return pygame.Rect(W - m - 28, m - 4, 28, 28)

    # ------------------------------------------------------------------ #
    def _wrap_up(self):
        self.phase = "done"
        self.state.party = [u for u in self.state.party if u in self.guild.roster]
        if self.result is None:
            self.result = hunt.grant_haul(self.state)

    @property
    def _tracking(self):
        return self.state.target == "ox"

    def _daylight(self):
        return ox.daylight_hours(self.guild.clock.hour_of_day)

    def _do_track(self):
        elapsed, found = ox.track(self.state, self.guild)
        res = self.on_tick(elapsed)
        self.stretch_events = res[0] if isinstance(res, tuple) else (res or [])
        self.state.party = [u for u in self.state.party if u in self.guild.roster]
        if self.guild.empty or not self.state.party:
            self._wrap_up()
        elif found:
            self.state.fights += 1
            self.ambush_pack = ox.aurochs_pack()
            self.phase = "ambush"
        else:
            self._wrap_up()

    def _do_stretch(self):
        if self._tracking:
            self._do_track()
            return
        clock = self.guild.clock
        lure = hunt.biwolf_lure(self.guild, self.state.party)
        self.state.biwolf = False
        elapsed, ambushed = hunt.hunt_stretch(self.state, hour=clock.hour_of_day, lure=lure)
        res = self.on_tick(elapsed)
        self.stretch_events = res[0] if isinstance(res, tuple) else (res or [])
        self.state.party = [u for u in self.state.party if u in self.guild.roster]
        if self.guild.empty or not self.state.party:
            self._wrap_up()
            return
        if ambushed:
            self.state.fights += 1
            self.ambush_pack = hunt.biwolf_pack(self.guild) if self.state.biwolf else hunt.wilds_pack()
            self.phase = "ambush"
            scen = self.state.node.scenario() if self.state.node.scenario else Scenario()
            self.autowin_estimator.request(self.state.party, self.ambush_pack,
                                           scenario=scen,
                                           daylight=self.guild.clock.is_daylight,
                                           lethal=self.state.node.lethal)
        else:
            self._wrap_up()

    # ------------------------------------------------------------------ #
    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "confirm":
                self.state.hours_left = min(self.hours, self._daylight()) if self._tracking else self.hours
                self._do_stretch()
            elif key == "hunt_on":
                self._do_stretch()
            elif key == "leave":
                self.on_done()
            elif key == "head_back":
                self._wrap_up()
            elif key == "fight_ambush":
                self.on_ambush(self.state, self.ambush_pack)
            elif key == "autowin_ambush":
                if self.on_autowin and self.autowin_estimator.result:
                    self.on_autowin(self.state, self.ambush_pack, self.autowin_estimator.result)
            elif key == "done":
                self.on_done()
            return
        if self.phase == "setup":
            for rect, h in self.chips:
                if rect.collidepoint(px):
                    self.hours = h
                    return
            for rect, t in self.target_chips:
                if rect.collidepoint(px):
                    self.state.target = t
                    return

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._F
        m = T.S * 3
        screen.fill(T.TABLE)
        self.chips = []
        self.target_chips = []
        self._reset_buttons()

        text(screen, F["titleb"], "THE OX FIELDS" if self._tracking else "THE WILDS", (m, m - 2), T.TX)
        clock = self.guild.clock
        y = hunt.party_yield(len(self.state.party))
        if self._tracking:
            best = max((u.mod_wisdom for u in self.state.party), default=0)
            yields = f"best tracker: Wisdom {best:+d}"
        else:
            yields = (f"meat: {y / hunt.HUNT_MEAT_HOURS:.2f} kg per hour for the party" if self.state.target == "meat"
                      else f"forage: {y:.2f}x the usual finds for the party")
        if self.state.ambush_mult != 1.0:
            yields += f"   ·   ambush chance x{self.state.ambush_mult:.2f} (cautious)"
        text(screen, F["body"], f"{clock.label}   ·   {len(self.state.party)} in the party   ·   {yields}",
             (m, m + 30), T.TX_MUTED)

        self._draw_party(screen, m + 72)

        body_top = screen.get_height() - 264
        if self.phase == "setup":
            self._draw_setup(screen, body_top)
        elif self.phase == "interlude":
            self._draw_interlude(screen, body_top)
        elif self.phase == "ambush":
            self._draw_ambush(screen, body_top)
        else:
            self._draw_done(screen, body_top)
        self._draw_footer(screen)

    # ------------------------------------------------------------------ #
    def _draw_party(self, screen, top):
        from .combatant import Combatant
        from .ui.sheet_card import draw_row, unit_to_ch

        F = self._F
        pad = T.S * 3
        w = screen.get_width() - 2 * pad
        party = self.state.party
        
        col_w = (w - T.S * 2) // 2
        
        def _trailing(surf, r, ch):
            u = ch["unit"]
            caps(surf, F["micro"], f"{u.rations} RATIONS", (r.right - T.S * 2, r.centery - 10), T.GREEN, right=True)
            caps(surf, F["micro"], f"{u.work_xp} WORK XP", (r.right - T.S * 2, r.centery + 10), T.BRASS, right=True)
            
        for i, u in enumerate(party):
            col = i % 2
            row_idx = i // 2
            rect = pygame.Rect(pad + col * (col_w + T.S * 2), top + row_idx * (74 + T.S), col_w, 74)
            c = Combatant(u)
            draw_row(screen, F, rect, unit_to_ch(c), draw_trailing=_trailing)

    def _draw_tracking_setup(self, screen, top):
        F = self._F
        m = T.S * 3
        w = screen.get_width() - 2 * m
        daylight = self._daylight()
        top = section(screen, F, "HOW LONG TO READ THE GROUND", m, top, w)
        opts = [h for h in ox.TRACK_SHIFT_HOURS if h <= daylight] or [0]
        self.hours = min(self.hours, max(opts))
        gap = T.S
        cw = (w - (len(opts) - 1) * gap) // len(opts)
        for i, h in enumerate(opts):
            r = pygame.Rect(m + i * (cw + gap), top, cw, 56)
            sel = h == self.hours
            panel(screen, r, hover=sel or r.collidepoint(self.mouse), width=2 if sel else 1)
            text(screen, F["bodyb"], f"{h} h", (r.x + T.S, r.y + 8), T.BRASS if sel else T.TX)
            text(screen, F["body_sm"], f"{h} Wisdom check{'s' * (h != 1)}", (r.x + T.S, r.y + 30), T.TX_MUTED)
            self.chips.append((r, h))
        top += 66
        dc = ox.track_dc(self.guild)
        text(screen, F["body_sm"], f"One check an hour against DC {dc}; a found trail opens the field and "
             f"makes the next DC {dc + ox.TRACK_DC_STEP}.", (m, top), T.TX_FAINT)
        top += 18
        note = ("The tracks can only be read by daylight." if daylight else
                "Too dark to read the ground -- come back at dawn.")
        text(screen, F["body_sm"], note, (m, top), T.TX_FAINT if daylight else T.BLOOD)

    def _draw_setup(self, screen, top):
        if self._tracking:
            self._draw_tracking_setup(screen, top)
            return
        F = self._F
        m = T.S * 3
        w = screen.get_width() - 2 * m
        
        # Target section
        top = section(screen, F, "WHAT TO LOOK FOR", m, top, w)
        gap = T.S
        tw = (w - gap) // 2
        
        rect_meat = pygame.Rect(m, top, tw, 56)
        sel_meat = self.state.target == "meat"
        panel(screen, rect_meat, hover=sel_meat or rect_meat.collidepoint(self.mouse), width=2 if sel_meat else 1)
        text(screen, F["bodyb"], "HUNT FOR MEAT", (rect_meat.x + T.S, rect_meat.y + 8), T.BRASS if sel_meat else T.TX)
        text(screen, F["body_sm"], "Guaranteed 1 kg per 2 hours", (rect_meat.x + T.S, rect_meat.y + 30), T.TX_FAINT)
        self.target_chips.append((rect_meat, "meat"))
        
        rect_shrooms = pygame.Rect(m + tw + gap, top, tw, 56)
        sel_shrooms = self.state.target == "shrooms"
        panel(screen, rect_shrooms, hover=sel_shrooms or rect_shrooms.collidepoint(self.mouse), width=2 if sel_shrooms else 1)
        text(screen, F["bodyb"], "FORAGE WILDS", (rect_shrooms.x + T.S, rect_shrooms.y + 8), T.BRASS if sel_shrooms else T.TX)
        text(screen, F["body_sm"], "Mushrooms & fresh fruits", (rect_shrooms.x + T.S, rect_shrooms.y + 30), T.TX_FAINT)
        self.target_chips.append((rect_shrooms, "shrooms"))
        
        top += 66
        
        top = section(screen, F, "HOW LONG", m, top, w)
        opts = hunt.HUNT_SHIFT_HOURS
        cw = (w - (len(opts) - 1) * gap) // len(opts)
        for i, h in enumerate(opts):
            r = pygame.Rect(m + i * (cw + gap), top, cw, 56)
            sel = h == self.hours
            hov = r.collidepoint(self.mouse)
            panel(screen, r, hover=sel or hov, width=2 if sel else 1)
            text(screen, F["bodyb"], f"{h} h", (r.x + T.S, r.y + 8), T.BRASS if sel else T.TX)
            
            if self.state.target == "meat":
                sub = f"~{int(h * hunt.party_yield(len(self.state.party)) // hunt.HUNT_MEAT_HOURS)} kg meat"
            else:
                sub = "Mushrooms & Fruits"
            text(screen, F["body_sm"], sub, (r.x + T.S, r.y + 30), T.TX_MUTED)
            self.chips.append((r, h))
        top += 66
        odds = round(hunt.AMBUSH_CHANCE_PER_HOUR * 100)
        text(screen, F["body_sm"], f"{odds}% chance each hour that a pack finds you first -- "
             f"a scaled fight, lethal, but the bodies are worth looting.",
             (m, top), T.TX_FAINT)

    def _draw_interlude(self, screen, top):
        F = self._F
        m = T.S * 3
        w = screen.get_width() - 2 * m
        top = section(screen, F, "THE HUNT GOES ON", m, top, w)
        if self.state.target == "meat":
            tally = f"{self.state.meat} kg of meat so far."
        else:
            tally = (f"{self.state.shrooms_found} mushroom(s) and "
                     f"{self.state.fruit_found} fruit(s) so far.")
        text(screen, F["body"], f"Pack driven off. {self.state.hours_left} h of daylight left, "
             f"{tally}", (m, top), T.TX_MUTED)
        top += 24
        self._draw_events(screen, top)

    def _draw_done(self, screen, top):
        F = self._F
        m = T.S * 3
        w = screen.get_width() - 2 * m
        top = section(screen, F, "THE TRAIL GOES COLD" if self._tracking else "BACK FROM THE WILDS", m, top, w)
        for ln in self.result or []:
            text(screen, F["body_sm"], ln, (m, top), T.GREEN if ("meat" in ln or "bring back" in ln) else T.BRASS)
            top += 16
        top += 8
        self._draw_events(screen, top)

    def _draw_ambush(self, screen, top):
        F = self._F
        m = T.S * 3
        w = screen.get_width() - 2 * m
        if self._tracking:
            top = section(screen, F, "THE TRAIL IS FRESH!", m, top, w)
            text(screen, F["bodyb"], "Aurochs is grazing somewhere on the open fields ahead.", (m, top), T.BLOOD)
            top += 24
            text(screen, F["body_sm"], "A lethal chase: he runs from anyone near. Pin him in a canyon "
                 "and bring him down -- and every few rounds the herd answers his call.", (m, top), T.TX_MUTED)
            top += 24
            self._draw_events(screen, top)
            return
        top = section(screen, F, "THE BIWOLF!" if self.state.biwolf else "AMBUSH IN THE WILDS!", m, top, w)
        if self.state.biwolf:
            text(screen, F["body_sm"], "The smell of your meat drew it out of the dark.", (m, top), T.TX_FAINT)
            top += 20
        n = len(self.ambush_pack or [])
        enemies_desc = ", ".join(u.name for u in (self.ambush_pack or []))
        text(screen, F["bodyb"], f"A pack of {n} hostile{'s' if n > 1 else ''} intercepted the party!", (m, top), T.BLOOD)
        top += 24
        text(screen, F["body"], f"Enemies: {enemies_desc}", (m, top), T.TX)
        top += 24
        text(screen, F["body_sm"], "A lethal fight -- victory leaves the field to loot.", (m, top), T.TX_MUTED)
        top += 24
        self._draw_events(screen, top)

    def _draw_events(self, screen, top):
        F = self._F
        m = T.S * 3
        w = screen.get_width() - 2 * m
        for ln in self.stretch_events:
            for wln in wrap(F["body_sm"], ln, w):
                col = T.BLOOD if "starved" in ln or "did not eat" in ln else T.TX_FAINT
                text(screen, F["body_sm"], wln, (m, top), col)
                top += 16

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen):
        if self.phase == "setup":
            footer_bar(self, screen, self._F, back=("leave", "LEAVE"),
                       primary=("confirm", "READ THE GROUND" if self._tracking else "INTO THE WILDS",
                                not self._tracking or self._daylight() > 0))
        elif self.phase == "interlude":
            footer_bar(self, screen, self._F, back=("head_back", "HEAD BACK"),
                      primary=("hunt_on", "KEEP HUNTING"))
        elif self.phase == "ambush":
            sec = None
            if self._tracking:
                footer_bar(self, screen, self._F, primary=("fight_ambush", "FOLLOW THE TRAIL"), danger=True)
                return
            if self.autowin_estimator.result and self.autowin_estimator.result.eligible:
                sec = ("autowin_ambush", "AUTO-WIN (100% - NO XP)")
            n = len(self.ambush_pack or [])
            footer_bar(self, screen, self._F, secondary=sec,
                       primary=("fight_ambush", f"FIGHT ({n})"),
                       danger=True)
        else:
            footer_bar(self, screen, self._F, primary=("done", "CONTINUE"))


class TrackScreen(HuntScreen):
    """The same screen, tracking Aurochs (`HuntState.target == "ox"`): its own card."""

    def tutorial_key(self):
        return "ox_hunt"

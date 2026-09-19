"""The Wilds claim: [[gartok-property-two-paths]]'s "Wilds" path -- scout,
clear, fence, sweep, sustain, established. Six stages
(`guild.WILDS_CLAIM_STAGES`), each its own small mechanic; this screen is
just the front end for whichever one is next. The two fights (`CLEAR`,
`SWEEP`) leave the screen entirely -- `on_fight_clear`/`on_fight_sweep` hand
off to `app`, which drops the present group into a real `BattleScreen` and
comes back to the map, not this screen, once it resolves (`App._battle_end`'s
own `_claim_stage_pending` hook advances the stage on a win). Everything else
(scouting, hauling Lumber, raising fences, garrisoning) resolves right here,
same idiom `bank_screen`/`city_property_screen` use for a flat action.
"""

import pygame

from . import data, economy, orders
from .screen import Screen
from .theme import set_pointer, token_badge
from .ui.primitives import (caps, draw_button, header, hline, text, token_badge)
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class WildsClaimScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, on_done, on_fight_clear, on_fight_sweep):
        super().__init__()
        self.fonts = fonts
        self._F = None
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.on_fight_clear = on_fight_clear
        self.on_fight_sweep = on_fight_sweep
        self.notice = None
        self.buttons = []

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

    def tutorial_key(self):
        return None

    # ------------------------------------------------------------------ #
    def _party_lumber(self):
        return sum(m.count_of("Lumber") for m in self.group.members)

    def _deposit_lumber(self):
        total = 0
        for m in self.group.members:
            n = m.count_of("Lumber")
            if n:
                m.remove_named("Lumber", n)
                total += n
                m._derive_combat()
        if total:
            self.guild.wilds_claim_deposit_lumber(total)
            self.notice = f"deposited {total} Lumber toward the fences."
        else:
            self.notice = "nobody here is carrying Lumber."

    def _collect_lumber(self):
        stock = self.guild.garrison_stock.setdefault(self.group.node, [])
        taken = 0
        for m in self.group.members:
            while stock and m.load + data.item_weight("Lumber") <= m.carry_max:
                stock.pop()
                m.give_to_pack("Lumber")
                m._derive_combat()
                taken += 1
        self.notice = (f"collected {taken} Lumber." if taken
                       else "no room to carry any Lumber right now.")

    # ------------------------------------------------------------------ #
    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            {
                "done": self.on_done,
                "scout": self._scout,
                "fight_clear": lambda: self.on_fight_clear(self.group),
                "deposit": self._deposit_lumber,
                "build": self._build_fences,
                "fight_sweep": lambda: self.on_fight_sweep(self.group),
                "garrison": self._start_garrison,
                "leave_garrison": self._leave_garrison,
                "collect": self._collect_lumber,
            }[key]()
            return

    def _scout(self):
        events, cas = self.guild.pass_time(economy.WILDS_CLAIM_SCOUT_HOURS)
        self.guild.wilds_claim_scout()
        self.notice = "  ".join(["the land is scouted -- ready to clear."] + events)

    def _build_fences(self):
        if self.guild.wilds_claim_fence_lumber < economy.WILDS_CLAIM_FENCE_LUMBER:
            return
        events, cas = self.guild.pass_time(economy.WILDS_CLAIM_FENCE_HOURS)
        self.guild.wilds_claim_build_fences()
        self.notice = "  ".join(["the fences go up -- time to sweep the region."] + events)

    def _start_garrison(self):
        self.group.order = orders.garrison("lumber")
        self.guild.wilds_claim_start_sustaining()
        self.on_done()

    def _leave_garrison(self):
        if self.group.order is not None and self.group.order.kind == "garrison":
            self.group.order = orders.idle()
        self.notice = "the garrison stands down -- sustaining the claim starts over."

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.buttons = []

        head = pygame.Rect(0, 0, W, T.S * 9)
        stage = self.guild.wilds_claim_stage
        header(screen, F, head, "THE WILDS CLAIM", f"stage: {stage.title()}", (), None, mpos=self.mouse)

        top = head.bottom + T.S * 4
        panel_w = min(640, W - 2 * T.S * 3)

        {
            "NONE": self._draw_scout,
            "SCOUTED": self._draw_clear,
            "CLEARED": self._draw_fence,
            "FENCED": self._draw_sweep,
            "SWEPT": self._draw_garrison,
            "SUSTAINING": self._draw_sustaining,
            "ESTABLISHED": self._draw_established,
        }[stage](screen, F, T.S * 3, top, panel_w)

        self._draw_party(screen, F, panel_w, W, H)
        self._draw_footer(screen, F, W, H)

        set_pointer(any(r.collidepoint(self.mouse) for _, r in self.buttons))

    def _draw_party(self, screen, F, panel_w, W, H):
        from .combatant import Combatant
        from .ui.sheet_card import draw_row, unit_to_ch
        
        x = T.S * 3
        y = H - T.S * 20
        hline(screen, x, x + panel_w, y - T.S * 2)
        caps(screen, F["microb"], f"HERE ({len(self.group.members)})", (x, y), T.TX_FAINT)
        y += T.S * 3
        
        # Two columns if needed, but since it's a fixed y=H-T.S*20, let's use columns to fit.
        # But wait, y=H-320 means we have ~250px left (H - 320 to H - 70).
        # We can fit 3 rows of 74px + gap vertically.
        # I'll just use a 2-column grid.
        col_w = (panel_w - T.S * 2) // 2
        for i, m in enumerate(self.group.members):
            col = i % 2
            row_idx = i // 2
            r = pygame.Rect(x + col * (col_w + T.S * 2), y + row_idx * (74 + T.S), col_w, 74)
            c = Combatant(m)
            draw_row(screen, F, r, unit_to_ch(c))

    def _draw_footer(self, screen, F, W, H):
        d = pygame.Rect(W - T.S * 3 - 240, H - T.S * 4 - 36, 240, 36)
        draw_button(screen, F, d, "LEAVE", primary=False, mpos=self.mouse)
        self.buttons.append(("done", d))

        if self.notice:
            img = F["body_sm"].render(self.notice, True, T.BRASS)
            r = img.get_rect()
            r.midright = (d.left - T.S * 3, d.centery)
            screen.blit(img, r)

    # ------------------------------------------------------------------ #
    # per-stage panels                                                    #
    # ------------------------------------------------------------------ #
    def _button(self, screen, F, key, label, top, w, enabled=True):
        r = pygame.Rect(T.S * 3, top, w, 40)
        draw_button(screen, F, r, label, primary=True, enabled=enabled, mpos=self.mouse)
        if enabled:
            self.buttons.append((key, r))
        return r.bottom + T.S * 2

    def _draw_scout(self, screen, F, x, y, w):
        for ln in ("The land isn't scouted yet -- someone has to walk it before ",
                   "the guild can do anything else here.",
                   f"Costs {economy.WILDS_CLAIM_SCOUT_HOURS} h. No fight, no roll."):
            text(screen, F["body_sm"], ln, (x, y), T.TX_MUTED)
            y += 17
        y += T.S * 2
        self._button(screen, F, "scout", "SCOUT THE LAND", y, w)

    def _draw_clear(self, screen, F, x, y, w):
        for ln in ("Scouted. Something already lives here -- clear it out before ",
                   "building anything.",
                   f"A real fight: {economy.WILDS_CLAIM_CLEAR_SIZE} opponents, ",
                   f"level {economy.WILDS_CLAIM_CLEAR_LEVEL}."):
            text(screen, F["body_sm"], ln, (x, y), T.TX_MUTED)
            y += 17
        y += T.S * 2
        self._button(screen, F, "fight_clear", "CLEAR THE LAND", y, w)

    def _draw_fence(self, screen, F, x, y, w):
        have = self.guild.wilds_claim_fence_lumber
        need = economy.WILDS_CLAIM_FENCE_LUMBER
        carried = self._party_lumber()
        text(screen, F["body_sm"], "Cleared. Raise fences to hold the ground -- hauls Lumber "
             "bought at the Market, no mechanical cover yet.", (x, y), T.TX_MUTED)
        y += 24
        text(screen, F["bodyb"], f"Lumber banked: {have} / {need}", (x, y), T.GREEN if have >= need else T.TX)
        y += 20
        text(screen, F["body_sm"], f"{carried} Lumber carried here right now", (x, y), T.TX_FAINT)
        y += T.S * 2 + 10
        y = self._button(screen, F, "deposit", "DEPOSIT CARRIED LUMBER", y, w, enabled=carried > 0)
        self._button(screen, F, "build", f"BUILD THE FENCES ({economy.WILDS_CLAIM_FENCE_HOURS} h)", y, w, enabled=have >= need)

    def _draw_sweep(self, screen, F, x, y, w):
        for ln in ("Fenced. One more pass -- root out any nest or bandit camp ",
                   "still close enough to matter.",
                   f"A second fight: {economy.WILDS_CLAIM_SWEEP_SIZE} opponents, ",
                   f"level {economy.WILDS_CLAIM_SWEEP_LEVEL}."):
            text(screen, F["body_sm"], ln, (x, y), T.TX_MUTED)
            y += 17
        y += T.S * 2
        self._button(screen, F, "fight_sweep", "SWEEP THE REGION", y, w)

    def _draw_garrison(self, screen, F, x, y, w):
        for ln in ("Swept clean. The claim only counts once someone holds it --",
                   " garrison this group here and sustain it.",
                   f"{economy.WILDS_CLAIM_SUSTAIN_DAYS} days, uninterrupted. A ",
                   "lost raid or pulling out early starts the count over."):
            text(screen, F["body_sm"], ln, (x, y), T.TX_MUTED)
            y += 17
        y += T.S * 2
        self._button(screen, F, "garrison", "GARRISON HERE", y, w)

    def _draw_sustaining(self, screen, F, x, y, w):
        left = self.guild.wilds_claim_sustain_days_left
        garrisoned = self.guild._wilds_claim_garrisoned()
        text(screen, F["bodyb"], f"Sustaining -- {left} day(s) left." if left is not None else "Sustaining.", (x, y), T.BRASS)
        y += 22
        if not garrisoned:
            text(screen, F["body_sm"], "Nobody is garrisoned here right now -- the countdown isn't moving.", (x, y), T.BLOOD)
            y += 20
        y += T.S
        if self.group.order is not None and self.group.order.kind == "garrison":
            self._button(screen, F, "leave_garrison", "STAND DOWN THE GARRISON", y, w)

    def _draw_established(self, screen, F, x, y, w):
        if self.guild.wilds_claim_owner == "seized":
            for ln in ("SEIZED. Occupiers hold the claim right now -- the ",
                       "structure still stands, it's just not the guild's to work.",
                       "Travel a group here to fight for it back -- no need to ",
                       "redo the campaign, only to retake the ground."):
                text(screen, F["body_sm"], ln, (x, y), T.BLOOD)
                y += 17
            return
        text(screen, F["body_sm"], "Established. The land is the guild's -- the garrison keeps working it on its own.", (x, y), T.GREEN)
        y += 24
        stock = self.guild.garrison_stock_at(self.group.node)
        hline(screen, x, x + w, y)
        y += T.S
        caps(screen, F["microb"], f"BANKED HERE  ({len(stock)})", (x, y), T.TX_FAINT)
        y += T.S * 3
        if stock:
            text(screen, F["body"], f"{len(stock)} x Lumber", (x, y), T.TX)
            y += 20
        else:
            text(screen, F["body_sm"], "(nothing banked yet)", (x, y), T.TX_FAINT)
            y += 20
        y += T.S * 2
        self._button(screen, F, "collect", "COLLECT LUMBER", y, w, enabled=bool(stock))

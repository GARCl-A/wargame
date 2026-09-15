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
from .theme import (ACCENT, DANGER, INK, INK_DIM, INK_FAINT,
                    MARGIN, OK, SP1, SP2, WARN, section, text, token_badge)
from .widgets import ButtonsMixin, footer_bar


class WildsClaimScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, group, on_done, on_fight_clear, on_fight_sweep):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.on_fight_clear = on_fight_clear
        self.on_fight_sweep = on_fight_sweep
        self.notice = None
        self.buttons = []
        self._hot = False

    def tutorial_key(self):
        return None

    # ------------------------------------------------------------------ #
    def _party_lumber(self):
        return sum(m._base_inventory.count("Lumber") for m in self.group.members)

    def _deposit_lumber(self):
        total = 0
        for m in self.group.members:
            n = m._base_inventory.count("Lumber")
            if n:
                m._base_inventory = [it for it in m._base_inventory if it != "Lumber"]
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
                m._base_inventory.append("Lumber")
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
        f = self.fonts
        screen.fill((18, 22, 18))
        self._reset_buttons()

        text(screen, "THE WILDS CLAIM", f.title, INK, (MARGIN, MARGIN - 2))
        stage = self.guild.wilds_claim_stage
        text(screen, f"stage: {stage.title()}", f.body_bd, ACCENT, (MARGIN, MARGIN + 30))

        top = MARGIN + 70
        panel_w = min(640, screen.get_width() - 2 * MARGIN)
        {
            "NONE": self._draw_scout,
            "SCOUTED": self._draw_clear,
            "CLEARED": self._draw_fence,
            "FENCED": self._draw_sweep,
            "SWEPT": self._draw_garrison,
            "SUSTAINING": self._draw_sustaining,
            "ESTABLISHED": self._draw_established,
        }[stage](screen, MARGIN, top, panel_w)

        self._draw_party(screen, panel_w)
        self._draw_footer(screen)

    def _draw_party(self, screen, panel_w):
        f = self.fonts
        x = MARGIN
        y = screen.get_height() - 200
        y = section(screen, f"HERE ({len(self.group.members)})", x, y, panel_w, f)
        for m in self.group.members:
            tok = (x + 12, y + 10)
            token_badge(screen, tok, m, f)
            text(screen, m.name, f.body_sm, INK, (tok[0] + 20, y))
            y += 22

    def _draw_footer(self, screen):
        footer_bar(self, screen, primary=("done", "LEAVE"), notice=self.notice,
                  notice_color=ACCENT)

    # ------------------------------------------------------------------ #
    # per-stage panels                                                    #
    # ------------------------------------------------------------------ #
    def _button(self, screen, key, label, top, w, *, enabled=True):
        r = pygame.Rect(MARGIN, top, w, 40)
        self.add_button(screen, r, key, label, enabled=enabled, primary=True)
        return r.bottom + SP2

    def _draw_scout(self, screen, x, y, w):
        f = self.fonts
        for ln in ("The land isn't scouted yet -- someone has to walk it before "
                   "the guild can do anything else here.",
                   f"Costs {economy.WILDS_CLAIM_SCOUT_HOURS} h. No fight, no roll."):
            text(screen, ln, f.body_sm, INK_DIM, (x, y))
            y += 17
        y += SP2
        self._button(screen, "scout", "SCOUT THE LAND", y, w)

    def _draw_clear(self, screen, x, y, w):
        f = self.fonts
        for ln in ("Scouted. Something already lives here -- clear it out before "
                   "building anything.",
                   f"A real fight: {economy.WILDS_CLAIM_CLEAR_SIZE} opponents, "
                   f"level {economy.WILDS_CLAIM_CLEAR_LEVEL}."):
            text(screen, ln, f.body_sm, INK_DIM, (x, y))
            y += 17
        y += SP2
        self._button(screen, "fight_clear", "CLEAR THE LAND", y, w)

    def _draw_fence(self, screen, x, y, w):
        f = self.fonts
        have = self.guild.wilds_claim_fence_lumber
        need = economy.WILDS_CLAIM_FENCE_LUMBER
        carried = self._party_lumber()
        text(screen, "Cleared. Raise fences to hold the ground -- hauls Lumber "
             "bought at the Market, no mechanical cover yet.", f.body_sm, INK_DIM, (x, y))
        y += 24
        text(screen, f"Lumber banked: {have} / {need}", f.body_bd,
             OK if have >= need else INK, (x, y))
        y += 20
        text(screen, f"{carried} Lumber carried here right now", f.body_sm, INK_FAINT, (x, y))
        y += SP2 + 10
        y = self._button(screen, "deposit", "DEPOSIT CARRIED LUMBER", y, w,
                         enabled=carried > 0)
        self._button(screen, "build", f"BUILD THE FENCES ({economy.WILDS_CLAIM_FENCE_HOURS} h)",
                    y, w, enabled=have >= need)

    def _draw_sweep(self, screen, x, y, w):
        f = self.fonts
        for ln in ("Fenced. One more pass -- root out any nest or bandit camp "
                   "still close enough to matter.",
                   f"A second fight: {economy.WILDS_CLAIM_SWEEP_SIZE} opponents, "
                   f"level {economy.WILDS_CLAIM_SWEEP_LEVEL}."):
            text(screen, ln, f.body_sm, INK_DIM, (x, y))
            y += 17
        y += SP2
        self._button(screen, "fight_sweep", "SWEEP THE REGION", y, w)

    def _draw_garrison(self, screen, x, y, w):
        f = self.fonts
        for ln in ("Swept clean. The claim only counts once someone holds it --"
                   " garrison this group here and sustain it.",
                   f"{economy.WILDS_CLAIM_SUSTAIN_DAYS} days, uninterrupted. A "
                   "lost raid or pulling out early starts the count over."):
            text(screen, ln, f.body_sm, INK_DIM, (x, y))
            y += 17
        y += SP2
        self._button(screen, "garrison", "GARRISON HERE", y, w)

    def _draw_sustaining(self, screen, x, y, w):
        f = self.fonts
        left = self.guild.wilds_claim_sustain_days_left
        garrisoned = self.guild._wilds_claim_garrisoned()
        text(screen, f"Sustaining -- {left} day(s) left." if left is not None
             else "Sustaining.", f.body_bd, WARN, (x, y))
        y += 22
        if not garrisoned:
            text(screen, "Nobody is garrisoned here right now -- the countdown "
                 "isn't moving.", f.body_sm, DANGER, (x, y))
            y += 20
        y += SP1
        if self.group.order is not None and self.group.order.kind == "garrison":
            self._button(screen, "leave_garrison", "STAND DOWN THE GARRISON", y, w)

    def _draw_established(self, screen, x, y, w):
        f = self.fonts
        if self.guild.wilds_claim_owner == "seized":
            for ln in ("SEIZED. Occupiers hold the claim right now -- the "
                       "structure still stands, it's just not the guild's to work.",
                       "Travel a group here to fight for it back -- no need to "
                       "redo the campaign, only to retake the ground."):
                text(screen, ln, f.body_sm, DANGER, (x, y))
                y += 17
            return
        text(screen, "Established. The land is the guild's -- the garrison "
             "keeps working it on its own.", f.body_sm, OK, (x, y))
        y += 24
        stock = self.guild.garrison_stock_at(self.group.node)
        y = section(screen, f"BANKED HERE  ({len(stock)})", x, y, w, f)
        if stock:
            text(screen, f"{len(stock)} x Lumber", f.body, INK, (x, y))
            y += 20
        else:
            text(screen, "(nothing banked yet)", f.body_sm, INK_FAINT, (x, y))
            y += 20
        y += SP2
        self._button(screen, "collect", "COLLECT LUMBER", y, w, enabled=bool(stock))

"""Ledger Hold: the Bankers' fortified outpost where the trust mission's
sealed chest (`data.MISSION_CHEST_ITEM`) is traded, intact, for a letter of
receipt (`data.LETTER_ITEM`) -- the thing `missions.turn_in` actually counts
back at the City (`trust_screen.py`). No progress bar, no goal_qty -- either
someone in the group is carrying the chest, or there is nothing to hand over.
"""

import pygame

from . import data, economy, orders
from .constants import fmt_money
from .screen import Screen
from .ui import hub_body as hb
from .ui.hub_frame import MARGIN, hub_button
from .ui.primitives import set_pointer, text, wrap
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class LedgerScreen(Screen):
    native = True
    framed = True

    def tutorial_key(self):
        return "ledger"

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.notice = None
        self.buttons = []              # [(key, rect)]
        self._hot = False

    def _reset_buttons(self):
        self.buttons = []
        self._hot = False

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False):
        hub_button(surf, self._F, rect, label, primary=primary, enabled=enabled, mpos=self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or rect.collidepoint(self.mouse)

    def _carrier(self):
        return next((u for u in self.group.members
                    if u.has_item(data.MISSION_CHEST_ITEM)), None)

    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "exchange":
                carrier = self._carrier()
                if carrier is not None:
                    carrier.remove_named(data.MISSION_CHEST_ITEM)
                    carrier.give_to_pack(data.LETTER_ITEM)
                    self.notice = (f"{carrier.name} hands over the sealed chest -- the "
                                   "outpost gives a letter of receipt in return.")
            elif key == "accept_mentorship":
                from . import missions
                recruit = missions.make_treefolk_recruit()
                self.guild.add_member(recruit, self.group)
                signer = self.group.leader or self.group.members[0]
                missions.accept_treefolk_mentorship(self.guild, signer, recruit)
                self.notice = f"{recruit.name} (Treefolk) joins your group for mentorship."
            elif key == "deliver_recruit":
                from . import missions
                m_tree = next((m for m in self.guild.missions if m.template_id == "ledger_treefolk"), None)
                if m_tree is not None:
                    recruit = next((u for u in self.guild.roster if u.uid == m_tree.recruit_uid), None)
                    if recruit is not None:
                        missions.deliver_treefolk_recruit(self.guild, self.group, m_tree, recruit)
                        self.notice = f"{recruit.name} steps into the garrison. $230 reward received!"
            elif key == "supply_run":
                try:
                    self.group.order = orders.supply_run(self.guild, self.group)
                    self.on_done()
                except ValueError as err:
                    self.notice = str(err)
                return
            return

    # ------------------------------------------------------------------ #
    def hub_cards(self):
        cards = [{"label": "party purse", "value": fmt_money(sum(u.money for u in self.group.members)),
                  "tone": "money"}]
        if "bankers_trust" in self.guild.deeds_done:
            done = "ledger_hold_supply_run" in self.guild.deeds_done
            cards.insert(0, {"label": "supply runs", "value": f"{self.guild.supply_runs_completed} / 10",
                             "tone": "good" if done else None})
        return cards

    def draw(self, screen):
        F = self._F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self._reset_buttons()

        carrier = self._carrier()
        trusted = "bankers_trust" in self.guild.deeds_done
        panels = []
        if carrier is not None:
            panels.append(self._draw_chest)
        if trusted:
            panels += [self._draw_mentorship, self._draw_supply_run]
        if not panels:
            panels.append(self._draw_gate)

        bottom = H - T.S * 4 - (T.S * 3 if self.notice else 0)
        body = pygame.Rect(MARGIN, 0, W - 2 * MARGIN, bottom)
        gap = T.S * 3
        w = min(T.S * 72, (body.w - gap * (len(panels) - 1)) // len(panels))
        for i, draw_panel in enumerate(panels):
            draw_panel(screen, pygame.Rect(body.x + i * (w + gap), body.y, w, body.h))

        if self.notice:
            text(screen, F["hub_body"], self.notice, (MARGIN, H - T.S * 3), T.BRASS)
        set_pointer(self._hot)

    def _draw_chest(self, screen, rect):
        F = self._F
        inner = hb.draw_panel(screen, F, rect, "The Sealed Chest", "the Bankers' trust")
        y = hb.draw_facts(screen, F, (inner.x, inner.y), inner.w, [
            ("Carrier", self._carrier().name, None),
            ("In return", "a letter of receipt, to take back to the City", "muted")])
        self.add_button(screen, pygame.Rect(inner.x, y + T.S, inner.w, T.S * 6 + 4), "exchange",
                        "Hand over the chest", primary=True)

    def _draw_mentorship(self, screen, rect):
        from . import missions
        F = self._F
        inner = hb.draw_panel(screen, F, rect, "Garrison Mentorship", "Commander Varkas")
        m_tree = next((m for m in self.guild.missions if m.template_id == "ledger_treefolk"), None)
        button = None
        if m_tree is None:
            rows = [("Offer", "a green Treefolk recruit (racial level 0) joins the group", None),
                    ("Task", "train them to racial level 2, then bring them back", "muted")]
            button = ("accept_mentorship", "Accept the recruit", True)
        elif m_tree.state == "active":
            recruit = next((u for u in self.guild.roster if u.uid == m_tree.recruit_uid), None)
            if recruit is None:
                m_tree.state = "failed"
                rows = [("Status", "the Treefolk recruit fell in battle: the mentorship has failed", "bad")]
            elif recruit in self.group.members:
                lvl = recruit.racial_level
                ready = lvl >= 2
                rows = [("Recruit", recruit.name, None),
                        ("Training", f"racial level {lvl} / 2", "good" if ready else "muted"),
                        ("Reward", f"{fmt_money(missions.LEDGER_TREEFOLK.reward)}  ·  the recruit leaves the guild",
                         "money")]
                button = ("deliver_recruit", "Deliver the recruit", ready)
            else:
                rows = [("Recruit", f"{recruit.name} is in another group: bring them here to hand over", "muted")]
        else:
            rows = [("Status", "the Treefolk soldier serves with honour", "good"),
                    ("Gates", "Ledger Hold stands open to the guild", "muted")]
        y = hb.draw_facts(screen, F, (inner.x, inner.y), inner.w, rows)
        if button:
            key, label, enabled = button
            self.add_button(screen, pygame.Rect(inner.x, y + T.S, inner.w, T.S * 6 + 4), key, label,
                            enabled=enabled, primary=True)

    def _draw_supply_run(self, screen, rect):
        F = self._F
        inner = hb.draw_panel(screen, F, rect, "Frontier Supply Run", "to the Frontier Outpost and back")
        trip = orders.supply_hours(self.guild, self.group)
        cargo = self.group.free_cargo_capacity
        need = economy.SUPPLY_RUN_CARGO_KG
        can_run = cargo >= need
        y = hb.draw_facts(screen, F, (inner.x, inner.y), inner.w, [
            ("Trip", f"{trip:.1f} hours, walking {need:.0f} kg of supplies", None),
            ("Pay", f"{fmt_money(economy.SUPPLY_RUN_PAY)} each  ·  work level {economy.SUPPLY_RUN_LEVEL}", "money"),
            ("Cargo", f"{cargo:.1f} / {need:.0f} kg free" if can_run
             else f"{cargo:.1f} / {need:.0f} kg free: bring pack animals or lighten the load",
             "good" if can_run else "bad")])
        b = pygame.Rect(inner.x, y + T.S, inner.w, T.S * 6 + 4)
        self.add_button(screen, b, "supply_run", "Depart with the caravan", enabled=can_run, primary=True)
        text(screen, F["hub_body"], "Enemy soldiers may ambush each leg.", (inner.x, b.bottom + T.S * 2), T.BLOOD)

    def _draw_gate(self, screen, rect):
        F = self._F
        inner = hb.draw_panel(screen, F, rect, "The Gatehouse")
        y = inner.y
        for line in ("The sentries look the band over from the gatehouse.",
                     ("Commander Varkas only receives couriers bearing the counting-house seal, "
                      "or bands the Bankers vouch for.")):
            for ln in wrap(F["hub_body"], line, inner.w):
                text(screen, F["hub_body"], ln, (inner.x, y), T.TX_MUTED)
                y += F["hub_body"].get_linesize()
            y += T.S

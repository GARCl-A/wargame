"""Ledger Hold: the Bankers' fortified outpost where the trust mission's
sealed chest (`data.MISSION_CHEST_ITEM`) is traded, intact, for a letter of
receipt (`data.LETTER_ITEM`) -- the thing `missions.turn_in` actually counts
back at the City (`trust_screen.py`). No progress bar, no goal_qty -- either
someone in the group is carrying the chest, or there is nothing to hand over.

The desk's panels are data (`panels`), drawn here and by the browser's THE DESK (`web/ledger_tab.py`).
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
            if rect.collidepoint(px):
                self._act(key)
                return

    def _act(self, key):
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

    # ------------------------------------------------------------------ #
    def hub_cards(self):
        cards = [{"label": "party purse", "value": fmt_money(sum(u.money for u in self.group.members)),
                  "tone": "money"}]
        if "bankers_trust" in self.guild.deeds_done:
            done = "ledger_hold_supply_run" in self.guild.deeds_done
            cards.insert(0, {"label": "supply runs", "value": f"{self.guild.supply_runs_completed} / 10",
                             "tone": "good" if done else None})
        return cards

    def panels(self):
        """The chest while someone carries it, the mentorship and the supply run once the Bankers vouch
        for the guild, else the gate; each `{key, title, aside, rows, lines, button, warn}`, `rows` as
        `(label, value, tone)` and `button` as `(key, label, enabled)`."""
        out = []
        if self._carrier() is not None:
            out.append(self._chest())
        if "bankers_trust" in self.guild.deeds_done:
            out += [self._mentorship(), self._supply_run()]
        return out or [self._gate()]

    def draw(self, screen):
        F = self._F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self._reset_buttons()

        panels = self.panels()
        bottom = H - T.S * 4 - (T.S * 3 if self.notice else 0)
        body = pygame.Rect(MARGIN, 0, W - 2 * MARGIN, bottom)
        gap = T.S * 3
        w = min(T.S * 72, (body.w - gap * (len(panels) - 1)) // len(panels))
        for i, p in enumerate(panels):
            self._draw_panel(screen, pygame.Rect(body.x + i * (w + gap), body.y, w, body.h), p)

        if self.notice:
            text(screen, F["hub_body"], self.notice, (MARGIN, H - T.S * 3), T.BRASS)
        set_pointer(self._hot)

    def _draw_panel(self, screen, rect, p):
        F = self._F
        inner = hb.draw_panel(screen, F, rect, p["title"], p["aside"])
        y = inner.y
        for line in p["lines"]:
            for ln in wrap(F["hub_body"], line, inner.w):
                text(screen, F["hub_body"], ln, (inner.x, y), T.TX_MUTED)
                y += F["hub_body"].get_linesize()
            y += T.S
        if p["rows"]:
            y = hb.draw_facts(screen, F, (inner.x, inner.y), inner.w, p["rows"])
        if p["button"]:
            key, label, enabled = p["button"]
            b = pygame.Rect(inner.x, y + T.S, inner.w, T.S * 6 + 4)
            self.add_button(screen, b, key, label, enabled=enabled, primary=True)
            y = b.bottom
        if p["warn"]:
            text(screen, F["hub_body"], p["warn"], (inner.x, y + T.S * 2), T.BLOOD)

    @staticmethod
    def _panel(key, title, aside=None, rows=(), lines=(), button=None, warn=None):
        return {"key": key, "title": title, "aside": aside, "rows": list(rows), "lines": list(lines),
                "button": button, "warn": warn}

    def _chest(self):
        return self._panel("chest", "The Sealed Chest", "the Bankers' trust", rows=[
            ("Carrier", self._carrier().name, None),
            ("In return", "a letter of receipt, to take back to the City", "muted")],
            button=("exchange", "Hand over the chest", True))

    def _mentorship(self):
        from . import missions
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
        return self._panel("mentorship", "Garrison Mentorship", "Commander Varkas", rows=rows, button=button)

    def _supply_run(self):
        trip = orders.supply_hours(self.guild, self.group)
        cargo = self.group.free_cargo_capacity
        need = economy.SUPPLY_RUN_CARGO_KG
        can_run = cargo >= need
        return self._panel("supply_run", "Frontier Supply Run", "to the Frontier Outpost and back", rows=[
            ("Trip", f"{trip:.1f} hours, walking {need:.0f} kg of supplies", None),
            ("Pay", f"{fmt_money(economy.SUPPLY_RUN_PAY)} each  ·  work level {economy.SUPPLY_RUN_LEVEL}", "money"),
            ("Cargo", f"{cargo:.1f} / {need:.0f} kg free" if can_run
             else f"{cargo:.1f} / {need:.0f} kg free: bring pack animals or lighten the load",
             "good" if can_run else "bad")],
            button=("supply_run", "Depart with the caravan", can_run),
            warn="Enemy soldiers may ambush each leg.")

    def _gate(self):
        return self._panel("gate", "The Gatehouse", lines=(
            "The sentries look the band over from the gatehouse.",
            ("Commander Varkas only receives couriers bearing the counting-house seal, "
             "or bands the Bankers vouch for.")))

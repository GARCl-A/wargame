"""The Gathering tab of a work node (Lumber Yard, Mine): buy licence and pick gathering shifts."""

import pygame

from . import economy, gather, orders
from .constants import fmt_money
from .screen import Screen
from .ui import hub_body as hb
from .ui.hub_frame import MARGIN, hub_button
from .ui.primitives import footer_bar, header, set_pointer, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

SHIFTS = (4, 8, 12, 16)


class GatherScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, node, on_done):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.group = group
        self.node = node
        self.on_done = on_done
        self.buttons = []
        self._hot = False
        self.notice = None

    def tutorial_key(self):
        return "gathering"

    def handle_escape(self):
        self.on_done()
        return True

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self.buttons:
                if rect.collidepoint(event.pos):
                    self._on_button(key)
                    return

    def _on_button(self, key):
        if key == "leave":
            self.on_done()
        elif key == "buy_licence":
            if self.guild.buy_licence(self.node.id, self.group):
                self.notice = f"{self.node.name}: Gathering licence acquired!"
            else:
                self.notice = "Not enough funds to buy the licence."
        elif key.startswith("gather:"):
            hours = int(key.split(":")[1])
            self.group.order = orders.work(self.guild, self.group, hours, gather=True)
            self.on_done()

    def update(self, dt):
        pass

    def _payback_line(self, price):
        """A full day's haul against the wage for this group, and the days a licence takes to pay."""
        haul, wage, risk = self.guild.shift_worth(self.group, self.node.id, gather.DAY_HOURS)
        line = (f"{gather.DAY_HOURS} h for this group: haul ~{fmt_money(round(haul))} sold, "
                f"wage {fmt_money(round(wage))}, {risk * 100:.0f}% ambush")
        if self.guild.has_licence(self.node.id):
            return line
        if haul <= wage:
            return line + " · the licence never pays back"
        return line + f" · licence pays back in ~{price / (haul - wage):.0f} days"

    def add_button(self, surf, rect, key, label, enabled=True, primary=False, danger=False):
        self.buttons.append((key, rect))
        hub_button(surf, self._F, rect, label, primary=primary, enabled=enabled, mpos=self.mouse)

    framed = False          # a hub's tab: the hub draws the keeper, the tabs and the back

    def hub_cards(self):
        price = gather.licence_price(self.node.id)
        held = self.guild.has_licence(self.node.id)
        purse = sum(u.money for u in self.group.members)
        return [{"label": "licence", "value": "held" if held else fmt_money(price),
                 "tone": "good" if held else None},
                {"label": "party purse", "value": fmt_money(purse), "tone": "money"}]

    def draw(self, surf):
        W, H = surf.get_size()
        surf.fill(T.TABLE)
        F = self._F
        self.buttons.clear()
        self._hot = False

        if self.framed:
            top = 0
        else:
            header(surf, F, pygame.Rect(0, 0, W, 72), f"{self.node.name.upper()} — GATHERING",
                   "harvest materials instead of wages", (), None, mpos=self.mouse)
            top = 96
        bottom = H - T.S * 4 - (T.S * 3 if self.notice else 0)
        body = pygame.Rect(MARGIN, top, W - 2 * MARGIN, bottom - top)
        left_w = max(T.S * 56, min(T.S * 72, round(body.w * 0.4)))
        self._draw_licence(surf, pygame.Rect(body.x, body.y, left_w, body.h))
        self._draw_shifts(surf, pygame.Rect(body.x + left_w + T.S * 3, body.y, body.w - left_w - T.S * 3, body.h))

        if self.notice:
            text(surf, F["hub_body"], self.notice, (MARGIN, H - T.S * 3 - (0 if self.framed else 64)), T.BRASS)
        if not self.framed:
            footer_bar(self, surf, F, back=("leave", "BACK TO MAP"))
        self._hot = any(r.collidepoint(self.mouse) for _, r in self.buttons)
        set_pointer(self._hot)

    def _draw_licence(self, surf, rect):
        F = self._F
        inner = hb.draw_panel(surf, F, rect, "The Licence", "one licence covers the whole guild")
        held = self.guild.has_licence(self.node.id)
        price = gather.licence_price(self.node.id)
        short = self.guild.licence_shortfall(self.node.id, self.group)
        rows = [("Status", "held: every group gathers here" if held else f"not held  ·  {fmt_money(price)}",
                 "good" if held else "money")]
        if not held:
            rows.append(("Purse", f"the group is short {fmt_money(short)}" if short > 0
                         else "the group can pay it now", "bad" if short > 0 else "muted"))
        y = hb.draw_facts(surf, F, (inner.x, inner.y), inner.w, rows)
        if not held:
            b = pygame.Rect(inner.x, y, inner.w, T.S * 6 + 4)
            self.add_button(surf, b, "buy_licence", f"Buy the licence  {fmt_money(price)}", primary=True,
                            enabled=short == 0)
            y = b.bottom + T.S * 2
        y += T.S
        pygame.draw.line(surf, T.STEEL_LINE, (inner.x, y), (inner.right, y))
        y += T.S * 2
        lab = hb.draw_section(surf, F, (inner.x, y), "What the ground gives")
        text(surf, F["hub_sub"], f"{gather.rolls(gather.DAY_HOURS):.1f} rolls a worker in {gather.DAY_HOURS} h",
             (lab.right + T.S * 2, lab.y - 1), T.TX_MUTED)
        y = lab.bottom + T.S
        for name, pct in gather.drops(self.node.id):
            if y + hb.OFFER_H > inner.bottom + T.S * 2:
                break
            hb.draw_offer(surf, F, pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, hb.OFFER_H), {
                "icon": {"item": name}, "name": name, "sub": f"sells for {fmt_money(economy.sell_price(name))}",
                "price": f"{pct}%", "price_tone": None}, (-1, -1))
            y += hb.OFFER_H + T.S

    def _draw_shifts(self, surf, rect):
        F = self._F
        inner = hb.draw_panel(surf, F, rect, "Shifts", "the crew keeps what it finds instead of a wage")
        held = self.guild.has_licence(self.node.id)
        main = gather.drops(self.node.id)[0][0]
        y = inner.y
        for h in SHIFTS:
            haul, wage, risk = self.guild.shift_worth(self.group, self.node.id, h)
            self._offer(surf, pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, hb.OFFER_H), {
                "icon": {"item": main}, "name": f"{h} hours",
                "sub": f"the same hours' wage {fmt_money(round(wage))}  ·  {risk * 100:.0f}% ambush",
                "price": f"~{fmt_money(round(haul))}", "price_tone": "good" if haul > wage else "muted",
                "buttons": [(f"gather:{h}", "Gather", True, held)], "dim": not held})
            y += hb.OFFER_H + T.S
        if not held:
            text(surf, F["hub_body"], "Gathering needs the licence.", (inner.x, y + T.S), T.TX_FAINT)
        foot = inner.bottom - T.S * 6
        pygame.draw.line(surf, T.STEEL_LINE, (rect.x, foot), (rect.right - 1, foot))
        text(surf, F["hub_body"], "A pack may ambush the crew: the fight must be won to keep the haul.",
             (inner.x, foot + T.S * 2), T.BLOOD)
        text(surf, F["hub_sub"], self._payback_line(gather.licence_price(self.node.id)),
             (inner.x, foot + T.S * 5), T.TX_MUTED)

    def _offer(self, surf, rect, o):
        for b, key in hb.draw_offer(surf, self._F, rect, o, self.mouse):
            self.buttons.append((key, b))

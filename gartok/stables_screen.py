"""The Stables (the Farm) and the Carpenter's wagon yard (`WagonYardScreen`): the pygame windows over
`stables.Stables` and `stables.WagonYard`."""

import pygame

from . import animals, data, wagon
from .constants import fmt_money
from .screen import Screen
from .stables import Stables, WagonYard, resale, tack_price
from .ui import hub_body as hb
from .ui.hub_frame import MARGIN
from .ui.primitives import draw_button, footer_bar, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class StablesScreen(Screen, Stables):
    native = True
    header_reserve = 0
    framed = False          # a hub's tab: the hub draws the keeper, the tabs and the back
    title = "THE STABLES"
    subtitle = "buy and sell animals and tack"
    leave = "LEAVE THE STABLES"

    def tutorial_key(self):
        return "stable"

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        Stables.__init__(self, guild, group)           # Screen ends the cooperative chain
        self.fonts = fonts
        self._F = ui_fonts()
        self.on_done = on_done
        self.buttons = []
        self._hot = False

    def handle_escape(self):
        return False

    # ------------------------------------------------------------------ #
    def handle_event(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        for key, rect in self.buttons:
            if rect.collidepoint(event.pos):
                self._click(key)
                return

    def _click(self, key):
        g = self.group
        kind, _, arg = key.partition(":")
        if kind == "done":
            self.on_done()
        elif kind == "buy":
            self._buy_animal(arg)
        elif kind in ("sell", "fit"):
            idx, _, tack = arg.partition(":")
            animal = g.herd[int(idx)]
            {"sell": self._sell_animal, "fit": lambda a: self._fit(a, tack)}[kind](animal)

    # ------------------------------------------------------------------ #
    def _offer(self, screen, rect, o):
        for b, key in hb.draw_offer(screen, self._F, rect, o, self.mouse):
            self.buttons.append((key, b))
            self._hot = self._hot or b.collidepoint(self.mouse)

    def draw(self, screen):
        F = self._F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.buttons = []
        self._hot = False

        if self.framed:
            top, bottom = 0, H - T.S * 4
        else:
            m = T.S * 3
            text(screen, F["titleb"], self.title, (m, m - 2), T.TX)
            text(screen, F["body"], self.subtitle, (m, m + 30), T.TX_MUTED)
            text(screen, F["bodyb"], f"party holds {fmt_money(self.wealth)}",
                 (W - m - (28 + T.S) - self.header_reserve, m + 4), T.BRASS, right=True)
            top, bottom = m + 62, H - 80
        body = pygame.Rect(MARGIN, top, W - 2 * MARGIN, bottom - top)
        left_w = max(T.S * 56, min(T.S * 76, round(body.w * 0.42)))
        self._draw_market(screen, pygame.Rect(body.x, body.y, left_w, body.h))
        self._draw_herd(screen, pygame.Rect(body.x + left_w + T.S * 3, body.y, body.w - left_w - T.S * 3, body.h))
        if not self.framed:
            footer_bar(self, screen, F, primary=("done", self.leave), notice=self.notice)
        elif self.notice:
            text(screen, F["hub_body"], self.notice, (MARGIN, H - T.S * 3), T.TX_MUTED)

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False, danger=False):
        draw_button(surf, self._F, rect, label, primary=primary, danger=danger, enabled=enabled, mpos=self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or rect.collidepoint(self.mouse)

    def _draw_market(self, screen, rect):
        F, g = self._F, self.group
        inner = hb.draw_panel(screen, F, rect, "For Sale", "animals; wagons are the Carpenter's")
        lab = hb.draw_section(screen, F, (inner.x, inner.y), f"Animals  ·  herd {g.herd_load} / {g.herd_capacity}")
        if g.herd_load >= g.herd_capacity:
            text(screen, F["hub_subb"], f"full: {self._keeper.name} controls no more", (lab.right + T.S * 2, lab.y - 1),
                 T.BLOOD)
        y = lab.bottom + T.S
        for species in data.LIVESTOCK:
            sample = animals.Animal(species)
            can = g.can_take(sample) and self.wealth >= sample.price
            self._offer(screen, pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, hb.OFFER_H), {
                "icon": {"face": {"race": species, "portrait_id": None, "token": species[0]}},
                "name": species, "price": fmt_money(sample.price), "price_tone": "money" if can else "faint",
                "sub": f"carries {sample.back_load} kg  ·  draws {sample.draw} kg  ·  speed {sample.speed:g} m",
                "buttons": [(f"buy:{species}", "Buy", True, can)], "dim": not can})
            y += hb.OFFER_H + T.S
        text(screen, F["hub_sub"], "Every animal eats a ration a day; tack decides what it does.",
             (inner.x, y + T.S), T.TX_FAINT)

    def _draw_herd(self, screen, rect):
        F, g = self._F, self.group
        inner = hb.draw_panel(screen, F, rect, "The Group's Herd",
                              "hitching and riding are set on the group's gear screen")
        y = hb.draw_section(screen, F, (inner.x, inner.y), "Animals").bottom + T.S
        for i, a in enumerate(g.herd):
            role = {"pack": "carries cargo", "draft": "pulls a wagon"}.get(a.role, "no tack")
            buttons = []
            if not a.tack:
                buttons = [(f"fit:{i}:{tack}", f"{tack} {fmt_money(tack_price(tack))}", False,
                            self.wealth >= tack_price(tack)) for tack in (animals.HARNESS, animals.PACK_SADDLE)]
            buttons.append((f"sell:{i}", f"Sell {fmt_money(resale(a.price))}", False, True))
            self._offer(screen, pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, hb.OFFER_H), {
                "icon": {"face": {"race": a.species, "portrait_id": None, "token": a.species[0]}},
                "name": a.species + (f"  ·  {a.tack}" if a.tack else ""),
                "sub": f"{role}  ·  speed {a.speed:g} m  ·  HP {a.hp}",
                "note": (f"unfed {a.unfed_days} day{'s' if a.unfed_days != 1 else ''}", "bad") if a.unfed_days else None,
                "buttons": buttons})
            y += hb.OFFER_H + T.S
        if not g.herd:
            text(screen, F["hub_body"], "No animals yet.", (inner.x, y), T.TX_FAINT)


class WagonYardScreen(StablesScreen, WagonYard):
    """The Carpenter's WAGONS tab: buy a cart or a carriage, sell an empty one back."""
    title = "THE WAGON YARD"
    subtitle = "buy and sell wagons"
    leave = "LEAVE THE YARD"

    def tutorial_key(self):
        return "wagon_yard"

    def _click(self, key):
        kind, _, arg = key.partition(":")
        if kind == "buy_wagon" and arg in wagon.VEHICLES:
            self._buy_wagon(arg)
        elif kind == "sell_wagon":
            self._sell_wagon(self.group.wagons[int(arg)])
        else:
            super()._click(key)

    def _draw_market(self, screen, rect):
        F = self._F
        inner = hb.draw_panel(screen, F, rect, "For Sale", "wagons; the animals that pull them are the Farm's")
        y = hb.draw_section(screen, F, (inner.x, inner.y), "Wagons").bottom + T.S
        for vehicle in wagon.VEHICLES.values():
            can = self.wealth >= vehicle.price
            self._offer(screen, pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, hb.OFFER_H), {
                "icon": {"glyph": "wagon", "covered": vehicle.name == "Carriage"},
                "name": vehicle.name, "price": fmt_money(vehicle.price), "price_tone": "money" if can else "faint",
                "sub": f"holds {vehicle.capacity} kg  ·  {vehicle.slots} animal{'s' if vehicle.slots != 1 else ''} to pull",
                "buttons": [(f"buy_wagon:{vehicle.name}", "Buy", True, can)], "dim": not can})
            y += hb.OFFER_H + T.S

    def _draw_herd(self, screen, rect):
        F, g = self._F, self.group
        inner = hb.draw_panel(screen, F, rect, "The Group's Wagons",
                              "hitching and riding are set on the group's gear screen")
        y = hb.draw_section(screen, F, (inner.x, inner.y), "Wagons").bottom + T.S
        for i, w_ in enumerate(g.wagons):
            pulled = " + ".join(a.species for a in w_.draft) or "nothing hitched"
            speed = f"{w_.speed:g} m" if w_.speed else "--"
            riders = f"  ·  {w_.passenger_weight:g} kg of riders" if w_.passengers else ""
            sell = [] if w_.stash.items else [(f"sell_wagon:{i}", f"Sell {fmt_money(resale(w_.price))}", False, True)]
            self._offer(screen, pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, hb.OFFER_H), {
                "icon": {"glyph": "wagon", "covered": w_.kind == "Carriage"},
                "name": f"{self._wagon_label(w_)}  ·  cargo {w_.stash.load:g} / {w_.capacity:g} kg  ·  {pulled}",
                "sub": f"HP {w_.hp}  ·  speed {speed}  ·  {w_.rations} meals aboard{riders}  ·  "
                       f"draws up to {w_.budget:g} kg",
                "note": None if w_.draft else ("nothing pulls it: the cargo box is shut", "bad"),
                "buttons": sell})
            y += hb.OFFER_H + T.S
        if not g.wagons:
            text(screen, F["hub_body"], "No wagon. Cargo in a wagon never goes into a fight and feeds the group "
                 "on the road; animals in a Harness pull it.", (inner.x, y), T.TX_FAINT)

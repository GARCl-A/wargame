"""A garage: park the group's wagons and animals, take them out again, and (at the
house) add bays.

The house garage holds one wagon and one animal per tier (`holdings.Garage`). What is
parked there belongs to the house, not the group: it is safe, eats from the house stash
and does not count against the group's herd capacity. The party pays out of its pooled
coin, richest first, like the stables. The Claim's garage (`claim=True`) has no bays and
no limit, and is only safe while a garrison stands there.
"""

import pygame

from . import economy, wagon_watch
from .constants import fmt_money
from .screen import Screen
from .ui.primitives import draw_button, footer_bar, panel, section, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class GarageScreen(Screen):
    native = True

    def tutorial_key(self):
        return "garage"

    def __init__(self, fonts, guild, group, on_done, claim=False):
        super().__init__()
        self.claim = claim
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.notice = None
        self.buttons = []
        self._hot = False

    def handle_escape(self):
        return False

    @property
    def garage(self):
        return self.guild.claim_garage if self.claim else self.guild.house.garage

    @property
    def wealth(self):
        return sum(m.money for m in self.group.members)

    def handle_event(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        for key, rect in self.buttons:
            if rect.collidepoint(event.pos):
                self._click(key)
                return

    def _click(self, key):
        g, garage, guild = self.group, self.garage, self.guild
        kind, _, arg = key.partition(":")
        if kind == "done":
            self.on_done()
        elif kind == "bay":
            if self.wealth < economy.GARAGE_PRICE:
                self.notice = f"a bay costs {fmt_money(economy.GARAGE_PRICE)} -- the party has {fmt_money(self.wealth)}."
                return
            economy.charge_richest_first(g.members, economy.GARAGE_PRICE)
            guild.buy_garage_tier()
            self.notice = "a new bay: room for one more wagon and one more animal."
        elif kind == "park_wagon":
            wagon = g.wagons[int(arg)]
            if guild.park_wagon(g, wagon, garage):
                self.notice = f"the {wagon.kind.lower()} is parked in the garage."
            else:
                self.notice = "every bay already holds a wagon."
        elif kind == "take_wagon":
            wagon = garage.wagons[int(arg)]
            if guild.take_wagon(g, wagon, garage):
                self.notice = f"the {wagon.kind.lower()} rejoins the group."
        elif kind == "park_animal":
            animal = g.herd[int(arg)]
            if guild.park_animal(g, animal, garage):
                self.notice = f"the {animal.species} is stabled in the garage."
            else:
                self.notice = "every bay already holds an animal."
        elif kind == "take_animal":
            animal = garage.herd[int(arg)]
            if guild.take_animal(g, animal, garage):
                self.notice = f"the {animal.species} rejoins the group."
            else:
                keeper = g.leader or g.members[0]
                self.notice = f"{keeper.name} can control a herd of {g.herd_capacity} at most."

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False, danger=False, sub=None):
        draw_button(surf, self._F, rect, label, sub=sub, primary=primary, danger=danger,
                    enabled=enabled, mpos=self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or rect.collidepoint(self.mouse)

    def draw(self, screen):
        F = self._F
        m = T.S * 3
        screen.fill(T.TABLE)
        self.buttons = []
        self._hot = False

        text(screen, F["titleb"], "THE CLAIM GARAGE" if self.claim else "THE GARAGE", (m, m - 2), T.TX)
        sub = ("wagons and animals kept at the claim  ·  safe only while a garrison stands here, fed from its food"
               if self.claim else "wagons and animals kept at the house  ·  safe, and fed from the house stash")
        text(screen, F["body"], sub, (m, m + 30), T.TX_MUTED)
        text(screen, F["bodyb"], f"party holds {fmt_money(self.wealth)}", (screen.get_width() - m, m + 4), T.BRASS, right=True)

        top = m + 62
        area = pygame.Rect(m, top, min(760, screen.get_width() - 2 * m), screen.get_height() - top - 80)
        panel(screen, area)
        x, w = area.x + 12, area.w - 24
        y = (self._draw_claim_risk if self.claim else self._draw_bays)(screen, x, area.y + 12, w)
        y = self._draw_wagons(screen, x, y + T.S, w)
        self._draw_animals(screen, x, y + T.S, w)
        footer_bar(self, screen, F, primary=("done", "LEAVE THE GARAGE"), notice=self.notice)

    def _draw_claim_risk(self, screen, x, y, w):
        F = self._F
        y = section(screen, F, "THE CLAIM", x, y, w)
        if self.guild.claim_garrison() is not None:
            text(screen, F["body"], "A garrison stands here: what is parked is safe, and a raid is a fight.",
                 (x, y), T.TX)
        else:
            chance = wagon_watch.flight_chance(self.garage)
            text(screen, F["bodyb"], "Nobody is garrisoned: each day the animals may bolt and take it all"
                 f"  ({chance:.0%} a day).", (x, y), T.BLOOD if chance else T.TX)
        return y + 28

    def _draw_bays(self, screen, x, y, w):
        F, garage = self._F, self.garage
        y = section(screen, F, f"BAYS  ({garage.tier})", x, y, w)
        if not garage.open:
            text(screen, F["body_sm"], "No garage yet. Each bay keeps one wagon and one animal safe at the house.",
                 (x, y), T.TX_MUTED)
            y += 24
        can = self.wealth >= economy.GARAGE_PRICE
        label = "BUILD A GARAGE" if not garage.open else "ADD A BAY"
        self.add_button(screen, pygame.Rect(x, y, w, 40), "bay", f"{label}  ·  {fmt_money(economy.GARAGE_PRICE)}",
                        enabled=can, primary=can, sub="one more wagon and one more animal")
        return y + 46

    def _held(self, n):
        return str(n) if self.claim else f"{n} / {self.garage.tier}"

    def _draw_wagons(self, screen, x, y, w):
        F, g, garage = self._F, self.group, self.garage
        y = section(screen, F, f"WAGONS  (garage {self._held(len(garage.wagons))})", x, y, w)
        for i, wagon in enumerate(garage.wagons):
            text(screen, F["bodyb"], f"{wagon.kind}  ·  in the garage  ·  cargo {wagon.stash.load:g} kg",
                 (x, y + 4), T.TX)
            self.add_button(screen, pygame.Rect(x + w - 150, y, 150, 28), f"take_wagon:{i}", "TAKE OUT")
            y += 36
        for i, wagon in enumerate(g.wagons):
            text(screen, F["bodyb"], f"{wagon.kind}  ·  with the group  ·  cargo {wagon.stash.load:g} kg",
                 (x, y + 4), T.TX_MUTED)
            self.add_button(screen, pygame.Rect(x + w - 150, y, 150, 28), f"park_wagon:{i}", "PARK",
                            enabled=garage.wagon_room > 0)
            y += 36
        if not garage.wagons and not g.wagons:
            text(screen, F["body_sm"], "No wagons.", (x, y), T.TX_FAINT)
            y += 24
        return y

    def _draw_animals(self, screen, x, y, w):
        F, g, garage = self._F, self.group, self.garage
        y = section(screen, F, f"ANIMALS  (garage {self._held(len(garage.herd))})", x, y, w)
        for i, animal in enumerate(garage.herd):
            fed_by = "the garrison's food" if self.claim else "the house stash"
            note = f"unfed {animal.unfed_days} day(s)" if animal.unfed_days else f"eats from {fed_by}"
            text(screen, F["bodyb"], f"{animal.species}  ·  in the garage  ·  {note}", (x, y + 4),
                 T.BLOOD if animal.unfed_days else T.TX)
            self.add_button(screen, pygame.Rect(x + w - 150, y, 150, 28), f"take_animal:{i}", "TAKE OUT",
                            enabled=g.can_take(animal))
            y += 36
        for i, animal in enumerate(g.herd):
            text(screen, F["bodyb"], f"{animal.species}  ·  with the group", (x, y + 4), T.TX_MUTED)
            self.add_button(screen, pygame.Rect(x + w - 150, y, 150, 28), f"park_animal:{i}", "STABLE",
                            enabled=garage.animal_room > 0)
            y += 36
        if not garage.herd and not g.herd:
            text(screen, F["body_sm"], "No animals.", (x, y), T.TX_FAINT)
        return y

"""The house garage: park the group's wagons and animals, take them out again,
and add bays.

A garage holds one wagon and one animal per tier (`holdings.Garage`). What is
parked there belongs to the house, not the group: it is safe, eats from the
house stash and does not count against the group's herd capacity. The party
pays out of its pooled coin, richest first, like the stables.
"""

import pygame

from . import economy
from .screen import Screen
from .ui.primitives import draw_button, footer_bar, panel, section, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


class GarageScreen(Screen):
    native = True

    def tutorial_key(self):
        return "garage"

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
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
        return self.guild.house.garage

    @property
    def wealth(self):
        return sum(m.gold for m in self.group.members)

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
                self.notice = f"a bay costs {economy.GARAGE_PRICE} copper -- the party has {self.wealth}."
                return
            economy.charge_richest_first(g.members, economy.GARAGE_PRICE)
            guild.buy_garage_tier()
            self.notice = "a new bay: room for one more wagon and one more animal."
        elif kind == "park_wagon":
            wagon = g.wagons[int(arg)]
            if guild.park_wagon(g, wagon):
                self.notice = f"the {wagon.kind.lower()} is parked in the garage."
            else:
                self.notice = "every bay already holds a wagon."
        elif kind == "take_wagon":
            wagon = garage.wagons[int(arg)]
            if guild.take_wagon(g, wagon):
                self.notice = f"the {wagon.kind.lower()} rejoins the group."
        elif kind == "park_animal":
            animal = g.herd[int(arg)]
            if guild.park_animal(g, animal):
                self.notice = f"the {animal.species} is stabled in the garage."
            else:
                self.notice = "every bay already holds an animal."
        elif kind == "take_animal":
            animal = garage.herd[int(arg)]
            if guild.take_animal(g, animal):
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

        text(screen, F["titleb"], "THE GARAGE", (m, m - 2), T.TX)
        text(screen, F["body"], "wagons and animals kept at the house  ·  safe, and fed from the house stash",
             (m, m + 30), T.TX_MUTED)
        text(screen, F["bodyb"], f"party holds {self.wealth} cp", (screen.get_width() - m, m + 4), T.BRASS, right=True)

        top = m + 62
        area = pygame.Rect(m, top, min(760, screen.get_width() - 2 * m), screen.get_height() - top - 80)
        panel(screen, area)
        x, w = area.x + 12, area.w - 24
        y = self._draw_bays(screen, x, area.y + 12, w)
        y = self._draw_wagons(screen, x, y + T.S, w)
        self._draw_animals(screen, x, y + T.S, w)
        footer_bar(self, screen, F, primary=("done", "LEAVE THE GARAGE"), notice=self.notice)

    def _draw_bays(self, screen, x, y, w):
        F, garage = self._F, self.garage
        y = section(screen, F, f"BAYS  ({garage.tier})", x, y, w)
        if not garage.open:
            text(screen, F["body_sm"], "No garage yet. Each bay keeps one wagon and one animal safe at the house.",
                 (x, y), T.TX_MUTED)
            y += 24
        can = self.wealth >= economy.GARAGE_PRICE
        label = "BUILD A GARAGE" if not garage.open else "ADD A BAY"
        self.add_button(screen, pygame.Rect(x, y, w, 40), "bay", f"{label}  ·  {economy.GARAGE_PRICE} c",
                        enabled=can, primary=can, sub="one more wagon and one more animal")
        return y + 46

    def _draw_wagons(self, screen, x, y, w):
        F, g, garage = self._F, self.group, self.garage
        y = section(screen, F, f"WAGONS  (garage {len(garage.wagons)} / {garage.tier})", x, y, w)
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
        y = section(screen, F, f"ANIMALS  (garage {len(garage.herd)} / {garage.tier})", x, y, w)
        for i, animal in enumerate(garage.herd):
            note = f"unfed {animal.unfed_days} day(s)" if animal.unfed_days else "eats from the house stash"
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

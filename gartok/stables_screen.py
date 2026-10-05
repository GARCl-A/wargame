"""The Stables: buy a wagon for the group, animals to keep, and the tack that
decides what each animal does.

Nothing is stored here -- the wagon and the animals live on the `Group` and
travel with it (see `wagon.py`, `animals.py`). The party pays out of its pooled
coin, richest first; selling back returns `economy.SELL_FACTOR` of the price to
the group's leader.
"""

import pygame

from . import animals, economy, items, wagon
from .screen import Screen
from .ui.primitives import draw_button, ellipsize, footer_bar, panel, section, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts


def _resale(price):
    return max(1, int(price * economy.SELL_FACTOR))


def _tack_price(name):
    return items.get(name).price


class StablesScreen(Screen):
    native = True

    def tutorial_key(self):
        return "stable"

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
    def wealth(self):
        return sum(m.gold for m in self.group.members)

    @property
    def _keeper(self):
        return self.group.leader or self.group.members[0]

    def _pay(self, price, what):
        if self.wealth < price:
            self.notice = f"{what} costs {price} copper -- the party has {self.wealth}."
            return False
        economy.charge_richest_first(self.group.members, price)
        return True

    def _receive(self, amount):
        self._keeper.gold += amount

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
        elif kind == "buy_wagon" and g.wagon is None:
            if self._pay(wagon.WAGON_PRICE, "a wagon"):
                g.wagon = wagon.Wagon()
                self.notice = "the wagon is yours -- harness an animal to pull it."
        elif kind == "sell_wagon" and g.wagon is not None and not g.wagon.stash.items:
            self._receive(_resale(wagon.WAGON_PRICE))
            g.wagon = None
            self.notice = "sold the wagon."
        elif kind == "buy":
            self._buy_animal(arg)
        elif kind in ("sell", "fit", "unfit"):
            idx, _, tack = arg.partition(":")
            animal = g.animals[int(idx)]
            {"sell": self._sell_animal, "fit": lambda a: self._fit(a, tack), "unfit": self._unfit}[kind](animal)

    def _buy_animal(self, species):
        if len(self.group.animals) >= animals.MAX_ANIMALS:
            self.notice = f"a group can keep at most {animals.MAX_ANIMALS} animals."
        elif self._pay(animals.SPECIES[species]["price"], f"a {species}"):
            self.group.animals.append(animals.Animal(species))
            self.notice = f"a {species} joins the group."

    def _fit(self, animal, tack):
        if animal.tack is None and self._pay(_tack_price(tack), f"a {tack}"):
            animal.give_to_tack(tack)
            self.notice = f"the {animal.species} now wears a {tack}."

    def _unfit(self, animal):
        if animal.stash.items:
            self.notice = f"unload the {animal.species} first."
            return
        self._keeper.give_to_pack(animal.take_tack())
        self.notice = f"took the tack off the {animal.species}."

    def _sell_animal(self, animal):
        if animal.stash.items:
            self.notice = f"unload the {animal.species} first."
            return
        if animal.tack:
            self._keeper.give_to_pack(animal.take_tack())
        self.group.animals.remove(animal)
        self._receive(_resale(animal.price))
        self.notice = f"sold the {animal.species}."

    # ------------------------------------------------------------------ #
    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False, danger=False,
                   font=None, sub=None):
        draw_button(surf, self._F, rect, label, sub=sub, primary=primary, danger=danger,
                    enabled=enabled, mpos=self.mouse, fnt=font)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or rect.collidepoint(self.mouse)

    def draw(self, screen):
        F = self._F
        m = T.S * 3
        screen.fill(T.TABLE)
        self.buttons = []
        self._hot = False

        text(screen, F["titleb"], "THE STABLES", (m, m - 2), T.TX)
        text(screen, F["body"], "animals, wagons and tack  ·  they belong to the group that buys them",
             (m, m + 30), T.TX_MUTED)
        text(screen, F["bodyb"], f"party holds {self.wealth} cp", (screen.get_width() - m, m + 4), T.BRASS, right=True)

        top = m + 62
        area = pygame.Rect(m, top, min(760, screen.get_width() - 2 * m), min(520, screen.get_height() - top - 80))
        panel(screen, area)
        x, w = area.x + 12, area.w - 24
        y = self._draw_wagon(screen, x, area.y + 12, w)
        self._draw_animals(screen, x, y + T.S, w)
        footer_bar(self, screen, F, primary=("done", "LEAVE THE STABLES"), notice=self.notice)

    def _draw_wagon(self, screen, x, y, w):
        F, g = self._F, self.group
        y = section(screen, F, "THE WAGON", x, y, w)
        if g.wagon is None:
            text(screen, F["body_sm"], f"Carries up to {wagon.WAGON_CAPACITY} kg that never goes into a fight, "
                 "and feeds the group on the road.", (x, y), T.TX_MUTED)
            text(screen, F["body_sm"], f"It weighs {wagon.WAGON_WEIGHT} kg itself, so animals wearing a Harness "
                 "must pull it. Lost if the whole group dies.", (x, y + 17), T.TX_MUTED)
            self.add_button(screen, pygame.Rect(x, y + 40, w, 36), "buy_wagon",
                            f"BUY A WAGON  ·  {wagon.WAGON_PRICE} c", enabled=self.wealth >= wagon.WAGON_PRICE,
                            primary=True)
            return y + 84
        w_ = g.wagon
        pulled = " + ".join(a.species for a in w_.draft) or "nothing harnessed"
        text(screen, F["bodyb"], f"Cargo {w_.stash.load:g} / {w_.capacity} kg  ·  pulled by {pulled}", (x, y), T.TX)
        speed = f"{w_.speed:g} m" if w_.speed else "--"
        text(screen, F["body_sm"], f"HP {w_.hp}  ·  speed {speed}  ·  {w_.rations} meals aboard", (x, y + 20), T.TX_MUTED)
        if not w_.draft:
            text(screen, F["body_sm"], "Nothing is pulling it -- the cargo box is shut.", (x, y + 38), T.BLOOD)
        if not w_.stash.items:
            self.add_button(screen, pygame.Rect(x + w - 190, y, 190, 28), "sell_wagon",
                            f"SELL  ·  {_resale(wagon.WAGON_PRICE)} c")
        return y + 62

    def _draw_animals(self, screen, x, y, w):
        F, g = self._F, self.group
        y = section(screen, F, f"ANIMALS  ({len(g.animals)} / {animals.MAX_ANIMALS})", x, y, w)
        for i, a in enumerate(g.animals):
            role = {"pack": "carries cargo", "draft": "pulls the wagon"}.get(a.role, "no tack")
            note = f"{role}  ·  speed {a.speed:g} m  ·  HP {a.hp}"
            if a.unfed_days:
                note = f"unfed {a.unfed_days} day(s)  ·  " + note
            text(screen, F["bodyb"], a.species, (x, y + 4), T.TX)
            bx = x + w - 130
            self.add_button(screen, pygame.Rect(bx, y, 130, 28), f"sell:{i}", f"SELL · {_resale(a.price)} c")
            if a.tack:
                bx -= 138
                self.add_button(screen, pygame.Rect(bx, y, 130, 28), f"unfit:{i}", "TAKE TACK OFF")
            else:
                for tack in (animals.HARNESS, animals.PACK_SADDLE):
                    price = _tack_price(tack)
                    bx -= 138
                    self.add_button(screen, pygame.Rect(bx, y, 130, 28), f"fit:{i}:{tack}",
                                    f"{tack.upper()} · {price} c", enabled=self.wealth >= price)
            text(screen, F["body_sm"], ellipsize(note, F["body_sm"], bx - (x + 80) - T.S),
                 (x + 80, y + 6), T.BLOOD if a.unfed_days else T.TX_MUTED)
            y += 36
        if not g.animals:
            text(screen, F["body_sm"], "No animals yet.", (x, y), T.TX_FAINT)
            y += 24
        y += T.S
        for species, spec in animals.SPECIES.items():
            can = len(g.animals) < animals.MAX_ANIMALS and self.wealth >= spec["price"]
            self.add_button(screen, pygame.Rect(x, y, w, 40), f"buy:{species}",
                            f"BUY A {species.upper()}  ·  {spec['price']} c", enabled=can, primary=can,
                            sub=(f"carries {spec['carry']} kg  ·  draws {spec['pull']} kg  ·  speed {spec['speed']:g} m"
                                 "  ·  eats a ration a day"))
            y += 46

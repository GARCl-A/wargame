"""The Stables: buy wagons for the group, animals to keep, and the tack that
decides what each animal does.

Nothing is stored here -- the wagons and the animals live on the `Group` and
travel with it (see `wagon.py`, `animals.py`). The party pays out of its pooled
coin, richest first; selling back returns `economy.SELL_FACTOR` of the price to
the group's leader.
"""

import pygame

from . import animals, data, economy, items, wagon
from .constants import fmt_money
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
        return sum(m.money for m in self.group.members)

    @property
    def _keeper(self):
        return self.group.leader or self.group.members[0]

    def _pay(self, price, what):
        if self.wealth < price:
            self.notice = f"{what} costs {fmt_money(price)} -- the party has {fmt_money(self.wealth)}."
            return False
        economy.charge_richest_first(self.group.members, price)
        return True

    def _receive(self, amount):
        self._keeper.money += amount

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
        elif kind == "buy_wagon" and arg in wagon.VEHICLES:
            if self._pay(wagon.VEHICLES[arg].price, f"a {arg.lower()}"):
                g.add_wagon(wagon.Wagon(arg))
                g.hitch_idle()
                self.notice = f"the {arg.lower()} is yours -- harness an animal to pull it."
        elif kind == "sell_wagon" and not g.wagons[int(arg)].stash.items:
            sold = g.wagons[int(arg)]
            g.remove_wagon(sold)
            self._receive(_resale(sold.price))
            self.notice = f"sold the {sold.kind.lower()}."
        elif kind == "hitch":
            animal = g.herd[int(arg)]
            g.next_hitch(animal)
            pulled = g.pulling(animal)
            self.notice = (f"the {animal.species} pulls {self._wagon_label(pulled)}." if pulled
                           else f"the {animal.species} is unhitched.")
        elif kind == "buy":
            self._buy_animal(arg)
        elif kind in ("sell", "fit", "unfit"):
            idx, _, tack = arg.partition(":")
            animal = g.herd[int(idx)]
            {"sell": self._sell_animal, "fit": lambda a: self._fit(a, tack), "unfit": self._unfit}[kind](animal)

    def _buy_animal(self, species):
        animal = animals.Animal(species)
        if not self.group.can_take(animal):
            self.notice = f"{self._keeper.name} can control a herd of {self.group.herd_capacity} at most."
        elif self._pay(animal.price, f"a {species}"):
            self.group.herd.append(animal)
            self.notice = f"a {species} joins the group."

    def _fit(self, animal, tack):
        if animal.tack is None and self._pay(_tack_price(tack), f"a {tack}"):
            animal.give_to_tack(tack)
            self.group.hitch_idle()
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
        self.group.herd.remove(animal)
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
        text(screen, F["bodyb"], f"party holds {fmt_money(self.wealth)}", (screen.get_width() - m, m + 4), T.BRASS, right=True)

        top = m + 62
        area = pygame.Rect(m, top, min(760, screen.get_width() - 2 * m), screen.get_height() - top - 80)
        panel(screen, area)
        x, w = area.x + 12, area.w - 24
        y = self._draw_wagon(screen, x, area.y + 12, w)
        self._draw_animals(screen, x, y + T.S, w)
        footer_bar(self, screen, F, primary=("done", "LEAVE THE STABLES"), notice=self.notice)

    def _wagon_label(self, w):
        """"Cart" alone, "Cart 2" when the group keeps several."""
        same = [x for x in self.group.wagons if x.kind == w.kind]
        return w.kind.lower() if len(same) == 1 else f"{w.kind.lower()} {same.index(w) + 1}"

    def _draw_wagon(self, screen, x, y, w):
        F, g = self._F, self.group
        y = section(screen, F, "WAGONS", x, y, w)
        for i, w_ in enumerate(g.wagons):
            pulled = " + ".join(a.species for a in w_.draft) or "nothing hitched"
            text(screen, F["bodyb"], f"{self._wagon_label(w_).capitalize()}  ·  cargo {w_.stash.load:g} / {w_.capacity:g} kg"
                 f"  ·  pulled by {pulled}", (x, y), T.TX)
            speed = f"{w_.speed:g} m" if w_.speed else "--"
            riders = f"{w_.passenger_weight:g} kg of riders  ·  " if w_.passengers else ""
            text(screen, F["body_sm"], f"HP {w_.hp}  ·  speed {speed}  ·  {w_.rations} meals aboard  ·  {riders}"
                 f"carries up to {w_.budget:g} kg, {w_.vehicle.slots} to hitch", (x, y + 20), T.TX_MUTED)
            if not w_.draft:
                text(screen, F["body_sm"], "Nothing is pulling it -- the cargo box is shut.", (x, y + 38), T.BLOOD)
            if not w_.stash.items:
                self.add_button(screen, pygame.Rect(x + w - 190, y, 190, 28), f"sell_wagon:{i}",
                                f"SELL  ·  {fmt_money(_resale(w_.price))}")
            y += 62
        if not g.wagons:
            text(screen, F["body_sm"], "Cargo that never goes into a fight and feeds the group on the road. "
                 "Animals wearing a Harness pull it, as much as they can draw.", (x, y), T.TX_MUTED)
            y += 24
        half = (w - T.S) // 2
        for n, vehicle in enumerate(wagon.VEHICLES.values()):
            can = self.wealth >= vehicle.price
            self.add_button(screen, pygame.Rect(x + n * (half + T.S), y, half, 40), f"buy_wagon:{vehicle.name}",
                            f"BUY A {vehicle.name.upper()}  ·  {fmt_money(vehicle.price)}", enabled=can, primary=can,
                            sub=f"holds {vehicle.capacity} kg  ·  {vehicle.slots} animal(s) to pull")
        return y + 46

    def _draw_animals(self, screen, x, y, w):
        F, g = self._F, self.group
        y = section(screen, F, f"ANIMALS  (herd {g.herd_load} / {g.herd_capacity})", x, y, w)
        for i, a in enumerate(g.herd):
            role = {"pack": "carries cargo", "draft": "pulls a wagon"}.get(a.role, "no tack")
            note = f"{role}  ·  speed {a.speed:g} m  ·  HP {a.hp}"
            if a.unfed_days:
                note = f"unfed {a.unfed_days} day(s)  ·  " + note
            text(screen, F["bodyb"], a.species, (x, y + 4), T.TX)
            bx = x + w - 130
            self.add_button(screen, pygame.Rect(bx, y, 130, 28), f"sell:{i}", f"SELL · {fmt_money(_resale(a.price))}")
            if a.tack:
                bx -= 138
                self.add_button(screen, pygame.Rect(bx, y, 130, 28), f"unfit:{i}", "TAKE TACK OFF")
                if a.role == "draft" and g.wagons:
                    pulled = g.pulling(a)
                    bx -= 138
                    self.add_button(screen, pygame.Rect(bx, y, 130, 28), f"hitch:{i}",
                                    f"→ {self._wagon_label(pulled).upper()}" if pulled else "HITCH")
            else:
                for tack in (animals.HARNESS, animals.PACK_SADDLE):
                    price = _tack_price(tack)
                    bx -= 138
                    self.add_button(screen, pygame.Rect(bx, y, 130, 28), f"fit:{i}:{tack}",
                                    f"{tack.upper()} · {fmt_money(price)}", enabled=self.wealth >= price)
            text(screen, F["body_sm"], ellipsize(note, F["body_sm"], bx - (x + 80) - T.S),
                 (x + 80, y + 6), T.BLOOD if a.unfed_days else T.TX_MUTED)
            y += 36
        if not g.herd:
            text(screen, F["body_sm"], "No animals yet.", (x, y), T.TX_FAINT)
            y += 24
        y += T.S
        for species in data.LIVESTOCK:
            sample = animals.Animal(species)
            can = g.can_take(sample) and self.wealth >= sample.price
            self.add_button(screen, pygame.Rect(x, y, w, 40), f"buy:{species}",
                            f"BUY A {species.upper()}  ·  {fmt_money(sample.price)}", enabled=can, primary=can,
                            sub=(f"carries {sample.back_load} kg  ·  draws {sample.draw} kg  ·  speed {sample.speed:g} m"
                                 "  ·  eats a ration a day"))
            y += 46

"""
GARTOK Tactical - transfer.py
UMA tela para mercado, banco, propriedade, loot e (futuro) construcoes.

    draw_transfer(surf, size, place, members, pinned)

`place` e o unico parametro que muda entre as cinco telas:

    Place(title, rules, container, verbs, priced, capacity, tabs, services)

  mercado ....... container infinito/estoque, priced=True, tabs de categoria
  banco ......... container 30 kg, services=[alugar strongbox]
  propriedade ... container 20 kg, services=[comprar casa]
  loot .......... container = o chao, verbo "take what fits"
  construcao .... igual banco, capacidade propria

Regras unicas (ja valem no codigo hoje):
  - abaixo do normal: ok | entre normal e max: passa com penalidade
  - acima do max: a tela bloqueia
  - equipar e ESTADO, nao mover: os slots sao zonas de drop de capacidade 1
  - comprar/vender E mover, com moeda anexada

  python transfer.py --shot
"""

import sys
from dataclasses import dataclass, field

import pygame

from screens_v4 import (T, fonts, mix, text, caps, hline, button, header, footer,
                        load_bar, hp_color)


# ---------------------------------------------------------------- spec
@dataclass
class Place:
    title: str
    rules: str                    # a "regra da casa", uma linha so
    container: str                # rotulo do painel da esquerda
    verb_in: str                  # do container -> membro
    verb_out: str                 # do membro -> container
    items: list
    priced: bool = False
    capacity: tuple = None        # (usado, total) ou None = sem limite
    tabs: list = field(default_factory=list)
    services: list = field(default_factory=list)
    bulk: str = None              # verbo de lote, ex "take what fits"
    stock: bool = False


MARKET = Place(
    title="Market", rules="resale at 50%  ·  the vendor speaks Ankarin  ·  1% markup",
    container="for sale", verb_in="buy", verb_out="sell",
    priced=True, tabs=["weapons", "armor", "consumables & kit"],
    items=[("Dagger", "1d4 · 1h", 0.5, 1, "8 c", True),
           ("Hatchet", "1d6 · 1h", 1.0, 1, "10 c", True),
           ("Club", "1d6 · 1h", 1.5, 1, "6 c", True),
           ("Shortspear", "1d6 · 1h", 1.5, 1, "12 c", True),
           ("Axe", "1d8 · 1h", 3.0, 1, "35 c", True),
           ("Hammer", "1d8 · 1h", 4.0, 1, "35 c", True),
           ("Broadsword", "1d12 · 2h", 4.0, 1, "105 c", False),
           ("Rapier", "1d6 · 1h", 1.0, 1, "65 c", False),
           ("Light crossbow", "1d8 · 2h · 16m", 2.5, 2, "80 c", False),
           ("Studded leather", "armor · scarce", 6.0, 1, "45 c", True)],
    stock=True)

LOOT = Place(
    title="Loot", rules="what you leave stays behind  ·  nothing regrows here",
    container="on the ground", verb_in="take", verb_out="drop",
    items=[("Iron bar", "goods", 5.0, 3, None, True),
           ("Studded leather", "armor", 6.0, 1, None, True),
           ("Arrows", "ammo", 0.05, 24, None, True),
           ("Rope, 50 ft", "tool", 3.0, 1, None, True)],
    bulk="take what fits")

BANK = Place(
    title="The Bank", rules="the Bankers rent one strongbox  ·  a flat fee, no questions",
    container="the strongbox", verb_in="take", verb_out="store",
    capacity=(12.5, 30.0),
    items=[("Mail shirt", "armor", 12.0, 1, None, True),
           ("Dictionary of Verdant", "book", 2.0, 1, None, True)],
    services=[("Buy the house", "1000 c  ·  needs 4 standing with the Bankers", False),
              ("Rent a strongbox", "100 c  ·  30 kg held in the City", True)])


MEMBERS = [
    dict(nm="Tordundorir", race="Dwarf", occ="Linguist", kg=0.5, norm=11.0, mx=29.0,
         coin=34, hand="Dagger", off=None, armor=None, pack=[]),
    dict(nm="Skeltorma", race="Dwarf", occ="Jailer", kg=5.5, norm=23.0, mx=47.0,
         coin=12, hand="Club", off=None, armor=None,
         pack=[("Dictionary of Verdant", "book", 2.0, 1),
               ("Iron shackles", "tool", 1.0, 1), ("Cloak", "wear", 1.0, 1)]),
    dict(nm="Braedralel", race="Dwarf", occ="Thief", kg=0.5, norm=9.0, mx=24.0,
         coin=31, hand="Dagger", off=None, armor=None, pack=[]),
    dict(nm="Rurax", race="Halfling", occ="Guard", kg=7.0, norm=7.0, mx=23.0,
         coin=8, hand="Hammer", off=None, armor=None,
         pack=[("Stone brick", "goods", 7.0, 1)]),
    dict(nm="Ekmun", race="Human", occ="Hunter", kg=3.5, norm=11.0, mx=29.0,
         coin=24, hand="Shortspear", off=None, armor=None,
         pack=[("Rope, 50 ft", "tool", 3.0, 1)]),
    dict(nm="Ribit", race="Grippli", occ="Hunter", kg=1.0, norm=6.0, mx=16.0,
         coin=3, hand="Sling", off=None, armor=None, pack=[]),
]
PINNED = [0, 1, 3]


# ---------------------------------------------------------------- pecas
def qty_stepper(s, F, rect, qty):
    """Uma linha de item, uma pilha. Chao e strongbox passam a empilhar tambem."""
    pygame.draw.rect(s, T.TABLE, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    for i, sign in enumerate(("–", "+")):
        b = pygame.Rect(rect.x if i == 0 else rect.right - T.S * 2, rect.y,
                        T.S * 2, rect.h)
        caps(s, F["micro"], sign, b.center, T.TX_MUTED, center=True)
    caps(s, F["microb"], str(qty), rect.center, T.TX, center=True)


def item_line(s, F, rect, nm, sub, kg, qty, price, ok, direction="in",
              highlight=False):
    """
    A MESMA linha nos dois lados da tela e nas cinco telas.
    direction 'in'  = seta pra direita (entra no grupo)
    direction 'out' = seta pra esquerda (volta pro container)
    """
    bg = mix(T.BRASS, T.STEEL, .88) if highlight else T.TABLE
    pygame.draw.rect(s, bg, rect)
    pygame.draw.rect(s, T.BRASS if highlight else T.STEEL_LINE, rect, 1)
    # alca de arrastar: o item e objeto, nao texto
    for i in range(2):
        pygame.draw.line(s, T.TX_FAINT, (rect.x + T.S, rect.centery - 3 + i * 5),
                         (rect.x + T.S + 6, rect.centery - 3 + i * 5), 1)
    fg = T.TX if ok else T.TX_FAINT
    text(s, F["body"], nm, (rect.x + T.S * 3, rect.centery - 13), fg)
    caps(s, F["micro"], sub, (rect.x + T.S * 3, rect.centery + 3), T.TX_FAINT)

    x = rect.right - T.S * 5
    arrow = pygame.Rect(x, rect.y + T.S, T.S * 4, rect.h - T.S * 2)
    pygame.draw.rect(s, T.STEEL_LINE, arrow, 1)
    a = arrow.centerx
    d = 1 if direction == "in" else -1
    pygame.draw.lines(s, T.BRASS if ok else T.TX_FAINT, False,
                      [(a - 3 * d, arrow.centery - 4), (a + 3 * d, arrow.centery),
                       (a - 3 * d, arrow.centery + 4)], 2)
    x -= T.S * 2
    if qty > 1:
        st = pygame.Rect(x - T.S * 8, rect.centery - 8, T.S * 8, T.S * 2 + 2)
        qty_stepper(s, F, st, qty)
        x = st.x - T.S
    if price:
        caps(s, F["microb"], price, (x, rect.centery - 12), T.BRASS if ok else
             T.TX_FAINT, right=True)
    caps(s, F["micro"], f"{kg:.1f} kg", (x, rect.centery + 2),
         T.TX_FAINT, right=True)
    if not ok:
        caps(s, F["micro"], "won't fit", (rect.x + T.S * 3 +
             F["body"].size(nm)[0] + T.S, rect.centery - 10), T.BLOOD)


def source_panel(s, F, rect, place):
    pygame.draw.rect(s, T.STEEL, rect)
    pygame.draw.line(s, T.STEEL_LINE, (rect.right - 1, rect.y),
                     (rect.right - 1, rect.bottom), 1)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4
    y = rect.y + T.S * 2

    caps(s, F["microb"], place.container, (x, y), T.BRASS)
    y += T.S * 3
    if place.tabs:
        for i, t in enumerate(place.tabs):
            tw = F["micro"].size(t.upper())[0] + T.S * 3
            r = pygame.Rect(x, y, tw, T.S * 4)
            on = i == 0
            pygame.draw.rect(s, T.STEEL_HI if on else T.TABLE, r)
            pygame.draw.rect(s, T.BRASS if on else T.STEEL_LINE, r, 1)
            caps(s, F["micro"], t, r.center, T.TX if on else T.TX_FAINT, center=True)
            x += tw + T.S
        x = rect.x + T.S * 2
        y += T.S * 6
    if place.capacity:
        used, total = place.capacity
        load_bar(s, pygame.Rect(x, y, w, 8), used / total, False)
        caps(s, F["micro"], f"{used:.1f} / {total:.0f} kg held here",
             (x, y + T.S + 4), T.TX_FAINT)
        y += T.S * 5

    for nm, sub, kg, qty, price, ok in place.items:
        r = pygame.Rect(x, y, w, T.S * 6)
        item_line(s, F, r, nm, sub, kg, qty, price, ok, "in")
        y = r.bottom + T.S
    if place.stock:
        y += T.S
        caps(s, F["micro"], "greyed out  ·  nobody here can carry it or afford it",
             (x, y), T.TX_FAINT)

    if place.services:
        y = rect.bottom - T.S * (6 + 9 * len(place.services))
        hline(s, x, x + w, y)
        y += T.S * 2
        caps(s, F["micro"], "services", (x, y), T.TX_FAINT)
        y += T.S * 2
        for label, sub, enabled in place.services:
            r = pygame.Rect(x, y, w, T.S * 7)
            button(s, F, r, label, primary=enabled, sub=sub, ghost=not enabled)
            y = r.bottom + T.S * 2


def chip_rail(s, F, rect, members, pinned):
    """O trilho horizontal: todo mundo cabe, e cada ficha e alvo de soltar."""
    pygame.draw.rect(s, T.TABLE, rect)
    hline(s, rect.x, rect.right, rect.bottom - 1)
    x = rect.x + T.S * 2
    for i, m in enumerate(members):
        on = i in pinned
        free = m["mx"] - m["kg"]
        w = T.S * 20
        r = pygame.Rect(x, rect.y + T.S, w, rect.h - T.S * 2)
        pygame.draw.rect(s, T.STEEL_HI if on else T.STEEL, r)
        pygame.draw.rect(s, T.BRASS if on else T.STEEL_LINE, r, 1)
        text(s, F["body"], m["nm"][:11], (r.x + T.S, r.y + T.S - 2),
             T.TX if on else T.TX_MUTED)
        caps(s, F["micro"], f"room {free:.1f} kg", (r.x + T.S, r.y + T.S * 3 + 2),
             T.GREEN if free > 8 else T.BRASS)
        caps(s, F["micro"], f"{m['coin']} c", (r.right - T.S, r.y + T.S - 1),
             T.BRASS, right=True)
        x += w + T.S



def slot(s, F, rect, label, val):
    caps(s, F["micro"], label, (rect.x, rect.y - 13), T.TX_FAINT)
    pygame.draw.rect(s, T.TABLE, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    text(s, F["body"], val or "empty", (rect.x + T.S, rect.centery - 8),
         T.TX if val else T.TX_FAINT)
    return rect.bottom + T.S * 3


def member_column(s, F, rect, m, place):
    pygame.draw.rect(s, T.STEEL, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4

    head = pygame.Rect(rect.x, rect.y, rect.w, T.S * 10)
    pygame.draw.rect(s, T.STEEL_HI, head)
    hline(s, head.x, head.right, head.bottom)
    text(s, F["nameb"], m["nm"], (x, head.y + T.S), T.TX)
    caps(s, F["micro"], f"{m['coin']} c", (head.right - T.S * 2, head.y + T.S + 4),
         T.BRASS, right=True)
    enc = m["kg"] > m["norm"]
    load_bar(s, pygame.Rect(x, head.y + T.S * 4 + 4, w, 8), m["kg"] / m["mx"], enc)
    caps(s, F["micro"], f"{m['kg']:.1f} / normal {m['norm']:.0f}  ·  max {m['mx']:.0f}",
         (x, head.y + T.S * 6 + 4), T.BRASS if enc else T.TX_FAINT)
    if enc:
        caps(s, F["micro"], "encumbered  ·  -2 str/dex  ·  -1 speed",
             (head.right - T.S * 2, head.y + T.S * 6 + 4), T.BRASS, right=True)

    y = head.bottom + T.S * 4
    y = slot(s, F, pygame.Rect(x, y, w, T.S * 5), "main hand", m["hand"])
    y = slot(s, F, pygame.Rect(x, y, w, T.S * 5), "armor", m["armor"])
    caps(s, F["micro"], "equipping is a state, not a move  ·  drop a weapon here",
         (x, y - T.S * 2), T.TX_FAINT)
    y += T.S

    carried = sum(kg * q for _, _, kg, q in m["pack"])
    caps(s, F["micro"], f"pack · {len(m['pack'])} stacks", (x, y), T.TX_FAINT)
    caps(s, F["micro"], f"{carried:.1f} kg", (x + w, y), T.TX_FAINT, right=True)
    y += T.S * 3
    for nm, sub, kg, qty in m["pack"]:
        r = pygame.Rect(x, y, w, T.S * 6)
        price = f"{int(kg * 4)} c" if place.priced else None
        item_line(s, F, r, nm, sub, kg, qty, price, True, "out")
        y = r.bottom + T.S
    if not m["pack"]:
        caps(s, F["micro"], "carrying nothing", (x, y), T.TX_FAINT)

    drop = pygame.Rect(x, rect.bottom - T.S * 6, w, T.S * 4)
    pygame.draw.rect(s, T.STEEL_LINE, drop, 1)
    caps(s, F["micro"], f"drop here to {place.verb_in} for {m['nm'].split()[0][:8]}",
         drop.center, T.TX_FAINT, center=True)


# ---------------------------------------------------------------- tela
def draw_transfer(size, place, members=MEMBERS, pinned=PINNED):
    s = pygame.Surface(size).convert()
    s.fill(T.TABLE)
    F = fonts()
    head = pygame.Rect(0, 0, size[0], T.S * 9)
    foot = pygame.Rect(0, size[1] - T.S * 8, size[0], T.S * 8)
    left = pygame.Rect(0, head.bottom, T.S * 56, foot.y - head.bottom)
    railr = pygame.Rect(left.right, head.bottom, size[0] - left.right, T.S * 7)
    cols = pygame.Rect(left.right, railr.bottom, size[0] - left.right,
                       foot.y - railr.bottom)

    header(s, F, head, place.title, place.rules, ["here"], "here")
    purse = sum(m["coin"] for m in members)
    caps(s, F["microb"], f"purse {purse} c", (size[0] - T.S * 20, T.S * 3), T.BRASS,
         right=True)
    caps(s, F["micro"], "paid by whoever takes the item",
         (size[0] - T.S * 20, T.S * 5 + 2), T.TX_FAINT, right=True)

    source_panel(s, F, left, place)
    chip_rail(s, F, railr, members, pinned)

    gap = T.S * 2
    cw = (cols.w - gap * (len(pinned) + 1)) // len(pinned)
    for i, idx in enumerate(pinned):
        r = pygame.Rect(cols.x + gap + i * (cw + gap), cols.y + gap, cw,
                        cols.h - gap * 2)
        member_column(s, F, r, members[idx], place)

    actions = [("distribute load", False), (f"leave the {place.title.lower()}", True)]
    if place.bulk:
        actions.insert(0, (place.bulk, False))
    footer(s, F, foot,
           f"{place.verb_in} ↔ {place.verb_out}  ·  click a name to open its column  ·  "
           "drag onto a name to hand it  ·  over max load is blocked", actions)
    return s


def main():
    pygame.init()
    size = (1600, 900)
    if "--shot" in sys.argv:
        pygame.display.set_mode(size, pygame.HIDDEN)
        pygame.image.save(draw_transfer(size, MARKET), "gartok_transfer_market.png")
        pygame.image.save(draw_transfer(size, LOOT), "gartok_transfer_loot.png")
        pygame.image.save(draw_transfer(size, BANK), "gartok_transfer_bank.png")
        pygame.quit()
        return
    win = pygame.display.set_mode(size)
    frames = [draw_transfer(size, p) for p in (MARKET, LOOT, BANK)]
    i, run = 0, True
    while run:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                run = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    run = False
                else:
                    i = (i + 1) % len(frames)
        win.blit(frames[i], (0, 0))
        pygame.display.flip()
        pygame.time.wait(16)
    pygame.quit()


if __name__ == "__main__":
    main()

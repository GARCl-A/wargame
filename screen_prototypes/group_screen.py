"""
GARTOK Tactical - tela de GRUPO (v6)

Uma tela, duas visoes, o mesmo trilho lateral:

  BAGS   - o personagem como compartimento. 3 colunas fixadas, mochila visivel,
           arrastar entre colunas ou clicar o item e escolher o destino.
  CARGO  - a mesma banda vista como carga: tudo em uma tabela, ordenavel por
           peso, com selecao em lote pra preparar venda ou redistribuicao.

Trocar de visao nao perde selecao nem quem esta fixado.
Mercado e strongbox NAO vivem aqui: sao lugares, tem tela propria.

  python group_v6.py --shot
"""

import sys

import pygame

from screens_v4 import (T, fonts, mix, text, caps, hline, button, header, footer,
                        load_bar, role_mark, hp_color)

# ---------------------------------------------------------------- dados
MEMBERS = [
    dict(k="grokvyr",  nm="Grokvyrdrixek", role="vanguard", kg=8.5,  cap=9.0,
         hp=(3, 10), hand="Club", off=None, body=None,
         pack=[("Iron shackles", "tool", 1.0, 1), ("Rope, 50 ft", "tool", 3.0, 1),
               ("Tinderbox", "camp", 0.5, 1)]),
    dict(k="grokhrom", nm="Grokhromlysfel", role="healer", kg=2.5, cap=6.0,
         hp=(1, 9), hand="Quarterstaff", off=None, body=None,
         pack=[("Holy symbol", "relic", 0.5, 1)]),
    dict(k="vyrkael",  nm="Vyrkaelbrae", role="hand", kg=1.5, cap=23.0,
         hp=(8, 8), hand="Dagger", off=None, body="Cloak",
         pack=[("Lockpicks", "tool", 0.3, 1)]),
    dict(k="sella",    nm="Sella Vond", role="archer", kg=14.0, cap=15.0,
         hp=(6, 7), hand="Shortbow", off="Quiver", body="Leather",
         pack=[("Arrows", "ammo", 0.05, 24), ("Bedroll", "camp", 2.0, 1)]),
    dict(k="bren",     nm="Bren Oduld", role="hand", kg=31.0, cap=24.0,
         hp=(9, 11), hand="Felling axe", off="Shield", body="Mail",
         hand_by="Tam", pack=[("Pick", "tool", 4.0, 1)]),
    dict(k="tam",      nm="Tam Reddle", role="hand", kg=46.0, cap=20.0,
         hp=(5, 9), hand="Spear", off=None, body="Padded",
         pack=[("Iron ore", "goods", 1.0, 40), ("Silver candlesticks", "loot", 2.0, 3),
               ("Felling axe", "tool", 6.0, 1)]),
    dict(k="oder",     nm="Oder Vash", role="vanguard", kg=12.0, cap=18.0,
         hp=(7, 12), hand="Mace", off="Shield", body="Mail", pack=[]),
    dict(k="isa",      nm="Isa Quill", role="archer", kg=5.0, cap=12.0,
         hp=(4, 8), hand="Sling", off=None, body=None, pack=[]),
    dict(k="rill",     nm="Rill", role="hand", kg=3.0, cap=14.0,
         hp=(6, 6), hand="Knife", off=None, body=None, pack=[]),
    dict(k="hask",     nm="Hask Dun", role="hand", kg=9.0, cap=21.0,
         hp=(9, 9), hand="Hammer", off=None, body="Padded", pack=[]),
]
BY_KEY = {m["k"]: m for m in MEMBERS}
PINNED = ["grokvyr", "bren", "tam"]
SELECTED = "tam"
SELECTED_ITEM = ("tam", 0)          # o minerio: a linha com o menu aberto

TAG_COLOR = {"goods": T.TX_FAINT, "tool": T.BLUE, "armor": T.TX_MUTED,
             "weapon": T.TX_MUTED, "ammo": T.TX_FAINT, "loot": T.BRASS,
             "relic": T.BRASS, "wear": T.TX_FAINT, "camp": T.TX_FAINT}


def short(nm):
    return nm.split()[0][:8]


# ---------------------------------------------------------------- trilho
def rail(s, F, rect, view):
    """
    O trilho e o que faz a tela escalar pra 10 e o que torna o arrastar util:
    todo nome aqui e um alvo de soltar, esteja a coluna aberta ou nao.
    """
    pygame.draw.rect(s, T.STEEL, rect)
    pygame.draw.line(s, T.STEEL_LINE, (rect.right - 1, rect.y),
                     (rect.right - 1, rect.bottom), 1)
    x, w = rect.x + T.S * 2, rect.w - T.S * 4
    y = rect.y + T.S * 2
    caps(s, F["micro"], "band  ·  6 of 10", (x, y), T.TX_FAINT)
    caps(s, F["micro"], "free", (x + w, y), T.TX_FAINT, right=True)
    y += T.S * 3

    for m in MEMBERS:
        if not m["pack"] and m["k"] not in PINNED and m["kg"] < 1:
            pass
        pinned = m["k"] in PINNED
        r = pygame.Rect(x, y, w, T.S * 7)
        pygame.draw.rect(s, T.STEEL_HI if pinned else T.TABLE, r)
        pygame.draw.rect(s, T.BRASS if m["k"] == SELECTED else T.STEEL_LINE, r, 1)
        if pinned:                       # marca de fixado: a coluna esta aberta
            pygame.draw.rect(s, T.BRASS, pygame.Rect(r.x, r.y, 3, r.h))
        role_mark(s, (r.x + T.S * 2, r.y + T.S * 2), m["role"], T.TX_MUTED)
        text(s, F["body"], short(m["nm"]), (r.x + T.S * 4, r.y + T.S - 2),
             T.TX if pinned else T.TX_MUTED)
        free = m["cap"] - m["kg"]
        caps(s, F["micro"], f"{free:+.1f}", (r.right - T.S, r.y + T.S), 
             T.BLOOD if free < 0 else T.GREEN if free > 4 else T.TX_MUTED, right=True)
        load_bar(s, pygame.Rect(r.x + T.S, r.y + T.S * 4, r.w - T.S * 2, 6),
                 m["kg"] / m["cap"], m["kg"] > m["cap"])
        y = r.bottom + 4

    y += T.S
    hline(s, x, x + w, y)
    y += T.S * 2
    caps(s, F["micro"], "click to pin  ·  drop to hand over", (x, y), T.TX_FAINT)


def view_switch(s, F, pos, view):
    for i, lab in enumerate(("bags", "cargo")):
        w = T.S * 12
        r = pygame.Rect(pos[0] + i * w, pos[1], w, T.S * 4)
        on = lab == view
        pygame.draw.rect(s, T.STEEL_HI if on else T.TABLE, r)
        pygame.draw.rect(s, T.BRASS if on else T.STEEL_LINE, r, 1)
        caps(s, F["microb"], lab, r.center, T.TX if on else T.TX_FAINT, center=True)
    return pygame.Rect(pos[0], pos[1], T.S * 24, T.S * 4)


# ---------------------------------------------------------------- visao BAGS
def slot(s, F, rect, label, val, note=None):
    caps(s, F["micro"], label, (rect.x, rect.y - 13), T.TX_FAINT)
    pygame.draw.rect(s, T.TABLE, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    text(s, F["body"], val or "empty", (rect.x + T.S, rect.centery - 8),
         T.TX_FAINT if not val else T.TX)
    if note:
        caps(s, F["micro"], note, (rect.right - T.S, rect.centery - 5), T.BRASS,
             right=True)
    return rect.bottom + T.S * 3


def item_row(s, F, rect, it, selected=False):
    nm, tag, kg, qty = it
    pygame.draw.rect(s, mix(T.BRASS, T.STEEL, .85) if selected else T.TABLE, rect)
    pygame.draw.rect(s, T.BRASS if selected else T.STEEL_LINE, rect, 1)
    # alca de arrastar: dois tracinhos. o item e um objeto, nao uma linha de texto
    for i in range(2):
        pygame.draw.line(s, T.TX_FAINT, (rect.x + T.S, rect.centery - 3 + i * 5),
                         (rect.x + T.S + 6, rect.centery - 3 + i * 5), 1)
    text(s, F["body"], nm, (rect.x + T.S * 3, rect.centery - 13), T.TX)
    caps(s, F["micro"], tag, (rect.x + T.S * 3, rect.centery + 3), TAG_COLOR[tag])
    if qty > 1:
        caps(s, F["microb"], f"×{qty}", (rect.right - T.S * 11, rect.centery - 12),
             T.TX_MUTED, right=True)
    total = kg * qty
    caps(s, F["micro"], f"{total:.1f} kg", (rect.right - T.S * 11, rect.centery + 2),
         T.BLOOD if total >= 10 else T.TX_FAINT, right=True)
    # botao de entregar: o caminho por clique, sempre visivel
    b = pygame.Rect(rect.right - T.S * 9, rect.y + T.S, T.S * 8, rect.h - T.S * 2)
    pygame.draw.rect(s, T.STEEL_LINE, b, 1)
    caps(s, F["micro"], "hand ›", b.center, T.TX_MUTED, center=True)
    return b


def member_column(s, F, rect, m, sel_item=None):
    pygame.draw.rect(s, T.STEEL, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    over = m["kg"] > m["cap"]
    x, w = rect.x + T.S * 2, rect.w - T.S * 4

    head = pygame.Rect(rect.x, rect.y, rect.w, T.S * 11)
    pygame.draw.rect(s, T.STEEL_HI, head)
    hline(s, head.x, head.right, head.bottom)
    role_mark(s, (x + 8, head.y + T.S * 2 + 2), m["role"], T.TX_MUTED)
    text(s, F["nameb"], m["nm"], (x + T.S * 3, head.y + T.S), T.TX)
    cur, mx = m["hp"]
    caps(s, F["micro"], f"{cur}/{mx} hp", (head.right - T.S * 2, head.y + T.S + 2),
         hp_color(cur / mx), right=True)
    load_bar(s, pygame.Rect(x, head.y + T.S * 5, w, 8), m["kg"] / m["cap"], over)
    caps(s, F["micro"], f"{m['kg']:.1f} / {m['cap']:.0f} kg",
         (x, head.y + T.S * 7 + 2), T.BLOOD if over else T.TX_MUTED)
    if over:
        caps(s, F["micro"], f"overloaded  ·  {m['kg'] - m['cap']:.1f} kg too much",
             (head.right - T.S * 2, head.y + T.S * 7 + 2), T.BLOOD, right=True)

    y = head.bottom + T.S * 4
    y = slot(s, F, pygame.Rect(x, y, w, T.S * 5), "main hand", m["hand"],
             note=f"carried by {m['hand_by']}" if m.get("hand_by") else None)
    y = slot(s, F, pygame.Rect(x, y, w, T.S * 5), "off hand", m["off"])
    y = slot(s, F, pygame.Rect(x, y, w, T.S * 5), "body", m["body"])

    carried = sum(kg * q for _, _, kg, q in m["pack"])
    caps(s, F["micro"], f"pack  ·  {len(m['pack'])} stacks", (x, y), T.TX_FAINT)
    caps(s, F["micro"], f"{carried:.1f} kg", (x + w, y), T.TX_FAINT, right=True)
    y += T.S * 3
    for i, it in enumerate(m["pack"]):
        r = pygame.Rect(x, y, w, T.S * 6)
        item_row(s, F, r, it, selected=(sel_item == i))
        y = r.bottom + T.S
    if not m["pack"]:
        caps(s, F["micro"], "carrying nothing", (x, y), T.TX_FAINT)

    # rodape da coluna: area de soltar explicita
    drop = pygame.Rect(x, rect.bottom - T.S * 7, w, T.S * 5)
    pygame.draw.rect(s, T.STEEL_LINE, drop, 1)
    caps(s, F["micro"], "drop here to give to " + short(m["nm"]), drop.center,
         T.TX_FAINT, center=True)


def hand_popup(s, F, anchor, item="Iron ore ×40", kg=40.0):
    w, h = T.S * 30, T.S * 28
    r = pygame.Rect(anchor[0], anchor[1], w, h)
    pygame.draw.rect(s, (8, 9, 11), r.move(4, 5))
    pygame.draw.rect(s, T.STEEL_HI, r)
    pygame.draw.rect(s, T.BRASS, r, 1)
    caps(s, F["microb"], f"hand {item} to", (r.x + T.S * 2, r.y + T.S * 2), T.TX)
    caps(s, F["micro"], f"{kg:.0f} kg  ·  or split the stack",
         (r.x + T.S * 2, r.y + T.S * 4), T.TX_FAINT)
    y = r.y + T.S * 7
    for m in MEMBERS[:6]:
        if m["k"] == "tam":
            continue
        free = m["cap"] - m["kg"]
        ok = free >= kg
        row = pygame.Rect(r.x + T.S, y, r.w - T.S * 2, T.S * 4)
        if m["k"] == "vyrkael":
            pygame.draw.rect(s, T.STEEL_LINE, row)
        text(s, F["body"], short(m["nm"]), (row.x + T.S, row.centery - 8),
             T.TX if ok else T.TX_FAINT)
        caps(s, F["micro"], f"{free:+.1f} kg free" if ok else f"only {free:+.1f} kg",
             (row.right - T.S, row.centery - 5), T.GREEN if ok else T.TX_FAINT,
             right=True)
        y = row.bottom + 2
    hline(s, r.x + T.S, r.right - T.S, y + T.S)
    caps(s, F["micro"], "nobody can take all 40 kg  ·  split it", (r.x + T.S * 2,
         y + T.S * 3), T.BRASS)


# ---------------------------------------------------------------- visao CARGO
def cargo_view(s, F, rect):
    rows = []
    for m in MEMBERS:
        for it in m["pack"]:
            rows.append((it, m))
        if m.get("hand_by"):
            pass
    rows.sort(key=lambda t: -t[0][2] * t[0][3])

    hd = pygame.Rect(rect.x, rect.y, rect.w, T.S * 3)
    pygame.draw.rect(s, T.TABLE, hd)
    for lab, dx in (("item", T.S * 5), ("weight", T.S * 40), ("carried by", T.S * 52),
                    ("used by", T.S * 70)):
        caps(s, F["micro"], lab, (rect.x + dx, hd.centery - 5), T.TX_FAINT)
    caps(s, F["micro"], "↓", (rect.x + T.S * 49, hd.centery - 5), T.BRASS)
    hline(s, rect.x, rect.right, hd.bottom)

    y = hd.bottom
    for i, (it, m) in enumerate(rows):
        nm, tag, kg, qty = it
        r = pygame.Rect(rect.x, y, rect.w, T.S * 5)
        sel = i in (0, 1)
        pygame.draw.rect(s, mix(T.BRASS, T.STEEL, .88) if sel else T.STEEL, r)
        hline(s, r.x, r.right, r.bottom - 1)
        cb = pygame.Rect(r.x + T.S * 2, r.centery - 6, 12, 12)
        pygame.draw.rect(s, T.BRASS if sel else T.STEEL_LINE, cb, 1)
        if sel:
            pygame.draw.lines(s, T.BRASS, False, [(cb.x + 3, cb.centery),
                              (cb.centerx, cb.bottom - 4), (cb.right - 3, cb.y + 3)], 2)
        label = f"{nm} ×{qty}" if qty > 1 else nm
        text(s, F["body"], label, (r.x + T.S * 5, r.centery - 8), T.TX)
        caps(s, F["micro"], tag, (r.x + T.S * 5 + F["body"].size(label)[0] + T.S,
             r.centery - 5), TAG_COLOR[tag])
        total = kg * qty
        text(s, F["bodyb"] if total >= 10 else F["body"], f"{total:.1f} kg",
             (r.x + T.S * 48, r.centery - 8), T.BLOOD if total >= 10 else T.TX_MUTED,
             right=True)
        cc = pygame.Rect(r.x + T.S * 52, r.centery - 12, T.S * 13, T.S * 3)
        pygame.draw.rect(s, T.TABLE, cc)
        pygame.draw.rect(s, T.STEEL_LINE, cc, 1)
        caps(s, F["micro"], short(m["nm"]), (cc.x + T.S, cc.centery - 5), T.TX_MUTED)
        caps(s, F["micro"], "▾", (cc.right - T.S, cc.centery - 5), T.TX_FAINT, right=True)
        used = "Bren" if nm == "Felling axe" else None
        if used:
            caps(s, F["microb"], used, (r.x + T.S * 70, r.centery - 5), T.BRASS)
            caps(s, F["micro"], "wields it, Tam carries it",
                 (r.x + T.S * 78, r.centery - 5), T.BRASS)
        else:
            caps(s, F["micro"], "—", (r.x + T.S * 70, r.centery - 5), T.TX_FAINT)
        y = r.bottom

    bulk = pygame.Rect(rect.x, rect.bottom - T.S * 7, rect.w, T.S * 7)
    pygame.draw.rect(s, T.TABLE, bulk)
    hline(s, bulk.x, bulk.right, bulk.y, T.BRASS)
    caps(s, F["microb"], "2 selected  ·  46.0 kg  ·  frees Tam completely",
         (bulk.x + T.S * 3, bulk.centery - 6), T.BRASS)
    bx = bulk.right - T.S * 3
    for lab, prim in (("hand to…", True), ("split stack", False), ("drop", False)):
        w = T.S * 16
        button(s, F, pygame.Rect(bx - w, bulk.y + T.S * 2, w, bulk.h - T.S * 4), lab,
               primary=prim)
        bx -= w + T.S


# ---------------------------------------------------------------- telas
def screen(size, view="bags"):
    s = pygame.Surface(size).convert()
    s.fill(T.TABLE)
    F = fonts()
    head = pygame.Rect(0, 0, size[0], T.S * 9)
    foot = pygame.Rect(0, size[1] - T.S * 8, size[0], T.S * 8)
    bar = pygame.Rect(0, head.bottom, size[0], T.S * 7)
    left = pygame.Rect(0, bar.bottom, T.S * 26, foot.y - bar.bottom)
    mid = pygame.Rect(left.right, bar.bottom, size[0] - left.right,
                      foot.y - bar.bottom)

    header(s, F, head, "Grokvyrdrixek's Band",
           "6 / 10 members  ·  ankareth  ·  no orders",
           ["gear", "quests", "orders"], "gear")

    # barra de estado da banda + troca de visao
    pygame.draw.rect(s, T.TABLE, bar)
    hline(s, bar.x, bar.right, bar.bottom - 1)
    view_switch(s, F, (T.S * 2, bar.y + T.S * 2), view)
    x = T.S * 30
    for lab, val, col, sub in (("band load", "103 / 97 kg", T.BLOOD, "+35% travel"),
                               ("supplies", "0 days", T.BLOOD, "hunger in 6 h"),
                               ("condition", "3 hurt", T.BLOOD, "1 at death's door")):
        caps(s, F["micro"], lab, (x, bar.centery - 13), T.TX_FAINT)
        text(s, F["bodyb"], val, (x, bar.centery), col)
        caps(s, F["micro"], sub, (x + F["bodyb"].size(val)[0] + T.S, bar.centery + 3),
             T.TX_FAINT)
        x += T.S * 34
    button(s, F, pygame.Rect(bar.right - T.S * 24, bar.y + T.S * 2, T.S * 22,
                             bar.h - T.S * 4), "split load evenly")

    rail(s, F, left, view)

    if view == "bags":
        gap = T.S * 2
        cw = (mid.w - gap * 4) // 3
        for i, k in enumerate(PINNED):
            r = pygame.Rect(mid.x + gap + i * (cw + gap), mid.y + gap, cw,
                            mid.h - gap * 2)
            member_column(s, F, r, BY_KEY[k],
                          sel_item=0 if k == SELECTED_ITEM[0] else None)
        col_x = mid.x + T.S * 2 + 2 * (cw + T.S * 2)
        hand_popup(s, F, (col_x - T.S * 31, mid.y + T.S * 36))
        hint = "drag an item onto a column or a name  ·  or use hand ›"
    else:
        cargo_view(s, F, mid.inflate(-T.S * 2, -T.S * 2))
        hint = "sort by weight, select in bulk, then hand it over"

    footer(s, F, foot, hint, [("distribute load", False), ("back to map", True)])
    return s


def main():
    pygame.init()
    size = (1600, 900)
    if "--shot" in sys.argv:
        pygame.display.set_mode(size, pygame.HIDDEN)
        pygame.image.save(screen(size, "bags"), "gartok_v6_bags.png")
        pygame.image.save(screen(size, "cargo"), "gartok_v6_cargo.png")
        pygame.quit()
        return
    win = pygame.display.set_mode(size)
    frames = [screen(size, "bags"), screen(size, "cargo")]
    i, run = 0, True
    while run:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                run = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    run = False
                else:
                    i = (i + 1) % 2
        win.blit(frames[i], (0, 0))
        pygame.display.flip()
        pygame.time.wait(16)
    pygame.quit()


if __name__ == "__main__":
    main()
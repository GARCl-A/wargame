"""
GARTOK Tactical - tela de BANDA e tela de GUILDA (v4)

Divisao de funcao:
  BANDA  = prontidao. "esse grupo aguenta o que eu vou mandar?"
           carga, papeis, comida, ferimento, slots. 1 linha por membro (ate 10).
  GUILDA = alocacao. "que gente eu tenho e onde ela esta?"
           quadro de bandas por proposito + reserva. pessoa e o que se move.

Componentes compartilhados: header, tabs, member_row, load_bar, role_mark,
item_row, footer. Os dois arquivos de tela consomem os mesmos helpers.

  python screens_v4.py --shot
"""

import os
import sys

import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gartok.ui.tokens import T, mix, fonts as _ui_fonts
from gartok.ui.primitives import text, caps, hline, draw_button
from gartok.ui.inspector_panel import draw_role, ROLE_MARK
from gartok.ui.roster_panel import hp_color

# Not in the shared war-table palette yet (gartok/ui/tokens.py) -- only the
# guild-screen prototype's garrison-band color uses it.
BLUE = (92, 124, 150)


def fonts():
    """Shared war-table fonts plus a serif display size these prototypes
    use for screen titles -- not in gartok/ui/tokens.py yet."""
    F = _ui_fonts()
    F["titleb"] = pygame.font.SysFont("dejavuserif,georgia,serif", 24, bold=True)
    return F


# ---------------------------------------------------------------- helpers
def role_mark(s, p, kind, c):
    draw_role(s, p, ROLE_MARK.get(kind, "sword"), c)


def load_bar(s, rect, ratio, over=False):
    """Barra de carga: o traco marca o limite normal, o excesso vira sangue."""
    pygame.draw.rect(s, T.TABLE, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    w = int((rect.w - 2) * min(ratio, 1.0))
    col = T.BLOOD if over else T.GREEN if ratio < .7 else T.BRASS
    pygame.draw.rect(s, col, pygame.Rect(rect.x + 1, rect.y + 1, w, rect.h - 2))
    mark = rect.x + int((rect.w - 2) * .72)
    pygame.draw.line(s, T.TX_FAINT, (mark, rect.y - 2), (mark, rect.bottom + 2), 1)


ROLES = ["vanguard", "hand", "archer", "healer"]


def button(s, F, rect, label, primary=False, ghost=False, sub=None, danger=False):
    if primary:
        fill = T.BLOOD if danger else T.BRASS
        pygame.draw.rect(s, fill, rect)
        fg = (255, 245, 238) if danger else T.TABLE
    else:
        pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
        fg = T.TX_FAINT if ghost else T.TX_MUTED
    y = rect.centery - (9 if sub else 0)
    caps(s, F["microb"], label, (rect.centerx, y), fg, center=True)
    if sub:
        text(s, F["micro"], sub, (rect.centerx, rect.centery + 10),
             mix(fg, T.TABLE, .3) if primary else T.TX_FAINT, center=True)
    return rect


def tabs(s, F, pos, items, active, mpos=(-1, -1), right=False):
    x = pos[0]
    widths = []
    for t in items:
        w = F["microb"].size(t.upper())[0] + T.S * 4
        widths.append(w)
    if right:
        x -= sum(widths)
    rects = {}
    for t, w in zip(items, widths):
        r = pygame.Rect(x, pos[1], w, T.S * 4)
        rects[t] = r
        on = t == active
        # Use ghost=not on so the active tab looks "pressed" or highlighted
        draw_button(s, F, r, t, ghost=not on, mpos=mpos)
        if on:
            pygame.draw.line(s, T.BRASS, (r.x, r.bottom - 2), (r.right, r.bottom - 2), 2)
        x += w
    return rects


def header(s, F, rect, title, sub, tabitems, active, mpos=(-1, -1)):
    pygame.draw.rect(s, T.STEEL, rect)
    hline(s, rect.x, rect.right, rect.bottom - 1)
    # voltar: seta discreta, nao botao
    cx = rect.x + T.S * 3
    pygame.draw.lines(s, T.TX_MUTED, False,
                      [(cx + 6, rect.centery - 7), (cx - 2, rect.centery),
                       (cx + 6, rect.centery + 7)], 2)
    text(s, F["titleb"], title, (rect.x + T.S * 6, rect.y + T.S * 2), T.TX)
    caps(s, F["micro"], sub, (rect.x + T.S * 6, rect.y + T.S * 2 + 30), T.TX_FAINT)
    return tabs(s, F, (rect.right - T.S * 3, rect.y + T.S * 2), tabitems, active, mpos=mpos, right=True)


def footer(s, F, rect, hint, actions, mpos=(-1, -1)):
    pygame.draw.rect(s, T.STEEL, rect)
    hline(s, rect.x, rect.right, rect.y)
    caps(s, F["micro"], hint, (rect.x + T.S * 3, rect.centery - 6), T.TX_FAINT)
    x = rect.right - T.S * 3
    for label, primary in reversed(actions):
        w = T.S * 22 if primary else T.S * 18
        r = pygame.Rect(x - w, rect.y + T.S * 2, w, rect.h - T.S * 4)
        draw_button(s, F, r, label, primary=primary, mpos=mpos)
        x -= w + T.S * 2


def stat_block(s, F, rect, label, value, color=T.TX, sub=None):
    pygame.draw.rect(s, T.TABLE, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    caps(s, F["micro"], label, (rect.x + T.S * 2, rect.y + T.S), T.TX_FAINT)
    text(s, F["big"], value, (rect.x + T.S * 2, rect.y + T.S * 3), color)
    if sub:
        caps(s, F["micro"], sub, (rect.x + T.S * 2, rect.y + T.S * 9), color)


# ---------------------------------------------------------------- dados
BAND = dict(
    name="Grokvyrdrixek's Band", lead="Grokvyrdrixek", where="Ankareth",
    state="NO ORDERS",
    members=[
        dict(nm="Grokvyrdrixek", race="Grippli", cls="Jailer", role="vanguard",
             hp=(3, 10), ac=10, hand="Club", off="—", body="—",
             pack=["Iron Shackles", "Rope", "Tinderbox"], kg=8.5, cap=9.0, lvl=None),
        dict(nm="Grokhromlysfel", race="Centaur", cls="Priest", role="healer",
             hp=(1, 9), ac=12, hand="Quarterstaff", off="—", body="—",
             pack=["Holy Symbol"], kg=2.5, cap=6.0, lvl=2),
        dict(nm="Vyrkaelbrae", race="Human", cls="Thief", role="hand",
             hp=(8, 8), ac=10, hand="Dagger", off="free", body="—",
             pack=["Cloak", "Lockpicks"], kg=1.5, cap=23.0, lvl=None),
        dict(nm="Sella Vond", race="Human", cls="Archer", role="archer",
             hp=(6, 7), ac=11, hand="Shortbow", off="Quiver", body="Leather",
             pack=["Arrows ×24", "Bedroll"], kg=14.0, cap=15.0, lvl=None),
        dict(nm="Bren Oduld", race="Dwarf", cls="Hand", role="hand",
             hp=(9, 11), ac=13, hand="Axe", off="Shield", body="Mail",
             pack=["Rations ×0", "Pick"], kg=31.0, cap=24.0, lvl=1),
        dict(nm="Tam Reddle", race="Human", cls="Hand", role="hand",
             hp=(5, 9), ac=10, hand="Spear", off="—", body="Padded",
             pack=["Ore ×40kg"], kg=46.0, cap=20.0, lvl=None),
    ])

STRONGBOX = [("Mail Shirt", "12 kg", "armor"), ("Longsword", "3 kg", "hand"),
             ("Rations ×12", "6 kg", "supply"), ("Healing draught", "0.5 kg", "supply"),
             ("Iron ingots ×5", "25 kg", "goods")]

BANDS = [
    dict(nm="Grokvyrdrixek's Band", kind="ADVENTURING", where="Ankareth",
         n=6, cap=10, hurt=3, col=T.BRASS),
    dict(nm="Pyrskeldral's Band", kind="ADVENTURING", where="→ Arena",
         n=4, cap=10, hurt=0, col=T.BRASS),
    dict(nm="Hold Watch", kind="GARRISON", where="Ledger Hold",
         n=8, cap=8, hurt=1, col=BLUE),
    dict(nm="Ankareth Watch", kind="GARRISON", where="Ankareth",
         n=6, cap=8, hurt=0, col=BLUE),
    dict(nm="Seam Crew", kind="WORK", where="The Claim",
         n=7, cap=8, hurt=0, col=T.GREEN),
    dict(nm="Timber Crew", kind="WORK", where="Lumber Yard",
         n=5, cap=8, hurt=2, col=T.GREEN),
    dict(nm="Salt Caravan", kind="TRADE", where="→ Ledger Hold",
         n=4, cap=6, hurt=0, col=T.TX_MUTED),
    dict(nm="Coin Runners", kind="TRADE", where="Market",
         n=3, cap=6, hurt=0, col=T.TX_MUTED),
]

RESERVE = 27


# ---------------------------------------------------------------- banda
def member_row(s, F, rect, m, selected=False):
    pygame.draw.rect(s, T.STEEL_HI if selected else T.STEEL, rect)
    hline(s, rect.x, rect.right, rect.bottom - 1)
    if selected:
        pygame.draw.rect(s, T.BRASS, pygame.Rect(rect.x, rect.y, 3, rect.h))

    x = rect.x + T.S * 3
    role_mark(s, (x + 6, rect.centery), m["role"], T.TX_MUTED)
    x += T.S * 3
    text(s, F["nameb"] if selected else F["name"], m["nm"],
         (x, rect.centery - 16), T.TX if selected else T.TX_MUTED)
    caps(s, F["micro"], f"{m['race']} · {m['cls']}", (x, rect.centery + 4), T.TX_FAINT)
    if m["lvl"]:
        badge = pygame.Rect(x + F["name"].size(m["nm"])[0] + T.S, rect.centery - 15,
                            T.S * 7, T.S * 2)
        pygame.draw.rect(s, T.BRASS_DIM, badge)
        caps(s, F["micro"], f"level ×{m['lvl']}", badge.center, T.TABLE, center=True)

    # condicao
    cx = rect.x + T.S * 34
    cur, mx = m["hp"]
    text(s, F["bodyb"], f"{cur}", (cx, rect.centery - 8), hp_color(cur / mx))
    text(s, F["micro"], f"/{mx} hp", (cx + 16, rect.centery - 5), T.TX_FAINT)
    text(s, F["micro"], f"ac {m['ac']}", (cx, rect.centery + 8), T.TX_FAINT)

    # slots inline
    for i, (lab, val) in enumerate((("hand", m["hand"]), ("off", m["off"]),
                                    ("body", m["body"]))):
        sx = rect.x + T.S * 44 + i * T.S * 17
        box = pygame.Rect(sx, rect.centery - 15, T.S * 16, T.S * 4)
        empty = val in ("—", "free")
        pygame.draw.rect(s, T.TABLE, box)
        pygame.draw.rect(s, T.STEEL_LINE, box, 1)
        caps(s, F["micro"], lab, (box.x + 6, box.y - 12), T.TX_FAINT)
        text(s, F["body"], val, (box.x + 8, box.centery - 8),
             T.TX_FAINT if empty else T.TX_MUTED)

    # mochila + carga
    px = rect.x + T.S * 96
    caps(s, F["micro"], f"pack {len(m['pack'])}", (px, rect.centery - 14), T.TX_FAINT)
    text(s, F["micro"], ", ".join(m["pack"])[:26], (px, rect.centery + 1), T.TX_MUTED)

    lx = rect.right - T.S * 20
    over = m["kg"] > m["cap"]
    load_bar(s, pygame.Rect(lx, rect.centery - 10, T.S * 15, 8), m["kg"] / m["cap"], over)
    text(s, F["micro"], f"{m['kg']:.1f} / {m['cap']:.0f} kg",
         (lx, rect.centery + 4), T.BLOOD if over else T.TX_FAINT)


def side_slot(s, F, rect, label, val, weight=None, dice=None, empty=False):
    caps(s, F["micro"], label, (rect.x, rect.y - 14), T.TX_FAINT)
    pygame.draw.rect(s, T.TABLE, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    text(s, F["body"], val, (rect.x + T.S, rect.centery - 8),
         T.TX_FAINT if empty else T.TX)
    if dice:
        caps(s, F["micro"], dice, (rect.right - T.S, rect.centery - 5),
             T.TX_MUTED, right=True)
    if weight:
        caps(s, F["micro"], weight, (rect.right - T.S * 9, rect.centery - 5),
             T.TX_FAINT, right=True)
    return rect.bottom + T.S * 2


def band_side(s, F, rect, m):
    pygame.draw.rect(s, T.STEEL, rect)
    pygame.draw.line(s, T.STEEL_LINE, (rect.x, rect.y), (rect.x, rect.bottom), 1)
    x, w = rect.x + T.S * 3, rect.w - T.S * 6
    y = rect.y + T.S * 3
    text(s, F["nameb"], m["nm"], (x, y), T.TX)
    y += T.S * 3
    caps(s, F["micro"], f"{m['race']} · {m['cls']}  ·  carries for the band", (x, y),
         T.TX_FAINT)
    y += T.S * 4

    y = side_slot(s, F, pygame.Rect(x, y, w, T.S * 5), "main hand", m["hand"],
                  "2 kg", "1d6 -3")
    y = side_slot(s, F, pygame.Rect(x, y, w, T.S * 5), "off hand", "free", empty=True)
    y = side_slot(s, F, pygame.Rect(x, y, w, T.S * 5), "body", "no armor", empty=True)

    caps(s, F["micro"], f"pack · {len(m['pack'])} items", (x, y), T.TX_FAINT)
    caps(s, F["micro"], f"{m['kg']:.1f} kg", (x + w, y), T.TX_FAINT, right=True)
    y += T.S * 2
    for it in m["pack"]:
        r = pygame.Rect(x, y, w, T.S * 4)
        pygame.draw.rect(s, T.TABLE, r)
        text(s, F["body"], it, (r.x + T.S, r.centery - 8), T.TX_MUTED)
        caps(s, F["micro"], "1 kg", (r.right - T.S, r.centery - 5), T.TX_FAINT, right=True)
        y = r.bottom + 4
    y += T.S * 2

    hline(s, x, x + w, y)
    y += T.S * 2
    # fonte de itens: so existe porque a banda ESTA em Ankareth
    caps(s, F["microb"], "strongbox · ankareth", (x, y), T.BRASS)
    y += T.S * 2
    caps(s, F["micro"], "available because the band is here", (x, y), T.TX_FAINT)
    y += T.S * 3
    for nm, kg, _ in STRONGBOX:
        r = pygame.Rect(x, y, w, T.S * 4)
        pygame.draw.rect(s, T.TABLE, r)
        pygame.draw.rect(s, T.STEEL_LINE, r, 1)
        text(s, F["body"], nm, (r.x + T.S, r.centery - 8), T.TX_MUTED)
        caps(s, F["micro"], kg, (r.right - T.S * 5, r.centery - 5), T.TX_FAINT, right=True)
        # seta de transferencia
        ax = r.right - T.S * 2
        pygame.draw.lines(s, T.BRASS, False, [(ax - 8, r.centery - 4), (ax, r.centery),
                                              (ax - 8, r.centery + 4)], 2)
        y = r.bottom + 4


def readiness(s, F, rect):
    """A faixa que responde 'aguenta?'. Carga em CONSEQUENCIA, nao em kg."""
    pygame.draw.rect(s, T.TABLE, rect)
    hline(s, rect.x, rect.right, rect.bottom - 1)
    w = (rect.w - T.S * 8) // 4
    y = rect.y + T.S * 2
    h = rect.h - T.S * 4

    r1 = pygame.Rect(rect.x + T.S * 3, y, w, h)
    stat_block(s, F, r1, "band load", "103 / 97 kg", T.BLOOD, "overloaded · +35% travel")
    load_bar(s, pygame.Rect(r1.x + T.S * 2, r1.y + T.S * 7, r1.w - T.S * 4, 6),
             1.06, True)

    r2 = pygame.Rect(r1.right + T.S * 2, y, w, h)
    pygame.draw.rect(s, T.TABLE, r2)
    pygame.draw.rect(s, T.STEEL_LINE, r2, 1)
    caps(s, F["micro"], "roles covered", (r2.x + T.S * 2, r2.y + T.S), T.TX_FAINT)
    rx = r2.x + T.S * 2 + 8
    have = {"vanguard": 1, "hand": 3, "archer": 1, "healer": 1}
    for role in ROLES:
        n = have[role]
        role_mark(s, (rx, r2.y + T.S * 5), role, T.TX_MUTED if n else T.TX_FAINT)
        caps(s, F["micro"], f"×{n}", (rx + 10, r2.y + T.S * 5 - 5), T.TX_MUTED)
        rx += T.S * 7
    caps(s, F["micro"], "no scout · traps go unseen", (r2.x + T.S * 2,
         r2.y + T.S * 9), T.BRASS)

    r3 = pygame.Rect(r2.right + T.S * 2, y, w, h)
    stat_block(s, F, r3, "supplies", "0 days", T.BLOOD, "no rations · hunger in 6 h")

    r4 = pygame.Rect(r3.right + T.S * 2, y, w, h)
    stat_block(s, F, r4, "condition", "3 hurt", T.BLOOD, "1 at death's door")


def screen_band(size):
    s = pygame.Surface(size).convert()
    s.fill(T.TABLE)
    F = fonts()
    head = pygame.Rect(0, 0, size[0], T.S * 9)
    foot = pygame.Rect(0, size[1] - T.S * 8, size[0], T.S * 8)
    side = pygame.Rect(size[0] - T.S * 46, head.bottom, T.S * 46, foot.y - head.bottom)
    ready = pygame.Rect(0, head.bottom, side.x, T.S * 15)
    table = pygame.Rect(0, ready.bottom, side.x, foot.y - ready.bottom)

    header(s, F, head, BAND["name"],
           f"6 / 10 members  ·  {BAND['where']}  ·  {BAND['state']}",
           ["gear", "quests", "orders"], "gear")
    readiness(s, F, ready)

    pygame.draw.rect(s, T.STEEL, table)
    hd = pygame.Rect(table.x, table.y, table.w, T.S * 3)
    pygame.draw.rect(s, T.TABLE, hd)
    for lab, dx in (("member", T.S * 9), ("condition", T.S * 34), ("equipped", T.S * 44),
                    ("pack", T.S * 96)):
        caps(s, F["micro"], lab, (table.x + dx, hd.centery - 5), T.TX_FAINT)
    caps(s, F["micro"], "load", (table.right - T.S * 3, hd.centery - 5), T.TX_FAINT,
         right=True)
    hline(s, table.x, table.right, hd.bottom)

    y = hd.bottom
    for i, m in enumerate(BAND["members"]):
        member_row(s, F, pygame.Rect(table.x, y, table.w, T.S * 8), m, selected=(i == 1))
        y += T.S * 8
    # lugares vazios: a banda cabe 10
    r = pygame.Rect(table.x, y, table.w, T.S * 6)
    caps(s, F["micro"], "4 empty slots  ·  assign from the guild roster",
         (r.x + T.S * 9, r.centery - 5), T.TX_FAINT)
    hline(s, r.x, r.right, r.bottom - 1)

    band_side(s, F, side, BAND["members"][1])
    footer(s, F, foot, "esc for the pause menu",
           [("distribute load", False), ("back to map", True)])
    return s


# ---------------------------------------------------------------- guilda
def band_card(s, F, rect, b, selected=False):
    pygame.draw.rect(s, T.STEEL_HI if selected else T.STEEL, rect)
    pygame.draw.rect(s, T.BRASS if selected else T.STEEL_LINE, rect, 1)
    pygame.draw.rect(s, b["col"], pygame.Rect(rect.x, rect.y, 3, rect.h))
    x = rect.x + T.S * 2
    caps(s, F["micro"], b["kind"], (x, rect.y + T.S), b["col"])
    text(s, F["name"], b["nm"], (x, rect.y + T.S * 3), T.TX)
    caps(s, F["micro"], b["where"], (x, rect.y + T.S * 6), T.TX_FAINT)

    # vagas como caixinhas: cheio/vazio se le sem numero
    bx = x
    by = rect.bottom - T.S * 4
    for i in range(b["cap"]):
        filled = i < b["n"]
        c = T.TX_MUTED if filled else T.STEEL_LINE
        if filled and i < b["hurt"]:
            c = T.BLOOD
        r = pygame.Rect(bx, by, 8, 10)
        if filled:
            pygame.draw.rect(s, c, r)
        else:
            pygame.draw.rect(s, c, r, 1)
        bx += 11
    caps(s, F["micro"], f"{b['n']}/{b['cap']}", (rect.right - T.S * 2, by), T.TX_FAINT,
         right=True)


def guild_side(s, F, rect):
    pygame.draw.rect(s, T.STEEL, rect)
    pygame.draw.line(s, T.STEEL_LINE, (rect.x, rect.y), (rect.x, rect.bottom), 1)
    x, w = rect.x + T.S * 3, rect.w - T.S * 6
    y = rect.y + T.S * 3
    caps(s, F["micro"], "selected member", (x, y), T.TX_FAINT)
    y += T.S * 2
    text(s, F["nameb"], "Grokhromlysfel", (x, y), T.TX)
    y += T.S * 3
    caps(s, F["micro"], "centaur · priest · Grokvyrdrixek's Band", (x, y), T.TX_FAINT)
    y += T.S * 4

    # level pendente: o unico primario da tela
    r = pygame.Rect(x, y, w, T.S * 7)
    button(s, F, r, "spend 2 level-ups", primary=True, sub="pick abilities and attributes")
    y = r.bottom + T.S * 3

    cw = (w - T.S * 3) // 4
    for i, (lab, val, col) in enumerate((("hp", "1/9", T.BLOOD), ("ac", "12", T.TX),
                                         ("md", "8", T.TX), ("spd", "8", T.TX))):
        b = pygame.Rect(x + i * (cw + T.S), y, cw, T.S * 7)
        pygame.draw.rect(s, T.TABLE, b)
        pygame.draw.rect(s, T.STEEL_LINE, b, 1)
        caps(s, F["micro"], lab, (b.centerx, b.y + T.S + 2), T.TX_FAINT, center=True)
        text(s, F["big"], val, (b.centerx, b.centery + 8), col, center=True)
    y += T.S * 10

    caps(s, F["micro"], "attributes", (x, y), T.TX_FAINT)
    y += T.S * 2
    attrs = [("str", 4, -3), ("dex", 14, 2), ("con", 10, 0),
             ("int", 12, 1), ("wis", 6, -2), ("cha", 6, -2)]
    cw = (w - T.S * 5) // 6
    for i, (lab, val, mod) in enumerate(attrs):
        b = pygame.Rect(x + i * (cw + T.S), y, cw, T.S * 8)
        pygame.draw.rect(s, T.TABLE, b)
        caps(s, F["micro"], lab, (b.centerx, b.y + 6), T.TX_FAINT, center=True)
        text(s, F["bodyb"], str(val), (b.centerx, b.centery - 2), T.TX, center=True)
        caps(s, F["micro"], f"{mod:+d}", (b.bottom and b.centerx, b.bottom - 16),
             T.GREEN if mod > 0 else T.BLOOD if mod < 0 else T.TX_FAINT, center=True)
    y += T.S * 9

    caps(s, F["micro"], "abilities", (x, y), T.TX_FAINT)
    y += T.S * 2
    for nm, desc in (("Gallop", "+3 m (2 squares) of speed"),
                     ("Laying of hands", "heal 1d6, once per rest")):
        text(s, F["bodyb"], nm, (x, y), T.BRASS)
        y += T.S * 2
        text(s, F["micro"], desc, (x, y), T.TX_FAINT)
        y += T.S * 3

    y = rect.bottom - T.S * 17
    hline(s, x, x + w, y)
    y += T.S * 2
    caps(s, F["micro"], "assign to", (x, y), T.TX_FAINT)
    y += T.S * 2
    button(s, F, pygame.Rect(x, y, w, T.S * 5), "move to another band")
    button(s, F, pygame.Rect(x, y + T.S * 6, w, T.S * 5), "send to reserve", ghost=True)


def screen_guild(size):
    s = pygame.Surface(size).convert()
    s.fill(T.TABLE)
    F = fonts()
    head = pygame.Rect(0, 0, size[0], T.S * 9)
    foot = pygame.Rect(0, size[1] - T.S * 8, size[0], T.S * 8)
    side = pygame.Rect(size[0] - T.S * 46, head.bottom, T.S * 46, foot.y - head.bottom)
    main = pygame.Rect(0, head.bottom, side.x, foot.y - head.bottom)

    header(s, F, head, "The Ashen Ledger",
           "70 sworn  ·  8 bands  ·  27 in reserve  ·  standing +2",
           ["bands", "roster", "reputations"], "bands")

    # faixa de pendencias: com 70 membros, isso e o que impede o acumulo invisivel
    alert = pygame.Rect(main.x, main.y, main.w, T.S * 6)
    pygame.draw.rect(s, mix(T.BRASS, T.TABLE, .82), alert)
    pygame.draw.line(s, T.BRASS, (alert.x, alert.y), (alert.x, alert.bottom), 3)
    caps(s, F["microb"], "5 members are ready to level", (alert.x + T.S * 3,
         alert.centery - 12), T.BRASS)
    caps(s, F["micro"], "3 hurt bands have no healer  ·  timber crew idle since 09:00",
         (alert.x + T.S * 3, alert.centery + 2), T.TX_FAINT)
    button(s, F, pygame.Rect(alert.right - T.S * 22, alert.y + T.S, T.S * 19,
                             alert.h - T.S * 2), "review all")

    y = alert.bottom + T.S * 3
    caps(s, F["micro"], "bands by purpose", (main.x + T.S * 3, y), T.TX_FAINT)
    caps(s, F["micro"], "drag a member between cards to reassign",
         (main.right - T.S * 3, y), T.TX_FAINT, right=True)
    y += T.S * 3

    cols, gap = 3, T.S * 2
    cw = (main.w - T.S * 6 - gap * (cols - 1)) // cols
    ch = T.S * 12
    for i, b in enumerate(BANDS):
        r = pygame.Rect(main.x + T.S * 3 + (i % cols) * (cw + gap),
                        y + (i // cols) * (ch + gap), cw, ch)
        band_card(s, F, r, b, selected=(i == 0))

    ry = y + ((len(BANDS) + cols - 1) // cols) * (ch + gap)
    res = pygame.Rect(main.x + T.S * 3, ry, main.w - T.S * 6, T.S * 11)
    pygame.draw.rect(s, T.STEEL, res)
    pygame.draw.rect(s, T.STEEL_LINE, res, 1)
    caps(s, F["micro"], "reserve", (res.x + T.S * 2, res.y + T.S), T.TX_FAINT)
    text(s, F["name"], f"{RESERVE} unassigned", (res.x + T.S * 2, res.y + T.S * 3), T.TX)
    caps(s, F["micro"], "eating rations, doing nothing",
         (res.x + T.S * 2, res.y + T.S * 6 + 2), T.BRASS)
    # fileira de fichinhas: a reserva e um monte, nao uma lista
    px = res.x + T.S * 26
    for i in range(RESERVE):
        c = T.BLOOD if i < 4 else T.TX_FAINT
        pygame.draw.rect(s, c, pygame.Rect(px + (i % 14) * 12, res.y + T.S * 2 +
                                           (i // 14) * 14, 8, 10))
    caps(s, F["micro"], "4 hurt", (px + 14 * 12 + T.S * 2, res.y + T.S * 2), T.BLOOD)

    guild_side(s, F, side)
    footer(s, F, foot, "esc for the pause menu",
           [("hire  ·  3", False), ("back to map", True)])
    return s


# ---------------------------------------------------------------- main
def main():
    pygame.init()
    size = (1600, 900)
    if "--shot" in sys.argv:
        pygame.display.set_mode(size, pygame.HIDDEN)
        pygame.image.save(screen_band(size), "gartok_v4_band.png")
        pygame.image.save(screen_guild(size), "gartok_v4_guild.png")
        pygame.quit()
        return
    win = pygame.display.set_mode(size)
    frames = [screen_band(size), screen_guild(size)]
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
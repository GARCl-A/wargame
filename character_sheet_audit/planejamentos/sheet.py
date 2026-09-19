"""
GARTOK Tactical - sheet.py
A ficha de personagem como UM componente, usado pelas 5 telas.

    draw_sheet(surf, rect, ch, density)   -> altura consumida
    draw_row(surf, rect, ch, ...)         -> a linha de lista (guilda, banda)

Regras do sistema:
  1. ORDEM CANONICA. Os blocos sempre saem nesta ordem. Uma tela corta
     blocos, nunca reordena. Assim o olho aprende onde procurar cada coisa
     e nunca reaprende.
  2. TRES DENSIDADES. Cada densidade ja define quais blocos entram e a
     ALTURA FIXA de cada um. Altura fixa = cards do draft alinham sozinhos.
  3. EDICAO so no character creator (density FULL + editable=True). Level-up
     e outra tela e nao usa este componente em modo edicao.

Quem usa o que:
  guild list / band rail ......... draw_row
  band column / draft card ....... NORMAL
  battle inspect ................. COMPACT
  sheet modal / char creator ..... FULL
"""

import sys

import pygame

from screens_v4 import (T, fonts, mix, text, caps, hline, hp_color)

# ---------------------------------------------------------------- ordem
ORDER = ["identity", "status", "vitals", "attributes", "weapon", "gear",
         "languages", "ability"]

# blocos por densidade (corte, nunca reordenacao)
BLOCKS = {
    "compact": ["identity", "vitals", "attributes", "weapon", "gear"],
    "normal":  ["identity", "status", "vitals", "attributes", "weapon", "gear",
                "ability"],
    "full":    ORDER,
}

# altura fixa de cada bloco por densidade. e isto que faz cards alinharem.
H = {
    "compact": dict(identity=T.S * 5, vitals=T.S * 4, attributes=T.S * 4,
                    weapon=T.S * 6, gear=T.S * 5),
    "normal":  dict(identity=T.S * 6, status=T.S * 3, vitals=T.S * 8,
                    attributes=T.S * 8, weapon=T.S * 8, gear=T.S * 6,
                    ability=T.S * 9),
    "full":    dict(identity=T.S * 8, status=T.S * 3, vitals=T.S * 10,
                    attributes=T.S * 10, weapon=T.S * 9, gear=T.S * 14,
                    languages=T.S * 5, ability=T.S * 9),
}

GAP = {"compact": T.S, "normal": T.S * 2, "full": T.S * 2}


def sheet_height(density):
    return sum(H[density][b] for b in BLOCKS[density]) + \
        GAP[density] * (len(BLOCKS[density]) - 1)


# ---------------------------------------------------------------- helpers
def block_label(s, F, x, y, label):
    caps(s, F["micro"], label, (x, y), T.TX_FAINT)
    return y + T.S * 2


def cell(s, F, rect, label, value, color=T.TX, label_color=None, small=False):
    pygame.draw.rect(s, T.TABLE, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    caps(s, F["micro"], label, (rect.centerx, rect.y + 7), label_color or T.TX_FAINT,
         center=True)
    f = F["bodyb"] if small else F["big"]
    text(s, f, str(value), (rect.centerx, rect.centery + (3 if small else 7)),
         color, center=True)
    return rect


def stepper(s, F, rect):
    """Controle de edicao. So aparece com editable=True (character creator)."""
    for i, sign in enumerate(("–", "+")):
        b = pygame.Rect(rect.x + i * (rect.w // 2), rect.bottom - T.S * 2 - 2,
                        rect.w // 2, T.S * 2 + 2)
        pygame.draw.rect(s, T.STEEL_LINE, b, 1)
        caps(s, F["micro"], sign, b.center, T.TX_MUTED, center=True)


# ---------------------------------------------------------------- blocos
def b_identity(s, F, r, ch, d, ed):
    if d == "compact":
        text(s, F["bodyb"], ch["name"], (r.x, r.y), T.TX)
        caps(s, F["micro"], f"{ch['race']} · {ch['occ']}", (r.x, r.y + T.S * 2 + 2),
             T.TX_FAINT)
        return
    # retrato: disco com a inicial. barato e identifica na lista e no card.
    d_r = T.S * 3 if d == "normal" else T.S * 4
    cx, cy = r.x + d_r, r.y + d_r
    pygame.draw.circle(s, T.STEEL_HI, (cx, cy), d_r)
    pygame.draw.circle(s, T.STEEL_LINE, (cx, cy), d_r, 1)
    text(s, F["nameb"], ch["name"][0], (cx, cy), T.BRASS, center=True)
    x = r.x + d_r * 2 + T.S * 2
    text(s, F["titleb"] if d == "full" else F["nameb"], ch["name"], (x, r.y), T.TX)
    caps(s, F["micro"], f"{ch['race']} · {ch['occ']}", (x, r.y + T.S * 3 + 4),
         T.TX_MUTED)
    if d == "full":
        caps(s, F["micro"],
             f"{ch['align']} · {ch['size']} · {ch['age']} yrs · combat {ch['combat']}",
             (x, r.y + T.S * 5 + 4), T.TX_FAINT)
    if ed:
        caps(s, F["micro"], "edit", (r.right, r.y + 4), T.BRASS, right=True)


def b_status(s, F, r, ch, d, ed):
    x = r.x
    for tag in ch["status"]:
        w = F["micro"].size(tag.upper())[0] + T.S * 2
        box = pygame.Rect(x, r.y, w, T.S * 2 + 4)
        pygame.draw.rect(s, mix(T.BLOOD, T.TABLE, .7), box)
        pygame.draw.rect(s, T.BLOOD, box, 1)
        caps(s, F["micro"], tag, box.center, T.BLOOD, center=True)
        x += w + T.S
    for tag in ch["tags"]:
        w = F["micro"].size(tag.upper())[0] + T.S * 2
        box = pygame.Rect(x, r.y, w, T.S * 2 + 4)
        pygame.draw.rect(s, T.STEEL_LINE, box, 1)
        caps(s, F["micro"], tag, box.center, T.TX_MUTED, center=True)
        x += w + T.S


VITALS = [("hp", T.GREEN), ("ac", T.TX), ("md", T.BRASS), ("spd", T.TX)]


def b_vitals(s, F, r, ch, d, ed):
    vals = dict(hp=f"{ch['hp'][0]}", ac=ch["ac"], md=ch["md"], spd=ch["spd"])
    keys = VITALS + ([("init", T.TX_MUTED)] if d == "full" else [])
    if d == "full":
        vals["init"] = ch["init"]
    if d == "compact":
        x = r.x
        for k, col in keys:
            caps(s, F["micro"], k, (x, r.y + 2), T.TX_FAINT)
            text(s, F["bodyb"], str(vals[k]), (x + T.S * 4, r.y), 
                 hp_color(ch["hp"][0] / ch["hp"][1]) if k == "hp" else T.TX)
            x += T.S * 9
        return
    n = len(keys)
    cw = (r.w - T.S * (n - 1)) // n
    for i, (k, col) in enumerate(keys):
        c = pygame.Rect(r.x + i * (cw + T.S), r.y, cw, r.h)
        cell(s, F, c, k, vals[k], hp_color(ch["hp"][0] / ch["hp"][1])
             if k == "hp" else T.TX, label_color=col)


def b_attributes(s, F, r, ch, d, ed):
    n = len(ch["attrs"])
    if d == "compact":
        x = r.x
        for nm, v, mod in ch["attrs"]:
            caps(s, F["micro"], nm, (x, r.y + 2), T.TX_FAINT)
            text(s, F["body"], f"{v}", (x + T.S * 3, r.y - 1), T.TX)
            caps(s, F["micro"], f"{mod:+d}", (x + T.S * 5 + 4, r.y + 2),
                 T.GREEN if mod > 0 else T.BLOOD if mod < 0 else T.TX_FAINT)
            x += T.S * 8
        return
    cw = (r.w - T.S * (n - 1)) // n
    for i, (nm, v, mod) in enumerate(ch["attrs"]):
        c = pygame.Rect(r.x + i * (cw + T.S), r.y, cw, r.h)
        cell(s, F, c, nm, v, T.TX, small=(d == "normal"))
        caps(s, F["micro"], f"{mod:+d}", (c.centerx, c.bottom - (T.S * 4 if ed else 14)),
             T.GREEN if mod > 0 else T.BLOOD if mod < 0 else T.TX_FAINT, center=True)
        if ed:
            stepper(s, F, c)


def b_weapon(s, F, r, ch, d, ed):
    w = ch["weapon"]
    y = r.y
    if d != "compact":
        y = block_label(s, F, r.x, y, "attack with the weapon in hand")
    text(s, F["bodyb"], w["nm"], (r.x, y), T.TX)
    caps(s, F["micro"], w["tags"], (r.right, y + 2), T.TX_FAINT, right=True)
    y += T.S * 2 + 4
    text(s, F["micro"], f"to hit  {w['hit']}   ·   {w['crit']}", (r.x, y), T.TX_MUTED)
    y += T.S * 2
    text(s, F["micro"], f"damage  {w['dmg']}", (r.x, y), T.TX_MUTED)


def b_gear(s, F, r, ch, d, ed):
    g = ch["gear"]
    cur, norm, high = g["load"]
    y = r.y
    if d == "full":
        y = block_label(s, F, r.x, y, "gear")
        for lab, val in (("hands", g["hands"] or "empty"),
                         ("armor", g["armor"] or "none"),
                         ("pack", ", ".join(g["pack"]) if g["pack"] else "empty")):
            caps(s, F["micro"], lab, (r.x, y + 2), T.TX_FAINT)
            text(s, F["body"], val, (r.x + T.S * 8, y - 1),
                 T.TX_FAINT if val in ("empty", "none") else T.TX_MUTED)
            y += T.S * 2 + 4
        y += 2
    # carga: barra com o limite normal marcado. mesma leitura da tela de grupo.
    bar = pygame.Rect(r.x, y, r.w, 8)
    pygame.draw.rect(s, T.TABLE, bar)
    pygame.draw.rect(s, T.STEEL_LINE, bar, 1)
    ratio = min(cur / high, 1.0)
    over = cur > norm
    pygame.draw.rect(s, T.BLOOD if over else T.GREEN,
                     pygame.Rect(bar.x + 1, bar.y + 1, int((bar.w - 2) * ratio),
                                 bar.h - 2))
    mark = bar.x + int((bar.w - 2) * (norm / high))
    pygame.draw.line(s, T.TX_FAINT, (mark, bar.y - 2), (mark, bar.bottom + 2), 1)
    caps(s, F["micro"], f"load {cur} kg  ·  normal {norm}  ·  high {high}",
         (r.x, bar.bottom + 4), T.BLOOD if over else T.TX_FAINT)
    caps(s, F["micro"], f"{g['copper']} c", (r.right, bar.bottom + 4), T.BRASS,
         right=True)


def b_languages(s, F, r, ch, d, ed):
    y = block_label(s, F, r.x, r.y, "languages")
    text(s, F["body"], ", ".join(ch["langs"]), (r.x, y), T.TX_MUTED)


def b_ability(s, F, r, ch, d, ed):
    nm, desc = ch["ability"]
    y = block_label(s, F, r.x, r.y, "racial ability")
    box = pygame.Rect(r.x, y, r.w, r.bottom - y)
    pygame.draw.rect(s, T.TABLE, box)
    pygame.draw.rect(s, T.STEEL_LINE, box, 1)
    text(s, F["bodyb"], nm, (box.x + T.S, box.y + T.S - 2), T.BRASS)
    # quebra simples em duas linhas
    words, line, ly = desc.split(), "", box.y + T.S * 3
    for wd in words:
        probe = (line + " " + wd).strip()
        if F["micro"].size(probe)[0] <= box.w - T.S * 2:
            line = probe
        else:
            text(s, F["micro"], line, (box.x + T.S, ly), T.TX_FAINT)
            ly += T.S * 2
            line = wd
    text(s, F["micro"], line, (box.x + T.S, ly), T.TX_FAINT)


PAINT = dict(identity=b_identity, status=b_status, vitals=b_vitals,
             attributes=b_attributes, weapon=b_weapon, gear=b_gear,
             languages=b_languages, ability=b_ability)


# ---------------------------------------------------------------- api
def draw_sheet(surf, rect, ch, density="normal", editable=False, only=None):
    """
    Desenha a ficha. `only` corta blocos (sempre na ordem canonica).
    Retorna a altura consumida.
    """
    F = fonts()
    blocks = [b for b in BLOCKS[density] if only is None or b in only]
    y = rect.y
    for i, b in enumerate(blocks):
        h = H[density][b]
        r = pygame.Rect(rect.x, y, rect.w, h)
        PAINT[b](surf, F, r, ch, density, editable)
        y += h + (GAP[density] if i < len(blocks) - 1 else 0)
    return y - rect.y


def draw_row(surf, rect, ch, selected=False, tag=None):
    """A linha de lista: mesma fonte, mesmas cores, mesmo vocabulario."""
    F = fonts()
    pygame.draw.rect(surf, T.STEEL_HI if selected else T.STEEL, rect)
    pygame.draw.rect(surf, T.BRASS if selected else T.STEEL_LINE, rect, 1)
    cx = rect.x + T.S * 3
    pygame.draw.circle(surf, T.STEEL_HI, (cx, rect.centery), T.S * 2)
    pygame.draw.circle(surf, T.STEEL_LINE, (cx, rect.centery), T.S * 2, 1)
    text(surf, F["micro"], ch["name"][0], (cx, rect.centery), T.BRASS, center=True)
    text(surf, F["name"], ch["name"], (rect.x + T.S * 6, rect.centery - 16), T.TX)
    caps(surf, F["micro"], f"{ch['race']} · {ch['occ']}",
         (rect.x + T.S * 6, rect.centery + 4), T.TX_FAINT)
    cur, mx = ch["hp"]
    caps(surf, F["micro"], f"hp {cur}   ac {ch['ac']}   {ch['gear']['load'][0]} kg",
         (rect.right - T.S * 2, rect.centery - 14), T.TX_MUTED, right=True)
    if ch["status"]:
        caps(surf, F["micro"], ch["status"][0], (rect.right - T.S * 2,
             rect.centery + 2), T.BLOOD, right=True)
    if tag:
        caps(surf, F["micro"], tag, (rect.x + T.S * 6 +
             F["micro"].size(f"{ch['race']} · {ch['occ']}".upper())[0] + T.S * 2,
             rect.centery + 4), T.BRASS)


# ---------------------------------------------------------------- demo
CH = dict(name="Tordundorir", race="Dwarf", occ="Linguist",
          align="Neutral and Good", size="Medium", age=165, combat="N0",
          hp=(4, 4), ac=9, md=9, spd=6, init="+1",
          attrs=[("str", 11, -1), ("dex", 11, -1), ("con", 10, -1),
                 ("int", 13, 0), ("wis", 14, 1), ("cha", 8, -2)],
          weapon=dict(nm="Dagger", hit="d20 -1 (STR/DEX)", dmg="1d4 -1 (STR)",
                      tags="melee · 1 hand · thrown 6", crit="crit 20, fumble 1"),
          gear=dict(hands="Dagger", armor=None, pack=[], load=(0.5, 11, 29),
                    copper=34),
          langs=["Dwarvish"], ability=("Darkvision",
                                       "sees 12 squares in the dark as if it were lit"),
          status=["hungry"], tags=["lead"])

CH2 = dict(CH, name="Skeltorma", occ="Jailer", hp=(9, 9), ac=8, md=10, spd=5,
           attrs=[("str", 14, 2), ("dex", 9, -1), ("con", 13, 1),
                  ("int", 10, 0), ("wis", 8, -1), ("cha", 12, 1)],
           weapon=dict(nm="Hammer", hit="d20 +2 (STR)", dmg="1d8 +2 (STR)",
                       tags="melee · 1 hand", crit="crit 20, fumble 1"),
           gear=dict(hands="Hammer", armor="Mail", pack=["Rope"], load=(5.5, 14, 32),
                     copper=12),
           ability=("Stonecunning", "notices unsound rock and worked stone"),
           status=[], tags=["guild leader"])

CH3 = dict(CH, name="Braedralel", occ="Thief", hp=(5, 6), ac=10, md=9, spd=7,
           attrs=[("str", 8, -1), ("dex", 16, 3), ("con", 10, 0),
                  ("int", 12, 1), ("wis", 11, 0), ("cha", 13, 1)],
           weapon=dict(nm="Shortbow", hit="d20 +3 (DEX)", dmg="1d6 (DEX)",
                       tags="ranged 16 · 2 hands", crit="crit 20, fumble 1"),
           gear=dict(hands="Shortbow", armor="Leather", pack=["Lockpicks"],
                     load=(2.5, 9, 24), copper=31),
           ability=("Nimble", "ignores the first square of difficult ground"),
           status=[], tags=[])


def demo_catalog(size):
    s = pygame.Surface(size).convert()
    s.fill(T.TABLE)
    F = fonts()
    caps(s, F["microb"], "one component  ·  three densities  ·  fixed block order",
         (T.S * 4, T.S * 3), T.TX_MUTED)
    caps(s, F["micro"], "a screen cuts blocks, never reorders them  ·  block heights "
         "are fixed per density, so cards align", (T.S * 4, T.S * 6), T.TX_FAINT)

    tops = T.S * 12
    labels = [("compact", "battle inspect  ·  tooltips", T.S * 4, T.S * 52),
              ("normal", "draft card  ·  band column  ·  guild panel", T.S * 60,
               T.S * 52),
              ("full", "sheet modal  ·  character creator", T.S * 116, T.S * 60)]
    for d, use, x, w in labels:
        panel = pygame.Rect(x, tops, w, sheet_height(d) + T.S * 6)
        pygame.draw.rect(s, T.STEEL, panel)
        pygame.draw.rect(s, T.BRASS if d == "full" else T.STEEL_LINE, panel, 1)
        caps(s, F["microb"], d, (panel.x + T.S * 3, panel.y - T.S * 4), T.BRASS)
        caps(s, F["micro"], use, (panel.x + T.S * 13, panel.y - T.S * 4 + 1),
             T.TX_FAINT)
        draw_sheet(s, pygame.Rect(panel.x + T.S * 3, panel.y + T.S * 3,
                                  panel.w - T.S * 6, 0), CH, d,
                   editable=(d == "full"))
        caps(s, F["micro"], f"{sheet_height(d)} px  ·  "
             f"{len(BLOCKS[d])} blocks", (panel.x + T.S * 3, panel.bottom + T.S),
             T.TX_FAINT)

    # a linha de lista, o quarto uso
    y = tops + sheet_height("compact") + T.S * 14
    caps(s, F["microb"], "row", (T.S * 4, y - T.S * 3), T.BRASS)
    caps(s, F["micro"], "guild list  ·  band rail", (T.S * 10, y - T.S * 3 + 1),
         T.TX_FAINT)
    for i, c in enumerate((CH, CH2, CH3)):
        draw_row(s, pygame.Rect(T.S * 4, y + i * (T.S * 8), T.S * 52, T.S * 7), c,
                 selected=(i == 0), tag=(c["tags"][0] if c["tags"] else None))
    return s


def demo_draft(size):
    """Prova do alinhamento: tres fichas NORMAL lado a lado, blocos casados."""
    s = pygame.Surface(size).convert()
    s.fill(T.TABLE)
    F = fonts()
    text(s, F["titleb"], "Squad draft", (T.S * 4, T.S * 3), T.TX)
    caps(s, F["micro"], "round 1 of 3  ·  pick 1 of 3  ·  the same component, "
         "density normal", (T.S * 4, T.S * 8), T.TX_FAINT)

    gap = T.S * 3
    cw = (size[0] - T.S * 8 - gap * 2) // 3
    top = T.S * 14
    for i, c in enumerate((CH, CH2, CH3)):
        r = pygame.Rect(T.S * 4 + i * (cw + gap), top, cw,
                        sheet_height("normal") + T.S * 12)
        pygame.draw.rect(s, T.STEEL, r)
        pygame.draw.rect(s, T.BRASS if i == 0 else T.STEEL_LINE, r, 1)
        draw_sheet(s, pygame.Rect(r.x + T.S * 3, r.y + T.S * 3, r.w - T.S * 6, 0),
                   c, "normal")
        b = pygame.Rect(r.x + T.S * 3, r.bottom - T.S * 7, r.w - T.S * 6, T.S * 5)
        if i == 0:
            pygame.draw.rect(s, T.BRASS, b)
            caps(s, F["microb"], "pick", b.center, T.TABLE, center=True)
        else:
            pygame.draw.rect(s, T.STEEL_LINE, b, 1)
            caps(s, F["microb"], "click to pick", b.center, T.TX_FAINT, center=True)
    # guias horizontais provando o alinhamento
    y = top + T.S * 3
    for blk in BLOCKS["normal"]:
        hline(s, T.S * 4, size[0] - T.S * 4, y - 3, mix(T.BRASS, T.TABLE, .86))
        caps(s, F["micro"], blk, (size[0] - T.S * 3, y - 8), T.TX_FAINT, right=True)
        y += H["normal"][blk] + GAP["normal"]
    return s


def main():
    pygame.init()
    size = (1600, 900)
    if "--shot" in sys.argv:
        pygame.display.set_mode(size, pygame.HIDDEN)
        pygame.image.save(demo_catalog(size), "gartok_sheet_catalog.png")
        pygame.image.save(demo_draft(size), "gartok_sheet_draft.png")
        pygame.quit()
        return
    win = pygame.display.set_mode(size)
    frames = [demo_catalog(size), demo_draft(size)]
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
